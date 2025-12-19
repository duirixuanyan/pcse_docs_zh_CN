# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""PCSE 引擎提供了 SimulationObjects 存活的环境。
该引擎负责读取模型配置、初始化模型组件（例如 SimulationObjects 组），
通过调用 SimulationObjects 驱动仿真向前推进，调用农事管理单元，
跟踪时间并提供所需的气象数据。

模型与引擎一起处理，因为模型实际上就是预配置好的引擎。
任何模型都可以通过使用合适的配置文件启动引擎来开始仿真。
唯一的区别在于模型可以包含处理其特定特性的函数方法。
这种特定于模型的功能不能在引擎中实现，因为在此之前模型细节尚不可知。
"""
import os, sys
import datetime
import gc

from .traitlets import Instance, Bool, List, Dict
from .base import (VariableKiosk, WeatherDataProvider,
                           AncillaryObject, SimulationObject,
                           BaseEngine, ParameterProvider)
from .util import check_date
from .base import ConfigurationLoader
from .timer import Timer
from . import signals
from . import exceptions as exc
from .settings import settings


class Engine(BaseEngine):
    """用于模拟土壤/作物系统的仿真引擎。

    :param parameterprovider: 提供模型参数（键/值对）的 ParameterProvider 对象。
        parameterprovider 封装了作物、土壤和地点参数的不同参数集。
    :param weatherdataprovider: WeatherDataProvider 的一个实例，
        可以为指定日期返回 WeatherDataContainer 中的气象数据。
    :param agromanagement: 农事管理数据。该数据格式在农事管理部分有描述。
    :param config: 指定模型配置文件的字符串。
        仅提供文件名时，PCSE 假定它位于主 PCSE 文件夹下的 'conf/' 文件夹中。
        如果要提供自定义配置文件，请将其指定为绝对路径或相对路径（如以 '.' 开头）。
    :param output_vars: 需要添加/替换到 OUTPUT_VARS 配置变量中的变量名
    :param summary_vars: 需要添加/替换到 SUMMARY_OUTPUT_VARS 配置变量中的变量名
    :param terminal_vars: 需要添加/替换到 TERMINAL_OUTPUT_VARS 配置变量中的变量名

    `Engine` 负责实际仿真土壤-作物系统。其核心是持续进行土壤水分平衡的仿真。
    与之对照，`CropSimulation` 对象只会在收到农事管理单元的 "CROP_START" 信号后初始化。
    从此刻起，模拟土壤-作物系统的相互作用（如根系生长和蒸腾等）。
    
    同理，在收到 "CROP_FINISH" 信号时，作物仿真会被结束。
    此时将会执行其 `finalize()` 部分。此外，"CROP_FINISH" 信号还可以指定
    是否从系统中删除该作物仿真对象。这对于扩展 PCSE、实现轮作等功能是有用的。
    
    最终，在收到 "TERMINATE" 信号时，整个仿真会结束。
    此时将执行水分平衡模块的 `finalize()` 部分，仿真终止。

    **Engine 处理的信号如下：**
    
    `Engine` 会处理下列信号：
        * CROP_START：启动一个 `CropSimulation` 实例进行作物生长仿真。
          详见 `_on_CROP_START` 处理函数。
        * CROP_FINISH：运行某个 `CropSimulation` 实例的 `finalize()`，
          并可选地将其删除。详见 `_on_CROP_FINISH` 处理函数。
        * TERMINATE：运行水分平衡模块的 `finalize()`，并终止整个仿真。
          详见 `_on_TERMINATE` 处理函数。
        * OUTPUT：在仿真过程中保存选定状态或速率变量的副本以备后用。
          详见 `_on_OUTPUT` 处理函数。
        * SUMMARY_OUTPUT：保存选定状态或速率变量的副本，通常仅在作物仿真结束时请求输出。
          详见 `_on_SUMMARY_OUTPUT` 处理函数。

    """
    # 系统配置
    mconf = Instance(ConfigurationLoader)
    parameterprovider = Instance(ParameterProvider)

    # 仿真子组件
    crop = Instance(SimulationObject)
    soil = Instance(SimulationObject)
    agromanager = Instance(AncillaryObject)
    weatherdataprovider = Instance(WeatherDataProvider)
    drv = None
    kiosk = Instance(VariableKiosk)
    timer = Instance(Timer)
    day = Instance(datetime.date)

    # 由信号设置的标志位
    flag_terminate = Bool(False)
    flag_crop_finish = Bool(False)
    flag_crop_start = Bool(False)
    flag_crop_delete = Bool(False)
    flag_output = Bool(False)
    flag_summary_output = Bool(False)
    
    # 在模型执行过程中保存变量的占位符
    _saved_output = List()
    _saved_summary_output = List()
    _saved_terminal_output = Dict()

    def __init__(self, parameterprovider, weatherdataprovider, agromanagement, config=None,
                 output_vars=None, summary_vars=None, terminal_vars=None):

        BaseEngine.__init__(self)

        # 加载模型配置文件
        if config is not None:
            self.mconf = ConfigurationLoader(config)
        elif hasattr(self, "config"):
            self.mconf = ConfigurationLoader(self.config)
        else:
            msg = "No model configuration file. Specify model configuration file with " \
                  "`config=<path_to_config_file>` in the call to Engine()."
            raise exc.PCSEError(msg)
        self.mconf.update_output_variable_lists(output_vars, summary_vars, terminal_vars)

        self.parameterprovider = parameterprovider

        # 用于注册和发布变量的变量管理台
        self.kiosk = VariableKiosk()

        # 在模型运行过程中用于保存变量的占位符
        self._saved_output = list()
        self._saved_summary_output = list()
        self._saved_terminal_output = dict()

        # 注册各类信号的处理函数，如作物仿真启动/结束、输出与系统终止等
        self._connect_signal(self._on_CROP_START, signal=signals.crop_start)
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)
        self._connect_signal(self._on_OUTPUT, signal=signals.output)
        self._connect_signal(self._on_TERMINATE, signal=signals.terminate)

        # 农业管理组件
        self.agromanager = self.mconf.AGROMANAGEMENT(self.kiosk, agromanagement)
        start_date = self.agromanager.start_date
        end_date = self.agromanager.end_date

        # 定时器：仿真起始日、结束日及模型输出
        self.timer = Timer(self.kiosk, start_date, end_date, self.mconf)
        self.day, delt = self.timer()

        # 驱动变量
        self.weatherdataprovider = weatherdataprovider
        self.drv = self._get_driving_variables(self.day)

        # 土壤过程模拟组件
        if self.mconf.SOIL is not None:
            self.soil = self.mconf.SOIL(self.day, self.kiosk, parameterprovider)

        # 模型初始化时调用农业管理组件进行管理操作
        self.agromanager(self.day, self.drv)

        # 计算初始的速率变量
        self.calc_rates(self.day, self.drv)

    def calc_rates(self, day, drv):

        # 对各个子组件计算速率
        if self.crop is not None:
            self.crop.calc_rates(day, drv)

        if self.soil is not None:
            self.soil.calc_rates(day, drv)

        # 保存模型的状态变量
        if self.flag_output:
            self._save_output(day)

        # 检查是否需要结束作物仿真
        if self.flag_crop_finish:
            self._finish_cropsimulation(day)

    def integrate(self, day, delt):

        # 在状态变量更新前从kiosk清空状态变量
        self.kiosk.flush_states()

        if self.crop is not None:
            self.crop.integrate(day, delt)

        if self.soil is not None:
            self.soil.integrate(day, delt)

        # 将所有速率变量设为零
        if settings.ZEROFY:
            self.zerofy()

        # 在状态变量更新后从kiosk清空速率变量
        self.kiosk.flush_rates()

    def _run(self):
        """执行一步仿真时间步。"""

        # 更新定时器
        self.day, delt = self.timer()

        # 状态积分
        self.integrate(self.day, delt)

        # 获取驱动变量
        self.drv = self._get_driving_variables(self.day)

        # 执行农业管理决策
        self.agromanager(self.day, self.drv)

        # 计算速率
        self.calc_rates(self.day, self.drv)

        if self.flag_terminate is True:
            self._terminate_simulation(self.day)

    def run(self, days=1):
        """将系统状态推进指定天数"""

        days_done = 0
        while (days_done < days) and (self.flag_terminate is False):
            days_done += 1
            self._run()

    def run_till_terminate(self):
        """运行系统直到收到终止信号为止。"""

        while self.flag_terminate is False:
            self._run()

    def run_till(self, rday):
        """运行系统直到到达指定日期 rday。"""

        try:
            rday = check_date(rday)
        except KeyError as e:
            msg = "run_till() function needs a date object as input"
            print(msg)
            return

        if rday <= self.day:
            msg = "date argument for run_till() function before current model date."
            print(msg)
            return

        while self.flag_terminate is False and self.day < rday:
            self._run()

    def _on_CROP_FINISH(self, day, crop_delete=False):
        """当收到CROP_FINISH信号时，将变量'flag_crop_finish'设为True。
        
        需要该标志的原因是结束作物仿真会延后到处理循环中的合适位置，由_routine _finish_cropsimulation()处理。
        
        如果crop_delete=True，那么CropSimulation对象会在_finish_cropsimulation()中从系统中删除。

        最后，根据conf.SUMMARY_OUTPUT_VARS生成汇总输出。
        """
        self.flag_crop_finish = True
        self.flag_crop_delete = crop_delete

    def _on_CROP_START(self, day, crop_name=None, variety_name=None,
                       crop_start_type=None, crop_end_type=None):
        """开始作物"""
        self.logger.debug("Received signal 'CROP_START' on day %s" % day)

        # 如果已有作物模拟对象，抛出异常（提示用户未先完成前一个作物的仿真）
        if self.crop is not None:
            msg = ("A CROP_START signal was received while self.cropsimulation "
                   "still holds a valid cropsimulation object. It looks like "
                   "you forgot to send a CROP_FINISH signal with option "
                   "crop_delete=True")
            raise exc.PCSEError(msg)

        # 根据提供的参数设置当前作物
        self.parameterprovider.set_active_crop(crop_name, variety_name, crop_start_type,
                                               crop_end_type)
        # 创建作物仿真对象
        self.crop = self.mconf.CROP(day, self.kiosk, self.parameterprovider)

    def _on_TERMINATE(self):
        """接收到TERMINATE信号时，将变量'flag_terminate'设为True。"""
        self.flag_terminate = True
        
    def _on_OUTPUT(self):
        """接收到OUTPUT信号时，将变量'flag_output'设为True。"""
        self.flag_output = True
        
    def _finish_cropsimulation(self, day):
        """当'flag_crop_finish'变量因收到'CROP_FINISH'信号被设置为True时，完成作物仿真对象。"""
        self.flag_crop_finish = False

        # 执行作物仿真对象及其子组件的finalize阶段
        self.crop.finalize(day)

        # finalize()执行后生成汇总输出
        self._save_summary_output()

        # 清除ParameterProvider中的任何覆盖参数，避免影响下一个作物
        self.parameterprovider.clear_override()

        # 仅在明确要求的情况下，从系统中删除作物仿真对象
        if self.flag_crop_delete:
            self.flag_crop_delete = False
            self.crop._delete()
            self.crop = None
            # 执行专用的垃圾回收，因为标准python GC未能回收作物仿真对象，会导致应被删除的对象仍然接收信号
            gc.collect()

    def _terminate_simulation(self, day):
        """终止整个仿真过程。

        首先执行土壤组件的finalize()方法。
        接着收集并保存TERMINAL_OUTPUT。
        """

        if self.soil is not None:
            self.soil.finalize(self.day)
        self._save_terminal_output()

    def _get_driving_variables(self, day):
        """获取驱动变量，计算相关属性并返回。"""
        drv = self.weatherdataprovider(day)
        
        # 计算平均温度和平均日温度（如需要）
        if not hasattr(drv, "TEMP"):
            drv.add_variable("TEMP", (drv.TMIN + drv.TMAX)/2., "Celcius")
        if not hasattr(drv, "DTEMP"):
            drv.add_variable("DTEMP", (drv.TEMP + drv.TMAX)/2., "Celcius")

        return drv

    def _save_output(self, day):
        """将指定的模型变量结果添加到self._saved_output，用于保存当天的输出。"""
        # 关闭生成输出的标志位
        self.flag_output = False

        # 查找并保存需要保存的变量的当前值
        states = {"day":day}
        for var in self.mconf.OUTPUT_VARS:
            states[var] = self.get_variable(var)
        self._saved_output.append(states)

    def _save_summary_output(self):
        """将指定的模型变量结果添加到self._saved_summary_output，用于保存汇总输出。"""
        # 查找并保存需要保存的变量的当前值
        states = {}
        for var in self.mconf.SUMMARY_OUTPUT_VARS:
            states[var] = self.get_variable(var)
        self._saved_summary_output.append(states)

    def _save_terminal_output(self):
        """将指定的模型变量结果添加到self._saved_terminal_output，便于终端输出。"""
        # 查找并保存需要保存的变量的当前值
        for var in self.mconf.TERMINAL_OUTPUT_VARS:
            self._saved_terminal_output[var] = self.get_variable(var)

    def set_variable(self, varname, value):
        """设置指定状态变量或速率变量的值。

        :param varname: 要更新的变量名称（字符串）。
        :param value: 变量要更新为的值（浮点数）

        :returns: 返回一个包含被更新变量增量（新值-旧值）的字典。如果未能找到类方法（见下文），则返回一个空字典。

        注意，“设置”一个变量（如更新模型状态）通常比“获取”一个变量要复杂得多，因为通常还需要更新其他内部变量（如校验和、相关状态变量）等。由于没有通用的规则来“设置”变量，因此由模型设计者实现合适的代码来执行变量的更新。

        `set_variable()` 的实现方式如下：首先会递归查找仿真对象上名称为 `_set_variable_<varname>`（区分大小写）的类方法。如果找到该方法，将以 value 作为参数调用。

        例如，要将作物叶面积指数（变量名“LAI”）更新为5.0，可以这样调用：`set_variable('LAI', 5.0)`。在内部，这个调用会查找名为 `_set_variable_LAI` 的类方法，并以5.0为参数执行。
        """
        increments = {}
        if self.soil is not None:
            self.soil.set_variable(varname, value, increments)
        if self.crop is not None:
            self.crop.set_variable(varname, value, increments)

        return increments

    def get_output(self):
        """返回模拟过程中存储的变量。

        如果没有存储任何输出，则返回一个空列表。否则，输出按时间顺序以字典列表的形式返回。每个字典是一组特定日期存储的模型变量。"""

        return self._saved_output

    def get_summary_output(self):
        """返回模拟过程中存储的汇总变量。"""

        return self._saved_summary_output

    def get_terminal_output(self):
        """返回模拟过程中存储的终端输出变量。"""

        return self._saved_terminal_output


class CGMSEngine(Engine):
    """用于模拟CGMS行为的Engine。

    原始CGMS在作物生长周期结束后并不会终止仿真，而是继续仿真周期，但不再改变crop和soil组件。
    这导致作物周期结束后，所有状态变量都保持不变，天数计数器继续增加。
    这种行为有两个好处：

    1. CGMS通常输出旬（dekad）结果，如果成熟日或收获日不是旬的边界，最终模拟值依然会在下一个旬存储。
    2. 当聚合有成熟日或收获日变异的空间仿真时，能保证数据库表中有记录，因此SQL中的GroupBy子句在计算空间平均时可得出正确结果。

    与Engine的区别：

    1. 不支持轮作
    2. 接收到CROP_FINISH信号后，Engine会继续，仅更新时间计数器，soil、crop和agromanagement不会执行仿真循环。
       因此，所有状态变量保持其值不变。
    3. TERMINATE信号无效。
    4. CROP_FINISH信号不会删除CROP SimulationObject。
    5. 不支持run()和run_till_terminate()，只支持run_till()。
    """

    flag_crop_finish = False
    # 由于CGMSEngine的设计目的，flag_crop_delete总是False
    flag_crop_delete = False

    def run(self, days=1):
        msg = "run() is not supported in the CGMSEngine, use: run_till(<date>)"
        raise NotImplementedError(msg)

    def run_till_terminate(self):
        msg = "run_till_terminate() is not supported in the CGMSEngine, use: run_till(<date>)"
        raise NotImplementedError(msg)

    def run_till(self, rday):
        """运行系统直到rday为止。"""

        try:
            rday = check_date(rday)
        except KeyError as e:
            msg = "run_till() function needs a date object as input"
            print(msg)
            return

        if rday <= self.day:
            msg = "date argument for run_till() function before current model date."
            print(msg)
            return

        while self.day < rday:
            self._run()

    def _run(self):
        """执行仿真的一个时间步。"""

        # 更新时间计数器
        self.day, delt = self.timer()

        if self.flag_crop_finish is False:
            # 状态变量积分
            self.integrate(self.day, delt)

            # 驱动变量
            self.drv = self._get_driving_variables(self.day)

            # 农业管理决策
            self.agromanager(self.day, self.drv)

            # 速率计算
            self.calc_rates(self.day, self.drv)

        elif self.flag_crop_finish is True:
            # 执行crop和soil仿真以及子组件的finalize方法
            if self.crop is not None:
                self.crop.finalize(self.day)
            if self.soil is not None:
                self.soil.finalize(self.day)

            # finalize()后生成汇总输出
            self._save_summary_output()

            # 设置self.flag_crop_finish为None，表示仿真循环不应继续
            self.flag_crop_finish = None

            # 如果设置了flag_output，仍然保留输出
            if self.flag_output:
                self._save_output(self.day)
        else:
            # 什么都不做，但如果设置了flag_output，仍然保留输出
            if self.flag_output:
                self._save_output(self.day)

    def _on_CROP_FINISH(self, day, *args, **kwargs):
        """当接收到CROP_FINISH信号时，将变量'flag_crop_finish'设置为True。"""
        self.flag_crop_finish = True

    def _on_TERMINATE(self):
        """TERMINATE未在CGMS Engine中实现。此方法仅用于拦截TERMINATE信号。"""
        pass

    def _finish_cropsimulation(self, day):
        """该功能已在_run()中实现。

        该方法仅用于拦截来自calc_rates()的_finish_cropsimulation()调用。
        """
        pass