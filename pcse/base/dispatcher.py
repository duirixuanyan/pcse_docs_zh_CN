# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
from pydispatch import dispatcher


class DispatcherObject(object):
    """该类只定义了 _send_signal() 和 _connect_signal() 方法。

    该类只用于继承，不应被直接使用。
    """

    def _send_signal(self, signal, *args, **kwargs):
        """使用 dispatcher 模块发送 <signal>。

        此 SimulationObject 的 VariableKiosk 用作 signal 的发送者。
        传递给 _send_signal() 方法的附加参数会传递给 dispatcher.send()。
        """

        self.logger.debug("Sent signal: %s" % signal)
        dispatcher.send(signal=signal, sender=self.kiosk, *args, **kwargs)

    def _connect_signal(self, handler, signal):
        """使用 dispatcher 模块将 handler 连接到 signal。

        该 handler 只会对 sender 是当前 SimulationObject 的 VariableKiosk 的信号作出反应。
        这样可以确保在同一运行时环境中的不同 PCSE 模型实例不会相互响应各自的信号。
        """

        dispatcher.connect(handler, signal, sender=self.kiosk)
        self.logger.debug("Connected handler '%s' to signal '%s'." % (handler, signal))
