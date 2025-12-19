# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Herman Berghuijs (herman.berghuijs@wur.nl) 和 Allard de Wit (allard.dewit@wur.nl)，2024年1月

import numpy as np
from .. import exceptions as exc
from pcse.decorators import prepare_rates, prepare_states
from pcse.base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject
from pcse import signals
from ..traitlets import Float, Int, Instance, Bool
# from .soiln_profile import SoilNProfile


class SNOMIN(SimulationObject):
    """
    SNOMIN（土壤无机和矿质氮模块，Soil Nitrogen module for Mineral and Inorganic Nitrogen）是一个分层土壤氮平衡模型。该模型的完整数学描述详见 Berghuijs 等（2024）。

    Berghuijs HNC, Silva JV, Reidsma P, De Wit AJW (2024) 扩展 WOFOST 作物模型以探索可持续氮管理方案：以荷兰冬小麦为例。European Journal of Agronomy 154 ARTN 127099. https://doi.org/10.1016/j.eja.2024.127099

    **模拟参数:**

    ========== ====================================================  ====================
     名称      描述                                                  单位
    ========== ====================================================  ====================
    A0SOM      土壤有机质初始年龄                                     年
    CNRatioBio 微生物生物量C:N比                                       kg C kg-1 N
    FASDIS     同化与异化的比例                                       -
    KDENIT_REF 参考一级反硝化速率常数                                  d-1
    KNIT_REF   参考一级硝化速率常数                                   d-1
    KSORP      铵的吸附系数（m3水/kg土壤）                            m3土壤 kg-1土壤
    MRCDIS     反硝化作用对应土壤呼吸的米氏常数                        kg C m-2 d-1
    NO3ConcR   降雨中NO3-N浓度                                        mg NO3--N L-水
    NH4ConcR   降雨中NH4-N浓度                                        mg NH4+-N L-1水
    NO3I       NO3-N的初始量 :sup:`1`                                  kg NO3--N ha-1
    NH4I       NH4-N的初始量 :sup:`1`                                  kg NH4+-N ha-1
    WFPS_CRIT  临界土壤孔隙水充满度                                    m3水 m-3孔隙
    ========== ====================================================  ====================

    :sup:`1` 该状态变量对每个土层分别定义

    **状态变量:**

    ========== ====================================================  ==============
     名称      描述                                                  单位
    ========== ====================================================  ==============
    AGE        土壤修正物的表观年龄 (d) :sup:`1`                        d
    ORGMAT     有机质含量 (kg ORG ha-1) :sup:`1`                        kg OM m-2
    CORG       有机质中碳含量 (kg C ha-1) :sup:`1`                      kg C m-2
    NORG       有机质中氮含量 (kg N ha-1) :sup:`1`                      kg N m-2
    NH4        NH4-N含量 (kg N ha-1) :sup:`2`                           kg NH4-N m-2
    NO3        NO3-N含量 (kg N ha-1) :sup:`2`                           kg NO3-N m-2
    ========== ====================================================  ==============

    | :sup:`1` 该状态变量对每个土层和修正物组合定义
    | :sup:`2` 该状态变量对每个土层分别定义

    **变化率变量:**

    ========== ==================================================  ====================
     名称      描述                                                单位
    ========== ==================================================  ====================
    RAGE       表观年龄变化速率 :sup:`2`                           d d-1
    RAGEAM     初始表观年龄 :sup:`2`                               d d-1
    RAGEAG     修正物老化速率 :sup:`2`                              d d-1
    RCORG      有机碳变化速率 :sup:`2`                              kg C m-2 d-1
    RCORGAM    有机碳施加速率 :sup:`2`                              kg C m-2 d-1
    RCORGDIS   有机碳异化速率 :sup:`2`                              kg C m-2 d-1
    RNH4       NH4+-N变化速率 :sup:`1`                              kg NH4+-N m-2 d-1
    RNH4AM     NH4+-N施加速率 :sup:`1`                              kg NH4+-N m-2 d-1
    RNH4DEPOS  NH4-N沉积速率 :sup:`1`                               kg NH4+-N m-2 d-1
    RNH4IN     邻近层流入NH4+-N速率 :sup:`1`                         kg NH4+-N m-2 d-1
    RNH4MIN    净矿化速率 :sup:`1`                                  kg NH4+-N m-2 d-1
    RNH4NITR   硝化速率 :sup:`1`                                    kg NH4+-N m-2 d-1
    RNH4OUT    流出到邻层NH4+-N速率 :sup:`1`                         kg NH4+-N m-2 d-1
    RNH4UP     NH4+-N根系吸收速率 :sup:`1`                           kg NH4+-N m-2 d-1
    RNO3       NO3--N变化速率 :sup:`1`                              kg NO3--N m-2 d-1
    RNO3AM     NO3--N施加速率 :sup:`1`                              kg NO3--N m-2 d-1
    RNO3DENITR 反硝化速率 :sup:`1`                                  kg NO3--N m-2 d-1
    RNO3DEPOS  NO3--N沉积速率 :sup:`1`                               kg NO3--N m-2 d-1
    RNO3IN     邻近层流入NO3--N速率 :sup:`1`                         kg NO3--N m-2 d-1
    RNO3NITR   硝化速率 :sup:`1`                                    kg NO3--N m-2 d-1
    RNO3OUT    流出到邻层NO3--N速率 :sup:`1`                         kg NO3--N m-2 d-1
    RNO3UP     NO3--N根系吸收速率 :sup:`1`                           kg NO3--N m-2 d-1
    RNORG      有机氮变化速率 :sup:`2`                              kg N m-2 d-1
    RNORGAM    有机氮施加速率 :sup:`2`                              kg N m-2 d-1
    RNORGDIS   有机质异化速率 :sup:`2`                              kg N m-2 d-1
    RORGMAT    有机质变化速率 :sup:`2`                              kg OM m-2 d-1
    RORGMATAM  有机质施加速率 :sup:`2`                              kg OM m-2 d-1
    RORGMATDIS 有机质异化速率 :sup:`2`                              kg OM m-2 d-1
    ========== ==================================================  ====================

    | :sup:`1` 该状态变量对每个土层分别定义
    | :sup:`2` 该状态变量对每个土层和修正物组合定义

    **发送或接收的信号**

    `SNOMIN` 接收下列信号:
        * APPLY_N_SNOMIN：当通过外部输入提供N肥时将接收到。详见 `_on_APPLY_N_SNOMIN()` 及 `signals.apply_n_snomin`。
    """

    # 占位符初始值
    _ORGMATI = None
    _CORGI = None
    _NORGI = None
    _NH4I = None
    _NO3I = None

    # 占位符
    _RNO3AM = None
    _RNH4AM = None
    _RAGEAM = None
    _RORGMATAM = None
    _RCORGAM = None
    _RNORGAM = None

    # 单位换算
    g_to_kg = 1e-3      # 克转千克
    cm_to_m = 1e-2      # 厘米转米
    cm2_to_ha = 1e-8    # 平方厘米转公顷
    cm3_to_m3 = 1e-6    # 立方厘米转立方米
    ha_to_m2 = 1e-4     # 公顷转平方米
    m2_to_ha = 1e-4     # 平方米转公顷
    y_to_d = 365.25     # 年转天

    # 土壤对象占位符
    soiln_profile = None

    class StateVariables(StatesTemplate):
        AGE0   = Instance(np.ndarray) # 物质初始表观年龄 (天)
        AGE    = Instance(np.ndarray) # 物质表观年龄 (天)
        ORGMAT = Instance(np.ndarray) # 有机质含量 (kg ORG ha-1)
        CORG   = Instance(np.ndarray) # 有机质中的碳含量 (kg C ha-1)
        NORG   = Instance(np.ndarray) # 有机质中的氮含量
        NH4    = Instance(np.ndarray) # NH4-N 含量 (kg N ha-1)
        NO3    = Instance(np.ndarray) # NO3-N 含量 (kg N ha-1)
        NAVAIL = Float()  # 土壤及肥料中无机氮总量  kg N ha-1
        NDENITCUM = Float()      # 反硝化累积量
        NO3LEACHCUM = Float()    # NO3 流失累计量
        NH4LEACHCUM = Float()    # NH4 流失累计量
        NLOSSCUM = Float()       # 氮损失累计量

        RORGMATDISTT = Float()   # 有机质异化总速率
        RORGMATAMTT = Float()    # 有机质施加总速率
        RCORGDISTT = Float()     # 有机碳异化总速率
        RCORGAMTT = Float()      # 有机碳施加总速率
        RNORGDISTT = Float()     # 有机氮异化总速率
        RNORGAMTT = Float()      # 有机氮施加总速率

        RNO3NITRTT = Float()     # 硝化总速率
        RNO3DENITRTT = Float()   # 反硝化总速率
        RNO3UPTT = Float()       # NO3 吸收总速率
        RNO3INTT = Float()       # NO3 进入总速率
        RNO3OUTTT = Float()      # NO3 流出总速率
        RNO3AMTT = Float()       # NO3 施加总速率
        RNO3DEPOSTT = Float()    # NO3 沉积总速率

        RNH4MINTT = Float()      # NH4 净矿化总速率
        RNH4NITRTT = Float()     # NH4 硝化总速率
        RNH4UPTT = Float()       # NH4 吸收总速率
        RNH4INTT = Float()       # NH4 进入总速率
        RNH4OUTTT = Float()      # NH4 流出总速率
        RNH4AMTT = Float()       # NH4 施加总速率
        RNH4DEPOSTT = Float()    # NH4 沉积总速率

        ORGMATT = Float()        # 有机质总量
        CORGT = Float()          # 有机碳总量
        NORGT = Float()          # 有机氮总量
        RMINT = Float()          # 净矿化速率总量
        NH4T = Float()           # NH4 总量
        NO3T = Float()           # NO3 总量

    class RateVariables(RatesTemplate):
        RAGE = Instance(np.ndarray)         # 表观年龄变化率
        RORGMAT = Instance(np.ndarray)      # 有机质变化率
        RCORG = Instance(np.ndarray)        # 有机碳变化率
        RNORG = Instance(np.ndarray)        # 有机氮变化率

        RAGEAG = Instance(np.ndarray)       # 修正物老化速率

        RORGMATDIS = Instance(np.ndarray)   # 有机质异化速率
        RCORGDIS = Instance(np.ndarray)     # 有机碳异化速率
        RNORGDIS = Instance(np.ndarray)     # 有机氮异化速率

        RAGEAM = Instance(np.ndarray)       # 初始表观年龄
        RORGMATAM = Instance(np.ndarray)    # 有机质施加速率
        RCORGAM = Instance(np.ndarray)      # 有机碳施加速率
        RNORGAM = Instance(np.ndarray)      # 有机氮施加速率

        RNH4 = Instance(np.ndarray)         # NH4-N 变化速率
        RNH4MIN = Instance(np.ndarray)      # 净矿化速率
        RNH4NITR = Instance(np.ndarray)     # NH4-N 硝化速率
        RNH4UP = Instance(np.ndarray)       # NH4-N 根系吸收速率
        RNH4IN = Instance(np.ndarray)       # 邻近层流入NH4-N速率
        RNH4OUT = Instance(np.ndarray)      # NH4-N流出到邻层速率
        RNH4AM = Instance(np.ndarray)       # NH4-N施加速率
        RNH4DEPOS = Instance(np.ndarray)    # NH4-N沉积速率

        RNO3 = Instance(np.ndarray)         # NO3-N变化速率
        RNO3NITR = Instance(np.ndarray)     # 硝化速率
        RNO3DENITR = Instance(np.ndarray)   # 反硝化速率
        RNO3UP = Instance(np.ndarray)       # NO3-N根系吸收速率
        RNO3IN = Instance(np.ndarray)       # 邻近层流入NO3-N速率
        RNO3OUT = Instance(np.ndarray)      # NO3-N流出到邻层速率
        RNO3AM = Instance(np.ndarray)       # NO3-N施加速率
        RNO3DEPOS = Instance(np.ndarray)    # NO3-N沉积速率

        RNH4LEACHCUM = Float()              # NH4-N 流失累计量
        RNO3LEACHCUM = Float()              # NO3-N 流失累计量
        RNDENITCUM = Float()                # 反硝化累计量
        RNLOSS = Float()                    # 氮损失量

    class Parameters(ParamTemplate):
        A0SOM = Float()             # 腐殖质初始年龄 (年)
        CNRatioBio = Float()        # 微生物生物量C:N比 (kg C kg-1 N)
        FASDIS = Float()            # 同化/异化比例 (kg ORG kg-1 ORG)
        KDENIT_REF = Float()        # 参考一级反硝化速率常数 (d-1)
        KNIT_REF = Float()          # 参考一级硝化速率常数 (d-1)
        KSORP = Float()             # 铵离子吸附系数 (m3水 kg-1土壤)
        MRCDIS = Float()            # 反硝化对土壤呼吸反应因子的米氏常数
        NO3ConcR = Float()          # 降雨中NO3-N浓度 (mg N L-1)
        NH4ConcR = Float()          # 降雨中NH4-N浓度 (mg N L-1)
        NO3I = Instance(list)       # 初始NO3-N含量 (kg N ha-1)
        NH4I = Instance(list)       # 初始NH4-N含量 (kg N ha-1)
        WFPS_CRIT = Float()         # 反硝化的临界孔隙含水率 (m3水 m-3孔隙)

    def initialize(self, day, kiosk, parvalues):
        self.kiosk  = kiosk
        self.params = self.Parameters(parvalues)
        if "soil_profile" not in parvalues:
            msg = "Cannot find 'soil_profile' object in `parvalues`. The 'soil_profile' object should be " \
                  "instantiated by the multi-layer waterbalance before SNOMIN can run. It looks like SNOMIN " \
                  "was started before the waterbalance."
            raise exc.PCSEError(msg)
        self.soiln_profile = parvalues["soil_profile"]

        # 初始化模块
        sinm = self.SoilInorganicNModel()

        # 初始化状态变量
        # parvalues._soildata["soil_profile"] = self.soiln_profile
        NH4 = np.zeros(len(self.soiln_profile))
        NO3 = np.zeros_like(NH4)
        AGE =  np.zeros((1, len(self.soiln_profile)))
        AGE0 = np.zeros_like(AGE)
        ORGMAT = np.zeros_like(AGE)
        CORG =  np.zeros_like(AGE)
        NORG =  np.zeros_like(AGE)
        minip_C = self.SoilOrganicNModel.MINIP_C()
        for il, layer in enumerate(self.soiln_profile):
            NH4[il] = self.params.NH4I[il] * self.m2_to_ha
            NO3[il] = self.params.NO3I[il] * self.m2_to_ha
            AGE0[0,il] = self.params.A0SOM * self.y_to_d
            AGE[0,il] = self.params.A0SOM * self.y_to_d
            ORGMAT[0,il] = layer.RHOD_kg_per_m3 * layer.FSOMI * layer.Thickness_m
            CORG[0,il] = minip_C.calculate_organic_C(ORGMAT[0,il])
            NORG[0,il] = CORG[0, il] / layer.CNRatioSOMI

        states = dict(
            NH4 = NH4,
            NO3 = NO3,
            AGE = AGE,
            AGE0 = AGE0,
            ORGMAT = ORGMAT,
            CORG =  CORG,
            NORG =  NORG,

            # 初始化有机质质量衡算校验的状态变量
            RORGMATDISTT = 0.,
            RORGMATAMTT = 0.,

            # 初始化有机碳质量衡算校验的状态变量
            RCORGDISTT = 0.,
            RCORGAMTT = 0.,

            # 初始化有机氮质量衡算校验的状态变量
            RNORGDISTT = 0.,
            RNORGAMTT = 0.,

            # 初始化铵态氮（NH4-N）质量衡算校验的状态变量
            RNH4MINTT = 0.,
            RNH4NITRTT = 0.,
            RNH4UPTT = 0.,
            RNH4INTT = 0.,
            RNH4OUTTT = 0.,
            RNH4AMTT = 0.,
            RNH4DEPOSTT = 0.,

            # 初始化硝态氮（NO3-N）质量衡算校验的状态变量
            RNO3NITRTT = 0.,
            RNO3DENITRTT = 0.,
            RNO3UPTT = 0.,
            RNO3INTT = 0.,
            RNO3OUTTT = 0.,
            RNO3AMTT = 0.,
            RNO3DEPOSTT = 0.,

            # 初始化输出变量
            CORGT = np.sum(CORG) / self.m2_to_ha,
            NORGT = np.sum(NORG) / self.m2_to_ha,
            ORGMATT = np.sum(ORGMAT) / self.m2_to_ha,
            RMINT = 0.,
            NH4T = np.sum(NH4)/ self.m2_to_ha,
            NO3T = np.sum(NO3)/ self.m2_to_ha,
            NAVAIL = 0.,
            NH4LEACHCUM = 0.,
            NO3LEACHCUM = 0.,
            NDENITCUM = 0.,
            NLOSSCUM = 0.,
        )

        self.states = self.StateVariables(kiosk, publish=["NAVAIL", "ORGMATT", "CORGT", "NORGT"], **states)
        self.rates = self.RateVariables(kiosk)

        self._RAGEAM = np.zeros_like(AGE)
        self._RORGMATAM = np.zeros_like(ORGMAT)
        self._RCORGAM = np.zeros_like(CORG)
        self._RNORGAM = np.zeros_like(NORG)
        self._RNH4AM = np.zeros_like(NH4)
        self._RNO3AM = np.zeros_like(NO3)

        self._ORGMATI = ORGMAT
        self._CORGI = CORG
        self._NORGI = NORG
        self._NH4I = NH4
        self._NO3I = NO3

        # 连接模块至AgroManager信号
        self._connect_signal(self._on_APPLY_N_SNOMIN, signals.apply_n_snomin)

    @prepare_rates
    def calc_rates(self, day, drv):
        k = self.kiosk
        r = self.rates
        s = self.states
        p = self.params

        delt = 1.0

        # 初始化模型组件
        sonm = self.SoilOrganicNModel()
        sinm = self.SoilInorganicNModel()

        # 获取外部变量，并转换为正确单位
        infiltration_rate_m_per_d = self.get_infiltration_rate(k)
        flow_m_per_d = self.get_water_flow_rates(k)
        N_demand_soil = self.get_N_demand(k)
        RD_m = self.get_root_length(k)
        SM = self.get_soil_moisture_content(k)
        pF = self.get_pF(self.soiln_profile, SM)
        T = drv.TEMP

        # 获取土壤pH值
        pH = self.get_pH(self.soiln_profile)

        # 收集施肥速率
        r.RAGEAM = self._RAGEAM
        r.RORGMATAM = self._RORGMATAM
        r.RCORGAM = self._RCORGAM
        r.RNORGAM = self._RNORGAM
        r.RNH4AM = self._RNH4AM
        r.RNO3AM = self._RNO3AM

        # 重置施肥速率的占位数组
        self._RAGEAM = np.zeros_like(s.AGE)
        self._RORGMATAM = np.zeros_like(r.RORGMATAM)
        self._RCORGAM = np.zeros_like(r.RCORGAM)
        self._RNORGAM = np.zeros_like(r.RNORGAM)
        self._RNH4AM = np.zeros_like(r.RNH4)
        self._RNO3AM = np.zeros_like(r.RNH4)

        # 计算每个有机物施肥的表观年龄增长速率
        r.RAGEAG = sonm.calculate_apparent_age_increase_rate(s.AGE, delt, pF, pH, T)

        # 计算各个有机物施肥的分解速率
        r.RORGMATDIS, r.RCORGDIS, r.RNORGDIS = \
            sonm.calculate_dissimilation_rates(s.AGE, p.CNRatioBio, p.FASDIS, s.NORG, s.ORGMAT, pF, pH, T)

        # 计算表观年龄、有机质、有机碳、有机氮的变化速率
        r.RAGE = r.RAGEAG + r.RAGEAM
        r.RORGMAT = r.RORGMATAM - r.RORGMATDIS
        r.RCORG = r.RCORGAM - r.RCORGDIS
        r.RNORG = r.RNORGAM - r.RNORGDIS

        # 计算无机氮的吸收速率
        r.RNH4UP, r.RNO3UP = sinm.calculate_N_uptake_rates(self.soiln_profile, delt, p.KSORP, N_demand_soil,
                                                           s.NH4, s.NO3, RD_m, SM)

        # 计算NH4-N和NO3-N吸收后的剩余量，并进行化学转化
        NH4PRE = s.NH4 - r.RNH4UP * delt
        NO3PRE = s.NO3 - r.RNO3UP * delt
        r.RNH4MIN, r.RNH4NITR, r.RNO3NITR, r.RNO3DENITR = \
            sinm.calculate_reaction_rates(self.soiln_profile, p.KDENIT_REF, p.KNIT_REF, p.KSORP, p.MRCDIS,
                                          NH4PRE, NO3PRE, r.RCORGDIS, r.RNORGDIS, SM, T, p.WFPS_CRIT)

        # 对每一层：如果净矿化速率为负（净固持），且该层NH4-N不足，则只能利用反硝化剩余的N参与固持，同时RNORGDIS也被更新以保证氮平衡
        for il, layer in enumerate(self.soiln_profile):
            if NH4PRE[il] + (r.RNH4MIN[il] - r.RNH4NITR[il]) * delt < 0:
                r.RNH4MIN[il] = NH4PRE[il] - r.RNH4NITR[il]
                RNORDIST = r.RNORGDIS[:,il].sum()
                for iam in range(0,len(r.RNORGDIS[:,il])):
                    r.RNORGDIS[iam,il] = (r.RNH4MIN[il] / RNORDIST) * r.RNORGDIS[iam,il]
            r.RNORG = r.RNORGAM - r.RNORGDIS

        # 计算沉降速率
        r.RNH4DEPOS, r.RNO3DEPOS = sinm.calculate_deposition_rates(self.soiln_profile, infiltration_rate_m_per_d,
                                                                   s.NH4, p.NH4ConcR, s.NO3, p.NO3ConcR)

        # 计算NH4-N和NO3-N吸收及反应后的剩余量，并计算层间的无机氮流动速率
        NH4PRE2 = NH4PRE + (r.RNH4AM + r.RNH4MIN + r.RNH4DEPOS - r.RNH4NITR) * delt
        NO3PRE2 = NO3PRE + (r.RNO3AM + r.RNO3NITR + r.RNO3DEPOS  - r.RNO3DENITR) * delt
        r.RNH4IN, r.RNH4OUT, r.RNO3IN, r.RNO3OUT = \
            sinm.calculate_flow_rates(self.soiln_profile, flow_m_per_d, p.KSORP, NH4PRE2, NO3PRE2, SM)

        # 计算NH4-N和NO3-N的变化速率
        r.RNH4 = r.RNH4AM + r.RNH4MIN + r.RNH4DEPOS - r.RNH4NITR - r.RNH4UP + r.RNH4IN - r.RNH4OUT
        r.RNO3 = r.RNO3AM + r.RNO3NITR + r.RNO3DEPOS - r.RNO3DENITR - r.RNO3UP + r.RNO3IN - r.RNO3OUT

        # 计算N损失的输出速率变量
        r.RNH4LEACHCUM =  (1/self.m2_to_ha) * r.RNH4OUT[-1]
        r.RNO3LEACHCUM =  (1/self.m2_to_ha) * r.RNO3OUT[-1]
        r.RNDENITCUM = (1/self.m2_to_ha) * r.RNO3DENITR.sum()

    @prepare_states
    def integrate(self, day, delt=1.0):
        k = self.kiosk
        p = self.params
        r = self.rates
        s = self.states

        # 初始化土壤模块
        sinm = self.SoilInorganicNModel()

        # 计算下一个时刻有机物质、有机碳和有机氮以及表观年龄
        AGE = s.AGE + r.RAGE * delt
        ORGMAT = s.ORGMAT + r.RORGMAT * delt
        CORG = s.CORG + r.RCORG * delt
        NORG= s.NORG + r.RNORG * delt

        # 计算下一个时刻NH4-N和NO3-N的数值
        NH4 = s.NH4 + r.RNH4 * delt
        NO3 = s.NO3 + r.RNO3 * delt

        # 更新状态变量
        s.AGE = AGE
        s.ORGMAT = ORGMAT
        s.CORG = CORG
        s.NORG = NORG
        s.NH4 = NH4
        s.NO3 = NO3

        # 获取外部根长状态变量和土壤含水量
        RD_m = self.get_root_length(k)
        SM = self.get_soil_moisture_content(k)

        # 计算下一个时刻根可吸收的N
        s.NAVAIL = sinm.calculate_NAVAIL(self.soiln_profile, p.KSORP, s.NH4, s.NO3, RD_m, SM) / self.m2_to_ha
        self.check_mass_balances(day, delt)

        # 设置输出变量
        s.ORGMATT = np.sum(s.ORGMAT)  * (1/self.m2_to_ha)
        s.CORGT = np.sum(s.CORG)  * (1/self.m2_to_ha)
        s.NORGT = np.sum(s.NORG)  * (1/self.m2_to_ha)
        s.RMINT += np.sum(r.RNORGDIS) * (1/self.m2_to_ha)
        s.NH4T = np.sum(s.NH4) * (1/self.m2_to_ha)
        s.NO3T = np.sum(s.NO3) * (1/self.m2_to_ha)
        NH4LEACHCUM = s.NH4LEACHCUM + r.RNH4LEACHCUM * delt
        NO3LEACHCUM = s.NO3LEACHCUM + r.RNO3LEACHCUM * delt
        NDENITCUM = s.NDENITCUM + r.RNDENITCUM * delt
        NLOSSCUM =  NH4LEACHCUM + NO3LEACHCUM + NDENITCUM
        s.NH4LEACHCUM = NH4LEACHCUM
        s.NO3LEACHCUM = NO3LEACHCUM
        s.NDENITCUM = NDENITCUM
        s.NLOSSCUM = NLOSSCUM

    def _on_APPLY_N_SNOMIN(self, amount=None, application_depth = None, cnratio=None, f_orgmat=None,
                           f_NH4N = None, f_NO3N = None, initial_age =None):
        """本函数在施用日期计算有机物质、有机碳、有机氮、NH4-N、NO3-N的施用速率，以及施用品的初始表观年龄。

        对于每次施用，下列变量需要在仿真的AgroManagement文件中指定：

        **施用物性质**
        ================== ======================================================    =========================
         名称              描述                                                        单位
        ================== ======================================================    =========================
        amount             施用物质的总量                                              kg material ha-1
        application_depth  施用物质在土壤中的分布深度                                  cm
        cnratio            施用物中有机物质的C:N比                                     kg C kg-1 N
        initial_age        施用物中有机物质的初始表观年龄                              y
        f_NH4N             施用物中NH4+-N的比例                                       kg NH4+-N kg-1 material
        f_NO3N             施用物中NO3--N的比例                                       kg NO3--N kg-1 material
        f_orgmat           施用物中有机物质的比例                                     kg OM kg-1 material
        ================== ======================================================    =========================
        """

        r = self.rates
        s = self.states
        delt = 1.

        # 创建模型组件
        sinm = self.SoilInorganicNModel()
        sonm = self.SoilOrganicNModel()

        # 初始化施用速率
        RAGE_am = np.zeros((1, len(self.soiln_profile)))
        AGE0_am = np.zeros_like(RAGE_am)
        RORGMAT_am = np.zeros_like(RAGE_am)
        RCORG_am = np.zeros_like(RAGE_am)
        RNORG_am = np.zeros_like(RAGE_am)
        RNH4_am = np.zeros_like(s.NH4)
        RNO3_am = np.zeros_like(s.NO3)

        # 若施用深度小于顶层厚度，则自动将其调整为顶层厚度，确保N不会部分未被施用
        if application_depth < self.soiln_profile[0].Thickness:
            application_depth = self.soiln_profile[0].Thickness

        AGE0_am[0, :] = initial_age * self.y_to_d
        RAGE_am[0, :] = initial_age * self.y_to_d
        RNH4_am, RNO3_am = np.array(sinm.calculate_N_application_amounts(self.soiln_profile, amount, application_depth,
                                                                          f_NH4N, f_NO3N)) * self.m2_to_ha
        RORGMAT_am, RCORG_am, RNORG_am = np.array(sonm.calculate_application_rates(self.soiln_profile, amount,
                                                                                   application_depth, cnratio, f_orgmat)
                                                  ) * self.m2_to_ha

        # 有机物施用时添加新列以扩展状态变量，纳入新的施用
        s.AGE0 = np.concatenate((s.AGE0, AGE0_am), axis = 0)
        s.ORGMAT = np.concatenate((s.ORGMAT, np.zeros((1, len(self.soiln_profile)))), axis = 0)
        s.CORG = np.concatenate((s.CORG, np.zeros((1, len(self.soiln_profile)))), axis = 0)
        s.NORG = np.concatenate((s.NORG, np.zeros((1, len(self.soiln_profile)))), axis = 0)
        s.AGE = np.concatenate((s.AGE, np.zeros((1, len(self.soiln_profile)))), axis = 0)

        # 存储施用速率
        self._RAGEAM = np.concatenate((self._RAGEAM, RAGE_am), axis = 0)
        self._RORGMATAM = np.concatenate((self._RORGMATAM, RORGMAT_am), axis = 0)
        self._RCORGAM = np.concatenate((self._RCORGAM, RCORG_am), axis = 0)
        self._RNORGAM = np.concatenate(( self._RNORGAM, RNORG_am), axis = 0)
        self._RNH4AM = RNH4_am
        self._RNO3AM = RNO3_am

    def get_infiltration_rate(self, k):
        # 获取入渗速率，单位为m/d
        infiltration_rate_m_per_d = k.RIN * self.cm_to_m
        return infiltration_rate_m_per_d

    def get_pF(self, soiln_profile, SM):
        # 计算各层土壤的pF值
        pF = np.zeros_like(SM)
        for il, layer in enumerate(soiln_profile):
            pF[il] = layer.PFfromSM(SM[il])
        return pF

    def get_pH(self, soiln_profile):
        # 获取各层土壤pH值
        pH = np.zeros(len(soiln_profile))
        for il, layer in enumerate(soiln_profile):
            pH[il] = layer.Soil_pH
        return pH

    def get_soil_moisture_content(self, k):
        # 获取土壤含水量
        SM = k.SM
        return SM

    def get_water_flow_rates(self, k):
        # 获取水分流动速率，单位为m/d
        flow_m_per_d = k.Flow * self.cm_to_m
        return flow_m_per_d

    def get_N_demand(self, k):
        # 获取土壤N养分需求
        if "RNuptake" in k:
            N_demand_soil = k.RNuptake * self.m2_to_ha
        else:
            N_demand_soil = 0.
        return N_demand_soil

    def get_root_length(self, k):
        # 获取根系长度，单位为m
        if "RD" in k:
            RD_m = k.RD * self.cm_to_m
        else:
            RD_m = 0.
        return RD_m

    def check_mass_balances(self, day, delt):
        s = self.states
        r = self.rates

        # 更新各累积速率变量
        s.RORGMATAMTT += delt * r.RORGMATAM.sum()
        s.RORGMATDISTT += delt * r.RORGMATDIS.sum()
        s.RCORGAMTT += delt * r.RCORGAM.sum()
        s.RCORGDISTT += delt * r.RCORGDIS.sum()
        s.RNORGAMTT += delt * r.RNORGAM.sum()
        s.RNORGDISTT += delt * r.RNORGDIS.sum()

        s.RNH4MINTT += delt * r.RNH4MIN.sum()
        s.RNH4NITRTT += delt * r.RNH4NITR.sum()
        s.RNH4UPTT += delt * r.RNH4UP.sum()
        s.RNH4INTT += delt * r.RNH4IN.sum()
        s.RNH4OUTTT += delt * r.RNH4OUT.sum()
        s.RNH4AMTT += delt * r.RNH4AM.sum()
        s.RNH4DEPOSTT += delt * r.RNH4DEPOS.sum()

        s.RNO3NITRTT += delt * r.RNO3NITR.sum()
        s.RNO3DENITRTT += delt * r.RNO3DENITR.sum()
        s.RNO3UPTT += delt * r.RNO3UP.sum()
        s.RNO3INTT += delt * r.RNO3IN.sum()
        s.RNO3OUTTT += delt * r.RNO3OUT.sum()
        s.RNO3AMTT += delt * r.RNO3AM.sum()
        s.RNO3DEPOSTT += delt * r.RNO3DEPOS.sum()

        # 有机质质量平衡校验
        ORGMATBAL = self._ORGMATI.sum() - s.ORGMAT.sum() + s.RORGMATAMTT - s.RORGMATDISTT
        if abs(ORGMATBAL) > 0.0001:
            msg = "Organic matter mass balance is not closing on %s with checksum: %f" % (day, ORGMATBAL)
            raise exc.SoilOrganicMatterBalanceError(msg)

        # 有机碳质量平衡校验
        CORGBAL = self._CORGI.sum() - s.CORG.sum() + s.RCORGAMTT - s.RCORGDISTT
        if abs(CORGBAL) > 0.0001:
            msg = "Organic carbon mass balance is not closing on %s with checksum: %f" % (day, CORGBAL)
            raise exc.SoilOrganicCarbonBalanceError(msg)

        # 有机氮质量平衡校验
        NORGBAL = self._NORGI.sum() - s.NORG.sum() + s.RNORGAMTT - s.RNORGDISTT
        if abs(NORGBAL) > 0.0001:
            msg = "Organic carbon mass balance is not closing on %s with checksum: %f" % (day, NORGBAL)
            raise exc.SoilOrganicNitrogenBalanceError(msg)

        # 铵态氮质量平衡校验
        NH4BAL = self._NH4I.sum() - s.NH4.sum() + s.RNH4AMTT + s.RNH4INTT + s.RNH4MINTT + s.RNH4DEPOSTT - s.RNH4NITRTT - s.RNH4OUTTT - s.RNH4UPTT
        if abs(NH4BAL) > 0.0001:
            msg = "NH4-N mass balance is not closing on %s with checksum: %f" % (day, NH4BAL)
            raise exc.SoilAmmoniumBalanceError(msg)

        # 硝态氮质量平衡校验
        NO3BAL = self._NO3I.sum() - s.NO3.sum() + s.RNO3AMTT + s.RNO3NITRTT + s.RNO3INTT + s.RNO3DEPOSTT - s.RNO3DENITRTT - s.RNO3OUTTT - s.RNO3UPTT
        if abs(NO3BAL) > 0.0001:
            msg = "NO3-N mass balance is not closing on %s with checksum: %f" % (day, NO3BAL)
            raise exc.SoilNitrateBalanceError(msg)

    class SoilInorganicNModel:
        def calculate_N_application_amounts(self, soiln_profile, amount, application_depth, f_NH4N, f_NO3N):
            # 计算氮施用量
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            RNH4_am = np.zeros(len(soiln_profile))
            RNO3_am = np.zeros_like(RNH4_am)
            zmin = 0
            for il, layer in enumerate(soiln_profile):
                zmax = zmin + soiln_profile[il].Thickness
                RNH4_am[il] = samm.calculate_NH4_application_amount(amount, application_depth, f_NH4N, layer.Thickness, zmax, zmin)
                RNO3_am[il] = sni.calculate_NO3_application_amount(amount, application_depth, f_NO3N, layer.Thickness, zmax, zmin)
                zmin = zmax
            return RNH4_am, RNO3_am

        def calculate_flow_rates(self, soiln_profile, flow_m_per_d, KSORP, NH4, NO3, SM):
            # 计算水流速率带来的NH4和NO3的输入与输出
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            RNH4IN, RNH4OUT = samm.calculate_NH4_flow_rates(soiln_profile, flow_m_per_d, KSORP, NH4, SM)
            RNO3IN, RNO3OUT = sni.calculate_NO3_flow_rates(soiln_profile, flow_m_per_d, NO3, SM)
            return RNH4IN, RNH4OUT, RNO3IN, RNO3OUT

        def calculate_deposition_rates(self,soiln_profile,infiltration_rate_m_per_d, NH4, NH4ConcR, NO3, NO3ConcR):
            # 计算NH4和NO3的沉降速率
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            RNH4DEPOS = samm.calculate_NH4_deposition_rates(soiln_profile, infiltration_rate_m_per_d, NH4, NH4ConcR)
            RNO3DEPOS = sni.calculate_NO3_deposition_rates(soiln_profile, infiltration_rate_m_per_d, NO3, NO3ConcR)
            return RNH4DEPOS, RNO3DEPOS

        def calculate_reaction_rates(self, soiln_profile, KDENIT_REF, KNIT_REF, KSORP, MRCDIS, NH4, NO3, RCORGDIS, RNORGDIS, SM, T, WFPS_CRIT):
            # 计算反应过程的速率，包括矿化、硝化、反硝化等
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            RNH4MIN, RNH4NITR = samm.calculate_NH4_reaction_rates(soiln_profile, KNIT_REF, KSORP, NH4, RNORGDIS, SM, T)
            RNO3NITR, RNO3DENITR = sni.calculate_NO3_reaction_rates(soiln_profile, KDENIT_REF, MRCDIS, NO3, RCORGDIS, RNH4NITR, SM, T, WFPS_CRIT)
            return RNH4MIN, RNH4NITR, RNO3NITR, RNO3DENITR

        def calculate_NAVAIL(self, soiln_profile, KSORP, NH4, NO3, RD_m, SM):
            # 计算根系可获得的氮素总量
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            zmin = 0.
            NAVAIL = 0.
            for il, layer in enumerate(soiln_profile):
                zmax = zmin + layer.Thickness_m
                NH4_avail_layer = samm.calculate_available_NH4(KSORP, NH4[il], RD_m, layer.RHOD_kg_per_m3, SM[il], zmax, zmin)
                NO3_avail_layer = sni.calculate_available_NO3(NO3[il], RD_m, SM[il], zmax, zmin)
                NAVAIL += (NH4_avail_layer + NO3_avail_layer)
                zmin = zmax
            return NAVAIL

        def calculate_N_uptake_rates(self, soiln_profile, delt, KSORP, N_demand_soil, NH4, NO3, RD_m, SM):
            # 计算NH4和NO3的植株吸收速率
            RNH4UP = np.zeros_like(NH4)
            RNO3UP = np.zeros_like(NO3)
            samm = self.SoilAmmoniumNModel()
            sni = self.SoilNNitrateModel()
            zmin = 0.
            for il, layer in enumerate(soiln_profile):
                zmax = zmin + layer.Thickness_m
                RNH4UP[il] = samm.calculate_NH4_plant_uptake_rate(KSORP, N_demand_soil, NH4[il], RD_m, layer.RHOD_kg_per_m3, SM[il], zmax, zmin)
                N_demand_soil -= RNH4UP[il] * delt
                RNO3UP[il] = sni.calculate_NO3_plant_uptake_rate(N_demand_soil, NO3[il], RD_m, SM[il], zmax, zmin)
                N_demand_soil -= RNO3UP[il] * delt
                zmin = zmax
            return RNH4UP, RNO3UP

        class SoilAmmoniumNModel:
            def calculate_NH4_deposition_rates(self, soiln_profile, infiltration_rate_m_per_d, NH4, NH4ConcR):
                """
                计算NH4的沉降速率
                """
                RNH4DEPOS = np.zeros_like(NH4)
                mg_to_kg = 1e-6
                L_to_m3 = 1e-3
                for il, layer in enumerate(soiln_profile):
                    if il == 0:
                        RNH4DEPOS[il] = (mg_to_kg / L_to_m3) * NH4ConcR * infiltration_rate_m_per_d
                    else:
                        RNH4DEPOS[il] = 0.
                return RNH4DEPOS

            def calculate_NH4_reaction_rates(self, soiln_profile, KNITREF, KSORP, NH4, RNORGDIS, SM, T):
                """
                计算NH4的反应速率，包括矿化和硝化
                """
                RNH4MIN = np.zeros_like(NH4)
                RNH4NITR = np.zeros_like(NH4)
                for il, layer in enumerate(soiln_profile):
                    RNMIN_kg_per_m2 = RNORGDIS[:,il].sum()
                    RNH4MIN[il] = self.calculate_mineralization_rate(RNMIN_kg_per_m2)
                    RNH4NITR[il] = self.calculate_nitrification_rate(KNITREF, KSORP, layer.Thickness_m, NH4[il], layer.RHOD_kg_per_m3, SM[il], layer.SM0, T)
                return RNH4MIN, RNH4NITR

            def calculate_NH4_flow_rates(self, soiln_profile, flow_m_per_d, KSORP, NH4, SM):
                """
                计算NH4的流动速率（包括上下向水流的NH4输入/输出）
                """
                cNH4Kwel = 0.

                RNH4IN = np.zeros_like(NH4)
                RNH4OUT = np.zeros_like(NH4)
                RHOD = np.zeros_like(NH4)
                cNH4 = np.zeros_like(NH4)
                dz = np.zeros_like(NH4)

                # 下向流动
                for il, layer in enumerate(soiln_profile):
                    RHOD[il] = layer.RHOD_kg_per_m3
                    dz[il] = layer.Thickness_m
                    cNH4[il] = self.calculate_NH4_concentration(KSORP, dz[il], NH4[il], RHOD[il], SM[il])

                for il in range(0,len(soiln_profile)):
                    if flow_m_per_d[il] >= 0.:
                        if il == 0:
                            RNH4IN[il] += 0.
                        else:
                            RNH4IN[il] += flow_m_per_d[il] * cNH4[il - 1]
                            RNH4OUT[il-1] += flow_m_per_d[il] * cNH4[il - 1]
                if flow_m_per_d[len(NH4) - 1] >= 0.:
                    RNH4OUT[len(NH4) - 1] += flow_m_per_d[len(NH4)] * cNH4[len(NH4) - 1]

                ## 上向流动
                for il in reversed(range(0,len(soiln_profile))):
                    if flow_m_per_d[il + 1] < 0.:
                        if il == len(NH4) - 1:
                            RNH4IN[il] += - flow_m_per_d[il + 1] * cNH4Kwel
                        else:
                            RNH4IN[il] += - flow_m_per_d[il + 1] * cNH4[il + 1]
                            RNH4OUT[il + 1] += - flow_m_per_d[il + 1] * cNH4[il + 1]
                if flow_m_per_d[0] < 0.:
                    RNH4OUT[0] += - flow_m_per_d[0] * cNH4[0]
                else:
                    RNH4OUT[0] += 0.
                return RNH4IN, RNH4OUT

            def calculate_NH4_application_amount(self, amount, application_depth, f_NH4N, layer_thickness, zmax, zmin):
                """
                计算每一土层施用的NH4量
                """
                if application_depth > zmax:
                    NH4_am = (layer_thickness / application_depth) * f_NH4N *  amount
                elif zmin <= application_depth <= zmax:
                    NH4_am = ((application_depth - zmin) / application_depth) * f_NH4N  * amount
                else:
                    NH4_am = 0.
                return NH4_am

            def calculate_NH4_concentration(self, KSORP, layer_thickness, NH4, RHOD_kg_per_m3, SM):
                """
                计算NH4的浓度（kg/m3）
                """
                cNH4 = (1 / ( KSORP * RHOD_kg_per_m3 + SM)) * NH4 / layer_thickness
                return cNH4

            def calculate_available_NH4(self, KSORP, NH4, RD, RHOD_kg_per_m3, SM, zmax, zmin):
                """
                计算本层可被根系吸收的NH4量
                """
                layer_thickness = zmax - zmin
                cNH4 = self.calculate_NH4_concentration(KSORP, layer_thickness, NH4, RHOD_kg_per_m3, SM)

                if RD <= zmin:
                    NH4_avail = 0.
                elif RD > zmax:
                    NH4_avail = (SM / ( KSORP * RHOD_kg_per_m3 + SM)) * NH4
                else:
                    NH4_avail = ((RD - zmin)/ layer_thickness) * (SM / ( KSORP * RHOD_kg_per_m3 + SM)) * NH4
                return NH4_avail

            def calculate_mineralization_rate(self, rNMINs_layer):
                """
                计算矿化速率
                """
                RNH4MIN = rNMINs_layer.sum()
                return RNH4MIN

            def calculate_nitrification_rate(self, KNIT_REF, KSORP, layer_thickness, NH4, RHOD_kg_per_m3, SM, SM0, T):
                """
                计算硝化速率
                """
                cNH4 = self.calculate_NH4_concentration(KSORP, layer_thickness, NH4, RHOD_kg_per_m3, SM)
                fWNIT = self.calculate_soil_moisture_response_nitrification_rate_constant(SM, SM0)
                fT = self.calculate_temperature_response_nitrification_rate_constant(T)
                RNH4NIT = fWNIT * fT *  KNIT_REF * SM * cNH4 * layer_thickness
                return RNH4NIT

            def calculate_NH4_plant_uptake_rate(self, KSORP, N_demand_soil, NH4, RD_m, RHOD_kg_per_m3, SM, zmax, zmin):
                """
                计算本层NH4的植株吸收速率
                """
                NH4_av = self.calculate_available_NH4(KSORP, NH4, RD_m, RHOD_kg_per_m3, SM, zmax, zmin)
                RNH4UP = min(N_demand_soil, NH4_av)
                return RNH4UP

            def calculate_soil_moisture_response_nitrification_rate_constant(self, SM, SM0):
                """
                土壤含水率对硝化速率常数的响应函数
                """
                WFPS = SM / SM0
                fWNIT = 0.9 / (1. + np.exp(-15 *(WFPS - 0.45))) + 0.1 - 1/(1+np.exp(-50. * (WFPS - 0.95)))
                return fWNIT

            def calculate_temperature_response_nitrification_rate_constant(self, T):
                """
                温度对硝化速率常数的响应函数
                """
                fT = 1/(1+np.exp(-0.26*(T-17.)))-1/(1+np.exp(-0.77*(T-41.9)))
                return fT

        class SoilNNitrateModel:
            def calculate_NO3_deposition_rates(self, soiln_profile, infiltration_rate_m_per_d, NO3, NO3ConcR):
                """
                计算NO3的沉降速率
                """
                mg_to_kg = 1e-6
                L_to_m3 = 1e-3
                RNO3DEPOS = np.zeros_like(NO3)
                for il, layer in enumerate(soiln_profile):
                    if il == 0:
                        RNO3DEPOS[il] = (mg_to_kg / L_to_m3) * NO3ConcR * infiltration_rate_m_per_d
                    else:
                        RNO3DEPOS[il] = 0.
                return RNO3DEPOS

            def calculate_NO3_flow_rates(self, soiln_profile, flow_m_per_d, NO3, SM):
                """
                计算NO3的流动速率（包括上下向水流的NO3输入/输出）
                """
                cNO3Kwel = 0.

                RNO3IN = np.zeros_like(NO3)
                RNO3OUT = np.zeros_like(NO3)
                cNO3 = np.zeros_like(NO3)
                dz = np.zeros_like(NO3)

                # 下向流动
                for il, layer in enumerate(soiln_profile):
                    dz[il] = layer.Thickness_m
                    cNO3[il] =  self.calculate_NO3_concentration(dz[il], NO3[il], SM[il])

                for il in range(0,len(soiln_profile)):
                    if flow_m_per_d[il] >= 0.:
                        if il == 0:
                            RNO3IN[il] += 0.
                        else:
                            RNO3IN[il] += flow_m_per_d[il] * cNO3[il - 1]
                            RNO3OUT[il-1] += flow_m_per_d[il] * cNO3[il - 1]
                if flow_m_per_d[len(NO3) - 1] >= 0.:
                    RNO3OUT[len(NO3) - 1] += flow_m_per_d[len(NO3)] * cNO3[len(NO3) - 1]
                else:
                    RNO3OUT[len(NO3) - 1] += 0

                # 上向流动
                for il in reversed(range(0,len(soiln_profile))):
                    if flow_m_per_d[il + 1] < 0.:
                        if il == len(NO3) - 1:
                            RNO3IN[il] += - flow_m_per_d[il + 1] * cNO3Kwel
                        else:
                            RNO3IN[il] += - flow_m_per_d[il + 1] * cNO3[il + 1]
                            RNO3OUT[il + 1] += - flow_m_per_d[il + 1] * cNO3[il + 1]
                if flow_m_per_d[0] < 0.:
                    RNO3OUT[0] += - flow_m_per_d[0] * cNO3[0]
                else:
                    RNO3OUT[0] += 0.
                return RNO3IN, RNO3OUT

            def calculate_NO3_reaction_rates(self, soiln_profile, KDENIT_REF, MRCDIS, NO3, RCORGDIS,
                                             RNH4NITR, SM, T, WFPS_CRIT):
                """
                计算NO3相关反应速率（硝化和反硝化）
                """
                RNO3NITR = np.zeros_like(NO3)
                RNO3DENITR = np.zeros_like(NO3)
                for il, layer in enumerate(soiln_profile):
                    RNO3NITR[il] = RNH4NITR[il]
                    RNO3DENITR[il] = \
                        self.calculate_denitrification_rate(layer.Thickness_m, NO3[il], KDENIT_REF, MRCDIS,
                                                            RCORGDIS[:,il].sum(), SM[il], layer.SM0, T, WFPS_CRIT)
                return RNO3NITR, RNO3DENITR

            def calculate_NO3_application_amount(self, amount, application_depth, f_NO3N, layer_thickness, zmax, zmin):
                """
                计算每一层NO3的施用量
                """
                if application_depth > zmax:
                    NO3_am = (layer_thickness / application_depth) * f_NO3N *  amount
                elif zmin <= application_depth <= zmax:
                    NO3_am = ((application_depth - zmin) / application_depth) * f_NO3N  * amount
                else:
                    NO3_am = 0.
                return NO3_am

            def calculate_NO3_concentration(self, layer_thickness, NO3, SM):
                """
                计算NO3的体积浓度
                """
                cNO3 = NO3 / (layer_thickness * SM)
                return cNO3

            def calculate_available_NO3(self, NO3, RD, SM, zmax, zmin):
                """
                计算某一层土壤根系可用的NO3
                """
                layer_thickness = zmax - zmin
                if RD <= zmin:
                    NO3_avail_layer = 0.
                elif RD > zmax:
                    NO3_avail_layer = NO3
                else:
                    NO3_avail_layer = ((RD - zmin)/ layer_thickness) * NO3
                return NO3_avail_layer

            def calculate_denitrification_rate(self, layer_thickness, NO3, KDENIT_REF, MRCDIS, RCORGT_kg_per_m2,
                                               SM, SM0, T, WFPS_CRIT):
                """
                计算反硝化速率
                """
                cNO3 = self.calculate_NO3_concentration(layer_thickness, NO3, SM)
                fR = self.calculate_soil_respiration_response_denitrifiation_rate_constant(RCORGT_kg_per_m2, MRCDIS)
                fW = self.calculate_soil_moisture_response_denitrification_rate_constant(SM, SM0, WFPS_CRIT)
                fT = self.calculate_temperature_response_denitrification_rate_constant(T)
                RNO3DENIT = fW * fT * fR * KDENIT_REF * SM * cNO3 * layer_thickness
                return RNO3DENIT

            def calculate_NO3_plant_uptake_rate(self, N_demand_soil, NO3, RD_m, SM, zmax, zmin):
                """
                计算植物对NO3的吸收速率
                """
                NO3_av = self.calculate_available_NO3(NO3, RD_m, SM, zmax, zmin)
                RNO3UP = min(N_demand_soil, NO3_av)
                return RNO3UP

            def calculate_soil_moisture_response_denitrification_rate_constant(self, SM, SM0, WFPS_CRIT):
                """
                计算土壤水分对反硝化速率常数的响应因子
                """
                WFPS = SM / SM0
                if WFPS < WFPS_CRIT:
                    fW = 0.
                else:
                    fW = np.power((WFPS - WFPS_CRIT)/(1 - WFPS_CRIT),2)
                return fW

            def calculate_soil_respiration_response_denitrifiation_rate_constant(self, RCORGT, MRCDIS):
                """
                计算土壤呼吸对反硝化速率常数的响应因子
                """
                fR = RCORGT / (MRCDIS + RCORGT)
                return fR

            def calculate_temperature_response_denitrification_rate_constant(self, T):
                """
                计算温度对反硝化速率常数的响应因子
                """
                fT = 1/(1+np.exp(-0.26*(T-17)))-1/(1+np.exp(-0.77*(T-41.9)))
                return fT

    class SoilOrganicNModel:
        def calculate_apparent_age_increase_rate(self, AGE, delt, pF, pH, T):
            """
            计算表观年龄增加速率
            """
            RAGEAG = np.zeros_like(AGE)
            janssen = self.Janssen()
            for am in range(0, AGE.shape[0]):
                for il in range(0, AGE.shape[1]):
                    RAGEAG[am,il] = janssen.calculate_increase_apparent_age_rate(delt, pF[il], pH[il], T)
            return RAGEAG

        def calculate_application_rates(self, soiln_profile, amount, application_depth, cnratio, f_orgmat):
            """
            计算施用速率
            """
            RORGMAT_am = np.zeros((1, len(soiln_profile)))
            RCORG_am = np.zeros_like(RORGMAT_am)
            RNORG_am = np.zeros_like(RORGMAT_am)

            zmin = 0.
            for il, layer in enumerate(soiln_profile):
                zmax = zmin + soiln_profile[il].Thickness
                RORGMAT_am[0, il] = \
                    self.calculate_organic_material_application_amount(amount, application_depth, f_orgmat,
                                                                       layer.Thickness, zmax, zmin)
                RCORG_am[0, il] = \
                    self.calculate_organic_carbon_application_amount(amount, application_depth, f_orgmat,
                                                                     layer.Thickness, zmax, zmin)
                RNORG_am[0, il] = \
                    self.calculate_organic_nitrogen_application_amount(amount, application_depth, cnratio, f_orgmat,
                                                                       layer.Thickness, zmax, zmin)
                zmin = zmax

            return RORGMAT_am, RCORG_am, RNORG_am

        def calculate_dissimilation_rates(self, AGE, CNRatioBio, FASDIS, NORG, ORGMAT, pF, pH, T):
            """
            计算分解速率
            """
            RORGMATDIS = np.zeros_like(AGE)
            RCORGDIS = np.zeros_like(AGE)
            RNORGDIS = np.zeros_like(AGE)
            janssen = self.Janssen()
            minip_c = self.MINIP_C()
            minip_n = self.MINIP_N()

            for am in range(0, AGE.shape[0]):
                for il in range(0, AGE.shape[1]):
                    if ORGMAT[am, il] > 0:
                        RORGMATDIS[am,il] = \
                            janssen.calculate_dissimilation_rate_OM_T(ORGMAT[am,il], AGE[am,il], pF[il], pH[il], T)
                        RCORGDIS[am,il] = \
                            minip_c.calculate_dissimilation_rate_C(janssen, ORGMAT[am,il], AGE[am,il], pF[il],
                                                                   pH[il], T)
                        RNORGDIS[am,il] = \
                            minip_n.calculate_dissimilation_rate_N(janssen, minip_c, ORGMAT[am,il], NORG[am,il],
                                                                   FASDIS, CNRatioBio, AGE[am,il], pF[il], pH[il], T)
                    else:
                        RORGMATDIS[am,il] = 0.
                        RCORGDIS[am,il] = 0.
                        RNORGDIS[am,il] = 0.
            return RORGMATDIS, RCORGDIS, RNORGDIS

        def calculate_organic_carbon_application_amount(self, amount, application_depth, f_orgmat, layer_thickness, zmax, zmin):
            """
            计算有机碳施用量
            """
            minip_C = self.MINIP_C()
            ORGMAT_am = \
                self.calculate_organic_material_application_amount(amount, application_depth, f_orgmat,
                                                                   layer_thickness, zmax, zmin)
            CORG_am = minip_C.calculate_organic_C(ORGMAT_am)
            return CORG_am

        def calculate_organic_nitrogen_application_amount(self, amount, application_depth, cnratio, f_orgmat, layer_thickness, zmax, zmin):
            """
            计算有机氮施用量
            """
            minip_C = self.MINIP_C()
            ORGMAT_am = self.calculate_organic_material_application_amount(amount, application_depth, f_orgmat, layer_thickness, zmax, zmin)
            CORG_am = minip_C.calculate_organic_C(ORGMAT_am)
            if cnratio == 0:
                NORG_am = 0.
            else:
                NORG_am = CORG_am / cnratio
            return NORG_am

        def calculate_organic_material_application_amount(self, amount, application_depth, f_orgmat, layer_thickness, zmax, zmin):
            """
            计算有机物质施用量
            """
            if application_depth > zmax:
                ORGMAT_am = (layer_thickness / application_depth) * f_orgmat * amount
            elif zmin <= application_depth <= zmax:
                ORGMAT_am = ((application_depth - zmin) / application_depth) * f_orgmat * amount
            else:
                ORGMAT_am = 0
            return ORGMAT_am

        class Janssen:
            m = 1.6
            b = 2.82
            y_to_d = 365.25

            def calculate_increase_apparent_age_rate(self, dt, pF, pH, T):
                """
                计算表观年龄增加速率
                """
                f_pH = self.calculate_pH_response_dissimilation_rate(pH)
                f_T = self.calculate_temperature_response_dissimilation_rate_Yang(T)
                f_SM = self.calculate_soil_moisture_response_dissimilation_rate(pF)
                dA = f_pH * f_T * f_SM * dt
                return dA

            def calculate_relative_dissimilation_rate_OM_T(self, t, pF, pH, T):
                """
                计算有机物相对异化速率与温度的关系
                """
                m = self.m
                b = self.b
                f_pH = self.calculate_pH_response_dissimilation_rate(pH)
                f_T = self.calculate_temperature_response_dissimilation_rate_Yang(T)
                f_SM = self.calculate_soil_moisture_response_dissimilation_rate(pF)
                k = f_pH * f_T * f_SM * b *  pow(t/self.y_to_d, -m) / self.y_to_d
                return k

            def calculate_dissimilation_rate_OM_T(self, OM, t, pF, pH, T):
                """
                计算有机物异化速率
                """
                k = self.calculate_relative_dissimilation_rate_OM_T(t, pF, pH, T)
                rate = k * OM
                return rate

            def calculate_soil_moisture_response_dissimilation_rate(self, pF):
                """
                计算土壤水分对异化速率的响应
                """
                if pF < 2.7:
                    f_SM = 1.0
                elif pF < 4.2:
                    f_SM = 1.0 * (4.2 - pF) / (4.2 - 2.7)
                else:
                    f_SM = 0.
                return f_SM

            def calculate_pH_response_dissimilation_rate(self, pH):
                """
                计算土壤pH对异化速率的响应
                """
                f_pH = 1 / (1 + np.exp(-1.5 * (pH - 4)))
                return f_pH

            def calculate_temperature_response_dissimilation_rate(self, T):
                """
                计算温度对异化速率的响应
                """
                f_T = pow(2, (T-9)/9)
                return f_T

            def calculate_temperature_response_dissimilation_rate_Yang(self, T):
                """
                使用Yang公式计算温度对异化速率的响应
                """
                if T < -1:
                    f_T = 0.
                elif T < 9.:
                    f_T = 0.09 * (T + 1)
                elif T < 27.:
                    f_T = 0.88 * pow(2, (T-9)/9)
                else:
                    f_T = 3.5
                return f_T

        class MINIP_C:
            OM_to_C = 0.58
            y_to_d = 365.

            def calculate_assimilation_rate(self, janssen, OM, f_ass_dis, t, pF, pH, T):
                """
                计算有机碳同化速率
                """
                r_disc = self.calculate_dissimilation_rate_C(janssen, OM, t, pF, pH, T)
                r_ass = r_disc * f_ass_dis
                return r_ass

            def calculate_dissimilation_rate_C(self, janssen, OM, t, pF, pH, T):
                """
                计算有机碳异化速率
                """
                k = janssen.calculate_relative_dissimilation_rate_OM_T(t, pF, pH, T)
                Corg = self.calculate_organic_C(OM)
                rate = k * Corg
                return rate

            def calculate_total_conversion_rate_C(self, janssen, OM, f_ass_dis, t, pF, pH, T):
                """
                计算有机碳总转化速率
                """
                r_dis_C = self.calculate_dissimilation_rate_C(janssen, OM, t, pF, pH, T)
                r_ass_C = self.calculate_assimilation_rate(janssen, OM, f_ass_dis, t, pF, pH, T)
                r_conv_C = r_dis_C + r_ass_C
                return r_conv_C

            def calculate_organic_C(self, OM):
                """
                计算有机碳含量
                """
                Corg = OM * self.OM_to_C
                return Corg

        class MINIP_N:
            def calculate_total_conversion_rate_N(self, janssen, minip_c, OM, Norg, f_ass_dis, t, pF, pH, T):
                """
                计算有机氮总转化速率
                """
                r_conv_C = minip_c.calculate_total_conversion_rate_C(janssen, OM, f_ass_dis, t, pF, pH, T)
                C = minip_c.calculate_organic_C(OM)
                r_conv_N = r_conv_C * (Norg/C)
                return r_conv_N

            def calculate_assimilation_rate_N(self, janssen, minip_c, OM, f_ass_dis, f_C_N_microbial, t, pF, pH, T):
                """
                计算有机氮同化速率
                """
                r_ass_C = minip_c.calculate_assimilation_rate(janssen, OM, f_ass_dis, t, pF, pH, T)
                r_ass_N = r_ass_C/f_C_N_microbial
                return r_ass_N

            def calculate_dissimilation_rate_N(self, janssen, minip_c, OM, Norg, f_ass_dis, f_C_N_microbial, t, pF, pH, T):
                """
                计算有机氮异化速率
                """
                r_ass_N = self.calculate_assimilation_rate_N(janssen, minip_c, OM, f_ass_dis, f_C_N_microbial, t, pF, pH, T)
                r_conv_N = self.calculate_total_conversion_rate_N(janssen, minip_c, OM, Norg, f_ass_dis, t, pF, pH, T)
                r_diss_N = r_conv_N - r_ass_N
                return r_diss_N
