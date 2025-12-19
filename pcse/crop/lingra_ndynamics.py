# -*- coding: utf-8 -*-
# 版权所有 (c) 2021 Wageningen 环境研究所
# Allard de Wit (allard.dewit@wur.nl)，2021年7月
# LINGRA N 方法基于 Joost Wolf 的工作
from collections import namedtuple

import pcse
from pcse import exceptions as exc
from pcse.traitlets import Float, Int, Instance, Bool
from pcse.decorators import prepare_rates, prepare_states
from pcse.base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject
from pcse.util import AfgenTrait, limit

MaxNutrientConcentrations = namedtuple("MaxNutrientConcentrations", ["NMAXLV", "NMAXRT",])


class N_Demand_Uptake(SimulationObject):
    """计算作物氮需求量及其从土壤中的吸收量。

    作物氮需求量的计算方法为：植株营养器官（叶、茎和根）中氮的实际浓度（kg N/kg生物量）与各器官最大氮浓度的差值。氮的吸收量估算为土壤供应与作物需求之间的最小值。

    **模拟参数**

    ============  ======================================== =======  =====================
      名称         描述                                      类型       单位
    ============  ======================================== =======  =====================
    NMAXLV_TB      叶片最大氮浓度，DVS的函数                 TCr      kg N kg-1 干生物量
    NMAXRT_FR      根的最大氮浓度，相对于叶片最大值的分数    SCr      -
    ============  ======================================== =======  =====================


    **速率变量**

    ===========  ============================================= ==== ================
      名称          描述                                        Pbl      单位
    ===========  ============================================= ==== ================
    RNuptakeLV     叶中氮的吸收速率                              Y   |kg N ha-1 d-1|
    RNuptakeRT     根中氮的吸收速率                              Y   |kg N ha-1 d-1|

    RNuptake       氮的总吸收速率                                Y   |kg N ha-1 d-1|
    NdemandLV      叶的氮需求量，基于当前生长速率及前期的亏缺    N   |kg N ha-1|
    NdemandRT      根的氮需求量，同叶                            N   |kg N ha-1|

    Ndemand        总氮需求量（叶+根）                           N   |kg N ha-1|
    ===========  ============================================= ==== ================

    **发送或处理的信号**

    无

    **外部依赖**

    ================  ================================ ====================  ===========
      名称             描述                                提供模块                单位
    ================  ================================ ====================  ===========
    DVS               作物发育阶段                      DVS_Phenology              -
    NAVAIL            土壤中可用氮总量                  NPK_Soil_Dynamics      |kg ha-1|
    ================  ================================ ====================  ===========

    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()  # 叶片最大氮浓度，按DVS的函数
        NMAXRT_FR = Float(-99.)  # 根的最大氮浓度，相对于叶片最大氮浓度
        NUPTAKE_MAX = Float(-99)

    class RateVariables(RatesTemplate):
        RNuptakeLV = Float(-99.)  # 氮吸收速率 [kg ha-1 d -1]
        RNuptakeRT = Float(-99.)
        RNuptake = Float(-99.)  # 总氮吸收速率 [kg ha-1 d -1]

        NdemandLV = Float(-99.)
        NdemandRT = Float(-99.)
        Ndemand = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param parvalues: 包含参数键/值对的ParameterProvider
        """

        self.params = self.Parameters(parvalues)
        self.kiosk = kiosk

        self.rates = self.RateVariables(kiosk, publish=["RNuptakeLV", "RNuptakeRT", "RNuptake", ])

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        p = self.params
        k = self.kiosk

        delt = 1.0
        mc = self._compute_N_max_concentrations()

        # 叶片、茎、根和贮藏器官的总NPK需求量
        # 需求由前一时刻遗留的需求及新生长所需的需求组成
        # 注意此处为预积分，因此需要乘以时间步长delt

        # 氮的需求量 [kg ha-1]
        r.NdemandLV = max(mc.NMAXLV * k.WeightLVgreen - k.NamountLV, 0.) + max(k.LVgrowth * mc.NMAXLV, 0) * delt
        r.NdemandRT = max(mc.NMAXRT * k.WeightRT - k.NamountRT, 0.) + max(k.dWeightRT * mc.NMAXRT, 0) * delt
        r.Ndemand = r.NdemandLV + r.NdemandRT

        # 当发生严重干旱（即RFTRA <= 0.01）时，不吸收营养物质
        NutrientLIMIT = 1.0 if k.RFTRA > 0.01 else 0.

        # 氮的吸收速率
        # 如果没有需求，则吸收速率为0
        if r.Ndemand == 0.:
            r.RNuptake = r.RNuptakeLV = r.RNuptakeRT = 0.
        else:
            # 从土壤吸收的氮，其最大值不超过NUPTAKE_MAX
            RNuptake = (max(0., min(r.Ndemand, k.NAVAIL)) * NutrientLIMIT)
            r.RNuptake = min(RNuptake, p.NUPTAKE_MAX)
            # 在根/叶之间分配
            r.RNuptakeLV = (r.NdemandLV / r.Ndemand) * r.RNuptake
            r.RNuptakeRT = (r.NdemandRT / r.Ndemand) * r.RNuptake

    @prepare_states
    def integrate(self, day, delt=1.0):
        pass

    def _compute_N_max_concentrations(self):
        """计算叶片、茎、根和贮藏器官中的最大氮浓度。

        注意，最大浓度首先通过叶片的稀释曲线得到。
        茎和根的最大浓度是叶片最大浓度的一个分数。
        贮藏器官的最大浓度直接取自参数 NMAXSO。
        """

        p = self.params
        k = self.kiosk
        NMAXLV = p.NMAXLV_TB(k.DVS)
        max_NPK_conc = MaxNutrientConcentrations(
            # 叶片中的最大NPK浓度 [kg N kg-1 DM]
            NMAXLV=NMAXLV,
            NMAXRT=p.NMAXRT_FR * NMAXLV,
        )

        return max_NPK_conc


