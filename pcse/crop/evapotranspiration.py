# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究院，瓦赫宁根大学与研究中心
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
from math import exp

import array
import numpy as np

from ..traitlets import Float, Int, Instance, Bool, Instance
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
                         SimulationObject
from ..util import limit, merge_dict, AfgenTrait


def SWEAF(ET0, DEPNR):
    """计算土壤易利用水分分数（SWEAF）。

    :param ET0: 参考作物的蒸散量。
    :param DEPNR: 作物依赖性编号。
    
    易利用土壤水分分数（即田间持水量和永久萎蔫点之间的水分），是潜在蒸散速率
    （全冠闭合时，cm/day，ET0）和作物组编号DEPNR（1=干旱敏感，5=耐旱）函数。
    SWEAF 函数以表格形式描述了Doorenbos & Kassam (1979)以及Van Keulen & Wolf (1986, 第108页, 表20)
    http://edepot.wur.nl/168025 所给出的这种关系。
    """
    A = 0.76
    B = 1.5
    # CGNR 5 的曲线，其它曲线以固定距离向下平移
    sweaf = 1./(A+B*ET0) - (5.-DEPNR)*0.10

    # 对低位曲线（CGNR 小于 3）进行修正
    if (DEPNR < 3.):
        sweaf += (ET0-0.6)/(DEPNR*(DEPNR+3.))

    return limit(0.10, 0.95, sweaf)


