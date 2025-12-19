# -*- coding: utf-8 -*-
# 人工智能组，瓦赫宁根大学
# Hilmy Baja (hilmy.baja@wur.nl)，2025年2月
# 大量代码借鉴自 Allard de Wit 的 nasapower.py

import os
import datetime
import time

from typing import Union

import requests

import pandas as pd
import numpy as np

from pcse.base import WeatherDataProvider, WeatherDataContainer
from pcse.util import reference_ET, wind10to2, check_angstromAB
from pcse.exceptions import PCSEError
from pcse.settings import settings


class OpenMeteoWeatherDataProvider(WeatherDataProvider):
    """一个使用 Open Meteo 天气 API 的天气数据提供者。

    :param latitude: 需要请求天气数据的纬度
    :param longitude: 需要请求天气数据的经度
    :param timezone: 用于日聚合的时区（字符串，默认为 'UTC'）
    :param openmeteo_model: 使用的气象模型，默认为 'best_match'
    :param start_date: 开始获取数据的起始日期（字符串，默认为 'UTC'）
    :keyword ETmodel: "PM"|"P"，选择 Penman-Monteith 或 Penman 方法计算参考蒸散发。默认为 "PM"。
    :keyword forecast: 是否包含天气预报，默认为 False
    :keyword force_update: 设为 True 时强制从 OpenMeteo 网站请求最新数据。

    此对象在初始化时仅需提供位置（经度和纬度）。

    构造对象时有两个重要参数：
    `openmeteo_model` 和 `forecast`。
    类变量列举了可用的模型类型，无论是用于预测还是历史数据。

    如需指定模型，可使用对应的关键字参数调用。
    注意，使用某些模型时可能有一些细微区别。
    该功能未经严格测试，因此起始日期可能有问题。
    如遇此类问题，请为 `start_date` 参数提供一个值。
    各模型的更多信息可参见：https://open-meteo.com/en/docs

    如果未指定模型，Open Meteo API 将自动为您的位置选择最佳模型。
    """

    # 一些类变量
    HTTP_OK = 200
    angstA = 0.29
    angstB = 0.49

    # OpenMeteo 的预报和历史天气模型列表
    # 注释显示了覆盖范围和空间分辨率
    dict_forecast_models = {
        "best_match": datetime.date(2023, 1, 1),  # 全球, 0.25度
        "arpae_cosmo_5m": datetime.date(2024, 2, 2),  # 欧洲, 5分钟
        "bom_access_global": datetime.date(2024, 1, 19),  # 全球, 0.15度
        "gem_seamless": datetime.date(2022, 11, 24),  # 全球, 0.15度
        "jma_gsm": datetime.date(2016, 1, 1),  # 全球, 0.5度
        "icon_seamless": datetime.date(2022, 11, 25),  # 全球, 11公里
        "ecmwf_ifs025": datetime.date(2024, 2, 4),  # 全球, 0.25度
        "knmi_seamless": datetime.date(2024, 7, 2),  # 欧洲, 2.5公里
        "meteofrance_seamless": datetime.date(2024, 1, 3),  # 全球, 0.25度
        "gfs_seamless": datetime.date(2021, 3, 24),  # 全球, 0.11度
        "ukmo_seamless": datetime.date(2022, 3, 2),  # 全球, 0.09度/10公里
    }

    dict_historical_models = {
        "best_match": datetime.date(1951, 1, 1), # 全球, 0.25度
        "era5": datetime.date(1941, 1, 1),  # 全球, 0.25度
        "era5_land": datetime.date(1951, 1, 1),  # 全球, 0.1度
        "ecmwf_ifs": datetime.date(2017, 1, 1),  # 全球, 9公里
        "cerra": datetime.date(1986, 1, 1),  # 全球, 5公里
    }

    # 历史模型延迟（日）
    delay_historical_models = {
        "best_match": 10,
        "era5": 6,  # 全球, 0.25度
        "era5_land": 6,  # 全球, 0.1度
        "ecmwf_ifs": 3,  # 全球, 9公里
        "cerra": 1,
    }

    def __init__(
        self,
        latitude: float,
        longitude: float,
        timezone: str = "UTC",
        openmeteo_model: str = "best_match",
        start_date: Union[str, datetime.date] = None,
        ETmodel: str = "PM",
        forecast: bool = False,
        force_update: bool = False,
    ):
        # 构造函数，初始化对象属性
        WeatherDataProvider.__init__(self)

        self.model = openmeteo_model
        self.ETmodel = ETmodel
        self.start_date = start_date
        self.is_forecast = forecast

        # 如果使用特定模型，则更新起始日期
        self._check_start_date()

        if latitude < -90 or latitude > 90:
            msg = "Latitude should be between -90 and 90 degrees."
            raise ValueError(msg)
        if longitude < -180 or longitude > 180:
            msg = "Longitude should be between -180 and 180 degrees."
            raise ValueError(msg)

        self.latitude = float(latitude)
        self.longitude = float(longitude)
        self.timezone = timezone

        self.description = self._get_description

        # 检查缓存
        self._check_cache(force_update)

    def _check_cache(self, force_update: bool = False):
        # 检查是否存在缓存文件
        cache_file = self._find_cache_file(self.latitude, self.longitude)
        if cache_file is None or force_update is True:
            msg = "No cache file or forced update, getting data from OpenMeteo Power."
            self.logger.debug(msg)
            # 没有缓存文件时，从 open-meteo 服务器获取数据
            self._fetch_data(self.start_date)
            return

        # 获取缓存文件的时间，如果小于90天则尝试加载；如果加载失败，则从 OpenMeteo 服务器获取数据
        r = os.stat(cache_file)
        cache_file_date = datetime.date.fromtimestamp(r.st_mtime)
        age = (datetime.date.today() - cache_file_date).days
        if age < 90:
            msg = "Start loading weather data from cache file: %s" % cache_file
            self.logger.debug(msg)

            status = self._load_cache_file()
            if status is not True:
                msg = "Loading cache file failed, reloading data from OpenMeteo."
                self.logger.debug(msg)
                # 加载缓存文件失败时，从 open-meteo 服务器获取数据
                self._fetch_data(self.start_date)
        else:
            # 缓存文件过旧，尝试从 OpenMeteo 获取新数据
            try:
                msg = "Cache file older then 90 days, reloading data from OpenMeteo."
                self.logger.debug(msg)
                self._fetch_data(self.start_date)
            except Exception as e:
                msg = ("Reloading data from OpenMeteo failed, reverting to (outdated) " +
                       "cache file")
                self.logger.debug(msg)
                status = self._load_cache_file()
                if status is not True:
                    msg = "Outdated cache file failed loading."
                    raise PCSEError(msg)

    def _fetch_data(self, start_date):
        """
        内部方法，用于根据指定日期范围获取并处理天气数据。
        返回一个缓存文件。
        """

        url = self._get_url(previous_runs=True)
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": self.format_date(start_date),
            "end_date": self.format_date(self._get_end_date()),
            "daily": self.daily_variables,
            "hourly": self.hourly_variables,
            "timezone": self.timezone,
            "model": self.model,
        }

        response_json = self._get_response(url, params)

        self.elevation = response_json.get('elevation', 0)

        # raw_data = self._extract_weather_data(weather_api_object, params)

        df = self._prepare_weather_dataframe(response_json)

        self._make_WeatherDataContainers(df.to_dict(orient='records'))

        cache_filename = self._get_cache_filename(self.latitude, self.longitude)
        self._dump(cache_filename)

    # 带错误检查的请求例程
    def _get_response(self, url, params):
        try:
            response = requests.get(url, params=params, timeout=30)
            self._check_response_status(response)

            response_json = response.json()
            return response_json
        except requests.RequestException as e:
            print(f"Error fetching weather data: {e}")
            return None

    def _check_response_status(self, response):
        if response.status_code != self.HTTP_OK:
            msg = ("Failed retrieving OpenMeteo data, server returned HTTP " +
                   "code: %i on following URL %s") % (response.status_code, response.url)
            raise PCSEError(msg)

    def _find_cache_file(self, latitude, longitude):
        """
        尝试查找给定纬度/经度的缓存文件。

        如果缓存文件不存在则返回None，否则返回缓存文件的完整路径。
        """
        cache_filename = self._get_cache_filename(latitude, longitude)
        if os.path.exists(cache_filename):
            return cache_filename
        else:
            return None

    def _get_cache_filename(self, latitude, longitude):
        """
        构建用于缓存文件的文件名，基于给定的纬度和经度。

        纬度和经度通过保留到0.1度位进行编码。例如，纬度/经度为52.56/-124.78且使用
        “knmi_seamless”模型的点的缓存文件名为:
        OpenMeteoWeatherDataProvider_LAT00525_LON-1247_knmi_.cache
        """

        fname = "%s_LAT%05i_LON%05i_%s.cache" % (self.__class__.__name__,
                                                 int(latitude * 10), int(longitude * 10),
                                                 self.model[:5])
        cache_filename = os.path.join(settings.METEO_CACHE_DIR, fname)
        return cache_filename

    def _load_cache_file(self):
        """
        从缓存文件中加载数据。成功时返回True。
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
        """从recs创建WeatherDataContainers，计算ET并存储WDC。"""

        for rec in recs:
            # 从字典't'构建 weather data container
            wdc = WeatherDataContainer(**rec)

            # 将wdc添加到此日期的字典中
            self._store_WeatherDataContainer(wdc, wdc.DAY)

    def _prepare_weather_dataframe(self, weather_data):
        """
        将原始Open-Meteo气象数据转换为单一的日尺度DataFrame
        当前针对PCSE所需输入进行了定制

        返回:
            DataFrame: 以日期为索引的每日气象数据。
        """
        # 处理每日数据
        daily = weather_data.get('daily', {})
        df_daily = pd.DataFrame(daily)
        # 将'time'列转换为datetime对象并设置为索引
        df_daily['date'] = pd.to_datetime(df_daily['time'])
        df_daily.set_index('date', inplace=True)

        # 重命名每日数据列以提高可读性
        df_daily.rename(columns={
            'temperature_2m_min': 'TMIN',
            'temperature_2m_max': 'TMAX',
            'precipitation_sum': 'RAIN',    # 单位为mm/天
            'shortwave_radiation_sum': 'IRRAD'  # 单位为MJ/m²/天
        }, inplace=True)

        # 处理逐小时数据
        hourly = weather_data.get('hourly', {})
        df_hourly = pd.DataFrame(hourly)
        # 将逐小时的time转换为datetime对象
        df_hourly['date'] = pd.to_datetime(df_hourly['time'])
        # 设置time为DataFrame的索引
        df_hourly.set_index('date', inplace=True)

        # 计算逐小时数据的日均值
        df_hourly.drop(columns=['time'], inplace=True)
        df_hourly_daily = df_hourly.groupby(df_hourly.index.date).mean()
        # 将索引转换回datetime
        df_hourly_daily.index = pd.to_datetime(df_hourly_daily.index)
        df_hourly_daily.rename(columns={
            'temperature_2m': 'TEMP',
            "wind_speed_10m": 'WIND',
            'dewpoint_2m': 'dewpoint'
        }, inplace=True)

        # 以date索引进行合并（内连接，仅保留两者都存在的日期）
        df_openmeteo = pd.merge(df_daily, df_hourly_daily, left_index=True, right_index=True, how='inner')

        # 将太阳辐射从MJ/m²/天转换为W/m²/天
        df_openmeteo['IRRAD'] = df_openmeteo['IRRAD'] * 1e6

        # 将降水量从mm/天转换为cm/天
        df_openmeteo['RAIN'] = df_openmeteo['RAIN'] * 0.1

        # 将风速从10m高度换算为2m高度
        df_openmeteo['WIND'] = wind10to2(df_openmeteo['WIND'])

        # 根据露点温度(°C)计算水汽压(hPa), 采用公式：
        # e = 6.108 * exp((17.27 * T_d) / (T_d + 237.3))
        df_openmeteo['VAP'] = (6.108 * np.exp((17.27 * df_openmeteo['dewpoint']) / (df_openmeteo['dewpoint'] + 237.3)))

        df_openmeteo.drop(columns=['dewpoint'], inplace=True)

        df_openmeteo['DAY'] = df_openmeteo.index.date

        df_openmeteo['LAT'] = self.latitude
        df_openmeteo['LON'] = self.longitude
        df_openmeteo['ELEV'] = self.elevation

        self.angstA, self.angstB = self._estimate_AngstAB(df_openmeteo)

        df_openmeteo = df_openmeteo[['TMIN', 'TMAX', 'TEMP', 'IRRAD', 'RAIN', 'WIND', 'VAP', 'DAY', 'LAT', 'LON', 'ELEV']]

        E0_list = []
        ES0_list = []
        ET0_list = []

        for row in df_openmeteo.itertuples():
            E0, ES0, ET0 = reference_ET(row.DAY, row.LAT, row.ELEV, row.TMIN,
                                        row.TMAX, row.IRRAD,
                                        row.VAP, row.WIND,
                                        self.angstA, self.angstB, self.ETmodel)

            # 转换为cm/天
            E0_list.append(E0 / 10.)
            ES0_list.append(ES0 / 10.)
            ET0_list.append(ET0 / 10.)

        # 关于复制切片的警告
        df_openmeteo = df_openmeteo.copy()

        df_openmeteo.loc[:, "E0"] = E0_list
        df_openmeteo.loc[:, "ES0"] = ES0_list
        df_openmeteo.loc[:, "ET0"] = ET0_list

        df_openmeteo = df_openmeteo[
            [
                'TMIN',
                'TMAX',
                'TEMP',
                'IRRAD',
                'RAIN',
                'WIND',
                'VAP',
                'DAY',
                'LAT',
                'LON',
                'ELEV',
                'E0',
                'ES0',
                'ET0'
            ]
        ]

        return df_openmeteo

    def calculate_toa_radiation(self, day_of_year):
        """
        计算每日大气顶短波辐射
        此大气顶辐射估算方法取自FAO-56文献。
        """
        G_sc = 1361  # 太阳常数 (W/m²)

        # 地日距离修正因子
        d_r = 1 + 0.033 * np.cos(2 * np.pi * day_of_year / 365)

        # 太阳赤纬角（弧度）
        delta = np.radians(23.45 * np.sin(2 * np.pi * (day_of_year - 81) / 365))

        # 纬度转换为弧度
        phi = np.radians(self.latitude)

        # 日落时角
        h_s = np.arccos(-np.tan(phi) * np.tan(delta))

        # 修正后每日大气顶辐射（H0）
        H0 = (24 * 3600 / np.pi) * G_sc * d_r * (
                np.cos(phi) * np.cos(delta) * np.sin(h_s) + (h_s * np.sin(phi) * np.sin(delta))
        )

        # 单位从J/m²/天转换为MJ/m²/天
        H0 = H0 / 1e6

        return H0

    def _estimate_AngstAB(self, df):
        """
        从大气顶估算和冠层顶（ALLSKY_SFC_SW_DWN）辐射数据确定Angstrom A/B参数。

        :param df: 包含Openmeteo数据的数据框
        :return: Angstrom A/B值的元组

        Angstrom A/B参数通过swv_dwn与toa_dwn的比值，
        取0.05分位数为Angstrom A，取0.98分位数为Angstrom A+B：
        toa_dwn*(A+B)趋近于swv_dwn记录的上包络线，toa_dwn*A趋近于下包络线。

        引自PCSE的NASA POWER实现。
        """

        msg = "Start estimation of Angstrom A/B values from Open Meteo data."
        self.logger.debug(msg)

        # 检查数据是否足够以获得合理的估算：
        # 至少需要200天的数据
        if len(df) < 200:
            msg = ("Less then 200 days of data available. Reverting to " +
                   "default Angstrom A/B coefficients (%f, %f)")
            self.logger.warn(msg % (self.angstA, self.angstB))
            return self.angstA, self.angstB

        # 计算相对辐射（swv_dwn/toa_dwn）及分位数
        doys = pd.to_datetime(df.DAY).dt.dayofyear
        relative_radiation = (df.IRRAD/1e6)/self.calculate_toa_radiation(doys)
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


    def _get_url(self, previous_runs: bool = False) -> str:
        # 获取接口URL，根据模型类型（预报/历史）和previous_runs参数选择
        if self.model in self.dict_forecast_models and self.is_forecast is True and previous_runs is True:
            return "https://previous-runs-api.open-meteo.com/v1/forecast"
        elif self.model in self.dict_forecast_models and self.is_forecast is True and previous_runs is False:
            return "https://api.open-meteo.com/v1/forecast"
        elif self.model in self.dict_historical_models and self.is_forecast is False:
            return "https://archive-api.open-meteo.com/v1/archive"
        else:
            raise ValueError("Model not found. Check model availability.")

    def _get_end_date(self):
        # 获取结束日期，预报模型返回今天+7天，历史模型返回数据发布延迟后的日期
        if self.model in self.dict_forecast_models and self.is_forecast is True:
            return datetime.date.today() + datetime.timedelta(days=7)
        elif self.model in self.dict_historical_models and self.is_forecast is False:
            return datetime.date.today() - datetime.timedelta(days=self.delay_historical_models[self.model])
        else:
            raise ValueError("Model not found. Check model availability.")

    def _check_start_date(self):
        # 检查并设置起始日期，如未指定则根据当前模型类型设定默认值
        if self.start_date is None and self.model in self.dict_forecast_models and self.is_forecast is True:
            self.start_date = self.dict_forecast_models[self.model]
        elif self.start_date is None and self.model in self.dict_historical_models and self.is_forecast is False:
            self.start_date = self.dict_historical_models[self.model]

    @property
    def _get_description(self) -> str:
        # 返回所选模型的信息字符串
        return (f"Using a {'historical' if self.is_forecast is not True else 'forecast'} model."
                f"Specifically, {self.model}. Please check the documentation for the model resolution.")

    @staticmethod
    def format_date(date: Union[str, datetime.date]):
        """
        将日期或datetime对象转换为'YYYY-MM-DD'格式的字符串。
        如果参数已经是字符串，则直接返回原值。
        """
        if isinstance(date, (datetime.date, datetime)):
            return date.strftime("%Y-%m-%d")
        return date

    @property
    def daily_variables(self):
        # 返回每日变量列表
        return [
        "temperature_2m_max",
        "temperature_2m_min",
        "precipitation_sum",
        "shortwave_radiation_sum",
    ]

    @property
    def hourly_variables(self):
        # 返回每小时变量列表
        return [
            "wind_speed_10m",
            "temperature_2m",
            "dewpoint_2m"
        ]


if __name__ == '__main__':
    # Wageningen地点天气获取示例
    omwp = OpenMeteoWeatherDataProvider(51.98, 5.65)

    # 获取某一天的天气。
    single_date = datetime.date(2024, 5, 15)
    weather_single = omwp(single_date)
    print(f"Weather on {single_date}:", weather_single)
