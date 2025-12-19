# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl)，2014年4月
from math import exp
from collections import deque
from array import array
import numpy as np

from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..util import limit, AfgenTrait
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals

class WOFOST_Leaf_Dynamics(SimulationObject):
    """WOFOST作物模型的叶片动态

    实现叶片的生物量分配、生长及衰老。WOFOST每天跟踪分配到叶片的生物量（变量 `LV`，称为叶类）。
    对于每个叶类，也记录了叶龄（变量 `LVAGE`）和比叶面积（变量 `SLA`）。
    总活叶生物量通过对所有叶类生物量求和获得。类似地，叶面积通过生物量和比叶面积之积（`LV` * `SLA`）求和得出。

    叶片的衰老可能由于生理年龄、干旱胁迫或自遮荫等原因发生。

    *模拟参数* （在cropdata字典中提供）

    =======  ============================================= =======  ============
     名称     描述                                           类型     单位
    =======  ============================================= =======  ============
    RGRLAI   LAI的最大相对增长率                            SCr     ha ha-1 d-1
    SPAN     叶片在35摄氏度下的寿命                         SCr     |d|
    TBASE    叶片衰老的下限温度                             SCr     |C|
    PERDL    由于水分胁迫导致的叶片最大相对死亡率           SCr
    TDWI     初始作物干重                                   SCr     |kg ha-1|
    KDIFTB   随DVS变化的漫射可见光消光系数                  TCr
    SLATB    随DVS变化的比叶面积                            TCr     |ha kg-1|
    =======  ============================================= =======  ============

    *状态变量*

    =======  ================================================= ==== ============
     名称     描述                                             Pbl      单位
    =======  ================================================= ==== ============
    LV       每个叶类的叶片生物量                              N    |kg ha-1|
    SLA      每个叶类的比叶面积                                N    |ha kg-1|
    LVAGE    每个叶类的叶龄（天）                              N    |d|
    LVSUM    LV的总和                                          N    |kg ha-1|
    LAIEM    苗期的LAI                                         N    -
    LASUM    LV*SLA之和得到的总叶面积，不包括茎和荚的面积       N    -
    LAIEXP   理论指数生长下的LAI值                             N    -
    LAIMAX   生长周期达到的最大LAI                             N    -
    LAI      包含茎与荚面积的叶面积指数                        Y    -
    WLV      活叶干重                                          Y    |kg ha-1|
    DWLV     死叶干重                                          N    |kg ha-1|
    TWLV     总叶干重（活+死）                                 Y    |kg ha-1|
    =======  ================================================= ==== ============

    *速率变量*

    =======  ================================================= ==== ============
     名称     描述                                             Pbl      单位
    =======  ================================================= ==== ============
    GRLV     叶片的生长速率                                     N   |kg ha-1 d-1|
    DSLV1    水分胁迫导致的叶片死亡速率                         N   |kg ha-1 d-1|
    DSLV2    自遮荫导致的叶片死亡速率                           N   |kg ha-1 d-1|
    DSLV3    霜冻导致的叶片死亡速率                             N   |kg ha-1 d-1|
    DSLV     取DSLV1、DSLV2、DSLV3中最大值                      N   |kg ha-1 d-1|
    DALV     叶片衰老导致的死亡速率                             N   |kg ha-1 d-1|
    DRLV     DSLV和DALV合并后的叶片死亡速率                     N   |kg ha-1 d-1|
    SLAT     当前时间步的比叶面积，针对此源/库限制              N   |ha kg-1|
             叶片膨胀速率
    FYSAGE   生理叶龄的增加量                                   N   -
    GLAIEX   受库限制的叶片扩展速率（指数曲线）                 N   |ha ha-1 d-1|
    GLASOL   受源限制的叶片扩展速率（生物量增加）               N   |ha ha-1 d-1|
    =======  ================================================= ==== ============

    
    *外部依赖项:*
    
    ======== ============================== =============================== ===========
     名称     描述                                  提供者                  单位
    ======== ============================== =============================== ===========
    DVS      作物发育阶段                     DVS_Phenology                   - 
    FL       分配到叶片的生物量分数           DVS_Partitioning                -
    FR       分配到根的生物量分数             DVS_Partitioning                -
    SAI      茎面积指数                       WOFOST_Stem_Dynamics            -
    PAI      荚面积指数                       WOFOST_Storage_Organ_Dynamics   -
    TRA      蒸腾速率                         Evapotranspiration            |cm day-1|
    TRAMX    最大蒸腾速率                     Evapotranspiration            |cm day-1| 
    ADMI     地上干物质增加量                 CropSimulation                |kg ha-1 d-1|
    RF_FROST 抗冻减少因子                     FROSTOL                         -
    ======== ============================== =============================== ===========
    """

    class Parameters(ParamTemplate):
        RGRLAI = Float(-99.)
        SPAN   = Float(-99.)
        TBASE  = Float(-99.)
        PERDL  = Float(-99.)
        TDWI   = Float(-99.)
        SLATB  = AfgenTrait()
        KDIFTB = AfgenTrait()

    class StateVariables(StatesTemplate):
        LV     = Instance(deque)
        SLA    = Instance(deque)
        LVAGE  = Instance(deque)
        LAIEM  = Float(-99.)
        LASUM  = Float(-99.)
        LAIEXP = Float(-99.)
        LAIMAX = Float(-99.)
        LAI    = Float(-99.)
        WLV    = Float(-99.)
        DWLV   = Float(-99.)
        TWLV   = Float(-99.)

    class RateVariables(RatesTemplate):
        GRLV  = Float(-99.)
        DSLV1 = Float(-99.)
        DSLV2 = Float(-99.)
        DSLV3 = Float(-99.)
        DSLV  = Float(-99.)
        DALV  = Float(-99.)
        DRLV  = Float(-99.)
        SLAT  = Float(-99.)
        FYSAGE = Float(-99.)
        GLAIEX = Float(-99.)
        GLASOL = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，以键值对提供参数
        """

        self.kiosk  = kiosk
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk)

        # 计算初始状态变量
        params = self.params
        FL  = self.kiosk["FL"]
        FR  = self.kiosk["FR"]
        DVS = self.kiosk["DVS"]

        # 初始叶片生物量
        WLV  = (params.TDWI * (1-FR)) * FL
        DWLV = 0.
        TWLV = WLV + DWLV

        # 第一叶片级（SLA、年龄和重量）
        SLA   = deque([params.SLATB(DVS)])
        LVAGE = deque([0.])
        LV    = deque([WLV])

        # 初始叶面积值
        LAIEM  = LV[0] * SLA[0]
        LASUM  = LAIEM
        LAIEXP = LAIEM
        LAIMAX = LAIEM
        LAI    = LASUM + self.kiosk["SAI"] + self.kiosk["PAI"]

        # 初始化StateVariables对象
        self.states = self.StateVariables(kiosk, publish=["LAI","TWLV","WLV"],
                                          LV=LV, SLA=SLA, LVAGE=LVAGE, LAIEM=LAIEM,
                                          LASUM=LASUM, LAIEXP=LAIEXP, LAIMAX=LAIMAX,
                                          LAI=LAI, WLV=WLV, DWLV=DWLV, TWLV=TWLV)

    def _calc_LAI(self):
        # 总叶面积指数等于叶片、荚果和茎的面积之和
        SAI = self.kiosk["SAI"]
        PAI = self.kiosk["PAI"]
        return self.states.LASUM + SAI + PAI

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        p = self.params
        k = self.kiosk

        # 叶片生长速率
        # 新叶片重量
        r.GRLV = k.ADMI * k.FL

        # 因水分/氧气胁迫导致的叶片死亡
        r.DSLV1 = s.WLV * (1. - k.RFTRA) * p.PERDL

        # 因LAI过高造成的自遮荫导致叶片死亡
        DVS = self.kiosk["DVS"]
        LAICR = 3.2/p.KDIFTB(DVS)
        r.DSLV2 = s.WLV * limit(0., 0.03, 0.03*(s.LAI-LAICR)/LAICR)

        # 因冻害导致叶片死亡，由抗冻减少因子"RF_FROST"决定
        if "RF_FROST" in self.kiosk:
            r.DSLV3 = s.WLV * k.RF_FROST
        else:
            r.DSLV3 = 0.

        # 叶片死亡等于水分胁迫、遮荫和冻害中的最大值
        r.DSLV = max(r.DSLV1, r.DSLV2, r.DSLV3)

        # 判断在states.LV中有多少叶片生物量类需要死亡，
        # 若寿命 > SPAN，这些类会在DALV中累计
        # 实际的叶片死亡会在状态积分步骤中加在LV数组上
        DALV = 0.0
        for lv, lvage in zip(s.LV, s.LVAGE):
            if lvage > p.SPAN:
                DALV += lv
        r.DALV = DALV

        # 总叶片死亡速率
        r.DRLV = max(r.DSLV, r.DALV)

        # 每个时间步叶片的生理年龄增长量
        r.FYSAGE = max(0., (drv.TEMP - p.TBASE)/(35. - p.TBASE))

        # 每个时间步的单位叶面积(SLA)
        r.SLAT = p.SLATB(DVS)

        # 叶面积不超过指数增长曲线
        if s.LAIEXP < 6.:
            DTEFF = max(0., drv.TEMP-p.TBASE)
            r.GLAIEX = s.LAIEXP * p.RGRLAI * DTEFF
            # 源库限制的叶面积增加量
            r.GLASOL = r.GRLV * r.SLAT
            # 汇库限制的叶面积增加量
            GLA = min(r.GLAIEX, r.GLASOL)
            # 调整最年轻叶片类的单位叶面积
            if r.GRLV > 0.:
                r.SLAT = GLA/r.GRLV

    @prepare_states
    def integrate(self, day, delt=1.0):
        params = self.params
        rates = self.rates
        states = self.states

        # --------- 叶片死亡 ---------
        tLV = array('d', states.LV)
        tSLA = array('d', states.SLA)
        tLVAGE = array('d', states.LVAGE)
        tDRLV = rates.DRLV

        # 通过从deque右侧移除叶片类别来实现叶片死亡。
        for LVweigth in reversed(states.LV):
            if tDRLV > 0.:
                if tDRLV >= LVweigth: # 移除整个叶片类别
                    tDRLV -= LVweigth
                    tLV.pop()
                    tLVAGE.pop()
                    tSLA.pop()
                else: # 只减少最老（最右边）叶片类别的值
                    tLV[-1] -= tDRLV
                    tDRLV = 0.
            else:
                break

        # 生理年龄的积分
        tLVAGE = deque([age + rates.FYSAGE for age in tLVAGE])
        tLV = deque(tLV)
        tSLA = deque(tSLA)

        # --------- 叶片生长 ---------
        # 新叶片进入第1类
        tLV.appendleft(rates.GRLV)
        tSLA.appendleft(rates.SLAT)
        tLVAGE.appendleft(0.)

        # 计算新的叶面积
        states.LASUM = sum([lv*sla for lv, sla in zip(tLV, tSLA)])
        states.LAI = self._calc_LAI()
        states.LAIMAX = max(states.LAI, states.LAIMAX)

        # 指数增长曲线
        states.LAIEXP += rates.GLAIEX

        # 更新叶片生物量状态
        states.WLV  = sum(tLV)
        states.DWLV += rates.DRLV
        states.TWLV = states.WLV + states.DWLV

        # 存储最终叶片生物量的deque
        self.states.LV = tLV
        self.states.SLA = tSLA
        self.states.LVAGE = tLVAGE

    @prepare_states
    def _set_variable_LAI(self, nLAI):
        """将LAI值更新为输入的新值。

        相关的状态变量也会被更新，并且所有被调整状态变量的增量会以字典形式返回。
        """
        states = self.states

        # 存储状态变量的旧值
        oWLV = states.WLV
        oLAI = states.LAI
        oTWLV = states.TWLV
        oLASUM = states.LASUM

        # 为荚和茎面积调整oLAI。SAI和PAI通常是叶面积的极小部分，因此不做调整。
        # 对所有WOFOST作物文件而言，SPA和SSA都为零。
        SAI = self.kiosk["SAI"]
        PAI = self.kiosk["PAI"]
        adj_nLAI = max(nLAI - SAI - PAI, 0.)
        adj_oLAI = max(oLAI - SAI - PAI, 0.)

        # 叶生物量LV的LAI调整因子（rLAI）
        if adj_oLAI > 0:
            rLAI = adj_nLAI/adj_oLAI
            LV = [lv*rLAI for lv in states.LV]
        # 若adj_oLAI == 0，则直接将叶生物量加到最年轻的叶龄类别（LV[0]）
        else:
            LV = [nLAI/states.SLA[0]]

        states.LASUM = sum([lv*sla for lv, sla in zip(LV, states.SLA)])
        states.LV = deque(LV)
        states.LAI = self._calc_LAI()
        states.WLV = sum(states.LV)
        states.TWLV = states.WLV + states.DWLV

        increments = {"LAI": states.LAI - oLAI,
                      "LAISUM":states.LASUM - oLASUM,
                      "WLV": states.WLV - oWLV,
                      "TWLV": states.TWLV - oTWLV}
        return increments

class CSDM_Leaf_Dynamics(SimulationObject):
    """叶片动态遵循冠层结构动态模型（Canopy Structure Dynamic Model, CSDM）。

    与真实CSDM模型的唯一区别在于，CSDM中是温度积作为驱动变量，而在本例中驱动变量仅为模型运行后的日数。

    参考文献:
    Koetz 等, 2005. 使用耦合冠层结构动态和辐射传输模型估算冠层生物物理特性.
    Remote Sensing of Environment. Volume 95, Issue 1, 2005年3月15日, 页115-124. http://dx.doi.org/10.1016/j.rse.2004.11.017

    下述GNUPLOT代码可用于作图展示CSDM模型效果：

        td = 150
        CSDM_MAX = 5.
        CSDM_MIN = 0.15
        CSDM_A = 0.085
        CSDM_B = 0.045
        CSDM_T1 = int(td/3.)
        CSDM_T2 = td

        set xrange [0:200]
        set yrange [-1:8]
        plot CSDM_MIN + CSDM_MAX*(1./(1. + exp(-CSDM_B*(x - CSDM_T1)))**2 - exp(CSDM_A*(x - CSDM_T2)))

    """

    class Parameters(ParamTemplate):
        CSDM_MAX = Float()
        CSDM_MIN = Float()
        CSDM_A = Float()
        CSDM_B = Float()
        CSDM_T1 = Float()
        CSDM_T2 = Float()

    class StateVariable(StatesTemplate):
        LAI = Float()
        DAYNR = Int()
        LAIMAX = Float()

    def _CSDM(self, daynr):
        """根据当前日数（daynr）和CSDM模型参数返回LAI值。"""
        p = self.params

        LAI_growth = 1./(1. + exp(-p.CSDM_B*(daynr - p.CSDM_T1)))**2
        LAI_senescence = -exp(p.CSDM_A*(daynr - p.CSDM_T2))
        LAI = p.CSDM_MIN + p.CSDM_MAX*(LAI_growth + LAI_senescence)

        # 不允许LAI低于CSDM_MIN
        if LAI < p.CSDM_MIN:
            msg = ("LAI of CSDM model smaller then lower LAI limit "+
                   "(CSDM_MIN)! Adjusting LAI to CSDM_MIN.")
            self.logger.warn(msg)
            LAI = max(p.CSDM_MIN, LAI)

        return LAI

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，以键/值对形式提供参数
        """

        self.params = self.Parameters(parvalues)

        # 通过CSDM模型计算第1天的LAI
        LAI = self._CSDM(1)
        self.states = self.StateVariable(kiosk, LAI=LAI, DAYNR=1,
                                         LAIMAX=self.params.CSDM_MIN,
                                         publish="LAI")

    @prepare_rates
    def calc_rates(self, day, drv):
        pass

    @prepare_states
    def integrate(self, day, delt=1.0):

        self.states.DAYNR += 1
        self.states.LAI = self._CSDM(self.states.DAYNR)
        if self.states.LAI > self.states.LAIMAX:
            self.states.LAIMAX = self.states.LAI

        if self.states.DAYNR > self.params.CSDM_T2:
            self._send_signal(signal=signals.crop_finish, day=day,
                              finish_type="Canopy died according to CSDM leaf model.",
                              crop_delete=True)