class EvapotranspirationWrapper(SimulationObject):
    """根据是否采用分层或非分层土壤的水量平衡及是否考虑CO2的影响，选择合适的蒸散量模块
    """
    etmodule = Instance(SimulationObject)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: 参数值
        """

        if "soil_profile" in parvalues:
            self.etmodule = EvapotranspirationCO2Layered(day, kiosk, parvalues)
        elif "CO2" in parvalues and "CO2TRATB" in parvalues:
            self.etmodule = EvapotranspirationCO2(day, kiosk, parvalues)
        else:
            self.etmodule = Evapotranspiration(day, kiosk, parvalues)

    def __call__(self, day, drv):
        r = self.etmodule(day, drv)
        return r


class Evapotranspiration(SimulationObject):
    """计算潜在蒸发（包括水体和土壤）速率以及作物实际蒸腾速率。

    *模拟参数*:

    =======  ============================================= =======  ============
     名称     描述                                           类型      单位
    =======  ============================================= =======  ============
    CFET     潜在蒸腾速率修正系数                            SCr       -
    DEPNR    作物对土壤水分胁迫的敏感依赖编号                SCr       -
    KDIFTB   随DVS变化的漫射可见光衰减系数                   TCr       -
    IOX      是否考虑氧气胁迫（1为开启，0为关闭）            SCr       -
    IAIRDU   是否考虑通气组织（1为开启，0为关闭）            SCr       -
    CRAIRC   根系需氧临界含气量                              SSo       -
    SM0      土壤孔隙度                                      SSo       -
    SMW      萎蔫点体积含水量                                SSo       -
    SMCFC    田间持水量体积含水量                            SSo       -
    SM0      土壤孔隙度                                      SSo       -
    =======  ============================================= =======  ============

    *状态变量*

    注意：这些状态变量只会在finalize()运行后才被赋值。

    =======  ============================================ ==== ============
     名称      描述                                        Pbl      单位
    =======  ============================================ ==== ============
    IDWST     发生水分胁迫的天数计数                        N       -
    IDOST     发生氧气胁迫的天数计数                        N       -
    =======  ============================================ ==== ============

    *速率变量*

    =======  ================================================= ==== ============
     名称      描述                                            Pbl      单位
    =======  ================================================= ==== ============
    EVWMX    水面最大蒸发速率                                  Y     |cm day-1|
    EVSMX    湿润土壤表面最大蒸发速率                          Y     |cm day-1|
    TRAMX    植物冠层最大蒸腾速率                              Y     |cm day-1|
    TRA      植物冠层实际蒸腾速率                              Y     |cm day-1|
    IDOS     当天是否发生氧气胁迫（True|False）                N      -
    IDWS     当天是否发生水分胁迫（True|False）                N      -
    RFWS     水分胁迫下的蒸腾调节因子                          N      -
    RFOS     氧气胁迫下的蒸腾调节因子                          N      -
    RFTRA    蒸腾调节因子（同时考虑水分与氧气）                Y      -
    =======  ================================================= ==== ============

    *发送或处理的信号*

    无

    *外部依赖*:

    =======  =================================== =================  ============
     名称       描述                                 来源                 单位
    =======  =================================== =================  ============
    DVS      作物发育阶段                          DVS_Phenology       -
    LAI      叶面积指数                            Leaf_dynamics       -
    SM       土壤体积含水量                        Waterbalance        -
    =======  =================================== =================  ============
    """

    # 计数水分和氧气胁迫总天数的辅助变量（IDWST, IDOST）
    _IDWST = Int(0)
    _IDOST = Int(0)

    class Parameters(ParamTemplate):
        CFET = Float(-99.)
        DEPNR = Float(-99.)
        KDIFTB = AfgenTrait()
        IAIRDU = Float(-99.)
        IOX = Float(-99.)
        CRAIRC = Float(-99.)
        SM0 = Float(-99.)
        SMW = Float(-99.)
        SMFCF = Float(-99.)

    class RateVariables(RatesTemplate):
        EVWMX = Float(-99.)
        EVSMX = Float(-99.)
        TRAMX = Float(-99.)
        TRA = Float(-99.)
        IDOS = Bool(False)
        IDWS = Bool(False)
        RFWS = Float(-99.)
        RFOS = Float(-99.)
        RFTRA = Float(-99.)

    class StateVariables(StatesTemplate):
        IDOST = Int(-99)
        IDWST = Int(-99)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 仿真开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，以键值对形式提供参数
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["EVWMX", "EVSMX", "TRAMX", "TRA", "RFTRA"])
        self.states = self.StateVariables(kiosk, IDOST=-999, IDWST=-999)

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk
        
        KGLOB = 0.75 * p.KDIFTB(k.DVS)
  
        # 作物类型对潜在蒸腾速率的修正
        ET0_CROP = max(0., p.CFET * drv.ET0)
  
        # 最大蒸发和蒸腾速率
        EKL = exp(-KGLOB * k.LAI)
        r.EVWMX = drv.E0 * EKL
        r.EVSMX = max(0., drv.ES0 * EKL)
        r.TRAMX = ET0_CROP * (1.-EKL)
                
        # 临界土壤含水量
        SWDEP = SWEAF(ET0_CROP, p.DEPNR)
        SMCR = (1.-SWDEP)*(p.SMFCF-p.SMW) + p.SMW

        # 缺水胁迫下的蒸腾调节因子（RFWS）
        r.RFWS = limit(0., 1., (k.SM - p.SMW)/(SMCR - p.SMW))

        # 缺氧胁迫下的蒸腾调节因子（RFOS）
        # 针对非水稻作物及排水较差的情况
        r.RFOS = 1.
        if p.IAIRDU == 0 and p.IOX == 1:
            RFOSMX = limit(0., 1., (p.SM0 - k.SM)/p.CRAIRC)
            # 最大抑制效应在4天后达到
            r.RFOS = RFOSMX + (1. - min(k.DSOS, 4)/4.)*(1.-RFOSMX)

        # 同时考虑水分与氧气胁迫的总蒸腾调节因子
        r.RFTRA = r.RFOS * r.RFWS
        r.TRA = r.TRAMX * r.RFTRA

        # 记录胁迫天数
        if r.RFWS < 1.:
            r.IDWS = True
            self._IDWST += 1
        if r.RFOS < 1.:
            r.IDOS = True
            self._IDOST += 1

        return r.TRA, r.TRAMX
        
    @prepare_states
    def finalize(self, day):

        self.states.IDWST = self._IDWST
        self.states.IDOST = self._IDOST
        
        SimulationObject.finalize(self, day)


class EvapotranspirationCO2(SimulationObject):
    """计算蒸发（包括水体和土壤）与蒸腾速率，同时考虑大气CO2对作物蒸腾的影响。

    *模拟参数* （需要在cropdata字典中提供）：

    ======== ============================================= =======  ============
     名称       描述                                        类型      单位
    ======== ============================================= =======  ============
    CFET     潜在蒸腾速率的修正系数                         S          -
    DEPNR    作物对土壤水分胁迫敏感度的依赖编号             S          -
    KDIFTB   散射可见光的消光系数，随DVS而变                 T          -
    IOX      氧气胁迫开关，1为开，0为关                      S          -
    IAIRDU   通气道开关，1为开，0为关                        S          -
    CRAIRC   根部通气的临界空气含量                          S          -
    SM0      土壤孔隙度                                      S          -
    SMW      萎蔫点体积含水量                                S          -
             （即土壤萎蔫点）
    SMCFC    田间持水量体积含水量                            S          -
    SM0      土壤孔隙度                                      S          -
    CO2      大气CO2浓度                                    S          ppm
    CO2TRATB TRAMX随大气CO2浓度变化的修正因子                T          -
    ======== ============================================= =======  ============

    *状态变量*

    注意：这些状态变量仅在执行finalize()后被赋值。

    =======  ======================================== ==== ============
     名称      描述                                   公布    单位
    =======  ======================================== ==== ============
    IDWST     水分胁迫天数                              N      -
    IDOST     氧气胁迫天数                              N      -
    =======  ======================================== ==== ============

    *速率变量*

    =======  ======================================== ==== ============
     名称      描述                                   公布    单位
    =======  ======================================== ==== ============
    EVWMX    开阔水面最大蒸发速率                       Y    |cm day-1|
    EVSMX    湿润土壤表面最大蒸发速率                   Y    |cm day-1|
    TRAMX    植被冠层最大蒸腾速率                       Y    |cm day-1|
    TRA      植被冠层实际蒸腾速率                       Y    |cm day-1|
    IDOS     表示当天是否水分胁迫（True|False）         N      -
    IDWS     表示当天是否氧气胁迫（True|False）         N      -
    RFWS     水分胁迫修正系数                           Y      -
    RFOS     氧气胁迫修正系数                           Y      -
    RFTRA    考虑水分和氧气胁迫的蒸腾修正系数           Y      -
    =======  ======================================== ==== ============

    *信号的发送与处理*

    无

    *外部依赖变量：*

    =======  =================================== ================  ============
     名称      描述                               来源               单位
    =======  =================================== ================  ============
    DVS      作物发育阶段                         DVS_Phenology       -
    LAI      叶面积指数                           Leaf_dynamics       -
    SM       土壤体积含水量                       Waterbalance        -
    =======  =================================== ================  ============
    """

    # 用于统计水分和氧气胁迫总天数（IDWST, IDOST）的辅助变量
    _IDWST = Int(0)
    _IDOST = Int(0)

    class Parameters(ParamTemplate):
        CFET    = Float(-99.)
        DEPNR   = Float(-99.)
        KDIFTB  = AfgenTrait()
        IAIRDU  = Float(-99.)
        IOX     = Float(-99.)
        CRAIRC  = Float(-99.)
        SM0     = Float(-99.)
        SMW     = Float(-99.)
        SMFCF   = Float(-99.)
        CO2     = Float(-99.)
        CO2TRATB = AfgenTrait()

    class RateVariables(RatesTemplate):
        EVWMX = Float(-99.)
        EVSMX = Float(-99.)
        TRAMX = Float(-99.)
        TRA   = Float(-99.)
        TRALY = Instance(array.array)
        IDOS  = Bool(False)
        IDWS  = Bool(False)
        RFWS = Float(-99.)
        RFOS = Float(-99.)
        RFTRA = Float(-99.)

    class StateVariables(StatesTemplate):
        IDOST  = Int(-99)
        IDWST  = Int(-99)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param cropdata: 包含WOFOST作物数据键/值对的字典
        :param soildata: 包含WOFOST土壤数据键/值对的字典
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["EVWMX","EVSMX", "TRAMX","TRA","TRALY", "RFTRA"])
        self.states = self.StateVariables(kiosk, IDOST=-999, IDWST=-999)

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # CO2对TRAMX的削减因子
        RF_TRAMX_CO2 = p.CO2TRATB(p.CO2)

        # 针对作物修正的参考蒸散发速率
        ET0_CROP = max(0., p.CFET * drv.ET0)

        # 最大蒸发和蒸腾速率
        KGLOB = 0.75*p.KDIFTB(k.DVS)
        EKL = exp(-KGLOB * k.LAI)
        r.EVWMX = drv.E0 * EKL
        r.EVSMX = max(0., drv.ES0 * EKL)
        r.TRAMX = ET0_CROP * (1.-EKL) * RF_TRAMX_CO2

        # 临界土壤含水量
        SWDEP = SWEAF(ET0_CROP, p.DEPNR)

        SMCR = (1.-SWDEP)*(p.SMFCF-p.SMW) + p.SMW

        # 缺水情况下蒸腾的削减因子（RFWS）
        r.RFWS = limit(0., 1., (k.SM-p.SMW)/(SMCR-p.SMW))

        # 缺氧情况下蒸腾的削减因子（RFOS）
        # 针对非水稻作物，或可能排水不良的土地
        r.RFOS = 1.
        if p.IAIRDU == 0 and p.IOX == 1:
            RFOSMX = limit(0., 1., (p.SM0 - k.SM)/p.CRAIRC)
            # 4天后达到最大削减
            r.RFOS = RFOSMX + (1. - min(k.DSOS, 4)/4.)*(1.-RFOSMX)

        # 蒸腾速率乘以缺氧与缺水的两种削减因子
        r.RFTRA = r.RFOS * r.RFWS
        r.TRA = r.TRAMX * r.RFTRA

        # 计数有胁迫的天数
        if r.RFWS < 1.:
            r.IDWS = True
            self._IDWST += 1
        if r.RFOS < 1.:
            r.IDOS = True
            self._IDOST += 1

        return r.TRA, r.TRAMX

    @prepare_states
    def finalize(self, day):
        # 最终统计水分胁迫和氧气胁迫的总天数
        self.states.IDWST = self._IDWST
        self.states.IDOST = self._IDOST

        SimulationObject.finalize(self, day)


class EvapotranspirationCO2Layered(SimulationObject):
    """计算水和土壤蒸发及作物蒸腾速率，考虑分层土壤中二氧化碳对作物蒸腾的影响

    *模拟参数* （由cropdata字典提供）：

    ======== ============================================= =======  ============
     名称      描述                                         类型      单位
    ======== ============================================= =======  ============
    CFET     潜在蒸腾率的修正系数。                           S        -
    DEPNR    作物对土壤水分胁迫敏感性的依赖号。               S        -
    KDIFTB   不同DVS下散射可见光的消光系数。                  T        -
    IOX      是否开启氧气胁迫（开1，关0）                     S        -
    IAIRDU   是否开启通气组织（开1，关0）                     S        -
    CRAIRC   根系通气的临界空气含量                           S        -
    SM0      土壤孔隙度                                       S        -
    SMW      萎蔫点体积含水量。                               S        -
    SMCFC    田间持水量的体积含水量。                         S        -
    SM0      土壤孔隙度（重复项）                             S        -
    CO2      大气二氧化碳浓度                                 S        ppm
    CO2TRATB 随大气CO2浓度变动的TRAMX修正因子                 T        -
    ======== ============================================= =======  ============

    *状态变量*

    注意：这些状态变量仅在finalize()运行后被赋值。

    =======  ============================================= ==== ============
     名称      描述                                        参与      单位
    =======  ============================================= ==== ============
    IDWST     水分胁迫天数                                   N      -
    IDOST     氧气胁迫天数                                   N      -
    =======  ============================================= ==== ============

    *速率变量*

    =======  ============================================= ==== ============
     名称      描述                                        参与      单位
    =======  ============================================= ==== ============
    EVWMX    开阔水面最大蒸发速率                            Y     |cm day-1|
    EVSMX    湿土表面最大蒸发速率                            Y     |cm day-1|
    TRAMX    植被冠层最大蒸腾速率                            Y     |cm day-1|
    TRA      植被冠层实际蒸腾速率                            Y     |cm day-1|
    IDOS     当天是否发生水分胁迫（True|False）              N      -
    IDWS     当天是否发生氧气胁迫（True|False）              N      -
    RFWS     水分胁迫修正因子                                Y      -
    RFOS     氧气胁迫修正因子                                Y      -
    RFTRA    蒸腾综合修正因子（水分与氧气）                  Y      -
    =======  ============================================= ==== ============

    *发送或处理的信号*

    无

    *外部依赖：*

    =======  ================================ ================  ============
     名称      描述                                提供者           单位
    =======  ================================ ================  ============
    DVS      作物发育阶段                      DVS_Phenology         -
    LAI      叶面积指数                        Leaf_dynamics         -
    SM       土壤体积含水量                    Waterbalance          -
    =======  ================================ ================  ============
    """

    # 辅助变量，用于累计水分及氧气胁迫天数（IDWST, IDOST）
    _IDWST = Int(0)
    _IDOST = Int(0)
    _DSOS = Int(0)

    soil_profile = None

    class Parameters(ParamTemplate):
        CFET    = Float(-99.)
        DEPNR   = Float(-99.)
        KDIFTB  = AfgenTrait()
        IAIRDU  = Float(-99.)
        IOX     = Float(-99.)
        CO2     = Float(-99.)
        CO2TRATB = AfgenTrait()

    class RateVariables(RatesTemplate):
        EVWMX = Float(-99.)
        EVSMX = Float(-99.)
        TRAMX = Float(-99.)
        TRA   = Float(-99.)
        TRALY = Instance(np.ndarray)
        IDOS  = Bool(False)
        IDWS  = Bool(False)
        RFWS = Instance(np.ndarray)
        RFOS = Instance(np.ndarray)
        RFTRALY = Instance(np.ndarray)
        RFTRA = Float(-99.)

    class StateVariables(StatesTemplate):
        IDOST  = Int(-99)
        IDWST  = Int(-99)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 当前PCSE实例的变量kiosk
        :param cropdata: WOFOST作物参数的键值对字典
        :param soildata: WOFOST土壤参数的键值对字典
        """

        self.soil_profile = parvalues["soil_profile"]
        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["EVWMX","EVSMX", "TRAMX","TRA","TRALY", "RFTRA"])
        self.states = self.StateVariables(kiosk, IDOST=-999, IDWST=-999)

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # CO2对TRAMX的还原因子
        RF_TRAMX_CO2 = p.CO2TRATB(p.CO2)

        # 作物特定的潜在蒸腾速率修正
        ET0_CROP = max(0., p.CFET * drv.ET0)

        # 最大蒸发和蒸腾速率
        KGLOB = 0.75*p.KDIFTB(k.DVS)
        EKL = exp(-KGLOB * k.LAI)
        r.EVWMX = drv.E0 * EKL
        r.EVSMX = max(0., drv.ES0 * EKL)
        r.TRAMX = ET0_CROP * (1.-EKL) * RF_TRAMX_CO2

        # 临界土壤含水量
        SWDEP = SWEAF(ET0_CROP, p.DEPNR)
        depth = 0.0

        RFWS = np.zeros(len(self.soil_profile), dtype=np.float64)
        RFOS = np.zeros_like(RFWS)
        TRALY = np.zeros_like(RFWS)

        layercnt = range(len(self.soil_profile))
        for i, SM, layer in zip(layercnt, k.SM, self.soil_profile):
            SMCR = (1.-SWDEP)*(layer.SMFCF - layer.SMW) + layer.SMW

            # 水分胁迫下的蒸腾还原因子 (RFWS)
            RFWS[i] = limit(0., 1., (SM - layer.SMW)/(SMCR - layer.SMW))

            # 氧气胁迫下的蒸腾还原因子 (RFOS)
            # 针对非水稻作物，以及排水不良的土壤
            RFOS[i] = 1.
            if p.IAIRDU == 0 and p.IOX == 1:
                SMAIR = layer.SM0 - layer.CRAIRC
                if(SM >= SMAIR):
                    self._DSOS = min((self._DSOS + 1), 4)
                else:
                    self._DSOS = 0                
                RFOSMX = limit(0., 1., (layer.SM0 - SM)/layer.CRAIRC)
                RFOS[i] = RFOSMX + (1. - min( self._DSOS, 4)/4.)*(1.-RFOSMX)
            root_fraction = max(0.0, (min(k.RD, depth + layer.Thickness) - depth)) / k.RD
            RFTRA_layer = RFOS[i] * RFWS[i]
            TRALY[i] = r.TRAMX * RFTRA_layer * root_fraction

            depth += layer.Thickness

        r.TRA = TRALY.sum()
        r.TRALY = TRALY
        r.RFTRA = r.TRA/r.TRAMX if r.TRAMX > 0. else 1.
        r.RFOS = RFOS
        r.RFWS = RFWS

        # 统计胁迫天数
        if any(r.RFWS < 1.):
            r.IDWS = True
            self._IDWST += 1
        if any(r.RFOS < 1.):
            r.IDOS = True
            self._IDOST += 1

    @prepare_states
    def finalize(self, day):

        self.states.IDWST = self._IDWST
        self.states.IDOST = self._IDOST

        SimulationObject.finalize(self, day)


