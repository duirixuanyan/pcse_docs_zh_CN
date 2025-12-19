# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import datetime

from ..traitlets import Float, Instance
from ..decorators import prepare_rates, prepare_states
from ..base import StatesTemplate, SimulationObject
from .. import signals

from .evapotranspiration import Simple_Evapotranspiration as Evapotranspiration
from .root_dynamics import Simple_Root_Dynamics as Root_Dynamics
from .leaf_dynamics import CSDM_Leaf_Dynamics as Leaf_Dynamics


class GreenLayerCrop(SimulationObject):
    """作物模型的顶层对象，用于组织作物模拟的不同组成部分。
    该模型仅模拟作物用水，不模拟生物量增长等过程。本方法类似于
    FAO的水分需求满足指数（WRSI）。

    本类嵌入的模拟对象包含如下过程：

        1. 蒸散发过程取自WOFOST模型
        2. 叶片动态按CSDM模型定义（逻辑/指数LAI曲线）
        3. 根系动态取自WOFOST模型

    **模拟参数:**
    
    本类没有，但请参见蒸散发、叶片动态和根系动态相关类。

    **状态变量:**

    =======  ================================================= ==== ============
     名称     描述                                             Pbl     单位
    =======  ================================================= ==== ============
    CTRAT    作物总蒸腾量                                       N      cm
    DOF      表示作物模拟结束日期的日期                         N      -
             （日）
    SumAET   作物加土壤的实际蒸散发总量                         N      cm
    SumPET   作物加土壤的潜在蒸散发总量                         N      cm
    FINISH   表示终止模拟原因的字符串                           N      -
             （成熟、收获、叶片死亡等）
    WRSI     水分需求满足指数，计算方式为                       N      %
             SumAET/SumPET * 100
    =======  ================================================= ==== ============

     **变化率变量:**

    无
    """
    
    # 作物模拟的子模型组件
    evtra = Instance(SimulationObject)
    lv_dynamics = Instance(SimulationObject)
    ro_dynamics = Instance(SimulationObject)
    
    class StateVariables(StatesTemplate):
        CTRAT = Float(-99.) # 作物总蒸腾量
        DOF = Instance(datetime.date)
        FINISH = Instance(str)
        WRSI = Float()
        SumPET = Float() # 潜在作物蒸散发总量
        SumAET = Float() # 实际作物蒸散发总量

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: 提供参数键/值对的`ParameterProvider`对象
        """

        self.kiosk = kiosk
        
        # 初始化作物的组件
        self.evtra = Evapotranspiration(day, kiosk, parvalues)
        self.ro_dynamics = Root_Dynamics(day, kiosk, parvalues)
        self.lv_dynamics = Leaf_Dynamics(day, kiosk, parvalues)

        self.states = self.StateVariables(kiosk, CTRAT=0.0, DOF=None, FINISH=None, WRSI=100,
                                          SumPET=0., SumAET=0.)
            
        # 分配CROP_FINISH信号的处理函数
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)

    @prepare_rates
    def calc_rates(self, day, drv):
        states = self.states

        # （蒸）散发速率
        self.evtra(day, drv)

        # 根系生长
        self.ro_dynamics.calc_rates(day, drv)
        # 叶片生长
        self.lv_dynamics.calc_rates(day, drv)

    @prepare_states
    def integrate(self, day, delt=1.0):
        states = self.states
        
        # 对叶片、贮藏器官、茎及根的状态集成
        self.ro_dynamics.integrate(day, delt)
        self.lv_dynamics.integrate(day, delt)

        # 作物总蒸腾量 (CTRAT)
        states.CTRAT += self.kiosk["TRA"] * delt

        # 潜在和实际蒸散发总量
        states.SumPET += (self.kiosk["TRAMX"] + self.kiosk["EVS"]) * delt
        states.SumAET += (self.kiosk["TRA"] + self.kiosk["EVS"]) * delt
        # 按照FAO方法，计算水分需求满足指数
        states.WRSI = states.SumAET/states.SumPET * 100
        
    def _on_CROP_FINISH(self, day, finish_type, *args, **kwargs):
        """设置作物模拟结束日期(DOF)及终止原因(FINISH)的处理函数。"""
        self._for_finalize["DOF"] = day
        self._for_finalize["FINISH"]= finish_type
