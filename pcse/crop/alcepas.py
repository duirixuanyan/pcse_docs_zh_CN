# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究院，瓦赫宁根大学
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
"""用于在潜在生产条件下洋葱生长（ALCEPAS）模型的基本例程。

该模型详见以下文献：
- De Visser, C. L. M. . “ALCEPAS, an Onion Growth Model Based on SUCROS87.I. Development of the Model.”
  Journal of Horticultural Science 69, no. 3 (January 1994): 501–18. https://doi.org/10.1080/14620316.1994.11516482.
- De Visser, C. L. M. “ALCEPAS, an Onion Growth Model Based on SUCROS87. II. Validation of the Model.”
  Journal of Horticultural Science 69, no. 3 (January 1994): 519–25. https://doi.org/10.1080/14620316.1994.11516483.
"""
from __future__ import print_function
from math import exp
from collections import deque
from array import array
import datetime as dt

from ..traitlets import Instance, Float, Enum, Unicode
from .assimilation import totass7
from ..util import limit, astro, doy, daylength, AfgenTrait
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, SimulationObject
from ..decorators import prepare_rates, prepare_states
from .. import signals
from .. import exceptions as exc


class Respiration(SimulationObject):

    class Parameters(ParamTemplate):
        Q10 = Float()
        MSOTB = AfgenTrait()
        MLVTB = AfgenTrait()
        MRTTB = AfgenTrait()

    class RateVariables(RatesTemplate):
        MAINT = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish="MAINT")

    @prepare_rates
    def __call__(self, day, drv):
        r = self.rates
        k = self.kiosk
        p = self.params

        MAINSO = p.MSOTB(k.DVS)
        MAINLV = p.MLVTB(k.DVS)
        MAINRT = p.MRTTB(k.DVS)
        MAINTS = MAINLV * k.WLV + MAINRT * k.WRT + MAINSO * k.WSO

        TEFF = p.Q10 ** ((drv.TEMP - 20.) / 10.)
        MNDVS = 1.0
        r.MAINT = min(k.GPHOT, MAINTS * TEFF * MNDVS)
        return r.MAINT


class Assimilation(SimulationObject):

    class Parameters(ParamTemplate):
        AMX = Float()
        EFF = Float()
        KDIF = Float()
        AMDVST = AfgenTrait()
        AMTMPT = AfgenTrait()

    class RateVariables(RatesTemplate):
        GPHOT = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish="GPHOT")

    @prepare_rates
    def __call__(self, day, drv):
        r = self.rates
        k = self.kiosk
        p = self.params

        a = astro(day, drv.LAT, drv.IRRAD)
        AMDVS = p.AMDVST(k.DVS)
        AMTMP = p.AMTMPT(drv.DTEMP)
        AMAX = p.AMX * AMDVS * AMTMP
        DTGA = totass7(a.DAYL, AMAX, p.EFF, k.LAI, p.KDIF, drv.IRRAD, a.DIFPP, a.DSINBE, a.SINLD, a.COSLD)
        r.GPHOT = DTGA * 30./44.
        return r.GPHOT


class Partitioning(SimulationObject):

    class Parameters(ParamTemplate):
        FLVTB = AfgenTrait()
        FSHTB = AfgenTrait()

    class RateVariables(RatesTemplate):
        FSH = Float()
        FLV = Float()
        FSO = Float()
        FRT = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["FSH","FLV","FRT","FSO"])

    @prepare_rates
    def __call__(self, day, drv):
        r = self.rates
        p = self.params
        k = self.kiosk
        r.FSH = p.FSHTB(k.DVS)
        r.FRT = 1. - r.FSH
        r.FLV = p.FLVTB(k.DVS)
        r.FSO = 1. - r.FLV


