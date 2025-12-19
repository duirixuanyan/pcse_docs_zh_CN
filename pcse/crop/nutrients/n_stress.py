# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""
计算氮胁迫因子的类：

"""

from ...traitlets import Float
from ...util import limit, AfgenTrait
from ...base import ParamTemplate, SimulationObject, RatesTemplate
from ...decorators import prepare_rates

class N_Stress(SimulationObject):
    """通过[N]营养指数实现氮胁迫计算。

    HB 20220405 对本子程序进行了大量更改，需要重新编写文档。

    ============  ============================================= ======================
     名称           描述                                         单位
    ============  ============================================= ======================
    NMAXLV_TB      叶片中最大氮浓度，作为DVS的函数               kg N kg-1 干物质
    NMAXRT_FR      根系中最大氮浓度，为叶片最大氮浓度的分数      -
    NMAXSO         谷粒中最大氮浓度                             kg N kg-1 干物质
    NMAXST_FR      茎秆中最大氮浓度，为叶片最大氮浓度的分数      -
    NCRIT_FR       植物营养器官（叶片+茎秆）                     -
                   最大氮浓度的关键分数
    NRESIDLV       叶片中残留氮分数                             kg N kg-1 干物质
    NRESIDST       茎秆中残留氮分数                             kg N kg-1 干物质
    RGRLAI_MIN     最大氮胁迫下指数生长期                       d-1
                   相对生长速率
    ============  ============================================= ======================

    **速率变量**

    这里的速率变量并不是传统意义上的真实速率变量，而是派生状态变量，并不代表速率。
    但由于它们直接用于速率变量的计算，故放在此处。

    =======  ================================================= ==== ==============
     名称      描述                                            发布   单位
    =======  ================================================= ==== ==============
    NSLLV     氮胁迫因子                                       Y    -
    RFRGRL    指数生长期相对生长速率的还原因子                 Y    -
    =======  ================================================= ==== ==============


    **外部依赖：**

    ==========  =================================== =================================== ==============
     名称        描述                                 提供者                            单位
    ==========  =================================== =================================== ==============
    DVS          作物发育阶段                         DVS_Phenology                      -
    WST          活茎干重                             WOFOST_Stem_Dynamics               |kg ha-1|
    WLV          活叶片干重                           WOFOST_Leaf_Dynamics               |kg ha-1|
    WSO          经济器官干重                         WOFOST_Storage_Organ_Dynamics      |kg ha-1|
    NamountLV    叶片中氮的含量                       N_Crop_Dynamics                    |kg ha-1|
    NamountST    茎干中氮的含量                       N_Crop_Dynamics                    |kg ha-1|
    ==========  =================================== =================================== ==============
    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()
        NSLLV_TB = AfgenTrait() 
        NMAXRT_FR = Float(-99.)
        NMAXST_FR = Float(-99.)
        NRESIDLV = Float(-99.)
        NRESIDST = Float(-99.)
        NMAXSO = Float(-99.)
        RGRLAI_MIN = Float(-99.)
        RGRLAI = Float(-99.)

    class RateVariables(RatesTemplate):
        NSLLV = Float()
        RFRGRL = Float()

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 当前日期
        :param kiosk: 此PCSE实例中的变量kiosk
        :param parvalues: 包含参数键/值对的ParameterProvider
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish = ["NSLLV", "RFRGRL"])

    @prepare_rates
    def __call__(self, day, drv):
        """
        :param day: 当前日期
        :param drv: 驱动变量
        """
        p = self.params
        r = self.rates
        k = self.kiosk

        # 叶片中最大氮浓度 (kg N kg-1 干物质)
        NMAXLV = p.NMAXLV_TB(k.DVS)

        # 茎秆中最大氮浓度 (kg N kg-1 干物质)
        NMAXST = p.NMAXST_FR * NMAXLV
        
        # 由于氮胁迫引起的叶片死亡的倍数因子计算
        NamountABG = k.NamountLV + k.NamountST + k.NamountSO
        NamountABGMX = k.WLV * NMAXLV + k.WST * NMAXST + k.WSO * p.NMAXSO

        if NamountABGMX / NamountABG <= 1:
            NstressIndexDLV = 1.
        elif NamountABGMX / NamountABG > 2:
            NstressIndexDLV = 2.
        else:
            NstressIndexDLV = NamountABGMX / NamountABG 
        
        r.NSLLV = p.NSLLV_TB(NstressIndexDLV)

        # 指数生长期叶生长速率的还原因子计算
        if(k.WLV > 0):
            NconcentrationLV = k.NamountLV / k.WLV
        else:
            NconcentrationLV = 0.

        NstressIndexRGRLAI = max(0, min(1, (NconcentrationLV - 0.9 * NMAXLV) / (NMAXLV - 0.9 * NMAXLV)))
        r.RFRGRL = 1 - (1.-NstressIndexRGRLAI)*(p.RGRLAI-p.RGRLAI_MIN) / p.RGRLAI