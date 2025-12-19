# -*- coding: utf-8 -*-
# 版权所有 (c) 2021 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2021年3月
"""LINGRA草地模拟模型的实现

本模块实现了LINGRA (LINtul GRAssland)草地模拟模型，参见Schapendonk等, 1998
(https://doi.org/10.1016/S1161-0301(98)00027-6)，用于
Python Crop Simulation Environment。

"""
from math import exp, log

from pcse.base import SimulationObject, ParamTemplate, StatesTemplate, RatesTemplate
from pcse.traitlets import Float, List, Bool, Instance, Integer
from pcse.util import AfgenTrait, limit
from pcse.decorators import prepare_states, prepare_rates
from pcse.crop.evapotranspiration import Evapotranspiration
from pcse.crop.root_dynamics import Simple_Root_Dynamics
import pcse.signals


class SourceLimitedGrowth(SimulationObject):
    """基于辐射和温度这两个驱动变量计算受源限制的草地生长速率，生长速率也可能受土壤湿度或叶片氮含量的限制。
    叶片氮含量限制目前基于当前和最大氮浓度的静态值，实现主要是为将来连接氮模块做准备。

    本过程采用光能利用效率（LUE）方法，其中LUE会根据温度和辐射水平做调整。
    温度调整反映了光合作用对温度的响应，辐射调整反映光合作用随辐射增加趋于平缓，导致“表观”LUE下降。
    参数`LUEreductionRadiationTB`为该效应的粗略经验修正。

    注意：土壤湿度对生长速率的抑制通过蒸腾的还原因子（RFTRA）来实现。

    本模块不提供真正的速率变量，而是通过__call__()直接返回计算得到的生长速率。

    *模拟参数*:

    =======================  =============================================  ==============
     名称                      描述                                            单位
    =======================  =============================================  ==============
    KDIFTB                    漫射可见光消光系数，随着DVS变化                    -
    CO2A                      大气CO2浓度                                     ppm
    LUEreductionSoilTempTB    随土壤温度变化的LUE降低函数                       °C, -
    LUEreductionRadiationTB   随辐射水平变化的LUE降低函数                       MJ, -
    LUEmax                    最大光能利用效率
    =======================  =============================================  ==============


    *速率变量*

    ===================  =============================================  ===============
     名称                 描述                                            单位
    ===================  =============================================  ===============
    RF_RadiationLevel     由于辐射水平导致的LUE降低因子                         -
    RF_RadiationLevel     由于辐射水平导致的LUE降低因子                         -
    LUEact                实际的光能利用效率                                 g/(MJ PAR)
    ===================  =============================================  ===============

    *信号发送或处理*

    无

    *外部依赖:*

    ===============  =================================== ==============================
     名称             描述                                  提供方
    ===============  =================================== ==============================
    DVS               作物发育阶段                           pylingra.LINGRA
    TemperatureSoil   土壤温度                               pylingra.SoilTemperature
    RFTRA             蒸腾还原因子                           pcse.crop.Evapotranspiration
    ===============  =================================== ==============================
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

        # 温度和辐射水平对光合作用的抑制因子
        r.RF_Temperature = p.LUEreductionSoilTempTB(k.TemperatureSoil)
        r.RF_RadiationLevel = p.LUEreductionRadiationTB(DTR)

        # 光截获分数
        FINT = (1.-exp(-p.KDIFTB(k.DVS) * k.LAI))

        # 总截获有效光合辐射，单位 MJ m-2 d-1
        PARINT = FINT * PAR

        # 修正温度和辐射水平后的最大光能利用效率，单位 g MJ PAR-1
        LUEpot = p.LUEmax * r.RF_Temperature * r.RF_RadiationLevel

        # 修正蒸腾胁迫后的光能利用效率
        r.LUEact = LUEpot * k.RFTRA

        if k.dWeightHARV == 0.:  # 今天未割草，正常生长
            # (10: 单位从 g m-2 d-1 转换为 kg ha-1 d-1)
            GrowthSource = r.LUEact * PARINT * (1. + 0.8 * log(p.CO2A / 360.)) * 10.
        else:
            # 割草当天生长为零
            GrowthSource = 0.

        return GrowthSource


class SinkLimitedGrowth(SimulationObject):
    """计算草地的汇受限生长速率，假设最大叶片伸长速率由温度驱动，并乘以分蘖数。
    通过用比叶面积（SLA）进行除法，将其转换为干物质kg/ha的生长量。

    除了汇受限的生长速率，此类还计算分蘖数的变化，考虑了生长速率、死亡率以及收割后天数的影响。

    *模拟参数*:

    =======================  =============================================  ==============
     名称                        描述                                             单位
    =======================  =============================================  ==============
    TempBase                  叶片发育和禾草物候的基温                            ℃
    LAICrit                   临界叶面积指数，超过此值因自遮阴导致叶片死亡           -
    SiteFillingMax            新芽最大部位填充数                                  tiller/leaf-1
    SLA                       比叶面积                                           ha/kg
    TSUMmax                   达到最大发育阶段所需的温度积算                       ℃·d
    TillerFormRateA0          分蘖形成速率方程中A参数，适用于收割后7天以内
    TillerFormRateB0          分蘖形成速率方程中B参数，适用于收割后7天以内
    TillerFormRateA8          分蘖形成速率方程中A参数，适用于收割后第8天及以后
    TillerFormRateB8          分蘖形成速率方程中B参数，适用于收割后第8天及以后
    =======================  =============================================  ==============

    *速率变量*:

    ===================  =============================================  ===============
     名称                  描述                                              单位
    ===================  =============================================  ===============
    dTillerNumber         分蘖数变化，受到辐射水平影响                         tillers/m2/d
    dLeafLengthPot        潜在叶片长度变化。实际叶片长度变化将在下一步考虑
                          源限制后计算。                                     cm/d
    LAIGrowthSink         基于汇受限生长率的叶面积增长                         d-1
    ===================  =============================================  ===============

    *发送或处理的信号*

    无

    *外部依赖*:

    ===============      ===================================       ==============================
     名称                   描述                                        提供者
    ===============      ===================================       ==============================
    DVS                     作物发育阶段                               pylingra.LINGRA
    LAI                     叶面积指数                                 pylingra.LINGRA
    TemperatureSoil         土壤温度                                   pylingra.SoilTemperature
    RF_Temperature          基于温度的光能利用效率降低因子               pylingra.SourceLimitedGrowth
    TillerNumber            实际分蘖数                                 pylingra.LINGRA
    LVfraction              同化物分配到叶片的比例                     pylingra.LINGRA
    dWeightHARV             收获重变化（表明当天是否收割）               pylingra.LINGRA
    ===============      ===================================       ==============================
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

        # 叶片出现率受温度影响，根据(Davies and Thomas, 1983)，土壤温度（TemperatureSoil）作为驱动力，估算自10天滑动平均值
        LeafAppRate = k.TemperatureSoil * 0.01 if k.RF_Temperature > 0. else 0.
        # 计算分蘖数变化率
        r.dTillerNumber = self._calc_tillering_rate(LeafAppRate)

        # 叶片伸长速率受温度影响：cm/天/分蘖
        r.dLeafLengthPot = 0.83 * log(max(drv.TEMP, 2.)) - 0.8924 if (drv.TEMP - p.TempBase) > 0. else 0.

        # 汇受限（sink limited）叶面积生长率，TillerNumber单位为tillers m-2
        # 1.0E-8用于cm-2到ha-1的单位换算，单位：ha叶/ha地/天
        r.LAIgrowthSink = (k.TillerNumber * 1.0E4 * (r.dLeafLengthPot * 0.3)) * 1.0E-8
        # 利用SLA换算叶生长速率为总的汇受限碳需求，单位为kg叶/ha/天
        GrowthSink = r.LAIgrowthSink * (1./p.SLA) * (1./k.LVfraction) if k.dWeightHARV <= 0. else 0.

        return GrowthSink

    def _calc_tillering_rate(self, LeafAppRate):
        k = self.kiosk
        p = self.params
        # 实际分蘖位点填充等于无氮胁迫时的最大填充
        SiteFillingAct =  p.SiteFillingMax

        if k.DaysAfterHarvest < 8.:
            # 当离最后一次割草小于8天时的分蘖形成相对速率，单位：根/根/天
            TillerFormationRate = max(0., p.TillerFormRateA0 - p.TillerFormRateB0 * k.LAI) * k.RF_Temperature
        else:
            # 当离最后一次割草大于8天时的分蘖形成相对速率，单位：根/根/天
            TillerFormationRate = limit(0., SiteFillingAct, p.TillerFormRateA8 - p.TillerFormRateB8 * k.LAI) * k.RF_Temperature

        # 分蘖因自我遮荫（DTILD）导致的相对死亡速率，单位：根/根/天
        TillerDeathRate = max(0.01 * (1. + k.TSUM / p.TSUMmax), 0.05 * (k.LAI - p.LAIcrit) / p.LAIcrit)

        # 分蘖数变化
        if k.TillerNumber <= 14000.:
            dTillerNumber = (TillerFormationRate - TillerDeathRate) * LeafAppRate * k.TillerNumber
        else:
            dTillerNumber = -TillerDeathRate * LeafAppRate * k.TillerNumber

        return dTillerNumber


