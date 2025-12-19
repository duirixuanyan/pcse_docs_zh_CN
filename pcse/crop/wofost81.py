# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Herman Berghuijs (herman.berghuijs@wur.nl) 和 Allard de Wit (allard.dewit@wur.nl), 2024年1月

import datetime

from ..traitlets import Float, Instance, Unicode
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals
from .. import exceptions as exc
from .phenology import DVS_Phenology as Phenology
from .respiration import WOFOST_Maintenance_Respiration as MaintenanceRespiration
from .stem_dynamics import WOFOST_Stem_Dynamics as Stem_Dynamics
from .root_dynamics import WOFOST_Root_Dynamics as Root_Dynamics
from .leaf_dynamics import WOFOST_Leaf_Dynamics_N as Leaf_Dynamics
from .storage_organ_dynamics import WOFOST_Storage_Organ_Dynamics as \
    Storage_Organ_Dynamics
from .assimilation import WOFOST81_Assimilation as Assimilation
from .partitioning import DVS_Partitioning_N as Partitioning
from .evapotranspiration import EvapotranspirationWrapper as Evapotranspiration
from .n_dynamics import N_Crop_Dynamics as N_crop
from .nutrients.n_stress import N_Stress as N_Stress

class Wofost81(SimulationObject):
    """
    WOFOST作物模拟各组件的顶层组织对象。EvapotranspirationCO2Layered作为蒸发蒸腾模块允许分层土壤水分平衡（watfgdw）模拟。    
    
    CropSimulation对象负责组织作物模拟的不同过程，并且包含适用于整个作物水平的参数、速率和状态变量。作为内嵌模拟对象实现的各过程包括：
    
        1. 发育历程 (self.pheno)
        2. 同化物分配 (self.part)
        3. 光合同化 (self.assim)
        4. 维持呼吸 (self.mres)
        5. 蒸散作用 (self.evtra)
        6. 叶片发育 (self.lv_dynamics)
        7. 茎部发育 (self.st_dynamics)
        8. 根部发育 (self.ro_dynamics)
        9. 贮藏器官发育 (self.so_dynamics)
        10. N素作物动态 (self.n_crop_dynamics)
        11. N素胁迫 (self.n_stress)

    **模拟参数:**
    
    ======== ============================================= =======  ==========
     名称      说明                                         类型      单位
    ======== ============================================= =======  ==========
    CVL      同化物到叶子的转化系数                          SCr      -
    CVO      同化物到贮藏器官的转化系数                       SCr      -
             （贮藏器官）。
    CVR      同化物到根部的转化系数                          SCr      -
    CVS      同化物到茎的转化系数                            SCr      -
    ======== ============================================= =======  ==========
    
    
    **状态变量:**

    =============  =========================================== ==== ===============
     名称            说明                                      Pbl      单位
    =============  =========================================== ==== ===============
    TAGP           地上部总产量                                  N    |kg ha-1|
    GASST          总净同化量                                    N    |kg CH2O ha-1|
    MREST          总维持呼吸消耗                                N    |kg CH2O ha-1|
    CTRAT          作物整个生育期累计的总蒸腾量                  N    cm
    CEVST          作物整个生育期累计的总土壤蒸发量              N    cm
    HI             收获指数（只在`finalize()`期间计算）          N    -
    DOF            作物模拟终止日的日期                          N    -
    FINISH_TYPE    模拟终止的原因（收获、叶片死亡等）            N    -
    REALLOC_<o>    组织o的再分配速率                             
    =============  =========================================== ==== ===============

 
     **速率变量:**

    ======================= ========================================= ==== =============
     名称                   说明                                       Pbl      单位
    ======================= ========================================= ==== =============
    GASS                    修正水分胁迫后的同化速率                    N  |kg CH2O ha-1 d-1|
    PGASS                   潜在同化速率                                N  |kg CH2O ha-1 d-1|
    MRES                    实际维持呼吸速率，满足 MRES <= GASS         N  |kg CH2O ha-1 d-1|
    PMRES                   潜在维持呼吸速率                            N  |kg CH2O ha-1 d-1|
    REALLOC_DVS             再分配开始的发育阶段                        N  -
    REALLOC_<o>_FRACTION    组织o在再分配发育阶段REALLOC_DVS
                            中可再分配的干物质比例                      Y  |kg DM kg-1 DM|
    REALLOC_<o>_RATE:       组织o的相对再分配速率                       N  |d-1|
    REALLOC_EFFICIENCY:     再分配效率                                  N  |kg DM kg-1 DM|
    ASRC                    净可用同化物(GASS - MRES)                   N  |kg CH2O ha-1 d-1|
    DMI                     总干物质增加量，                            Y  |kg ha-1 d-1|
                            ASRC×加权转化效率
    ADMI                    地上干物质增加量                            Y  |kg ha-1 d-1|
    ======================= ========================================= ==== =============

    """
   
    # 可再分配生物量的占位符
    _WLV_REALLOC = Float(None)
    _WST_REALLOC = Float(None)
    
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
    n_crop_dynamics = Instance(SimulationObject)
    n_stress = Instance(SimulationObject)
    
    # 在主要作物模拟层面相关的参数、速率和状态
    class Parameters(ParamTemplate):
        CVL = Float(-99.)
        CVO = Float(-99.)
        CVR = Float(-99.)
        CVS = Float(-99.)
        REALLOC_DVS = Float(2.0)
        REALLOC_STEM_FRACTION = Float(0.)
        REALLOC_LEAF_FRACTION = Float(0.)
        REALLOC_STEM_RATE = Float(0.)
        REALLOC_LEAF_RATE = Float(0.)
        REALLOC_EFFICIENCY = Float(0.)

    class StateVariables(StatesTemplate):
        TAGP  = Float(-99.)
        GASST = Float(-99.)
        MREST = Float(-99.)
        CEVST = Float(-99.)
        CTRAT = Float(-99.) # 作物整个生育期累计总蒸腾量
        HI    = Float(-99.)
        DOF = Instance(datetime.date)
        FINISH_TYPE = Unicode(allow_none=True)
        LV_REALLOCATED = Float(0.)
        ST_REALLOCATED = Float(0.)

    class RateVariables(RatesTemplate):
        GASS  = Float(-99.)
        MRES  = Float(-99.)
        ASRC  = Float(-99.)
        DMI   = Float(-99.)
        ADMI  = Float(-99.)
        REALLOC_LV = Float(0.)
        REALLOC_ST = Float(0.)
        REALLOC_SO = Float(0.)
        RLV_REALLOCATED = Float(0.)
        RST_REALLOCATED = Float(0.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始的日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，提供参数为键/值对
        """
        
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk, publish=["DMI","ADMI", "REALLOC_LV", "REALLOC_ST", "REALLOC_SO"])
        self.kiosk = kiosk
        
        # 初始化作物的各个子模块
        self.pheno = Phenology(day, kiosk, parvalues)
        self.part  = Partitioning(day, kiosk, parvalues)
        self.assim = Assimilation(day, kiosk, parvalues)
        self.mres  = MaintenanceRespiration(day, kiosk, parvalues)
        self.evtra = Evapotranspiration(day, kiosk, parvalues)
        self.ro_dynamics = Root_Dynamics(day, kiosk, parvalues)
        self.st_dynamics = Stem_Dynamics(day, kiosk, parvalues)
        self.so_dynamics = Storage_Organ_Dynamics(day, kiosk, parvalues)
        self.lv_dynamics = Leaf_Dynamics(day, kiosk, parvalues)

        # 添加用于作物和土壤中N/P/K的记账
        self.n_crop_dynamics = N_crop(day, kiosk, parvalues)
        self.n_stress = N_Stress(day, kiosk, parvalues)

        # 作物初始地上生物量（包括活体和死亡部分）
        TAGP = self.kiosk.TWLV + self.kiosk.TWST + self.kiosk.TWSO
        
        self.states = self.StateVariables(kiosk,
                                          publish=["TAGP", "GASST", "MREST", "HI"],
                                          TAGP=TAGP, GASST=0.0, MREST=0.0, CEVST = 0.0,
                                          CTRAT=0.0, HI=0.0, LV_REALLOCATED = 0., ST_REALLOCATED = 0.,
                                          DOF=None, FINISH_TYPE=None)

        # 检查初始生物量（TDWI）在各器官的分配情况
        checksum = parvalues["TDWI"] - self.states.TAGP - self.kiosk["TWRT"]
        if abs(checksum) > 0.0001:
            msg = "Error in partitioning of initial biomass (TDWI)!"
            raise exc.PartitioningError(msg)
            
        # 分配CROP_FINISH信号的处理函数
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)
    #---------------------------------------------------------------------------
    @staticmethod
    def _check_carbon_balance(day, DMI, GASS, MRES, CVF, pf):
        (FR, FL, FS, FO) = pf
        checksum = (GASS - MRES - (FR+(FL+FS+FO)*(1.-FR)) * DMI/CVF) * \
                    1./(max(0.0001,GASS))
        if abs(checksum) >= 0.0001:
            msg = "Carbon flows not balanced on day %s\n" % day
            msg += "Checksum: %f, GASS: %f, MRES: %f\n" % (checksum, GASS, MRES)
            msg += "FR,L,S,O: %5.3f,%5.3f,%5.3f,%5.3f, DMI: %f, CVF: %f\n" % \
                   (FR, FL, FS, FO, DMI, CVF)
            raise exc.CarbonBalanceError(msg)

    #---------------------------------------------------------------------------
    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # 发育阶段
        self.pheno.calc_rates(day, drv)
        crop_stage = self.pheno.get_variable("STAGE")

        # 如果作物尚未出苗，则无需继续，因为只有发育阶段模块在运行。
        if crop_stage == "emerging":
            return

        # 潜在光合同化量
        PGASS = self.assim(day, drv)

        # 蒸发/蒸腾 速率
        self.evtra(day, drv)

        # 水分胁迫修正
        r.GASS = PGASS * k.RFTRA

        # 呼吸作用
        PMRES = self.mres(day, drv)
        r.MRES  = min(r.GASS, PMRES)

        # 可供分配的净同化物
        r.ASRC  = r.GASS - r.MRES

        # 干物质分配因子（pf）、转换因子（CVF）、干物质增加量（DMI）以及碳平衡校验
        pf = self.part.calc_rates(day, drv)
        CVF = 1./((pf.FL/p.CVL + pf.FS/p.CVS + pf.FO/p.CVO) *
                  (1.-pf.FR) + pf.FR/p.CVR)
        r.DMI = CVF * r.ASRC
        self._check_carbon_balance(day, r.DMI, r.GASS, r.MRES,
                                   CVF, pf)

        # TODO: 可将再分配机制移动到可被7.3和8.1共享的独立模块
        # 茎/叶的干物质再分配
        if k.DVS < p.REALLOC_DVS:
            r.REALLOC_LV = 0.0
            r.REALLOC_ST = 0.0
            r.REALLOC_SO = 0.0
        else:
            if self._WST_REALLOC is None:  # 再分配开始时，计算最大可再分配的生物量
                self._WST_REALLOC = k.WST * p.REALLOC_STEM_FRACTION
                self._WLV_REALLOC = k.WLV * p.REALLOC_LEAF_FRACTION
            # 按茎/叶干物质损失计算的再分配速率
            if self.states.LV_REALLOCATED < self._WLV_REALLOC:
                r.REALLOC_LV = min(self._WLV_REALLOC * p.REALLOC_LEAF_RATE, self._WLV_REALLOC - self.states.LV_REALLOCATED)
            else:
                r.REALLOC_LV = 0.

            if self.states.ST_REALLOCATED < self._WST_REALLOC:
                r.REALLOC_ST = min(self._WST_REALLOC * p.REALLOC_STEM_RATE, self._WST_REALLOC - self.states.ST_REALLOCATED)
            else:
                r.REALLOC_ST = 0.
            # 按储藏器官增加量的再分配速率，需考虑CVL/CVO比、CVS/CVO比以及呼吸损失
            r.REALLOC_SO = (r.REALLOC_LV + r.REALLOC_ST) * p.REALLOC_EFFICIENCY

        # 计算氮胁迫指数
        self.n_stress(day, drv)

        # 各植株器官的分配

        # 地下部干物质增加与根生长动态
        self.ro_dynamics.calc_rates(day, drv)
        # 地上部干物质增加与分配到茎、叶、贮藏器官
        r.ADMI = (1. - pf.FR) * r.DMI
        self.st_dynamics.calc_rates(day, drv)
        self.so_dynamics.calc_rates(day, drv)
        self.lv_dynamics.calc_rates(day, drv)

        self.n_crop_dynamics.calc_rates(day, drv)

    #---------------------------------------------------------------------------
    @prepare_states
    def integrate(self, day, delt=1.0):
        rates = self.rates
        states = self.states

        # 积分前的作物生育阶段
        crop_stage = self.pheno.get_variable("STAGE")

        # 物候发育
        self.pheno.integrate(day, delt)

        # 如在出苗前，无需继续，因为只有物候在运行。
        # 只需运行 touch()，确保所有状态变量在 kiosk 中可用
        if crop_stage == "emerging":
            self.touch()
            return

        # 干物质分配
        self.part.integrate(day, delt)
        
        # 根、贮藏器官、茎和叶子状态的积分
        self.ro_dynamics.integrate(day, delt)
        self.so_dynamics.integrate(day, delt)
        self.st_dynamics.integrate(day, delt)
        self.lv_dynamics.integrate(day, delt)

        self.n_crop_dynamics.integrate(day, delt)

        # 积分作物地上部（活体+死体）总生物量
        states.TAGP = self.kiosk.TWLV + \
                      self.kiosk.TWST + \
                      self.kiosk.TWSO

        # 记录已再分配生物量的数量
        states.LV_REALLOCATED += rates.REALLOC_LV * delt
        states.ST_REALLOCATED += rates.REALLOC_ST * delt

        # 总净同化量和维持呼吸消耗
        states.GASST += rates.GASS * delt
        states.MREST += rates.MRES * delt
        states.CEVST += self.kiosk.EVS * delt
        states.CTRAT += self.kiosk.TRA * delt
        
    #---------------------------------------------------------------------------
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

    #---------------------------------------------------------------------------
    def _on_CROP_FINISH(self, day, finish_type=None):
        """设置作物收获（DOF）日期及其终止原因（FINISH_TYPE）。
        """
        self._for_finalize["DOF"] = day
        self._for_finalize["FINISH_TYPE"]= finish_type
