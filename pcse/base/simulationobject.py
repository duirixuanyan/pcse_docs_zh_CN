# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import types
import logging
from datetime import date

from .dispatcher import DispatcherObject
from ..traitlets import (HasTraits, List, Float, Int, Instance, Dict, Bool, All)
from .. import exceptions as exc
from .variablekiosk import VariableKiosk
from .states_rates import StatesTemplate, RatesTemplate, ParamTemplate



class SimulationObject(HasTraits, DispatcherObject):
    """PCSE模拟对象的基类。

    :param day: 模拟的起始日期
    :param kiosk: 此PCSE实例的变量亭

    day 和 kiosk 是必需参数，实例化 SimulationObject 时必须传递。

    """

    # logger、params、states、rates 和 variable kiosk 的占位符
    states = Instance(StatesTemplate)
    rates = Instance(RatesTemplate)
    params = Instance(ParamTemplate)
    kiosk = Instance(VariableKiosk)

    # finalize 期间将被设置的变量占位符
    _for_finalize = Dict()

    def __init__(self, day, kiosk, *args, **kwargs):
        HasTraits.__init__(self, *args, **kwargs)

        # 检查 day 变量是否被指定
        if not isinstance(day, date):
            this = "%s.%s" % (self.__class__.__module__, self.__class__.__name__)
            msg = ("%s should be instantiated with the simulation start " +
                   "day as first argument!")
            raise exc.PCSEError(msg % this)

        # 检查 kiosk 变量是否被指定，并赋值给 self
        if not isinstance(kiosk, VariableKiosk):
            this = "%s.%s" % (self.__class__.__module__, self.__class__.__name__)
            msg = ("%s should be instantiated with the VariableKiosk " +
                   "as second argument!")
            raise exc.PCSEError(msg % this)
        self.kiosk = kiosk

        self.initialize(day, kiosk, *args, **kwargs)
        self.logger.debug("Component successfully initialized on %s!" % day)

    def initialize(self, *args, **kwargs):
        msg = "`initialize` method not yet implemented on %s" % self.__class__.__name__
        raise NotImplementedError(msg)

    @property
    def logger(self):
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)

    def integrate(self, *args, **kwargs):
        msg = "`integrate` method not yet implemented on %s" % self.__class__.__name__
        raise NotImplementedError(msg)

    def calc_rates(self, *args, **kwargs):
        msg = "`calc_rates` method not yet implemented on %s" % self.__class__.__name__
        raise NotImplementedError(msg)

    def __setattr__(self, attr, value):
        # __setattr__ 已被修改，用于强制类属性在赋值前必须已定义。有几个例外情况：
        # 1. 如果属性名以 '_' 开头，将直接赋值。
        # 2. 如果属性值是一个函数（例如 types.FunctionType），也会被直接赋值。这是因为
        #    'prepare_states' 和 'prepare_rates' 装饰器会为 Simulation Object 分别赋予包装后的函数
        #    'calc_rates'、'integrate' 和可选的 'finalize'。此时__setattr__会冲突，因为这些类方法不是已定义的属性。
        #
        # 最后，如果赋值给某个属性的值是 SimulationObject 类型，或者已有属性值是 SimulationObject 类型，
        # 则需要重建子 SimulationObject 的列表。

        if attr.startswith("_") or type(value) is types.FunctionType:
            HasTraits.__setattr__(self, attr, value)
        elif hasattr(self, attr):
            HasTraits.__setattr__(self, attr, value)
        else:
            msg = "Assignment to non-existing attribute '%s' prevented." % attr
            raise AttributeError(msg)

    def get_variable(self, varname):
        """ 返回指定状态变量或速率变量的值。

        :param varname: 变量名。

        注意：`get_variable()` 将严格按照指定（区分大小写）搜索变量名。
        """

        # 先在当前对象中查找变量，随后遍历层级结构查找
        value = None
        if hasattr(self.states, varname):
            value = getattr(self.states, varname)
        elif hasattr(self.rates, varname):
            value = getattr(self.rates, varname)
        # 向各个子模拟对象查询是否存在该变量
        else:
            for simobj in self.subSimObjects:
                value = simobj.get_variable(varname)
                if value is not None:
                    break
        return value

    def set_variable(self, varname, value, incr):
        """ 设置指定状态变量或速率变量的值。

        :param varname: 需要更新的变量名（字符串）。
        :param value: 需要更新到的值（float）。
        :param incr: 用于接收已更新变量增量的字典。

        :returns: 变量的增量（新值 - 旧值）；如果未成功找到对应的类方法，则返回 `None`。

        注意：'设置' 一个变量（比如更新模型状态）通常比 '获取' 一个变量更复杂，
        因为经常需要同时更新其他内部变量（校验和、相关状态变量等）。
        由于没有通用规则来'设置'一个变量，这需要模型设计者自行实现相关的代码以完成更新。

        `set_variable()` 的实现方式如下。它会递归在 simulationobjects 中搜索名为
        `_set_variable_<varname>` （区分大小写）的类方法。如果找到该方法，则使用提供的 value 作为输入参数调用。

        例如，要将作物叶面积指数（变量名 'LAI'）更新为 5.0，可调用：`set_variable('LAI', 5.0)`。
        在内部，这将搜索名为 `_set_variable_LAI` 的类方法，并以 5.0 作为输入参数执行该方法。
        """
        method_name = "_set_variable_%s" % varname.strip()
        try:
            method_obj = getattr(self, method_name)
            rv = method_obj(value)
            # 检查返回值是否为字典
            if not isinstance(rv, dict):
                msg = ("Method %s on '%s' should return a dict with the increment of the " +
                       "updated state variables!") % (method_name, self.__class__.__name__)
                raise exc.PCSEError(msg)
            incr.update(rv)
        except AttributeError:  # 方法不存在则继续
            pass
        except TypeError:  # 方法存在但不可调用，抛出异常
            msg = ("Method '%s' on '%s' could not be called by 'set_variable()': " +
                   "check your code!") % (method_name, self.__class__.__name__)
            raise exc.PCSEError(msg)

        # 递归对子模拟对象执行 set_variable
        for simobj in self.subSimObjects:
            simobj.set_variable(varname, value, incr)

    def _delete(self):
        """ 执行 states/rates 对象的 _delete() 方法，并递归调用所有子模拟对象的 _delete()。"""
        if self.states is not None:
            self.states._delete()
            self.states = None
        if self.rates is not None:
            self.rates._delete()
            self.rates = None
        for obj in self.subSimObjects:
            obj._delete()

    @property
    def subSimObjects(self):
        """ 返回嵌入在本对象内的 SimulationObject。"""

        subSimObjects = []
        defined_traits = self.__dict__["_trait_values"]
        for attr in defined_traits.values():
            if isinstance(attr, SimulationObject):
                subSimObjects.append(attr)
        return subSimObjects

    def finalize(self, day):
        """ 对所有子模拟对象执行 _finalize 调用 """
        # 用 _for_finalize 字典中的值更新 states 对象
        if self.states is not None:
            self.states.unlock()
            while len(self._for_finalize) > 0:
                k, v = self._for_finalize.popitem()
                setattr(self.states, k, v)
            self.states.lock()
        # 遍历所有子模拟对象，执行 finalize
        if self.subSimObjects is not None:
            for simobj in self.subSimObjects:
                simobj.finalize(day)

    def touch(self):
        """'Touch' 本对象及所有子模拟对象的所有状态变量。

        这个名字来源于 UNIX 的 `touch` 命令，该命令不会更改文件内容，
        只会更新文件的元数据（如时间等）。
        类似地，`touch` 方法会重新赋值每个状态变量，
        触发任意的触发器（例如 `on_trait_change()`）。
        这将保证这些状态变量在 VariableKiosk 中保持可用。
        """

        if self.states is not None:
            self.states.touch()
        # 遍历可能存在的子模拟对象，执行 touch 方法。
        if self.subSimObjects is not None:
            for simobj in self.subSimObjects:
                simobj.touch()

    def zerofy(self):
        """将本对象及所有子模拟对象的所有速率变量置零。"""

        if self.rates is not None:
            self.rates.zerofy()

        # 遍历可能存在的子模拟对象，执行 zerofy 方法。
        if self.subSimObjects is not None:
            for simobj in self.subSimObjects:
                simobj.zerofy()


