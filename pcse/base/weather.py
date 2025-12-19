# -*- coding: utf-8 -*-
# Copyright (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2024
"""用于创建PCSE模拟单元的基类。

通常这些类不应直接使用，而是在创建PCSE模拟单元时进行子类化使用。
"""
import logging
import pickle
import datetime as dt

from .. import exceptions as exc
from ..settings import settings


class SlotPickleMixin(object):
    """该mixin使得定义了__slots__的对象可以被pickle/反pickle。

    在许多程序中，一个或几个类的实例数量非常大。为这些类添加__slots__可以显著减少内存占用，并通过消除实例字典提高执行速度。
    不幸的是，由此生成的对象无法被pickle。该mixin让这些类重新可以被pickle，并且还能兼容在添加__slots__之前创建的pickle文件。

    摘录自：
    http://code.activestate.com/recipes/578433-mixin-for-pickling-objects-with-__slots__/
    """

    def __getstate__(self):
        return dict(
            (slot, getattr(self, slot))
            for slot in self.__slots__
            if hasattr(self, slot)
        )

    def __setstate__(self, state):
        for slot, value in state.items():
            setattr(self, slot, value)


class WeatherDataContainer(SlotPickleMixin):
    """用于存储气象数据要素的类。

    气象数据要素通过关键字参数提供，这些关键字也是在 WeatherDataContainer
    中可以访问变量的属性名。因此，关键字 TMAX=15 会设置名为 TMAX，值为 15 的属性。

    以下关键字是必需的：

    :keyword LAT: 位置的纬度（十进制度）
    :keyword LON: 位置的经度（十进制度）
    :keyword ELEV: 位置的海拔（米）
    :keyword DAY: 观测日期（python datetime.date）
    :keyword IRRAD: 入射全球辐射（J/m2/day）
    :keyword TMIN: 日最低气温（摄氏度）
    :keyword TMAX: 日最高气温（摄氏度）
    :keyword VAP: 日平均水汽压（hPa）
    :keyword RAIN: 日降水总量（cm/day）
    :keyword WIND: 2米高度日平均风速（m/sec）
    :keyword E0: 日蒸发量（静水面，cm/day）
    :keyword ES0: 日蒸发量（裸土，cm/day）
    :keyword ET0: 日参考作物蒸散量（cm/day）

    有两个可选关键字参数：

    :keyword TEMP: 日平均温度（摄氏度），否则将由 (TMAX+TMIN)/2 得出
    :keyword SNOWDEPTH: 积雪深度（cm）
    """
    sitevar = ["LAT", "LON", "ELEV"]
    required = ["IRRAD", "TMIN", "TMAX", "VAP", "RAIN", "E0", "ES0", "ET0", "WIND"]
    optional = ["SNOWDEPTH", "TEMP", "TMINRA"]
    # 未来可通过给 __slots__ 添加 '__dict__' 来扩展 __slots__ 或允许设置属性。
    __slots__ = sitevar + required + optional + ["DAY"]

    units = {"IRRAD": "J/m2/day", "TMIN": "Celsius", "TMAX": "Celsius", "VAP": "hPa",
             "RAIN": "cm/day", "E0": "cm/day", "ES0": "cm/day", "ET0": "cm/day",
             "LAT": "Degrees", "LON": "Degrees", "ELEV": "m", "SNOWDEPTH": "cm",
             "TEMP": "Celsius", "TMINRA": "Celsius", "WIND": "m/sec"}

    # 气象变量的取值范围
    ranges = {"LAT": (-90., 90.),
              "LON": (-180., 180.),
              "ELEV": (-300, 6000),
              "IRRAD": (0., 40e6),
              "TMIN": (-50., 60.),
              "TMAX": (-50., 60.),
              "VAP": (0.06, 199.3),  # hPa，按-50和60摄氏度的饱和水汽压计算
              "RAIN": (0, 25),
              "E0": (0., 2.5),
              "ES0": (0., 2.5),
              "ET0": (0., 2.5),
              "WIND": (0., 100.),
              "SNOWDEPTH": (0., 250.),
              "TEMP": (-50., 60.),
              "TMINRA": (-50., 60.)}

    def __init__(self, *args, **kwargs):

        # 仅应使用关键字参数初始化气象数据容器
        if len(args) > 0:
            msg = ("WeatherDataContainer should be initialized by providing weather " +
                   "variables through keywords only. Got '%s' instead.")
            raise exc.PCSEError(msg % args)

        # 首先赋值站点变量
        for varname in self.sitevar:
            try:
                setattr(self, varname, float(kwargs.pop(varname)))
            except (KeyError, ValueError) as e:
                msg = "Site parameter '%s' missing or invalid when building WeatherDataContainer: %s"
                raise exc.PCSEError(msg, varname, e)

        # 检查是否有 DAY 字段
        if "DAY" not in kwargs:
            msg = "Date of observations 'DAY' not provided when building WeatherDataContainer."
            raise exc.PCSEError(msg)
        self.DAY = kwargs.pop("DAY")

        # 遍历必需参数，检查是否全部提供
        for varname in self.required:
            value = kwargs.pop(varname, None)
            try:
                setattr(self, varname, float(value))
            except (KeyError, ValueError, TypeError) as e:
                msg = "%s: Weather attribute '%s' missing or invalid numerical value: %s"
                logging.warning(msg, self.DAY, varname, value)

        # 遍历可选参数
        for varname in self.optional:
            value = kwargs.pop(varname, None)
            if value is None:
                continue
            else:
                try:
                    setattr(self, varname, float(value))
                except (KeyError, ValueError, TypeError) as e:
                    msg = "%s: Weather attribute '%s' missing or invalid numerical value: %s"
                    logging.warning(msg, self.DAY, varname, value)

        # 检查是否还有剩余未知参数
        if len(kwargs) > 0:
            msg = "WeatherDataContainer: unknown keywords '%s' are ignored!"
            logging.warning(msg, kwargs.keys())

    def __setattr__(self, key, value):
        # 重写以允许对已知气象变量进行范围检查。

        # 如果用户未禁用范围检查，则进行检查
        if settings.METEO_RANGE_CHECKS:
            if key in self.ranges:
                vmin, vmax = self.ranges[key]
                if not vmin <= value <= vmax:
                    msg = "Value (%s) for meteo variable '%s' outside allowed range (%s, %s)." % (
                    value, key, vmin, vmax)
                    raise exc.PCSEError(msg)
        SlotPickleMixin.__setattr__(self, key, value)

    def __str__(self):
        msg = "Weather data for %s (DAY)\n" % self.DAY
        for v in self.required:
            value = getattr(self, v, None)
            if value is None:
                msg += "%5s: element missing!\n"
            else:
                unit = self.units[v]
                msg += "%5s: %12.2f %9s\n" % (v, value, unit)
        for v in self.optional:
            value = getattr(self, v, None)
            if value is None:
                continue
            else:
                unit = self.units[v]
                msg += "%5s: %12.2f %9s\n" % (v, value, unit)
        msg += ("Latitude  (LAT): %8.2f degr.\n" % self.LAT)
        msg += ("Longitude (LON): %8.2f degr.\n" % self.LON)
        msg += ("Elevation (ELEV): %6.1f m.\n" % self.ELEV)
        return msg

    def add_variable(self, varname, value, unit):
        """添加一个属性 <varname>，其值为 <value> 并指定 <unit>

        :param varname: 要作为属性名设置的变量名 (字符串)
        :param value: 要添加的变量（属性）的值。
        :param unit: 变量的单位的字符串表示，仅用于打印 WeatherDataContainer 的内容。
        """
        if varname not in self.units:
            self.units[varname] = unit
        setattr(self, varname, value)


