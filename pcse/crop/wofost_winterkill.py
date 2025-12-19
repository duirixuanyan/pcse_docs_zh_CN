# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

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
from .evapotranspiration import Evapotranspiration
from .abioticdamage import FROSTOL
from .abioticdamage import CrownTemperature
from .stem_dynamics import WOFOST_Stem_Dynamics as Stem_Dynamics
from .root_dynamics import WOFOST_Root_Dynamics as Root_Dynamics
from .leaf_dynamics import WOFOST_Leaf_Dynamics as Leaf_Dynamics
from .storage_organ_dynamics import WOFOST_Storage_Organ_Dynamics as \
     Storage_Organ_Dynamics

#-------------------------------------------------------------------------------
class Wofost_winterkill(SimulationObject):
    """
    最高层对象，组织WOFOST作物模拟的不同组件，包括冻害模拟。

    CropSimulation对象负责组织作物生长模拟中的各个过程。此外，它包含与整个作物层面相关的参数、速率和状态变量。具体嵌入的模拟组件包括：

        1. 物候 (self.pheno)
        2. 干物质分配 (self.part)
        3. 同化作用 (self.assim)
        4. 维持呼吸 (self.mres)
        5. 蒸发蒸腾 (self.evtra)
        6. 抗冻性 (self.frostol)
        7. 叶片动态 (self.lv_dynamics)
        8. 茎动态 (self.st_dynamics)
        9. 根动态 (self.ro_dynamics)
       10. 贮藏器官动态 (self.so_dynamics)

    **模拟参数:**

    ======== ================================ =======  ==========
     名称     描述                             类型     单位
    ======== ================================ =======  ==========
    CVL      光合产物向叶片的转换系数          SCr     -
    CVO      光合产物向贮藏器官的转换系数        SCr     -
    CVR      光合产物向根的转换系数             SCr     -
    CVS      光合产物向茎的转换系数             SCr     -
    ======== ================================ =======  ==========

    **状态变量:**

    =========== =================================== ==== ===============
     名称        描述                               公布      单位
    =========== =================================== ==== ===============
    TAGP        地上总生产量                          N    |kg ha-1|
    GASST       总光合同化量                          N    |kg CH2O ha-1|
    MREST       总维持呼吸                            N    |kg CH2O ha-1|
    CTRAT       作物总蒸腾量                          N    cm
    HI          收获指数(仅在 `finalize()` 计算)      N    -
    DOF         表示作物模拟结束日期                  N    -
    FINISH_TYPE 说明模拟结束原因的字符串              N    -
                （成熟、收获、叶片死亡等）
    =========== =================================== ==== ===============

    **速率变量:**

    =======  =================================== ==== =============
     名称      描述                              公布      单位
    =======  =================================== ==== =============
    GASS     修正水分胁迫后的同化速率              N  |kg CH2O ha-1 d-1|
    PGASS    潜在同化速率                          N  |kg CH2O ha-1 d-1|
    MRES     实际维持呼吸速率                      N  |kg CH2O ha-1 d-1|
             （MRES <= GASS）
    PMRES    潜在维持呼吸速率                      N  |kg CH2O ha-1 d-1|
    ASRC     净可用光合产物                        N  |kg CH2O ha-1 d-1|
             (GASS - MRES)
    DMI      干物质总增加量                        Y  |kg ha-1 d-1|
             （ASRC乘加权转换效率）
    ADMI     地上干物质增加量                      Y  |kg ha-1 d-1|
    =======  =================================== ==== =============

    """
    
    # 作物模拟的子模型组件
    pheno = Instance(SimulationObject)
    part  = Instance(SimulationObject)
    assim = Instance(SimulationObject)
    mres  = Instance(SimulationObject)
    evtra = Instance(SimulationObject)
    frostol = Instance(SimulationObject)
    crowntemp = Instance(SimulationObject)
    lv_dynamics = Instance(SimulationObject)
    st_dynamics = Instance(SimulationObject)
    ro_dynamics = Instance(SimulationObject)
    so_dynamics = Instance(SimulationObject)
    
    # 主要作物模拟层面涉及的参数、速率和状态变量
    class Parameters(ParamTemplate):
        CVL = Float(-99.)
        CVO = Float(-99.)
        CVR = Float(-99.)
        CVS = Float(-99.)

    class StateVariables(StatesTemplate):
        TAGP  = Float(-99.)
        GASST = Float(-99.)
        MREST = Float(-99.)
        CTRAT = Float(-99.) # 作物蒸腾总量
        HI    = Float(-99.)
        DOF = Instance(datetime.date)
        FINISH_TYPE = Unicode()

    class RateVariables(RatesTemplate):
        GASS  = Float(-99.)
        PGASS = Float(-99.)
        MRES  = Float(-99.)
        PMRES = Float(-99.)
        ASRC  = Float(-99.)
        DMI   = Float(-99.)
        ADMI  = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，按键值对提供参数
        """
        
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk, publish=["DMI", "ADMI"])
        self.kiosk = kiosk
        
        # 初始化作物的各个组件
        self.pheno = Phenology(day, kiosk,  parvalues)
        self.part  = Partitioning(day, kiosk, parvalues)
        self.assim = Assimilation(day, kiosk, parvalues)
        self.mres  = MaintenanceRespiration(day, kiosk, parvalues)
        self.evtra = Evapotranspiration(day, kiosk, parvalues)
        self.crowntemp = CrownTemperature(day, kiosk, parvalues)
        self.frostol = FROSTOL(day, kiosk, parvalues)
        self.ro_dynamics = Root_Dynamics(day, kiosk, parvalues)
        self.st_dynamics = Stem_Dynamics(day, kiosk, parvalues)
        self.so_dynamics = Storage_Organ_Dynamics(day, kiosk, parvalues)
        self.lv_dynamics = Leaf_Dynamics(day, kiosk, parvalues)

        # 初始地上（活+死）生物量总量
        TAGP = self.kiosk["TWLV"] + \
               self.kiosk["TWST"] + \
               self.kiosk["TWSO"]
        self.states = self.StateVariables(kiosk,
                                          publish=["TAGP","GASST","MREST","HI"],
                                          TAGP=TAGP, GASST=0.0, MREST=0.0,
                                          CTRAT=0.0, HI=0.0,
                                          DOF=None, FINISH_TYPE=None)

        # 检查TDWI在各器官间的分配
        checksum = parvalues["TDWI"] - self.states.TAGP - self.kiosk["TWRT"]
        if abs(checksum) > 0.0001:
            msg = "Error in partitioning of initial biomass (TDWI)!"
            raise exc.PartitioningError(msg)
            
        # 分配CROP_FINISH信号的处理器
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)
    #---------------------------------------------------------------------------
    @staticmethod
    def _check_carbon_balance(day, DMI, GASS, MRES, CVF, pf):
        (FR, FL, FS, FO) = pf
        checksum = (GASS - MRES - (FR+(FL+FS+FO)*(1.-FR)) * DMI/CVF) * \
                    1./(max(0.0001,GASS))
        if abs(checksum) >= 0.0001:
            msg = "Carbon flows not balanced on day %s\n" % day  # 碳流量不平衡
            msg += "Checksum: %f, GASS: %f, MRES: %f\n" % (checksum, GASS, MRES)  # 校验值、总同化量、呼吸消耗
            msg += "FR,L,S,O: %5.3f,%5.3f,%5.3f,%5.3f, DMI: %f, CVF: %f\n" % \
                   (FR, FL, FS, FO, DMI, CVF)  # 分配系数和转换系数
            raise exc.CarbonBalanceError(msg)

    #---------------------------------------------------------------------------
    @prepare_rates
    def calc_rates(self, day, drv):
        params = self.params
        rates  = self.rates
        states = self.states

        # 物候期计算
        self.pheno.calc_rates(day, drv)
        crop_stage = self.pheno.get_variable("STAGE")

        # 如果作物尚未出苗，无需继续，因为只有物候期在运行。
        if crop_stage == "emerging":
            return

        # 潜在同化量
        rates.PGASS = self.assim(day, drv)

        # （蒸散）蒸发速率
        self.evtra(day, drv)

        # 水分胁迫调节
        TRA = self.kiosk["TRA"]
        TRAMX = self.kiosk["TRAMX"]
        rates.GASS = rates.PGASS * TRA/TRAMX

        # 呼吸作用
        rates.PMRES = self.mres(day, drv)
        rates.MRES  = min(rates.GASS, rates.PMRES)

        # 实际可利用的同化物
        rates.ASRC  = rates.GASS - rates.MRES

        # 干物质分配系数（pf）、转换系数（CVF）、干重增加（DMI）并检查碳平衡
        pf = self.part.calc_rates(day, drv)
        CVF = 1./((pf.FL/params.CVL + pf.FS/params.CVS + pf.FO/params.CVO) *
                  (1.-pf.FR) + pf.FR/params.CVR)
        rates.DMI = CVF * rates.ASRC
        self._check_carbon_balance(day, rates.DMI, rates.GASS, rates.MRES,
                                   CVF, pf)

        # 冻害耐受性
        self.crowntemp(day, drv)
        self.frostol.calc_rates(day, drv)

        # -- 植物器官的分配 --
        # 地下部干重增加及根动态
        self.ro_dynamics.calc_rates(day, drv)
        # 地上部干重增加，并分配至茎、叶、贮藏器官
        rates.ADMI = (1. - pf.FR) * rates.DMI
        self.st_dynamics.calc_rates(day, drv)
        self.so_dynamics.calc_rates(day, drv)
        self.lv_dynamics.calc_rates(day, drv)

    #---------------------------------------------------------------------------
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 积分前的作物发育阶段
        crop_stage = self.pheno.get_variable("STAGE")

        # 物候积分
        self.pheno.integrate(day, delt)

        # 如果尚未出苗，无需继续，因为此时只有物候在运行。
        # 只需运行 touch()，以确保所有状态变量都可用于 kiosk
        if crop_stage == "emerging":
            self.touch()
            return

        # 干物质分配积分
        self.part.integrate(day, delt)
        
        # 冻害耐受性积分
        self.frostol.integrate(day, delt)

        # 叶片、贮藏器官、茎和根的状态积分
        self.ro_dynamics.integrate(day, delt)
        self.so_dynamics.integrate(day, delt)
        self.st_dynamics.integrate(day, delt)
        self.lv_dynamics.integrate(day, delt)

        # 作物地上（活+死）总生物量积分
        states.TAGP = self.kiosk["TWLV"] + \
                      self.kiosk["TWST"] + \
                      self.kiosk["TWSO"]

        # 总同化量与总维持呼吸积分
        states.GASST += rates.GASS
        states.MREST += rates.MRES
        
        # 总作物蒸散量（CTRAT）积分
        states.CTRAT += self.kiosk["TRA"]
        
    #---------------------------------------------------------------------------
    @prepare_states
    def finalize(self, day):

        # 计算收获指数
        if self.states.TAGP > 0:
            self.states.HI = self.kiosk["TWSO"]/self.states.TAGP
        else:
            msg = "Cannot calculate Harvest Index because TAGP=0"
            self.logger.warning(msg)
            self.states.HI = -1.
        
        SimulationObject.finalize(self, day)

    #---------------------------------------------------------------------------
    def _on_CROP_FINISH(self, day, finish):
        """设置作物终止日（DOF）和终止原因（FINISH）的处理函数。"""
        self._for_finalize["DOF"] = day
        self._for_finalize["FINISH_TYPE"]= finish
