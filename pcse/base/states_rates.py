# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import logging

from ..traitlets import (HasTraits, List, Float, Int, Instance, Dict, Bool, All)
from ..util import Afgen
from .. import exceptions as exc
from .variablekiosk import VariableKiosk


class ParamTemplate(HasTraits):
    """用于存储参数值的模板。

    此类应该被实际定义参数的类继承。

    示例::

        >>> import pcse
        >>> from pcse.base import ParamTemplate
        >>> from pcse.traitlets import Float
        >>>
        >>>
        >>> class Parameters(ParamTemplate):
        ...     A = Float()
        ...     B = Float()
        ...     C = Float()
        ...
        >>> parvalues = {"A" :1., "B" :-99, "C":2.45}
        >>> params = Parameters(parvalues)
        >>> params.A
        1.0
        >>> params.A; params.B; params.C
        1.0
        -99.0
        2.4500000000000002
        >>> parvalues = {"A" :1., "B" :-99}
        >>> params = Parameters(parvalues)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "pcse/base.py", line 205, in __init__
            raise exc.ParameterError(msg)
        pcse.exceptions.ParameterError: Value for parameter C missing.
    """

    def __init__(self, parvalues):

        HasTraits.__init__(self)

        for parname in self.trait_names():
            # 如果类的属性名称以 "trait" 开头，则这是一个特殊属性，不是 WOFOST 参数
            if parname.startswith("trait"):
                continue
            # 否则检查参数名是否在 parvalues 字典中
            if parname not in parvalues:
                msg = "Value for parameter %s missing." % parname
                raise exc.ParameterError(msg)
            value = parvalues[parname]
            if isinstance(getattr(self, parname), (Afgen)):
                # AFGEN 表参数
                setattr(self, parname, Afgen(value))
            else:
                # 单值参数
                setattr(self, parname, value)

    def __setattr__(self, attr, value):
        if attr.startswith("_"):
            HasTraits.__setattr__(self, attr, value)
        elif hasattr(self, attr):
            HasTraits.__setattr__(self, attr, value)
        else:
            # 阻止对不存在的属性赋值
            msg = "Assignment to non-existing attribute '%s' prevented." % attr
            raise AttributeError(msg)


def check_publish(publish):
    """将要发布的变量列表转换为具有唯一元素的集合。"""

    if publish is None:
        publish = []
    elif isinstance(publish, str):
        publish = [publish]
    elif isinstance(publish, (list, tuple)):
        pass
    else:
        # publish 参数应指定为字符串或字符串列表
        msg = "The publish keyword should specify a string or a list of strings"
        raise RuntimeError(msg)
    return set(publish)


