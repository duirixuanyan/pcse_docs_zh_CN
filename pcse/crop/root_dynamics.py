# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen 环境研究中心, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from copy import deepcopy

from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..util import limit, merge_dict, AfgenTrait
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject, VariableKiosk
    


class WOFOST_Root_Dynamics(SimulationObject):
    """根系生物量动态与根系深度。
    
    在WOFOST中，根系生长和根系生物量动态是两个独立的过程，
    唯一的例外是当不再有生物量分配到根系时，根系生长才会停止。
    
    根系生物量的增加来源于分配到根系的同化物。根死亡定义为当前根系生物量
    乘以相对死亡率（`RDRRTB`），该死亡率是发育阶段（`DVS`）的函数。
    
    根系深度的增加是随时间线性扩展，直到达到最大根系深度（`RDM`）。
    
    **模拟参数**
    
    =======  ============================================= =======  ============
     名称     说明                                         类型       单位
    =======  ============================================= =======  ============
    RDI      初始根系深度                                  SCr       cm
    RRI      根系深度每日增长                              SCr      |cm day-1|
    RDMCR    作物最大根系深度                              SCR       cm
    RDMSOL   土壤最大根系深度                              SSo       cm
    TDWI     初始作物总干重                                SCr      |kg ha-1|
    IAIRDU   根系内有（1）或无（0）通气道                  SCr        -
    RDRRTB   根系相对死亡率（发育阶段的函数）              TCr        -
    =======  ============================================= =======  ============
    

    **状态变量**

    =======  ================================================= ==== ============
     名称     说明                                             公布     单位
    =======  ================================================= ==== ============
    RD       当前根系深度                                       Y      cm
    RDM      可达最大根系深度为土壤和作物最大深度的最小值       N      cm
    WRT      活根生物量                                         Y    |kg ha-1|
    DWRT     死根生物量                                         N    |kg ha-1|
    TWRT     根系总生物量                                       Y    |kg ha-1|
    =======  ================================================= ==== ============

    **变化率变量**

    =======  ================================================= ==== ============
     名称     说明                                             公布     单位
    =======  ================================================= ==== ============
    RR       根系深度增长速率                                   N      cm
    GRRT     根系生物量增长速率                                 N   |kg ha-1 d-1|
    DRRT     根系生物量死亡速率                                 N   |kg ha-1 d-1|
    GWRT     根系生物量净变化                                   N   |kg ha-1 d-1|
    =======  ================================================= ==== ============
    
    **发送或处理的信号**
    
    无
    
    **外部依赖：**
    
    =======  =================================== =================  ============
     名称     说明                                  提供模块          单位
    =======  =================================== =================  ============
    DVS      作物发育阶段                         DVS_Phenology       -
    DMI      总干物质增加                         CropSimulation    |kg ha-1 d-1|
    FR       分配给根的生物量分数                 DVS_Partitioning    - 
    =======  =================================== =================  ============
    """

    """
    重要说明
    当前的根系发育是线性的，仅取决于分配到根系的光合产物比例（FR），而不是光合产物的绝对量。这意味着即使在冬季由于低温没有同化产物产生，根系仍然会继续生长。此前我们曾讨论过是否应改变这种行为，使根系生长依赖于分配到根系的光合产物量：也就是说，当无可用于生长的同化产物时，根系生长应停止。
    
    最终，我们决定不改变根系模型，而保持WOFOST的原始方法，主要基于以下理由：
    - 在干燥的土壤表层可能会造成严重的干旱胁迫，使同化物接近于零。在这种情况下，如果根系生长依赖于同化产物，根系将无法生长，而其实根区下方依然有水。因此，让根系生长依赖同化产物容易导致模型在干旱条件下（例如地中海南部等）不稳定。
    - 为解决上述问题，曾探讨过其他方案：例如仅在某一发育阶段后才施加该限制，或令根生长取决于未生根土壤层的含水量。但所有这些解决方案都引入了没有明确解释的任意参数。因此全部被弃用。
    
    我们认为，目前对根系生长的认识尚不足以提出更完善、更符合生物物理学的WOFOST根系生长建模方法。  
    """

    class Parameters(ParamTemplate):
        RDI    = Float(-99.)
        RRI    = Float(-99.)
        RDMCR  = Float(-99.)
        RDMSOL = Float(-99.)
        TDWI   = Float(-99.)
        IAIRDU = Float(-99)
        RDRRTB = AfgenTrait()
                    
    class RateVariables(RatesTemplate):
        RR   = Float(-99.)
        GRRT = Float(-99.)
        DRRT = Float(-99.)
        GWRT = Float(-99.)

    class StateVariables(StatesTemplate):
        RD   = Float(-99.)
        RDM  = Float(-99.)
        WRT  = Float(-99.)
        DWRT = Float(-99.)
        TWRT = Float(-99.)
        
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始的日期
        :param kiosk: 当前 PCSE 实例的变量 kiosk
        :param parvalues: 提供参数及其键值对的 `ParameterProvider` 对象
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["DRRT", "GRRT"])
        self.kiosk = kiosk
        
        # 初始状态
        params = self.params
        # 初始根系深度状态
        rdmax = max(params.RDI, min(params.RDMCR, params.RDMSOL))
        RDM = rdmax
        RD = params.RDI
        # 初始根系生物量状态
        WRT  = params.TDWI * self.kiosk.FR
        DWRT = 0.
        TWRT = WRT + DWRT

        self.states = self.StateVariables(kiosk, publish=["RD","WRT", "TWRT"],
                                          RD=RD, RDM=RDM, WRT=WRT, DWRT=DWRT,
                                          TWRT=TWRT)

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        s = self.states
        k = self.kiosk

        # 根系生物量增加量
        r.GRRT = k.FR * k.DMI
        r.DRRT = s.WRT * p.RDRRTB(k.DVS)
        r.GWRT = r.GRRT - r.DRRT
        
        # 根系深度增长量
        r.RR = min((s.RDM - s.RD), p.RRI)
        # 当分配到根（FR）为零时，不让根系生长
        if k.FR == 0.:
            r.RR = 0.
    
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 活根干重
        states.WRT += rates.GWRT
        # 死根干重
        states.DWRT += rates.DRRT
        # 总根干重（活+死）
        states.TWRT = states.WRT + states.DWRT

        # 新的根系深度
        states.RD += rates.RR


    @prepare_states
    def _set_variable_WRT(self, nWRT):
        """将WRT的值更新为输入的新值。

        相关的状态变量也将被更新，所有被调整状态变量的增量将作为字典返回。
        """
        states = self.states

        # 存储旧的状态值
        oWRT = states.WRT
        oTWRT = states.TWRT

        # 应用新的根重并调整总（死+活）根重
        states.WRT = nWRT
        states.TWRT = states.WRT + states.DWRT

        increments = {"WRT": states.WRT - oWRT,
                      "TWLRT": states.TWRT - oTWRT}
        return increments



