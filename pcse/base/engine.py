# -*- coding: utf-8 -*-
# Copyright (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2024
"""用于创建PCSE仿真单元的基类。

通常这些类不应直接使用，而是应在创建PCSE仿真单元时进行子类化。
"""
import types
import logging

from ..traitlets import (HasTraits, List, Float, Int, Instance, Dict, Bool, All)
from .dispatcher import DispatcherObject
from .simulationobject import SimulationObject


class BaseEngine(HasTraits, DispatcherObject):
    """Engine的基类，供继承使用"""

    def __init__(self):
        HasTraits.__init__(self)
        DispatcherObject.__init__(self)

    @property
    def logger(self):
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)

    def __setattr__(self, attr, value):
        # __setattr__已经被修改，用于强制要求类属性在赋值前必须被定义。
        # 有以下几个例外情况：
        # 1. 如果属性名称以下划线‘_’开头，将直接赋值。
        # 2. 如果属性值是函数类型(如types.FunctionType)，将直接赋值。
        #    这是因为 'prepare_states' 和 'prepare_rates' 装饰器会将包装函数
        #    'calc_rates', 'integrate' 及可选的 'finalize' 赋值给Simulation Object。
        #    由于这些类方法不是定义的属性，这会和 __setattr__ 冲突。
        #
        # 最后，如果赋值的属性值是SimulationObject对象，或者已存在的属性值是SimulationObject，
        #   则需要重建子SimulationObject列表。

        if attr.startswith("_") or type(value) is types.FunctionType:
            HasTraits.__setattr__(self, attr, value)
        elif hasattr(self, attr):
            HasTraits.__setattr__(self, attr, value)
        else:
            msg = "Assignment to non-existing attribute '%s' prevented." % attr
            raise AttributeError(msg)

    @property
    def subSimObjects(self):
        """查找嵌入在自身中的SimulationObjects。"""

        subSimObjects = []
        defined_traits = self.__dict__["_trait_values"]
        for attr in defined_traits.values():
            if isinstance(attr, SimulationObject):
                subSimObjects.append(attr)
        return subSimObjects

    def get_variable(self, varname):
        """返回指定状态或速率变量的值。

        :param varname: 变量名称。

        注意：`get_variable()` 会先精确查找 `varname`（区分大小写）。
        如果无法找到变量，则会查找该变量的全大写名称。这仅仅是为了方便。
        """

        # 检查变量是否已在kiosk中注册，同时检查大写名称，因为大多数变量都以大写字母定义。
        # 如果变量未注册至kiosk，则直接返回None。
        if self.kiosk.variable_exists(varname):
            v = varname
        elif self.kiosk.variable_exists(varname.upper()):
            v = varname.upper()
        else:
            return None

        if v in self.kiosk:
            return self.kiosk[v]

        # 通过遍历层级关系查找变量
        value = None
        for simobj in self.subSimObjects:
            value = simobj.get_variable(v)
            if value is not None:
                break
        return value

    def zerofy(self):
        """将所有子SimulationObjects的速率变量值归零。"""
        # 遍历所有可能的子SimulationObject对象。
        if self.subSimObjects is not None:
            for simobj in self.subSimObjects:
                simobj.zerofy()
