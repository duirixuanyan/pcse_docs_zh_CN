# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""WOFOST 水分平衡模块的 Python 实现，用于在自由排水条件下
模拟潜在生产力（`WaterbalancePP`）和水分受限生产力
（`WaterbalanceFD`）。
"""
from math import sqrt

from ..traitlets import Float, Int, Instance, Enum, Unicode, Bool, List
from ..decorators import prepare_rates, prepare_states
from ..util import limit, Afgen, merge_dict
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals
from .. import exceptions as exc
from .snowmaus import SnowMAUS


class WaterbalancePP(SimulationObject):
    """在潜在生产力下模拟的虚拟水分平衡。

    保持土壤水分在田间持水量，并且在仿真过程中只累计作物的蒸腾
    和土壤蒸发速率。
    """
    # 距上次下雨天数计数器
    DSLR = Float(1)
    # 前一天的降雨量
    RAINold = Float(0)

    class Parameters(ParamTemplate):
        SMFCF = Float(-99.)

    class StateVariables(StatesTemplate):
        SM = Float(-99.)
        WTRAT = Float(-99.)
        EVST = Float(-99.)

    class RateVariables(RatesTemplate):
        EVS = Float(-99.)
        WTRA = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """    
        :param day: 仿真的起始日期
        :param kiosk: 该 PCSE 实例的变量 kiosk
        :param parvalues: 包含所有参数的 ParameterProvider 对象
    
        该水分平衡模块始终保持土壤水分在田间持水量。因此，   
        `WaterbalancePP` 只有一个参数（`SMFCF`：土壤的田间持水量）
        和一个状态变量（`SM`：体积含水量）。
        """
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish="EVS")
        self.states = self.StateVariables(kiosk, SM=self.params.SMFCF,
                                          publish="SM", EVST=0, WTRAT=0)
    
    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        # 作物蒸腾和最大土壤/地表水分蒸发速率由作物蒸散发模块计算
        # 但是，如果作物尚未出苗，则将TRA设为0，且直接采用潜在土壤/水分蒸发速率，因此时无冠层遮荫
        if "TRA" not in self.kiosk:
            r.WTRA = 0.
            EVSMX = drv.ES0
        else:
            r.WTRA = self.kiosk["TRA"]
            EVSMX = self.kiosk["EVSMX"]

        # 实际蒸发速率

        if self.RAINold >= 1:
            # 如果前一天降雨量≥1cm，则假定为最大土壤蒸发
            r.EVS = EVSMX
            self.DSLR = 1.
        else:
            # 否则土壤蒸发速率是上次降雨天数(DSLR)的函数
            self.DSLR += 1
            EVSMXT = EVSMX * (sqrt(self.DSLR) - sqrt(self.DSLR - 1))
            r.EVS = min(EVSMX, EVSMXT + self.RAINold)

        # 保存降雨量以跟踪土壤表面湿度，并在需要时重置self.DSLR
        self.RAINold = drv.RAIN

    @prepare_states
    def integrate(self, day, delt=1.0):
        # 保持土壤水分等于田间持水量
        self.states.SM = self.params.SMFCF

        # 累计蒸腾量和土壤蒸发量
        self.states.EVST += self.rates.EVS * delt
        self.states.WTRAT += self.rates.WTRA * delt
        

class WaterbalanceFD(SimulationObject):
    """自由排水土壤的水分平衡（受限水分生产条件）。

    土壤水分平衡计算的目的是估算每日的土壤含水量。土壤水分含量会影响土壤水分的吸收与作物蒸腾。

    动态计算分为两个部分：一部分是每个时间步长（=1天）内变化速率的计算，另一部分是累积变量和状态变量的计算。水分平衡受降雨、地表储水的缓冲（如有）以及蒸散作用驱动。涉及的过程包括入渗、土壤水分保持、渗漏（此处指根系土层向第二层的向下水流）以及超出最大根系生长层水分的损失。

    假设土壤质地剖面为均质。最初土壤剖面分为两层：实际已扎根的土壤以及根层之下、直到根系达到最大根深的土壤区域（受土壤和作物共同影响）。根区从初始根深延伸到最大根深的过程在 Root_Dynamics 类中描述。从根深达到最大后，若根系能穿透整个土层，土壤剖面可视为单层，否则底部保留未扎根区域。

    WaterbalanceFD 类源自 WOFOST7.1 的 WATFD.FOR 文件，区别在于土壤的深度现在完全由最大土壤深度（RDMSOL）决定，而不是取土壤深度与作物最大根深（RDMCR）中的较小值。

    **模拟参数:**
 
    ======== ======================================================== ======= ==========
     名称      说明                                                     类型     单位
    ======== ======================================================== ======= ==========
    SMFCF     土壤田间持水量                                             SSo     -
    SM0       土壤孔隙度                                                 SSo     -
    SMW       土壤凋萎点                                                 SSo     -
    CRAIRC    土壤临界含气量(涝害)                                       SSo     -
    SOPE      根区最大渗漏速率                                           SSo    |cmday-1|
    KSUB      底层（非根区）最大渗漏速率                                 SSo    |cmday-1|
    RDMSOL    土壤可扎根深度                                             SSo     cm
    IFUNRN    非入渗降雨比例是否为降雨量的函数(1为是,0为否)               SSi    -
    SSMAX     最大地表储水量                                             SSi     cm
    SSI       初始地表储水量                                             SSi     cm
    WAV       整个土壤剖面的初始水量                                     SSi     cm
    NOTINF    不能入渗进土壤的最大降雨比例                               SSi     -
    SMLIM     初始根区的最大含水量                                       SSi     -
    ======== ======================================================== ======= ==========

    **状态变量:**

    ======= ====================================================================== ==== ============
     名称     描述                                                                  Pbl      单位
    ======= ====================================================================== ==== ============
    SM       根区体积含水量                                                          Y    -
    SS       地表储水（地表覆盖水层）                                                N    cm
    SSI      初始地表储水量                                                          N    cm
    W        根区土壤水量                                                            N    cm
    WI       根区初始土壤水量                                                        N    cm
    WLOW     底层土壤（当前根深到最大根层深之间）的水量                               N    cm
    WLOWI    初始底层土壤水量                                                        N    cm
    WWLOW    整个土壤剖面总水量（WWLOW=WLOW+W）                                     N    cm
    WTRAT    水分平衡计算损失的总蒸腾水量                                            N    cm
             注: 该变量可能与CTRAT变量不同,后者仅在作物周期内统计
    EVST     土壤表面总蒸发量                                                        N    cm
    EVWT     水面总蒸发量                                                            N    cm
    TSR      地表径流总量                                                            N    cm
    RAINT    总降雨量(有效+无效)                                                     N    cm
    WDRT     根系生长导致增加的根区水量                                              N    cm
    TOTINF   入渗总量                                                               N    cm
    TOTIRR   有效灌溉总量                                                           N    cm
    PERCT    根区至底层的总渗漏量                                                    N    cm
    LOSST    损失到更深土壤中的水量总量                                              N    cm
    DSOS     缺氧压力天数，累计连续缺氧天数                                           Y     -
    WBALRT   根区水分平衡校验值(将在 finalize()中计算，若abs(WBALRT)>0.0001则抛出     N    cm
             WaterBalanceError)
    WBALTT   总水分平衡校验值(将在 finalize()中计算，若abs(WBALTT)>0.0001则抛出       N    cm
             WaterBalanceError)
    ======= ====================================================================== ==== ============

    **速率变量：**

    =========== ================================================================== ==== ============
     名称        描述                                                               Pbl     单位
    =========== ================================================================== ==== ============
    EVS         土壤中实际蒸发速率                                                    N    |cmday-1|
    EVW         水面实际蒸发速率                                                      N    |cmday-1|
    WTRA        实际作物冠层蒸腾速率，直接来源于蒸散发模块的TRA变量                   N    |cmday-1|
    RAIN_INF    当前日降雨的有效入渗速率                                              N    |cmday-1|
    RAIN_NOTINF 当前日降雨的未渗入速率                                                N    |cmday-1|
    RIN         当前日的入渗速率                                                      N    |cmday-1|
    RIRR        当前日有效灌溉速率(按灌溉量×效率计算)                                N    |cmday-1|
    PERC        向非根区(底层)的渗漏速率                                              N    |cmday-1|
    LOSS        向更深层土壤的水分损失速率                                            N    |cmday-1|
    DW          根区水分因入渗、蒸腾和蒸发变化的速率                                  N    |cmday-1|
    DWLOW       底层水分变化速率                                                      N    |cmday-1|
    DTSR        地表径流变化速率                                                      N    |cmday-1|
    DSS         地表储水变化速率                                                      N    |cmday-1|
    =========== ================================================================== ==== ============

    **外部依赖变量：**

    ============ ================================= ========================= =========
     名称        描述                                 来源                     单位
    ============ ================================= ========================= =========
     TRA         作物蒸腾速率                          蒸散发模块              |cmday-1|
     EVSMX       土壤表面（植被冠层下）                蒸散发模块              |cmday-1|
                 最大蒸发速率
     EVWMX       水面（冠层下）最大蒸发速率            蒸散发模块              |cmday-1|
     RD          根深                                 Root_dynamics           cm
    ============ ================================= ========================= =========

    **抛出异常说明：**

    在模拟周期结束时，如果水分平衡未闭合（如发生“水分泄漏”），将抛出 WaterbalanceError。
    """
    # 先前和最大根系深度值
    RDold = Float(-99.)
    RDM = Float(-99.)
    # 距上次降雨天数计数器
    DSLR = Float(-99.)
    # 前一天的入渗速率
    RINold = Float(-99)
    # 非入渗降雨与暴雨大小的关系
    NINFTB = Instance(Afgen)
    # 是否存在作物的标志
    in_crop_cycle = Bool(False)
    # 标志，表示作物开始或结束，因此根区深度可能发生变化，需要在根区和底层之间重新分配水分
    rooted_layer_needs_reset = Bool(False)
    # 灌溉占位符
    _RIRR = Float(0.)
    # 上层（根区深度）默认深度
    DEFAULT_RD = Float(10.)
    # 由于状态更新导致WLOW的增量
    _increments_W = List()

    class Parameters(ParamTemplate):
        # 土壤参数
        SMFCF  = Float(-99.)
        SM0    = Float(-99.)
        SMW    = Float(-99.)
        CRAIRC = Float(-99.)
        SOPE   = Float(-99.)
        KSUB   = Float(-99.)
        RDMSOL = Float(-99.)
        # 地块参数
        IFUNRN = Float(-99.)
        SSMAX  = Float(-99.)
        SSI    = Float(-99.)
        WAV    = Float(-99.)
        NOTINF = Float(-99.)

    class StateVariables(StatesTemplate):
        SM = Float(-99.)
        SS = Float(-99.)
        SSI = Float(-99.)
        W  = Float(-99.)
        WI = Float(-99.)
        WLOW  = Float(-99.)
        WLOWI = Float(-99.)
        WWLOW = Float(-99.)
        # 累积变量
        WTRAT  = Float(-99.)
        EVST   = Float(-99.)
        EVWT   = Float(-99.)
        TSR    = Float(-99.)
        RAINT  = Float(-99.)
        WDRT   = Float(-99.)
        TOTINF = Float(-99.)
        TOTIRR = Float(-99.)
        PERCT  = Float(-99.)
        LOSST  = Float(-99.)
        # 根区(RT)和系统总量(TT)校验值
        WBALRT = Float(-99.)
        WBALTT = Float(-99.)
        DSOS = Int(-99)

    class RateVariables(RatesTemplate):
        EVS   = Float(-99.)
        EVW   = Float(-99.)
        WTRA  = Float(-99.)
        RIN   = Float(-99.)
        RIRR  = Float(-99.)
        PERC  = Float(-99.)
        LOSS  = Float(-99.)
        DW    = Float(-99.)
        DWLOW = Float(-99.)
        DTSR = Float(-99.)
        DSS = Float(-99.)
        DRAINT = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 此 PCSE 实例的变量kiosk
        :param parvalues: 包含所有参数的 ParameterProvider
        """

        # 检查表层土壤最大持水量(SMLIM)的有效性
        SMLIM = limit(parvalues["SMW"], parvalues["SM0"],  parvalues["SMLIM"])

        if SMLIM != parvalues["SMLIM"]:
            msg = "SMLIM not in valid range, changed from %f to %f."
            self.logger.warn(msg % (parvalues["SMLIM"], SMLIM))

        # 赋值参数
        self.params = self.Parameters(parvalues)
        p = self.params
        
        # 默认设定RD为10cm，同时确定最大深度和旧的根系深度
        RD = self.DEFAULT_RD
        RDM = max(RD, p.RDMSOL)
        self.RDold = RD
        self.RDM = RDM
        
        # 初始地表径流储量
        SS = p.SSI
        
        # 初始土壤含水量及根区水分储量，受SMLIM限制。记录初始值WI
        SM = limit(p.SMW, SMLIM, (p.SMW + p.WAV/RD))
        W = SM * RD
        WI = W
        
        # 当前根区与最大根系可达深度之间的初始含水量（WLOW）。记录初值WLOWI
        WLOW  = limit(0., p.SM0*(RDM - RD), (p.WAV + RDM*p.SMW - W))
        WLOWI = WLOW
        
        # 土壤剖面（水分根区 + 下部土壤）总含水量
        WWLOW = W + WLOW

        # 土壤蒸发，距上次降雨天数(DSLR)。当土壤湿度高于SMW和SMFCF的中值时设为1，否则为5
        self.DSLR = 1. if (SM >= (p.SMW + 0.5*(p.SMFCF-p.SMW))) else 5.

        # 初始化剩余辅助变量
        self.RINold = 0.
        self.in_crop_cycle = False
        self.NINFTB = Afgen([0.0,0.0, 0.5,0.0, 1.5,1.0])

        # 初始化模型状态变量
        self.states = self.StateVariables(kiosk, publish=["SM", "DSOS"], SM=SM, SS=SS,
                           SSI=p.SSI, W=W, WI=WI, WLOW=WLOW, WLOWI=WLOWI,
                           WWLOW=WWLOW, WTRAT=0., EVST=0., EVWT=0., TSR=0.,
                           RAINT=0., WDRT=0., TOTINF=0., TOTIRR=0., DSOS=0,
                           PERCT=0., LOSST=0., WBALRT=-999., WBALTT=-999.)
        self.rates = self.RateVariables(kiosk, publish="EVS")
        
        # 连接CROP_START/CROP_FINISH信号，用于水分平衡，查找作物蒸散量
        self._connect_signal(self._on_CROP_START, signals.crop_start)
        self._connect_signal(self._on_CROP_FINISH, signals.crop_finish)
        # 灌溉信号
        self._connect_signal(self._on_IRRIGATE, signals.irrigate)

        self._increments_W = []

    @prepare_rates
    def calc_rates(self, day, drv):
        s = self.states
        p = self.params
        r = self.rates
        k = self.kiosk

        # 灌溉速率(RIRR)
        r.RIRR = self._RIRR
        self._RIRR = 0.

        # 作物蒸散和土壤/地表水最大蒸发速率由作物蒸散模块计算
        # 若作物尚未出苗，则TRA=0，直接采用潜在土壤/地表水蒸发速率，因为无冠层遮蔽
        if "TRA" not in self.kiosk:
            r.WTRA = 0.
            EVWMX = drv.E0
            EVSMX = drv.ES0
        else:
            r.WTRA = k.TRA
            EVWMX = k.EVWMX
            EVSMX = k.EVSMX

        # 实际蒸发速率
        r.EVW = 0.
        r.EVS = 0.
        if s.SS > 1.:
            # 如果地表径流储量>1cm，则从地表水层蒸发
            r.EVW = EVWMX
        else:
            # 否则假设从土壤表面蒸发
            if self.RINold >= 1:
                # 如果上一日入渗 >= 1cm，假设土壤蒸发为最大值
                r.EVS = EVSMX
                self.DSLR = 1.
            else:
                # 否则土壤蒸发为降雨间隔天数(DSLR)的函数
                EVSMXT = EVSMX * (sqrt(self.DSLR + 1) - sqrt(self.DSLR))
                r.EVS = min(EVSMX, EVSMXT + self.RINold)
                self.DSLR += 1

        # 潜在可入渗降雨量
        if p.IFUNRN == 0:
            RINPRE = (1. - p.NOTINF) * drv.RAIN
        else:
            # 入渗量为降雨量的函数(NINFTB)
            RINPRE = (1. - p.NOTINF * self.NINFTB(drv.RAIN)) * drv.RAIN

        # 二次初步入渗速率(RINPRE)，包含地表水储量和灌溉
        RINPRE = RINPRE + r.RIRR + s.SS
        if s.SS > 0.1:
            # 存在地表水储量，入渗受SOPE限制
            AVAIL = RINPRE - r.EVW
            RINPRE = min(p.SOPE, AVAIL)
            
        RD = self._determine_rooting_depth()
        
        # 根区土壤水分平衡含水量
        WE = p.SMFCF * RD
        # 根区向下部土壤的渗漏量为根区多余水分，不超过根区最大渗漏速率(SOPE)
        PERC1 = limit(0., p.SOPE, (s.W - WE) - r.WTRA - r.EVS)

        # 最大根区底部的水分损失
        # 根区以下土壤水分的平衡含水量
        WELOW = p.SMFCF * (self.RDM - RD)
        r.LOSS = limit(0., p.KSUB, (s.WLOW - WELOW + PERC1))

        # 渗漏量不超过下层土壤的吸收能力
        PERC2 = ((self.RDM - RD) * p.SM0 - s.WLOW) + r.LOSS
        r.PERC = min(PERC1, PERC2)

        # 调整入渗速率
        r.RIN = min(RINPRE, (p.SM0 - s.SM)*RD + r.WTRA + r.EVS + r.PERC)
        self.RINold = r.RIN

        # 根区和下部区域的含水量变化率
        r.DW = r.RIN - r.WTRA - r.EVS - r.PERC
        r.DWLOW = r.PERC - r.LOSS

        # 检查DW是否导致W为负
        # 如为负，则减少EVS使W=0
        Wtmp = s.W + r.DW
        if Wtmp < 0.0:
            r.EVS += Wtmp
            assert r.EVS >= 0., "Negative soil evaporation rate on day %s: %s" % (day, r.EVS)
            r.DW = -s.W

        # 计算地表储水和径流速率的变化量
        # SStmp为不可入渗但可储存于地表的水层。假设RAIN_NOTINF自动形成地表径流（最终变为径流）
        SStmp = drv.RAIN + r.RIRR - r.EVW - r.RIN
        # 地表储水变化率不超过SSMAX-SS
        r.DSS = min(SStmp, (p.SSMAX - s.SS))
        # SStmp剩余部分变为地表径流
        r.DTSR = SStmp - r.DSS
        # 输入降雨速率
        r.DRAINT = drv.RAIN

    @prepare_states
    def integrate(self, day, delt=1.0):
        s = self.states
        p = self.params
        r = self.rates
        
        # 水量平衡的积分：合计量和状态变量

        # 根区总蒸腾量
        s.WTRAT += r.WTRA * delt

        # 地表水层和/或土壤的总蒸发量
        s.EVWT += r.EVW * delt
        s.EVST += r.EVS * delt

        # 总降雨、灌溉和入渗量
        s.RAINT += r.DRAINT * delt
        s.TOTINF += r.RIN * delt
        s.TOTIRR += r.RIRR * delt

        # 更新地表储水和地表总径流（TSR）
        s.SS += r.DSS * delt
        s.TSR += r.DTSR * delt

        # 根区水量
        s.W += r.DW * delt
        assert s.W >= 0., "Negative amount of water in root zone on day %s: %s" % (day, s.W)

        # 深渗和深层淋溶损失总量
        s.PERCT += r.PERC * delt
        s.LOSST += r.LOSS * delt

        # 非根区（下层）可生根带的水量
        s.WLOW += r.DWLOW * delt
        # 根区和下层所有可生根带的总水量
        s.WWLOW = s.W + s.WLOW * delt

        # 根区子系统边界的变化

        # 首先获取实际根系深度
        RD = self._determine_rooting_depth()
        RDchange = RD - self.RDold
        self._redistribute_water(RDchange)

        # 根区平均土壤含水量
        s.SM = s.W/RD

        # 氧气胁迫天数累计（仅在作物存在时）
        if s.SM >= (p.SM0 - p.CRAIRC):  # and self.in_crop_cycle:
            s.DSOS += 1
        else:
            s.DSOS = 0

        # 保存根系深度
        self.RDold = RD

    @prepare_states
    def finalize(self, day):
        
        s = self.states
        p = self.params

        # 对于无地下水系统，检验水量平衡
        # 分别计算根区（WBALRT）和整个系统（WBALTT）
        # 所有增量的和相加以保证水量收支的闭合
        s.WBALRT = s.TOTINF + s.WI + s.WDRT - s.EVST - s.WTRAT - s.PERCT - s.W + sum(self._increments_W)
        s.WBALTT = (s.SSI + s.RAINT + s.TOTIRR + s.WI - s.W + sum(self._increments_W) +
                    s.WLOWI - s.WLOW - s.WTRAT - s.EVWT - s.EVST - s.TSR - s.LOSST - s.SS)

        if abs(s.WBALRT) > 0.0001:
            msg = "Water balance for root zone does not close."
            raise exc.WaterBalanceError(msg)

        if abs(s.WBALTT) > 0.0001:
            msg = "Water balance for complete soil profile does not close.\n"
            msg += ("Total INIT + IN:   %f\n" % (s.WI + s.WLOWI + s.SSI + s.TOTIRR +
                                                 s.RAINT))
            msg += ("Total FINAL + OUT: %f\n" % (s.W + s.WLOW + s.SS + s.EVWT + s.EVST +
                                                 s.WTRAT + s.TSR + s.LOSST))
            raise exc.WaterBalanceError(msg)
        
        # 对子仿真对象运行finalize
        SimulationObject.finalize(self, day)
    
    def _determine_rooting_depth(self):
        """判断根系深度（RD）的合理使用

        本函数包含确定水量平衡上层（有根层）深度的逻辑。详见代码中的注释说明。
        """
        if "RD" in self.kiosk:
            return self.kiosk["RD"]
        else:
            # 保持RD为默认值
            return self.DEFAULT_RD

    def _redistribute_water(self, RDchange):
        """在根区和下部土层之间重新分配水分。

        :param RDchange: 根系深度的变化 [cm]，向下生长为正，向上减少为负

        当生长季节根系生长、作物周期结束根区深度从作物根深退回到默认的根层深度、或者作物初始根深与水量平衡模块（10 cm）使用的默认值不同时，都需要进行土壤水分的重新分配。
        """
        s = self.states
        p = self.params
        
        WDR = 0.
        if RDchange > 0.001:
            # 根系向下生长超过0.001 cm
            # 从原本无根区转移水分到新根系区域
            WDR = s.WLOW * RDchange/(p.RDMSOL - self.RDold)
            # 取WDR和WLOW中的最小值，避免由于数值误差出现WLOW为负
            WDR = min(s.WLOW, WDR)
        else:
            # 根系向上减少超过0.001 cm（尤其在作物消失时）
            # 将原有根系区的水分转移到新形成的无根区
            WDR = s.W * RDchange/self.RDold

        if abs(WDR) > 0.:
            # 减少下层土壤中的水分
            s.WLOW -= WDR
            # 增加根区土壤中的水分
            s.W += WDR
            # 由根区重置带来的总水分增量
            s.WDRT += WDR

    def _on_CROP_START(self):
        # 作物生长周期开始
        self.in_crop_cycle = True
        self.rooted_layer_needs_reset = True

    def _on_CROP_FINISH(self):
        # 作物生长周期结束
        self.in_crop_cycle = False
        self.rooted_layer_needs_reset = True

    def _on_IRRIGATE(self, amount, efficiency):
        # 接收到灌溉事件
        self._RIRR = amount * efficiency

    def _set_variable_SM(self, nSM):
        """根据给定土壤含水量强制调整模型状态。

        这意味着除了根区土壤含水量，还必须更新根区可用水量（W），因为SM源于W。

        此外，对W的增量会添加到self._increments_W中，以确保水量平衡仍然闭合。
        """
        s = self.states

        # 旧值
        oSM = s.SM
        oW = s.W
        # 新值
        nW = nSM/oSM * s.W

        # 更新状态变量
        s.W = nW
        s.SM = nSM
        s.WWLOW = s.WLOW + s.W

        # 存储W的增量
        self._increments_W.append(nW - oW)

        # 返回所有变量的增量
        return {"W": nW - oW, "SM": nSM - oSM}


