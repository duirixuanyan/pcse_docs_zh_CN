# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl)
# 以及 Zacharias Steinmetz (stei4785@uni-landau.de), 2015年8月
"""一个从CSV文件读取天气数据的数据提供者。
"""
import os
import datetime as dt
import csv
import math

from ast import literal_eval

from ..base import WeatherDataContainer, WeatherDataProvider
from ..util import reference_ET, angstrom, check_angstromAB
from ..exceptions import PCSEError
from ..settings import settings


class ParseError(PCSEError):
    pass


class OutOfRange(PCSEError):
    pass


class IRRADFromSunshineDuration:

    def __init__(self, latitude, angstA, angstB):

        assert -90 < latitude < 90, \
            "Invalid latitude value (%s) encountered" % latitude
        check_angstromAB(angstA, angstB)
        self.latitude = latitude
        self.angstA = angstA
        self.angstB = angstB

    def __call__(self, value, day):
        """根据Angstrom方程，通过日照时长计算日辐射量（单位：J/m2/日）

        :param value: 日照时长（小时）
        :param day: 日期
        :return: 日辐射量（J/m2/日）
        """
        assert 0 <= value <= 24, \
            "Invalid sunshine duration value (%s) encountered at day %s" % (value, day)
        irrad = angstrom(day, self.latitude, value, self.angstA, self.angstB)

        return irrad


def csvdate_to_date(x, dateformat):
    """将字符串x根据给定格式转换为datetime.date。

    :param x: 表示日期的字符串
    :param dateformat: strptime() 接受的日期格式
    :return: 一个日期对象
    """
    return dt.datetime.strptime(x, dateformat).date()


# 单位转换函数
def NoConversion(x, d):
    # 不做转换，直接转为浮点数
    return float(x)


def kJ_to_J(x, d):
    # 千焦转焦耳
    return float(x)*1000.


def mm_to_cm(x, d):
    # 毫米转厘米
    return float(x)/10.


def kPa_to_hPa(x, d):
    # 千帕转百帕
    return float(x)*10.