class StatesRatesCommon(HasTraits):
    _kiosk = Instance(VariableKiosk)
    _valid_vars = Instance(set)
    _locked = Bool(False)

    def __init__(self, kiosk=None, publish=None):
        """
        设置states和rates模板的通用部分，包括必须在kiosk中发布的变量
        """

        HasTraits.__init__(self)

        # 确保提供了变量kiosk
        if not isinstance(kiosk, VariableKiosk):
            msg = ("Variable Kiosk must be provided when instantiating rate " +
                   "or state variables.")
            raise RuntimeError(msg)
        self._kiosk = kiosk

        # 检查publish变量是否正确使用
        publish = check_publish(publish)

        # 确定用户定义的rate/state属性
        self._valid_vars = self._find_valid_variables()

        # 在kiosk中注册所有变量，并可选发布它们
        self._register_with_kiosk(publish)

    def _find_valid_variables(self):
        """
        返回有效state/rate变量名的集合。有效的rate变量名不能以'trait'或'_'开头。
        """

        valid = lambda s: not (s.startswith("_") or s.startswith("trait"))
        r = [name for name in self.trait_names() if valid(name)]
        return set(r)

    def _register_with_kiosk(self, publish):
        """
        在variable kiosk中注册变量。

        这里进行了以下几步操作：
         1. 在kiosk中注册变量，如果rates/states被注册两次会抛出错误，这确保了整个模型变量的唯一性。
         2. 如果变量名包含在publish关键字指定的列表中，则对该变量设置触发器，在kiosk中自动更新其值。

         注意self._vartype用于指定该变量注册为state变量(_vartype=="S")还是rate变量(_vartype=="R")
        """

        for attr in self._valid_vars:
            if attr in publish:
                publish.remove(attr)
                self._kiosk.register_variable(id(self), attr, type=self._vartype,
                                              publish=True)
                self.observe(handler=self._update_kiosk, names=attr, type=All)
            else:
                self._kiosk.register_variable(id(self), attr, type=self._vartype,
                                              publish=False)
        # 检查publish变量集合是否已被完全处理，否则抛出错误。
        if len(publish) > 0:
            msg = ("Unknown variable(s) specified with the publish " +
                   "keyword: %s") % publish
            raise exc.PCSEError(msg)

    # def __setattr__(self, attr, value):
    #     # 以“_”开头的属性无论对象是否锁定都可以赋值或更新。
    #     #
    #     # 注意：startswith("_") 的判断必须放在最前面，否则部分trait内部赋值会失败
    #     if attr.startswith("_"):
    #         HasTraits.__setattr__(self, attr, value)
    #     elif attr in self._valid_vars:
    #         if not self._locked:
    #             HasTraits.__setattr__(self, attr, value)
    #         else:
    #             msg = "Assignment to locked attribute '%s' prevented." % attr
    #             raise AttributeError(msg)
    #     else:
    #         msg = "Assignment to non-existing attribute '%s' prevented." % attr
    #         raise AttributeError(msg)

    def _update_kiosk(self, change):
        """通过trait通知更新variable_kiosk。"""
        self._kiosk.set_variable(id(self), change["name"], change["new"])

    def unlock(self):
        "解锁此类的属性。"
        self._locked = False

    def lock(self):
        "锁定此类的属性。"
        self._locked = True

    def _delete(self):
        """在垃圾回收前从kiosk注销变量。

        该方法命名为_delete()，必须显式调用，
        因为python中__del__()的处理方式较为极端和不确定。
        """
        for attr in self._valid_vars:
            self._kiosk.deregister_variable(id(self), attr)

    @property
    def logger(self):
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)


class StatesTemplate(StatesRatesCommon):
    """负责为state变量分配初始值、在kiosk中注册变量和监控需要发布变量的赋值。

    :param kiosk: VariableKiosk类的实例。所有state变量都会被注册到kiosk，
        用于确保整个模型中变量名唯一。同时，被发布的变量值会通过VariableKiosk对外可见。
    :param publish: 需要在VariableKiosk中发布的变量名列表。如果不需要发布变量可以省略。

    State变量的初始值可在实例化States类时用关键字参数指定。

    示例::

        >>> import pcse
        >>> from pcse.base import VariableKiosk, StatesTemplate
        >>> from pcse.traitlets import Float, Integer, Instance
        >>> from datetime import date
        >>>
        >>> k = VariableKiosk()
        >>> class StateVariables(StatesTemplate):
        ...     StateA = Float()
        ...     StateB = Integer()
        ...     StateC = Instance(date)
        ...
        >>> s1 = StateVariables(k, StateA=0., StateB=78, StateC=date(2003,7,3),
        ...                     publish="StateC")
        >>> print s1.StateA, s1.StateB, s1.StateC
        0.0 78 2003-07-03
        >>> print k
        Contents of VariableKiosk:
         * Registered state variables: 3
         * Published state variables: 1 with values:
          - variable StateC, value: 2003-07-03
         * Registered rate variables: 0
         * Published rate variables: 0 with values:

        >>>
        >>> s2 = StateVariables(k, StateA=200., StateB=1240)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "pcse/base.py", line 396, in __init__
            raise exc.PCSEError(msg)
        pcse.exceptions.PCSEError: Initial value for state StateC missing.

    """

    _kiosk = Instance(VariableKiosk)
    _locked = Bool(False)
    _vartype = "S"

    def __init__(self, kiosk=None, publish=None, **kwargs):

        StatesRatesCommon.__init__(self, kiosk, publish)

        # 设置初始state值
        for attr in self._valid_vars:
            if attr in kwargs:
                value = kwargs.pop(attr)
                setattr(self, attr, value)
            else:
                msg = "Initial value for state %s missing." % attr
                raise exc.PCSEError(msg)

        # 检查kwargs是否为空，否则发出警告
        if len(kwargs) > 0:
            msg = ("Initial value given for unknown state variable(s): " +
                   "%s") % kwargs.keys()
            self.logger.warning(msg)

        # 锁定对象，防止此阶段进一步更改。
        self._locked = True

    def touch(self):
        """重新为每个state变量赋值，如果变量被发布，则更新其在variablekiosk中的值。"""

        self.unlock()
        for name in self._valid_vars:
            value = getattr(self, name)
            setattr(self, name, value)
        self.lock()


