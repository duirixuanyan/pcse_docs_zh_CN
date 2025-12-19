# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
"""在PCSE中实现AgroManager和相关类，以支持农事管理操作。

可用的类：

  * CropCalendar: 用于处理作物历的类
  * TimedEventDispatcher: 用于处理定时事件（例如与日期相关的事件）的类
  * StateEventDispatcher: 用于处理状态事件（例如当状态变量达到某个值时发生的事件）的类
  * AgroManager: 用于处理所有农事管理事件的类，封装了CropCalendar和定时/状态事件。
"""

from datetime import date, timedelta
import logging
from collections import Counter

from .base import DispatcherObject, VariableKiosk, SimulationObject, ParameterProvider, AncillaryObject
from .traitlets import HasTraits, Float, Int, Instance, Enum, Bool, List, Dict, Unicode
from . import exceptions as exc
from .base import ConfigurationLoader
from . import signals
from . import exceptions as exc


def cmp2(x, y):
    """
    比较两个值并返回其符号

    用于替代Python2中的cmp()函数
    """
    return (x > y) - (x < y)


def check_date_range(day, start, end):
    """如果 start <= day < end 则返回True

    end参数可以为None。如果为None，则只要start <= day就返回True

    :param day: 要检查的日期
    :param start: 范围的起始日期
    :param end: 范围的结束日期或None
    :return: True/False
    """

    if end is None:
        return start <= day
    else:
        return start <= day < end
        

def take_first(iterator):
    """返回iterator的第一个元素。"""
    for item in iterator:
        return item


