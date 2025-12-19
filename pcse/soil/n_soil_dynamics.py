# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

from pcse.traitlets import Float
from pcse.decorators import prepare_rates, prepare_states
from pcse.base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject
from pcse import signals


class N_PotentialProduction(SimulationObject):
    """为潜在生产模拟提供无限的土壤N/P/K。

    无论作物吸收多少，NAVAIL 始终保持在 100 kg/ha。
    """

    class StateVariables(StatesTemplate):
        NAVAIL = Float(-99.)  # 土壤和肥料中可利用的总矿质N，单位 kg N ha-1

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param cropdata: WOFOST作物数据的键/值对字典
        """
        self.states = self.StateVariables(kiosk, publish=["NAVAIL"], NAVAIL=100.)

    def calc_rates(self, day, drv):
        pass

    @prepare_states
    def integrate(self, day, delt=1.0):
        self.touch()


class N_Soil_Dynamics(SimulationObject):
    """土壤氮动力学的简单模块。

    此模块将土壤表征为可用N的一个水桶，由两个部分组成：
    1）原生土壤供给，包括一定初始量的N，并且每天有固定比例变为可用N；
    2）外源供给，根据提供的N量并乘以回收系数，得到可被作物吸收的有效N量。

    此模块不模拟任何土壤生理过程，仅作为N可用性的记账方法。因此无需详细的土壤参数，只需初始土壤N量、施肥输入、回收系数和背景供给即可。

    **模拟参数**

    ============  =========================================== =======  ==============
     名称          说明                                         类型     单位
    ============  =========================================== =======  ==============
    NSOILBASE     通过矿化作用可用的基础土壤N供给量              SSi      |kg ha-1|
    NSOILBASE_FR  每天有多少比例的基础土壤N可被释放               SSi        -
    NAVAILI       初始N池中可用N的数量                            SSi      |kg ha-1|
    BG_N_SUPPLY   大气沉降等背景N供给                             SSi      |kg ha-1 d-1|
    ============  =========================================== =======  ==============


    **状态变量**

    =======  =========================================== ==== ============
     名称     说明                                       发布      单位
    =======  =========================================== ==== ============
     NSOIL    生长期开始时土壤可用的总矿质N                 N    [kg ha-1]
     NAVAIL   土壤和肥料中可用的N总量                      Y    |kg ha-1|
    =======  =========================================== ==== ============

    **速率变量**

    =============  ========================================= ==== =============
     名称            说明                                    发布     单位
    =============  ========================================= ==== =============
    RNSOIL         土壤矿质N总量的变化速率                     N   |kg ha-1 d-1|
    RNAVAIL        可用N总量的变化速率                         N   |kg ha-1 d-1|
    FERT_N_SUPPLY  氮肥供应量。                                N   |kg ha-1 d-1|
                   此值由AgroManager模块通过事件机制提供。
                   详细内容见下方的信号部分。
    =============  ========================================= ==== =============

    **接收和发送的信号**

    `N_Soil_Dynamics` 接收下列信号：
        * APPLY_N: 当有N肥料外源输入时将收到该信号。
          详见 `_on_APPLY_N()`。

    **外部依赖**

    =========  =============================== ===================  ==============
     名称       说明                           提供模块               单位
    =========  =============================== ===================  ==============
    DVS        作物发育阶段                    DVS_Phenology           -
    TRA        作物实际蒸腾量增加              Evapotranspiration     |cm|
    TRAMX      作物潜在蒸腾量增加              Evapotranspiration     |cm|
    RNuptake   作物对N的吸收速率               NPK_Demand_Uptake     |kg ha-1 d-1|
    =========  =============================== ===================  ==============
    """

    NSOILI = Float(-99.) # 初始土壤氮含量

    class Parameters(ParamTemplate):      
        NSOILBASE = Float(-99.)  # 生长期开始时土壤可用矿质氮总量 [kg N/ha]
        NSOILBASE_FR = Float(-99.)  # 每天有多少比例的矿质氮可以释放出来 [day-1]
        NAVAILI = Float()
        BG_N_SUPPLY = Float()

    class StateVariables(StatesTemplate):
        NSOIL = Float(-99.)  # 土壤中可供作物利用的矿质氮 [kg N/ha]
        NAVAIL = Float(-99.)  # 土壤和肥料中的总矿质氮 [kg N/ha]
      
    class RateVariables(RatesTemplate):
        RNSOIL = Float(-99.)        
        RNAVAIL = Float(-99.)

        # 氮肥的供应速率 [kg/ha/day]
        FERT_N_SUPPLY = Float()

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 当前PCSE实例的变量仓库
        :param cropdata: WOFOST作物数据的键值对字典
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
        
        # 初始状态
        p = self.params
        self.NSOILI = p.NSOILBASE
        
        self.states = self.StateVariables(kiosk,
            publish=["NAVAIL"], NSOIL=p.NSOILBASE, NAVAIL=p.NAVAILI)
        self._connect_signal(self._on_APPLY_N, signals.apply_n)

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        p = self.params
        k = self.kiosk

        r.RNSOIL = -max(0., min(p.NSOILBASE_FR * self.NSOILI, s.NSOIL))

        # 检查作物对氮的吸收速率，如果作物正在生长
        RNuptake = k.RNuptake if "RNuptake" in self.kiosk else 0.

        r.RNAVAIL = r.FERT_N_SUPPLY + p.BG_N_SUPPLY - RNuptake - r.RNSOIL
        
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 土壤中的矿质氮含量
        states.NSOIL += rates.RNSOIL * delt
        
        # 土壤中（包括肥料）的总氮含量
        states.NAVAIL += rates.RNAVAIL * delt

    def _on_APPLY_N(self, N_amount=None, N_recovery=None):
        r = self.rates
        r.unlock()
        r.FERT_N_SUPPLY = N_amount * N_recovery
        r.lock()