class WaterbalanceFDSnow(SimulationObject):
    """组合了SnowMAUS和WaterbalanceFD对象的SimulationObject。

    注意，目前雪模块和水分平衡被视为独立的模拟：我们只是累积雪被，
    同时土壤水分平衡则将降雨累积为如果没有雪的情况。
    这需要更改，但在此之前雪模块应当被集成到一个更通用的土壤表面
    储水模拟对象中，该对象包括土壤表面储水的所有选项：水体（积水）、雪，
    也许还有冠层截留（目前缺乏该部分）。
    """
    waterbalance = Instance(SimulationObject)
    snowcover = Instance(SimulationObject)

    # 使用观测雪深
    use_observed_snow_depth = Bool(False)
    # 观测雪深的辅助变量
    _SNOWDEPTH = Float()

    class StateVariables(StatesTemplate):
        SNOWDEPTH = Float()

    def initialize(self, day, kiosk, parvalues):
        self.waterbalance = WaterbalanceFD(day, kiosk, parvalues)

        # 判断使用观测雪深还是模拟雪深
        if "ISNOWSRC" not in parvalues:
            msg = "Parameter for selecting observed(0)/simulated(1) snow depth ('ISNOWSRC') missing!"
            raise exc.ParameterError(msg)
        else:
            self.use_observed_snow_depth = True if parvalues["ISNOWSRC"] == 0 else False

        if self.use_observed_snow_depth:
            self.states = self.StateVariables(kiosk, SNOWDEPTH=0.)
        else:
            self.snowcover = SnowMAUS(day, kiosk, parvalues)

    def calc_rates(self, day, drv):
        self.waterbalance.calc_rates(day, drv)
        if self.use_observed_snow_depth:
            self._SNOWDEPTH = drv.SNOWDEPTH
        else:
            self.snowcover.calc_rates(day, drv)

    @prepare_states
    def integrate(self, day, delt=1.0):
        self.waterbalance.integrate(day, delt)
        if self.use_observed_snow_depth:
            self.states.SNOWDEPTH = self._SNOWDEPTH
        else:
            self.snowcover.integrate(day, delt)