class CropCalendar(HasTraits, DispatcherObject):
    """用于管理作物生长周期的作物历。

    `CropCalendar`对象负责存储、检查、启动和结束作物周期。
    初始化作物历时需提供定义作物周期所需的参数。在每个时间步调用`CropCalendar`的实例，
    并在其参数定义的日期触发相应的操作：

    - 播种/出苗：发送`crop_start`信号，同时包含启动新作物模拟对象所需的参数
    - 成熟/收获：用适当的参数发送`crop_finish`信号，结束作物生长周期

    :param kiosk: PCSE的VariableKiosk实例
    :param crop_name: 表示作物名称的字符串
    :param variety_name: 表示品种名称的字符串
    :param crop_start_date: 作物模拟的开始日期
    :param crop_start_type: 作物模拟的开始类型（'sowing', 'emergence'）
    :param crop_end_date: 作物模拟的结束日期
    :param crop_end_type: 作物模拟的结束类型（'harvest', 'maturity', 'earliest'）
    :param max_duration: 表示作物周期最大持续时间的整数

    :return: CropCalendar实例
    """

    # 作物周期的特征
    crop_name = Unicode()
    variety_name = Unicode()
    crop_start_date = Instance(date)
    crop_start_type = Enum(["sowing", "emergence"])
    crop_end_date = Instance(date)
    crop_end_type = Enum(["maturity", "harvest", "earliest"])
    max_duration = Int()

    # 系统参数
    kiosk = Instance(VariableKiosk)
    parameterprovider = Instance(ParameterProvider)
    mconf = Instance(ConfigurationLoader)
    logger = Instance(logging.Logger)

    # 作物周期持续时间的计数器
    duration = Int(0)
    in_crop_cycle = Bool(False)

    def __init__(self, kiosk, crop_name=None, variety_name=None, crop_start_date=None,
                 crop_start_type=None, crop_end_date=None, crop_end_type=None, max_duration=None):

        # 设置日志
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)

        self.logger = logging.getLogger(loggername)
        self.kiosk = kiosk
        self.crop_name = crop_name
        self.variety_name = variety_name
        self.crop_start_date = crop_start_date
        self.crop_start_type = crop_start_type
        self.crop_end_date = crop_end_date
        self.crop_end_type = crop_end_type
        self.max_duration = max_duration

        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)

    def validate(self, campaign_start_date, next_campaign_start_date):
        """内部及与农业周期区间一起校验作物历。

        :param campaign_start_date: 当前周期的开始日期
        :param next_campaign_start_date: 下一个周期的开始日期
        """

        # 检查 crop_start_date 是否早于 crop_end_date
        crop_end_date = self.crop_end_date
        if self.crop_end_type == "maturity":
            crop_end_date = self.crop_start_date + timedelta(days=self.max_duration)
        if self.crop_start_date >= crop_end_date:
            msg = "crop_end_date (%s) before or equal to crop_start_date (%s) for crop '%s'!"
            raise exc.PCSEError(msg % (self.crop_end_date, self.crop_start_date, self.crop_name))

        # 检查 crop_start_date 是否在 campaign 区间之内
        r = check_date_range(self.crop_start_date, campaign_start_date, next_campaign_start_date)
        if r is not True:
            msg = "Start date (%s) for crop '%s' vareity '%s' not within campaign window (%s - %s)." % \
                  (self.crop_start_date, self.crop_name, self.variety_name,
                   campaign_start_date, next_campaign_start_date)
            raise exc.PCSEError(msg)

    def __call__(self, day):
        """运行作物历，以判断是否需要采取任何行动。

        :param day:  当前模拟天的日期对象
        :param drv: 该天的驱动变量
        :return: None
        """

        if self.in_crop_cycle:
            self.duration += 1

        # 作物周期的开始
        if day == self.crop_start_date:  # 开始一轮新的作物
            self.duration = 0
            self.in_crop_cycle = True
            msg = "Starting crop (%s) with variety (%s) on day %s" % (self.crop_name, self.variety_name, day)
            self.logger.info(msg)
            self._send_signal(signal=signals.crop_start, day=day, crop_name=self.crop_name,
                              variety_name=self.variety_name, crop_start_type=self.crop_start_type,
                              crop_end_type=self.crop_end_type)

        # 作物周期的结束
        finish_type = None
        if self.in_crop_cycle:
            # 检查当CROP_END_TYPE为 harvest/earliest 时，crop_end_date是否到达
            if self.crop_end_type in ["harvest", "earliest"]:
                if day == self.crop_end_date:
                    finish_type = "harvest"

            # 检查是否由于到达最大持续时间而被强制终止
            if self.in_crop_cycle and self.duration == self.max_duration:
                finish_type = "max_duration"

        # 如果达到结束条件，则发送信号以结束作物
        if finish_type is not None:
            self.in_crop_cycle = False
            self._send_signal(signal=signals.crop_finish, day=day,
                              finish_type=finish_type, crop_delete=True)

    def _on_CROP_FINISH(self):
        """记录作物已到达生长周期终点。
        """
        self.in_crop_cycle = False

    def get_end_date(self):
        """返回作物周期的结束日期。

        这要么是收获日期，要么是通过 crop_start_date + max_duration 计算得到。

        :return: 一个日期对象
        """
        if self.crop_end_type in ["harvest", 'earliest']:
            return self.crop_end_date
        else:
            return self.crop_start_date + timedelta(days=self.max_duration)

    def get_start_date(self):
        """返回作物周期的开始日期。始终为 self.crop_start_date

        :return: 开始日期
        """
        return self.crop_start_date


