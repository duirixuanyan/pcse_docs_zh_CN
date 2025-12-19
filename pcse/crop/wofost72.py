# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl)，2014年4月

import datetime

from ..traitlets import Float, Int, Instance, Enum, Unicode
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals
from .. import exceptions as exc

from .phenology import DVS_Phenology as Phenology
from .assimilation import WOFOST72_Assimilation as Assimilation
from .partitioning import DVS_Partitioning as Partitioning
from .respiration import WOFOST_Maintenance_Respiration as MaintenanceRespiration
from .evapotranspiration import EvapotranspirationWrapper as Evapotranspiration
from .stem_dynamics import WOFOST_Stem_Dynamics as Stem_Dynamics
from .root_dynamics import WOFOST_Root_Dynamics as Root_Dynamics
from .leaf_dynamics import WOFOST_Leaf_Dynamics as Leaf_Dynamics
from .storage_organ_dynamics import WOFOST_Storage_Organ_Dynamics as \
     Storage_Organ_Dynamics


class Wofost72(SimulationObject):
    """WOFOST作物模拟不同组件的顶层组织对象。

    CropSimulation 对象组织了作物模拟的不同过程。此外，它包含了与整个作物层级相关的参数、速率和状态变量。作为嵌入式子模型实现的过程包括：

        1. 物候期 (self.pheno)
        2. 分配 (self.part)
        3. 同化 (self.assim)
        4. 维持呼吸 (self.mres)
        5. 蒸散 (self.evtra)
        6. 叶片动态 (self.lv_dynamics)
        7. 茎动态 (self.st_dynamics)
        8. 根动态 (self.ro_dynamics)
        9. 储藏器官动态 (self.so_dynamics)

    **模拟参数:**
    
    ======== =============================================== =======  ==========
     名称      描述                                           类型      单位
    ======== =============================================== =======  ==========
    CVL      同化物转化为叶片的系数                            SCr     -
    CVO      同化物转化为储藏器官的系数                        SCr     -
             (储藏器官)。
    CVR      同化物转化为根的系数                              SCr     -
    CVS      同化物转化为茎的系数                              SCr     -
    ======== =============================================== =======  ==========


    **状态变量:**

    =========== ================================================= ==== ===============
     名称        描述                                             Pbl     单位
    =========== ================================================= ==== ===============
    TAGP        地上总生产量                                       N    |kg ha-1|
    GASST       总总同化量                                         N    |kg CH2O ha-1|
    MREST       总维持呼吸量                                       N    |kg CH2O ha-1|
    CTRAT       作物生长期累积作物蒸腾量                           N    cm
    CEVST       作物生长期累积土壤蒸发量                           N    cm
    HI          收获指数                                           N    -
                （仅在 `finalize()` 时计算）
    DOF         表示作物模拟结束日的日期                           N    -
    FINISH_TYPE 表示模拟结束原因的字符串：                         N    -
                成熟、收获、叶片死亡等。
    =========== ================================================= ==== ===============


    **速率变量:**

    =======  ================================================ ==== =============
     名称      描述                                           Pbl      单位
    =======  ================================================ ==== =============
    GASS     校正水分胁迫的同化速率                             N  |kg CH2O ha-1 d-1|
    MRES     实际维持呼吸速率，MRES <= GASS                     N  |kg CH2O ha-1 d-1|
    ASRC     纯可用同化物 (GASS - MRES)                         N  |kg CH2O ha-1 d-1|
    DMI      总干物质增加值，ASRC * 加权转化效率                Y  |kg ha-1 d-1|
    ADMI     地上部分干物质增加值                               Y  |kg ha-1 d-1|
    =======  ================================================ ==== =============

    """

    # 作物模拟的子模型组件
    pheno = Instance(SimulationObject)
    part  = Instance(SimulationObject)
    assim = Instance(SimulationObject)
    mres  = Instance(SimulationObject)
    evtra = Instance(SimulationObject)
    lv_dynamics = Instance(SimulationObject)
    st_dynamics = Instance(SimulationObject)
    ro_dynamics = Instance(SimulationObject)
    so_dynamics = Instance(SimulationObject)
    
    # 主要作物模拟层面相关的参数、速率和状态变量
    class Parameters(ParamTemplate):
        CVL = Float(-99.)
        CVO = Float(-99.)
        CVR = Float(-99.)
        CVS = Float(-99.)

    class StateVariables(StatesTemplate):
        TAGP  = Float(-99.)
        GASST = Float(-99.)
        MREST = Float(-99.)
        CTRAT = Float(-99.)
        CEVST = Float(-99.)
        HI = Float(-99.)
        DOF = Instance(datetime.date)
        FINISH_TYPE = Unicode(allow_none=True)

    class RateVariables(RatesTemplate):
        GASS = Float(-99.)
        MRES = Float(-99.)
        ASRC = Float(-99.)
        DMI = Float(-99.)
        ADMI = Float(-99.)
        REALLOC_LV = Float(0.)
        REALLOC_ST = Float(0.)
        REALLOC_SO = Float(0.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 本 PCSE 实例的变量 kiosk
        :param parvalues: `ParameterProvider` 对象，提供参数的键/值对
        """
        
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["DMI", "ADMI", "REALLOC_LV", "REALLOC_ST", "REALLOC_SO"])
        self.kiosk = kiosk
        
        # 初始化作物的各个组件
        self.pheno = Phenology(day, kiosk, parvalues)
        self.part = Partitioning(day, kiosk, parvalues)
        self.assim = Assimilation(day, kiosk, parvalues)
        self.mres = MaintenanceRespiration(day, kiosk, parvalues)
        self.evtra = Evapotranspiration(day, kiosk, parvalues)
        self.ro_dynamics = Root_Dynamics(day, kiosk, parvalues)
        self.st_dynamics = Stem_Dynamics(day, kiosk, parvalues)
        self.so_dynamics = Storage_Organ_Dynamics(day, kiosk, parvalues)
        self.lv_dynamics = Leaf_Dynamics(day, kiosk, parvalues)

        # 初始(活+死)地上部生物量总量
        TAGP = self.kiosk.TWLV + self.kiosk.TWST + self.kiosk.TWSO
        self.states = self.StateVariables(kiosk,
                                          publish=["TAGP", "GASST", "MREST", "HI"],
                                          TAGP=TAGP, GASST=0.0, MREST=0.0,
                                          CTRAT=0.0, CEVST=0.0, HI=0.0,
                                          DOF=None, FINISH_TYPE=None)

        # 检查 TDWI 在器官间的初始分配
        checksum = parvalues["TDWI"] - self.states.TAGP - self.kiosk["TWRT"]
        if abs(checksum) > 0.0001:
            msg = "Error in partitioning of initial biomass (TDWI)!"
            raise exc.PartitioningError(msg)
            
        # 为 CROP_FINISH 信号分配处理函数
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)

    @staticmethod
    def _check_carbon_balance(day, DMI, GASS, MRES, CVF, pf):
        (FR, FL, FS, FO) = pf
        # 检查碳流是否平衡
        checksum = (GASS - MRES - (FR+(FL+FS+FO)*(1.-FR)) * DMI/CVF) * 1./(max(0.0001, GASS))
        if abs(checksum) >= 0.0001:
            msg = "Carbon flows not balanced on day %s\n" % day
            msg += "Checksum: %f, GASS: %f, MRES: %f\n" % (checksum, GASS, MRES)
            msg += "FR,L,S,O: %5.3f,%5.3f,%5.3f,%5.3f, DMI: %f, CVF: %f\n" % \
                   (FR, FL, FS, FO, DMI, CVF)
            raise exc.CarbonBalanceError(msg)

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # 物候计算
        self.pheno.calc_rates(day, drv)
        crop_stage = self.pheno.get_variable("STAGE")

        # 如果尚未出苗, 则不需要继续, 只有物候模块会运行
        if crop_stage == "emerging":
            return

        # 潜在同化作用
        PGASS = self.assim(day, drv)

        # （蒸发）蒸腾速率
        self.evtra(day, drv)

        # 水分胁迫减少
        r.GASS = PGASS * k.RFTRA

        # 呼吸作用
        PMRES = self.mres(day, drv)
        r.MRES  = min(r.GASS, PMRES)

        # 可用于分配的净同化物
        r.ASRC  = r.GASS - r.MRES

        # 干物质分配因子（pf）、转换因子（CVF）、干物质增加量（DMI），并检查碳平衡
        pf = self.part.calc_rates(day, drv)
        CVF = 1./((pf.FL/p.CVL + pf.FS/p.CVS + pf.FO/p.CVO) *
                  (1.-pf.FR) + pf.FR/p.CVR)
        r.DMI = CVF * r.ASRC
        self._check_carbon_balance(day, r.DMI, r.GASS, r.MRES,
                                   CVF, pf)

        # 作物器官的分配

        # 在WOFOST72中不适用茎/叶的重新分配
        r.REALLOC_LV = 0.0
        r.REALLOC_ST = 0.0
        r.REALLOC_SO = 0.0

        # 地下干物质增加与根系动力学
        self.ro_dynamics.calc_rates(day, drv)
        # 地上部干物质增加及在茎、叶、器官间的分配
        r.ADMI = (1. - pf.FR) * r.DMI
        self.st_dynamics.calc_rates(day, drv)
        self.so_dynamics.calc_rates(day, drv)
        self.lv_dynamics.calc_rates(day, drv)

    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 积分前的作物生育阶段
        crop_stage = self.pheno.get_variable("STAGE")

        # 物候积分
        self.pheno.integrate(day, delt)

        # 如果尚未出苗，则不需要继续，因为只有物候模块在运行。
        # 只需运行 touch()，确保所有的状态变量都可在kiosk中获取
        if crop_stage == "emerging":
            self.touch()
            return

        # 干物质分配模块积分
        self.part.integrate(day, delt)
        
        # 叶、贮藏器官、茎、根各器官状态积分
        self.ro_dynamics.integrate(day, delt)
        self.so_dynamics.integrate(day, delt)
        self.st_dynamics.integrate(day, delt)
        self.lv_dynamics.integrate(day, delt)

        # 积分作物地上部总干物质（活体和枯死）
        states.TAGP = self.kiosk.TWLV + self.kiosk.TWST + self.kiosk.TWSO

        # 积分总同化速率和总维护呼吸消耗
        states.GASST += rates.GASS
        states.MREST += rates.MRES
        
        # 积分作物蒸腾量与土壤蒸发量
        states.CTRAT += self.kiosk.TRA
        states.CEVST += self.kiosk.EVS

    @prepare_states
    def finalize(self, day):

        # 计算收获指数
        if self.states.TAGP > 0:
            self.states.HI = self.kiosk.TWSO/self.states.TAGP
        else:
            msg = "Cannot calculate Harvest Index because TAGP=0"
            self.logger.warning(msg)
            self.states.HI = -1.
        
        SimulationObject.finalize(self, day)

    def _on_CROP_FINISH(self, day, finish_type=None):
        """用于设置完成日(DOF)和作物结束原因(FINISH)的处理函数
        """
        self._for_finalize["DOF"] = day
        self._for_finalize["FINISH_TYPE"]= finish_type
