# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究所，瓦赫宁根大学与研究中心
# Allard de Wit (allard.dewit@wur.nl)，2024年3月
from ..traitlets import Float, Int, Instance, Dict
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, SimulationObject, RatesTemplate
from ..util import AfgenTrait

class WOFOST_Maintenance_Respiration(SimulationObject):
    """WOFOST中的维持呼吸

    WOFOST 计算维持呼吸方式是与需要维持的植物器官的干重成正比，每个器官可以分配不同的维持系数。
    用各器官的干重乘以对应的维持系数得到相对维持呼吸（`RMRES`），然后通过参数`RFSETB`对其进行衰老修正。
    最后，实际的维持呼吸速率通过日平均温度计算，假定温度每升高10摄氏度，维持呼吸速率相对增加量由`Q10`定义。

    **模拟参数：** （需在 cropdata 字典中提供）:

    =======  ============================================= =======  ============
     名称      说明                                         类型       单位
    =======  ============================================= =======  ============
    Q10      维持呼吸速率随温度每升高10度的相对增加量               SCr         -
    RMR      根的相对维持呼吸速率                           SCr     |kg CH2O kg-1 d-1|
    RMS      茎的相对维持呼吸速率                           SCr     |kg CH2O kg-1 d-1|
    RML      叶的相对维持呼吸速率                           SCr     |kg CH2O kg-1 d-1|
    RMO      储藏器官的相对维持呼吸速率                     SCr     |kg CH2O kg-1 d-1|
    =======  ============================================= =======  ============

    **状态和速率变量：**

    `WOFOSTMaintenanceRespiration` 通过 `__call__()` 方法直接返回潜在维持呼吸 PMRES，同时也将其包括在对象的速率变量中。

    **速率变量：**

    =======  =========================================  ==== =============
     名称      说明                                     公开      单位
    =======  =========================================  ==== =============
    PMRES    潜在维持呼吸速率                           N    |kg CH2O ha-1 d-1|
    =======  =========================================  ==== =============

    **发送或处理的信号**

    无

    **外部依赖：**

    =======  ===================================== =============================  ============
     名称      说明                                  提供者                         单位
    =======  ===================================== =============================  ============
    DVS      作物发育阶段                          DVS_Phenology                   -
    WRT      活根干重                              WOFOST_Root_Dynamics           |kg ha-1|
    WST      活茎干重                              WOFOST_Stem_Dynamics           |kg ha-1|
    WLV      活叶干重                              WOFOST_Leaf_Dynamics           |kg ha-1|
    WSO      活储藏器官干重                        WOFOST_Storage_Organ_Dynamics  |kg ha-1|
    =======  ===================================== =============================  ============

    """
    
    class Parameters(ParamTemplate):
        Q10 = Float(-99.)
        RMR = Float(-99.)
        RML = Float(-99.)
        RMS = Float(-99.)
        RMO = Float(-99.)
        RFSETB = AfgenTrait()

    class RateVariables(RatesTemplate):
        PMRES = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的开始日期
        :param kiosk: 此 PCSE 实例的变量存取器
        :param parvalues: `ParameterProvider` 对象，提供参数的键/值对
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
        
    def __call__(self, day, drv):
        p = self.params
        kk = self.kiosk
        
        # 计算各器官干重与各自维持系数(RMR, RML, RMS, RMO)的乘积之和，得到相对维持呼吸（RMRES）
        RMRES = (p.RMR * kk["WRT"] +
                 p.RML * kk["WLV"] +
                 p.RMS * kk["WST"] +
                 p.RMO * kk["WSO"])
        # 用RFSETB参数(老化修正)修正RMRES
        RMRES *= p.RFSETB(kk["DVS"])
        # 根据日平均温度(TEMP)与Q10效应，计算温度修正系数TEFF
        TEFF = p.Q10**((drv.TEMP-25.)/10.)
        # 计算潜在维持呼吸速率
        self.rates.PMRES = RMRES * TEFF
        return self.rates.PMRES