class TimedEventsDispatcher(HasTraits, DispatcherObject):
    """负责处理与日期相关联的事件。

    事件的处理方式是分发信号（取自 `signals` 模块），并用信号传递相关参数。
    TimedEvents 可以通过在 agromanagement 文件中的定义最容易理解。以下（YAML）形式的示例展示了两个 TimedEventsDispatcher 的定义::

        TimedEvents:
        -   event_signal: irrigate
            name:  定时灌溉事件
            comment: 所有灌溉量, 单位 mm
            events_table:
            - 2000-01-01: {irrigation_amount: 20}
            - 2000-01-21: {irrigation_amount: 50}
            - 2000-03-18: {irrigation_amount: 30}
            - 2000-03-19: {irrigation_amount: 25}
        -   event_signal: apply_n
            name:  定时氮肥施用表
            comment: 所有施肥量, 单位 kg/ha
            events_table:
            - 2000-01-10: {N_amount : 10, N_recovery: 0.7}
            - 2000-01-31: {N_amount : 30, N_recovery: 0.7}
            - 2000-03-25: {N_amount : 50, N_recovery: 0.7}
            - 2000-04-05: {N_amount : 70, N_recovery: 0.7}

    每个 TimedEventDispatcher 都由一个 `event_signal`、一个可选名字、一个可选注释以及 events_table（事件表）组成。
    events_table 是一个列表，针对每个日期，给出应随 event_signal 一起分发的参数。
    """
    event_signal = None
    events_table = List()
    days_with_events = Instance(Counter)
    kiosk = Instance(VariableKiosk)
    logger = Instance(logging.Logger)
    name = Unicode()
    comment = Unicode()

    def __init__(self, kiosk, event_signal, name, comment, events_table):
        """初始化 TimedEventDispatcher

        :param kiosk: VariableKiosk 的实例
        :param event_signal: 当事件发生时要分发的信号（来自 pcse.signals）
        :param name: 事件调度器的名称
        :param comment: 用于日志消息的注释
        :param events_table: 事件表，这里的结构是字典组成的列表，每个字典只包含一个键值对，
            其中键是事件的日期，值是要随信号分发的参数值的字典
        """

        # 设置日志记录
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        self.logger = logging.getLogger(loggername)

        self.kiosk = kiosk
        self.events_table = events_table
        self.name = name
        self.comment = comment

        # 从 signals 模块获取信号
        if not hasattr(signals, event_signal):
            msg = "Signal '%s'  not defined in pcse.signals module."
            raise exc.PCSEError(msg % event_signal)
        # self.event_signal = getattr(signals, event_signal)
        self.event_signal = getattr(signals, event_signal)

        # 构建有事件天数的计数器
        self.days_with_events = Counter()
        for ev in self.events_table:
            self.days_with_events.update(ev.keys())

        # 检查是否有一天有两个或更多的事件（同一信号下不允许）
        multi_days = []
        for day, count in self.days_with_events.items():
            if count > 1:
                multi_days.append(day)
        if multi_days:
            msg = "Found days with more than 1 event for events table '%s' on days: %s"
            raise exc.PCSEError(msg % (self.name, multi_days))

    def validate(self, campaign_start_date, next_campaign_start_date):
        """校验给定作业窗口的定时事件

        :param campaign_start_date: 作业周期起始日期
        :param next_campaign_start_date: 下一作业周期的起始日期，可以为 None
        """
        for event in self.events_table:
            day = list(event.keys())[0]
            r = check_date_range(day, campaign_start_date, next_campaign_start_date)
            if r is not True:
                msg = "Timed event at day %s not in campaign interval (%s - %s)" %\
                      (day, campaign_start_date, next_campaign_start_date)
                raise exc.PCSEError(msg)

    def __call__(self, day):
        """运行 TimedEventDispatcher 来判断是否需要执行操作。

        :param day: 当前模拟天（date 类型）
        :return: None
        """
        if day not in self.days_with_events:
            return

        for event in self.events_table:
            if day in event:
                msg = "Time event dispatched from '%s' at day %s" % (self.name, day)
                self.logger.info(msg)
                kwargs = event[day]
                self._send_signal(signal=self.event_signal, **kwargs)

    def get_end_date(self):
        """返回定时事件出现的最后一天
        """
        return max(self.days_with_events)


