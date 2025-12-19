# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究院，瓦赫宁根大学与研究中心
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
from collections import namedtuple

from ...base import StatesTemplate, ParamTemplate, SimulationObject, RatesTemplate
from ...decorators import prepare_rates, prepare_states
from ...traitlets import HasTraits, Float, Int, Instance
from ...util import AfgenTrait

MaxNutrientConcentrations = namedtuple("MaxNutrientConcentrations",
                                       ["NMAXLV", "PMAXLV", "KMAXLV",
                                        "NMAXST", "PMAXST", "KMAXST",
                                        "NMAXRT", "PMAXRT", "KMAXRT",
                                        "NMAXSO", "PMAXSO", "KMAXSO"])

class NPK_Demand_Uptake(SimulationObject):
    """计算作物N/P/K的需量及其从土壤中的吸收。

    作物的N/P/K需求量通过营养器官（叶片、茎和根）中的实际N/P/K浓度（kg N/P/K 每 kg 生物量）
    与每个器官的最大N/P/K浓度之差得到。N/P/K的吸收量则为作物需求与土壤供给的最小值。

    固氮作物（豆科植物）假定每日N需求的固定比例由生物固氮提供。
    剩余部分则由土壤供应。

    储藏器官的N/P/K需求量计算与前述略有不同，假定储藏器官的需求由叶片、茎和根进行
    N/P/K再分配（转运）满足。因此，储藏器官的N/P/K吸收量为可转运N/P/K（供给）
    与储藏器官需求的最小值。此外，转运过程考虑了时间系数，表示转运N/P/K的可用性存在延迟。

    **模拟参数**

    ============  =============================================  ======================
     名称          描述                                           单位
    ============  =============================================  ======================
    NMAXLV_TB      叶片最大N浓度, 随发育阶段DVS变化               kg N kg-1 干物质
    PMAXLV_TB      类似于N, 作用于P                              kg P kg-1 干物质
    KMAXLV_TB      类似于N, 作用于K                              kg K kg-1 干物质

    NMAXRT_FR      根最大N浓度, 以叶片最大N浓度的比例表示         -
    PMAXRT_FR      类似于N, 作用于P                              -
    KMAXRT_FR      类似于N, 作用于K                              -

    NMAXST_FR      茎最大N浓度, 以叶片最大N浓度的比例表示         -
    PMAXST_FR      类似于N, 作用于P                              -
    KMAXST_FR      类似于N, 作用于K                              -

    NMAXSO         储藏器官的最大N浓度                            kg N kg-1 干物质
    PMAXSO         类似于N, 作用于P                              kg P kg-1 干物质
    KMAXSO         类似于N, 作用于K                              kg K kg-1 干物质

    NCRIT_FR       临界N浓度,                                    -
                   为营养器官最大N浓度的比例（叶+茎）
    PCRIT_FR       类似于N, 作用于P                              -
    KCRIT_FR       类似于N, 作用于K                              -

    TCNT           向储藏器官进行N转运的时间系数                   天
    TCPT           类似于N, 作用于P                              天
    TCKT           类似于N, 作用于K                              天

    NFIX_FR        生物固氮提供的作物N吸收比例                     kg N kg-1 干物质
    RNUPTAKEMAX    N吸收速率最大值                               |kg N ha-1 d-1|
    RPUPTAKEMAX    P吸收速率最大值                               |kg N ha-1 d-1|
    RKUPTAKEMAX    K吸收速率最大值                               |kg N ha-1 d-1|
    ============  =============================================  ======================

    **状态变量**

    =============  ================================================= ==== ============
     名称           描述                                             Pbl      单位
    =============  ================================================= ==== ============
    NuptakeTotal     作物总N吸收量                                    N   |kg N ha-1|
    PuptakeTotal     作物总P吸收量                                    N   |kg N ha-1|
    KuptakeTotal     作物总K吸收量                                    N   |kg N ha-1|
    NfixTotal        作物固氮总量                                     N   |kg N ha-1|

    NdemandST        活茎N需求                                        N   |kg N ha-1|
    NdemandRT        活根N需求                                        N   |kg N ha-1|
    NdemandSO        储藏器官N需求                                    N   |kg N ha-1|

    PdemandLV        活叶P需求                                        N   |kg P ha-1|
    PdemandST        活茎P需求                                        N   |kg P ha-1|
    PdemandRT        活根P需求                                        N   |kg P ha-1|
    PdemandSO        储藏器官P需求                                    N   |kg P ha-1|

    KdemandLV        活叶K需求                                        N   |kg K ha-1|
    KdemandST        活茎K需求                                        N   |kg K ha-1|
    KdemandRT        活根K需求                                        N   |kg K ha-1|
    KdemandSO        储藏器官K需求                                    N   |kg K ha-1|
    =============  ================================================= ==== ============


    **速率变量**

    ===========  ================================================= ==== ================
     名称         描述                                             Pbl      单位
    ===========  ================================================= ==== ================
    RNuptakeLV     叶片N吸收速率                                    Y   |kg N ha-1 d-1|
    RNuptakeST     茎N吸收速率                                      Y   |kg N ha-1 d-1|
    RNuptakeRT     根N吸收速率                                      Y   |kg N ha-1 d-1|
    RNuptakeSO     储藏器官N吸收速率                                Y   |kg N ha-1 d-1|

    RPuptakeLV     叶片P吸收速率                                    Y   |kg P ha-1 d-1|
    RPuptakeST     茎P吸收速率                                      Y   |kg P ha-1 d-1|
    RPuptakeRT     根P吸收速率                                      Y   |kg P ha-1 d-1|
    RPuptakeSO     储藏器官P吸收速率                                Y   |kg P ha-1 d-1|

    RKuptakeLV     叶片K吸收速率                                    Y   |kg K ha-1 d-1|
    RKuptakeST     茎K吸收速率                                      Y   |kg K ha-1 d-1|
    RKuptakeRT     根K吸收速率                                      Y   |kg K ha-1 d-1|
    RKuptakeSO     储藏器官K吸收速率                                Y   |kg K ha-1 d-1|

    RNuptake       总N吸收速率                                      Y   |kg N ha-1 d-1|
    RPuptake       总P吸收速率                                      Y   |kg P ha-1 d-1|
    RKuptake       总K吸收速率                                      Y   |kg K ha-1 d-1|
    RNfixation     N固氮速率                                        Y   |kg N ha-1 d-1|

    NdemandLV      活叶N需求                                        N   |kg N ha-1|
    NdemandST      活茎N需求                                        N   |kg N ha-1|
    NdemandRT      活根N需求                                        N   |kg N ha-1|
    NdemandSO      储藏器官N需求                                    N   |kg N ha-1|

    PdemandLV      活叶P需求                                        N   |kg P ha-1|
    PdemandST      活茎P需求                                        N   |kg P ha-1|
    PdemandRT      活根P需求                                        N   |kg P ha-1|
    PdemandSO      储藏器官P需求                                    N   |kg P ha-1|

    KdemandLV      活叶K需求                                        N   |kg K ha-1|
    KdemandST      活茎K需求                                        N   |kg K ha-1|
    KdemandRT      活根K需求                                        N   |kg K ha-1|
    KdemandSO      储藏器官K需求                                    N   |kg K ha-1|

    Ndemand        作物N总需求                                      N   |kg N ha-1 d-1|
    Pdemand        作物P总需求                                      N   |kg P ha-1 d-1|
    Kdemand        作物K总需求                                      N   |kg K ha-1 d-1|
    ===========  ================================================= ==== ================

    **信号的发送或处理**

    无

    **外部依赖**

    ================  =================================== ====================  ===========
     名称              描述                                    提供方               单位
    ================  =================================== ====================  ===========
    DVS               作物发育阶段                          DVS_Phenology               -
    TRA               作物蒸腾                              Evapotranspiration     |cm d-1|
    TRAMX             作物潜在蒸腾量                        Evapotranspiration     |cm d-1|
    NAVAIL            土壤中可供应N总量                     NPK_Soil_Dynamics      |kg ha-1|
    PAVAIL            土壤中可供应P总量                     NPK_Soil_Dynamics      |kg ha-1|
    KAVAIL            土壤中可供应K总量                     NPK_Soil_Dynamics      |kg ha-1|
    Ntranslocatable   可从茎、叶、根再分配的N量             NPK_Translocation      |kg ha-1|
                      （转运的N）
    Ptranslocatable   类似于N, 作用于P                      NPK_Translocation      |kg ha-1|
    Ktranslocatable   类似于N, 作用于K                      NPK_Translocation      |kg ha-1|
    ================  =================================== ====================  ===========

    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()  # 叶片中最大氮浓度，随dvs变化
        PMAXLV_TB = AfgenTrait()  # 叶片中最大磷浓度，随dvs变化
        KMAXLV_TB = AfgenTrait()  # 叶片中最大钾浓度，随dvs变化
        
        NMAXRT_FR = Float(-99.)  # 根中最大氮浓度，占叶片最大氮浓度的比例
        PMAXRT_FR = Float(-99.)  # 根中最大磷浓度，占叶片最大磷浓度的比例
        KMAXRT_FR = Float(-99.)  # 根中最大钾浓度，占叶片最大钾浓度的比例

        NMAXST_FR = Float(-99.)  # 茎中最大氮浓度，占叶片最大氮浓度的比例
        PMAXST_FR = Float(-99.)  # 茎中最大磷浓度，占叶片最大磷浓度的比例
        KMAXST_FR = Float(-99.)  # 茎中最大钾浓度，占叶片最大钾浓度的比例
        
        NMAXSO = Float(-99.)  # 储藏器官中最大氮浓度 [kg N kg-1 干物质]
        PMAXSO = Float(-99.)  # 储藏器官中最大磷浓度 [kg P kg-1 干物质]
        KMAXSO = Float(-99.)  # 储藏器官中最大钾浓度 [kg K kg-1 干物质]
        
        TCNT = Float(-99.)  # 向储藏器官转运氮的时间系数 [天]
        TCPT = Float(-99.)  # 向储藏器官转运磷的时间系数 [天]
        TCKT = Float(-99.)  # 向储藏器官转运钾的时间系数 [天]

        NFIX_FR = Float(-99.)  # 作物氮素吸收中由生物固氮占的比例
        RNUPTAKEMAX = Float()  # 最大氮吸收速率
        RPUPTAKEMAX = Float()  # 最大磷吸收速率
        RKUPTAKEMAX = Float()  # 最大钾吸收速率

    class RateVariables(RatesTemplate):
        RNuptakeLV = Float(-99.)  # 各器官的氮吸收速率 [kg ha-1 d -1]
        RNuptakeST = Float(-99.)
        RNuptakeRT = Float(-99.)
        RNuptakeSO = Float(-99.)

        RPuptakeLV = Float(-99.)  # 各器官的磷吸收速率 [kg ha-1 d -1]
        RPuptakeST = Float(-99.)
        RPuptakeRT = Float(-99.)
        RPuptakeSO = Float(-99.)

        RKuptakeLV = Float(-99.)  # 各器官的钾吸收速率 [kg ha-1 d -1]
        RKuptakeST = Float(-99.)
        RKuptakeRT = Float(-99.)
        RKuptakeSO = Float(-99.)

        RNuptake = Float(-99.)  # 总氮吸收速率 [kg ha-1 d -1]
        RPuptake = Float(-99.)  # 总磷吸收速率
        RKuptake = Float(-99.)  # 总钾吸收速率
        RNfixation = Float(-99.)  # 总氮固定量

        NdemandLV = Float(-99.)  # 各器官的氮需求量 [kg ha-1]
        NdemandST = Float(-99.)
        NdemandRT = Float(-99.)
        NdemandSO = Float(-99.)

        PdemandLV = Float(-99.)  # 各器官的磷需求量 [kg ha-1]
        PdemandST = Float(-99.)
        PdemandRT = Float(-99.)
        PdemandSO = Float(-99.)

        KdemandLV = Float(-99.)  # 各器官的钾需求量 [kg ha-1]
        KdemandST = Float(-99.)
        KdemandRT = Float(-99.)
        KdemandSO = Float(-99.)

        Ndemand = Float()  # 作物N/P/K总需求
        Pdemand = Float()
        Kdemand = Float()

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: 一个包含参数键/值对的ParameterProvider
        """

        self.params = self.Parameters(parvalues)
        self.kiosk = kiosk

        self.rates = self.RateVariables(kiosk,
            publish=["RNuptakeLV", "RNuptakeST", "RNuptakeRT", "RNuptakeSO",
                     "RPuptakeLV", "RPuptakeST", "RPuptakeRT", "RPuptakeSO",
                     "RKuptakeLV", "RKuptakeST", "RKuptakeRT", "RKuptakeSO",
                     "RNuptake", "RPuptake", "RKuptake", "RNfixation"])

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        p = self.params
        k = self.kiosk

        delt = 1.0
        mc = self._compute_NPK_max_concentrations()

        # 叶片、茎秆、根和储藏器官的NPK总需求
        # 需求量包括从前一时间步带过来的需求量以及由新生长产生的需求量
        # 注意，这里为预积分阶段，因此需要乘以时间步长delt

        # 氮需求量 [kg ha-1]
        r.NdemandLV = max(mc.NMAXLV * k.WLV - k.NamountLV, 0.) + max(k.GRLV * mc.NMAXLV, 0) * delt
        r.NdemandST = max(mc.NMAXST * k.WST - k.NamountST, 0.) + max(k.GRST * mc.NMAXST, 0) * delt
        r.NdemandRT = max(mc.NMAXRT * k.WRT - k.NamountRT, 0.) + max(k.GRRT * mc.NMAXRT, 0) * delt
        r.NdemandSO = max(mc.NMAXSO * k.WSO - k.NamountSO, 0.)

        # 磷需求量 [kg ha-1]
        r.PdemandLV = max(mc.PMAXLV * k.WLV - k.PamountLV, 0.) + max(k.GRLV * mc.PMAXLV, 0) * delt
        r.PdemandST = max(mc.PMAXST * k.WST - k.PamountST, 0.) + max(k.GRST * mc.PMAXST, 0) * delt
        r.PdemandRT = max(mc.PMAXRT * k.WRT - k.PamountRT, 0.) + max(k.GRRT * mc.PMAXRT, 0) * delt
        r.PdemandSO = max(mc.PMAXSO * k.WSO - k.PamountSO, 0.)

        # 钾需求量 [kg ha-1]
        r.KdemandLV = max(mc.KMAXLV * k.WLV - k.KamountLV, 0.) + max(k.GRLV * mc.KMAXLV, 0) * delt
        r.KdemandST = max(mc.KMAXST * k.WST - k.KamountST, 0.) + max(k.GRST * mc.KMAXST, 0) * delt
        r.KdemandRT = max(mc.KMAXRT * k.WRT - k.KamountRT, 0.) + max(k.GRRT * mc.KMAXRT, 0) * delt
        r.KdemandSO = max(mc.KMAXSO * k.WSO - k.KamountSO, 0.)

        r.Ndemand = r.NdemandLV + r.NdemandST + r.NdemandRT
        r.Pdemand = r.PdemandLV + r.PdemandST + r.PdemandRT
        r.Kdemand = r.KdemandLV + r.KdemandST + r.KdemandRT

        # 储藏器官的NPK吸收速率（kg N ha-1 d-1），等于供给量和需求量的较小值，再除以N/P/K转移的时间系数
        r.RNuptakeSO = min(r.NdemandSO, k.Ntranslocatable)/p.TCNT
        r.RPuptakeSO = min(r.PdemandSO, k.Ptranslocatable)/p.TCPT
        r.RKuptakeSO = min(r.KdemandSO, k.Ktranslocatable)/p.TCKT

        # 当发生严重干旱（即RFTRA<=0.01）时，养分不吸收
        if k.RFTRA > 0.01:
            NutrientLIMIT = 1.0
        else:
            NutrientLIMIT = 0.

        # 生物固氮
        r.RNfixation = (max(0., p.NFIX_FR * r.Ndemand) * NutrientLIMIT)

        # 从土壤吸收NPK速率
        r.RNuptake = (max(0., min(r.Ndemand - r.RNfixation, k.NAVAIL, p.RNUPTAKEMAX)) * NutrientLIMIT)
        r.RPuptake = (max(0., min(r.Pdemand, k.PAVAIL, p.RPUPTAKEMAX)) * NutrientLIMIT)
        r.RKuptake = (max(0., min(r.Kdemand, k.KAVAIL, p.RKUPTAKEMAX)) * NutrientLIMIT)

        # 各器官NPK吸收速率，通过各自需求量在总需求量中的比例加权
        # 如果没有需求，则吸收速率=0
        if r.Ndemand == 0.:
            r.RNuptakeLV = r.RNuptakeST = r.RNuptakeRT = 0.
        else:
            r.RNuptakeLV = (r.NdemandLV / r.Ndemand) * (r.RNuptake + r.RNfixation)
            r.RNuptakeST = (r.NdemandST / r.Ndemand) * (r.RNuptake + r.RNfixation)
            r.RNuptakeRT = (r.NdemandRT / r.Ndemand) * (r.RNuptake + r.RNfixation)

        if r.Pdemand == 0.:
            r.RPuptakeLV = r.RPuptakeST = r.RPuptakeRT = 0.
        else:
            r.RPuptakeLV = (r.PdemandLV / r.Pdemand) * r.RPuptake
            r.RPuptakeST = (r.PdemandST / r.Pdemand) * r.RPuptake
            r.RPuptakeRT = (r.PdemandRT / r.Pdemand) * r.RPuptake

        if r.Kdemand == 0.:
            r.RKuptakeLV = r.RKuptakeST = r.RKuptakeRT = 0.
        else:
            r.RKuptakeLV = (r.KdemandLV / r.Kdemand) * r.RKuptake
            r.RKuptakeST = (r.KdemandST / r.Kdemand) * r.RKuptake
            r.RKuptakeRT = (r.KdemandRT / r.Kdemand) * r.RKuptake

    @prepare_states
    def integrate(self, day, delt=1.0):
        pass

    def _compute_NPK_max_concentrations(self):
        """计算叶、茎、根和储藏器官中N/P/K的最大浓度。

        注意最大浓度首先根据叶的稀释曲线得出。茎和根的最大浓度按叶子的最大浓度乘以系数得到。
        储藏器官的最大N/P/K浓度直接来自参数N/P/KMAXSO。
        """

        p = self.params
        k = self.kiosk
        NMAXLV = p.NMAXLV_TB(k.DVS)
        PMAXLV = p.PMAXLV_TB(k.DVS)
        KMAXLV = p.KMAXLV_TB(k.DVS)
        max_NPK_conc = MaxNutrientConcentrations(
            # 叶中NPK最大浓度 [kg N kg-1 DM]
            NMAXLV=NMAXLV,
            PMAXLV=PMAXLV,
            KMAXLV=KMAXLV,
            # 茎和根中NPK最大浓度 [kg N kg-1 DM]
            NMAXST=(p.NMAXST_FR * NMAXLV),
            NMAXRT=p.NMAXRT_FR * NMAXLV,
            NMAXSO=p.NMAXSO,

            PMAXST=p.PMAXST_FR * PMAXLV,
            PMAXRT=p.PMAXRT_FR * PMAXLV,
            PMAXSO=p.PMAXSO,

            KMAXST=p.KMAXST_FR * KMAXLV,
            KMAXRT=p.KMAXRT_FR * KMAXLV,
            KMAXSO=p.KMAXSO
        )

        return max_NPK_conc
