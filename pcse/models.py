# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 和 Herman Berghuijs (herman.berghuijs@wur.nl), 2024年5月

from .engine import Engine


class Wofost72_PP(Engine):
    """便捷类，用于运行 WOFOST7.2 潜力产量。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost72_PP.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.2"
    __waterbalance__ = None
    __nitrogenbalance__ = None


class Wofost72_WLP_CWB(Engine):
    """便捷类，用于运行 WOFOST7.2 水分受限产量。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost72_WLP_CWB.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.2"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = None


class Wofost72_Phenology(Engine):
    """便捷类，仅运行 WOFOST7.2 物候。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost72_Pheno.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.2"
    __waterbalance__ = None
    __nitrogenbalance__ = None


class Wofost73_PP(Engine):
    """便捷类，用于运行 WOFOST7.3 潜力产量。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost73_PP.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.3"
    __waterbalance__ = None
    __nitrogenbalance__ = None


class Wofost73_WLP_CWB(Engine):
    """便捷类，用于 Classic Waterbalance 的 WOFOST7.3 水分受限产量运行。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost73_WLP_CWB.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.3"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = None


class Wofost73_WLP_MLWB(Engine):
    """便捷类，用于 Multi-layer Waterbalance 的 WOFOST7.3 水分受限产量运行。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost73_WLP_MLWB.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "7.3"
    __waterbalance__ = "MLWB"
    __nitrogenbalance__ = None


class Lintul10_NWLP_CWB_CNB(Engine):
    """LINTUL 模型（光拦截与利用，Light INTerception and UtiLisation）是一个简单的通用作物模型，
    通过假定恒定的光能利用效率，模拟作物因光拦截与利用所产生的干物质。

    在文献中，这个模型被称为 LINTUL3，能够模拟水分受限和氮素受限条件下的作物生长。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Lintul3.conf"
    __productionlevel__ = "NWLP"
    __cropmodel__ = "LINTUL"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = "CNB"


class FAO_WRSI10_WLP_CWB(Engine):
    """该便捷类用于通过（修正的）FAO WRSI 方法，利用作物需水满足指数计算作物实际用水量。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """

    config = "FAO_WRSI.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "FAO_WRSI"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = None


class Lingra10_PP(Engine):
    """LINGRA 草地模型用于潜力产量模拟的便捷类。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Lingra_PP.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "LINGRA"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = None
    __nitrogenbalance__ = None


class Lingra10_WLP_CWB(Engine):
    """LINGRA 草地模型用于水分受限产量模拟的便捷类。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Lingra_WLP_FD.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "LINGRA"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = None


class Lingra10_NWLP_CWB_CNB(Engine):
    """LINGRA 草地模型用于水分和氮素受限产量模拟的便捷类。

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Lingra_NWLP_FD.conf"
    __productionlevel__ = "NWLP"
    __cropmodel__ = "LINGRA"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = "CNB"


class Wofost81_PP(Engine):
    """WOFOST8.1 潜力产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_PP.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = None
    __nitrogenbalance__ = None


class Wofost81_WLP_CWB(Engine):
    """WOFOST8.1 经典水分平衡法下水分受限产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_WLP_CWB.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = None


class Wofost81_WLP_MLWB(Engine):
    """WOFOST8.1 多层水分平衡法下水分受限产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_WLP_MLWB.conf"
    __productionlevel__ = "WLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = "MLWB"
    __nitrogenbalance__ = None


class Wofost81_NWLP_CWB_CNB(Engine):
    """WOFOST8.1 经典水分平衡法和经典氮素平衡法下水分和氮素受限产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_NWLP_CWB_CNB.conf"
    __productionlevel__ = "NWLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = "CWB"
    __nitrogenbalance__ = "CNB"


class Wofost81_NWLP_MLWB_CNB(Engine):
    """WOFOST8.1 多层水分平衡法和经典氮素平衡法下水分和氮素受限产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_NWLP_MLWB_CNB.conf"
    __productionlevel__ = "NWLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = "MLWB"
    __nitrogenbalance__ = "CNB"


class Wofost81_NWLP_MLWB_SNOMIN(Engine):
    """WOFOST8.1 多层水分平衡法和SNOMIN碳/氮平衡法下水分和氮素受限产量模拟的便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Wofost81_NWLP_MLWB_SNOMIN.conf"
    __productionlevel__ = "NWLP"
    __cropmodel__ = "WOFOST"
    __cropmodelversion__ = "8.1"
    __waterbalance__ = "MLWB"
    __nitrogenbalance__ = "SNOMIN"


class Alcepas10_PP(Engine):
    """ALCEPAS 1.0 洋葱模型的潜力产量模拟便捷类

    参见 `pcse.engine.Engine` 获取参数和关键字说明
    """
    config = "Alcepas10_PP.conf"
    __productionlevel__ = "PP"
    __cropmodel__ = "ALCEPAS"
    __cropmodelversion__ = "1.0"
    __waterbalance__ = None
    __nitrogenbalance__ = None


# 此操作用于保证旧有代码仍能正常工作
Wofost71_PP = Wofost72_PP
Wofost71_WLP_FD = Wofost72_WLP_FD = Wofost72_WLP_CWB
LINTUL3 = Lintul10_NWLP_CWB_CNB
LINGRA_PP = Lingra10_PP
LINGRA_WLP_FD = Lingra10_WLP_CWB
LINGRA_NWLP_FD = Lingra10_NWLP_CWB_CNB
