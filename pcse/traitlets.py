# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""
该模块仅用于确保所有PCSE模块可以从 .traitlets 内部导入，
同时该模块从正确的位置加载实际的 traitlets 模块。此外，
部分 traits 被修改以允许 `None` 作为默认值并将其值强制转换为 float()。

目前使用的是适配过的 traitlets 包 'traitlets_pcse'。将来，
当 `observe()` 在 `type=All` 上实现后，可能会使用默认的 traitlets 包。
"""
from traitlets_pcse import *
import traitlets_pcse as tr


class Instance(tr.Instance):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Instance.__init__(self, *args, **kwargs)


class Enum(tr.Enum):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Enum.__init__(self, *args, **kwargs)


class Unicode(tr.Unicode):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Unicode.__init__(self, *args, **kwargs)


class Bool(tr.Bool):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Bool.__init__(self, *args, **kwargs)


class Float(tr.Float):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Float.__init__(self, *args, **kwargs)

    def validate(self, obj, value):
        try:
            value = float(value)
        except:
            self.error(obj, value)
        return value


class Int(tr.Int):

    def __init__(self, *args, **kwargs):
        if 'allow_none' not in kwargs:
            kwargs['allow_none'] = True
        tr.Int.__init__(self, *args, **kwargs)