class AncillaryObject(HasTraits, DispatcherObject):
    """PCSE辅助对象的基类。

    辅助对象本身不进行模拟计算，但通常对包装对象很有用。
    这类对象仍然具备一些与 SimulationObjects 相同的特性，
    例如存在 self.logger 和 self.kiosk，锁定属性机制（要求定义类属性），
    以及可以发送/接收信号的功能。
    """

    # logger、变量kiosk和参数的占位符
    kiosk = Instance(VariableKiosk)
    params = Instance(ParamTemplate)

    def __init__(self, kiosk, *args, **kwargs):
        HasTraits.__init__(self, *args, **kwargs)

        # 检查kiosk变量是否已指定，并赋值给self
        if not isinstance(kiosk, VariableKiosk):
            this = "%s.%s" % (self.__class__.__module__, self.__class__.__name__)
            msg = "%s should be instantiated with the VariableKiosk " \
                  "as second argument!"
            raise RuntimeError(msg % this)

        self.kiosk = kiosk
        self.initialize(kiosk, *args, **kwargs)
        self.logger.debug("Component successfully initialized!")

    @property
    def logger(self):
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)

    def __setattr__(self, attr, value):
        if attr.startswith("_"):
            HasTraits.__setattr__(self, attr, value)
        elif hasattr(self, attr):
            HasTraits.__setattr__(self, attr, value)
        else:
            msg = "Assignment to non-existing attribute '%s' prevented." % attr
            raise AttributeError(msg)
