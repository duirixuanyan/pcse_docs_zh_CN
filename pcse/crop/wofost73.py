# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl), 2024年1月

import datetime

from ..traitlets import Float, Int, Instance, Enum, Unicode
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import signals
from .. import exceptions as exc

from .phenology import DVS_Phenology as Phenology
from .assimilation import WOFOST73_Assimilation as Assimilation
from .partitioning import DVS_Partitioning as Partitioning
from .respiration import WOFOST_Maintenance_Respiration as MaintenanceRespiration
from .evapotranspiration import EvapotranspirationWrapper as Evapotranspiration
from .stem_dynamics import WOFOST_Stem_Dynamics as Stem_Dynamics
from .root_dynamics import WOFOST_Root_Dynamics as Root_Dynamics
from .leaf_dynamics import WOFOST_Leaf_Dynamics as Leaf_Dynamics
from .storage_organ_dynamics import WOFOST_Storage_Organ_Dynamics as \
     Storage_Organ_Dynamics


class Wofost73(SimulationObject):
    """
    WOFOST作物模拟各组成部分的顶层组织对象

    CropSimulation对象负责组织作物模拟的各个过程。此外，还包含对整个作物层面相关的参数、速率和状态变量。其包含作为内嵌模拟对象实现的以下过程：

        1. 物候（self.pheno）
        2. 物质分配（self.part）
        3. 光合同化（self.assim）
        4. 维持呼吸（self.mres）
        5. 蒸散发（self.evtra）
        6. 叶片动态（self.lv_dynamics）
        7. 茎秆动态（self.st_dynamics）
        8. 根系动态（self.ro_dynamics）
        9. 储藏器官动态（self.so_dynamics）


    **模拟参数:**

    ======== =============================================== =======  ==========
     名称       描述                                         类型       单位
    ======== =============================================== =======  ==========
    CVL      同化物转化为叶片的换算系数                      SCr         -
    CVO      同化物转化为储藏器官的换算系数                  SCr         -
    CVR      同化物转化为根的换算系数                        SCr         -
    CVS      同化物转化为茎的换算系数                        SCr         -
    ======== =============================================== =======  ==========


    **状态变量:**

    =========== ============================================ ==== ===============
     名称        描述                                        公开       单位
    =========== ============================================ ==== ===============
    TAGP        地上部分总生产量                              N     |kg ha-1|
    GASST       总光合作用量（净同化量加上维持呼吸）          N     |kg CH2O ha-1|
    MREST       总维持呼吸量                                  N     |kg CH2O ha-1|
    CTRAT       作物总蒸腾量                                  N     cm
    HI          收获指数（只在`finalize()`期间计算）          N     -
    DOF         模拟结束日期                                  N     -
    FINISH_TYPE 模拟结束原因（如成熟、收获、叶片枯死等）      N     -
    =========== ============================================ ==== ===============


    **速率变量:**

    =======  ================================================ ==== =============
     名称     描述                                            公开     单位
    =======  ================================================ ==== =============
    GASS     校正水分胁迫后的同化速率                          N   |kg CH2O ha-1 d-1|
    MRES     实际维持呼吸速率，MRES <= GASS                    N   |kg CH2O ha-1 d-1|
    ASRC     可用同化物净量（GASS - MRES）                     N   |kg CH2O ha-1 d-1|
    DMI      总干物质增长（ASRC与加权转化效率的乘积）          Y   |kg ha-1 d-1|
    ADMI     地上部分干物质增加                                Y   |kg ha-1 d-1|
    =======  ================================================ ==== =============

    """
    # 用于重新分配可用生物量的占位符
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
    
    # 在主要作物模拟层面相关的参数、速率和状态变量
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
        CTRAT = Float(-99.) # 作物总蒸腾量
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
        :param day: 模拟开始日期
        :param kiosk: 此 PCSE 实例的变量 kiosk
        :param parvalues: `ParameterProvider` 对象，提供参数的键/值对
        """
        
        self.params = self.Parameters(parvalues)
        self.rates  = self.RateVariables(kiosk, publish=["DMI","ADMI", "REALLOC_LV", "REALLOC_ST", "REALLOC_SO"])
        self.kiosk = kiosk
        
        # 初始化作物的组件
        self.pheno = Phenology(day, kiosk, parvalues)
        self.part  = Partitioning(day, kiosk, parvalues)
        self.assim = Assimilation(day, kiosk, parvalues)
        self.mres  = MaintenanceRespiration(day, kiosk, parvalues)
        self.evtra = Evapotranspiration(day, kiosk, parvalues)
        self.ro_dynamics = Root_Dynamics(day, kiosk, parvalues)
        self.st_dynamics = Stem_Dynamics(day, kiosk, parvalues)
        self.so_dynamics = Storage_Organ_Dynamics(day, kiosk, parvalues)
        self.lv_dynamics = Leaf_Dynamics(day, kiosk, parvalues)

        # 作物初始的地上（活+死）生物量总量
        TAGP = self.kiosk["TWLV"] + \
               self.kiosk["TWST"] + \
               self.kiosk["TWSO"]
        self.states = self.StateVariables(kiosk,
                                          publish=["TAGP", "GASST", "MREST", "HI"],
                                          TAGP=TAGP, GASST=0.0, MREST=0.0,
                                          CTRAT=0.0, HI=0.0, LV_REALLOCATED = 0., ST_REALLOCATED = 0.,
                                          DOF=None, FINISH_TYPE=None)

        # 检查 TDWI 在器官间的分配正确性
        checksum = parvalues["TDWI"] - self.states.TAGP - self.kiosk["TWRT"]
        if abs(checksum) > 0.0001:
            msg = "Error in partitioning of initial biomass (TDWI)!"
            raise exc.PartitioningError(msg)
            
        # 关联 CROP_FINISH 信号的处理器
        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)

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

    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        r = self.rates
        k = self.kiosk

        # 发育进程
        self.pheno.calc_rates(day, drv)
        crop_stage = self.pheno.get_variable("STAGE")

        # 如果作物尚未出苗，则无需继续，因为只有物候模块在运行
        if crop_stage == "emerging":
            return

        # 潜在同化速率
        PGASS = self.assim(day, drv)

        # （蒸发）蒸腾速率
        self.evtra(day, drv)

        # 水分胁迫修正
        r.GASS = PGASS * k.RFTRA

        # 呼吸作用
        PMRES = self.mres(day, drv)
        r.MRES  = min(r.GASS, PMRES)

        # 可用净同化物
        r.ASRC  = r.GASS - r.MRES

        # 干物质量分配因子（pf）、转换因子（CVF）、干物质量增加量（DMI），以及碳平衡检验
        pf = self.part.calc_rates(day, drv)
        CVF = 1./((pf.FL/p.CVL + pf.FS/p.CVS + pf.FO/p.CVO) *
                  (1.-pf.FR) + pf.FR/p.CVR)
        r.DMI = CVF * r.ASRC
        self._check_carbon_balance(day, r.DMI, r.GASS, r.MRES,
                                   CVF, pf)

        # 茎/叶物质再分配
        if k.DVS < p.REALLOC_DVS:
            r.REALLOC_LV = 0.0
            r.REALLOC_ST = 0.0
            r.REALLOC_SO = 0.0
        else:
            # 开始再分配，计算最大可再分配生物量
            if self._WST_REALLOC is None:
                self._WST_REALLOC = k.WST * p.REALLOC_STEM_FRACTION
                self._WLV_REALLOC = k.WLV * p.REALLOC_LEAF_FRACTION
            # 按茎/叶干物质损耗计算的再分配速率
            if self.states.LV_REALLOCATED < self._WLV_REALLOC:
                r.REALLOC_LV = min(self._WLV_REALLOC * p.REALLOC_LEAF_RATE, self._WLV_REALLOC - self.states.LV_REALLOCATED)
            else:
                r.REALLOC_LV = 0.

            if self.states.ST_REALLOCATED < self._WST_REALLOC:
                r.REALLOC_ST = min(self._WST_REALLOC * p.REALLOC_STEM_RATE, self._WST_REALLOC - self.states.ST_REALLOCATED)
            else:
                r.REALLOC_ST = 0.
            # 按贮藏器官增加量计算的再分配速率，考虑CVL/CVO、CVS/CVO比与呼吸耗损
            r.REALLOC_SO = (r.REALLOC_LV + r.REALLOC_ST) * p.REALLOC_EFFICIENCY

        # 植物器官间分配

        # 地下部分干物质量增加及根系动态
        self.ro_dynamics.calc_rates(day, drv)
        # 地上部分干物质量增加及分配到茎、叶、贮藏器官
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

        # 发育进程
        self.pheno.integrate(day, delt)

        # 如果作物尚未出苗，则无需继续
        # 因为此时只有发育进程在运行。
        # 只需运行一次 touch()，确保所有状态变量都已在 kiosk 中可用
        if crop_stage == "emerging":
            self.touch()
            return

        # 物质分配
        self.part.integrate(day, delt)
        
        # 积分叶片、贮藏器官、茎和根的状态
        self.ro_dynamics.integrate(day, delt)
        self.so_dynamics.integrate(day, delt)
        self.st_dynamics.integrate(day, delt)
        self.lv_dynamics.integrate(day, delt)

        # 积分作物地上（活+死）总干物质量
        states.TAGP = self.kiosk["TWLV"] + \
                      self.kiosk["TWST"] + \
                      self.kiosk["TWSO"]

        # 总同化量与维持呼吸耗损
        states.GASST += rates.GASS * delt
        states.MREST += rates.MRES * delt
        
        # 作物总蒸腾量（CTRAT）
        states.CTRAT += self.kiosk.TRA * delt

        # 记录已再分配的生物量
        states.LV_REALLOCATED += rates.REALLOC_LV * delt
        states.ST_REALLOCATED += rates.REALLOC_ST * delt

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

    def _on_CROP_FINISH(self, day, finish_type=None):
        """用于设置作物生长结束日(DOF)以及作物结束原因(FINISH_TYPE)的处理函数。
        """
        self._for_finalize["DOF"] = day
        self._for_finalize["FINISH_TYPE"]= finish_type
