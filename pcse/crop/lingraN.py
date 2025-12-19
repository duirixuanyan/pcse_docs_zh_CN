# -*- coding: utf-8 -*-
# Copyright (c) 2021 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2021
"""LINGRA-N草地模拟模型的实现

本模块实现了LINGRA-N（LINtul GRAssland）草地模拟模型，来源于 Schapendonk 等（1998年）对N限制的描述。
氮素限制的实现方式与LINTUL模型类似。
（参考文献：https://doi.org/10.1016/S1161-0301(98)00027-6）
"""
from math import exp, log

from pcse.base import SimulationObject, ParamTemplate, StatesTemplate, RatesTemplate
from pcse.traitlets import Float, List, Bool, Instance, Integer
from pcse.util import AfgenTrait, limit
from pcse.decorators import prepare_states, prepare_rates
from pcse.crop.evapotranspiration import Evapotranspiration
from pcse.crop.root_dynamics import Simple_Root_Dynamics
import pcse.signals

from .lingra_ndynamics import N_Crop_Dynamics, N_Stress


class SourceLimitedGrowth(SimulationObject):
    """根据辐射和温度等驱动变量计算草地的源限制生长速率，并可受土壤水分或叶片氮素含量的限制。
    叶片氮素的限制是基于当前和最大N浓度的静态值，主要为了将来与氮模块连接。

    该过程采用光能利用效率（LUE）方法，其中LUE会根据温度和辐射强度进行调整。
    温度的影响是因为光合作用具有明显的温度响应，辐射的影响是因为在高辐射水平下光合作用速率趋于饱和，导致表观LUE下降。
    参数 `LUEreductionRadiationTB` 是对该现象的粗略经验性修正。

    注意：因土壤水分引起的生长速率下降通过蒸腾的减弱因子（RFTRA）实现。

    该模块不提供真实的速率变量，而是通过 __call__() 直接返回计算得到的生长速率。

    *模拟参数*：

    =======================  =============================================  ==============
     名称                      说明                                             单位
    =======================  =============================================  ==============
    KDIFTB                    不同发育阶段（DVS）的散射可见光消光系数             -
    CO2A                      大气CO2浓度                                       ppm
    LUEreductionSoilTempTB    随土壤温度变化的光能利用效率修正函数               ℃, -
    LUEreductionRadiationTB   随辐射强度变化的光能利用效率修正函数               MJ, -
    LUEmax                    最大光能利用效率                                   -
    =======================  =============================================  ==============


    *速率变量*：

    ===================  =============================================  ===============
     名称                 说明                                             单位
    ===================  =============================================  ===============
    RF_RadiationLevel     受辐射强度影响的光能利用效率修正因子                -
    RF_RadiationLevel     受辐射强度影响的光能利用效率修正因子                -
    LUEact                实际光能利用效率                                  g /(MJ PAR)
    ===================  =============================================  ===============

    *信号发送与处理*

    无

    *外部依赖关系*：

    ===============  ==================================== ==============================
     名称             说明                                  所属模块
    ===============  ==================================== ==============================
    DVS              作物发育阶段                          pylingra.LINGRA
    TemperatureSoil  土壤温度                              pylingra.SoilTemperature
    RFTRA            受水分胁迫影响的光能利用效率修正因子  pcse.crop.Evapotranspiration
    RFNUTR           受养分胁迫影响的光能利用效率修正因子  pylingra.Nstress
    ===============  ==================================== ==============================
    """

    class Parameters(ParamTemplate):
        KDIFTB = AfgenTrait()
        LUEreductionSoilTempTB = AfgenTrait()
        LUEreductionRadiationTB = AfgenTrait()
        CO2A = Float()
        LUEmax = Float()

    class RateVariables(RatesTemplate):
        RF_Temperature = Float()
        RF_RadiationLevel = Float()
        LUEact = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(self.kiosk, publish=["RF_Temperature"])

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # 从 J/m2/d 转换为 MJ/m2/d
        DTR = drv.IRRAD / 1.E+6
        PAR = DTR * 0.50

        # 温度和辐射水平对光合作用抑制因子
        r.RF_Temperature = p.LUEreductionSoilTempTB(k.TemperatureSoil)
        r.RF_RadiationLevel = p.LUEreductionRadiationTB(DTR)

        # 光拦截分数
        FINT = (1.-exp(-p.KDIFTB(k.DVS) * k.LAI))

        # 总的被拦截的光合有效辐射，单位：MJ m-2 d-1
        PARINT = FINT * PAR

        # 校正温度和辐射水平后的最大光能利用率，单位：g MJ PAR-1
        LUEpot = p.LUEmax * r.RF_Temperature * r.RF_RadiationLevel

        # 校正水分或营养胁迫后的光能利用率
        # RFNUTR = (0.336 + 0.224 * p.NamountLV) / (0.336 + 0.224 * p.NmaxLV)
        r.LUEact = LUEpot * min(k.RFNUTR, k.RFTRA)

        if k.dWeightHARV == 0.:  # 今日没有收割牧草，正常生长
            # （10：从 g m-2 d-1 到 kg ha-1 d-1 的单位换算）
            GrowthSource = r.LUEact * PARINT * (1. + 0.8 * log(p.CO2A / 360.)) * 10.
        else:
            # 收割当天生长为零
            GrowthSource = 0.

        return GrowthSource