class N_Stress(SimulationObject):
    """通过氮素营养指数实现氮胁迫的计算。

    胁迫因子是根据植株营养器官生物量中的氮质量浓度计算的。对于每一种营养物质，会根据叶片和茎的生物量计算出四种浓度：
    - 实际浓度（实际营养元素总量/营养器官生物量）
    - 最大浓度（植株可以吸收进叶片和茎中的最大浓度）
    - 临界浓度（能维持生长速率不受氮限制的浓度，由 NCRIT_FR 决定，
      对N来说，临界浓度可以比最大浓度低，此浓度有时也称为“最优浓度”。）
    - 残留浓度（锁定在植物结构生物量中，不能再被动用的量）

    胁迫指数（SI）通过下述浓度的简单比值确定：

    :math:`SI = (C_{a) - C_{r})/(C_{c} - C_{r})`

    其中下标 `a`、`r` 和 `c` 分别代表营养元素的实际、残留和临界浓度。这一计算得到氮素营养指数（NNI）。
    最终，同化的还原因子（RFNUTR）通过光合有效系数的还原因子（NLUE）计算得到。

    **模拟参数**

    ============  ============================================= =======  ======================
     Name          说明                                         类型      单位
    ============  ============================================= =======  ======================
    NMAXLV_TB      叶片最大氮浓度，随DVS变化                     TCr     kg N kg-1 干物质
    NMAXRT_FR      根最大氮浓度占叶片最大N浓度的比例             SCr     -
    NCRIT_FR       营养器官整体（叶+茎）最大N浓度的临界倍数      SCr     -
    NRESIDLV       叶片残留N分数                                 SCr     kg N kg-1 干物质
    NLUE           氮胁迫对光合有效率的影响                      SCr     -
    ============  ============================================= =======  ======================

    **速率变量**

    这里的速率变量实际上是由状态变量推导得到，并不直接代表速率。不过它们直接用于速率变量计算，因此放在这里。

    =======  ================================================= ==== ==============
     名称     说明                                             发布     单位
    =======  ================================================= ==== ==============
    NNI      氮营养指数                                        Y     -
    RFNUTR   光合有效率还原因子                                Y     -
    =======  ================================================= ==== ==============


    **外部依赖：**

    ==============  =============================== =====================  ==============
     名称            说明                               提供者               单位
    ==============  =============================== =====================  ==============
    DVS              作物发育进程                    DVS_Phenology            -
    WST              活茎干重                        WOFOST_Stem_Dynamics   |kg ha-1|
    WeightLVgreen    活叶干重                        WOFOST_Leaf_Dynamics   |kg ha-1|
    NamountLV        叶片中的N总量                   N_Crop_Dynamics        |kg ha-1|
    ==============  =============================== =====================  ==============
    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()  # 最大叶片氮浓度，作为dvs的函数
        NCRIT_FR = Float(-99.)  # 最优氮浓度为最大氮浓度的分数
        NRESIDLV = Float(-99.)  # 叶片残留氮分数 [kg N kg-1 干物质]
        NLUE = Float()

    class RateVariables(RatesTemplate):
        NNI = Float()
        RFNUTR = Float()

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 当前日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: 含有参数键/值对的ParameterProvider
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["NNI", "RFNUTR"])

    @prepare_rates
    def __call__(self, day, drv):

        p = self.params
        r = self.rates
        k = self.kiosk

        # 叶片最大氮浓度 (kg N kg-1 干物质)
        NMAXLV = p.NMAXLV_TB(k.DVS)

        # 地上部分营养器官总活性干重 (kg 干物质 ha-1)
        VBM = k.WeightLVgreen

        # 地上营养器官中临界(最优)氮量
        # 及其氮浓度
        NcriticalLV = p.NCRIT_FR * NMAXLV * VBM

        # 如果地上部分活体生物量=0, 则最优=0
        if VBM > 0.:
            NcriticalVBM = NcriticalLV / VBM
            NconcentrationVBM = (k.NamountLV) / VBM
            NresidualVBM = (k.WeightLVgreen * p.NRESIDLV) / VBM
        else:
            NcriticalVBM = 0.
            NconcentrationVBM = 0.
            NresidualVBM = 0.

        # 氮胁迫指数（NNI）计算
        if (NcriticalVBM - NresidualVBM) > 0.:
            r.NNI = limit(0.001, 1.0, (NconcentrationVBM - NresidualVBM) / (NcriticalVBM - NresidualVBM))
        else:
            r.NNI = 0.001

        # 氮素还原因子计算
        r.RFNUTR = limit(0., 1.0, 1. - p.NLUE * (1.0 - r.NNI) ** 2)

        return r.NNI


class N_Crop_Dynamics(SimulationObject):
    """整体作物氮素动态的实现。

    NPK_Crop_Dynamics 实现了作物内部氮素收支的整体逻辑。

    **模拟参数**

    =============  ============================================== =======  ======================
     名称            说明                                           类型      单位
    =============  ============================================== =======  ======================
    NMAXLV_TB      叶片最大氮浓度，随dvs变化                       TCr     kg N kg-1 干物质
    NMAXRT_FR      根系最大氮浓度（以比例表示）                    SCr     -
    NRESIDLV       叶片中残留氮比例                                SCr     kg N kg-1 干物质
    NRESIDRT       根系中残留氮比例                                SCr     kg N kg-1 干物质
    =============  ============================================== =======  ======================

    **状态变量**

    ==========  ============================================ ==== ============
     名称         说明                                       Pbl       单位
    ==========  ============================================ ==== ============
    NamountLV    绿色叶片实际氮含量                          Y    |kg N ha-1|
    NamountRT    活根实际氮含量                              Y    |kg N ha-1|
    Nuptake_T    吸收氮素总量                                N    |kg N ha-1|
    Nlosses_T    衰老造成的总氮损失量                        N    |kg N ha-1|
    ==========  ============================================ ==== ============

    **速率变量**

    ===========  ================================================== ==== ============
     名称           说明                                             Pbl    单位
    ===========  ================================================== ==== ============
    RNamountLV     叶片氮素净增加量                                  N   |kg ha-1 d-1|
    RNamountRT     根系氮素净增加量                                  N   |kg ha-1 d-1|
    RNdeathLV      叶片氮损失速率                                    N   |kg ha-1 d-1|
    RNdeathRT      根系氮损失速率                                    N   |kg ha-1 d-1|
    RNloss         衰老导致的氮损失速率                              N   |kg ha-1 d-1|
    ===========  ================================================== ==== ============

    **发送或处理的信号**

    无

    **外部依赖**

    =======  =============================== ====================  ============
     名称         说明                             提供者              单位
    =======  =============================== ====================  ============
    LVdeath     叶片死亡速率                 WOFOST_Leaf_Dynamics  |kg ha-1 d-1|
    =======  =============================== ====================  ============
    """

    WeightLV_remaining = Float()
    _flag_MOWING = Bool(False)

    demand_uptake = Instance(SimulationObject)
    NamountLVI = Float(-99.)  # 初始叶片氮素含量
    NamountRTI = Float(-99.)  # 初始根系氮素含量

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()
        NMAXRT_FR = Float(-99.)
        NRESIDLV = Float(-99.)  # 叶片残留氮比例 [kg N kg-1 干物质]
        NRESIDRT = Float(-99.)  # 根系残留氮比例 [kg N kg-1 干物质]

    class StateVariables(StatesTemplate):
        NamountLV = Float(-99.)  # 叶片氮素含量 [kg N ha-1]
        NamountRT = Float(-99.)  # 根系氮素含量 [kg N]
        Nuptake_T = Float(-99.)  # 吸收氮素总量 [kg N]
        Nlosses_T = Float(-99.)

    class RateVariables(RatesTemplate):
        RNamountLV = Float(-99.)  # 不同器官氮PK净速率
        RNamountRT = Float(-99.)
        RNdeathLV = Float(-99.)  # 叶片氮损失速率 [kg ha-1 d-1]
        RNharvestLV = Float()    # 收获造成的氮损失 [kg ha-1 d-1]
        RNdeathRT = Float(-99.)  # 根系氮损失速率 [kg ha-1 d-1]
        RNloss = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param kiosk: 该PCSE实例的变量kiosk
        :param parvalues: 以参数名/值对形式给出的参数字典
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk

        # 初始化npk作物动态相关组件
        self.demand_uptake = N_Demand_Uptake(day, kiosk, parvalues)

        # 初始状态
        params = self.params
        k = kiosk

        # 初始氮素含量
        self.NamountLVI = NamountLV = k.WeightLVgreen * params.NMAXLV_TB(k.DVS)
        self.NamountRTI = NamountRT = k.WeightRT * params.NMAXLV_TB(k.DVS) * params.NMAXRT_FR

        self.states = self.StateVariables(kiosk, publish=["NamountLV", "NamountRT"],
                                          NamountLV=NamountLV,NamountRT=NamountRT,Nuptake_T=0., Nlosses_T=0.)
        self._connect_signal(self._on_MOWING, signal=pcse.signals.mowing)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates = self.rates
        params = self.params
        k = self.kiosk
        s = self.states

        self.demand_uptake.calc_rates(day, drv)

        if self._flag_MOWING is True:
            # 由于收割导致的氮损失
            rates.RNharvestLV = k.dWeightHARV / k.WeightLVgreen * s.NamountLV
            rates.RNdeathLV = 0.0
        else:
            # 由于植株死亡导致的氮损失
            rates.RNdeathLV = params.NRESIDLV * k.LVdeath
            rates.RNharvestLV = 0.0
        rates.RNdeathRT = 0.0
        rates.RNloss = rates.RNdeathLV + rates.RNdeathRT + rates.RNharvestLV

        # 叶片和根系的氮速率为吸收-死亡-收割
        rates.RNamountLV = k.RNuptakeLV - rates.RNdeathLV - rates.RNharvestLV
        rates.RNamountRT = k.RNuptakeRT - rates.RNdeathRT

        self._check_N_balance(day)
        self._flag_MOWING = False

    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states
        k = self.kiosk

        # 叶片、茎秆、根和储藏器官中的氮素含量
        states.NamountLV += rates.RNamountLV
        states.NamountRT += rates.RNamountRT

        self.demand_uptake.integrate(day, delt)

        # 植株从土壤吸收的总氮量
        states.Nuptake_T += k.RNuptake
        # 死亡物质造成的总氮损失
        states.Nlosses_T += rates.RNloss

    def _check_N_balance(self, day):
        s = self.states
        checksum = abs(s.Nuptake_T + (self.NamountLVI + self.NamountRTI) -
                       (s.NamountLV + s.NamountRT + s.Nlosses_T))

        if abs(checksum) >= 1.0:
            msg = "N flows not balanced on day %s\n" % day
            msg += "Checksum: %f, Nuptake_T: %f\n" % (checksum, s.Nuptake_T)
            msg += "NamountLVI: %f, NamountRTI: %f\n" % \
                   (self.NamountLVI, self.NamountRTI)
            msg += "NamountLV: %f, NamountRT: %f, \n" % \
                   (s.NamountLV, s.NamountRT)
            msg += "NLOSST: %f\n" % (s.Nlosses_T)
            raise exc.NutrientBalanceError(msg)

    def _on_MOWING(self, biomass_remaining):
        """处理割草事件的函数
        """
        self.WeightLV_remaining = biomass_remaining
        self._flag_MOWING = True