class WOFOST_Leaf_Dynamics_N(SimulationObject):
    """
    WOFOST作物模型中的叶片动态，包括叶片对氮胁迫的响应。

    # HB 20220405: 此函数已做较大修改，需重新编写文档。

    实现了叶片生物量的分配、叶片的生长和衰老。WOFOST跟踪每天分配给叶片的生物量（变量`LV`，称为叶片类）。
    对于每个叶片类，还记录了叶龄（变量`LVAGE`）和比叶面积（变量`SLA`）。
    通过对所有叶片类的生物量求和，计算总的活叶生物量。类似地，通过生物量与比叶面积（`LV` * `SLA`）的乘积求和计算叶面积。

    叶片的衰老可以由于生理年龄、干旱胁迫、养分胁迫或自遮荫而发生。

    最后，叶片扩展（SLA）可受到养分胁迫影响。

    *仿真参数* （在cropdata字典中提供）

    =======  ============================================= =======  ============
     名称     描述                                           类型      单位
    =======  ============================================= =======  ============
    RGRLAI   LAI的最大相对增长率                            SCr      ha ha-1 d-1
    SPAN     叶片在35℃下的寿命                             SCr      |d|
    TBASE    叶片衰老的下限温度阈值                         SCr      |C|
    PERDL    因水分胁迫导致的叶片最大相对死亡率             SCr
    TDWI     初始作物干物质量                               SCr      |kg ha-1|
    KDIFTB   扩散可见光的消光系数，DVS的函数                TCr
    SLATB    比叶面积，DVS的函数                            TCr      |ha kg-1|
    RDRNS    因氮素胁迫导致的叶片最大相对死亡率             TCr         -
    NLAI     氮素胁迫对LAI增长（幼苗期）的抑制系数          TCr         -
    NSLA     氮素NPK胁迫对SLA下降的系数                     TCr         -
    RDRNS    因氮素胁迫导致的叶片最大相对死亡率             TCr         -
    =======  ============================================= =======  ============

    *状态变量*

    =======  ================================================= ==== ============
     名称     描述                                             公布    单位
    =======  ================================================= ==== ============
    LV       每个叶片类的叶片生物量                             N    |kg ha-1|
    SLA      每个叶片类的比叶面积                               N    |ha kg-1|
    LVAGE    每个叶片类的叶龄                                   N    |d|
    LVSUM    LV的总和                                           N    |kg ha-1|
    LAIEM    出苗时的LAI                                        N    -
    LASUM    所有叶片类`LV*SLA`的总叶面积（不含茎和荚面积）      N    -
    LAIEXP   理论指数生长下的LAI                                 N    -
    LAIMAX   生长周期内达到的最大LAI                             N    -
    LAI      包括茎和荚面积的叶面积指数                         Y    -
    WLV      活叶干重                                           Y    |kg ha-1|
    DWLV     死叶干重                                           N    |kg ha-1|
    TWLV     叶片总干重（活+死）                                Y    |kg ha-1|
    =======  ================================================= ==== ============


    *速率变量*

    =======  ================================================= ==== ============
     名称     描述                                             公布    单位
    =======  ================================================= ==== ============
    GRLV     叶片生长速率                                       N   |kg ha-1 d-1|
    DSLV1    因水分胁迫导致的叶片死亡速率                       N   |kg ha-1 d-1|
    DSLV2    因自遮荫导致的叶片死亡速率                         N   |kg ha-1 d-1|
    DSLV3    因冻害导致的叶片死亡速率                           N   |kg ha-1 d-1|
    DSLV4    因养分胁迫导致的叶片死亡速率                       N   |kg ha-1 d-1|
    DSLV     DSLV1、DSLV2、DSLV3三者中的最大值                  N   |kg ha-1 d-1|
    DALV     由于老化导致的叶片死亡速率                         N   |kg ha-1 d-1|
    DRLV     由DSLV、DALV共同导致的叶片死亡速率                 N   |kg ha-1 d-1|
    SLAT     当前时间步长的比叶面积（根据源/库限制的            N   |ha kg-1|
             叶片扩展速率调整）
    FYSAGE   生理叶龄的增加                                     N   -
    GLAIEX   库限制下叶片指数增长速率（指数曲线）               N   |ha ha-1 d-1|
    GLASOL   源限制下叶片扩展速率（生物量增长）                 N   |ha ha-1 d-1|
    =======  ================================================= ==== ============


    *外部依赖：*

    ======== ============================== =============================== ===========
     名称     描述                               提供者                          单位
    ======== ============================== =============================== ===========
    DVS      作物发育阶段                    DVS_Phenology                    -
    FL       分配给叶的生物量分数            DVS_Partitioning                 -
    FR       分配给根的生物量分数            DVS_Partitioning                 -
    SAI      茎面积指数                      WOFOST_Stem_Dynamics             -
    PAI      荚面积指数                      WOFOST_Storage_Organ_Dynamics    -
    TRA      蒸腾速率                        Evapotranspiration              |cm day-1|
    TRAMX    最大蒸腾速率                    Evapotranspiration              |cm day-1|
    ADMI     地上干物质增量                  CropSimulation                  |kg ha-1 d-1|
    RF_FROST 冻害降低因子                    FROSTOL                          -
    ======== ============================== =============================== ===========
    """

    class Parameters(ParamTemplate):
        RGRLAI = Float(-99.)
        SPAN = Float(-99.)
        TBASE = Float(-99.)
        PERDL = Float(-99.)
        TDWI = Float(-99.)
        SLATB = AfgenTrait()
        KDIFTB = AfgenTrait()

    class StateVariables(StatesTemplate):
        LV = Instance(deque)
        SLA = Instance(deque)
        LVAGE = Instance(deque)
        LAIEM = Float(-99.)
        LASUM = Float(-99.)
        LAIEXP = Float(-99.)
        LAIMAX = Float(-99.)
        LAI = Float(-99.)
        WLV = Float(-99.)
        DWLV = Float(-99.)
        TWLV = Float(-99.)

    class RateVariables(RatesTemplate):
        GRLV = Float(-99.)
        DSLV1 = Float(-99.)
        DSLV2 = Float(-99.)
        DSLV3 = Float(-99.)
        DSLV4 = Float(-99.)
        DSLV = Float(-99.)
        DALV = Float(-99.)
        DRLV = Float(-99.)
        SLAT = Float(-99.)
        FYSAGE = Float(-99.)
        GLAIEX = Float(-99.)
        GLASOL = Float(-99.)

    def initialize(self, day, kiosk, cropdata):
        """
        :param day: 模拟开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param cropdata: 包含WOFOST作物数据键值对的字典
        """

        self.kiosk = kiosk
        self.params = self.Parameters(cropdata)
        self.rates = self.RateVariables(kiosk,publish=["DRLV", "GRLV"])

        # 计算初始状态变量
        p = self.params
        k = self.kiosk
        # 初始叶片生物量
        WLV = (p.TDWI * (1-k.FR)) * k.FL
        DWLV = 0.
        TWLV = WLV + DWLV

        # 第一片叶片（比叶面积、年龄和重量）
        SLA = deque([p.SLATB(k.DVS)])
        LVAGE = deque([0.])
        LV = deque([WLV])

        # 初始叶面积参数
        LAIEM = LV[0] * SLA[0]
        LASUM = LAIEM
        LAIEXP = LAIEM
        LAIMAX = LAIEM
        LAI = LASUM + k.SAI + k.PAI

        # 初始化状态变量对象
        self.states = self.StateVariables(
            kiosk, publish=["LAI", "TWLV", "WLV"],
            LV=LV, SLA=SLA, LVAGE=LVAGE,
            LAIEM=LAIEM, LASUM=LASUM, LAIEXP=LAIEXP,
            LAIMAX=LAIMAX, LAI=LAI, WLV=WLV, DWLV=DWLV, TWLV=TWLV
        )

    def _calc_LAI(self):
        # 总叶面积指数，为叶、荚、茎面积之和
        k = self.kiosk
        return self.states.LASUM + k.SAI + k.PAI

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        p = self.params
        k = self.kiosk

        # 叶片生长速率
        # 新叶片的重量
        r.GRLV = k.ADMI * k.FL

        # 由于水/氧胁迫导致的叶片死亡
        r.DSLV1 = s.WLV * (1. - k.RFTRA) * p.PERDL

        # 由于高LAI（自遮荫）导致的叶片死亡
        LAICR = 3.2 / p.KDIFTB(k.DVS)
        r.DSLV2 = s.WLV * limit(0., 0.03, 0.03 * (s.LAI - LAICR) / LAICR)

        # 由冻害导致的叶片死亡，通过冻害降低因子 "RF_FROST" 确定
        if "RF_FROST" in k:
            r.DSLV3 = s.WLV * k.RF_FROST
        else:
            r.DSLV3 = 0.

        # 决定在states.LV中有多少叶生物量类别需要死亡，
        # 假定寿命 > SPAN，这些类别将累加在DALV中。
        # 实际的叶片死亡作用在LV数组的状态积分阶段完成。
        DALV = 0.0
        for lv, lvage in zip(s.LV, s.LVAGE):
            if lvage > p.SPAN:
                DALV += lv
        r.DALV = DALV

        # Allard建议加快叶片老化
        r.DSLV = max(r.DSLV1, r.DSLV2, r.DSLV3)
        r.DALV = min(DALV * k.NSLLV, k.WLV)

        # 叶片总死亡速率
        r.DRLV = max(r.DSLV, r.DALV)

        # 叶片每步生理年龄的增加
        r.FYSAGE = max(0., (drv.TEMP - p.TBASE) / (35. - p.TBASE))

        # 叶片比叶面积每步的数值
        r.SLAT = p.SLATB(k.DVS)

        # 叶面积不超过指数增长曲线
        if s.LAIEXP < 6.:
            DTEFF = max(0., drv.TEMP - p.TBASE)

            # IS添加
            # 幼苗期养分和水分胁迫：
            if k.DVS < 0.2 and s.LAI < 0.75:
                factor = k.RFTRA * k.RFRGRL
            else:
                factor = 1.

            r.GLAIEX = s.LAIEXP * p.RGRLAI * DTEFF * factor
            # 受源限制的叶面积增加
            r.GLASOL = r.GRLV * r.SLAT
            # 受库限制的叶面积增加
            GLA = min(r.GLAIEX, r.GLASOL)
            # 对最年轻叶片类别的比叶面积进行调整
            if r.GRLV > 0.:
                r.SLAT = GLA / r.GRLV

    @prepare_states
    def integrate(self, day, delt=1.0):
        p = self.params
        r = self.rates
        s = self.states
        k = self.kiosk

        # --------- 叶片死亡 ---------
        tLV = array('d', s.LV)
        tSLA = array('d', s.SLA)
        tLVAGE = array('d', s.LVAGE)
        tDRLV = r.DRLV

        # 通过从双端队列右侧移除叶片类别，强加叶片死亡
        for LVweigth in reversed(s.LV):
            if tDRLV > 0.:
                if tDRLV >= LVweigth: # 移除整个叶片类别
                    tDRLV -= LVweigth
                    tLV.pop()
                    tLVAGE.pop()
                    tSLA.pop()
                else: # 仅减少最老（最右侧）叶片类别的叶重
                    tLV[-1] -= tDRLV
                    tDRLV = 0.
            else:
                break

        # 生理年龄的积分
        tLVAGE = deque([age + r.FYSAGE for age in tLVAGE])

        # 若出现再分配，则均匀减少叶片生物量
        if k.REALLOC_LV > 0:
            sumLV = sum(tLV)
            if k.REALLOC_LV < sumLV:
                ReductionFactorLV = (sumLV - k.REALLOC_LV)/sumLV
                tLV = np.array(tLV) * ReductionFactorLV

        tLV = deque(tLV)
        tSLA = deque(tSLA)

        # --------- 叶片生长 ---------
        # 新叶片进入类别1
        tLV.appendleft(r.GRLV)
        tSLA.appendleft(r.SLAT)
        tLVAGE.appendleft(0.)

        # 计算新的叶面积
        s.LASUM = sum([lv*sla for lv, sla in zip(tLV, tSLA)])
        s.LAI = self._calc_LAI()
        s.LAIMAX = max(s.LAI, s.LAIMAX)

        # 指数增长曲线
        s.LAIEXP += r.GLAIEX

        # 更新叶片生物量状态
        s.WLV  = sum(tLV)
        s.DWLV += r.DRLV
        s.TWLV = s.WLV + s.DWLV

        # 保存最终叶片生物量的双端队列
        self.states.LV = tLV
        self.states.SLA = tSLA
        self.states.LVAGE = tLVAGE