class SinkLimitedGrowth(SimulationObject):
    """计算牧草源受限（Sink-limited）生长速率，假定最大叶片伸长速率由温度驱动，并乘以分蘖数。通过比上比叶面积（SLA），将其转换为单位干重的生长（kg/ha）。

    除了源受限生长速率外，此类还根据生长、死亡及收割后去叶天数计算分蘖数的变化。

    *模拟参数*：

    =======================  =============================================  ==============
     名称                        说明                                            单位
    =======================  =============================================  ==============
    TempBase                  叶发育和牧草物候的基温                            C
    LAICrit                   超出该阈值后因自遮荫产生叶死亡的临界叶面积          -
    SiteFillingMax            新芽最大占位数                                 tiller/leaf-1
    SLA                       比叶面积                                         ha/kg
    TSUMmax                   最大发育阶段对应的温度积算                        C.d
    TillerFormRateA0          收割后7天内有效的分蘖形成率方程A参数
    TillerFormRateB0          收割后7天内有效的分蘖形成率方程B参数
    TillerFormRateA8          收割后第8天及之后有效的分蘖形成率方程A参数
    TillerFormRateB8          收割后第8天及之后有效的分蘖形成率方程B参数
    =======================  =============================================  ==============

    *速率变量*：

    ===================  =============================================  ===============
     名称                 说明                                             单位
    ===================  =============================================  ===============
    dTillerNumber         由辐射水平引起的分蘖数变化（tillers/m2/d）
    dLeafLengthPot        潜在叶片增长量（cm/d），                       
                          稍后将根据源限制计算实际变化量
    LAIGrowthSink         基于源受限生长速率的叶面积指数增长（d-1）
    ===================  =============================================  ===============

    *信号发送或处理*

    无

    *外部依赖关系*：

    ===============  =================================== ==============================
     名称             说明                                  所属模块
    ===============  =================================== ==============================
    DVS               作物发育阶段                            pylingra.LINGRA
    LAI               叶面积指数                              pylingra.LINGRA
    TemperatureSoil   土壤温度                                pylingra.SoilTemperature
    RF_Temperature    基于温度的LUE修正因子                    pylingra.SourceLimitedGrowth
    TillerNumber      实际分蘖数                                pylingra.LINGRA
    LVfraction        分配给叶的同化物分数                      pylingra.LINGRA
    dWeightHARV       当天收割标志（收割则变化）                pylingra.LINGRA
    ===============  =================================== ==============================
    """

    class Parameters(ParamTemplate):
        TempBase = Float()
        LAIcrit = Float()
        SiteFillingMax = Float()
        SLA = Float()
        TillerFormRateA0 = Float()
        TillerFormRateB0 = Float()
        TillerFormRateA8 = Float()
        TillerFormRateB8 = Float()
        TSUMmax = Float()

    class RateVariables(RatesTemplate):
        dTillerNumber = Float()
        dLeafLengthPot = Float()
        LAIGrowthSink = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["dTillerNumber", "dLeafLengthPot"])

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # 叶片出现速率受温度影响，依据（Davies 和 Thomas, 1983），土壤温度（TemperatureSoil）被用作驱动力，
        # 土壤温度由10天滑动平均得到
        LeafAppRate = k.TemperatureSoil * 0.01 if k.RF_Temperature > 0. else 0.
        # 计算分蘖速率
        r.dTillerNumber = self._calc_tillering_rate(LeafAppRate)

        # 叶片伸长速率受温度影响：厘米/天/分蘖
        r.dLeafLengthPot = 0.83 * log(max(drv.TEMP, 2.)) - 0.8924 if (drv.TEMP - p.TempBase) > 0. else 0.

        # 源限制下的叶片生长速率，TillerNumber 单位为 tillers m-2
        # 1.0E-8 用于将 cm-2 转换为 ha-1, 即单位为 ha 叶/ha 地/天
        r.LAIgrowthSink = (k.TillerNumber * 1.0E4 * (r.dLeafLengthPot * 0.3)) * 1.0E-8
        # 通过比叶面积（SLA）将叶生长速率转换为总的源限制碳需求，单位为 kg 叶 ha-1 d-1
        GrowthSink = r.LAIgrowthSink * (1./p.SLA) * (1./k.LVfraction) if k.dWeightHARV <= 0. else 0.

        return GrowthSink

    def _calc_tillering_rate(self, LeafAppRate):
        k = self.kiosk
        p = self.params
        # 最大分蘖新芽位点填充数会随氮含量降低而减少，参考 Van Loo 和 Schapendonk (1992)
        # 理论最大分蘖能力为 0.693
        SiteFillingAct = k.NNI * p.SiteFillingMax

        if k.DaysAfterHarvest < 8.:
            # 距离上次去叶不足8天时的相对分蘖形成速率，单位 tiller tiller-1 d-1
            TillerFormationRate = max(0., p.TillerFormRateA0 - p.TillerFormRateB0 * k.LAI) * k.RF_Temperature
        else:
            # 距离上次去叶超过8天时的相对分蘖形成速率，单位 tiller tiller-1 d-1
            TillerFormationRate = limit(0., SiteFillingAct, p.TillerFormRateA8 - p.TillerFormRateB8 * k.LAI) * k.RF_Temperature

        # 由于自身遮荫造成的分蘖死亡率（DTILD），单位 tiller tiller-1 d-1
        TillerDeathRate = max(0.01 * (1. + k.TSUM / p.TSUMmax), 0.05 * (k.LAI - p.LAIcrit) / p.LAIcrit)

        # 分蘖数的变化
        if k.TillerNumber <= 14000.:
            dTillerNumber = (TillerFormationRate - TillerDeathRate) * LeafAppRate * k.TillerNumber
        else:
            dTillerNumber = -TillerDeathRate * LeafAppRate * k.TillerNumber

        return dTillerNumber


