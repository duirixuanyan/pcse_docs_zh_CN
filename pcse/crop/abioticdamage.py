# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""
用于作物非生物损伤建模的组件。

可用组件如下：
* 冻害：
  - FROSTOL：采用LT50模型估算叶片和作物死亡率
  - CERES_WinterKill：采用硬化指数估算叶片和作物死亡率
"""

#!/usr/bin/env python
import os
from math import exp

from ..traitlets import Float, Int, Instance, Enum, Bool
from ..decorators import prepare_rates, prepare_states

from ..util import limit, merge_dict
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject, VariableKiosk
from .. import signals
from .. import exceptions as exc

class CrownTemperature(SimulationObject):
    """用于估算积雪下冠部温度（地表以下2cm）的简单算法实现。

    该算法基于一个简单的经验公式，根据日最小或最大温度和相对积雪深度（RSD）
    估算日最小、最大和平均冠部温度：

    :math:`RSD = min(15, SD)/15`

    以及

    :math:`T^{crown}_{min} = T_{min} * (A + B(1 - RSD)^{2})`

    和

    :math:`T^{crown}_{max} = T_{max} * (A + B(1 - RSD)^{2})`

    以及

    :math:`T^{crown}_{avg} = (T^{crown}_{max} + T^{crown}_{min})/2`

    当积雪为零时，冠部温度接近气温。积雪的增加起到缓冲作用，削弱低气温对冠部温度的影响。
    积雪深度的最大值限定为15cm。A和B的典型值分别为0.2和0.5。

    注意，仅当drv.TMIN<0时才估算冠部温度，否则返回TMIN、TMAX和日均温（TEMP）。

    :param day: 初始化模型的日期
    :param kiosk: 本实例的VariableKiosk
    :param parvalues: `ParameterProvider`对象，提供参数的键/值对
    :returns: 包含最低、最高和每日平均冠部温度的元组。

    *模拟参数*

    ========= ============================================== =======  ==========
     名称      描述                                          类型     单位
    ========= ============================================== =======  ==========
    ISNOWSRC  使用来自驱动变量(0)的规定积雪深度，            SSi      -
              或通过kiosk获取模拟积雪深度(1)
    CROWNTMPA 冠部温度计算公式中的A参数                      SSi      -
    CROWNTMPB 冠部温度计算公式中的B参数                      SSi      -
    ========= ============================================== =======  ==========

    *速率变量*

    ========== =============================================== =======  ==========
     名称       描述                                           Pbl      单位
    ========== =============================================== =======  ==========
    TEMP_CROWN  每日平均冠部温度                               N        |C|
    TMIN_CROWN  每日最低冠部温度                               N        |C|
    TMAX_CROWN  每日最高冠部温度                               N        |C|
    ========== =============================================== =======  ==========

    注意，所计算的冠部温度并非真正意义上的速率变量，因为它们不涉及变化速率。
    实际上，它们属于“派生驱动变量”。然而，为计算冻害，它们应在速率计算阶段可用，
    并作为速率变量处理，因此可以通过`get_variable()`调用获取，并在配置文件的
    OUTPUT_VARS列表中定义。

    *外部依赖关系:*

    ============ =============================== ========================== =====
     名称         描述                             提供方                    单位
    ============ =============================== ========================== =====
    SNOWDEPTH    积雪深度。                        由驱动变量直接提供，      |cm|
                                                   或由雪盖模块模拟并
                                                   从kiosk获取
    ============ =============================== ========================== =====
    """
    # 此设置仅在运行FROSTOL单元测试时使用。
    # 对于单元测试，FROSTOL不应依赖于CrownTemperature模型，
    # 而应直接使用规定的冠部温度。
    _testing_ = Bool(False)

    class Parameters(ParamTemplate):
        CROWNTMPA = Float()
        CROWNTMPB = Float()
        ISNOWSRC  = Float()

    class RateVariables(RatesTemplate):
        TEMP_CROWN = Float()
        TMIN_CROWN = Float()
        TMAX_CROWN = Float()

    def initialize(self, day, kiosk, parvalues, testing=False):
        self.kiosk = kiosk
        self._testing_ = testing
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(self.kiosk, publish=["TEMP_CROWN", "TMIN_CROWN", "TMAX_CROWN"])

    @prepare_rates
    def __call__(self, day, drv):

        p = self.params
        r = self.rates

        # 如果是单元测试，则直接返回规定的冠部温度
        if self._testing_:
            r.TMIN_CROWN = 0.
            r.TMAX_CROWN = 10.
            r.TEMP_CROWN = drv.TEMP_CROWN
            return

        # 根据ISNOWSRC从驱动变量或kiosk获取积雪深度，并限制最大为15cm
        if p.ISNOWSRC == 0:
            SD = drv.SNOWDEPTH
        else:
            SD = self.kiosk["SNOWDEPTH"]
        RSD = limit(0., 15., SD)/15.

        if drv.TMIN < 0:
            r.TMIN_CROWN = drv.TMIN*(p.CROWNTMPA + p.CROWNTMPB*(1. - RSD)**2)
            r.TMAX_CROWN = drv.TMAX*(p.CROWNTMPA + p.CROWNTMPB*(1. - RSD)**2)
            r.TEMP_CROWN = (r.TMIN_CROWN + r.TMAX_CROWN)/2.
        else:
            r.TMIN_CROWN = drv.TMIN
            r.TMAX_CROWN = drv.TMAX
            r.TEMP_CROWN = drv.TEMP


class CrownTemperatureJRC(SimulationObject):
    """JRC版实现：用于估算在积雪覆盖下（地下2cm）冠部温度的简单算法。

    基于一个简单的经验方程，按照每日最小/最大气温和积雪深度（cm）估算每日
    最小、最大和平均冠部温度：

    :math:`SD = min(15, SD)`

    以及

    :math:`T^{crown}_{min} = 2.0 + T_{min} * (A + B(SD - 15)^{2})`

    以及

    :math:`T^{crown}_{max} = 2.0 + T_{max} * (A + B(SD - 15)^{2})`

    以及

    :math:`T^{crown}_{avg} = (T^{crown}_{max} + T^{crown}_{min})/2`

    当无积雪时，冠部温度接近空气温度。增加积雪深度能起到缓冲作用，减缓低温对冠部温度的影响。
    积雪深度最大限制为15cm。A和B的典型值为0.4和0.0018。

    注意，仅当drv.TMIN<0时才估算冠部温度，否则返回当日的TMIN、TMAX和平均气温TEMP。

    :param day: 初始化模型的日期
    :param kiosk: 此实例使用的VariableKiosk
    :param parvalues: `ParameterProvider`对象，以键/值对提供参数
    :returns: 包含最小、最大和每日平均冠部温度的元组

    *模拟参数*

    ============ ============================================== =======  ==========
     名称         描述                                          类型     单位
    ============ ============================================== =======  ==========
    ISNOWSRC     使用驱动变量中规定的积雪深度(0)，              SSi      -
                 或通过kiosk获取模拟的积雪深度(1)
    JRCCROWNTMPA 冠部温度计算公式中的A参数                       SSi      -
    JRCCROWNTMPB 冠部温度计算公式中的B参数                       SSi      -
    ============ ============================================== =======  ==========

    *速率变量*

    ========== =============================================== =======  ==========
     名称        描述                                           Pbl     单位
    ========== =============================================== =======  ==========
    TEMP_CROWN  每日平均冠部温度                                 N       |C|
    TMIN_CROWN  每日最低冠部温度                                 N       |C|
    TMAX_CROWN  每日最高冠部温度                                 N       |C|
    ========== =============================================== =======  ==========

    注意，计算得到的冠部温度并不是真正的速率变量，因为它们不涉及变化率。
    实际上属于“派生驱动变量”。为计算冻害，它们需要在速率计算阶段可用，
    并作为速率变量处理，这样可通过`get_variable()`访问，也可在配置文件的OUTPUT_VARS列表中定义。

    *外部依赖关系:*

    ============ =============================== ========================== =====
     名称         描述                             提供方                    单位
    ============ =============================== ========================== =====
    SNOWDEPTH    积雪深度。                        由驱动变量直接提供，      |cm|
                                                   或由雪盖模块模拟并
                                                   从kiosk获取
    ============ =============================== ========================== =====
    """
    # 此设置仅用于FROSTOL的单元测试过程中。
    # 对于单元测试，FROSTOL不应依赖CrownTemperature模型，
    # 而应直接使用规定的冠部温度。
    _testing_ = Bool(False)

    class Parameters(ParamTemplate):
        JRCCROWNTMPA = Float()
        JRCCROWNTMPB = Float()
        ISNOWSRC = Float()

    class RateVariables(RatesTemplate):
        TEMP_CROWN = Float()
        TMIN_CROWN = Float()
        TMAX_CROWN = Float()

    def initialize(self, day, kiosk, parvalues, testing=False):
        self.kiosk = kiosk
        self._testing_ = testing
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(self.kiosk, publish=["TEMP_CROWN", "TMIN_CROWN", "TMAX_CROWN"])

    @prepare_rates
    def __call__(self, day, drv):

        p = self.params
        r = self.rates

        # 如果是单元测试，则直接返回规定的冠部温度
        if self._testing_:
            r.TMIN_CROWN = 0.
            r.TMAX_CROWN = 10.
            r.TEMP_CROWN = drv.TEMP_CROWN
            return

        # 根据ISNOWSRC参数，从驱动变量或kiosk获取积雪深度，并将其限制在15厘米以内
        if p.ISNOWSRC == 0:
            SD = drv.SNOWDEPTH
        else:
            SD = self.kiosk["SNOWDEPTH"]
        SD = limit(0., 15., SD)

        # 如果最低温度小于零，根据公式计算冠部温度，否则直接使用驱动变量中的温度
        if drv.TMIN < 0:
            r.TMIN_CROWN = 2.0 + drv.TMIN * (p.JRCCROWNTMPA + p.JRCCROWNTMPB * (SD - 15.) ** 2)
            r.TMAX_CROWN = 2.0 + drv.TMAX * (p.JRCCROWNTMPA + p.JRCCROWNTMPB * (SD - 15.) ** 2)
            r.TEMP_CROWN = (r.TMIN_CROWN + r.TMAX_CROWN) / 2.
        else:
            r.TMIN_CROWN = drv.TMIN
            r.TMAX_CROWN = drv.TMAX
            r.TEMP_CROWN = drv.TEMP


class FROSTOL(SimulationObject):
    """
    FROSTOL模型在冬小麦冻害模拟中的实现。

    :param day: 仿真开始日期
    :param kiosk: 本PCSE实例的变量kiosk
    :param parvalues: `ParameterProvider`对象，以键值对形式提供参数

    *仿真参数*

    ============== ===================================================== =======  ============
     名称          描述                                                  类型     单位
    ============== ===================================================== =======  ============
    IDSL           表型发育选项开关，温度(IDSL=0)，包括日长(IDSL=1)，      SCr      -
                   包括春化(IDSL>=2)。FROSTOL要求IDSL>=2
    LT50C          临界LT50，定义为小麦品种可获得的最低LT50值             SCr     |C|
    FROSTOL_H      硬化系数                                               SCr     |C-1day-1| 
    FROSTOL_D      脱硬系数                                               SCr     |C-3day-1|
    FROSTOL_S      低温胁迫系数                                           SCr     |C-1day-1|
    FROSTOL_R      呼吸胁迫系数                                           SCr     |day-1|
    FROSTOL_SDBASE 呼吸胁迫的最小积雪深度                                 SCr      cm
    FROSTOL_SDMAX  呼吸胁迫的最大积雪深度，超过此值不再增加               SCr      cm
                   胁迫
    FROSTOL_KILLCF 伤害函数的陡峭系数                                     SCr     -
    ISNOWSRC       使用驱动变量规定的积雪深度(0)或kiosk模拟的积雪(1)      SSi     -
    ============== ===================================================== =======  ============

    *状态变量*

    =======  ======================================================= ==== ============
     名称     描述                                                   Pbl      单位
    =======  ======================================================= ==== ============
     LT50T    当前LT50值                                             N    |C|
     LT50I    未硬化作物的初始LT50                                   N    |C|
     IDFST    发生冻害的天数累计                                     N     -
    =======  ======================================================= ==== ============

    *速率变量*

    ========== ===================================================== ==== ============
     名称       描述                                                 Pbl      单位
    ========== ===================================================== ==== ============
    RH         硬化速率                                              N    |C day-1|
    RDH_TEMP   由于温度导致的脱硬速率                                 N    |C day-1|
    RDH_RESP   由于呼吸胁迫导致的脱硬速率                             N    |C day-1|
    RDH_TSTR   由于温度应激导致的脱硬速率                             N    |C day-1|
    IDFS       冻害（1为有，0为无）。冻害定义为RF_FROST > 0           N    -
    RF_FROST   叶片生物量的冻害减少因子，随最小冠部温度                Y    -
               和LT50T改变，取值范围0（无伤害）到1（完全死亡）。
    RF_FROST_T 整个生育期内的累计冻害（每天累乘RF_FROST，              N    -
               0为无伤害，1为完全死亡）
    ========== ===================================================== ==== ============

    *外部依赖关系:*

    ============ =============================== ========================== =====
     名称        描述                               提供方                    单位
    ============ =============================== ========================== =====
    TEMP_CROWN   每日平均冠部温度                  CrownTemperature           |C|
                 由crown_temperature模块计算获取
    TMIN_CROWN   每日最低冠部温度                  CrownTemperature           |C|
                 由crown_temperature模块计算获取
    ISVERNALISED 春化状态布尔值，反映作物         Vernalisation与            -
                 是否春化                         DVS_Phenology模块配合
    ============ =============================== ========================== =====

    参考文献： Anne Kari Bergjord, Helge Bonesmo, Arne Oddvar Skjelvag, 2008.
    《Modelling the course of frost tolerance in winter wheat: I. Model development》
    载于 European Journal of Agronomy, Volume 28, Issue 3, April 2008, Pages 321-330.

    http://dx.doi.org/10.1016/j.eja.2007.10.002
    """

    # 受冻害影响后剩余作物分数的辅助变量
    _CROP_FRACTION_REMAINING = Float(1.0)

    class Parameters(ParamTemplate):
        IDSL      = Float(-99.)
        LT50C     = Float(-99.)
        FROSTOL_H = Float(-99.)
        FROSTOL_D = Float(-99.)
        FROSTOL_S = Float(-99.)
        FROSTOL_R = Float(-99.)
        FROSTOL_SDBASE = Float(-99.)
        FROSTOL_SDMAX  = Float(-99.)
        FROSTOL_KILLCF = Float(-99)
        ISNOWSRC = Float(-99)

    class RateVariables(RatesTemplate):
        RH       = Float(-99.)
        RDH_TEMP = Float(-99.)
        RDH_RESP = Float(-99.)
        RDH_TSTR = Float(-99.)
        IDFS     = Int(-99)
        RF_FROST = Float(-99.)

    class StateVariables(StatesTemplate):
        LT50T = Float(-99.)
        LT50I = Float(-99.)
        IDFST = Int(-99)
        RF_FROST_T = Float(-99)

    #---------------------------------------------------------------------------
    def initialize(self, day, kiosk, parvalues, testing=False):

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish="RF_FROST")
        self.kiosk = kiosk

        # 定义初始状态
        LT50I = -0.6 + 0.142 * self.params.LT50C
        self.states = self.StateVariables(kiosk, LT50T=LT50I, LT50I=LT50I,
                                          IDFST=0, RF_FROST_T=0.)

        # 检查春化状态
        if self.params.IDSL < 2:
            msg = ("FROSTOL needs vernalization to be enabled in the " +
                   "phenology module (IDSL=2).")
            self.logger.error(msg)
            raise exc.ParameterError(msg)

    #---------------------------------------------------------------------------
    @prepare_rates
    def calc_rates(self, day, drv):

        r = self.rates
        p = self.params
        s = self.states
        k = self.kiosk

        # 春化状态
        isVernalized = self.kiosk["ISVERNALISED"]

        # p.ISNOWSRC=0 时从驱动变量 `drv` 获取积雪深度
        # 否则假设积雪深度为已发布的状态变量
        if p.ISNOWSRC == 0:
            snow_depth = drv.SNOWDEPTH
        else:
            snow_depth = self.kiosk["SNOWDEPTH"]

        # 硬化作用
        if (not isVernalized) and (k.TEMP_CROWN < 10.):
            xTC = limit(0., 10., k.TEMP_CROWN)
            r.RH = p.FROSTOL_H * (10. - xTC)*(s.LT50T - p.LT50C)
        else:
            r.RH = 0.

        # 解除硬化
        TCcrit = (10. if (not isVernalized) else -4.)
        if k.TEMP_CROWN > TCcrit:
            r.RDH_TEMP = p.FROSTOL_D * (s.LT50I - s.LT50T) * \
                         (k.TEMP_CROWN + 4)**3
        else:
            r.RDH_TEMP = 0.

        # 积雪覆盖下的呼吸胁迫
        xTC = (k.TEMP_CROWN if k.TEMP_CROWN > -2.5 else -2.5)
        Resp = (exp(0.84 + 0.051*xTC)-2.)/1.85

        Fsnow = (snow_depth - p.FROSTOL_SDBASE)/(p.FROSTOL_SDMAX - p.FROSTOL_SDBASE)
        Fsnow = limit(0., 1., Fsnow)
        r.RDH_RESP = p.FROSTOL_R * Resp * Fsnow

        # 低温引起的胁迫
        r.RDH_TSTR = (s.LT50T - k.TEMP_CROWN) * \
                      1./exp(-p.FROSTOL_S * (s.LT50T - k.TEMP_CROWN) - 3.74)

        # 使用Logistic函数计算杀伤因子。由于Logistic函数的定义域为-∞到+∞，因此需要设置一些限制。
        # 在这里，当killfactor < 0.05时视为无杀伤，killfactor > 0.95时视为完全杀伤。
        if k.TMIN_CROWN < 0.:
            killfactor = 1/(1 + exp((k.TMIN_CROWN - s.LT50T)/p.FROSTOL_KILLCF))
            if killfactor < 0.05:
                killfactor = 0.
            elif killfactor > 0.95:
                killfactor = 1.
        else:
            killfactor = 0.

        # 是否发生冻害胁迫
        r.IDFS = 1 if (killfactor > 0.) else 0

        # 叶生物量的减少因子
        r.RF_FROST = killfactor

        # 留存作物的剩余分数
        self._CROP_FRACTION_REMAINING *= (1. - killfactor)

    #---------------------------------------------------------------------------
    @prepare_states
    def integrate(self, day, delt=1.0):
        states = self.states
        rates  = self.rates
        params = self.params

        # 更新硬化状态
        LT50T = states.LT50T
        LT50T -= rates.RH
        LT50T += (rates.RDH_TEMP + rates.RDH_RESP + rates.RDH_TSTR)
        states.LT50T = limit(params.LT50C, states.LT50I, LT50T)

        # 累计冻害天数
        states.IDFST += rates.IDFS

        # 总冻害累计杀伤，计算方式为 1 减去剩余活作物分数
        states.RF_FROST_T = 1. - self._CROP_FRACTION_REMAINING


class CERES_WinterKill(SimulationObject):
    """
    CERES-wheat模型（CWWK）冻害模块的实现

    :param day: 模拟开始日期
    :param kiosk: 本PCSE实例的变量kiosk
    :param parvalues: `ParameterProvider`对象，提供键值参数对

    *模拟参数*

    ============== ============================================= =======  ============
     名称           描述                                          类型      单位
    ============== ============================================= =======  ============
    CWWK_HC_S1      CERES第1阶段硬化系数                            SCr      TBD
    CWWK_HC_S2      CERES第2阶段硬化系数                            SCr      TBD
    CWWK_DHC        CERES去硬化系数                                 Scr      TBD
    CWWK_KILLTEMP   以HI为基准的CERES杀死温度                        Scr      |C|
    ============== ============================================= =======  ============

    *状态变量*

    =========== ================================================= ======= ======
     名称           描述                                           可发布    单位
    =========== ================================================= ======= ======
     HARDINDEX    硬化指数                                         N       -
     HIKILLTEMP   随HI变化的致死温度                               N      |C|
    =========== ================================================= ======= ======

    *速率变量*

    ============ ================================================= ======= ============
     名称         描述                                             可发布    单位
    ============ ================================================= ======= ============
    RH           硬化速率                                           N      |day-1|
    RDH          去硬化速率                                         N      |day-1|
    HIKILLFACTOR 因低温导致作物生物量损失的分数                     N      -
    ============ ================================================= ======= ============

    参考文献:
    Savdie, I., R. Whitewood, 等 (1991). Potential for winter wheat 
    production in western Canada: A CERES model winterkill risk 
    assessment. Canadian Journal of Plant Science 71: 21-30.
    """

    class Parameters(ParamTemplate):
        CWWK_HC_S1  = Float(-99.) # 第1阶段硬化系数
        CWWK_HC_S2  = Float(-99.) # 第2阶段硬化系数
        CWWK_DHC = Float(-99.)    # 去硬化系数
        CWWK_KILLTEMP = Float(-99.) # 初始致死温度

    class StateVariables(StatesTemplate):
        HARDINDEX  = Float(-99.) # 硬化指数
        HIKILLTEMP = Float(-99.) # 由硬化指数决定的致死温度

    class RateVariables(RatesTemplate):
        RH = Float(-99.)
        RDH = Float(-99.)
        HIKILLFACTOR = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish="HIKILLFACTOR")
        self.kiosk = kiosk

        # 初始化状态变量
        self.states = self.StateVariables(kiosk, HARDINDEX=0.,
                                          HIKILLTEMP=self.params.CWWK_KILLTEMP)

    @prepare_rates
    def calc_rates(self, day, drv):
        rates = self.rates
        params = self.params
        states = self.states

        # 从kiosk中获取积雪深度
        snow_depth = self.kiosk["SNOWDEPTH"]

        if states.HARDINDEX >= 1.: # 硬化指数HI在1到2之间
            if drv.TEMP_CROWN < 0.:
                # 12天硬化足以达到阶段2
                # 默认值0.083333=1/12
                rates.RH = params.CWWK_HC_S2
            else:
                rates.RH = 0.
        else:  # 硬化指数HI在0到1之间
            if (drv.TEMP_CROWN > -1.) and (drv.TEMP_CROWN < 8.):
                # 在3.5℃时硬化指数增量为0.1（最大），在-1℃和8℃时为0.06（最小）。
                # CERESWK_HC_S1的默认值为0.1
                rates.RH = params.CWWK_HC_S1 - \
                                       ((3.5 - drv.TEMP_CROWN)**2/506.)
            else:
                rates.RH = 0.

        # 去硬化过程
        if drv.TMAX_CROWN > 10:
            # 每高于10℃一度，HI减少0.02
            rates.RDH = (10 - drv.TMAX_CROWN) * params.CWWK_DHC
        else:
            rates.RDH = 0.

        # 基于当前致死温度计算杀死因子
        if drv.TMIN_CROWN < states.HIKILLTEMP:
            rates.KILLFACTOR = 1.
            # 发送作物结束信号
            self._send_signal(signals.crop_finish, day=day, finish_type="frost kill")

        elif drv.TMIN_CROWN > params.CWWK_KILLTEMP:
            rates.KILLFACTOR = 0.

        else:
            KF = (0.02 * states.HARDINDEX - 0.1) * \
                  ((drv.TMINCROWN * 0.85) + (drv.TMAX_CROWN * 0.15) + \
                   10 + (0.25 * snow_depth))
            rates.KILLFACTOR = limit(0, 0.96, KF)

    @prepare_states
    def integrate(self, day, delt=1.0):
        states = self.states
        rates  = self.rates
        params = self.params

        states.HARDINDEX += (rates.RH + rates.RDH)
        states.HIKILLTEMP = (states.HARDINDEX + 1.) * params.CWWK_KILLTEMP

