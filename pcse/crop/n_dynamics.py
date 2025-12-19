#!/usr/bin/env python
# Herman Berghuijs (herman.berghuijs@wur.nl) 和 Allard de Wit (allard.dewit@wur.nl)，2024年4月

from .. import exceptions as exc
from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject
from ..util import AfgenTrait
from .nutrients import N_Demand_Uptake


class N_Crop_Dynamics(SimulationObject):
    """氮素作物整体动态的实现。

    NPK_Crop_Dynamics 实现了作物体内氮素收支的整体逻辑。

    **模拟参数**
    
    =============  ================================================= =======================
     名称           描述                                             单位
    =============  ================================================= =======================
    NMAXLV_TB      叶片中氮最大浓度，作为dvs的函数                    kg N kg-1 干物质
    NMAXRT_FR      根中氮最大浓度为叶片最大氮浓度的分数                -
    NMAXST_FR      茎中氮最大浓度为叶片最大氮浓度的分数                -
    NRESIDLV       叶片中残余氮比例                                    kg N kg-1 干物质
    NRESIDRT       根中残余氮比例                                      kg N kg-1 干物质
    NRESIDST       茎中残余氮比例                                      kg N kg-1 干物质
    =============  ================================================= =======================

    **状态变量**

    ==========  ============================================  ============
     名称        描述                                         单位
    ==========  ============================================  ============
    NamountLV     活叶中实际氮含量                             |kg N ha-1|
    NamountST     活茎中实际氮含量                             |kg N ha-1|
    NamountSO     活贮藏器官中实际氮含量                       |kg N ha-1|
    NamountRT     活根中实际氮含量                             |kg N ha-1| 
    Nuptake_T     吸收的氮总量                                 |kg N ha-1|
    Nfix_T        生物固氮总量                                 |kg N ha-1|
    ==========  ============================================  ============

    **速率变量**

    ===========  ============================================  ================
     名称         描述                                         单位
    ===========  ============================================  ================
    RNamountLV     叶片中氮的净增量                             |kg N ha-1 d-1|    
    RNamountST     茎中氮的净增量                               |kg N ha-1 d-1|
    RNamountRT     根中氮的净增量                               |kg N ha-1 d-1|    
    RNamountSO     贮藏器官中氮的净增量                         |kg N ha-1 d-1|
    RNdeathLV      叶片中氮的损失速率                           |kg N ha-1 d-1|
    RNdeathST      根中氮的损失速率                             |kg N ha-1 d-1|
    RNdeathRT      茎中氮的损失速率                             |kg N ha-1 d-1|
    RNloss         衰老导致的氮损失                             |kg N ha-1 d-1|
    ===========  ============================================  ================
    
    **发送或处理的信号**
    
    无
    
    **外部依赖**
    
    =======  ============================== ====================  ==============
     名称     描述                            提供者                单位
    =======  ============================== ====================  ==============
    DVS      作物发育阶段                   DVS_Phenology           -
    WLV      活叶干重                       WOFOST_Leaf_Dynamics  |kg ha-1|
    WRT      活根干重                       WOFOST_Root_Dynamics  |kg ha-1|
    WST      活茎干重                       WOFOST_Stem_Dynamics  |kg ha-1|
    DRLV     叶片死亡速率                   WOFOST_Leaf_Dynamics  |kg ha-1 d-1|
    DRRT     根死亡速率                     WOFOST_Root_Dynamics  |kg ha-1 d-1|
    DRST     茎死亡速率                     WOFOST_Stem_Dynamics  |kg ha-1 d-1|
    =======  ============================== ====================  ==============
    """

    demand_uptake = Instance(SimulationObject)

    NamountLVI = Float(-99.)  # 初始叶片中的土壤氮含量
    NamountSTI = Float(-99.)  # 初始茎中的土壤氮含量
    NamountRTI = Float(-99.)  # 初始根中的土壤氮含量
    NamountSOI = Float(-99.)  # 初始贮藏器官中的土壤氮含量

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()
        NMAXST_FR = Float(-99.)
        NMAXRT_FR = Float(-99.)
        NRESIDLV = Float(-99.)  # 叶片中残余氮比例 [kg N kg-1 干物质]
        NRESIDST = Float(-99.)  # 茎中残余氮比例 [kg N kg-1 干物质]
        NRESIDRT = Float(-99.)  # 根中残余氮比例 [kg N kg-1 干物质]

    class StateVariables(StatesTemplate):
        NamountLV = Float(-99.) # 叶片中氮含量 [kg N ha-1]
        NamountST = Float(-99.) # 茎中氮含量 [kg N]
        NamountSO = Float(-99.) # 贮藏器官中氮含量 [kg N]
        NamountRT = Float(-99.) # 根中氮含量 [kg N]
        NuptakeTotal = Float(-99.) # 吸收的总氮量 [kg N]
        NfixTotal = Float(-99.) # 固定的总生物氮 [kg N]
    
        NlossesTotal = Float(-99.)

    class RateVariables(RatesTemplate):
        RNamountLV = Float(-99.)  # 植物各器官中氮的净变化速率
        RNamountST = Float(-99.)
        RNamountRT = Float(-99.)
        RNdeathLV = Float(-99.)  # 叶片中氮的损失速率 [kg ha-1 d-1]
        RNdeathST = Float(-99.)  # 茎中氮的损失速率 [kg ha-1 d-1]
        RNdeathRT = Float(-99.)  # 根中氮的损失速率 [kg ha-1 d-1]
        RNloss = Float(-99.)
        
    def initialize(self, day, kiosk, parvalues):
        """
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: 参数的键/值对字典
        """  
    
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
    
        # 初始化npk_crop_dynamics的相关组件
        self.demand_uptake = N_Demand_Uptake(day, kiosk, parvalues)

        # 初始状态
        params = self.params
        k = kiosk

        # 初始各组分氮的含量
        self.NamountLVI = NamountLV = k.WLV * params.NMAXLV_TB(k.DVS)
        self.NamountSTI = NamountST = k.WST * params.NMAXLV_TB(k.DVS) * params.NMAXST_FR
        self.NamountRTI = NamountRT = k.WRT * params.NMAXLV_TB(k.DVS) * params.NMAXRT_FR
        self.NamountSOI = NamountSO = 0.
    
        self.states = self.StateVariables(kiosk,
                        publish=["NamountLV", "NamountST", "NamountRT", "NamountSO"],
                        NamountLV=NamountLV, NamountST=NamountST, NamountRT=NamountRT, NamountSO=NamountSO,
                        NuptakeTotal=0, NfixTotal=0.,
                        NlossesTotal=0)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates = self.rates
        params = self.params
        states = self.states
        k = self.kiosk
    
        self.demand_uptake.calc_rates(day, drv)

        # 植物器官损失引起的氮的损失计算
        if k.WLV > 0.:
            rates.RNdeathLV = (states.NamountLV / k.WLV) * k.DRLV
        else:
            rates.RNdeathLV = 0.
        if k.WST > 0.:
            rates.RNdeathST = (states.NamountST / k.WST) * k.DRST
        else:
            rates.RNdeathST = 0.
        if k.WRT > 0.:
            rates.RNdeathRT = (states.NamountRT / k.WRT) * k.DRRT
        else:
            rates.RNdeathRT= 0.

        # 叶、茎、根及贮藏器官氮的速率：吸收-转运-死亡
        # 贮藏器官只通过转运获得氮
        rates.RNamountLV = k.RNuptakeLV - k.RNtranslocationLV - rates.RNdeathLV
        rates.RNamountST = k.RNuptakeST - k.RNtranslocationST - rates.RNdeathST
        rates.RNamountRT = k.RNuptakeRT - k.RNtranslocationRT - rates.RNdeathRT
        rates.RNamountSO = k.RNuptakeSO + k.RNtranslocation        
        rates.RNloss = rates.RNdeathLV + rates.RNdeathST + rates.RNdeathRT

        self._check_N_balance(day)
        
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states
        k = self.kiosk

        # 叶、茎、根和贮藏器官中的氮含量
        states.NamountLV += rates.RNamountLV
        states.NamountST += rates.RNamountST
        states.NamountRT += rates.RNamountRT
        states.NamountSO += rates.RNamountSO
                
        self.demand_uptake.integrate(day, delt)

        # 从土壤总吸收的NPK量
        states.NuptakeTotal += k.RNuptake
        states.NfixTotal += k.RNfixation        
        states.NlossesTotal += rates.RNloss

    def _check_N_balance(self, day):
        s = self.states
        checksum = abs(s.NuptakeTotal + s.NfixTotal +
                       (self.NamountLVI + self.NamountSTI + self.NamountRTI + self.NamountSOI) -
                       (s.NamountLV + s.NamountST + s.NamountRT + s.NamountSO + s.NlossesTotal))

        if abs(checksum) >= 1.0:
            # 当氮流量不平衡时，抛出异常并显示相关信息
            msg = "N flows not balanced on day %s\n" % day
            msg += "Checksum: %f, Nuptake_T: %f, Nfix_T: %f\n" % (checksum, s.NuptakeTotal, s.NfixTotal)
            msg += "NamountLVI: %f, NamountSTI: %f, NamountRTI: %f, NamountSOI: %f\n"  % \
                   (self.NamountLVI, self.NamountSTI, self.NamountRTI, self.NamountSOI)
            msg += "NamountLV: %f, NamountST: %f, NamountRT: %f, NamountSO: %f\n" % \
                   (s.NamountLV, s.NamountST, s.NamountRT, s.NamountSO)
            msg += "NLOSST: %f\n" % s.NlossesTotal
            raise exc.NutrientBalanceError(msg)