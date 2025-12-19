# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import os
import datetime as dt

import numpy as np
import pandas as pd
import requests

from pcse.base import WeatherDataProvider, WeatherDataContainer
from pcse.util import ea_from_tdew, reference_ET, check_angstromAB
from pcse.exceptions import PCSEError
from pcse.settings import settings

# 定义一些lambda，用于单位换算
MJ_to_J = lambda x: x * 1e6
mm_to_cm = lambda x: x / 10.
tdew_to_hpa = lambda x: ea_from_tdew(x) * 10.
to_date = lambda d: d.date()


class NASAPowerWeatherDataProvider(WeatherDataProvider):
    """
    用于 PCSE 的 NASA POWER 数据库天气数据提供者

    :param latitude: 请求天气数据的纬度
    :param longitude: 请求天气数据的经度
    :keyword force_update: 设为True时强制从POWER网站请求最新数据
    :keyword ETmodel: "PM" 或 "P"，用于选择Penman-Monteith或Penman方法计算参考作物蒸散。默认为 "PM"。

    NASA POWER 数据库是一个专为农业气象应用设计的全球日尺度天气数据库。其空间分辨率为0.25x0.25度（截至2018年）。
    数据库数据基于气象观测站信息联合卫星资料（如辐射）生成。

    天气数据一般有约5天的实时更新延迟（具体取决于变量），因而并不适用于实时监测，但对于其他研究依然非常有用。
    与过去WOFOST使用的月度气象数据相比，这是一项重大的进步。

    关于 NASA POWER 数据库的详细信息，请参见其文档:
    https://power.larc.nasa.gov/docs/

    `NASAPowerWeatherDataProvider` 通过 NASA POWER API 获取天气数据，并进行必要的转换以适应 PCSE。
    数据获取后将其存储为二进制缓存文件。当再次请求同一位置的数据时，
    将优先加载缓存文件，而不是再次完整请求 NASA Power 服务器。

    缓存文件只要小于90天便会被使用。超过90天，则会请求NASA POWER服务器以获得最新数据；
    如果请求失败，则回退使用已有缓存。
    通过设置 `force_update=True` 可强制更新缓存文件。

    特别注意，同一 0.25x0.25 度网格内任意纬经度请求将返回同样的数据，
    例如 5.3/52.1 和 5.35/52.2 的天气数据没有区别。
    但由于白天长度的细微差别，PCSE 模拟可能仍略有不同。
    """
    # POWER 数据中的变量名称
    power_variables_old = ["ALLSKY_TOA_SW_DWN", "ALLSKY_SFC_SW_DWN", "T2M", "T2M_MIN",
                       "T2M_MAX", "T2MDEW", "WS2M", "PRECTOT"]
    power_variables = ["TOA_SW_DWN", "ALLSKY_SFC_SW_DWN", "T2M", "T2M_MIN",
                       "T2M_MAX", "T2MDEW", "WS2M", "PRECTOTCORR"]
    # 其他常量
    HTTP_OK = 200
    angstA = 0.29
    angstB = 0.49

    def __init__(self, latitude, longitude, force_update=False, ETmodel="PM"):
        """
        用于初始化 NASAPowerWeatherDataProvider。

        :param latitude: 请求天气数据的纬度
        :param longitude: 请求天气数据的经度
        :param force_update: 是否强制从 NASA POWER 网站请求最新数据，默认为 False
        :param ETmodel: "PM" 或 "P"，用于选择 Penman-Monteith 或 Penman 方法计算参考作物蒸散，默认为 "PM"
        """
        WeatherDataProvider.__init__(self)

        if latitude < -90 or latitude > 90:
            msg = "Latitude should be between -90 and 90 degrees."
            raise ValueError(msg)
        if longitude < -180 or longitude > 180:
            msg = "Longitude should be between -180 and 180 degrees."
            raise ValueError(msg)

        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.ETmodel = ETmodel
        msg = "Retrieving weather data from NASA Power for lat/lon: (%f, %f)."
        self.logger.info(msg % (self.latitude, self.longitude))

        # 检查缓存文件是否存在
        cache_file = self._find_cache_file(self.latitude, self.longitude)
        if cache_file is None or force_update is True:
            msg = "No cache file or forced update, getting data from NASA Power."
            self.logger.debug(msg)
            # 没有缓存文件，必须从 NASA 服务器获取数据
            self._get_and_process_NASAPower(self.latitude, self.longitude)
            return

        # 获取缓存文件的创建时间，如果小于 90 天则尝试加载；如果加载失败则重新获取数据
        r = os.stat(cache_file)
        cache_file_date = dt.date.fromtimestamp(r.st_mtime)
        age = (dt.date.today() - cache_file_date).days
        if age < 90:
            msg = "Start loading weather data from cache file: %s" % cache_file
            self.logger.debug(msg)

            status = self._load_cache_file()
            if status is not True:
                msg = "Loading cache file failed, reloading data from NASA Power."
                self.logger.debug(msg)
                # 加载缓存文件失败，重新获取 NASA 数据
                self._get_and_process_NASAPower(self.latitude, self.longitude)
        else:
            # 缓存文件过旧，尝试从 NASA 获取最新数据
            try:
                msg = "Cache file older then 90 days, reloading data from NASA Power."
                self.logger.debug(msg)
                self._get_and_process_NASAPower(self.latitude, self.longitude)
            except Exception as e:
                msg = ("Reloading data from NASA failed, reverting to (outdated) " +
                       "cache file")
                self.logger.debug(msg)
                status = self._load_cache_file()
                if status is not True:
                    msg = "Outdated cache file failed loading."
                    raise PCSEError(msg)

    def _get_and_process_NASAPower(self, latitude, longitude):
        """处理从NASA Power获取以及处理数据的过程
        """
        powerdata = self._query_NASAPower_server(latitude, longitude)
        if not powerdata:
            msg = "Failure retrieving POWER data from server. This can be a connection problem with " \
                  "the NASA POWER server, retry again later."
            raise RuntimeError(msg)

        # 存储信息性header，并解析变量
        self.description = [powerdata["header"]["title"]]
        self.elevation = float(powerdata["geometry"]["coordinates"][2])
        df_power = self._process_POWER_records(powerdata)

        # 获取Angstrom A/B参数
        self.angstA, self.angstB = self._estimate_AngstAB(df_power)

        # 将power数据记录转换为PCSE兼容的数据结构
        df_pcse = self._POWER_to_PCSE(df_power)

        # 开始构建气象数据容器
        self._make_WeatherDataContainers(df_pcse.to_dict(orient="records"))

        # 将内容写入缓存文件
        cache_filename = self._get_cache_filename(latitude, longitude)
        self._dump(cache_filename)

    def _estimate_AngstAB(self, df_power):
        """根据大气顶层（ALLSKY_TOA_SW_DWN）与冠层顶层（ALLSKY_SFC_SW_DWN）的辐射值计算Angstrom A/B参数。

        :param df_power: 包含POWER数据的数据框
        :return: Angstrom A/B参数元组

        Angstrom A/B参数通过swv_dwn（地表短波下行辐射）除以toa_dwn（大气顶层短波下行辐射）得到相对辐射率，
        然后取其0.05分位数作为Angstrom A，0.98分位数作为Angstrom A+B：toa_dwn*(A+B)接近记录swv_dwn的上包络，
        toa_dwn*A接近下包络。
        """

        msg = "Start estimation of Angstrom A/B values from POWER data."
        self.logger.debug(msg)

        # 检查是否有足够多的数据以得到合理的估算
        # 经验法则是至少需要200天的数据
        if len(df_power) < 200:
            msg = ("Less then 200 days of data available. Reverting to " +
                   "default Angstrom A/B coefficients (%f, %f)")
            self.logger.warn(msg % (self.angstA, self.angstB))
            return self.angstA, self.angstB

        # 计算相对辐射(swv_dwn/toa_dwn)与分位数
        relative_radiation = df_power.ALLSKY_SFC_SW_DWN/df_power.TOA_SW_DWN
        ix = relative_radiation.notnull()
        angstrom_a = float(np.percentile(relative_radiation[ix].values, 5))
        angstrom_ab = float(np.percentile(relative_radiation[ix].values, 98))
        angstrom_b = angstrom_ab - angstrom_a

        try:
            check_angstromAB(angstrom_a, angstrom_b)
        except PCSEError as e:
            msg = ("Angstrom A/B values (%f, %f) outside valid range: %s. " +
                   "Reverting to default values.")
            msg = msg % (angstrom_a, angstrom_b, e)
            self.logger.warn(msg)
            return self.angstA, self.angstB

        msg = "Angstrom A/B values estimated: (%f, %f)." % (angstrom_a, angstrom_b)
        self.logger.debug(msg)

        return angstrom_a, angstrom_b

    def _query_NASAPower_server(self, latitude, longitude):
        """查询给定纬度/经度的NASA Power服务器获取数据
        """

        start_date = dt.date(1983,7,1)
        end_date = dt.date.today()

        # 构建用于检索数据的URL，使用新的NASA POWER API
        server = "https://power.larc.nasa.gov/api/temporal/daily/point"
        payload = {"request": "execute",
                   "parameters": ",".join(self.power_variables),
                   "latitude": latitude,
                   "longitude": longitude,
                   "start": start_date.strftime("%Y%m%d"),
                   "end": end_date.strftime("%Y%m%d"),
                   "community": "AG",
                   "format": "JSON",
                   "user": "anonymous"
                   }
        msg = "Starting retrieval from NASA Power"
        self.logger.debug(msg)
        req = requests.get(server, params=payload)

        if req.status_code != self.HTTP_OK:
            msg = ("Failed retrieving POWER data, server returned HTTP " +
                   "code: %i on following URL %s") % (req.status_code, req.url)
            raise PCSEError(msg)

        msg = "Successfully retrieved data from NASA Power"
        self.logger.debug(msg)
        return req.json()

    def _find_cache_file(self, latitude, longitude):
        """尝试查找给定纬度/经度的缓存文件。

        如果缓存文件不存在，则返回None，否则返回缓存文件的完整路径。
        """
        cache_filename = self._get_cache_filename(latitude, longitude)
        if os.path.exists(cache_filename):
            return cache_filename
        else:
            return None

    def _get_cache_filename(self, latitude, longitude):
        """根据纬度和经度构建用于缓存文件的文件名

        纬度和经度通过截断到0.1度编码到文件名中。例如，某点(纬度/经度52.56/-124.78)的缓存文件名为：
        NASAPowerWeatherDataProvider_LAT00525_LON-1247.cache
        """

        fname = "%s_LAT%05i_LON%05i.cache" % (self.__class__.__name__,
                                              int(latitude*10), int(longitude*10))
        cache_filename = os.path.join(settings.METEO_CACHE_DIR, fname)
        return cache_filename

    def _write_cache_file(self):
        """将NASA Power的气象数据写入缓存文件。
        """
        cache_filename = self._get_cache_filename(self.latitude, self.longitude)
        try:
            self._dump(cache_filename)
        except (IOError, EnvironmentError) as e:
            msg = "Failed to write cache to file '%s' due to: %s" % (cache_filename, e)
            self.logger.warning(msg)

    def _load_cache_file(self):
        """从缓存文件加载数据。如果成功返回True。
        """
        cache_filename = self._get_cache_filename(self.latitude, self.longitude)
        try:
            self._load(cache_filename)
            msg = "Cache file successfully loaded."
            self.logger.debug(msg)
            return True
        except (IOError, EnvironmentError, EOFError) as e:
            msg = "Failed to load cache from file '%s' due to: %s" % (cache_filename, e)
            self.logger.warning(msg)
            return False

    def _make_WeatherDataContainers(self, recs):
        """从recs创建WeatherDataContainers，计算ET并存储WDC对象。"""
        for rec in recs:
            # 参考蒸散量（mm/天）
            try:
                E0, ES0, ET0 = reference_ET(rec["DAY"], rec["LAT"], rec["ELEV"], rec["TMIN"], rec["TMAX"], rec["IRRAD"],
                                            rec["VAP"], rec["WIND"], self.angstA, self.angstB, self.ETmodel)
            except ValueError as e:
                msg = (("Failed to calculate reference ET values on %s. " % rec["DAY"]) +
                       ("With input values:\n %s.\n" % str(rec)) +
                       ("Due to error: %s" % e))
                raise PCSEError(msg)

            # 用ET值更新记录，值单位转换为cm/天
            rec.update({"E0": E0/10., "ES0": ES0/10., "ET0": ET0/10.})

            # 通过字典't'创建天气数据容器
            wdc = WeatherDataContainer(**rec)

            # 将wdc添加进以thisdate为键的字典
            self._store_WeatherDataContainer(wdc, wdc.DAY)

    def _process_POWER_records(self, powerdata):
        """处理NASA POWER返回的气象记录"""
        msg = "Start parsing of POWER records from URL retrieval."
        self.logger.debug(msg)

        fill_value = float(powerdata["header"]["fill_value"])

        df_power = {}
        for varname in self.power_variables:
            s = pd.Series(powerdata["properties"]["parameter"][varname])
            s[s == fill_value] = np.nan
            df_power[varname] = s
        df_power = pd.DataFrame(df_power)
        df_power["DAY"] = pd.to_datetime(df_power.index, format="%Y%m%d")

        # 找出至少有一个缺失值（NaN）的所有行
        ix = df_power.isnull().any(axis=1)
        # 获取所有没有缺失值的行
        df_power = df_power[~ix]

        return df_power

    def _POWER_to_PCSE(self, df_power):

        # 将POWER数据转换为PCSE兼容输入的dataframe
        df_pcse = pd.DataFrame({"TMAX": df_power.T2M_MAX,
                                "TMIN": df_power.T2M_MIN,
                                "TEMP": df_power.T2M,
                                "IRRAD": df_power.ALLSKY_SFC_SW_DWN.apply(MJ_to_J),
                                "RAIN": df_power.PRECTOTCORR.apply(mm_to_cm),
                                "WIND": df_power.WS2M,
                                "VAP": df_power.T2MDEW.apply(tdew_to_hpa),
                                "DAY": df_power.DAY.apply(to_date),
                                "LAT": self.latitude,
                                "LON": self.longitude,
                                "ELEV": self.elevation})

        return df_pcse