class Phenology(SimulationObject):

    class Parameters(ParamTemplate):
        TBAS = Float()
        DAGTB = AfgenTrait()
        RVRTB = AfgenTrait()
        BOL50 = Float()
        FALL50 = Float()
        TSOPK = Float() # 出苗所需的累积温度（tsum opkomst）
        TBASE = Float() # 发芽的基础温度
        CROP_START_TYPE = Unicode() # 作物开始的方式
        CROP_END_TYPE = Unicode()   # 作物结束的方式

    class StateVariables(StatesTemplate):
        DVS = Float()         # 发育阶段
        BULBSUM = Float()     # 鳞茎温和（累积）
        BULB = Float()        # 鳞茎生物量
        EMERGE = Float()      # 出苗进展
        DOS = Instance(dt.date)   # 播种日期
        DOE = Instance(dt.date)   # 出苗日期
        DOB50 = Instance(dt.date) # 50%抽薹日期
        DOF50 = Instance(dt.date) # 50%成熟日期
        STAGE = Enum(["emerging", "vegetative", "reproductive", "mature"]) # 生育阶段

    class RateVariables(RatesTemplate):
        DTDEV = Float()    # 日发育增量
        DAYFAC = Float()   # 日长度因子
        RFR = Float()      # 叶面积对发育的限制因子
        RFRFAC = Float()   # 发育修正因子
        DVR = Float()      # 发育进度
        DTSUM = Float()    # 日积温增量
        DEMERGE = Float()  # 出苗速率

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        if parvalues["CROP_START_TYPE"] == "sowing": # 如果为播种
            stage = "emerging"      # 阶段为出苗
            dos = day               # 记录播种日期
            doe = None
        else:                       # 如果为移栽或其他
            stage = "vegetative"    # 阶段为营养生长
            dos = None
            doe = day               # 记录出苗日期
        self.states = self.StateVariables(kiosk, DVS=0., BULBSUM=0., STAGE=stage,
                                          BULB=0., EMERGE=0., DOS=dos, DOE=doe,
                                          DOB50=None, DOF50=None, publish="DVS", )

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        k = self.kiosk
        p = self.params

        if s.STAGE == "emerging":  # 出苗期
            r.DEMERGE = max(0, drv.TEMP - p.TBASE) # 当前温度高于基础温度才积累
            r.DTSUM = 0.
            r.DVR = 0.
        elif s.STAGE == "vegetative": # 营养生长期
            r.DTDEV = max(0., drv.TEMP - p.TBAS) # 日发育增量
            DL = daylength(day, drv.LAT)         # 日长度
            r.DAYFAC = p.DAGTB(DL)               # 日长度修正因子
            r.RFR = exp(-0.222 * k.LAI)          # 叶面积限制因子
            r.RFRFAC = p.RVRTB(r.RFR)            # 发育修正因子
            r.DEMERGE = 0.
            r.DTSUM = r.DTDEV * r.DAYFAC * r.RFRFAC # 日积温
            r.DVR = r.DTSUM/p.BOL50                 # 发育进度
        else: # 生殖期及成熟期
            r.DEMERGE = 0.
            r.DTDEV = max(0., drv.TEMP - p.TBAS)
            r.DTSUM = r.DTDEV
            r.DVR = r.DTSUM/p.FALL50

    @prepare_states
    def integrate(self, day, delt=1.0):
        s = self.states
        r = self.rates
        p = self.params

        BULB = 0. # 鳞茎初始为0
        s.EMERGE += r.DEMERGE * delt           # 累加出苗进展
        s.BULBSUM += r.DTSUM * delt            # 累加鳞茎日温和
        s.DVS += r.DVR * delt                  # 累加发育阶段进度
        if s.STAGE == "emerging":              # 出苗期
            if s.EMERGE >= p.TSOPK:
                s.STAGE = "vegetative"         # 达到出苗温和，进入营养生长期
                s.DOE = day                    # 记录出苗日期
        elif s.STAGE == "vegetative":          # 营养生长期
            BULB = 0.3 + 100.45 * (exp(-exp(-0.0293*(s.BULBSUM - 91.9)))) # 鳞茎生物量计算
            if s.DVS >= 1.0:
                s.STAGE = "reproductive"       # 达到发育阶段1进入生殖期
                s.DOB50 = day                  # 50%抽薹日期
        elif s.STAGE == "reproductive":        # 生殖期
            BULB = 0.3 + 100.45 * (exp(-exp(-0.0293*(s.BULBSUM - 91.9)))) # 鳞茎生物量
            if s.DVS >= 2.0:
                print("Reached maturity at day %s" % day) # msg不翻译
                s.STAGE = "mature"             # 达到发育阶段2进入成熟期
                s.DOF50 = day                  # 50%成熟日期
                if p.CROP_END_TYPE == "maturity": # 终止方式为成熟
                    # 发送作物生命周期完成信号
                    self._send_signal(signal=signals.crop_finish, day=day,
                                      finish_type="MATURITY", crop_delete=True)
        else:  # 成熟期，生育阶段不再变化
            BULB = 0.3 + 100.45 * (exp(-exp(-0.0293*(s.BULBSUM - 91.9)))) # 鳞茎生物量不再变化

        s.BULB = limit(0., 100., BULB)         # 限定鳞茎生物量在[0,100]



