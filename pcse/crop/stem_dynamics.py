# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl), 2024年4月

from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..util import limit, AfgenTrait
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject, VariableKiosk

class WOFOST_Stem_Dynamics(SimulationObject):
    """茎生物量动态的实现。
    
    茎生物量的增加来源于分配到茎系统的同化物。茎的死亡定义为当前茎生物量
    乘以相对死亡率（`RDRSTB`）。后者是发育阶段（`DVS`）的函数。
    
    茎是植物冠层中的绿色器官，因此也可以贡献于总光合活性面积。
    这通过茎面积指数（SAI）表现出来，SAI由茎生物量与茎面积系数（SSATB）相乘获得，后者为DVS的函数。

    **模拟参数**：
    
    =======  ================================ =======  ============
     名称         描述                         类型     单位
    =======  ================================ =======  ============
    TDWI     初始作物干物质量                  SCr       |kg ha-1|
    RDRSTB   茎相对死亡率，作为发育阶段的函数  TCr       -
    SSATB    茎面积系数，作为发育阶段的函数    TCr       |ha kg-1|
    =======  ================================ =======  ============
    

    **状态变量**

    =======  ========================== ==== ============
     名称      描述                     公布      单位
    =======  ========================== ==== ============
    SAI      茎面积指数                   Y     -
    WST      活茎质量                     Y     |kg ha-1|
    DWST     死茎质量                     N     |kg ha-1|
    TWST     总茎质量                     Y     |kg ha-1|
    =======  ========================== ==== ============

    **速率变量**

    =======  ========================== ==== ============
     名称      描述                     公布      单位
    =======  ========================== ==== ============
    GRST     茎生物量增长速率             N   |kg ha-1 d-1|
    DRST     茎生物量死亡速率             N   |kg ha-1 d-1|
    GWST     茎生物量净变化速率           N   |kg ha-1 d-1|
    =======  ========================== ==== ============
    
    **发送或处理的信号**
    
    无
    
    **外部依赖**：
    
    =======  =========================== ================  ============
     名称        描述                      提供者             单位
    =======  =========================== ================  ============
    DVS      作物发育阶段                DVS_Phenology      -
    ADMI     地上部分干物质增加          CropSimulation    |kg ha-1 d-1|
    FR       分配到根的生物量分数        DVS_Partitioning   - 
    FS       分配到茎的生物量分数        DVS_Partitioning   - 
    =======  =========================== ================  ============
    """

    class Parameters(ParamTemplate):      
        RDRSTB = AfgenTrait()
        SSATB  = AfgenTrait()
        TDWI   = Float(-99.)

    class StateVariables(StatesTemplate):
        WST  = Float(-99.)
        DWST = Float(-99.)
        TWST = Float(-99.)
        SAI  = Float(-99.) # 茎面积指数

    class RateVariables(RatesTemplate):
        GRST = Float(-99.)
        DRST = Float(-99.)
        GWST = Float(-99.)
        
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 当前PCSE实例的变量kiosk
        :param parvalues: 提供参数（键/值对）的`ParameterProvider`对象
        """
        
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk, publish=["DRST", "GRST"])
        self.kiosk  = kiosk

        # 初始化状态
        params = self.params
        # 设置初始茎生物量
        FS = self.kiosk["FS"]
        FR = self.kiosk["FR"]
        WST  = (params.TDWI * (1-FR)) * FS
        DWST = 0.
        TWST = WST + DWST
        # 初始茎面积指数
        DVS = self.kiosk["DVS"]
        SAI = WST * params.SSATB(DVS)

        self.states = self.StateVariables(kiosk, publish=["TWST","WST","SAI"],
                                          WST=WST, DWST=DWST, TWST=TWST, SAI=SAI)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates  = self.rates
        states = self.states
        params = self.params
        k = self.kiosk
        
        DVS = self.kiosk["DVS"]
        FS = self.kiosk["FS"]
        ADMI = self.kiosk["ADMI"]

        # 茎的生长/死亡速率
        rates.GRST = ADMI * FS
        rates.DRST = params.RDRSTB(DVS) * states.WST
        rates.GWST = rates.GRST - rates.DRST - k.REALLOC_ST

    @prepare_states
    def integrate(self, day, delt=1.0):
        params = self.params
        rates = self.rates
        states = self.states

        # 茎生物量（活茎、死茎、总茎）
        states.WST += rates.GWST
        states.DWST += rates.DRST
        states.TWST = states.WST + states.DWST

        # 计算茎面积指数（SAI）
        DVS = self.kiosk["DVS"]
        states.SAI = states.WST * params.SSATB(DVS)

    @prepare_states
    def _set_variable_WST(self, nWST):
        s = self.states
        p = self.params
        k = self.kiosk

        oWST = s.WST
        oTWST = s.TWST
        oSAI = s.SAI
        s.WST = nWST
        s.TWST = s.DWST + nWST
        s.SAI = s.WST * p.SSATB(k.DVS)

        increments = {"WST": s.WST - oWST,
                      "SAI": s.SAI - oSAI,
                      "TWST": s.TWST - oTWST}
        return increments