class CSVWeatherDataProvider(WeatherDataProvider):
    """从CSV文件读取天气数据。

    :param csv_fname: 读取的CSV文件名
    :param delimiter: CSV文件分隔符
    :param dateformat: 日期格式，默认为'%Y%m%d'
    :keyword ETmodel: "PM"|"P"，用于选择Penman-Monteith或Penman方法计算参考作物蒸散。默认'PM'。
    :param force_reload: 是否忽略缓存强制从CSV文件重新加载

    CSV文件应具有以下结构（示例），缺失值应以'NaN'填写::

        ## Site Characteristics
        Country     = 'Netherlands'
        Station     = 'Wageningen, Haarweg'
        Description = 'Observed data from Station Haarweg in Wageningen'
        Source      = 'Meteorology and Air Quality Group, Wageningen University'
        Contact     = 'Peter Uithol'
        Longitude = 5.67; Latitude = 51.97; Elevation = 7; AngstromA = 0.18; AngstromB = 0.55; HasSunshine = False
        ## Daily weather observations (missing values are NaN)
        DAY,IRRAD,TMIN,TMAX,VAP,WIND,RAIN,SNOWDEPTH
        20040101,NaN,-0.7,1.1,0.55,3.6,0.5,NaN
        20040102,3888,-7.5,0.9,0.44,3.1,0,NaN
        20040103,2074,-6.8,-0.5,0.45,1.8,0,NaN
        20040104,1814,-3.6,5.9,0.66,3.2,2.5,NaN
        20040105,1469,3,5.7,0.78,2.3,1.3,NaN
        [...]

        各变量单位如下
        IRRAD: kJ/m2/天或小时
        TMIN 和 TMAX: 摄氏度 (°C)
        VAP: 千帕 (kPa)
        WIND: 米/秒 (m/sec)
        RAIN: 毫米 (mm)
        SNOWDEPTH: 厘米 (cm)

    早期用于读取天气数据文件的类为CABOWeatherDataProvider，它从CABO天气格式的文本中读取数据。
    但CABO天气文件的构建非常繁琐，每年都需要新建一个文件，而且容易出错，格式失误极易导致错误。

    为简化向PCSE模型提供天气数据，新增加了CSVWeatherDataProvider，其继承自ExcelWeatherDataProvider，
    可从简单的CSV文件读取数据。

    CSVWeatherDataProvider假定记录是完整的，不会插值缺失数据（这可以在文本编辑器中轻松完成）。
    只有SNOWDEPTH（积雪深度）允许缺失，因为该参数通常只在冬季提供。
    """

    obs_conversions = {
        "TMAX": NoConversion,
        "TMIN": NoConversion,
        "IRRAD": kJ_to_J,
        "VAP": kPa_to_hPa,
        "WIND": NoConversion,
        "RAIN": mm_to_cm,
        "SNOWDEPTH": NoConversion
    }

    def __init__(self, csv_fname, delimiter=',', dateformat='%Y%m%d',
                 ETmodel='PM', force_reload=False):
        """
        初始化CSVWeatherDataProvider。
        :param csv_fname: CSV文件名
        :param delimiter: CSV分隔符，默认为','
        :param dateformat: 日期格式，默认为'%Y%m%d'
        :param ETmodel: 蒸散发模型，'PM'或'P'
        :param force_reload: 是否强制重新加载数据，忽略缓存
        """
        WeatherDataProvider.__init__(self)

        self.fp_csv_fname = os.path.abspath(csv_fname)
        self.dateformat = dateformat
        self.ETmodel = ETmodel
        if not os.path.exists(self.fp_csv_fname):
            msg = "Cannot find weather file at: %s" % self.fp_csv_fname
            raise PCSEError(msg)

        # 如果强制重新加载或缓存不存在，则重新读取CSV文件
        if force_reload or not self._load_cache_file(self.fp_csv_fname):
            # 用utf-8打开
            # with open(csv_fname, 'r') as csv_file:
            with open(csv_fname, 'r', encoding='utf-8') as csv_file:
                csv_file.readline()  # 跳过第一行
                self._read_meta(csv_file)
                self._read_observations(csv_file, delimiter)
            self._write_cache_file(self.fp_csv_fname)

    def _read_meta(self, csv_file):
        """
        读取CSV文件中的元数据部分。
        """
        header = {}
        for line in csv_file:
            if line.startswith('## Daily weather observations'):
                break
            statements = line.split(';')
            for stmt in statements:
                key, val = stmt.split('=')
                header[key.strip()] = literal_eval(val.strip())

        self.nodata_value = -99
        self.description = [u"Weather data for:",
                            u"Country: %s" % header['Country'],
                            u"Station: %s" % header['Station'],
                            u"Description: %s" % header['Description'],
                            u"Source: %s" % header['Source'],
                            u"Contact: %s" % header['Contact']]

        self.longitude = float(header['Longitude'])
        self.latitude = float(header['Latitude'])
        self.elevation = float(header['Elevation'])
        angstA = float(header['AngstromA'])
        angstB = float(header['AngstromB'])
        self.angstA, self.angstB = check_angstromAB(angstA, angstB)
        self.has_sunshine = bool(header['HasSunshine'])

        # 如果文件包含日照时数，则使用angstrom模块替代IRRAD的转换器
        if self.has_sunshine:
            self.obs_conversions["IRRAD"] = IRRADFromSunshineDuration(self.latitude, self.angstA, self.angstB)

    def _read_observations(self, csv_file, delimiter):
        """处理气象数据的行并转换为正确的单位。
        """
        obs = csv.DictReader(csv_file, delimiter=delimiter, quotechar='"')
        for i, d in enumerate(obs):
            try:
                day = None
                day = csvdate_to_date(d.pop("DAY"), self.dateformat)
                row = {"DAY":  day}
                for label in self.obs_conversions.keys():
                    func = self.obs_conversions[label]
                    value = float(d[label])
                    r = func(value, day)
                    if math.isnan(r):
                        if label == "SNOWDEPTH":
                            continue
                        raise ParseError
                    row[label] = r

                # 参考ET，以mm/天为单位
                e0, es0, et0 = reference_ET(LAT=self.latitude, ELEV=self.elevation,
                                            ANGSTA=self.angstA, ANGSTB=self.angstB,
                                            ETMODEL=self.ETmodel, **row)
                # 转换为cm/天
                row["E0"] = e0/10.
                row["ES0"] = es0/10.
                row["ET0"] = et0/10.

                wdc = WeatherDataContainer(LAT=self.latitude, LON=self.longitude, ELEV=self.elevation, **row)
                self._store_WeatherDataContainer(wdc, day)
            except (ParseError, KeyError):
                msg = "Failed reading element '%s' for day '%s' at line %i. Skipping ..." % (label, day, i)
                self.logger.warn(msg)
            except ValueError as e:  # 单元格中的值异常
                msg = "Failed computing a value for day '%s' at row %i" % (day, i)
                self.logger.warn(msg)

    def _load_cache_file(self, csv_fname):
        # 尝试加载缓存文件，如果不存在则返回False
        cache_filename = self._find_cache_file(csv_fname)
        if cache_filename is None:
            return False
        else:
            self._load(cache_filename)
            return True

    def _find_cache_file(self, csv_fname):
        """尝试为文件名找到缓存文件

        如果缓存文件不存在，则返回None；否则返回缓存文件的完整路径。
        """
        cache_filename = self._get_cache_filename(csv_fname)
        if os.path.exists(cache_filename):
            cache_date = os.stat(cache_filename).st_mtime
            csv_date = os.stat(csv_fname).st_mtime
            if cache_date > csv_date:  # 缓存文件比CSV文件更新
                return cache_filename

        return None

    def _get_cache_filename(self, csv_fname):
        """根据csv_fname构建缓存文件名
        """
        basename = os.path.basename(csv_fname)
        filename, ext = os.path.splitext(basename)

        tmp = "%s_%s.cache" % (self.__class__.__name__, filename)
        cache_filename = os.path.join(settings.METEO_CACHE_DIR, tmp)
        return cache_filename

    def _write_cache_file(self, csv_fname):
        # 写入缓存文件
        cache_filename = self._get_cache_filename(csv_fname)
        try:
            self._dump(cache_filename)
        except (IOError, EnvironmentError) as e:
            msg = "Failed to write cache to file '%s' due to: %s" % (cache_filename, e)
            self.logger.warning(msg)