class LeafDynamics(SimulationObject):
    """ALCEPAS作物模型的叶片动态模块。

    *模拟参数* （在cropdata字典中提供）

    =======  ================================== =======  ===============
     名称         描述                            类型      单位
    =======  ================================== =======  ===============
    RGRLAI   LAI最大相对增长速率                  SCr     ha ha-1 d-1
    SPAN     叶片在35摄氏度下的寿命                SCr     |d|
    TBASE    叶片衰老的下限温度阈值                SCr     |C|
    PERDL    由水分胁迫引起的                     SCr
              最大叶片死亡速率
    TDWI     初始作物干物重                        SCr     |kg ha-1|
    KDIFTB   可见散射光的消光系数，                TCr
              DVS的函数
    SLATB    比叶面积，DVS的函数                    TCr     |ha kg-1|
    =======  ================================== =======  ===============

    *状态变量*

    =======  ============================== ==== ============
     名称         描述                       Pbl      单位
    =======  ============================== ==== ============
    XXX      xxxxxxxxxxxxxxxxxx              Y|N   |kg ha-1|
    =======  ============================== ==== ============

    *速率变量*

    =======  ============================== ==== ============
     名称         描述                       Pbl      单位
    =======  ============================== ==== ============
    xxxx     xxxxxxxxxxx                     N   |kg ha-1 d-1|
    =======  ============================== ==== ============

    *外部依赖：*

    ========  ======================= ======================== ===========
     名称           描述                  由谁提供                 单位
    ========  ======================= ======================== ===========
    ========  ======================= ======================== ===========
    """

    # 初始LAI随植株密度变化的参数
    LAII = Float(-99)
    SLAN = Float(-99)
    SLAR = Float(-99)

    class Parameters(ParamTemplate):
        SLANTB = AfgenTrait()
        SLARTB = AfgenTrait()
        AGECOR = Float(-99)
        METCOR = Float(-99)
        AGEA = Float(-99)
        AGEB = Float(-99)
        AGEC = Float(-99)
        AGED = Float(-99)
        LAGR = Float(-99.)  # LAI按指数函数计算的上限
        GEGR = Float(-99.)  # 达到LAGR时的总干物质
        LA0 = Float(-99)    # 出苗时的LAI，取决于植株密度（NPL）
        NPL = Float(-99)    # 植株密度
        RGRL = Float(-99)
        GTSLA = Float(-99)
        TTOP = Float(-99)
        TBASE = Float(-99)
        CORFAC = Float(-99)
        TBAS = Float(-99)

    class StateVariables(StatesTemplate):
        LV = Instance(deque)
        SLABC = Instance(deque)
        LVAGE = Instance(deque)
        SPAN = Instance(deque)
        LAIMAX = Float(-99.)
        LAI = Float(-99.)
        WLVG = Float(-99.)
        WLVD = Float(-99.)
        WLV = Float(-99.)
        TSUMEM = Float(-99)

    class RateVariables(RatesTemplate):
        GLV = Float(-99.)
        GLAD = Float(-99.)
        GLA = Float(-99.)
        DLV = Float(-99.)
        SLAT = Float(-99.)
        FYSAGE = Float(-99.)
        SPANT = Float(-99.)
        DTSUMM = Float(-99)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，以key/value对提供参数
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["GLV"])

        # 计算初始状态变量
        p = self.params
        self.LAII = p.NPL * p.LA0 * 1.E-4
        self.SLAN = p.SLANTB(p.NPL)
        self.SLAR = p.SLARTB(p.NPL)

        # 初始叶片生物量
        WLVG = 0.
        WLVD = 0.
        WLV = WLVG + WLVD

        # 第一叶片类（SLA、年龄和质量）
        LV = deque([WLV])
        LVAGE = deque([0.])
        SLABC = deque([0.])
        SPAN = deque([0.])

        # 初始化状态变量对象
        self.states = self.StateVariables(kiosk, publish=["LAI", "WLV", "WLVG", "WLVD"],
                                          LV=LV, LVAGE=LVAGE, SPAN=SPAN, SLABC=SLABC,
                                          LAIMAX=0., TSUMEM=0., LAI=self.LAII, WLV=WLV,
                                          WLVD=WLVD, WLVG=WLVG)

    def calc_SPAN(self):
        p = self.params
        k = self.kiosk
        SPAN = p.AGECOR * p.METCOR * (p.AGEA + p.AGEB / (1 + p.AGED * k.DVS) + p.AGEC * k.DVS)
        return SPAN

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        p = self.params
        k = self.kiosk

        # 叶片增长速率
        # 地上部分的质量
        GSH = k.FSH * k.GTW
        # 新叶片作为地上部分比例的质量
        r.GLV = k.FLV * GSH

        # 确定在states.LV中有多少叶片生物量类别需要死亡，
        # 假设寿命大于SPAN，这些类别将被累计在DLV中。即将死亡的叶面积累计在GLAD中
        # 注意，实际叶片死亡在状态积分步骤中会加到LV数组上。
        DLV = 0.0
        GLAD = 0.0
        for lv, lvage, span, sla in zip(s.LV, s.LVAGE, s.SPAN, s.SLABC):
            if lvage > span:
                DLV += lv
                GLAD += sla * lv
        r.DLV = DLV
        r.GLAD = GLAD

        # 每时间步叶片的生理老化
        DTDEV = max(0, drv.TEMP - p.TBAS)
        r.FYSAGE = DTDEV
        r.SPANT = self.calc_SPAN()

        # 叶面积和SLA的增长
        r.GLA, r.SLAT = self.leaf_area_growth(drv)

    @prepare_states
    def integrate(self, day, delt=1.0):
        params = self.params
        rates = self.rates
        states = self.states

        # --------- 叶片死亡处理 ---------
        tLV = array('d', states.LV)
        tSLABC = array('d', states.SLABC)
        tLVAGE = array('d', states.LVAGE)
        tSPAN = array('d', states.SPAN)
        tDLV = rates.DLV

        # 通过从右侧移除叶片类别，将叶片死亡加到叶片类上
        for LVweigth in reversed(states.LV):
            if tDLV > 0.:
                if tDLV >= LVweigth:  # 从deque中移除整个叶片类别
                    tDLV -= LVweigth
                    tLV.pop()
                    tLVAGE.pop()
                    tSLABC.pop()
                    tSPAN.pop()
                else:  # 减少最老（最右侧）叶片类别的值
                    tLV[-1] -= tDLV
                    tDLV = 0.
            else:
                break

        # 生理年龄的积分
        tLVAGE = deque([age + rates.FYSAGE for age in tLVAGE])
        tLV = deque(tLV)
        tSLABC = deque(tSLABC)
        tSPAN = deque(tSPAN)

        # --------- 叶片生长处理 ---------
        # 新叶片加入第一类
        tLV.appendleft(rates.GLV)
        tSLABC.appendleft(rates.SLAT)
        tLVAGE.appendleft(0.)
        tSPAN.appendleft(rates.SPANT)

        # 计算新的叶面积
