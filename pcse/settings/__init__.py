# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import os, sys
import importlib
import inspect

from . import default_settings

class Settings(object):
    """
    PCSE 的设置。

    默认值将从模块 pcse.settings.default_settings.py 中读取。
    用户设置从 $HOME/.pcse/user_settings.py 读取，并覆盖默认值；
    所有可能变量的列表请参见默认设置文件。
    """

    def __setattr__(self, name, value):
        if name == "METEO_CACHE_DIR":
            if not os.path.exists(value):
                os.mkdir(value)
        if name == "LOG_DIR":
            if not os.path.exists(value):
                os.mkdir(value)
        object.__setattr__(self, name, value)


    def __init__(self):
        # 从全局设置中更新此 dict（但只针对所有大写的设置项）
        for setting in dir(default_settings):
            if setting.isupper():
                setattr(self, setting, getattr(default_settings, setting))
            elif setting.startswith("_"):
                pass
            else:
                msg = ("Warning: settings should be ALL_CAPS. Setting '%s' in default_" +
                       "settings will be ignored.") % setting
                print(msg)

        try:
            mod = importlib.import_module("user_settings")
        except ImportError as e:
            raise ImportError(
                ("Could not import settings '%s' (Is it on sys.path? Is there an import" +
                 " error in the settings file?): %s") % ("$HOME/.pcse/user_settings.py", e)
            )

        # 从用户定义的模块导入设置
        for setting in dir(mod):
            if setting.isupper():
                setattr(self, setting, getattr(mod, setting))
            elif setting.startswith("_"):
                pass
            else:
                msg = ("Warning: settings should be ALL_CAPS. Setting '%s' in user_" +
                       "settings will be ignored.") % setting
                print(msg)

# 从 default_settings 和 user_settings 初始化设置
settings = Settings()
