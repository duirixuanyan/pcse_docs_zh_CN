# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

from ...traitlets import Float, Instance
from ...decorators import prepare_rates, prepare_states
from ...base import ParamTemplate, StatesTemplate, RatesTemplate, \
    SimulationObject

class NPK_Translocation(SimulationObject):
    """
    负责作物根、叶和茎中的N/P/K向储藏器官转运的记账工作。

    首先，该函数计算可转运N/P/K的状态。
    这种可转运的数量被定义为N/P/K总量超出残留N/P/K量的部分，
    其中残留量由残留浓度与活体生物量的乘积计算得出。残留量被锁定在植物结构生物量中，
    不能再被调动。可转运量分别针对茎、根和叶计算，并作为状态变量
    Ntranslocatable、Ptranslocatable 和 Ktranslocatable 发布。

    总体转运速率由供应量（可转运量）和储藏器官的需求量（在 Demand_Uptake 组件中计算）两者的最小值决定。
    实际N/P/K从不同器官的转运速率假设按各器官可转运量的比例在根、茎和叶之间分配。

    **模拟参数**

    ===============  =============================================  ======================
     名称              描述                                         单位
    ===============  =============================================  ======================
    NRESIDLV          叶中残留N分数                                 kg N kg-1 干生物量
    PRESIDLV          叶中残留P分数                                 kg P kg-1 干生物量
    KRESIDLV          叶中残留K分数                                 kg K kg-1 干生物量

    NRESIDST          茎中残留N分数                                 kg N kg-1 干生物量
    PRESIDST          茎中残留P分数                                 kg P kg-1 干生物量
    KRESIDST          茎中残留K分数                                 kg K kg-1 干生物量

    NPK_TRANSLRT_FR   根中NPK转运量占叶和茎NPK总转运量的比例         -
    ===============  =============================================  ======================


    **状态变量**

    ===================  ================================================= ===== ============
     名称                    描述                                            Pbl      单位
    ===================  ================================================= ===== ============
    NtranslocatableLV     活叶中可转运的N数量                               N    |kg N ha-1|
    PtranslocatableLV     活叶中可转运的P数量                               N    |kg P ha-1|
    KtranslocatableLV     活叶中可转运的K数量                               N    |kg K ha-1|
    NtranslocatableST     活茎中可转运的N数量                               N    |kg N ha-1|
    PtranslocatableST     活茎中可转运的P数量                               N    |kg P ha-1|
    KtranslocatableST     活茎中可转运的K数量                               N    |kg K ha-1|
    NtranslocatableRT     活根中可转运的N数量                               N    |kg N ha-1|
    PtranslocatableRT     活根中可转运的P数量                               N    |kg P ha-1|
    KtranslocatableRT     活根中可转运的K数量                               N    |kg K ha-1|
    Ntranslocatable       可转运至储藏器官的N总量                            Y    [kg N ha-1]
                          （全部器官汇总）
    Ptranslocatable       可转运至储藏器官的P总量                            Y    [kg P ha-1]
                          （全部器官汇总）
    Ktranslocatable       可转运至储藏器官的K总量                            Y    [kg K ha-1]
                          （全部器官汇总）
    ===================  ================================================= ===== ============


    **速率变量**

    ===================  ================================================= ==== ==============
     名称                 描述                                              Pbl      单位
    ===================  ================================================= ==== ==============
    RNtranslocationLV     叶中N的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RPtranslocationLV     叶中P的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RKtranslocationLV     叶中K的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RNtranslocationST     茎中N的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RPtranslocationST     茎中P的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RKtranslocationST     茎中K的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RNtranslocationRT     根中N的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RPtranslocationRT     根中P的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    RKtranslocationRT     根中K的重量减少（转运速率）                       Y    |kg ha-1 d-1|
    ===================  ================================================= ==== ==============

    **发送或处理的信号**

    无

    **外部依赖：**

    ===========  ================================ ======================  ===========
     名称           描述                               提供方                单位
    ===========  ================================ ======================  ===========
    DVS           作物发育阶段                      DVS_Phenology           -
    WST           活茎干重                          WOFOST_Stem_Dynamics   |kg ha-1|
    WLV           活叶干重                          WOFOST_Leaf_Dynamics   |kg ha-1|
    WRT           活根干重                          WOFOST_Root_Dynamics   |kg ha-1|
    NamountLV     叶中N的含量                       NPK_Crop_Dynamics      |kg ha-1|
    NamountST     茎中N的含量                       NPK_Crop_Dynamics      |kg ha-1|
    NamountRT     根中N的含量                       NPK_Crop_Dynamics      |kg ha-1|
    PamountLV     叶中P的含量                       NPK_Crop_Dynamics      |kg ha-1|
    PamountST     茎中P的含量                       NPK_Crop_Dynamics      |kg ha-1|
    PamountRT     根中P的含量                       NPK_Crop_Dynamics      |kg ha-1|
    KamountLV     叶中K的含量                       NPK_Crop_Dynamics      |kg ha-1|
    KamountST     茎中K的含量                       NPK_Crop_Dynamics      |kg ha-1|
    KamountRT     根中K的含量                       NPK_Crop_Dynamics      |kg ha-1|
    ===========  ================================ ======================  ===========
    """

    class Parameters(ParamTemplate):
        NRESIDLV = Float(-99.)  # 叶片中残留的N比例 [kg N kg-1 干物质]
        NRESIDST = Float(-99.)  # 茎秆中残留的N比例 [kg N kg-1 干物质]
        NRESIDRT = Float(-99.)  # 根系中残留的N比例 [kg N kg-1 干物质]

        PRESIDLV = Float(-99.)  # 叶片中残留的P比例 [kg P kg-1 干物质]
        PRESIDST = Float(-99.)  # 茎秆中残留的P比例 [kg P kg-1 干物质]
        PRESIDRT = Float(-99.)  # 根系中残留的P比例 [kg P kg-1 干物质]

        KRESIDLV = Float(-99.)  # 叶片中残留的K比例 [kg K kg-1 干物质]
        KRESIDST = Float(-99.)  # 茎秆中残留的K比例 [kg K kg-1 干物质]
        KRESIDRT = Float(-99.)  # 根系中残留的K比例 [kg K kg-1 干物质]

        NPK_TRANSLRT_FR = Float(-99.)  # 根系NPK向储藏器官转运占（叶、茎转运总量的比例）
                                       # 相关NPK从叶和茎转运的总量分数

    class RateVariables(RatesTemplate):
        RNtranslocationLV = Float(-99.)  # 叶片中N的转运速率 [kg ha-1 d-1]
        RNtranslocationST = Float(-99.)  # 茎秆中N的转运速率 [kg ha-1 d-1]
        RNtranslocationRT = Float(-99.)  # 根系中N的转运速率 [kg ha-1 d-1]

        RPtranslocationLV = Float(-99.)  # 叶片中P的转运速率 [kg ha-1 d-1]
        RPtranslocationST = Float(-99.)  # 茎秆中P的转运速率 [kg ha-1 d-1]
        RPtranslocationRT = Float(-99.)  # 根系中P的转运速率 [kg ha-1 d-1]

        RKtranslocationLV = Float(-99.)  # 叶片中K的转运速率 [kg ha-1 d-1]
        RKtranslocationST = Float(-99.)  # 茎秆中K的转运速率 [kg ha-1 d-1]
        RKtranslocationRT = Float(-99.)  # 根系中K的转运速率 [kg ha-1 d-1]

    class StateVariables(StatesTemplate):
        NtranslocatableLV = Float(-99.)  # 叶片中可转运的N含量 [kg N ha-1]
        NtranslocatableST = Float(-99.)  # 茎秆中可转运的N含量 [kg N ha-1]
        NtranslocatableRT = Float(-99.)  # 根系中可转运的N含量 [kg N ha-1]
        
        PtranslocatableLV = Float(-99.)  # 叶片中可转运的P含量 [kg P ha-1]
        PtranslocatableST = Float(-99.)  # 茎秆中可转运的P含量 [kg P ha-1]
        PtranslocatableRT = Float(-99.)  # 根系中可转运的P含量 [kg P ha-1]
        
        KtranslocatableLV = Float(-99.)  # 叶片中可转运的K含量 [kg K ha-1]
        KtranslocatableST = Float(-99.)  # 茎秆中可转运的K含量 [kg K ha-1]
        KtranslocatableRT = Float(-99.)  # 根系中可转运的K含量 [kg K ha-1]

        Ntranslocatable = Float(-99.)  # 可转运至储藏器官的N总量 [kg N ha-1]
        Ptranslocatable = Float(-99.)  # 可转运至储藏器官的P总量 [kg P ha-1]
        Ktranslocatable = Float(-99.)  # 可转运至储藏器官的K总量 [kg K ha-1]

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的开始日期
        :param kiosk: 当前PCSE实例的变量kiosk
        :param parvalues: WOFOST作物数据的键/值对字典
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["RNtranslocationLV", "RNtranslocationST", "RNtranslocationRT",
                                                        "RPtranslocationLV", "RPtranslocationST", "RPtranslocationRT",
                                                        "RKtranslocationLV", "RKtranslocationST", "RKtranslocationRT"])

        self.states = self.StateVariables(kiosk,
            NtranslocatableLV=0., NtranslocatableST=0., NtranslocatableRT=0., PtranslocatableLV=0., PtranslocatableST=0.,
            PtranslocatableRT=0., KtranslocatableLV=0., KtranslocatableST=0. ,KtranslocatableRT=0.,
            Ntranslocatable=0., Ptranslocatable=0., Ktranslocatable=0.,
            publish=["Ntranslocatable", "Ptranslocatable", "Ktranslocatable"])
        self.kiosk = kiosk
        
    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        s = self.states
        k = self.kiosk

        # 从叶片、茎秆、根系向储藏器官的吸收分配
        # 假设N/P/K从每个器官均匀分配。
        # 如果可转运N/P/K的量=0，则转运速率为0
        if s.Ntranslocatable > 0.:
            r.RNtranslocationLV = k.RNuptakeSO * s.NtranslocatableLV / s.Ntranslocatable
            r.RNtranslocationST = k.RNuptakeSO * s.NtranslocatableST / s.Ntranslocatable
            r.RNtranslocationRT = k.RNuptakeSO * s.NtranslocatableRT / s.Ntranslocatable
        else:
            r.RNtranslocationLV = r.RNtranslocationST = r.RNtranslocationRT = 0.

        if s.Ptranslocatable > 0:
            r.RPtranslocationLV = k.RPuptakeSO * s.PtranslocatableLV / s.Ptranslocatable
            r.RPtranslocationST = k.RPuptakeSO * s.PtranslocatableST / s.Ptranslocatable
            r.RPtranslocationRT = k.RPuptakeSO * s.PtranslocatableRT / s.Ptranslocatable
        else:
            r.RPtranslocationLV = r.RPtranslocationST = r.RPtranslocationRT = 0.

        if s.Ktranslocatable > 0:
            r.RKtranslocationLV = k.RKuptakeSO * s.KtranslocatableLV / s.Ktranslocatable
            r.RKtranslocationST = k.RKuptakeSO * s.KtranslocatableST / s.Ktranslocatable
            r.RKtranslocationRT = k.RKuptakeSO * s.KtranslocatableRT / s.Ktranslocatable
        else:
            r.RKtranslocationLV = r.RKtranslocationST = r.RKtranslocationRT = 0.

    @prepare_states
    def integrate(self, day, delt=1.0):
        p = self.params
        s = self.states
        k = self.kiosk
        
        # 各器官中可转运的N含量 [kg N ha-1]
        s.NtranslocatableLV = max(0., k.NamountLV - k.WLV * p.NRESIDLV)
        s.NtranslocatableST = max(0., k.NamountST - k.WST * p.NRESIDST)
        s.NtranslocatableRT = max(0., k.NamountRT - k.WRT * p.NRESIDRT)

        # 各器官中可转运的P含量 [kg P ha-1]
        s.PtranslocatableLV = max(0., k.PamountLV - k.WLV * p.PRESIDLV)
        s.PtranslocatableST = max(0., k.PamountST - k.WST * p.PRESIDST)
        s.PtranslocatableRT = max(0., k.PamountRT - k.WRT * p.PRESIDRT)

        # 各器官中可转运的K含量 [kg K ha-1]
        s.KtranslocatableLV = max(0., k.KamountLV - k.WLV * p.KRESIDLV)
        s.KtranslocatableST = max(0., k.KamountST - k.WST * p.KRESIDST)
        s.KtranslocatableRT = max(0., k.KamountRT - k.WRT * p.KRESIDRT)

        # 各器官中可转运的NPK总量 [kg N ha-1]
        s.Ntranslocatable = s.NtranslocatableLV + s.NtranslocatableST + s.NtranslocatableRT
        s.Ptranslocatable = s.PtranslocatableLV + s.PtranslocatableST + s.PtranslocatableRT
        s.Ktranslocatable = s.KtranslocatableLV + s.KtranslocatableST + s.KtranslocatableRT
