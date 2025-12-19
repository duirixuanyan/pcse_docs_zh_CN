# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究院，瓦赫宁根-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from collections import namedtuple

from ...base import StatesTemplate, ParamTemplate, SimulationObject, RatesTemplate
from ...decorators import prepare_rates, prepare_states
from ...traitlets import HasTraits, Float, Int, Instance
from ...util import AfgenTrait

MaxNutrientConcentrations = namedtuple("MaxNutrientConcentrations",
                                       ["NMAXLV","NMAXST", "NMAXRT", "NMAXSO"])

class N_Demand_Uptake(SimulationObject):
    """计算作物氮素需求及其从土壤中的吸收。

    作物氮需求是通过植物营养器官（叶、茎、根）中实际氮含量（kg N 每 kg 干生物量）与每个器官最大氮浓度的差值计算得出。氮素吸收量则取土壤氮素供应和作物需求的最小值。

    对于豆科植物的固氮，是通过假设作物每天氮素需求的一定比例由固氮供给，其余部分需由土壤提供来计算。

    贮藏器官的氮素需求的计算方式略有不同，因为假设贮藏器官的需求是通过叶、茎、根的N/P/K搬运来满足。因此，贮藏器官的吸收量取每日可搬运氮供应和贮藏器官需求的最小值。

    **模拟参数**

    ============  =============================================  ======================
     名称           说明                                           单位
    ============  =============================================  ======================
    NMAXLV_TB      叶片最大氮浓度，DVS的函数                      kg N kg-1 干物质
    NMAXRT_FR      根最大氮浓度，为叶片最大氮浓度的分数           -
    NMAXST_FR      茎最大氮浓度，为叶片最大氮浓度的分数           -
    NMAXSO         贮藏器官最大氮浓度                             kg N kg-1 干物质
    NCRIT_FR       临界氮浓度，为营养器官（叶+茎）                -
                   最大氮浓度的分数
    TCNT           向贮藏器官氮转运的时间系数                      天
    NFIX_FR        作物氮素吸收中由生物固氮提供的比例            kg N kg-1 干物质
                                                                 生物固氮量
    RNUPTAKEMAX    最大氮素吸收速率                              |kg N ha-1 d-1|
    ============  =============================================  ======================

    **状态变量**

    ============= ================================================= ==== ============
     名称             说明                                           Pbl      单位
    ============= ================================================= ==== ============
    NuptakeTotal    作物总氮吸收                                      N   |kg N ha-1|
    NfixTotal       作物总氮固定量                                    N   |kg N ha-1|
    NdemandST       活茎的氮需求                                      N   |kg N ha-1|
    NdemandRT       活根的氮需求                                      N   |kg N ha-1|
    NdemandSO       贮藏器官的氮需求                                  N   |kg N ha-1|
    ============= ================================================= ==== ============


    **速率变量**

    ===========  ================================================= ==== ================
     名称            说明                                          Pbl      单位
    ===========  ================================================= ==== ================
    RNuptakeLV     叶片氮吸收速率                                   Y   |kg N ha-1 d-1|
    RNuptakeST     茎氮吸收速率                                     Y   |kg N ha-1 d-1|
    RNuptakeRT     根氮吸收速率                                     Y   |kg N ha-1 d-1|
    RNuptakeSO     贮藏器官氮吸收速率                               Y   |kg N ha-1 d-1|
    RNuptake       氮素总吸收速率                                   Y   |kg N ha-1 d-1|
    RNfixation     固氮速率                                         Y   |kg N ha-1 d-1|
    NdemandLV      活叶的氮需求                                     N   |kg N ha-1|
    NdemandST      活茎的氮需求                                     N   |kg N ha-1|
    NdemandRT      活根的氮需求                                     N   |kg N ha-1|
    NdemandSO      贮藏器官的氮需求                                 N   |kg N ha-1|
    Ndemand        作物氮素总需求                                   N   |kg N ha-1 d-1|
    ===========  ================================================= ==== ================

    **信号发送或处理**

    无

    **外部依赖变量**

    ================  =================================== ====================  ===========
     名称              说明                                 提供者                  单位
    ================  =================================== ====================  ===========
    DVS               作物发育进程                          DVS_Phenology              -
    TRA               作物蒸腾量                            Evapotranspiration     |cm d-1|
    TRAMX             潜在作物蒸腾量                        Evapotranspiration     |cm d-1|
    NAVAIL            土壤中可用总氮                        N_Soil_Dynamics      |kg ha-1|
    ================  =================================== ====================  ===========

    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()  # 叶片最大氮浓度，作为dvs（发育阶段）的函数
        DVS_N_TRANSL = Float(-99.)

        NMAXRT_FR = Float(-99.)  # 根中最大氮浓度（占叶片最大氮浓度的比例）
        NMAXST_FR = Float(-99.)  # 茎中最大氮浓度（占叶片最大氮浓度的比例）
        NMAXSO = Float(-99.)  # 贮藏器官中的最大P浓度 [kg N kg-1 干物质]
        TCNT = Float(-99.)  # 氮向贮藏器官转移的时间系数 [天]

        NFIX_FR = Float(-99.)  # 作物吸收氮的生物固氮比例
        RNUPTAKEMAX = Float()  # 最大氮吸收速率
        NRESIDLV = Float(-99.)  # 叶片中的残余氮比例 [kg N kg-1 干物质]
        NRESIDST = Float(-99.)  # 茎中的残余氮比例 [kg N kg-1 干物质]
        NRESIDRT = Float(-99.)  # 根中的残余氮比例 [kg N kg-1 干物质]

    class RateVariables(RatesTemplate):
        RNtranslocationLV = Float(-99.)  # 叶片向贮藏器官转移的氮速率 [kg ha-1 d-1]
        RNtranslocationST = Float(-99.)  # 茎向贮藏器官转移的氮速率 [kg ha-1 d-1]
        RNtranslocationRT = Float(-99.)  # 根向贮藏器官转移的氮速率 [kg ha-1 d-1]
        RNtranslocation = Float(-99.)    # 向贮藏器官总的氮转移速率 [kg ha-1 d-1]

        RNuptakeLV = Float(-99.)  # 各器官氮吸收速率 [kg ha-1 d-1]
        RNuptakeST = Float(-99.)
        RNuptakeRT = Float(-99.)
        RNuptakeSO = Float(-99.)

        RNuptake = Float(-99.)  # 氮总吸收速率 [kg ha-1 d-1]
        RNfixation = Float(-99.)  # 固氮总量

        NdemandLV = Float(-99.)  # 各器官氮需求量 [kg ha-1]
        NdemandST = Float(-99.)
        NdemandRT = Float(-99.)
        NdemandSO = Float(-99.)

        Ndemand = Float()  # 作物对N/P/K的总需求

    class StateVariables(StatesTemplate):
        NtranslocatableLV = Float(-99.)  # 叶片可转移的氮含量 [kg N ha-1]
        NtranslocatableST = Float(-99.)  # 茎可转移的氮含量 [kg N ha-1]
        NtranslocatableRT = Float(-99.)  # 根可转移的氮含量 [kg N ha-1]
        Ntranslocatable = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的启动日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: 参数提供器，包含参数键值对
        """

        self.params = self.Parameters(parvalues)
        self.kiosk = kiosk

        self.rates = self.RateVariables(kiosk,
            publish=["RNtranslocationLV", "RNtranslocationST", "RNtranslocationRT", "RNtranslocation", 
                     "RNuptakeLV", "RNuptakeST", "RNuptakeRT", "RNuptakeSO","RNuptake", "RNfixation"])

        self.states = self.StateVariables(kiosk, NtranslocatableLV=0., NtranslocatableST=0., NtranslocatableRT=0., 
                                          Ntranslocatable=0., publish=["Ntranslocatable"])

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        p = self.params
        k = self.kiosk
        s = self.states

        delt = 1.0
        mc = self._compute_N_max_concentrations()

        # 当发生严重水分短缺时（即 RFTRA <= 0.01），不吸收养分
        if k.RFTRA > 0.01:
            NutrientLIMIT = 1.0
        else:
            NutrientLIMIT = 0.

        # 氮需求量 [kg ha-1]
        r.NdemandLV = max(mc.NMAXLV * k.WLV - k.NamountLV, 0.) + max(k.GRLV * mc.NMAXLV, 0) * delt
        r.NdemandST = max(mc.NMAXST * k.WST - k.NamountST, 0.) + max(k.GRST * mc.NMAXST, 0) * delt
        r.NdemandRT = max(mc.NMAXRT * k.WRT - k.NamountRT, 0.) + max(k.GRRT * mc.NMAXRT, 0) * delt
        r.NdemandSO = max(mc.NMAXSO * k.WSO - k.NamountSO, 0.) + max(k.GRSO * mc.NMAXSO, 0) * delt

        r.Ndemand = r.NdemandLV + r.NdemandST + r.NdemandRT + r.NdemandSO

        # 生物固氮
        r.RNfixation = (max(0., p.NFIX_FR * r.Ndemand) * NutrientLIMIT)

        # 计算各器官可转移的氮
        if(k.DVS < p.DVS_N_TRANSL):
            s.NTranslocatableLV = 0.
            s.NTranslocatableRT = 0.
            s.NTranslocatableST = 0.
            s.NTranslocatable = 0.
        else:
            s.NTranslocatableLV = max(0., k.NamountLV - k.WLV * p.NRESIDLV)
            s.NTranslocatableRT = max(0., k.NamountRT - k.WRT * p.NRESIDRT)
            s.NTranslocatableST = max(0., k.NamountST - k.WST * p.NRESIDST)
            s.NTranslocatable = s.NTranslocatableLV + s.NTranslocatableRT + s.NTranslocatableST

        r.RNtranslocation = min(r.NdemandSO/delt, s.NTranslocatable / p.TCNT)

        if(s.NTranslocatable == 0):
            r.RNtranslocationLV = 0.
            r.RNtranslocationRT = 0.
            r.RNtranslocationST = 0.
        else:
            r.RNtranslocationLV = r.RNtranslocation * (s.NTranslocatableLV / s.NTranslocatable)
            r.RNtranslocationRT = r.RNtranslocation * (s.NTranslocatableRT / s.NTranslocatable) 
            r.RNtranslocationST = r.RNtranslocation * (s.NTranslocatableST / s.NTranslocatable)

        r.RNuptake = (max(0., min(r.Ndemand - r.RNfixation, k.NAVAIL, p.RNUPTAKEMAX)) * NutrientLIMIT)

        if r.Ndemand == 0:
            r.RNuptakeLV = 0.
            r.RNuptakeRT = 0.
            r.RNuptakeST = 0.
            r.RNuptakeSO = 0.
        else:
            r.RNuptakeLV = max(0.,min(r.NdemandLV/delt + r.RNtranslocationLV, r.RNuptake * (r.NdemandLV/delt + r.RNtranslocationLV) / r.Ndemand))
            r.RNuptakeRT = max(0.,min(r.NdemandRT/delt + r.RNtranslocationRT, r.RNuptake * (r.NdemandRT/delt + r.RNtranslocationRT) / r.Ndemand))
            r.RNuptakeST = max(0.,min(r.NdemandST/delt + r.RNtranslocationST, r.RNuptake * (r.NdemandST/delt + r.RNtranslocationST) / r.Ndemand))
            r.RNuptakeSO = max(0.,min(r.NdemandSO/delt - r.RNtranslocation,   r.RNuptake * (r.NdemandSO/delt - r.RNtranslocation) / r.Ndemand))


    @prepare_states
    def integrate(self, day, delt=1.0):
        pass

    def _compute_N_max_concentrations(self):
        """计算叶、茎、根和贮藏器官的最大氮浓度。

        注意：最大浓度首先通过叶片稀释曲线获得；
        茎和根的最大浓度按叶片浓度的某一比例计算。
        """

        p = self.params
        k = self.kiosk
        NMAXLV = p.NMAXLV_TB(k.DVS)

        max_N_conc = MaxNutrientConcentrations(
            # 叶片最大氮浓度 [kg N kg-1 DM]
            NMAXLV=NMAXLV,
            # 茎和根最大氮浓度 [kg N kg-1 DM]
            NMAXST=(p.NMAXST_FR * NMAXLV),
            NMAXRT=p.NMAXRT_FR * NMAXLV,
            NMAXSO=p.NMAXSO
        )

        return max_N_conc
