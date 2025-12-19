# -*- coding: utf-8 -*-
from ..base import ParamTemplate, SimulationObject
from ..base import StatesWithImplicitRatesTemplate as StateVariables
from ..decorators import prepare_rates, prepare_states
from ..traitlets import Float, Bool
from ..util import limit
from math import sqrt
from ..exceptions import WaterBalanceError

cm2mm = lambda cm: 10. * cm
m2mm = lambda x: 1000 * x

class Lintul3Soil(SimulationObject):
    """
        * 原始版权声明:
        *-------------------------------------------------------------------------*
        * Copyright 2013. Wageningen University, Plant Production Systems group,  *
        * P.O. Box 430, 6700 AK Wageningen, The Netherlands.                      *
        * You may not use this work except in compliance with the Licence.        *
        * You may obtain a copy of the Licence at:                                *
        *                                                                         *
        * http://models.pps.wur.nl/content/licence-agreement                      *
        *                                                                         *
        * Unless required by applicable law or agreed to in writing, software     *
        * distributed under the Licence is distributed on an "AS IS" basis,       *
        * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.*
        *-------------------------------------------------------------------------*

        本模型中的水分平衡不处理稻田灌溉系统，而是保持土壤饱和，使作物不会经历水分胁迫。土壤水分平衡按单层土壤计算，其厚度随根向下生长而增加。模型不模拟根的伸长，只考虑平均根系深度增加。根的伸长不受土壤干燥度影响直至萎蔫点的假设最早来源于 LINTUL1（Spitters, 1990）。在水稻情境下，土壤为饱和状态，萎蔫点不太会出现。作物的水分和养分吸收仅限于有根区土层。通过根系向下生长补充的水分依据根的伸长速率和（饱和）含水量计算（Spitters and Schapendonk, 1990；Farré 等, 2000）。

        土壤中的氮供应

        供作物吸收的矿质氮（TNSOIL）来源于三方面：发芽/移栽时土壤中的氮，生长期土壤有机质的生物固定和矿化，及施用的化肥氮。在好氧条件下，土壤本底氮可较准确地根据有机质含量定量（Sinclair and Amir, 1992）。但在厌氧条件下，不同田块或季节间的矿质氮供应差异，不能通过土壤有机碳、全氮或初始无机态氮解释（Cassman et al., 1996；Bouman et al., 2001）。因此本底氮输入作为地点特异的外源参数引入，而不是模拟氮矿化。Ten Berge 等（1997）在热带土壤中发现本底氮供应范围为0.5–0.9 kg ha-1 d-1。可吸收的化肥氮（考虑挥发、反硝化、淋失）在模型中按变量因子表示，称为氮回收率NRF。稻田体系中的低回收率（30–39%，Cassman et al., 1996）主要由挥发损失导致。任何形式的无机氮（NH4+或NO3-）如果未被作物吸收，就有可能以挥发、反硝化或淋失方式流失。在淹水条件下，平均氮回收率每日变化不大。模型所用变量NRF表示施用化肥的净回收率，该值取决于土壤类型、作物生育阶段、肥料种类，以及施肥时期和方式（De Datta, 1986），需通过标定确定。

        参见：Farré, I., Van Oijen, M., Leffelaar, P.A., Faci, J.M., 2000. 分析西班牙东北部不同灌溉策略下玉米生长。Eur. J. Agron. 12, 225–238.
            doi:10.1016/S1161-0301(00)00051-4

        *参数*

        ======== =============================================== =======  ==========
        名称       描述                                            类型     单位
        ======== =============================================== =======  ==========
        DRATE    土壤最大排水速率                                         mm/day
        IRRIGF   灌溉开关                                                 (布尔值)
        WCAD     风干含水量                                               m³/m³
        WCFC     田间持水量 (0.03 MPa)                                    m³/m³
        WCST     完全饱和含水量                                           m³/m³
        WCSUBS   底土含水量 (?)                                           m³/m³
        WCWP     凋萎点含水量 (1.5 MPa)                                   m³/m³
        WMFAC    水分管理 (False = 灌溉至田间持水量，                     (布尔值)
                true = 灌溉至完全饱和)
        ROOTDI   初始根深                                                 m
        WCI      土壤初始含水量                                           m³/m³
        ======== =============================================== =======  ==========

        **状态变量:**

        =========== ================================================= ======== ===============
        名称         描述                                            是否输出    单位
        =========== ================================================= ======== ===============
        WA          土壤水分总量                                       *       mm
        WC          土壤体积含水量                                              -
        TRUNOF      径流累积量                                                  mm
        TTRAN       作物生长期间蒸腾累积量                                        mm
        TEVAP       作物生长期间土壤蒸发累积量                                    mm
        TDRAIN      排水累积量                                                  mm
        TRAIN       降雨累积量                                                  mm
        TEXPLO      探索累积量                                                  mm
        TIRRIG      灌溉累积量                                                  mm
        =========== ================================================= ======== ===============
    """

    class Parameters(ParamTemplate):
        DRATE   = Float(-99)    # 土壤最大排水速率 (mm/day)
        IRRIGF  = Bool()        # 灌溉开关
        WCFC    = Float(-99)    # 土壤水力参数
        WCI     = Float(-99)    # 初始含水量，单位为cm3水/(cm3土壤)
        WCST    = Float(-99)    # 土壤水力参数
        WCSUBS  = Float(-99)    # 亚土层含水量（？）
        WCAD    = Float(-99)    # 空气干燥时的含水量 m3/m3
        WCWP    = Float(-99)    # 土壤水力参数
        WMFAC   = Bool()        # 水分管理（0=灌溉至田间持水量, 1=灌溉至饱和）
        ROOTDI  = Float(-99)    # 初始根系深度 [m]

    class Lintul3SoilStates(StateVariables):
        WA      = Float(-99.)   # 土壤水分总量
        WC      = Float(-99.)   # 土壤体积含水量
        TRUNOF  = Float(-99.)   # 径流累计量
        TTRAN   = Float(-99.)   # 生长季作物蒸腾累计量
        TEVAP   = Float(-99.)   # 生长季土壤蒸发累计量
        TDRAIN  = Float(-99.)   # 累计排水量
        TRAIN   = Float(-99.)   # 降水累计量
        TEXPLO  = Float(-99.)   # 探索（土壤增长）累计量
        TIRRIG  = Float(-99.)   # 灌溉累计量

    # 自上次下雨以来的天数计数器
    DSLR  = 0
    # 上层（根域层）初始水量
    WAI = 0.

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 仿真开始日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider` 对象，以键值对形式提供参数
        """
        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)

        init = self.Lintul3SoilStates.initialValues()

        # 按初始含水量（mm）计算根系深度内初始水量。
        self.WAI = m2mm(self.params.ROOTDI) * self.params.WCI
        init["WA"] = self.WAI
        
        # 初始化状态变量
        self.states = self.Lintul3SoilStates(kiosk, publish=["WA", "WC"], **init)
        self.states.initialize_rates()

    def _safe_get_from_kiosk(self, varname, default=0.0):
        """
        从kiosk中获取变量值，如果不可用则返回默认值
        :param varname:    变量名
        :param default:    若kiosk无该变量则返回该值（可选，默认0.）
        """
        if varname in self.kiosk:
            return self.kiosk[varname]
        return default

    @prepare_rates
    def calc_rates(self, day, drv):

        # 动态计算
        p = self.params
        s = self.states

        DELT = 1.  # 时间步长

        ROOTD = self._safe_get_from_kiosk("ROOTD", p.ROOTDI)
        RROOTD = self._safe_get_from_kiosk("RROOTD")
        PEVAP = self._safe_get_from_kiosk("PEVAP", cm2mm(drv.ES0))
        TRAN = self._safe_get_from_kiosk("TRAN")
        
        # 天气系统提供的变量
        RAIN = cm2mm(drv.RAIN)  # cm  --> mm，WOFOST-WEATHER中非标准cm的修正

        # 土壤蒸发速率
        EVAP = self._soil_evaporation(RAIN, PEVAP, ROOTD, DELT)
        
        # 计算排水、径流和灌溉的子程序
        DRAIN, RUNOFF, IRRIG = self._drainage_runoff_irrigation(RAIN, EVAP, TRAN, DELT, s.WA, ROOTD)

        # 当根系向下生长时，土壤中被探索的水分量
        EXPLOR = m2mm(RROOTD) * p.WCSUBS
                
        RWA = (RAIN + EXPLOR + IRRIG)-(RUNOFF + TRAN + EVAP + DRAIN)

        # 给相关状态分配速率变量
        s.rWA = RWA
        s.rTEXPLO = EXPLOR
        s.rTEVAP = EVAP
        s.rTTRAN = TRAN
        s.rTRUNOF = RUNOFF
        s.rTIRRIG = IRRIG 
        s.rTRAIN  = RAIN  
        s.rTDRAIN = DRAIN
        
        # 水量平衡
        WATBAL = (s.WA + (s.TRUNOF + s.TTRAN + s.TEVAP + s.TDRAIN)
                       - (self.WAI + s.TRAIN + s.TEXPLO + s.TIRRIG))

        if abs(WATBAL) > 0.0001:
            raise WaterBalanceError("water un-balance in root zone at day %s" % day)

    @prepare_states
    def integrate(self, day, delt=1.0):
        s = self.states
        p = self.params
        s.integrate(delta=1.)

        # 根区的体积含水量
        ROOTD = self._safe_get_from_kiosk("ROOTD", p.ROOTDI)
        s.WC = s.WA / m2mm(ROOTD)

    def _drainage_runoff_irrigation(self, RAIN, EVAP, TRAN, DELT, WA, ROOTD):
        """计算排水、径流和灌溉的速率
        """
        p = self.params

        WAFC = p.WCFC * m2mm(ROOTD)
        WAST = p.WCST * m2mm(ROOTD)

        DRAIN = limit(0., p.DRATE, (WA-WAFC)/DELT + (RAIN - EVAP - TRAN))
        RUNOFF = max(0., (WA-WAST)/DELT + (RAIN - EVAP - TRAN - DRAIN))
        
        if p.WMFAC:
            # 如果土壤通过漫灌灌溉：土壤含水量通过“灌溉事件”维持在饱和状态
            IRRIG = max(0., (WAST-WA)/DELT - (RAIN - EVAP - TRAN - DRAIN - RUNOFF)) if p.IRRIGF else 0.0
        else:
            # 如果土壤灌溉但未漫灌：土壤含水量通过“灌溉事件”维持在田间持水量
            IRRIG = max(0., (WAFC-WA)/DELT - (RAIN - EVAP - TRAN - DRAIN - RUNOFF)) if p.IRRIGF else 0.0
    
        return DRAIN, RUNOFF, IRRIG

    def _soil_evaporation(self, RAIN, PEVAP, ROOTD, DELT):
        """根据距离上次下雨天数（DSLR），并考虑空气干燥状态下土壤水量（WAAD），计算实际土壤蒸发速率

        :param RAIN: 降水量 [mm]
        :param PEVAP: 潜在土壤蒸发速率 [mm/d]
        :param DELT: 时间步长 [1 天]
        """
        
        p = self.params
        s = self.states
        
        # 另见 classic_water balance.py
        WAAD = p.WCAD * m2mm(ROOTD)
         
        if RAIN >= 0.5:
            EVS = PEVAP
            self.DSLR = 1.
        else:
            self.DSLR += 1.
            EVSMXT = PEVAP*(sqrt(self.DSLR) - sqrt(self.DSLR - 1.))
            EVS = min(PEVAP, EVSMXT + RAIN)
        
        # WA-WAAD 是土壤中高于空气干燥状态的、物理上可利用的水量。为避免土壤水分低于空气干燥状态，对蒸发散量进行限制
        AVAILF = min(1., (s.WA - WAAD)/(EVS * DELT)) if (EVS > 0) else 0.0
        
        return EVS * AVAILF