class SoilTemperature(SimulationObject):
    """计算上层10厘米土壤温度，采用2米高度日平均气温的10天滑动平均。

    *模拟参数*:

    =======================  ================================  ==============
       名称                    描述                                    单位
    =======================  ================================  ==============
    SoilTemperatureInit       初始土壤温度                             摄氏度
    =======================  ================================  ==============


    *速率变量*
    ===================  ============================  ==============
        名称                  描述                                单位
    ===================  ============================  ==============
    dTemperatureSoil      土壤温度变化                           摄氏度/天
    ===================  ============================  ==============

    *状态变量*
    ===================  ============================  ==============
        名称                  描述                                单位
    ===================  ============================  ==============
    TemperatureSoil       当前土壤温度                            摄氏度
    ===================  ============================  ==============

    *发送或处理的信号*

    无

    *外部依赖*

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

        # soil temperature changes
        r.dTemperatureSoil = (drv.TEMP - s.TemperatureSoil) / 10.

    @prepare_states
    def integrate(self, day, delt=1.0):
        self.states.TemperatureSoil += self.rates.dTemperatureSoil * delt


class LINGRA(SimulationObject):
    """LINGRA顶层实现，集成所有组成模块

    该类集成了LINGRA模型的所有组成模块，并包含与不同生物量库的重量、叶面积、分蘖数和叶长相关的主要状态变量。集成的组成部分包括源/库限制生长（土壤源/库的潜力）、土壤温度、蒸散和根系动态。最后两者（蒸散和根系动态）来自WOFOST以避免代码重复。

    与Schapendonk等（1998）的原始代码相比，做出了如下改进：

    - 对代码进行了整体重构，删除了不需要的变量，并将剩余变量重命名为更易读的名称。
    - 更清晰地实现了源/库限制生长，包括储备的利用。
    - 由库限制生长模块计算的潜在叶片伸长速率现在已被实际生长校正。这样可以避免在水分胁迫条件下出现叶片无限制生长导致不现实结果。

    *模拟参数*:

    =======================  =============================================  ==============
     名称                      描述                                             单位
    =======================  =============================================  ==============
     LAIinit                  初始叶面积指数                                      -
     TillerNumberinit         初始分蘖数                                        tillers/m2
     WeightREinit             初始储备重                                        kg/ha
     WeightRTinit             初始根重                                          kg/ha
     LAIcrit                  因自我遮荫导致死亡的临界LAI                          -
     RDRbase                  根的基础相对死亡速率                               d-1
     RDRShading               因自我遮荫导致叶片的最大相对死亡速率                 d-1
     RDRdrought               因干旱胁迫导致叶片的最大相对死亡速率                 d-1
     SLA                      比叶面积                                           ha/kg
     TempBase                 光合与发育的基础温度                                  C
     PartitioningRootsTB      根分配分数，作为蒸腾调节因子的函数（RFTRA）             -, -
     TSUMmax                  到最大发育阶段的温度积累                              C.d
    =======================  =============================================  ==============

    *变化率变量*:

    ===================  =============================================  ===============
     名称                 描述                                             单位
    ===================  =============================================  ===============
    dTSUM                 发育温度积变化                                    C
    dLAI                  叶面积指数净变化                                   d-1
    dDaysAfterHarvest     距上次收割天数变化                                  -
    dCuttingNumber        收割（收获）次数变化                                 -
    dWeightLV             叶片重净变化                                      kg/ha/d
    dWeightRE             储备池净变化                                      kg/ha/d
    dLeafLengthAct        实际叶长变化                                      cm/d
    LVdeath               叶死亡速率                                        kg/ha/d
    LVgrowth              叶生长速率                                        kg/ha/d
    dWeightHARV           收获干物质量变化                                   kg/ha/d
    dWeightRT             根重净变化                                        kg/ha/d
    LVfraction            分配到叶片的比例                                   -
    RTfraction            分配到根的比例                                     -
    ===================  =============================================  ===============

    *状态变量*:

    ===================  =============================================  ===============
     名称                 描述                                             单位
    ===================  =============================================  ===============
     TSUM                 温度积累                                         C d
     LAI                  叶面积指数                                        -
     DaysAfterHarvest     距上次收割天数                                     d
     CuttingNumber        收割（收获）次数                                    -
     TillerNumber         分蘖数                                           tillers/m2
     WeightLVgreen        绿叶质量                                         kg/ha
     WeightLVdead         死叶质量                                         kg/ha
     WeightHARV           收获干物质量                                      kg/ha
     WeightRE             储备质量                                          kg/ha
     WeightRT             根质量                                            kg/ha
     LeafLength           叶片长度                                          kg/ha
     WeightABG            地上部总质量（收获+现有）                            kg/ha
     SLAINT               季节内集成比叶面积                                   ha/kg
     DVS                  发育阶段                                            -
    ===================  =============================================  ===============

    *发送或处理的信号*

    当广播 `pcse.signals.mowing` 事件时，会进行割草。这将减少活叶的数量（认为田间会保留一定生物量，这个量由MOWING事件的参数控制）。

    *外部依赖*:

    ===============  =================================== ====================================
     名称             描述                                   提供模块
    ===============  =================================== ====================================
    RFTRA             蒸腾调节因子                            pcse.crop.Evapotranspiration
    dLeafLengthPot    潜在叶长增长                            pcse.crop.lingra.SinkLimitedGrowth
    dTillerNumber     分蘖数变化                              pcse.crop.lingra.SinkLimitedGrowth
    ===============  =================================== ====================================
    """

    WeightLV_remaining = Float()
    _flag_MOWING = Bool(False)

    source_limited_growth = Instance(SimulationObject)
    sink_limited_growth = Instance(SimulationObject)
    soil_temperature = Instance(SimulationObject)
    evapotranspiration = Instance(SimulationObject)
    root_dynamics = Instance(SimulationObject)

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
        RDRshading = Float()
        RDRdrought = Float()

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
               "DaysAfterHarvest", "DVS"]
        self.states = self.StateVariables(kiosk, **s, publish=pub)
        self.rates = self.RateVariables(kiosk, publish=["dWeightHARV", "LVfraction", "RTfraction"])
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

        # 草地割草管理选项
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
        # 由于干旱胁迫导致的叶片相对死亡速率，d-1
        RDRdrought = limit(0., p.RDRdrought, p.RDRdrought * (1.-k.RFTRA))
        # 由于自遮阴导致的叶片相对死亡速率，d-1
        RDRshading = limit(0., p.RDRshading, p.RDRshading * (s.LAI-p.LAIcrit)/p.LAIcrit)
        # 实际叶片相对死亡速率是基础死亡速率与遮阴和干旱死亡速率最大值之和，d-1
        RDRtotal = p.RDRbase + max(RDRshading, RDRdrought)
        # 实际叶面积死亡速率，由叶面积的相对死亡速率或割草引起的变化决定，ha ha-1 d-1
        if self._flag_MOWING:
            LAIdeath = r.dWeightHARV * s.SLAINT
        else:
            LAIdeath = s.LAI * (1. - exp(-RDRtotal))

        # 分配到根/叶的干物质比例，kg kg-1
        r.RTfraction = p.PartitioningRootsTB(k.RFTRA)
        r.LVfraction = 1. - r.RTfraction

        # *** 生长速率 ***
        GrowthSource = self.source_limited_growth(day, drv)
        GrowthSink = self.sink_limited_growth(day, drv)

        # 实际生长在源限制和库限制之间切换
        if GrowthSource < GrowthSink:  # 源限制生长
            gap = GrowthSink - GrowthSource  # 同化物缺口
            dWeightRE = min(s.WeightRE, gap)  # 可用贮藏物质
            GrowthAct = GrowthSource + dWeightRE
            r.dWeightRE = -dWeightRE
        else:  # 库限制生长
            r.dWeightRE = GrowthSource - GrowthSink  # 同化物过剩
            GrowthAct = GrowthSink

        # 实际叶面积生长速率，ha ha-1 d-1
        LAIgrowthAct = GrowthAct * r.LVfraction * p.SLA

        # 由于叶片生长和衰老/定期收割引起的绿色叶片干重变化速率，kg ha-1
        r.LVgrowth = GrowthAct * r.LVfraction if r.dWeightHARV <= 0 else 0.

        # 包括收割叶片的叶片干重实际死亡速率，kg ha-1 d-1
        r.LVdeath = LAIdeath / s.SLAINT

        # LAI的变化量
        r.dLAI = LAIgrowthAct - LAIdeath

        # 绿色叶片干重的变化量
        r.dWeightLV = r.LVgrowth - r.LVdeath

        # 根的实际生长速率，kg ha-1 d-1
        r.dWeightRT = GrowthAct * r.RTfraction

        # 叶片长度的实际变化量
        if r.dWeightHARV > 0:  # 割草修正
            r.dLeafLengthAct = -s.LeafLength
        else:
            if GrowthSink > 0:
                # 源限制修正
                r.dLeafLengthAct = k.dLeafLengthPot * GrowthAct/GrowthSink
            else:
                r.dLeafLengthAct = 0

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

        # 地上部分（包括收割后）总干重，单位: kg ha-1
        s.WeightABG = s.WeightHARV + s.WeightLVgreen

        # 模型中即时比叶面积, 单位: ha kg-1
        s.SLAINT = s.LAI / s.WeightLVgreen

        s.DVS = s.TSUM / p.TSUMmax
        # TODO: 是否在割草后重置TSUM

        self.soil_temperature.integrate(day, delt)
        self.root_dynamics.integrate(day, delt)

    @prepare_states
    def finalize(self, day):
        SimulationObject.finalize(self, day)

    def _on_MOWING(self, biomass_remaining):
        """处理割草事件的函数
        """
        self.WeightLV_remaining = biomass_remaining
        self._flag_MOWING = True
