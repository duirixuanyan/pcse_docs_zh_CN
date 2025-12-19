.. include:: abbreviations.txt
PCSE 中可用的模型
========================

PCSE 包实现了几个在瓦赫宁根开发的作物模型。这些模型包括：

    - 用于模拟大田作物生长和发育的 WOFOST 作物系统模型。
    - 用于模拟大田作物生长和发育的 LINTUL3 模型。与 WOFOST 相比，LINTUL3 在估算 |CO2| 同化时采用了简化方法。
    - 用于模拟草地生产力的 LINGRA 模型。
    - 专门针对洋葱模拟开发的 ALCEPAS 模型。

PCSE 还提供了 FAO-WRSI（水分需求满足指数）模型的实现，该模型能够计算反映作物遭受水分胁迫程度的指数。

此外，这些作物模型可以与不同复杂度的土壤水分和氮素动态模型结合使用，从简单模型（称为“classic”）到使用多层土壤的高级水分平衡模型，以及高级土壤碳/氮模型（SNOMIN）。

下表列出了 PCSE 中可用并可从 `pcse.models` 包导入的模型。对于每个模型，表中展示了其生产水平及模型中包含的一些特性。大多数模型的名称由一组代码组成，格式如下：<modelname><version>_<productionlevel>_<waterbalance>_<nitrogenbalance>

.. 表由以下网站生成: https://tableconvert.com/restructuredtext-generator
.. https://rsted.info.ucl.ac.be/

=========================== ============================ ============ ====================== ============ =============== ===========
 模型名                       生产水平                      CO2影响        生物量再分配         氮素动态       水分平衡         氮素平衡
=========================== ============================ ============ ====================== ============ =============== ===========
 Wofost72_Pheno              仅物候期模拟                                                                  N/A             N/A
 Wofost72_PP                 潜力产量模拟                                                                  N/A             N/A
 Wofost72_WLP_CWB            限水产量模拟                                                                  经典模型         N/A
 Wofost73_PP                 潜力产量模拟                  X            X                                  N/A             N/A
 Wofost73_WLP_CWB            限水产量模拟                  X            X                                  经典模型         N/A
 Wofost73_WLP_MLWB           限水产量模拟                  X            X                                  多层模型         N/A
 Wofost81_PP                 潜力产量模拟                  X            X                     X            N/A             N/A
 Wofost81_WLP_CWB            限水产量模拟                  X            X                     X            经典模型         N/A
 Wofost81_WLP_MLWB           限水产量模拟                  X            X                     X            多层模型         N/A
 Wofost81_NWLP_CWB_CNB       限水和氮素产量模拟            X            X                     X            经典模型         经典模型
 Wofost81_NWLP_MLWB_CNB      限水和氮素产量模拟            X            X                     X            多层模型         经典模型
 Wofost81_NWLP_MLWB_SNOMIN   限水和氮素产量模拟            X            X                     X            多层模型         SNOMIN
 Lingra10_PP                 潜力产量模拟                  X                                               N/A             N/A
 Lingra10_WLP_CWB            限水产量模拟                  X                                               经典模型         N/A
 Lingra10_NWLP_CWB_CNB       限水和氮素产量模拟            X                                    X          经典模型         经典模型
 Lintul10_NWLP_CWB_CNB       限水和氮素产量模拟                                                 X          经典模型         经典模型
 Alcepas10_PP                潜力产量模拟                                                                  N/A             N/A
 FAO_WRSI10_WLP_CWB          限水产量模拟                                                                  经典模型         N/A
=========================== ============================ ============ ====================== ============ =============== ===========