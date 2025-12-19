# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from .. import exceptions as exc


class _GenericSiteDataProvider(dict):
    """通用场地数据提供者

    该类根据 _defaults 和 _required 检查作为关键字参数提供的值

    _defaults = {"VARNAME": (default, {maxvalue, minvalue}, type),
                }
    _required = ["VARNAME"]
    """

    def __init__(self, **kwargs):
        dict.__init__(self)

        for par_name, (default_value, par_range, par_conversion) in self._defaults.items():
            if par_name not in kwargs:
                # 参数未被提供，如果可能使用默认值
                if par_name in self._required:
                    msg = "Value for parameter '%s' must be provided!" % par_name
                    raise exc.PCSEError(msg)
                else:
                    par_value = default_value
            else:
                # 参数已被提供，检查其类型和范围
                par_value = par_conversion(kwargs.pop(par_name))
                if isinstance(par_range, set):
                    # 允许的值由一个集合组成
                    if par_value not in par_range:
                        msg = "Value for parameter '%s' can only have values: %s" % (par_name, par_range)
                        raise exc.PCSEError(msg)
                else:
                    if isinstance(par_value, list):
                        if not all(par_range[0] <= x <= par_range[1] for x in par_value):
                            msg = "At least one of the values for parameter '%s' out of range %s-%s" % \
                                  (par_name, par_range[0], par_range[1])
                            raise exc.PCSEError(msg)
                    else:
                        if not (par_range[0] <= par_value <= par_range[1]):
                            msg = "Value for parameter '%s' out of range %s-%s" % \
                                  (par_name, par_range[0], par_range[1])
                            raise exc.PCSEError(msg)
            self[par_name] = par_value

        # 检查 kwargs 是否为空
        if kwargs:
            msg = f"Unknown parameter values provided to {self.__class__}: %s" % kwargs
            raise exc.PCSEError(msg)


class WOFOST72SiteDataProvider(_GenericSiteDataProvider):
    """WOFOST 7.2 的场地数据提供者

    WOFOST 7.2 的场地特定参数可以通过此数据提供者，也可以通过普通的 Python 字典提供。
    实现该数据提供者的唯一目的是对 WOFOST 的场地参数进行文档说明、校验，并给出合理的默认值。

    可通过此数据提供者设置以下场地特定参数::

        - IFUNRN    表示降雨非入渗部分是否为暴雨大小的函数 (1)，
                    或不是 (0)。默认0
        - NOTINF    未入渗到土壤中的最大降雨比例 [0-1]，默认 0。
        - SSMAX     土壤表面能够储存的最大水深 [cm]
        - SSI       初始土壤表面水储量 [cm]
        - WAV       整个土壤剖面初始含水量 [cm]
        - SMLIM     初始根区最大土壤含水率 [0-1]，默认 0.4

    目前，只有 WAV 是必须指定的。
    """

    _defaults = {"IFUNRN": (0, {0, 1}, int),
                 "NOTINF": (0, [0., 1.], float),
                 "SSI": (0., [0., 100.], float),
                 "SSMAX": (0., [0., 100.], float),
                 "WAV": (None, [0., 100.], float),
                 "SMLIM": (0.4, [0., 1.], float)}
    _required = ["WAV"]


class WOFOST73SiteDataProvider(_GenericSiteDataProvider):
    """WOFOST 7.3 的场地数据提供者

    WOFOST 7.3 的场地特定参数可以通过此数据提供者，也可以通过普通的 Python 字典提供。
    实现该数据提供者的唯一目的是对 WOFOST 的场地参数进行文档说明、校验，并给出合理的默认值。

    可通过此数据提供者设置以下场地特定参数::

        - IFUNRN    表示降雨非入渗部分是否为暴雨大小的函数 (1)，
                    或不是 (0)。默认0
        - NOTINF    未入渗到土壤中的最大降雨比例 [0-1]，默认 0。
        - SSMAX     土壤表面能够储存的最大水深 [cm]
        - SSI       初始土壤表面水储量 [cm]
        - WAV       整个土壤剖面初始含水量 [cm]
        - SMLIM     初始根区最大土壤含水率 [0-1]，默认 0.4
        - CO2       大气 CO2 浓度（ppm）

    WAV 和 CO2 为必填项。
    """

    _defaults = {"IFUNRN": (0, {0, 1}, int),
                 "NOTINF": (0, [0., 1.], float),
                 "SSI": (0., [0., 100.], float),
                 "SSMAX": (0., [0., 100.], float),
                 "WAV": (None, [0., 100.], float),
                 "SMLIM": (0.4, [0., 1.], float),
                 "CO2": (None, [320, 700], float)}
    _required = ["WAV", "CO2"]