class StatesWithImplicitRatesTemplate(StatesTemplate):
    """具有相关rate的state变量的容器类。

    rates会在初始化时被创建，名称与其对应state相同，但前面加小写字母'r'。
    初始化后不允许隐式添加新属性。
    调用integrate()方法用当前rate积分所有state；积分后rate会重置为0.0。

    state为所有继承自Float且不是以下划线开头的属性。
    """

    rates = {}
    __initialized = False

    def __setattr__(self, name, value):
        if name in self.rates:
            # 已知属性：设置值
            self.rates[name] = value
        elif not self.__initialized:
            # 尚未初始化时的新属性：允许
            object.__setattr__(self, name, value)
        else:
            # 初始化后尝试添加新属性：不允许，按父类规则处理
            super(StatesWithImplicitRatesTemplate, self).__setattr__(name, value)

    def __getattr__(self, name):
        if name in self.rates:
            return self.rates[name]
        else:
            object.__getattribute__(self, name)

    def initialize_rates(self):
        self.rates = {}
        self.__initialized = True

        for s in self.__class__.listIntegratedStates():
            self.rates['r' + s] = 0.0

    def integrate(self, delta):
        # 积分所有state
        for s in self.listIntegratedStates():
            rate = getattr(self, 'r' + s)
            state = getattr(self, s)
            newvalue = state + delta * rate
            setattr(self, s, newvalue)

        # 重置所有rate
        for r in self.rates:
            self.rates[r] = 0.0

    @classmethod
    def listIntegratedStates(cls):
        return sorted([a for a in cls.__dict__ if isinstance(getattr(cls, a), Float) and not a.startswith('_')])

    @classmethod
    def initialValues(cls):
        return dict((a, 0.0) for a in cls.__dict__ if isinstance(getattr(cls, a), Float) and not a.startswith('_'))


class RatesTemplate(StatesRatesCommon):
    """负责在 kiosk 中注册变量，并监控已经发布变量的赋值。

    :param kiosk: VariableKiosk 类的实例。所有速率变量将被注册到 kiosk，
        以确保变量名在整个模型中唯一。此外，已发布变量的值可以通过 VariableKiosk 获取。
    :param publish: 需要在 VariableKiosk 中发布值的变量名列表。如果没有需要发布的变量，可以省略。

    具体示例见 `StatesTemplate`。唯一的区别是速率变量初始值无需指定，
    因为 Int、Float 类型的会自动设为零，Boolean 类型会设为 False。
    """

    _rate_vars_zero = Instance(dict)
    _vartype = "R"

    def __init__(self, kiosk=None, publish=None):
        """初始化 RatesTemplate，并设置对需要发布变量的监控。"""

        StatesRatesCommon.__init__(self, kiosk, publish)

        # 尽可能确定所有速率变量的零值
        self._rate_vars_zero = self._find_rate_zero_values()

        # 初始化所有速率变量为零或False
        self.zerofy()

        # 锁定对象，防止后续更改变量
        self._locked = True

    def _find_rate_zero_values(self):
        """返回一个字典，其 key 是所有有效速率变量名，value 是 zerofy() 方法使用的零值。
        Int 类型为 0，Float 类型为 0.0，Bool 类型为 False。
        """

        # 定义 Float, Int, Bool 类型的零值
        zero_value = {Bool: False, Int: 0, Float: 0.}

        d = {}
        for name, value in self.traits().items():
            if name not in self._valid_vars:
                continue
            try:
                d[name] = zero_value[value.__class__]
            except KeyError:
                msg = ("Rate variable '%s' not of type Float, Bool or Int. " +
                       "Its zero value cannot be determined and it will " +
                       "not be treated by zerofy().") % name
                self.logger.info(msg)
        return d

    def zerofy(self):
        """将所有速率变量的值设为零（Int，Float）或 False（Boolean）。"""
        self._trait_values.update(self._rate_vars_zero)
