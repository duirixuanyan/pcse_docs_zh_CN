# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

from ..traitlets import Float
from ..decorators import prepare_rates, prepare_states
from ..util import limit, merge_dict
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals
from .. import exceptions as exc

class SnowMAUS(SimulationObject):
    """适用于农业气象应用的简单积雪模型。
    
    这是对SnowMAUS模型的一个实现，该模型描述了降水、融雪和升华导致的积雪的积累和消融。SnowMAUS模型旨在跟踪存在为积雪的水层厚度（例如，雪水当量深度（状态变量SWEDEPTH [cm]））。将SWEDEPTH转换为实际雪深（状态变量SNOWDEPTH [cm]）的方法是将SWEDEPTH除以雪的密度[cm_water/cm_snow]。
    
    雪的密度被认为是一个固定值，尽管实际上雪的密度会因降雪类型、温度和雪层的年龄而变化。然而，对于雪密度的更复杂算法并不符合SnowMAUS模型的简洁性。
    
    当前实现的一个缺点是还没有与水分平衡建立联系。
    
    参考文献：
    M. Trnka, E. Kocmánková, J. Balek, J. Eitzinger, F. Ruget, H. Formayer,
    P. Hlavinka, A. Schaumberger, V. Horáková, M. Možný, Z. Žalud,
    简单的农业气象应用积雪模型,
    Agricultural and Forest Meteorology, 第150卷, 第7–8期, 2010年7月15日,
    第1115-1127页, ISSN 0168-1923

    http://dx.doi.org/10.1016/j.agrformet.2010.04.012

    **模拟参数:** （在作物、土壤和站点数据字典中提供）
    
    ============ =========================================== =======  ==========
     名称         描述                                        类型     单位
    ============ =========================================== =======  ==========
    TMINACCU1    积雪的上临界最低温度                          SSi      |C|
    TMINACCU2    积雪的下临界最低温度                          SSi      |C|
    TMINCRIT     融雪的临界最低温度                            SSi      |C|
    TMAXCRIT     融雪的临界最高温度                            SSi      |C|
    RMELT        高于临界最低温度时，每日每摄氏度的融化速率      SSi      |cmC-1day-1|
    SCTHRESHOLD  超过该值时考虑升华的雪水当量                   SSi      cm
    SNOWDENSITY  雪的密度                                     SSi      cm/cm
    SWEDEPTHI    初始的积雪水层厚度                            SSi      cm
    ============ =========================================== =======  ==========
      
    **状态变量:**

    =============== ========================================== ==== ============
     名称           描述                                       发布    单位
    =============== ========================================== ==== ============
    SWEDEPTH        土壤表面存在为积雪的水层厚度                  N     cm
                    （状态变量）
    SNOWDEPTH       表面积雪厚度                                 Y     cm
    =============== ========================================== ==== ============
    
    **速率变量:**

    ============ ============================================= ==== ============
     名称         描述                                         发布    单位
    ============ ============================================= ==== ============
    RSNOWACCUM   积雪的积累速率                                   N     |cmday-1|
    RSNOWSUBLIM  积雪升华速率                                     N     |cmday-1|
    RSNOWMELT    积雪融化速率                                     N     |cmday-1|
    ============ ============================================= ==== ============
    """
    
    class Parameters(ParamTemplate):
        TMINACCU1 = Float(-99.)
        TMINACCU2 = Float(-99.)
        TMINCRIT  = Float(-99.)
        TMAXCRIT  = Float(-99.)
        RMELT     = Float(-99.)
        SCTHRESHOLD = Float(-99.)
        SNOWDENSITY = Float(-99)
        SWEDEPTHI   = Float(-99)


    class StateVariables(StatesTemplate):
        SWEDEPTH = Float(-99.)
        SNOWDEPTH = Float(-99.)

    class RateVariables(RatesTemplate):
        RSNOWACCUM  = Float(-99.)
        RSNOWSUBLIM = Float(-99.)
        RSNOWMELT   = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param sitedata: 包含WOFOST场地数据键/值对的字典
        """
      
        if parvalues["SNOWDENSITY"] <= 0.:
            msg = ("SNOWDENSITY parameter of SnowMAUS module cannot <= zero " +
                   "to avoid division by zero")
            raise exc.ParameterError(msg)
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk)

        SWEDEPTH = self.params.SWEDEPTHI
        SNOWDEPTH = SWEDEPTH/self.params.SNOWDENSITY
        self.states = self.StateVariables(kiosk, SWEDEPTH=SWEDEPTH, 
                                          SNOWDEPTH=SNOWDEPTH, publish="SNOWDEPTH")

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        s = self.states
        
        # 积雪积累速率 (RSNOWACCUM)
        if drv.TMIN <= p.TMINACCU2:
            r.RSNOWACCUM = drv.RAIN
        elif drv.TMIN >= p.TMINACCU1:
            r.RSNOWACCUM = 0.
        else:
            rr = (drv.TMIN - p.TMINACCU2)/ abs(p.TMINACCU1 - p.TMINACCU2)
            r.RSNOWACCUM = (1-rr) * drv.RAIN

        # 积雪升华速率 (RSNOWSUBLIM)
        if s.SWEDEPTH > p.SCTHRESHOLD and r.RSNOWACCUM == 0.:
            RSNOWSUBLIM = drv.E0
        else:
            RSNOWSUBLIM = 0.
        # 避免升华量大于可用积雪
        r.RSNOWSUBLIM = limit(0, s.SWEDEPTH, RSNOWSUBLIM)        

        # 积雪融化速率 (RSNOWMELT)
        if drv.TMIN < p.TMINCRIT:
            RSNOWMELT = 0.
        else:
            if drv.TMIN <= 0. and drv.TMAX < p.TMAXCRIT:
                RSNOWMELT = 0.
            else:
                RSNOWMELT = (drv.TMIN - p.TMINCRIT) * p.RMELT

        # 避免融化量大于可用积雪
        r.RSNOWMELT = limit(0, (s.SWEDEPTH - r.RSNOWSUBLIM), RSNOWMELT)        

    @prepare_states
    def integrate(self, day, delt=1.0):
        s = self.states
        r = self.rates
        p = self.params
        
        s.SWEDEPTH += (r.RSNOWACCUM - r.RSNOWSUBLIM - r.RSNOWMELT)
        s.SNOWDEPTH = s.SWEDEPTH/p.SNOWDENSITY
