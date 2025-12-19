# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl)，2024年3月

"""用于读取气象和参数文件的工具。

包含以下数据提供者:
- CABOWeatherDataProvider 读取用于PCSE的CABOWE气象文件
- CABOFileReader 读取CABO参数文件
- PCSEFileReader 读取PCSE格式的参数文件
- ExcelWeatherDataProvider 读取xlsx格式的气象数据
- CSVWeatherDataProvider 读取CSV格式的气象数据
- YAMLAgroManagementReader 读取YAML格式的农业管理数据
- YAMLCropDataProvider 读取YAML格式的作物参数

针对不同WOFOST版本的场地数据提供者:
- WOFOST72SiteDataProvider
- WOFOST73SiteDataProvider
- WOFOST81SiteDataProvider_Classic
- WOFOST81SiteDataProvider_SNOMIN

"""

from .cabo_reader import CABOFileReader
from .cabo_weather import CABOWeatherDataProvider
from .pcsefilereader import PCSEFileReader
from .excelweatherdataprovider import ExcelWeatherDataProvider
from .csvweatherdataprovider import CSVWeatherDataProvider
from .yaml_agro_loader import YAMLAgroManagementReader
from .yaml_cropdataprovider import YAMLCropDataProvider
from .nasapower import NASAPowerWeatherDataProvider
from .openmeteo import OpenMeteoWeatherDataProvider
from .sitedataproviders import WOFOST72SiteDataProvider, WOFOST73SiteDataProvider, \
    WOFOST81SiteDataProvider_Classic, WOFOST81SiteDataProvider_SNOMIN
from .soildataproviders import DummySoilDataProvider