# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from .. import exceptions as exc


class VariableKiosk(dict):
    """
    VariableKiosk 用于在PCSE中注册和发布状态变量。

    实例化VariableKiosk不需要任何参数。
    所有在PCSE中定义的变量都会被注册到VariableKiosk中，
    但通常只有其中一小部分变量会被kiosk发布。
    发布变量的值可以通过方括号方式获取，因为variableKiosk
    本质上是一个（稍微花哨一点的）字典。

    速率变量和状态变量的注册/注销通过
    `self.register_variable()` 和 `self.deregister_variable()` 方法完成，
    而 `set_variable()` 方法用于更新已发布变量的值。
    通常情况下，用户不需要直接调用这些方法，
    因为`StatesTemplate` 和 `RatesTemplate`中的逻辑会处理这些操作。

    最后，可以使用 `variable_exists()` 检查变量是否已注册，
    而 `flush_states()` 和 `flush_rates()` 用于移除（清空）已发布的
    状态变量和速率变量的值。

    示例::

        >>> import pcse
        >>> from pcse.base import VariableKiosk
        >>>
        >>> v = VariableKiosk()
        >>> id0 = 0
        >>> v.register_variable(id0, "VAR1", type="S", publish=True)
        >>> v.register_variable(id0, "VAR2", type="S", publish=False)
        >>>
        >>> id1 = 1
        >>> v.register_variable(id1, "VAR3", type="R", publish=True)
        >>> v.register_variable(id1, "VAR4", type="R", publish=False)
        >>>
        >>> v.set_variable(id0, "VAR1", 1.35)
        >>> v.set_variable(id1, "VAR3", 310.56)
        >>>
        >>> print v
        Contents of VariableKiosk:
         * Registered state variables: 2
         * Published state variables: 1 with values:
          - variable VAR1, value: 1.35
         * Registered rate variables: 2
         * Published rate variables: 1 with values:
          - variable VAR3, value: 310.56

        >>> print v["VAR3"]
        310.56
        >>> v.set_variable(id0, "VAR3", 750.12)
        Traceback (most recent call last):
          File "<stdin>", line 1, in <module>
          File "pcse/base.py", line 148, in set_variable
            raise exc.VariableKioskError(msg % varname)
        pcse.exceptions.VariableKioskError: Unregistered object tried to set the value of variable 'VAR3': access denied.
        >>>
        >>> v.flush_rates()
        >>> print v
        Contents of VariableKiosk:
         * Registered state variables: 2
         * Published state variables: 1 with values:
          - variable VAR1, value: 1.35
         * Registered rate variables: 2
         * Published rate variables: 1 with values:
          - variable VAR3, value: undefined

        >>> v.flush_states()
        >>> print v
        Contents of VariableKiosk:
         * Registered state variables: 2
         * Published state variables: 1 with values:
          - variable VAR1, value: undefined
         * Registered rate variables: 2
         * Published rate variables: 1 with values:
          - variable VAR3, value: undefined
    """

    def __init__(self):
        dict.__init__(self)
        self.registered_states = {}
        self.registered_rates = {}
        self.published_states = {}
        self.published_rates = {}

    def __setitem__(self, item, value):
        # 请使用 set_variable() 方法来设置变量
        msg = "See set_variable() for setting a variable."
        raise RuntimeError(msg)

    def __contains__(self, item):
        """检查 item 是否在 self.registered_states 或 self.registered_rates 中。"""
        return dict.__contains__(self, item)

    def __getattr__(self, item):
        """允许通过属性方式（如 'kiosk.LAI'）访问已发布的速率或状态变量。"""
        return dict.__getitem__(self, item)

    def __str__(self):
        # 返回 VariableKiosk 的内容信息字符串
        msg = "Contents of VariableKiosk:\n"
        msg += " * Registered state variables: %i\n" % len(self.registered_states)
        msg += " * Published state variables: %i with values:\n" % len(self.published_states)
        for varname in self.published_states:
            if varname in self:
                value = self[varname]
            else:
                value = "undefined"
            msg += "  - variable %s, value: %s\n" % (varname, value)
        msg += " * Registered rate variables: %i\n" % len(self.registered_rates)
        msg += " * Published rate variables: %i with values:\n" % len(self.published_rates)
        for varname in self.published_rates:
            if varname in self:
                value = self[varname]
            else:
                value = "undefined"
            msg += "  - variable %s, value: %s\n" % (varname, value)
        return msg

    def register_variable(self, oid, varname, type, publish=False):
        """
        注册一个变量名，该变量由具有指定 id 的对象注册，并给定变量类型

        :param oid: 注册此变量的状态/速率对象的 Python 内置 id() 函数获取的 id
        :param varname: 要注册的变量名，例如 "DVS"
        :param type: 变量类型，"R"（速率）或 "S"（状态），由状态/速率模板类自动管理
        :param publish: 是否在kiosk中发布变量，默认为 False
        """

        self._check_duplicate_variable(varname)
        if type.upper() == "R":
            self.registered_rates[varname] = oid
            if publish is True:
                self.published_rates[varname] = oid
        elif type.upper() == "S":
            self.registered_states[varname] = oid
            if publish is True:
                self.published_states[varname] = oid
        else:
            msg = "Variable type should be 'S'|'R'"
            raise exc.VariableKioskError(msg)

    def deregister_variable(self, oid, varname):
        """对象通过 id(object) 请求将变量 varname 从 kiosk 注销

        :param oid: 注册此变量的状态/速率对象的 Python 内置 id() 函数获取的 id
        :param varname: 要注销的变量名，例如 "DVS"
        """
        if varname in self.registered_states:
            # 注销已注册的状态变量
            if oid != self.registered_states[varname]:
                msg = "Wrong object tried to deregister variable '%s'." \
                      % varname
                raise exc.VariableKioskError(msg)
            else:
                self.registered_states.pop(varname)
            if varname in self.published_states:
                self.published_states.pop(varname)
        elif varname in self.registered_rates:
            # 注销已注册的速率变量
            if oid != self.registered_rates[varname]:
                msg = "Wrong object tried to deregister variable '%s'." \
                      % varname
                raise exc.VariableKioskError(msg)
            else:
                self.registered_rates.pop(varname)
            if varname in self.published_rates:
                self.published_rates.pop(varname)
        else:
            msg = "Failed to deregister variabe '%s'!" % varname
            raise exc.VariableKioskError(msg)

        # 最后从内部字典中移除该变量的值
        if varname in self:
            self.pop(varname)

    def _check_duplicate_variable(self, varname):
        """检查变量是否已被注册，防止重复注册。"""
        if varname in self.registered_rates or \
                varname in self.registered_states:
            msg = "Duplicate state/rate variable '%s' encountered!"
            raise exc.VariableKioskError(msg % varname)

    def set_variable(self, id, varname, value):
        """允许拥有 id 的对象设置变量 varname 的值

        :param id: 注册该变量的状态/速率对象的 Python 内置 id() 函数获取的 id
        :param varname: 要更新的变量名
        :param value: 要赋予变量的值
        """

        if varname in self.published_rates:
            # 如果变量在发布的速率变量列表中
            if self.published_rates[varname] == id:
                # 如果拥有者的id匹配，则设置变量值
                dict.__setitem__(self, varname, value)
            else:
                msg = "Unregistered object tried to set the value " + \
                      "of variable '%s': access denied."
                raise exc.VariableKioskError(msg % varname)
        elif varname in self.published_states:
            # 如果变量在发布的状态变量列表中
            if self.published_states[varname] == id:
                # 如果拥有者的id匹配，则设置变量值
                dict.__setitem__(self, varname, value)
            else:
                msg = "Unregistered object tried to set the value of variable " \
                      "%s: access denied."
                raise exc.VariableKioskError(msg % varname)
        else:
            # 变量没有被发布
            msg = "Variable '%s' not published in VariableKiosk."
            raise exc.VariableKioskError(msg % varname)

    def variable_exists(self, varname):
        """ 如果状态/速率变量已在kiosk中注册，则返回True。

        :param varname: 要检查是否注册的变量名。
        """

        if varname in self.registered_rates or \
                varname in self.registered_states:
            return True
        else:
            return False

    def flush_rates(self):
        """清空所有已发布速率变量的值。"""
        for key in self.published_rates.keys():
            self.pop(key, None)

    def flush_states(self):
        """清空所有状态变量的值。"""
        for key in self.published_states.keys():
            self.pop(key, None)