class SoilTemperature(SimulationObject):
    """计算上层10厘米土壤温度，采用2米日均气温的10天滑动平均。

    *仿真参数*:

    =======================  =============================================  ==============
     名称                        描述                                            单位
    =======================  =============================================  ==============
    SoilTemperatureInit       初始土壤温度                                      ℃
    =======================  =============================================  ==============


    *速率变量（Rate variables）*

    ===================  =============================================  ===============
     名称                  描述                                            单位
    ===================  =============================================  ===============
    dTemperatureSoil      土壤温度变化                                      ℃/天
    ===================  =============================================  ===============

    *状态变量（State variables）*

    ===================  =============================================  ===============
     名称                  描述                                            单位
    ===================  =============================================  ===============
    TemperatureSoil       实际土壤温度                                      ℃
    ===================  =============================================  ===============

    *发送或处理的信号*

    无

    *外部依赖:*

    无
    """

    class Parameters(ParamTemplate):
        TemperatureSoilinit = Float()

    class StateVariables(StatesTemplate):
        TemperatureSoil = Float()

    class RateVariables(RatesTemplate):
        dTemperatureSoil = Float()

    def initialize(self, day, kiosk, parvalues):
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.states = self.StateVariables(kiosk, TemperatureSoil=self.params.TemperatureSoilinit,
                                          publish=["TemperatureSoil"])

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states

        # 土壤温度变化
        r.dTemperatureSoil = (drv.TEMP - s.TemperatureSoil) / 10.

    @prepare_states
    def integrate(self, day, delt=1.0):
        self.states.TemperatureSoil += self.rates.dTemperatureSoil * delt


