# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 与 Herman Berghuijs, 2024年1月

from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..util import limit
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject, VariableKiosk

class WOFOST_Storage_Organ_Dynamics(SimulationObject):
    """贮藏器官动态的实现。
    
    在WOFOST中，贮藏器官是植物最简单的组成部分，由静态的生物量池组成。贮藏器官的生长是光合产物分配的结果。贮藏器官的死亡未实现，相应的速率变量（DRSO）始终设为零。
    
    荚果是植株冠层中的绿色部分，因此可以对植物的总光合有效面积作出贡献。这通过荚果面积指数（PAI）来表达，PAI是通过将荚果生物量与一个固定的比荚面积（SPA）相乘获得的。

    **模拟参数**
    
    =======  ============================================= =======  ============
     名称     描述                                           类型     单位
    =======  ============================================= =======  ============
    TDWI     作物初始总干重                                 SCr      |kg ha-1|
    SPA      比荚面积                                       SCr      |ha kg-1|
    =======  ============================================= =======  ============    

    **状态变量**

    =======  ================================================= ==== ============
     名称     描述                                             发布    单位
    =======  ================================================= ==== ============
    PAI      荚果面积指数                                       Y       -
    WSO      活贮藏器官重                                       Y     |kg ha-1|
    DWSO     死贮藏器官重                                       N     |kg ha-1|
    TWSO     贮藏器官总重                                       Y     |kg ha-1|
    =======  ================================================= ==== ============

    **速率变量**

    =======  ================================================= ==== ============
     名称     描述                                             发布         单位
    =======  ================================================= ==== ============
    GRSO     贮藏器官生长速率                                   N   |kg ha-1 d-1|
    DRSO     贮藏器官死亡速率                                   N   |kg ha-1 d-1|
    GWSO     贮藏器官生物量净变化                               N   |kg ha-1 d-1|
    =======  ================================================= ==== ============
    
    **发送与接收的信号**
    
    无
    
    **外部依赖**
    
    =======  =================================== =================  ============
     名称     描述                                   来源                单位
    =======  =================================== =================  ============
    ADMI     地上部干物质增长                     CropSimulation    |kg ha-1 d-1|
    FO       分配到贮藏器官的生物量分数           DVS_Partitioning   - 
    FR       分配到根的生物量分数                 DVS_Partitioning   - 
    =======  =================================== =================  ============
    """

    class Parameters(ParamTemplate):      
        SPA  = Float(-99.)
        TDWI = Float(-99.)

    class StateVariables(StatesTemplate):
        WSO  = Float(-99.) # 活贮藏器官重
        DWSO = Float(-99.) # 死贮藏器官重
        TWSO = Float(-99.) # 贮藏器官总重
        PAI  = Float(-99.) # 荚果面积指数

    class RateVariables(RatesTemplate):
        GRSO = Float(-99.)
        DRSO = Float(-99.)
        GWSO = Float(-99.)
        
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，按键值对提供参数
        """

        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk, publish = ["GRSO"])
        self.kiosk = kiosk
        
        # 初始化状态变量
        params = self.params
        # 初始贮藏器官生物量
        FO = self.kiosk["FO"]
        FR = self.kiosk["FR"]
        WSO  = (params.TDWI * (1-FR)) * FO
        DWSO = 0.
        TWSO = WSO + DWSO
        # 初始荚果面积指数
        PAI = WSO * params.SPA

        self.states = self.StateVariables(kiosk, publish=["TWSO","WSO","PAI"],
                                          WSO=WSO, DWSO=DWSO, TWSO=TWSO,
                                          PAI=PAI)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates  = self.rates
        states = self.states
        params = self.params
        k = self.kiosk
        
        FO = self.kiosk["FO"]
        ADMI = self.kiosk["ADMI"]

        # 贮藏器官的生长/死亡速率
        rates.GRSO = ADMI * FO
        rates.DRSO = 0.0
        rates.GWSO = rates.GRSO - rates.DRSO + k.REALLOC_SO

    @prepare_states
    def integrate(self, day, delt=1.0):
        params = self.params
        rates = self.rates
        states = self.states

        # 茎生物量（活体，死亡，总计）
        states.WSO += rates.GWSO
        states.DWSO += rates.DRSO
        states.TWSO = states.WSO + states.DWSO

        # 计算荚果面积指数（SAI）
        states.PAI = states.WSO * params.SPA

    @prepare_states
    def _set_variable_WSO(self, nWSO):
        s = self.states
        p = self.params
        oWSO, oTWSO, oPAI = s.WSO, s.TWSO, s.PAI
        s.WSO = nWSO
        s.TWSO = s.DWSO + nWSO
        s.PAI = s.WSO * p.SPA

        increments = {"WSO": s.WSO - oWSO,
                      "PAI": s.PAI - oPAI,
                      "TWSO": s.TWSO - oTWSO}
        return increments