#        states.LAI = sum([lv * sla for lv, sla in zip(tLV, tSLABC)])
        states.LAI += rates.GLA
        states.LAIMAX = max(states.LAI, states.LAIMAX)

        # 更新叶片生物量状态
        states.WLVG = sum(tLV)
        states.WLVD += rates.DLV
        states.WLV = states.WLVG + states.WLVD

        # 保存最终的叶片生物量双端队列
        self.states.LV = tLV
        self.states.SLABC = tSLABC
        self.states.LVAGE = tLVAGE
        self.states.SPAN = tSPAN

        self.states.TSUMEM += self.rates.DTSUMM

    def leaf_area_growth(self, drv):
        # 计算每日叶面积指数的增加量（公顷叶/公顷地面/天）
        p = self.params
        k = self.kiosk
        s = self.states
        r = self.rates

        DTEFF = limit(p.TBASE, p.TTOP, drv.TEMP)
        DTR = drv.IRRAD
        if DTEFF > 0:
            r.DTSUMM = 1./((1./DTEFF) + p.CORFAC*(1/(0.5*0.000001*DTR)))
        else:
            r.DTSUMM = 0.

        if s.LAI < p.LAGR and k.TADRW < p.GEGR:
            # 幼苗生长期的叶片生长：
            SLA = (self.SLAN + self.SLAR * p.GTSLA ** k.DVS) * 1/100000.
            GLA = self.LAII * p.RGRL * r.DTSUMM * exp(p.RGRL * s.TSUMEM)
            # 在指数生长期调节最年轻叶片的SLA
            if r.GLV > 0.:
                SLA = GLA/r.GLV
        else:
            # 成熟植株生长期的叶片生长：
            SLA = (self.SLAN + self.SLAR * p.GTSLA ** k.DVS) * 1/100000.
            GLA = (SLA * r.GLV)

        # 考虑叶片死亡的修正
        GLA = GLA - r.GLAD

        return GLA, SLA


