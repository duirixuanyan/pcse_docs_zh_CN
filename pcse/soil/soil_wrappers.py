# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl), 2024年1月
"""该模块封装了土壤的水分和养分组分，使其能够在同一个模型中联合运行。只有在WOFOST 8+中才需要使用这些封装类，因为WOFOST 7x 版本并未模拟养分限制的生产，因此可以直接在配置中导入水分平衡模块。
"""
from pcse.base import SimulationObject
from .classic_waterbalance import WaterbalanceFD, WaterbalancePP
from .multilayer_waterbalance import WaterBalanceLayered, WaterBalanceLayered_PP
from .n_soil_dynamics import N_Soil_Dynamics, N_PotentialProduction
from .snomin import SNOMIN
from ..traitlets import Instance


class BaseSoilWrapper(SimulationObject):
    """用于封装土壤水分和养分/碳平衡的基类。
    """
    waterbalance_class = None
    nutrientbalance_class = None
    waterbalance = Instance(SimulationObject)
    nutrientbalance = Instance(SimulationObject)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的开始日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param parvalues: 包含参数键值对的字典
        """
        if self.waterbalance_class is not None:
            self.waterbalance = self.waterbalance_class(day, kiosk, parvalues)
        if self.nutrientbalance_class is not None:
            self.nutrientbalance = self.nutrientbalance_class(day, kiosk, parvalues)

    def calc_rates(self, day, drv):
        if self.waterbalance_class is not None:
            self.waterbalance.calc_rates(day, drv)
        if self.nutrientbalance_class is not None:
            self.nutrientbalance.calc_rates(day, drv)

    def integrate(self, day, delt=1.0):
        if self.waterbalance_class is not None:
            self.waterbalance.integrate(day, delt)
        if self.nutrientbalance_class is not None:
            self.nutrientbalance.integrate(day, delt)


class SoilModuleWrapper_PP(BaseSoilWrapper):
    """封装用于潜力生产的土壤水分平衡与土壤氮素平衡。
    """
    waterbalance_class = WaterbalancePP
    nutrientbalance_class = N_PotentialProduction


class SoilModuleWrapper_WLP_CWB(BaseSoilWrapper):
    """封装用于自由排水条件下的经典土壤水分平衡，以及仅受土壤水分限制生产条件下的无限制氮素平衡。
    """
    waterbalance_class = WaterbalanceFD
    nutrientbalance_class = N_PotentialProduction


class SoilModuleWrapper_NWLP_CWB_CNB(BaseSoilWrapper):
    """封装用于土壤水分与氮素均受限生产条件下，采用简单水分和氮素动力学的经典土壤水分平衡与经典氮素平衡。
    """
    waterbalance_class = WaterbalanceFD
    nutrientbalance_class = N_Soil_Dynamics


class SoilModuleWrapper_WLP_MLWB(BaseSoilWrapper):
    """封装用于土壤水分与氮素均受限生产条件下，多层土壤水分平衡与经典氮素平衡。
    """
    waterbalance_class = WaterBalanceLayered
    nutrientbalance_class = N_PotentialProduction

class SoilModuleWrapper_NWLP_MLWB_CNB(BaseSoilWrapper):
    """封装用于土壤水分与氮素均受限生产条件下，采用先进水分动力学和简单氮素动力学的自由排水土壤水分平衡与氮素平衡。
    """
    waterbalance_class = WaterBalanceLayered
    nutrientbalance_class = N_Soil_Dynamics


class SoilModuleWrapper_NWLP_MLWB_SNOMIN(BaseSoilWrapper):
    """封装用于自由排水条件下，采用先进SNOMIN碳/氮平衡的土壤水分平衡。适用于土壤水分与氮素均受限，且需要先进的水分和碳/氮动力学的生产条件。
    """
    waterbalance_class = WaterBalanceLayered
    nutrientbalance_class = SNOMIN

