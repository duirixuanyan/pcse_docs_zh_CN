# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""
用于计算多种养分相关胁迫因子的类:
    NNI      氮营养指数
    PNI      磷营养指数
    KNI      钾营养指数
    NPKI     NPK营养指数 (等于N/P/K指数的最小值)
    NPKREF   基于NPKI的同化还原因子
"""

from ...traitlets import Float
from ...util import limit, AfgenTrait
from ...base import ParamTemplate, SimulationObject, RatesTemplate
from ...decorators import prepare_rates

class NPK_Stress(SimulationObject):
    """ 通过[NPK]营养指数实现NPK胁迫计算。

    胁迫因子的计算基于植株叶片和茎部生物量中的N/P/K质量浓度。对于每种养分库，都会基于叶和茎的生物量计算四种浓度:
    - 实际浓度，基于养分的实际含量除以实际叶和茎的生物量得出。
    - 最大浓度，即植物能够吸收到叶和茎中的最大养分浓度。
    - 临界浓度，即能够维持不受N/P/K限制的生长速度所需的浓度。对于P和K，临界浓度通常等于最大浓度。
      对于N，临界浓度可以低于最大浓度。这个浓度有时也被称为“最佳浓度”。
    - 剩余浓度，指被锁定在植株结构性生物量中且不能再动员的部分。

    胁迫指数(SI) 按以下公式根据这些浓度的简单比率确定:

    :math:`SI = (C_{a} - C_{r})/(C_{c} - C_{r})`

    其中下标`a`、`r`和`c`分别表示该养分的实际、剩余和临界浓度。
    这个公式应用于N、P和K，可得到氮营养指数(NNI)、磷营养指数(PNI)和钾营养指数(KNI)。
    然后，NPK指数(NPKI)作为NNI、PNI、KNI中的最小值计算得到。最后，同化的还原因子(NPKREF)通过NPKI和光能利用效率还原因子(NLUE_NPK)计算。

    **仿真参数 (Simulation parameters)**

    ============  ============================================= ======================
     名称         说明                                            单位
    ============  ============================================= ======================
    NMAXLV_TB     叶片最大N浓度，作为DVS的函数                   kg N kg-1 干生物量
    PMAXLV_TB     与P类似                                       kg P kg-1 干生物量
    KMAXLV_TB     与K类似                                       kg K kg-1 干生物量

    NMAXRT_FR     根系最大N浓度(相对于叶片最大N浓度的比例)         -
    PMAXRT_FR     与P类似                                       -
    KMAXRT_FR     与K类似                                       -

    NMAXST_FR     茎部最大N浓度(相对于叶片最大N浓度的比例)         -
    PMAXST_FR     与P类似                                       -
    KMAXST_FR     与K类似                                       -

    NCRIT_FR      植物营养器官(叶+茎)最大N浓度的临界浓度比例        -
    PCRIT_FR      与P类似                                       -
    KCRIT_FR      与K类似                                       -

    NRESIDLV      叶片剩余N分数 (不可再动员)                      kg N kg-1 干生物量
    PRESIDLV      叶片剩余P分数                                  kg P kg-1 干生物量
    KRESIDLV      叶片剩余K分数                                  kg K kg-1 干生物量

    NRESIDST      茎部剩余N分数                                  kg N kg-1 干生物量
    PRESIDST      茎部剩余P分数                                  kg P kg-1 干生物量
    KRESIDST      茎部剩余K分数                                  kg K kg-1 干生物量

    NLUE_NPK      由于营养(N-P-K)胁迫导致RUE降低的系数             -
    ============  ============================================= ======================

    **速率变量 (Rate variables)**

    这里的速率变量并非真正意义上的速率变量，而是派生状态变量，不代表某一具体速率。但由于这些变量直接用于速率计算，这里仍统一归类。

    =======  ================================================= ==== ==============
     名称    说明                                              Pbl      单位
    =======  ================================================= ==== ==============
    NNI      氮营养指数                                         Y       -
    PNI      磷营养指数                                         N       -
    KNI      钾营养指数                                         N       -
    NPKI     NNI、PNI、KNI的最小值                              Y       -
    RFNPK    基于NPKI和参数NLUE_NPK的|CO2|同化还原因子          N       -
    =======  ================================================= ==== ==============


    **外部依赖 (External dependencies):**

    ==========  =================================== =====================  ==============
     名称        说明                                   提供者                单位
    ==========  =================================== =====================  ==============
    DVS          作物发育阶段                        DVS_Phenology         -
    WST          活茎干重                            WOFOST_Stem_Dynamics  |kg ha-1|
    WLV          活叶干重                            WOFOST_Leaf_Dynamics  |kg ha-1|
    NamountLV    叶片N含量                           NPK_Crop_Dynamics     |kg ha-1|
    NamountST    茎部N含量                           NPK_Crop_Dynamics     |kg ha-1|
    PamountLV    叶片P含量                           NPK_Crop_Dynamics     |kg ha-1|
    PamountST    茎部P含量                           NPK_Crop_Dynamics     |kg ha-1|
    KamountLV    叶片K含量                           NPK_Crop_Dynamics     |kg ha-1|
    KamountST    茎部K含量                           NPK_Crop_Dynamics     |kg ha-1|
    ==========  =================================== =====================  ==============
    """

    class Parameters(ParamTemplate):
        NMAXLV_TB = AfgenTrait()  # 最大叶片氮浓度，随dvs的函数
        PMAXLV_TB = AfgenTrait()  # 最大叶片磷浓度，随dvs的函数
        KMAXLV_TB = AfgenTrait()  # 最大叶片钾浓度，随dvs的函数
        NCRIT_FR = Float(-99.)   # 最优（临界）氮浓度占最大氮浓度的比例
        PCRIT_FR = Float(-99.)   # 最优（临界）磷浓度占最大磷浓度的比例
        KCRIT_FR = Float(-99.)   # 最优（临界）钾浓度占最大钾浓度的比例
        NMAXRT_FR = Float(-99.)  # 根部最大氮浓度占最大叶片氮浓度的比例
        NMAXST_FR = Float(-99.)  # 茎部最大氮浓度占最大叶片氮浓度的比例
        PMAXST_FR = Float(-99.)  # 根部最大磷浓度占最大叶片磷浓度的比例
        PMAXRT_FR = Float(-99.)  # 茎部最大磷浓度占最大叶片磷浓度的比例
        KMAXRT_FR = Float(-99.)  # 根部最大钾浓度占最大叶片钾浓度的比例
        KMAXST_FR = Float(-99.)  # 茎部最大钾浓度占最大叶片钾浓度的比例
        NRESIDLV = Float(-99.)  # 叶片剩余氮分数 [kg N kg-1 干物重]
        NRESIDST = Float(-99.)  # 茎部剩余氮分数 [kg N kg-1 干物重]
        PRESIDLV = Float(-99.)  # 叶片剩余磷分数 [kg P kg-1 干物重]
        PRESIDST = Float(-99.)  # 茎部剩余磷分数 [kg P kg-1 干物重]
        KRESIDLV = Float(-99.)  # 叶片剩余钾分数 [kg K kg-1 干物重]
        KRESIDST = Float(-99.)  # 茎部剩余钾分数 [kg K kg-1 干物重]
        NLUE_NPK = Float(-99.)  # 因营养（N-P-K）胁迫导致RUE降低的系数

    class RateVariables(RatesTemplate):
        NNI = Float()
        PNI = Float()
        KNI = Float()
        NPKI = Float()
        RFNPK = Float()

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 当前日期
        :param kiosk: 该PCSE实例的变量kiosk
        :param parvalues: 带有参数键/值对的ParameterProvider
        """

        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["NPKI", "NNI"])

    @prepare_rates
    def __call__(self, day, drv):
        """
        :param day: 当前日期
        :param drv: 驱动变量
        :return: 元组 (NNI, NPKI, NPKREF)
        """
        p = self.params
        r = self.rates
        k = self.kiosk

        # 叶片中NPK最大浓度 (kg N kg-1 干物重)
        NMAXLV = p.NMAXLV_TB(k.DVS)
        PMAXLV = p.PMAXLV_TB(k.DVS)
        KMAXLV = p.KMAXLV_TB(k.DVS)

        # 茎部NPK最大浓度 (kg N kg-1 干物重)
        NMAXST = p.NMAXST_FR * NMAXLV
        PMAXST = p.PMAXRT_FR * PMAXLV
        KMAXST = p.KMAXST_FR * KMAXLV
        
        # 地上部活的植被总生物量 (kg 干物重 ha-1)
        VBM = k.WLV + k.WST
      
        # 地上部活体生物量中NPK临界（最优）含量与其浓度
        NcriticalLV  = p.NCRIT_FR * NMAXLV * k.WLV
        NcriticalST  = p.NCRIT_FR * NMAXST * k.WST
        
        PcriticalLV = p.PCRIT_FR * PMAXLV * k.WLV
        PcriticalST = p.PCRIT_FR * PMAXST * k.WST

        KcriticalLV = p.KCRIT_FR * KMAXLV * k.WLV
        KcriticalST = p.KCRIT_FR * KMAXST * k.WST
        
        # 如果地上部活体生物量为0，则最优值取0
        if VBM > 0.:
            NcriticalVBM = (NcriticalLV + NcriticalST)/VBM
            PcriticalVBM = (PcriticalLV + PcriticalST)/VBM
            KcriticalVBM = (KcriticalLV + KcriticalST)/VBM
        else:
            NcriticalVBM = PcriticalVBM = KcriticalVBM = 0.

        # 地上部活体单位质量NPK浓度 (kg N/P/K kg-1 干物重)
        # 若地上部活体生物量为0，浓度为0
        if VBM > 0.:
            NconcentrationVBM  = (k.NamountLV + k.NamountST)/VBM
            PconcentrationVBM  = (k.PamountLV + k.PamountST)/VBM
            KconcentrationVBM  = (k.KamountLV + k.KamountST)/VBM
        else:
            NconcentrationVBM = PconcentrationVBM = KconcentrationVBM = 0.

        # 地上部活体生物量中NPK剩余浓度 (kg N/P/K kg-1 干物重)
        # 若地上部活体生物量为0，剩余浓度为0
        if VBM > 0.:
            NresidualVBM = (k.WLV * p.NRESIDLV + k.WST * p.NRESIDST)/VBM
            PresidualVBM = (k.WLV * p.PRESIDLV + k.WST * p.PRESIDST)/VBM
            KresidualVBM = (k.WLV * p.KRESIDLV + k.WST * p.KRESIDST)/VBM
        else:
            NresidualVBM = PresidualVBM = KresidualVBM = 0.
            
        if (NcriticalVBM - NresidualVBM) > 0.:
            r.NNI = limit(0.001, 1.0, (NconcentrationVBM - NresidualVBM)/(NcriticalVBM - NresidualVBM))
        else:
            r.NNI = 0.001
            
        if (PcriticalVBM - PresidualVBM) > 0.:
            r.PNI = limit(0.001, 1.0, (PconcentrationVBM - PresidualVBM)/(PcriticalVBM - PresidualVBM))
        else:
           r.PNI = 0.001
            
        if (KcriticalVBM-KresidualVBM) > 0:
            r.KNI = limit(0.001, 1.0, (KconcentrationVBM - KresidualVBM)/(KcriticalVBM - KresidualVBM))
        else:
            r.KNI = 0.001
      
        r.NPKI = min(r.NNI, r.PNI, r.KNI)

        # 同化作用的营养胁迫（NPK）修正因子
        r.RFNPK = limit(0., 1.0, 1. - (p.NLUE_NPK * (1.0001 - r.NPKI) ** 2))
         
        return r.NNI, r.NPKI, r.RFNPK