class Simple_Root_Dynamics(SimulationObject):
    """线性根系生长的简单类。

    根系深度的增加是一个随时间线性扩展的过程，直到达到最大根系深度（`RDM`）。

    **模拟参数**

    =======  =============================== =======  ============
     名称      描述                           类型      单位
    =======  =============================== =======  ============
    RDI      初始根系深度                      SCr      cm
    RRI      根系深度的日增加量                SCr      |cm day-1|
    RDMCR    作物可达到的最大根系深度          SCR      cm
    RDMSOL   土壤可达到的最大根系深度          SSo      cm
    =======  =============================== =======  ============

    **状态变量**

    =======  ======================================= ==== ============
     名称      描述                                   Pbl      单位
    =======  ======================================= ==== ============
    RD       当前根系深度                              Y     cm
    RDM      在土壤和作物最大根系深度下                N     cm
             可达的最大根系深度
    =======  ======================================= ==== ============

    **速率变量**

    =======  ======================================= ==== ============
     名称      描述                                   Pbl      单位
    =======  ======================================= ==== ============
    RR       根系深度的生长速率                         N    cm
    =======  ======================================= ==== ============

    **信号发送或处理**

    无

    **外部依赖：**

    无
    """

    class Parameters(ParamTemplate):
        """用于存储根系深度参数的 traits-based 类"""
        RDI    = Float(-99.)    
        RRI    = Float(-99.)
        RDMCR  = Float(-99.)
        RDMSOL = Float(-99.)
                    
    class RateVariables(RatesTemplate):
        """用于存储根系速率变量的类"""
        RR   = Float(-99.)

    class StateVariables(StatesTemplate):
        """用于存储根系状态变量的类"""
        RD   = Float(-99.)
        RDM  = Float(-99.)
        
    def initialize(self, day, kiosk, parameters):
        """
        :param day: 模拟开始日期
        :param kiosk: 本 PCSE 实例的变量 kiosk
        :param parameters: 包含键值对的 ParameterProvider 对象
        """

        self.params = self.Parameters(parameters)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
        
        # 初始化状态
        params = self.params

        # 初始化根系深度状态
        rdmax = max(params.RDI, min(params.RDMCR, params.RDMSOL))
        RDM = rdmax
        RD = params.RDI

        self.states = self.StateVariables(kiosk, publish=["RD"],
                                          RD=RD, RDM=RDM)
    @prepare_rates
    def calc_rates(self, day, drv):
        params = self.params
        rates = self.rates
        states = self.states
        
        # 根系深度的增加量
        rates.RR = min((states.RDM - states.RD), params.RRI)
    
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 新的根系深度
        states.RD += rates.RR