class Simple_Evapotranspiration(SimulationObject):
    """计算水和土壤的蒸发以及作物冠层的蒸腾速率。

    相较于WOFOST模型进行了简化，因此无需参数即可计算ET。参数如KDIF、CFET、DEPNR使用了典型禾本科作物的硬编码值。同时，已关闭氧气胁迫的影响。

    *模拟参数* （需在soildata字典中提供）:

    =======  ============================================= =======  ============
     名称      描述                                          类型      单位
    =======  ============================================= =======  ============
    SMW      萎蔫点时土壤体积含水量                           S         -
    SMCFC    田间持水量时土壤体积含水量                       S         -
    SM0      土壤孔隙度                                       S         -
    =======  ============================================= =======  ============

    *状态变量*

    无

    *速率变量*

    =======  ================================================= ==== ============
     名称      描述                                            发布      单位
    =======  ================================================= ==== ============
    EVWMX    开阔水面最大蒸发速率                                Y    |cm day-1|
    EVSMX    湿润土壤表面最大蒸发速率                            Y    |cm day-1|
    TRAMX    作物冠层最大蒸腾速率                                Y    |cm day-1|
    TRA      作物冠层实际蒸腾速率                                Y    |cm day-1|
    =======  ================================================= ==== ============

    *发送或处理的信号*

    无

    *外部依赖:*

    =======  =================================== =================  ============
     名称      描述                                  提供者            单位
    =======  =================================== =================  ============
    LAI      叶面积指数                              Leaf_dynamics       -
    SM       土壤体积含水量                          Waterbalance        -
    =======  =================================== =================  ============
    """

    class Parameters(ParamTemplate):
        SM0    = Float(-99.)
        SMW    = Float(-99.)
        SMFCF  = Float(-99.)
        CFET = Float(-99.)
        DEPNR = Float(-99.)

    class RateVariables(RatesTemplate):
        EVWMX = Float(-99.)
        EVSMX = Float(-99.)
        TRAMX = Float(-99.)
        TRA   = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param soildata: 含有WOFOST土壤数据的键值对字典
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["EVWMX","EVSMX",
                                                        "TRAMX","TRA"])

    @prepare_rates
    def __call__(self, day, drv):
        p = self.params
        r = self.rates
        
        LAI = self.kiosk["LAI"]
        SM  = self.kiosk["SM"]
        
        # KDIF为玉米作物取值
        KDIF = 0.6
        KGLOB = 0.75*KDIF
  
        # 作物特定的潜在蒸腾速率校正
        ET0 = p.CFET * drv.ET0
  
        # 最大蒸发与蒸腾速率
        EKL = exp(-KGLOB * LAI)
        r.EVWMX = drv.E0 * EKL
        r.EVSMX = max(0., drv.ES0 * EKL)
        r.TRAMX = max(0.000001, ET0 * (1.-EKL))
        
        # 临界土壤湿度
        SWDEP = SWEAF(ET0, p.DEPNR)
        
        SMCR = (1.-SWDEP)*(p.SMFCF-p.SMW) + p.SMW

        # 缺水时蒸腾速率的还原因子 (RFWS)
        RFWS = limit(0., 1., (SM-p.SMW)/(SMCR-p.SMW))
        
        # 氧气胁迫还原因子设为1
        RFOS = 1.0

        # 实际蒸腾速率，乘以氧气与缺水还原因子
        r.TRA = r.TRAMX * RFOS * RFWS

        return (r.TRA, r.TRAMX)