class StateEventsDispatcher(HasTraits, DispatcherObject):
    """负责处理与模型状态变量相关联的事件。

    事件通过分发一个信号（来自 `signals` 模块）并附带相关参数来进行处理。
    查看 agromanagement 文件中的定义可帮助理解 StateEvents，以下（YAML 格式）
    为两个 StateEventsDispatcher 实例的定义示例：

        StateEvents:
        -   event_signal: apply_n
            event_state: DVS
            zero_condition: rising
            name: 基于DVS的氮肥施用表
            comment: 所有施肥量单位为kg/ha
            events_table:
            - 0.3: {N_amount : 1, N_recovery: 0.7}
            - 0.6: {N_amount: 11, N_recovery: 0.7}
            - 1.12: {N_amount: 21, N_recovery: 0.7}
        -   event_signal: irrigate
            event_state: SM
            zero_condition: falling
            name: 基于土壤水分的灌溉调度
            comment: 所有灌溉量单位为cm水
            events_table:
            - 0.15: {irrigation_amount: 20}

    每个 StateEventDispatcher 由 `event_signal`、 `event_state`（触发事件的模型状态变量）
    和 `zero_condition` 定义。此外，还可以提供可选的 name 和 comment。最后，
    events_table 指定事件在状态变量取何值时发生。events_table 是一个列表，为每个
    状态变量数值指定应和 event_signal 一起分发的参数。

    为找到状态事件发生的时间步，PCSE 使用“过零点(zero-crossing)”的概念。
    这意味着当（`model_state` - `event_state`）等于或跨越零时，事件被触发。
    `zero_condition` 定义了这种跨越必须如何发生。其取值可以是：

    * `rising`: 当（`model_state` - `event_state`）从负值变为零或正值时触发事件
    * `falling`: 当（`model_state` - `event_state`）从正值变为零或负值时触发事件
    * `either`: 当（`model_state` - `event_state`）从任意方向跨过或达到零时触发事件

    zero_condition 的作用通过上面的示例可以说明。
    作物的发育期(DVS)只会从出苗时的0增长到成熟时的2。DVS上的事件（第一个示例）
    通常应指定为'rising'（虽然也可以使用'either'），但指定为'falling'则不会触发事件，
    因为DVS值不会降低。

    土壤水分(SM)既可能升高也可能降低。因此，控制灌溉的StateEvent（第二个示例）
    应指定为'falling'，因为只有当土壤水分低于阈值（即跨越最低值）时才应发生事件。
    如果将zero_condition设置为'either'，则下一个时间步由于灌溉使土壤水分上升且（`model_state` - `event_state`）再次跨越零，也可能再次触发事件。
    """
    event_signal = None
    event_state = Unicode()
    zero_condition = Enum(['rising', 'falling', 'either'])
    events_table = List()
    kiosk = Instance(VariableKiosk)
    logger = Instance(logging.Logger)
    name = Unicode()
    comment = Unicode()
    previous_signs = List()

    def __init__(self, kiosk, event_signal, event_state, zero_condition, name,
                 comment, events_table):
        """初始化 StateEventDispatcher

        :param kiosk: VariableKiosk 的一个实例
        :param event_signal: 事件发生时将被分发的信号（来自 pcse.signals）
        :param event_state: 应触发事件的状态变量名称
        :param zero_condition: zero_condition，取值为 'rising'|'falling'|'either' 中之一
        :param name: 事件分发器的名称
        :param comment: 用于日志信息的注释
        :param events_table: 事件表，其结构为字典组成的列表，每个字典只有一个键/值，
               该键为应该触发事件的状态值，值为将随信号一起分发的参数字典
        """

        # 设置日志记录
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        self.logger = logging.getLogger(loggername)

        self.kiosk = kiosk
        self.events_table = events_table
        self.zero_condition = zero_condition
        self.event_state = event_state
        self.name = name
        self.comment = comment

        # 为不同的 zero_condition 分配相应的状态评估函数
        if self.zero_condition == 'falling':
            self._evaluate_state = self._zero_condition_falling
        elif self.zero_condition == 'rising':
            self._evaluate_state = self._zero_condition_rising
        elif self.zero_condition == 'either':
            self._evaluate_state = self._zero_condition_either

        # 将 None 分配给 self.previous_signs，用于标记符号尚未被评估
        self.previous_signs = [None]*len(self.events_table)

        # 从 signals 模块获取信号
        if not hasattr(signals, event_signal):
            msg = "Signal '%s' not defined in pcse.signals module."
            raise exc.PCSEError(msg % event_signal)
        self.event_signal = getattr(signals, event_signal)

        # 为状态事件构建计数器
        self.states_with_events = Counter()
        for ev in self.events_table:
            self.states_with_events.update(ev.keys())

        # 检查在同一天内是否存在同一信号上的两个或多个事件（不允许）
        multi_states = []
        for state, count in self.states_with_events.items():
            if count > 1:
                multi_states.append(state)
        if multi_states:
            msg = "Found states with more than 1 event for events table '%s' for state: %s"
            raise exc.PCSEError(msg % (self.name, multi_states))

    def __call__(self, day):
        """运行 TimedEventDispatcher 以确定是否需要执行任何操作。

        :param day: 当前模拟天数的日期对象
        :return: None
        """
        if not self.event_state in self.kiosk:
            msg = "State variable '%s' not (yet) available in kiosk!" % self.event_state
            self.logger.warning(msg)
            return

        # 根据当前状态和事件条件，判断是否应触发某个事件。
        current_state = self.kiosk[self.event_state]
        zero_condition_signs = []
        for event, zero_condition_sign in zip(self.events_table, self.previous_signs):
            state, keywords = take_first(event.items())
            zcs = self._evaluate_state(current_state, state, keywords, zero_condition_sign)
            zero_condition_signs.append(zcs)
        self.previous_signs = zero_condition_signs


    def _zero_condition_falling(self, current_state, state, keywords, zero_condition_sign):
        sign = cmp2(current_state - state, 0)

        # 如果为 None，说明是第一次调用，还未计算 zero_condition_sign
        if zero_condition_sign is None:
            return sign

        if zero_condition_sign == 1 and sign in [-1, 0]:
            msg = "State event dispatched from '%s' at event_state %s" % (self.name, state)
            self.logger.info(msg)
            self._send_signal(signal=self.event_signal, **keywords)

        return sign

    def _zero_condition_rising(self, current_state, state, kwargs, zero_condition_sign):
        sign = cmp2(current_state - state, 0)

        # 如果为 None，说明是第一次调用，还未计算 zero_condition_sign
        if zero_condition_sign is None:
            return sign

        if zero_condition_sign == -1 and sign in [0, 1]:
            msg = "State event dispatched from '%s' at model state %s" % (self.name, current_state)
            self.logger.info(msg)
            self._send_signal(signal=self.event_signal, **kwargs)

        return sign

    def _zero_condition_either(self, current_state, state, keywords, zero_condition_sign):
        sign = cmp2(current_state - state, 0)

        # 如果为 None，说明是第一次调用，还未计算 zero_condition_sign
        if zero_condition_sign is None:
            return sign

        if (zero_condition_sign == 1 and sign in [-1, 0]) or \
           (zero_condition_sign == -1 and sign in [0, 1]):
            msg = "State event dispatched from %s at event_state %s" % (self.name, state)
            self.logger.info(msg)
            self._send_signal(signal=self.event_signal, **keywords)

        return sign


