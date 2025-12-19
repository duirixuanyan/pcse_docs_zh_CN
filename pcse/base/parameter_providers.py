# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2024
"""用于创建PCSE仿真单元的基类。

通常这些类不应被直接使用，而是应通过子类化的方式用于创建PCSE仿真单元。
"""
import sys
import logging
from collections import Counter
if sys.version_info > (3, 8):
    from collections.abc import MutableMapping
else:
    from collections import MutableMapping

from .. import exceptions as exc


class ParameterProvider(MutableMapping):
    """为所有参数集（作物、土壤、站点）提供类字典接口的类。
    作用类似于ChainMap，但有一些额外功能。

    此类的设计思想有三点。首先，通过将不同的参数集（sitedata, cropdata, soildata）封装到一个对象中，
    可以使每个SimulationObject的`initialize()`方法签名在所有SimulationObject间保持一致。
    其次，当需要不同的参数值集合时，ParameterProvider本身可以很方便地进行调整。例如在进行作物轮作时，
    同时需要不同的cropdata，这时可以通过增强ParameterProvider的功能，在引擎收到CROP_START信号时切换一组新的cropdata。
    最后，可以通过对某个参数设置`override`，轻松更改特定参数值。

    另见 `MultiCropDataProvider`
    """
    _maps = list()
    _sitedata = dict()
    _soildata = dict()
    _cropdata = dict()
    _timerdata = dict()
    _override = dict()
    _iter = 0  # 迭代器计数器
    _ncrops_activated = 0  # 记录`set_crop_type()`被调用的次数

    def __init__(self, sitedata=None, timerdata=None, soildata=None, cropdata=None):
        if sitedata is not None:
            self._sitedata = sitedata
        else:
            self._sitedata = {}
        if cropdata is not None:
            self._cropdata = cropdata
        else:
            self._cropdata = {}
        if soildata is not None:
            self._soildata = soildata
        else:
            self._soildata = {}
        if timerdata is not None:
            self._timerdata = timerdata
        else:
            self._timerdata = {}
        self._override = {}
        self._derived = {}
        self._maps = [self._override, self._sitedata, self._timerdata, self._soildata,
                      self._cropdata, self._derived]
        self._test_uniqueness()

    def set_active_crop(self, crop_name=None, variety_name=None, crop_start_type=None, crop_end_type=None):
        """激活给定 crop_name 和 variety_name 的作物参数。

        :param crop_name: 用于标识作物名称的字符串，此参数会被忽略，因为这里只假定有一个作物。
        :param variety_name: 用于标识品种名称的字符串，此参数会被忽略，因为这里只假定有一个作物。
        :param crop_start_type: 给定作物的开始类型: 'sowing'|'emergence'
        :param crop_end_type: 给定作物的结束类型: 'maturity'|'harvest'|'earliest'

        若存在作物轮作，则每次新作物开始时需要一套新的作物参数。本方法会激活给定 crop_name 和 variety_name 的作物参数。
        crop_name、variety_name、crop_start_type 和 crop_end_type 参数均在农事管理中定义并由 AgroManager 支持。

        注意，许多 CropDataProvider 并未为轮作设计，仅支持一个默认激活的作物参数集。在这种情况下，调用 set_active_crop()
        无实际效果，crop_name 和 variety_name 参数会被忽略。
        支持轮作的 CropDataProvider 必须显式继承 pcse.base.MultiCropDataProvider 才会被识别。

        除了作物参数外，此方法还会设定作物的 crop_start_type 和 crop_end_type，相关信息为物候模块所需。

        """

        self._timerdata["CROP_START_TYPE"] = crop_start_type
        self._timerdata["CROP_END_TYPE"] = crop_end_type
        if isinstance(self._cropdata, MultiCropDataProvider):
            # 拥有 MultiCropDataProvider，因此需设置当前激活的作物和品种
            self._cropdata.set_active_crop(crop_name, variety_name)
        else:
            # 没有 MultiCropDataProvider，意味着不支持作物轮作。
            # 第一次调用是允许的，若后续继续调用，则发出警告，因为无法改变作物参数集
            if self._ncrops_activated == 0:
                pass
            else:
                # 已多次调用
                msg = "A second crop was scheduled: however, the CropDataProvider does not " \
                      "support multiple crop parameter sets. This will only work for crop" \
                      "rotations with the same crop."
                self.logger.warning(msg)

        self._ncrops_activated += 1
        self._test_uniqueness()

    @property
    def logger(self):
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)

    def set_override(self, varname, value, check=True):
        """覆盖参数提供者中参数 varname 的值。

        覆盖特定参数的值通常在运行不同参数集或校准时很有用。

        注意，如果 check=True（默认值），varname 应该已存在于 site, timer, soil 或 cropdata 之一中。
        """

        if check:
            if varname in self:
                self._override[varname] = value
            else:
                msg = "Cannot override '%s', parameter does not already exist." % varname
                raise exc.PCSEError(msg)
        else:
            self._override[varname] = value

    def clear_override(self, varname=None):
        """从已覆盖参数集合中移除参数 varname。

        如果不带参数，会移除所有已覆盖参数。
        """

        if varname is None:
            self._override.clear()
        else:
            if varname in self._override:
                self._override.pop(varname)
            else:
                msg = "Cannot clear varname '%s' from override" % varname
                raise exc.PCSEError(msg)

    def set_derived(self, varname, value):
        """允许为 ParameterProvider 设置额外的“derived”参数。

        有时需要从已有参数计算新参数。例如某些特定 pF 值下的土壤湿度和导电率。

        :param varname: 参数名
        :param value: 参数值
        """

        self._derived[varname] = value

    def _test_uniqueness(self):
        """检查参数名是否唯一，如出现重复则抛出错误。

        注意不检查 self._override 中的参数名唯一性，因为该部分专用于覆盖参数。
        """
        parnames = []
        for mapping in [self._sitedata, self._timerdata, self._soildata, self._cropdata]:
            parnames.extend(mapping.keys())
        unique = Counter(parnames)
        for parname, count in unique.items():
            if count > 1:
                msg = "Duplicate parameter found: %s" % parname
                raise exc.PCSEError(msg)

    @property
    def _unique_parameters(self):
        """返回所有参数集合中唯一参数名的列表。

        这包括 self._override 中的参数，以便于遍历整个 ParameterProvider 中的所有参数。
        """
        s = []
        for mapping in self._maps:
            s.extend(mapping.keys())
        return sorted(list(set(s)))

    def __getitem__(self, key):
        """返回给定参数（key）的值。

        注意：在 self._map 的搜索顺序中，self._override 会被优先检查，
        这样可以确保已被覆盖的参数优先返回。

        :param key: 要返回的参数名
        """
        for mapping in self._maps:
            if key in mapping:
                return mapping[key]
        raise KeyError(key)

    def __contains__(self, key):
        """判断参数名 key 是否存在于参数集合中。"""
        for mapping in self._maps:
            if key in mapping:
                return True
        return False

    def __str__(self):
        msg = "ParameterProvider providing %i parameters, %i parameters overridden: %s."
        return msg % (len(self), len(self._override), self._override.keys())

    def __setitem__(self, key, value):
        """通过 value 覆盖已有参数（key）。

         被覆盖的参数会添加到 self._override。注意只有*已存在*的参数
         可以通过这种方式覆盖。如果需要真正添加一个*新*参数，
         请使用：ParameterProvider.set_override(key, value, check=False)

        :param key: 需要覆盖的参数名
        :param value: 参数值
        """
        if key in self:
            self._override[key] = value
        else:
            msg = "Cannot override parameter '%s', parameter does not exist. " \
                  "to bypass this check use: set_override(parameter, value, check=False)" % key
            raise exc.PCSEError(msg)

    def __delitem__(self, key):
        """从 self._override 删除参数。

        只有存在于 self._override 的参数才能被删除。注意，如果一个参数被覆盖，
        当通过该方法删除后会恢复为原始值。

        :param key: 要删除的参数名
        """
        if key in self._override:
            self._override.pop(key)
        elif key in self:
            msg = "Cannot delete default parameter: %s" % key
            raise exc.PCSEError(msg)
        else:
            msg = "Parameter not found!"
            raise KeyError(msg)

    def __len__(self):
        return len(self._unique_parameters)

    def __iter__(self):
        return self

    def next(self):
        i = self._iter
        if i < len(self):
            self._iter += 1
            return self._unique_parameters[self._iter - 1]
        else:
            self._iter = 0
            raise StopIteration


class MultiCropDataProvider(dict):

    def __init__(self):
        dict.__init__(self)
        self._store = {}

    def set_active_crop(self, crop_name, variety_name):
        """设置由 crop_name 和 variety_name 标识的作物参数。

        需要由 MultiCropDataProvider 的每个子类实现。
        """
        msg = "'set_crop_type' method should be implemented specifically for each" \
              "subclass of MultiCropDataProvider."
        raise NotImplementedError(msg)