class LINGRA_N(SimulationObject):
    """LINGRA-N 顶层实现，集成所有组件

    本类集成了 LINGRA-N 模型的所有组件，并包含了与不同生物量和氮库相关的主要状态变量（如权重），叶面积、分蘖数和叶片长度。集成的组件包括源/库限制生长、土壤温度、氮动态、蒸散发和根系动态的实现。后两者（蒸散发和根系动态）取自 WOFOST，以避免代码重复。

    与 Schapendonk 等（1998）年的原始代码相比，做了如下优化：

    - 对代码整体重构，去除了不必要的变量，并为保留变量提供了更易懂的名称。
    - 更清晰地实现了源/库限制的生长，包括储备库的使用。
    - 通过实际生长对 Sink-limited growth（库限制生长）模块计算的潜在叶片伸长速率进行修正，避免了水分胁迫条件下叶片生长无限制，这会导致不现实的结果。

    *模拟参数*：

    =======================  =============================================  ==============
     名称                      描述                                            单位
    =======================  =============================================  ==============
     LAIinit                  初始叶面积指数                                    -
     TillerNumberinit         初始分蘖数                                      tillers/m2
     WeightREinit             初始储备库的重量                                 kg/ha
     WeightRTinit             初始根重                                        kg/ha
     LAIcrit                  因自遮阴造成死亡的临界LAI                         -
     RDRbase                  根的基础相对死亡率                               d-1
     RDRShading               叶片由于自遮阴造成的最大相对死亡率                 d-1
     RDRdrought               叶片因干旱胁迫造成的最大相对死亡率                 d-1
     RDRnitrogen              叶片因氮胁迫造成的最大相对死亡率                   d-1
     SLA                      比叶面积                                        ha/kg
     TempBase                 光合与发育的基准温度                              C
     PartitioningRootsTB      根系分配分数作为蒸腾胁迫因子的函数（RFTRA）         -, -
     TSUMmax                  达到最大发育阶段的温度积                          C.d
    =======================  =============================================  ==============

    *变化率变量(Rate variables)*

    ===================  =============================================  ===============
     名称                 描述                                            单位
    ===================  =============================================  ===============
    dTSUM                 发育温度积的变化                                 C
    dLAI                  叶面积指数的净变化                               d-1
    dDaysAfterHarvest     收割后天数的变化                                 -
    dCuttingNumber        收割（刈割）次数的变化                           -
    dWeightLV             叶重的净变化                                     kg/ha/d
    dWeightRE             储备库的净变化                                   kg/ha/d
    dLeafLengthAct        实际叶片长度的变化                               cm/d
    LVdeath               叶片死亡速率                                     kg/ha/d
    LVgrowth              叶生长速率                                       kg/ha/d
    dWeightHARV           收获干重的变化                                   kg/ha/d
    dWeightRT             根重的净变化                                     kg/ha/d
    LVfraction            分配至叶片的比例                                 -
    RTfraction            分配至根的比例                                   -
    ===================  =============================================  ===============

    *状态变量(State variables)*

    ===================  =============================================  ===============
     名称                 描述                                            单位
    ===================  =============================================  ===============
     TSUM                 温度积                                           C d
     LAI                  叶面积指数                                       -
     DaysAfterHarvest     距上次收割的天数                                  d
     CuttingNumber        收割（刈割）次数                                   -
     TillerNumber         分蘖数                                           tillers/m2
     WeightLVgreen        绿色叶片重量                                     kg/ha
     WeightLVdead         枯叶重量                                         kg/ha
     WeightHARV           已收获干重                                       kg/ha
     WeightRE             储备库重量                                       kg/ha
     WeightRT             根重                                             kg/ha
     LeafLength           叶片长度                                         kg/ha
     WeightABG            地上总生物量（已收获+当前）                      kg/ha
     SLAINT               季节中集成的SLA                                  ha/kg
     DVS                  发育阶段                                         -
    ===================  =============================================  ===============

    *发出或处理的信号(Signals send or handled)*

    当广播 `pcse.signals.mowing` 信号时，将进行草坪收割。此操作将减少地上绿色叶片重，同时假定一定量的生物量将留在田间（此量由MOWING事件的参数提供）。

    *外部依赖(External dependencies):*

    ===============  =================================== =====================================
     名称             描述                                    提供者
    ===============  =================================== =====================================
    RFTRA             蒸腾削减因子                            pcse.crop.Evapotranspiration
    dLeafLengthPot    潜在叶片长度增长                        pcse.crop.lingra.SinkLimitedGrowth
    dTillerNumber     分蘖数变化                              pcse.crop.lingra.SinkLimitedGrowth
    NNI               氮营养指数                              pcse.crop.lingra_ndynamics.N_Stress
    ===============  =================================== =====================================
    """

    WeightLV_remaining = Float()
    _flag_MOWING = Bool(False)

    source_limited_growth = Instance(SimulationObject)
    sink_limited_growth = Instance(SimulationObject)
    soil_temperature = Instance(SimulationObject)
    evapotranspiration = Instance(SimulationObject)
    root_dynamics = Instance(SimulationObject)
    n_dynamics = Instance(SimulationObject)
    n_stress = Instance(SimulationObject)

    class Parameters(ParamTemplate):
        LAIinit = Float()
        TillerNumberinit = Float()
        WeightREinit = Float()
        WeightRTinit = Float()
        LAIcrit = Float()
        RDRbase = Float()
        SLA = Float()
        TempBase = Float()
        PartitioningRootsTB = AfgenTrait()
        TSUMmax = Float()
        NSLA = Float()
        RDRshading = Float()
        RDRdrought = Float()
        RDRnitrogen = Float()

    class RateVariables(RatesTemplate):
        dTSUM = Float()
        dLAI = Float()
        dDaysAfterHarvest = Integer()
        dCuttingNumber = Integer()
        dWeightLV = Float()
        dWeightRE = Float()
        dLeafLengthAct = Float()
        LVdeath = Float()
        LVgrowth = Float()
        dWeightHARV = Float()
        dWeightRT = Float()
        LVfraction = Float()
        RTfraction = Float()

    class StateVariables(StatesTemplate):
        TSUM = Float()
        LAI = Float()
        DaysAfterHarvest = Integer()
        CuttingNumber = Integer()
        TillerNumber = Float()
        WeightLVgreen = Float()
        WeightLVdead = Float()
        WeightHARV = Float()
        WeightRE = Float()
        WeightRT = Float()
        LeafLength = Float()
        WeightABG = Float()
        SLAINT = Float()
        DVS = Float()

    def initialize(self, day, kiosk, parvalues):

        self.source_limited_growth = SourceLimitedGrowth(day, kiosk, parvalues)
        self.sink_limited_growth = SinkLimitedGrowth(day, kiosk, parvalues)
        self.soil_temperature = SoilTemperature(day, kiosk, parvalues)
        self.evapotranspiration = Evapotranspiration(day, kiosk, parvalues)
        self.root_dynamics = Simple_Root_Dynamics(day, kiosk, parvalues)

        self.params = self.Parameters(parvalues)
        p = self.params
        s = {"TSUM": 0.,
             "LAI": p.LAIinit,
             "DaysAfterHarvest": 0,
             "CuttingNumber": 0,
             "TillerNumber": p.TillerNumberinit,
             "WeightLVgreen": p.LAIinit / p.SLA,
             "WeightLVdead": 0.,
             "WeightHARV": 0.,
             "WeightRE": p.WeightREinit,
             "WeightRT": p.WeightRTinit,
             "LeafLength": 0.,
             "WeightABG": p.LAIinit / p.SLA,
             "SLAINT": p.SLA,
             "DVS": 0.0}
        pub = ["LAI", "WeightRE", "LeafLength", "TillerNumber", "TSUM",
               "DaysAfterHarvest", "DVS", "WeightLVgreen", "WeightRT"]
        self.states = self.StateVariables(kiosk, **s, publish=pub)
        self.rates = self.RateVariables(kiosk, publish=["dWeightHARV", "LVfraction", "RTfraction",
                                                        "LVgrowth", "dWeightRT", "LVdeath"])
        self.n_dynamics = N_Crop_Dynamics(day, kiosk, parvalues)
        self.n_stress = N_Stress(day, kiosk, parvalues)
        self._connect_signal(self._on_MOWING, signal=pcse.signals.mowing)

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk
        s = self.states

        r.dTSUM = max(drv.TEMP - p.TempBase, 0.)

        self.soil_temperature.calc_rates(day, drv)
        self.root_dynamics.calc_rates(day, drv)
        self.evapotranspiration(day, drv)
        self.n_stress(day, drv)

        # 草地管理割草选项
        if self._flag_MOWING:
            r.dWeightHARV = max(0, s.WeightLVgreen - self.WeightLV_remaining)
            r.dDaysAfterHarvest = -s.DaysAfterHarvest
            r.dCuttingNumber = 1
        else:
            r.dCuttingNumber = 0
            r.dWeightHARV = 0.
            if s.CuttingNumber > 0 or r.dCuttingNumber == 1:
                r.dDaysAfterHarvest = 1
            else:
                r.dDaysAfterHarvest = 0

        # *** 叶片死亡速率 ***
        # 由于干旱胁迫导致的叶片相对死亡率，d-1
        RDRdrought = limit(0., p.RDRdrought, p.RDRdrought * (1.-k.RFTRA))
        # 由于自遮荫导致的叶片相对死亡率，d-1
        RDRshading = limit(0., p.RDRshading, p.RDRshading * (s.LAI-p.LAIcrit)/p.LAIcrit)
        # 由于氮胁迫导致的叶片相对死亡率
        RDRnitrogen = limit(0, p.RDRnitrogen, p.RDRnitrogen * (1. - k.NNI))
        # 实际叶片相对死亡率为基础死亡率与遮荫、干旱和氮死亡率三者最大值之和，d-1
        RDRtotal = p.RDRbase + max(RDRshading, RDRdrought, RDRnitrogen)
        # 实际叶面积死亡率，由叶片相对死亡率或割草导致的变化率决定，ha ha-1 d-1
        if self._flag_MOWING:
            LAIdeath = r.dWeightHARV * s.SLAINT
        else:
            LAIdeath = s.LAI * (1. - exp(-RDRtotal))

        # 分配给根/叶的干物质比例，kg kg-1
        r.RTfraction = p.PartitioningRootsTB(k.RFTRA)
        r.LVfraction = 1. - r.RTfraction

        # *** 生长速率 ***
        GrowthSource = self.source_limited_growth(day, drv)
        GrowthSink = self.sink_limited_growth(day, drv)

        # 实际生长在库源/库限制之间切换
        if GrowthSource < GrowthSink:  # 库源限制生长
            gap = GrowthSink - GrowthSource  # 同化物缺口
            dWeightRE = min(s.WeightRE, gap)  # 可用贮藏
            GrowthAct = GrowthSource + dWeightRE
            r.dWeightRE = -dWeightRE
        else:  # 库限制生长
            r.dWeightRE = GrowthSource - GrowthSink  # 同化物剩余
            GrowthAct = GrowthSink

        # 实际叶面积生长速率，ha ha-1 d-1
        SLA = p.SLA * exp(-p.NSLA * (1.-k.NNI))
        LAIgrowthAct = GrowthAct * r.LVfraction * SLA

        # 绿叶干重因叶生长/衰老或定期收割的变化速率，kg ha-1
        r.LVgrowth = GrowthAct * r.LVfraction if r.dWeightHARV <= 0 else 0.

        # 实际叶生物质死亡速率，含收割叶，kg ha-1 d-1
        r.LVdeath = LAIdeath / s.SLAINT

        # LAI变化量
        r.dLAI = LAIgrowthAct - LAIdeath

        # 绿叶重量变化
        r.dWeightLV = r.LVgrowth - r.LVdeath

        # 实际根系生长速率，kg ha-1 d-1
        r.dWeightRT = GrowthAct * r.RTfraction

        # 实际叶片长度变化
        if r.dWeightHARV > 0:  # 对收割进行修正
            r.dLeafLengthAct = -s.LeafLength
        else:
            if GrowthSink > 0:
                # 对库源限制修正
                r.dLeafLengthAct = k.dLeafLengthPot * GrowthAct/GrowthSink
            else:
                r.dLeafLengthAct = 0

        self.n_dynamics.calc_rates(day, drv)

        self._flag_MOWING = False

    @prepare_states
    def integrate(self, day, delt=1.0):
        r = self.rates
        k = self.kiosk
        s = self.states
        p = self.params

        s.TSUM += r.dTSUM * delt
        s.LAI += r.dLAI * delt
        s.DaysAfterHarvest += r.dDaysAfterHarvest
        s.CuttingNumber += r.dCuttingNumber
        s.TillerNumber += k.dTillerNumber * delt
        s.WeightLVgreen += r.dWeightLV * delt
        s.WeightLVdead += r.LVdeath * delt
        s.WeightHARV += r.dWeightHARV * delt
        s.WeightRE += r.dWeightRE * delt
        s.WeightRT += r.dWeightRT * delt
        s.LeafLength += r.dLeafLengthAct * delt

        # 地上部分总干重，包括已收割部分，单位kg ha-1
        s.WeightABG = s.WeightHARV + s.WeightLVgreen

        # 模型运行时的比叶面积，单位ha kg-1
        s.SLAINT = s.LAI / s.WeightLVgreen

        s.DVS = s.TSUM / p.TSUMmax
        # TODO: 是否在割草后重置TSUM

        self.soil_temperature.integrate(day, delt)
        self.root_dynamics.integrate(day, delt)
        self.n_dynamics.integrate(day, delt)

    @prepare_states
    def finalize(self, day):
        SimulationObject.finalize(self, day)

    def _on_MOWING(self, biomass_remaining):
        """青草割草事件的处理函数
        """
        self.WeightLV_remaining = biomass_remaining
        self._flag_MOWING = True