class RootDynamics(SimulationObject):

    class RateVariables(RatesTemplate):
        GRT = Float()

    class StateVariables(StatesTemplate):
        WRT = Float()

    def initialize(self, day, kiosk, parvalues):
        self.rates = self.RateVariables(kiosk, publish=["GRT"])
        self.states = self.StateVariables(kiosk, WRT=0., publish=["WRT"])

    @prepare_rates
    def calc_rates(self, day, drv):
        k = self.kiosk
        r = self.rates
        r.GRT = k.FRT * k.GTW

    @prepare_states
    def integrate(self, day, delt=1.0):
        r = self.rates
        s = self.states
        s.WRT += r.GRT * delt


class BulbDynamics(SimulationObject):

    class RateVariables(RatesTemplate):
        GSO = Float()

    class StateVariables(StatesTemplate):
        WSO = Float()

    def initialize(self, day, kiosk, parvalues):
        self.rates = self.RateVariables(kiosk, publish=["GSO"])
        self.states = self.StateVariables(kiosk, WSO=0., publish=["WSO"])

    @prepare_rates
    def calc_rates(self, day, drv):
        k = self.kiosk
        r = self.rates
        # 茎重的增加
        GSH = k.FSH * k.GTW
        # 鳞茎重的增加
        r.GSO = k.FSO * GSH

    @prepare_states
    def integrate(self, day, delt=1.0):
        r = self.rates
        s = self.states
        s.WSO += r.GSO * delt


class ALCEPAS(SimulationObject):
    leafdynamics = Instance(SimulationObject)
    phenology = Instance(SimulationObject)
    partitioning = Instance(SimulationObject)
    assimilation = Instance(SimulationObject)
    respiration = Instance(SimulationObject)
    rootdynamics = Instance(SimulationObject)
    bulbdynamics = Instance(SimulationObject)

    class Parameters(ParamTemplate):
        ASRQSO = Float()
        ASRQRT = Float()
        ASRQLV = Float()

    class RateVariables(RatesTemplate):
        GTW = Float()

    class StateVariables(StatesTemplate):
        TADRW = Float()

    def initialize(self, day, kiosk, parvalues):
        self.leafdynamics = LeafDynamics(day, kiosk, parvalues)
        self.phenology = Phenology(day, kiosk, parvalues)
        self.partitioning = Partitioning(day, kiosk, parvalues)
        self.assimilation = Assimilation(day, kiosk, parvalues)
        self.respiration = Respiration(day, kiosk, parvalues)
        self.rootdynamics = RootDynamics(day, kiosk, parvalues)
        self.bulbdynamics = BulbDynamics(day, kiosk, parvalues)

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["GTW"])
        self.states = self.StateVariables(kiosk, TADRW=0., publish=["TADRW"])

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        k = self.kiosk
        r = self.rates

        # 物候发育
        self.phenology.calc_rates(day, drv)
        if self.get_variable("STAGE") == "emerging":
            self.touch()  # 出苗前无需继续
            return

        # 光合及呼吸
        GPHOT = self.assimilation(day, drv)
        MAINT = self.respiration(day, drv)

        # 分配以及干物质转化所需同化物（kgCH20 / kgDM）
        self.partitioning(day, drv)
        ASRQ = k.FSH * (p.ASRQLV * k.FLV + p.ASRQSO * k.FSO) + p.ASRQRT * k.FRT
        # 干物质总生长量
        r.GTW = (GPHOT - MAINT) / ASRQ

        # 各器官的分配及动态
        self.leafdynamics.calc_rates(day, drv)
        self.rootdynamics.calc_rates(day, drv)
        self.bulbdynamics.calc_rates(day, drv)

        self.check_carbon_balance(day)

    def check_carbon_balance(self, day):
        r = self.rates
        k = self.kiosk
        if r.GTW - (k.GSO + k.GLV + k.GRT) > 0.0001:
            raise exc.CarbonBalanceError("Carbon balance not closing on day %s" % day)

    @prepare_states
    def integrate(self, day, delt=1.0):
        k = self.kiosk
        s = self.states

        self.leafdynamics.integrate(day, delt)
        self.phenology.integrate(day, delt)
        self.rootdynamics.integrate(day, delt)
        self.bulbdynamics.integrate(day, delt)

        s.TADRW = k.WLV + k.WSO + k.WRT
