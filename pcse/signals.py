# -*- coding: utf-8 -*-
# Copyright (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2024
"""本模块定义和描述 PCSE 中使用的信号

PCSE 使用信号通知各组件事件的发生，如播种、收获和终止。
可以通过任意 SimulationObject 的 `SimulationObject._send_signal()` 方法发送事件信号。
同理，任意 SimulationObject 也可以通过 `SimulationObject._connect_signal()` 方法注册处理器以接收信号。
可以通过位置参数或关键字参数将变量传递给信号的处理器。
但强烈不建议在发送信号时使用位置参数，以避免位置参数和关键字参数之间的冲突。

下面的例子有助于说明 PCSE 中信号的使用方法，更多信息也可参见 PyDispatcher_ 的文档::

    import sys, os
    import math
    sys.path.append('/home/wit015/Sources/python/pcse/')
    import datetime as dt
    
    import pcse
    from pcse.base import SimulationObject, VariableKiosk
    
    mysignal = "My first signal"
    
    class MySimObj(SimulationObject):
        
        def initialize(self, day, kiosk):
            self._connect_signal(self.handle_mysignal, mysignal)
    
        def handle_mysignal(self, arg1, arg2):
            print "Value of arg1,2: %s, %s" % (arg1, arg2)
    
        def send_signal_with_exact_arguments(self):
            self._send_signal(signal=mysignal, arg2=math.pi, arg1=None)
    
        def send_signal_with_more_arguments(self):
            self._send_signal(signal=mysignal, arg2=math.pi, arg1=None, 
                              extra_arg="extra")
    
        def send_signal_with_missing_arguments(self):
            self._send_signal(signal=mysignal, arg2=math.pi, extra_arg="extra")
    
            
    # 创建 MySimObj 实例
    day = dt.date(2000,1,1)
    k = VariableKiosk()
    mysimobj = MySimObj(day, k)
    
    # 精确发送所需数量的关键字参数
    mysimobj.send_signal_with_exact_arguments()
    
    # 发送了一个额外的关键字参数 'extra_arg'，会被忽略
    mysimobj.send_signal_with_more_arguments()
    
    # 发送信号时缺少 'arg1' 关键字参数，而处理器期望该参数，将导致错误，抛出 TypeError
    try:
        mysimobj.send_signal_with_missing_arguments()
    except TypeError, exc:
        print "TypeError occurred: %s" % exc

将上述代码保存为 `test_signals.py` 并导入后输出如下::

    >>> import test_signals
    Value of arg1,2: None, 3.14159265359
    Value of arg1,2: None, 3.14159265359
    TypeError occurred: handle_mysignal() takes exactly 3 non-keyword arguments (1 given)

目前 PCSE 内部使用如下信号及其关键字参数：

**CROP_START**

 表示新作物生长周期的开始::
 
     self._send_signal(signal=signals.crop_start, day=<date>,
                       crop_name=<string>, variety_name=<string>,
                       crop_start_type=<string>, crop_end_type=<string>)

 `signals.crop_start` 的关键字参数:
    
    * day: 当前日期
    * crop_name: 指定作物的字符串
    * variety_name: 指定作物品种的字符串
    * crop_start_type: 'sowing' 或 'emergence'
    * crop_end_type: 'maturity'、'harvest' 或 'earliest'

**CROP_FINISH**

 表示当前作物生长周期结束::
 
     self._send_signal(signal=signals.crop_finish, day=<date>,
                       finish_type=<string>, crop_delete=<True|False>)

`signals.crop_finish` 的关键字参数:

    * day: 当前日期
    * finish_type: 描述仿真结束原因的字符串，如 maturity、harvest、所有叶片死亡、达到最大持续时间等
    * crop_delete: 如果 CropSimulation 对象需要从系统中删除（比如作物轮作实现），设为 True，默认 False

**TERMINATE**
 
 表示整个系统应终止（作物 & 土壤水分平衡），并收集终端输出::

    self._send_signal(signal=signals.terminate)

 此信号无关键字参数

**OUTPUT**

 表示模型状态需要被保存以供以后使用::

    self._send_signal(signal=signals.output)
 
 此信号无关键字参数

**SUMMARY_OUTPUT**

 表示模型状态需要被保存以供以后使用，
 SUMMARY_OUTPUT 仅在收到 CROP_FINISH 信号并指示作物仿真需要结束时生成::

    self._send_signal(signal=signals.output)

 此信号无关键字参数

**APPLY_N**

用于施加氮肥事件::

    self._send_signal(signal=signals.apply_n, N_amount=<float>, N_recovery<float>)

`signals.apply_n` 的关键字参数:

    * N_amount: 当天施加的氮肥量（kg/ha）
    * N_recovery: 所用肥料类型的回收率

**APPLY_N_SNOMIN**

用于 SNOMIN 模块中施加氮肥::

    self._send_signal(signal=signals.apply_n_snomin,amount=<float>, application_depth=<float>,
                      cnratio=<float>, initial_age=<float>, f_NH4N=<float>, f_NO3N=<float>,
                      f_orgmat=<float>)

`signals.apply_n_snomin` 的关键字参数:

    * amount: 改良剂中材料的总量（kg material ha-1）
    * application_depth: 改良剂施入土壤的深度（cm）
    * cnratio: 材料中有机物的碳氮比（kg C kg-1 N）
    * initial_age: 材料中有机物的初始表观年龄（年）
    * f_NH4N: 材料中 NH4+-N 的分数（kg NH4+-N kg-1 material）
    * f_NO3N: 材料中 NO3--N 的分数（kg NO3--N kg-1 material）
    * f_orgmat: 改良剂中有机物的分数（kg OM kg-1 material）

**IRRIGATE**

用于发送灌溉事件::

    self._send_signal(signal=signals.irrigate, amount=<float>, efficiency=<float>)

`signals.irrigate` 的关键字参数:

    * amount: 当天施加的灌溉水量（cm 单位）
    * efficiency: 灌溉效率，即加入土壤库总水量为 amount * efficiency

**MOWING**

用于 LINGRA/LINGRA-N 模型发送割草事件::

    self._send_signal(signal=signals.mowing, biomass_remaining=<float>)

`signals.mowing` 的关键字参数:

    * biomass_remaining: 割草后剩余生物量（kg/ha）

.. _PyDispatcher: http://pydispatcher.sourceforge.net/
"""

crop_start = "CROP_START"
crop_emerged = "CROP_EMERGED"
crop_finish = "CROP_FINISH"
terminate = "TERMINATE"
output = "OUTPUT"
summary_output = "SUMMARY_OUTPUT"
apply_n = "APPLY_N"
apply_n_snomin = "APPLY_N_SNOMIN"
irrigate = "IRRIGATE"
mowing = "MOWING"