class WOFOST81SiteDataProvider_Classic(_GenericSiteDataProvider):
    """WOFOST 8.1 经典水和氮平衡下的场地数据提供者

    WOFOST 8.1 的场地特定参数可以通过此数据提供者，也可以通过普通的 Python 字典提供。
    实现该数据提供者的唯一目的是对 WOFOST 的场地参数进行文档说明、校验，并给出合理的默认值。

    可通过此数据提供者设置以下场地特定参数::

        - IFUNRN        表示降雨非入渗部分是否为暴雨大小的函数 (1)，
                        或不是 (0)。默认0
        - NOTINF        未入渗到土壤中的最大降雨比例 [0-1]，默认 0。
        - SSMAX         土壤表面能够储存的最大水深 [cm]
        - SSI           初始土壤表面水储量 [cm]
        - WAV           整个土壤剖面初始含水量 [cm]
        - SMLIM         初始根区最大土壤含水率 [0-1]，默认 0.4
        - CO2           大气 CO2 水平（ppm），默认 360。
        - BG_N_SUPPLY   背景大气沉降N补给，单位 kg/ha/天。在高氮污染区可能高达每年25 kg/ha。默认0.0
        - NSOILBASE     土壤可利用的基础氮量。通常为上次种植周期剩余的营养物（盈余营养物、作物残茬或绿肥）推算。
        - NSOILBASE_FR  土壤每日有机质矿化释放的氮比例
        - NAVAILI       系统初始化时氮池中的可利用氮量 [kg/ha]

    目前，初始水分可用性（WAV）与初始可用营养物（NAVAILI）为必填项。
    """

    _defaults = {"IFUNRN": (0, {0, 1}, int),
                 "NOTINF": (0, [0., 1.], float),
                 "SSI": (0., [0., 100.], float),
                 "SSMAX": (0., [0., 100.], float),
                 "WAV": (None, [0., 100.], float),
                 "SMLIM": (0.4, [0., 1.], float),
                 "CO2": (None, [300., 1400.], float),
                 "BG_N_SUPPLY": (0, (0, 0.1), float),
                 "NSOILBASE": (0, (0, 100), float),
                 "NSOILBASE_FR": (0.025, (0, 100), float),
                 "NAVAILI": (None, (0, 250), float),
                 }
    _required = ["WAV", "NAVAILI", "CO2"]


class WOFOST81SiteDataProvider_SNOMIN(_GenericSiteDataProvider):
    """WOFOST 8.1 用于 SNOMIN C/N 平衡的场地数据提供者

    可通过此数据提供者设置以下场地特定参数::

        - IFUNRN        表示降雨非入渗部分是否为暴雨大小的函数 (1)，
                        或不是 (0)。默认0
        - NOTINF        未入渗到土壤中的最大降雨比例 [0-1]，默认 0。
        - SSMAX         土壤表面能够储存的最大水深 [cm]
        - SSI           初始土壤表面水储量 [cm]
        - WAV           整个土壤剖面初始含水量 [cm]
        - SMLIM         初始根区最大土壤含水率 [0-1]，默认 0.4
        - CO2           大气 CO2 水平，目前约 400 [ppm]
        - A0SOM         有机物初始年龄 (24.0)  [年]
        - CNRatioBio    微生物生物量碳氮比  (9.0) [kg C kg-1 N]
        - FASDIS        同化与异化速率比 (0.5) [-]
        - KDENIT_REF    参考反硝化一阶速率 (0.06) [d-1]
        - KNIT_REF      参考硝化一阶速率 (1.0) [d-1]
        - KSORP         吸附系数 (0.0005) [m3 soil kg-1 soil]
        - MRCDIS        有机碳-异化速率与反硝化响应因子的米氏常数 (0.001) [kg C m-2 d-1]
        - NH4ConcR      雨水中 NH4-N 浓度 (0.9095) [mg NH4+-N L-1 water]
        - NO3ConcR      雨水中 NO3-N 浓度 (2.1) [mg NO3--N L-1 water]
        - NH4I          每一土层的初始 NH4+ 含量  [kg NH4+ ha-1]。数量应与土壤层数配置一致。若模型刚施肥，初始值可高达300-500 kg/ha NH4/NO3。
        - NO3I          每一土层的初始 NO3-N 含量 [kg NO3-N ha-1]。数量应与土壤层数配置一致。若模型刚施肥，初始值可高达300-500 kg/ha NH4/NO3。
        - WFPS_CRIT     临界土壤孔隙充水率 (0.8)  [m3 water m-3 pores]


        *重要*: 部分参数的有效范围仍不确定，因此本处范围之外的值在特定情况下也可能有效。

    """
    _required = ["WAV", "CO2", "NH4I", "NO3I", ]
    _defaults = {"IFUNRN": (0, {0, 1}, int),
                 "NOTINF": (0, [0., 1.], float),
                 "SSI": (0., [0., 100.], float),
                 "SSMAX": (0., [0., 100.], float),
                 "WAV": (None, [0., 100.], float),
                 "SMLIM": (0.4, [0., 1.], float),
                 "CO2": (None, [300., 1400.], float),
                 "A0SOM": (24.0, [5.0, 40.0], float),
                 "CNRatioBio": (9.0, [5.0, 20.0], float),
                 "FASDIS": (0.5, [0, 0.6], float),
                 "KDENIT_REF": (0.06, [0.0, 0.1], float),
                 "KNIT_REF": (1.0, [0.9, 1.0], float),
                 "KSORP": (0.0005, [0.0001, 0.001], float),
                 "MRCDIS": (0.001, [0.0001, 0.01], float),
                 "NH4ConcR": (0.0, [0.0, 5.], float),
                 "NO3ConcR": (0.0, [0.0, 20.], float),
                 "NH4I": (None, [0.0, 300.0], list),
                 "NO3I": (None, [0.0, 500.0], list),
                 "WFPS_CRIT": (0.8, [0.5, 0.99], float),
                 }
