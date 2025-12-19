#!/usr/bin/env python

from .. import exceptions as exc
from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject
from ..util import AfgenTrait
from .nutrients import NPK_Translocation
from .nutrients import NPK_Demand_Uptake


class NPK_Crop_Dynamics(SimulationObject):
    """实现整体NPK作物动态。

    NPK_Crop_Dynamics 实现在作物体内N/P/K簿记的整体逻辑。

    **模拟参数**
    
    =============  ================================================= =======================
     名称           描述                                              单位
    =============  ================================================= =======================
    NMAXLV_TB      叶片最大氮浓度，作为发育阶段函数                  kg N kg-1 干生物量
                   (dvs的函数)
    PMAXLV_TB      叶片最大磷浓度                                    kg P kg-1 干生物量
    KMAXLV_TB      叶片最大钾浓度                                    kg K kg-1 干生物量

    NMAXRT_FR      根系最大氮浓度为叶片最大氮浓度的比例               -
    PMAXRT_FR      根系最大磷浓度为叶片最大磷浓度的比例               -
    KMAXRT_FR      根系最大钾浓度为叶片最大钾浓度的比例               -

    NMAXST_FR      茎最大氮浓度为叶片最大氮浓度的比例                 -
    KMAXST_FR      茎最大钾浓度为叶片最大钾浓度的比例                 -
    PMAXST_FR      茎最大磷浓度为叶片最大磷浓度的比例                 -

    NRESIDLV       叶片残留氮分数                                     kg N kg-1 干生物量
    PRESIDLV       叶片残留磷分数                                     kg P kg-1 干生物量
    KRESIDLV       叶片残留钾分数                                     kg K kg-1 干生物量

    NRESIDRT       根系残留氮分数                                     kg N kg-1 干生物量
    PRESIDRT       根系残留磷分数                                     kg P kg-1 干生物量
    KRESIDRT       根系残留钾分数                                     kg K kg-1 干生物量

    NRESIDST       茎残留氮分数                                       kg N kg-1 干生物量
    PRESIDST       茎残留磷分数                                       kg P kg-1 干生物量
    KRESIDST       茎残留钾分数                                       kg K kg-1 干生物量
    =============  ================================================= =======================

    **状态变量**

    ==========  ================================================== ============
     名称        描述                                              单位
    ==========  ================================================== ============
    NamountLV     活叶中的实际氮含量                                 |kg N ha-1|
    PamountLV     活叶中的实际磷含量                                 |kg P ha-1|
    KamountLV     活叶中的实际钾含量                                 |kg K ha-1|
        
    NamountST     活茎中的实际氮含量                                 |kg N ha-1|
    PamountST     活茎中的实际磷含量                                 |kg P ha-1|
    KamountST     活茎中的实际钾含量                                 |kg K ha-1|

    NamountSO     活储藏器官中的实际氮含量                            |kg N ha-1|
    PamountSO     活储藏器官中的实际磷含量                            |kg P ha-1|
    KamountSO     活储藏器官中的实际钾含量                            |kg K ha-1|
    
    NamountRT     活根中的实际氮含量                                 |kg N ha-1|
    PamountRT     活根中的实际磷含量                                 |kg P ha-1|
    KamountRT     活根中的实际钾含量                                 |kg K ha-1|
    
    Nuptake_T     总吸收氮量                                         |kg N ha-1|
    Puptake_T     总吸收磷量                                         |kg P ha-1|
    Kuptake_T     总吸收钾量                                         |kg K ha-1|
    Nfix_T        总生物固氮量                                       |kg N ha-1|
    ==========  ================================================== ============

    **速率变量**

    ===========  =================================================  ================
     名称         描述                                               单位
    ===========  =================================================  ================
    RNamountLV     叶片氮含量日增量                                  |kg N ha-1 d-1|
    RPamountLV     叶片磷含量日增量                                  |kg P ha-1 d-1|
    RKamountLV     叶片钾含量日增量                                  |kg K ha-1 d-1|
    
    RNamountST     茎氮含量日增量                                    |kg N ha-1 d-1|
    RPamountST     茎磷含量日增量                                    |kg P ha-1 d-1|
    RKamountST     茎钾含量日增量                                    |kg K ha-1 d-1|
        
    RNamountRT     根氮含量日增量                                    |kg N ha-1 d-1|
    RPamountRT     根磷含量日增量                                    |kg P ha-1 d-1|
    RKamountRT     根钾含量日增量                                    |kg K ha-1 d-1|
    
    RNamountSO     储藏器官氮含量日增量                              |kg N ha-1 d-1|
    RPamountSO     储藏器官磷含量日增量                              |kg P ha-1 d-1|
    RKamountSO     储藏器官钾含量日增量                              |kg K ha-1 d-1|

    RNdeathLV      叶片氮损失速率                                    |kg N ha-1 d-1|
    RPdeathLV      叶片磷损失速率                                    |kg P ha-1 d-1|
    RKdeathLV      叶片钾损失速率                                    |kg K ha-1 d-1|

    RNdeathST      茎氮损失速率                                      |kg N ha-1 d-1|
    RPdeathST      茎磷损失速率                                      |kg P ha-1 d-1|
    RKdeathST      茎钾损失速率                                      |kg K ha-1 d-1|

    RNdeathRT      根氮损失速率                                      |kg N ha-1 d-1|
    RPdeathRT      根磷损失速率                                      |kg P ha-1 d-1|
    RKdeathRT      根钾损失速率                                      |kg K ha-1 d-1|

    RNloss         衰老导致的氮损失                                  |kg N ha-1 d-1|
    RPloss         衰老导致的磷损失                                  |kg P ha-1 d-1|
    RKloss         衰老导致的钾损失                                  |kg K ha-1 d-1|
    ===========  =================================================  ================
    
    **发送或处理的信号**
    
    无
    
    **外部依赖**

    =======  =================================== ====================  ==============
     名称      描述                                   提供者                    单位
    =======  =================================== ====================  ==============
    DVS      作物发育阶段                        DVS_Phenology           -
    WLV      活叶干重                            WOFOST_Leaf_Dynamics  |kg ha-1|
    WRT      活根干重                            WOFOST_Root_Dynamics  |kg ha-1|
    WST      活茎干重                            WOFOST_Stem_Dynamics  |kg ha-1|
    DRLV     叶片死亡速率                        WOFOST_Leaf_Dynamics  |kg ha-1 d-1|
    DRRT     根死亡速率                          WOFOST_Root_Dynamics  |kg ha-1 d-1|
    DRST     茎死亡速率                          WOFOST_Stem_Dynamics  |kg ha-1 d-1|
    =======  =================================== ====================  ==============
    """

    translocation = Instance(SimulationObject)
    demand_uptake = Instance(SimulationObject)

    NamountLVI = Float(-99.)  # 初始叶片中土壤氮含量
    NamountSTI = Float(-99.)  # 初始茎中土壤氮含量
    NamountRTI = Float(-99.)  # 初始根系中土壤氮含量
    NamountSOI = Float(-99.)  # 初始储藏器官中土壤氮含量
    
    PamountLVI = Float(-99.)  # 初始叶片中土壤磷含量
    PamountSTI = Float(-99.)  # 初始茎中土壤磷含量
    PamountRTI = Float(-99.)  # 初始根系中土壤磷含量
    PamountSOI = Float(-99.)  # 初始储藏器官中土壤磷含量

    KamountLVI = Float(-99.)  # 初始叶片中土壤钾含量
    KamountSTI = Float(-99.)  # 初始茎中土壤钾含量
    KamountRTI = Float(-99.)  # 初始根系中土壤钾含量
    KamountSOI = Float(-99.)  # 初始储藏器官中土壤钾含量

    class Parameters(ParamTemplate):
        DVS_NPK_STOP = Float(-99.)
        NMAXLV_TB = AfgenTrait()
        PMAXLV_TB = AfgenTrait()
        KMAXLV_TB = AfgenTrait()
        NMAXST_FR = Float(-99.)
        NMAXRT_FR = Float(-99.)
        PMAXST_FR = Float(-99.)
        PMAXRT_FR = Float(-99.)
        KMAXST_FR = Float(-99.)
        KMAXRT_FR = Float(-99.)
        NRESIDLV = Float(-99.)  # 叶片残留氮分数 [kg N kg-1 干物质]
        NRESIDST = Float(-99.)  # 茎残留氮分数 [kg N kg-1 干物质]
        NRESIDRT = Float(-99.)  # 根系残留氮分数 [kg N kg-1 干物质]
        PRESIDLV = Float(-99.)  # 叶片残留磷分数 [kg P kg-1 干物质]
        PRESIDST = Float(-99.)  # 茎残留磷分数 [kg P kg-1 干物质]
        PRESIDRT = Float(-99.)  # 根系残留磷分数 [kg P kg-1 干物质]
        KRESIDLV = Float(-99.)  # 叶片残留钾分数 [kg K kg-1 干物质]
        KRESIDST = Float(-99.)  # 茎残留钾分数 [kg K kg-1 干物质]
        KRESIDRT = Float(-99.)  # 根系残留钾分数 [kg K kg-1 干物质]

    class StateVariables(StatesTemplate):
        NamountLV = Float(-99.) # 叶片中的氮含量 [kg N ha-1]
        PamountLV = Float(-99.) # 叶片中的磷含量 [kg P]
        KamountLV = Float(-99.) # 叶片中的钾含量 [kg K]
        
        NamountST = Float(-99.) # 茎中的氮含量 [kg N]
        PamountST = Float(-99.) # 茎中的磷含量 [kg P]
        KamountST = Float(-99.) # 茎中的钾含量 [kg K]
      
        NamountSO = Float(-99.) # 储藏器官中的氮含量 [kg N]
        PamountSO = Float(-99.) # 储藏器官中的磷含量 [kg P]
        KamountSO = Float(-99.) # 储藏器官中的钾含量 [kg K]
        
        NamountRT = Float(-99.) # 根系中的氮含量 [kg N]
        PamountRT = Float(-99.) # 根系中的磷含量 [kg P]
        KamountRT = Float(-99.) # 根系中的钾含量 [kg K]
        
        NuptakeTotal = Float(-99.) # 累计吸收的氮含量 [kg N]
        PuptakeTotal = Float(-99.) # 累计吸收的磷含量 [kg P]
        KuptakeTotal = Float(-99.) # 累计吸收的钾含量 [kg K]
        NfixTotal = Float(-99.) # 累计生物固氮量 [kg N]
        
        NlossesTotal = Float(-99.) # 总氮损失
        PlossesTotal = Float(-99.) # 总磷损失
        KlossesTotal = Float(-99.) # 总钾损失

    class RateVariables(RatesTemplate):
        RNamountLV = Float(-99.)  # 各植株器官NPK净增长速率
        RPamountLV = Float(-99.)
        RKamountLV = Float(-99.)
        
        RNamountST = Float(-99.)
        RPamountST = Float(-99.)
        RKamountST = Float(-99.)
               
        RNamountRT = Float(-99.)
        RPamountRT = Float(-99.)
        RKamountRT = Float(-99.)
        
        RNamountSO = Float(-99.)
        RPamountSO = Float(-99.)
        RKamountSO = Float(-99.)
               
        RNdeathLV = Float(-99.)  # 叶片氮损失速率 [kg ha-1 d-1]
        RNdeathST = Float(-99.)  # 茎氮损失速率 [kg ha-1 d-1]
        RNdeathRT = Float(-99.)  # 根系氮损失速率 [kg ha-1 d-1]
        
        RPdeathLV = Float(-99.)  # 叶片磷损失速率 [kg ha-1 d-1]
        RPdeathST = Float(-99.)  # 茎磷损失速率 [kg ha-1 d-1]
        RPdeathRT = Float(-99.)  # 根系磷损失速率 [kg ha-1 d-1]
        
        RKdeathLV = Float(-99.)  # 叶片钾损失速率 [kg ha-1 d-1]
        RKdeathST = Float(-99.)  # 茎钾损失速率 [kg ha-1 d-1]
        RKdeathRT = Float(-99.)  # 根系钾损失速率 [kg ha-1 d-1]

        RNloss = Float(-99.)    # 氮损失速率
        RPloss = Float(-99.)    # 磷损失速率
        RKloss = Float(-99.)    # 钾损失速率
        
    def initialize(self, day, kiosk, parvalues):
        """
        :param kiosk: 此 PCSE 实例的变量 kiosk
        :param parvalues: 以参数为键/值对的字典
        """  
        
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
        
        # 初始化 npk_crop_dynamics 组件
        self.translocation = NPK_Translocation(day, kiosk, parvalues)
        self.demand_uptake = NPK_Demand_Uptake(day, kiosk, parvalues)

        # 初始状态
        params = self.params
        k = kiosk

        # 初始含量
        self.NamountLVI = NamountLV = k.WLV * params.NMAXLV_TB(k.DVS)
        self.NamountSTI = NamountST = k.WST * params.NMAXLV_TB(k.DVS) * params.NMAXST_FR
        self.NamountRTI = NamountRT = k.WRT * params.NMAXLV_TB(k.DVS) * params.NMAXRT_FR
        self.NamountSOI = NamountSO = 0.
        
        self.PamountLVI = PamountLV = k.WLV * params.PMAXLV_TB(k.DVS)
        self.PamountSTI = PamountST = k.WST * params.PMAXLV_TB(k.DVS) * params.PMAXST_FR
        self.PamountRTI = PamountRT = k.WRT * params.PMAXLV_TB(k.DVS) * params.PMAXRT_FR
        self.PamountSOI = PamountSO = 0.

        self.KamountLVI = KamountLV = k.WLV * params.KMAXLV_TB(k.DVS)
        self.KamountSTI = KamountST = k.WST * params.KMAXLV_TB(k.DVS) * params.KMAXST_FR
        self.KamountRTI = KamountRT = k.WRT * params.KMAXLV_TB(k.DVS) * params.KMAXRT_FR
        self.KamountSOI = KamountSO = 0.

        self.states = self.StateVariables(kiosk,
                        publish=["NamountLV", "NamountST", "NamountRT", "NamountSO", "PamountLV", "PamountST",
                                 "PamountRT", "PamountSO", "KamountLV", "KamountST", "KamountRT", "KamountSO"],
                        NamountLV=NamountLV, NamountST=NamountST, NamountRT=NamountRT, NamountSO=NamountSO,
                        PamountLV=PamountLV, PamountST=PamountST, PamountRT=PamountRT, PamountSO=PamountSO,
                        KamountLV=KamountLV, KamountST=KamountST, KamountRT=KamountRT, KamountSO=KamountSO,
                        NuptakeTotal=0, PuptakeTotal=0., KuptakeTotal=0., NfixTotal=0.,
                        NlossesTotal=0, PlossesTotal=0., KlossesTotal=0.)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates = self.rates
        params = self.params
        k = self.kiosk
        
        self.demand_uptake.calc_rates(day, drv)
        self.translocation.calc_rates(day, drv)

        # 由于植株器官死亡导致的 NPK 损失计算
        rates.RNdeathLV = params.NRESIDLV * k.DRLV
        rates.RNdeathST = params.NRESIDST * k.DRST
        rates.RNdeathRT = params.NRESIDRT * k.DRRT

        rates.RPdeathLV = params.PRESIDLV * k.DRLV
        rates.RPdeathST = params.PRESIDST * k.DRST
        rates.RPdeathRT = params.PRESIDRT * k.DRRT

        rates.RKdeathLV = params.KRESIDLV * k.DRLV
        rates.RKdeathST = params.KRESIDST * k.DRST
        rates.RKdeathRT = params.KRESIDRT * k.DRRT

        # 叶片、茎秆、根和储藏器官的氮素速率均按 吸收量-转流量-死亡量 计算。
        # 储藏器官除外，其仅因转流而获得 N。
        rates.RNamountLV = k.RNuptakeLV - k.RNtranslocationLV - rates.RNdeathLV
        rates.RNamountST = k.RNuptakeST - k.RNtranslocationST - rates.RNdeathST
        rates.RNamountRT = k.RNuptakeRT - k.RNtranslocationRT - rates.RNdeathRT
        rates.RNamountSO = k.RNuptakeSO
        
        # 叶片、茎秆、根和储藏器官的磷素速率
        rates.RPamountLV = k.RPuptakeLV - k.RPtranslocationLV - rates.RPdeathLV
        rates.RPamountST = k.RPuptakeST - k.RPtranslocationST - rates.RPdeathST
        rates.RPamountRT = k.RPuptakeRT - k.RPtranslocationRT - rates.RPdeathRT
        rates.RPamountSO = k.RPuptakeSO

        # 叶片、茎秆、根和储藏器官的钾素速率
        rates.RKamountLV = k.RKuptakeLV - k.RKtranslocationLV - rates.RKdeathLV
        rates.RKamountST = k.RKuptakeST - k.RKtranslocationST - rates.RKdeathST
        rates.RKamountRT = k.RKuptakeRT - k.RKtranslocationRT - rates.RKdeathRT
        rates.RKamountSO = k.RKuptakeSO
        
        rates.RNloss = rates.RNdeathLV + rates.RNdeathST + rates.RNdeathRT
        rates.RPloss = rates.RPdeathLV + rates.RPdeathST + rates.RPdeathRT
        rates.RKloss = rates.RKdeathLV + rates.RKdeathST + rates.RKdeathRT

        self._check_N_balance(day)
        self._check_P_balance(day)
        self._check_K_balance(day)
        
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states
        k = self.kiosk

        # 叶片、茎秆、根和储藏器官的氮素量
        states.NamountLV += rates.RNamountLV
        states.NamountST += rates.RNamountST
        states.NamountRT += rates.RNamountRT
        states.NamountSO += rates.RNamountSO
        
        # 叶片、茎秆、根和储藏器官的磷素量
        states.PamountLV += rates.RPamountLV
        states.PamountST += rates.RPamountST
        states.PamountRT += rates.RPamountRT
        states.PamountSO += rates.RPamountSO

        # 叶片、茎秆、根和储藏器官的钾素量
        states.KamountLV += rates.RKamountLV
        states.KamountST += rates.RKamountST
        states.KamountRT += rates.RKamountRT
        states.KamountSO += rates.RKamountSO
        
        self.translocation.integrate(day, delt)
        self.demand_uptake.integrate(day, delt)

        # 土壤中NPK吸收总量
        states.NuptakeTotal += k.RNuptake
        states.PuptakeTotal += k.RPuptake
        states.KuptakeTotal += k.RKuptake
        states.NfixTotal += k.RNfixation
        
        # NPK损失总量
        states.NlossesTotal += rates.RNloss
        states.PlossesTotal += rates.RPloss
        states.KlossesTotal += rates.RKloss

    def _check_N_balance(self, day):
        s = self.states
        # 检查氮素平衡
        checksum = abs(s.NuptakeTotal + s.NfixTotal +
                       (self.NamountLVI + self.NamountSTI + self.NamountRTI + self.NamountSOI) -
                       (s.NamountLV + s.NamountST + s.NamountRT + s.NamountSO + s.NlossesTotal))

        if abs(checksum) >= 1.0:
            msg = "N flows not balanced on day %s\n" % day
            msg += "Checksum: %f, Nuptake_T: %f, Nfix_T: %f\n" % (checksum, s.NuptakeTotal, s.NfixTotal)
            msg += "NamountLVI: %f, NamountSTI: %f, NamountRTI: %f, NamountSOI: %f\n"  % \
                   (self.NamountLVI, self.NamountSTI, self.NamountRTI, self.NamountSOI)
            msg += "NamountLV: %f, NamountST: %f, NamountRT: %f, NamountSO: %f\n" % \
                   (s.NamountLV, s.NamountST, s.NamountRT, s.NamountSO)
            msg += "NLOSST: %f\n" % (s.NlossesTotal)
            raise exc.NutrientBalanceError(msg)

    def _check_P_balance(self, day):
        s = self.states
        # 检查磷素平衡
        checksum = abs(s.PuptakeTotal +
                       (self.PamountLVI + self.PamountSTI + self.PamountRTI + self.PamountSOI) -
                       (s.PamountLV + s.PamountST + s.PamountRT + s.PamountSO + s.PlossesTotal))

        if abs(checksum) >= 1.:
            msg = "P flows not balanced on day %s\n" % day
            msg += "Checksum: %f, Puptake_T: %f\n" % (checksum, s.PuptakeTotal)
            msg += "PamountLVI: %f, PamountSTI: %f, PamountRTI: %f, PamountSOI: %f\n" % \
                   (self.PamountLVI, self.PamountSTI, self.PamountRTI, self.PamountSOI)
            msg += "PamountLV: %f, PamountST: %f, PamountRT: %f, PamountSO: %f\n" % \
                   (s.PamountLV, s.PamountST, s.PamountRT, s.PamountSO)
            msg += "PLOSST: %f\n" % (s.PlossesTotal)
            raise exc.NutrientBalanceError(msg)

    def _check_K_balance(self, day):
        s = self.states
        # 检查钾素平衡
        checksum = abs(s.KuptakeTotal +
                       (self.KamountLVI + self.KamountSTI + self.KamountRTI + self.KamountSOI) -
                       (s.KamountLV + s.KamountST + s.KamountRT + s.KamountSO + s.KlossesTotal))

        if abs(checksum) >= 1.:
            msg = "K flows not balanced on day %s\n" % day
            msg += "Checksum: %f, Kuptake_T: %f\n"  % (checksum, s.KuptakeTotal)
            msg += "KamountLVI: %f, KamountSTI: %f, KamountRTI: %f, KamountSOI: %f\n" % \
                   (self.KamountLVI, self.KamountSTI, self.KamountRTI, self.KamountSOI)
            msg += "KamountLV: %f, KamountST: %f, KamountRT: %f, KamountSO: %f\n" % \
                   (s.KamountLV, s.KamountST, s.KamountRT, s.KamountSO)
            msg += "KLOSST: %f\n" % (s.KlossesTotal)
            raise exc.NutrientBalanceError(msg)