class AgroManager(AncillaryObject):
    """
    用于连续农业管理操作（包括作物轮作和事件）的类。

    参考 `CropCalendar`、`TimedEventDispatcher` 和 `StateEventDispatcher` 类的文档。

    AgroManager 负责执行典型发生于农田的农业管理操作，包括作物的播种和收获，以及如施肥、灌溉、割草和喷药等管理活动。

    仿真期间的农业管理以一系列“种植季”（campaign）来实现。每个种植季从规定的日历日期开始，并在下一个种植季开始时结束。仿真在显式提供结尾的空种植季、或通过最后一个种植季的作物历和定时事件推断结束日期时终止。详见下文 `end_date` 属性部分。

    每个种植季最多包含一个作物历（crop calendar）、零个或多个定时事件（timed events）、零个或多个状态事件（state events）。
    AgroManager 所需输入数据的结构可以通过下方 YAML 示例轻松理解。该定义包含三个种植季，第一个从 1999-08-01 开始，第二个从 2000-09-01 开始，最后一个从 2001-03-01 开始。第一个种植季定义了冬小麦的作物历，从给定的 crop_start_date 播种。期间有两个灌溉的定时事件（2000-05-25 和 2000-06-30），以及按生育期（DVS 0.3、0.6 和 1.12）施肥的状态事件（event_signal: apply_n）。

    第二个种植季无作物历、定时事件和状态事件，这意味着这是一个裸地期，仅进行水量平衡模拟。第三个种植季为青贮玉米，2001-04-15 播种，有两组定时事件（灌溉和氮肥施用），没有状态事件。
    该情况下仿真结束日期为 2001-11-01（2001-04-15 + 200 天）。

    一个农业管理定义文件示例::

        AgroManagement:
        - 1999-08-01:
            CropCalendar:
                crop_name: wheat
                variety_name: winter-wheat
                crop_start_date: 1999-09-15
                crop_start_type: sowing
                crop_end_date:
                crop_end_type: maturity
                max_duration: 300
            TimedEvents:
            -   event_signal: irrigate
                name:  定时灌溉事件
                comment: 所有灌溉量单位为厘米
                events_table:
                - 2000-05-25: {irrigation_amount: 3.0}
                - 2000-06-30: {irrigation_amount: 2.5}
            StateEvents:
            -   event_signal: apply_n
                event_state: DVS
                zero_condition: rising
                name: 基于DVS的氮肥施用表
                comment: 所有施肥量单位为kg/ha
                events_table:
                - 0.3: {N_amount : 1, N_recovery: 0.7}
                - 0.6: {N_amount: 11, N_recovery: 0.7}
                - 1.12: {N_amount: 21, N_recovery: 0.7}
        - 2000-09-01:
            CropCalendar:
            TimedEvents:
            StateEvents
        - 2001-03-01:
            CropCalendar:
                crop_name: maize
                variety_name: fodder-maize
                crop_start_date: 2001-04-15
                crop_start_type: sowing
                crop_end_date:
                crop_end_type: maturity
                max_duration: 200
            TimedEvents:
            -   event_signal: irrigate
                name:  定时灌溉事件
                comment: 所有灌溉量单位为厘米
                events_table:
                - 2001-06-01: {irrigation_amount: 2.0}
                - 2001-07-21: {irrigation_amount: 5.0}
                - 2001-08-18: {irrigation_amount: 3.0}
                - 2001-09-19: {irrigation_amount: 2.5}
            -   event_signal: apply_n
                name:  定时氮肥施用表
                comment: 所有施肥量单位为kg/ha
                events_table:
                - 2001-05-25: {N_amount : 50, N_recovery: 0.7}
                - 2001-07-05: {N_amount : 70, N_recovery: 0.7}
            StateEvents:

    """

    # 各个耕作周期的开始日期
    campaign_start_dates = List()

    # 整个引擎的起始和结束日期
    _start_date = Instance(date)
    _end_date = Instance(date)

    # 耕作周期的定义
    crop_calendars = List()
    timed_event_dispatchers = List()
    state_event_dispatchers = List()

    _tmp_date = None  # 辅助变量
    _icampaign = 0  # 统计耕作周期数量

    def initialize(self, kiosk, agromanagement):
        """初始化AgroManager。

        :param kiosk: 一个PCSE变量Kiosk
        :param agromanagement: 耕作管理的定义，见上方的YAML示例。
        """

        self.kiosk = kiosk
        self.crop_calendars = []
        self.timed_event_dispatchers = []
        self.state_event_dispatchers = []
        self.campaign_start_dates = []

        # 连接CROP_FINISH信号与处理函数
        self._connect_signal(self._on_CROP_FINISH, signals.crop_finish)

        # 如果定义了 "AgroManagement" 条目，则首先获取其内部内容
        if "AgroManagement" in agromanagement:
            agromanagement = agromanagement["AgroManagement"]

        # 首先获取并校验不同耕作周期的日期
        for campaign in agromanagement:
            # 检查耕作周期的开始日期是否按时间顺序排列
            campaign_start_date = take_first(campaign.keys())
            self._check_campaign_date(campaign_start_date)
            self.campaign_start_dates.append(campaign_start_date)

        # 向耕作周期日期列表添加None以表示所有周期结束
        self.campaign_start_dates.append(None)

        # 遍历所有耕作周期，构建作物历和定时/状态事件调度器
        for campaign, campaign_start, next_campaign in \
                zip(agromanagement, self.campaign_start_dates[:-1], self.campaign_start_dates[1:]):

            # 获取该耕作周期开始日期的定义
            campaign_def = campaign[campaign_start]

            if self._is_empty_campaign(campaign_def):  # 此周期未定义（如休耕）
                self.crop_calendars.append(None)
                self.timed_event_dispatchers.append(None)
                self.state_event_dispatchers.append(None)
                continue

            # 获取当前耕作周期的作物历定义
            cc_def = campaign_def['CropCalendar']
            if cc_def is not None:
                cc = CropCalendar(kiosk, **cc_def)
                cc.validate(campaign_start, next_campaign)
                self.crop_calendars.append(cc)
            else:
                self.crop_calendars.append(None)

            # 获取定时事件的定义，并构建TimedEventsDispatchers
            te_def = campaign_def['TimedEvents']
            if te_def is not None:
                te_dsp = self._build_TimedEventDispatchers(kiosk, te_def)
                for te in te_dsp:
                    te.validate(campaign_start, next_campaign)
                self.timed_event_dispatchers.append(te_dsp)
            else:
                self.timed_event_dispatchers.append(None)

            # 获取状态事件的定义，并构建StateEventsDispatchers
            se_def = campaign_def['StateEvents']
            if se_def is not None:
                se_dsp = self._build_StateEventDispatchers(kiosk, se_def)
                self.state_event_dispatchers.append(se_dsp)
            else:
                self.state_event_dispatchers.append(None)

    def _is_empty_campaign(self, campaign_def):
        """检查该耕作周期定义是否为空"""

        if campaign_def is None:
            return True

        attrs = ["CropCalendar", "TimedEvents", "StateEvents"]
        r = []
        for attr in attrs:
            if attr in campaign_def:
                if campaign_def[attr] is None:
                    r.append(True)
                else:
                    r.append(False)
        if r == [True]*3:
            return True

        return False

    @property
    def start_date(self):
        """获取农事管理序列的起始日期，例如第一个模拟日期

        :return: 一个 date 对象
        """
        if self._start_date is None:
            self._start_date = take_first(self.campaign_start_dates)

        return self._start_date

    @property
    def end_date(self):
        """
        获取农事管理序列的结束日期，例如最后一个模拟日期。

        :return: 一个 date 对象

        获取最后一个模拟日期较为复杂，主要有两种情况。

        **1. 添加显式的结尾空周期**

        第一种方式是通过向农事管理定义中添加一个“结尾空周期”来显式定义模拟的结束日期。
        下面是包含“结尾空周期”的农事管理定义示例（YAML格式）。该示例将模拟到2001-01-01::

            Version: 1.0
            AgroManagement:
            - 1999-08-01:
                CropCalendar:
                    crop_name: winter-wheat
                    variety_name: winter-wheat
                    crop_start_date: 1999-09-15
                    crop_start_type: sowing
                    crop_end_date:
                    crop_end_type: maturity
                    max_duration: 300
                TimedEvents:
                StateEvents:
            - 2001-01-01:

        注意，如果最后一个周期中包含了StateEvents的定义，则**必须**提供结尾的空周期，
        否则无法确定结束日期。如下定义将导致错误::

            Version: 1.0
            AgroManagement:
            - 2001-01-01:
                CropCalendar:
                    crop_name: maize
                    variety_name: fodder-maize
                    crop_start_date: 2001-04-15
                    crop_start_type: sowing
                    crop_end_date:
                    crop_end_type: maturity
                    max_duration: 200
                TimedEvents:
                StateEvents:
                -   event_signal: apply_n
                    event_state: DVS
                    zero_condition: rising
                    name: DVS-based N application table
                    comment: 全部施肥量均为kg/ha
                    events_table:
                    - 0.3: {N_amount : 1, N_recovery: 0.7}
                    - 0.6: {N_amount: 11, N_recovery: 0.7}
                    - 1.12: {N_amount: 21, N_recovery: 0.7}


        **2. 无显式结尾周期的情况**

        第二种方式是没有结尾的空周期，此时模拟结束日期由作物历和/或计划的定时事件推断出来。
        在下例中，结束日期将为2000-08-05，即收获日期，且没有计划在此日期之后的定时事件::

            Version: 1.0
            AgroManagement:
            - 1999-09-01:
                CropCalendar:
                    crop_name: wheat
                    variety_name: winter-wheat
                    crop_start_date: 1999-10-01
                    crop_start_type: sowing
                    crop_end_date: 2000-08-05
                    crop_end_type: harvest
                    max_duration: 330
                TimedEvents:
                -   event_signal: irrigate
                    name:  定时灌溉事件
                    comment: 所有灌溉量以cm为单位
                    events_table:
                    - 2000-05-01: {irrigation_amount: 2, efficiency: 0.7}
                    - 2000-06-21: {irrigation_amount: 5, efficiency: 0.7}
                    - 2000-07-18: {irrigation_amount: 3, efficiency: 0.7}
                StateEvents:

        如果没有给出收获日期，并且作物持续生长至成熟，则结束日期将由作物历中的作物开始日期加上最大生长周期(max_duration)来估算。

        """
        if self._end_date is None:

            # 首先检查最后一个作物季（campaign）是否为空的结尾周期，如果是，则采用该日期。
            if self.crop_calendars[-1] is None and \
               self.timed_event_dispatchers[-1] is None and \
               self.state_event_dispatchers[-1] is None:
                self._end_date = self.campaign_start_dates[-2]  # 这里用 -2 是因为 None 已被添加到 campaign_start_dates
                return self._end_date

            # 检查最后一个作物季（campaign）是否有 StateEvents（状态事件）定义，却没有通过空的结尾周期显式指定结束日期
            if self.state_event_dispatchers[-1] is not None:
                msg = "In the AgroManagement definition, the last campaign with start date '%s' contains StateEvents. " \
                      "When specifying StateEvents, the end date of the campaign must be explicitly" \
                      "given by a trailing empty campaign."
                raise exc.PCSEError(msg)

            # 遍历 crop calendars 和 timed events，取得所有结束日期
            cc_dates = []
            te_dates = []
            for cc, teds in zip(self.crop_calendars, self.timed_event_dispatchers):
                if cc is not None:
                    cc_dates.append(cc.get_end_date())
                if teds is not None:
                    te_dates.extend([t.get_end_date() for t in teds])

            # 如果没有找到任何结束日期，抛出异常，因为 agromanagement 序列只包含空的作物季
            if not cc_dates and not te_dates:
                msg = "Empty agromanagement definition: no campaigns with crop calendars or timed events provided!"
                raise exc.PCSEError(msg)

            end_date = date(1, 1, 1)
            if cc_dates:
                end_date = max(max(cc_dates), end_date)
            if te_dates:
                end_date = max(max(te_dates), end_date)
            self._end_date = end_date

        return self._end_date

    def _check_campaign_date(self, campaign_start_date):
        """
        :param campaign_start_date: 作物季的开始日期
        :return: None
        """
        if not isinstance(campaign_start_date, date):
            msg = "Campaign start must be given as a date."
            raise exc.PCSEError(msg)

        if self._tmp_date is None:
            self._tmp_date = campaign_start_date
        else:
            if campaign_start_date <= self._tmp_date:
                msg = "The agricultural campaigns are not sequential " \
                      "in the agromanagement definition."
                raise exc.PCSEError(msg)

    def _build_TimedEventDispatchers(self, kiosk, event_definitions):
        # 创建定时事件（TimedEvents）的分派器列表
        r = []
        for ev_def in event_definitions:
            ev_dispatcher = TimedEventsDispatcher(kiosk, **ev_def)
            r.append(ev_dispatcher)
        return r

    def _build_StateEventDispatchers(self, kiosk, event_definitions):
        # 创建状态事件（StateEvents）的分派器列表
        r = []
        for ev_def in event_definitions:
            ev_dispatcher = StateEventsDispatcher(kiosk, **ev_def)
            r.append(ev_dispatcher)
        return r

    def __call__(self, day, drv):
        """调⽤ AgroManager 去执⾏作物历相关操作、定时事件和状态事件。

        :param day: 当前模拟日期
        :param drv: 当前⽇期的驱动变量
        :return: None
        """

        # 检查是否应该切换到新的作物季
        if day == self.campaign_start_dates[self._icampaign+1]:
            self._icampaign += 1
            # 如果进入新作物季，抛弃上一作物季的定义
            self.crop_calendars.pop(0)
            self.timed_event_dispatchers.pop(0)
            self.state_event_dispatchers.pop(0)

        # 调⽤作物历、定时事件和状态事件的处理器
        if self.crop_calendars[0] is not None:
            self.crop_calendars[0](day)

        if self.timed_event_dispatchers[0] is not None:
            for ev_dsp in self.timed_event_dispatchers[0]:
                ev_dsp(day)

        if self.state_event_dispatchers[0] is not None:
            for ev_dsp in self.state_event_dispatchers[0]:
                ev_dsp(day)

    def _on_CROP_FINISH(self, day):
        """在作物周期结束后发送终止信号。

        仿真在以下条件同时满足时将终止：
        1. 当前作物季后没有定义新的作物季
        2. 没有活跃的 StateEvents（状态事件）
        3. 当前日期之后没有安排的 TimedEvents（定时事件）
        """

        if self.campaign_start_dates[self._icampaign+1] is not None:
            return  # 例如，还有下一个作物季已定义

        if self.state_event_dispatchers[0] is not None:
            return  # 仍有活跃的状态事件，未来可能会被触发

        if self.timed_event_dispatchers[0] is not None:
            end_dates = [t.get_end_date() for t in self.timed_event_dispatchers[0]]
            if end_dates:
                if max(end_dates) > day:  # 至少还有一个定时事件安排在未来
                    return
        self._send_signal(signal=signals.terminate)


    @property
    def ndays_in_crop_cycle(self):
        """返回当前作物周期的天数。

        如果当前没有作物周期，则返回零。
        """

        if self.crop_calendars[0] is None:
            return 0
        else:
            return self.crop_calendars[0].duration
