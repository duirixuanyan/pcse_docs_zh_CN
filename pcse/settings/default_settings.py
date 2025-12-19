# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

"""PCSE设置

默认值将从文件 'pcse/settings/default_settings.py' 读取。
用户特定设置从 '$HOME/.pcse/user_settings.py' 读取。用户设置中定义的任何设置将覆盖默认设置。

设置必须用全大写字母定义，并可通过 pcse.settings.settings 作为属性访问。

例如，在 'crop' 下的模块中使用设置:

    from ..settings import settings
    print(settings.METEO_CACHE_DIR)

不是全大写的设置将产生警告。为了避免对不是设置的所有内容（如导入的模块）产生警告，需要在名称前加下划线。
"""

import os as _os
import pcse.util as _util

PCSE_USER_HOME =  _os.path.join(_util.get_user_home(), ".pcse")

# 气象缓存文件的存放位置
METEO_CACHE_DIR = _os.path.join(PCSE_USER_HOME, "meteo_cache")

# 对气象变量进行范围检查
METEO_RANGE_CHECKS = True

# PCSE在状态积分后将所有速率变量归零以保持一致性。
# 为了提高性能，你可以禁用这个行为。
ZEROFY = True

# 日志配置
# PCSE的日志系统包含两个日志处理器。一个用于将日志消息发送到屏幕（'console'），另一个用于将消息写入文件。
# 日志的位置和名称由 LOG_DIR 和 LOG_FILE_NAME 定义。此外，console 和 file 处理器能够设置日志级别（由 LOG_LEVEL_FILE 和 LOG_LEVEL_CONSOLE 定义）。
# 默认情况下，这些级别是 INFO 和 WARNING，意味着 INFO 及以上级别的消息会写入日志文件，WARNING 及以上级别会显示在控制台上。
# 如需更详细的日志消息，可以将日志级别设置为 DEBUG，但这将产生大量日志信息。
#
# 日志文件大小可达1MB。当文件达到此大小时会创建新文件，并重命名旧文件。为了避免日志文件过大，仅保留最近7个日志文件。

# 日志目录
LOG_DIR = _os.path.join(PCSE_USER_HOME, "logs")
# 日志文件名
LOG_FILE_NAME = _os.path.join(LOG_DIR, "pcse.log")
# 写入日志文件的日志级别
LOG_LEVEL_FILE = "INFO"
# 控制台输出的日志级别
LOG_LEVEL_CONSOLE = "ERROR"
# 日志配置
LOG_CONFIG = \
            {
                'version': 1,
                'disable_existing_loggers': True,
                # 格式化器定义日志输出的格式
                'formatters': {
                    'standard': {
                        'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                    },
                    'brief': {
                        'format': '[%(levelname)s] - %(message)s'
                    },
                },
                # 处理器定义日志的输出方式
                'handlers': {
                    'console': {
                        'level':LOG_LEVEL_CONSOLE,
                        'class':'logging.StreamHandler',
                        'formatter':'brief'
                    },
                    'file': {
                        'level':LOG_LEVEL_FILE,
                        'class':'logging.handlers.RotatingFileHandler',
                        'formatter':'standard',
                        'filename':LOG_FILE_NAME,
                        'maxBytes': 1024**2,  # 日志文件最大1MB
                        'backupCount': 7,     # 最多保留7个历史日志文件
                        'mode':'a',
                        'encoding': 'utf8'
                    },
                },
                # 根日志配置
                'root': {
                         'handlers': ['console', 'file'],
                         'propagate': True,
                         'level':'NOTSET'
                }
            }