class WeatherDataProvider(object):
    """所有气象数据提供者的基类。

    如果一个 WeatherDataProvider 支持集合气象数据，需要通过设置类变量 `supports_ensembles = True` 来指示。

    示例::

        class MyWeatherDataProviderWithEnsembles(WeatherDataProvider):
            supports_ensembles = True

            def __init__(self):
                WeatherDataProvider.__init__(self)

                # 此处填写剩余的初始化内容。
    """
    supports_ensembles = False

    # WeatherDataProvider 的描述性条目
    longitude = None
    latitude = None
    elevation = None
    description = []
    _first_date = None
    _last_date = None
    angstA = None
    angstB = None
    # 用于参考 ET 的模型
    ETmodel = "PM"

    def __init__(self):
        self.store = {}

    @property
    def logger(self):
        # 获取当前类的 logger 名称
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)

    def _dump(self, cache_fname):
        """使用 pickle 将内容写入 cache_fname。

        将 self.store, longitude, latitude, elevation 和 description 的值写入文件。
        """
        with open(cache_fname, "wb") as fp:
            dmp = (self.store, self.elevation, self.longitude, self.latitude, self.description, self.ETmodel)
            pickle.dump(dmp, fp, pickle.HIGHEST_PROTOCOL)

    def _load(self, cache_fname):
        """使用 pickle 从 cache_fname 加载内容。

        从 cache_fname 加载 self.store, longitude, latitude, elevation 和 description 的值，并设置 self.first_date, self.last_date。
        """

        with open(cache_fname, "rb") as fp:
            (store, self.elevation, self.longitude, self.latitude, self.description, ETModel) = pickle.load(fp)

        # 检查缓存文件中的参考 ET 是否和当前指定的 model 一致
        if ETModel != self.ETmodel:
            msg = "Mismatch in reference ET from cache file."
            raise exc.PCSEError(msg)

        self.store.update(store)

    def export(self):
        """将 WeatherDataProvider 的内容以字典列表导出。

        export 的结果可以直接转换成 Pandas DataFrame，方便绘图或分析。
        """
        weather_data = []
        if self.supports_ensembles:
            # 如果支持集合气象数据，需要在每个字典里包含 member_id
            pass
        else:
            days = sorted([r[0] for r in self.store.keys()])
            for day in days:
                wdc = self(day)
                r = {key: getattr(wdc, key) for key in wdc.__slots__ if hasattr(wdc, key)}
                weather_data.append(r)
        return weather_data

    @property
    def first_date(self):
        try:
            # 取最早日期
            self._first_date = min(self.store)[0]
        except ValueError:
            pass
        return self._first_date

    @property
    def last_date(self):
        try:
            # 取最晚日期
            self._last_date = max(self.store)[0]
        except ValueError:
            pass
        return self._last_date

    @property
    def missing(self):
        # 计算缺失天数
        missing = (self.last_date - self.first_date).days - len(self.store) + 1
        return missing

    @property
    def missing_days(self):
        # 返回缺失的日期列表
        numdays = (self.last_date - self.first_date).days
        all_days = {self.first_date + dt.timedelta(days=i) for i in range(numdays)}
        avail_days = {t[0] for t in self.store.keys()}
        return sorted(all_days - avail_days)

    def check_keydate(self, key):
        """检查用于气象数据存储/检索的日期表示形式。

        支持以下格式：

        1. date 对象
        2. datetime 对象
        3. 格式为 YYYYMMDD 的字符串
        4. 格式为 YYYYDDD 的字符串

        格式 2-4 都会被内部转换为 date 对象。
        """

        import datetime as dt
        if isinstance(key, dt.datetime):
            return key.date()
        elif isinstance(key, dt.date):
            return key
        elif isinstance(key, (str, int)):
            date_formats = {7: "%Y%j", 8: "%Y%m%d", 10: "%Y-%m-%d"}
            skey = str(key).strip()
            l = len(skey)
            if l not in date_formats:
                msg = "Key for WeatherDataProvider not recognized as date: %s"
                raise KeyError(msg % key)

            dkey = dt.datetime.strptime(skey, date_formats[l])
            return dkey.date()
        else:
            msg = "Key for WeatherDataProvider not recognized as date: %s"
            raise KeyError(msg % key)

    def _store_WeatherDataContainer(self, wdc, keydate, member_id=0):
        """将 WDC 存储在给定的 keydate 和 member_id 下。"""

        if member_id != 0 and self.supports_ensembles is False:
            msg = "Storing ensemble weather is not supported."
            raise exc.WeatherDataProviderError(msg)

        kd = self.check_keydate(keydate)
        if not (isinstance(member_id, int) and member_id >= 0):
            msg = "Member id should be a positive integer, found %s" % member_id
            raise exc.WeatherDataProviderError(msg)

        self.store[(kd, member_id)] = wdc

    def __call__(self, day, member_id=0):
        # 检查是否支持集合气象数据且 member_id 是否正确
        if self.supports_ensembles is False and member_id != 0:
            msg = "Retrieving ensemble weather is not supported by %s" % self.__class__.__name__
            raise exc.WeatherDataProviderError(msg)

        keydate = self.check_keydate(day)
        if self.supports_ensembles is False:
            # 单成员，直接查找数据
            msg = "Retrieving weather data for day %s" % keydate
            self.logger.debug(msg)
            try:
                return self.store[(keydate, 0)]
            except KeyError as e:
                msg = "No weather data for %s." % keydate
                raise exc.WeatherDataProviderError(msg)
        else:
            # 集合成员，按 (keydate, member_id) 查找
            msg = "Retrieving ensemble weather data for day %s member %i" % \
                  (keydate, member_id)
            self.logger.debug(msg)
            try:
                return self.store[(keydate, member_id)]
            except KeyError:
                msg = "No weather data for (%s, %i)." % (keydate, member_id)
                raise exc.WeatherDataProviderError(msg)

    def __str__(self):
        # 返回气象数据提供者的描述字符串
        msg = "Weather data provided by: %s\n" % self.__class__.__name__
        msg += "--------Description---------\n"
        if isinstance(self.description, str):
            # 如果描述是字符串，直接添加
            msg += ("%s\n" % self.description)
        else:
            # 如果描述是列表，将每条描述添加到消息中
            for l in self.description:
                msg += ("%s\n" % str(l))
        msg += "----Site characteristics----\n"
        msg += "Elevation: %6.1f\n" % self.elevation
        msg += "Latitude:  %6.3f\n" % self.latitude
        msg += "Longitude: %6.3f\n" % self.longitude
        msg += "Data available for %s - %s\n" % (self.first_date, self.last_date)
        msg += "Number of missing days: %i\n" % self.missing
        return msg

