# -*- coding: utf-8 -*-
# Copyright (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), March 2024
"""从PCSE演示数据库中检索数据的相关程序。

实现了以下函数:
    - fetch_cropdata()
    - fetch_sitedata()
    - fetch_soildata()
    - fetch_timerdata()

"""
import sys, os
import datetime as dt
import logging

import yaml

from ..exceptions import PCSEError
from ..base import WeatherDataContainer, WeatherDataProvider
from ..util import wind10to2, reference_ET, safe_float, check_date
from .. import settings


def fetch_crop_name(DBconn, crop):
    # 从crop表获取作物名称
    cursor = DBconn.cursor()
    cursor.execute("select crop_name from crop where crop_no=?", (crop,))
    row = cursor.fetchone()
    if row:
        return row.crop_name
    else:
        raise PCSEError(f"No crop_name found for crop_no={crop}")


def fetch_cropdata(DBconn, grid, year, crop):
    """从数据库检索指定grid、年份和作物的作物参数值。
    
    参数值由表 'crop_parameter_value' 和 'variety_parameter_value' 提供。
    Metadata 为 SQLAlchemy 的元数据对象。
    
    返回一个包含WOFOST作物参数（名称/数值对）的字典。
    
    请注意，参数名称在本函数内部定义，以区分标量参数和表格参数。
    当需要检索其他参数时，这些定义需要扩展。
    """
    
    # 为PCSE db_util函数定义一个日志记录器
    logger = logging.getLogger(__name__)

    # 创建初始字典
    cropdata = {}
    cropdata["CRPNAM"] = fetch_crop_name(DBconn, crop)

    # 从crop_calendar表获取作物品种
    cursor = DBconn.cursor()
    cursor.execute("select variety_no from crop_calendar where crop_no=? and grid_no=? and year=?", (crop, grid, year))
    rows = cursor.fetchall()
    variety = rows[0].variety_no

    # 定义作物参数值
    parameter_codes_sngl = ("CFET", "CVL", "CVO", "CVR", "CVS", "DEPNR", "DLC", 
                            "DLO", "DVSEND", "EFF", "IAIRDU", "IDSL", "KDIF", 
                            "LAIEM", "PERDL", "Q10", "RDI", "RDMCR", "RGRLAI", 
                            "RML", "RMO", "RMR", "RMS", "RRI", "SPA", "SPAN", "SSA", 
                            "TBASE", "TBASEM", "TDWI", "TEFFMX", "TSUM1", "TSUM2", 
                            "TSUMEM", "IOX")
    parameter_codes_mltp = ("AMAXTB", "DTSMTB", "FLTB", "FOTB", "FRTB", "FSTB", 
                            "RDRRTB", "RDRSTB", "RFSETB", "SLATB", "TMNFTB", 
                            "TMPFTB")
    
    # 首先从CROP_PARAMETER_VALUE拉取单值参数
    sql = "select * from crop_parameter_value where crop_no=? and parameter_code=?"
    for paramcode in parameter_codes_sngl:
        r = cursor.execute(sql, (crop, paramcode))
        rows = r.fetchall()
        cropdata[paramcode] = float(rows[0].parameter_xvalue)

    # 从CROP_PARAMETER_VALUE拉取数组参数值
    # 注意掩码值的变化以及SQL查询中使用了“LIKE”
    sql = "select * from crop_parameter_value where crop_no=? and parameter_code like ?"
    for paramcode in parameter_codes_mltp:
        pattern = paramcode + r'%'
        r = cursor.execute(sql, (crop, pattern))
        values = []
        for row in r.fetchall():
            values.append(float(row.parameter_xvalue))
            values.append(float(row.parameter_yvalue))
        cropdata[paramcode] = values

    # 从VARIETY_PARAMETER_VALUES拉取相同参数值
    # 如果该品种有定义则覆盖
    # 先拉取单值参数
    sql = "select * from variety_parameter_value where crop_no=? and variety_no=? and parameter_code=?"
    for paramcode in parameter_codes_sngl:
        r = cursor.execute(sql, (crop, variety, paramcode))
        rows = r.fetchall()
        if rows:
            cropdata[paramcode] = float(rows[0].parameter_xvalue)

    # 拉取数组参数值 —— 注意掩码值的变化以及SQL查询中使用了“LIKE”
    sql = "select * from variety_parameter_value where crop_no=? and variety_no=? and parameter_code like ?"
    for paramcode in parameter_codes_mltp:
        pattern = paramcode + r'%'
        r = cursor.execute(sql, (crop, variety, pattern))
        rows = r.fetchall()
        if rows:
            values = []
            for row in rows:
                values.append(float(row.parameter_xvalue))
                values.append(float(row.parameter_yvalue))
            cropdata[paramcode] = values

    cursor.close()

    # 针对PCSE wofost 7.2对变量SSA、KDIF和EFF做特殊处理
    # 由于7.2代码期望接收参数数组，而这些参数在CGMS中被定义为单值
    # DVSI在CGMS中不存在，因此设为0

    # SSA转换为SSATB:
    SSA = cropdata["SSA"]
    cropdata.update({"SSATB": [0, SSA, 2.0, SSA]})
    # KDIF转换为KDIFTB:
    KDIF = cropdata["KDIF"]
    cropdata.update({"KDIFTB": [0., KDIF, 2.0, KDIF]})
    # EFF转换为EFFTB
    EFF = cropdata["EFF"]
    cropdata.update({"EFFTB": [0., EFF, 40.0, EFF]})
    # DVSI设为0
    cropdata.update({"DVSI":0})
    
    logger.info("Succesfully retrieved crop parameter values from database")
    return cropdata


def fetch_soildata(DBconn, grid):
    """根据给定网格从数据库中提取单层土壤参数。
    
    从表 SOIL_TYPE 获取 soil_type_no，并从表 SOIL_LAYERS 和 SOIL_PHYSICAL_GROUP 获取相关土壤层和土壤理化数据。
    
    返回一个包含 WOFOST 土壤参数名称/数值对的字典。
    """
    
    cursor = DBconn.cursor()

    soildata = {}
    # 从 SOIL_TYPE 表中选择土壤类型
    sql = "select * from soil_type where grid_no=?"
    r = cursor.execute(sql, (grid,))
    row = r.fetchone()
    soil_type_no = row.soil_type_no
    
    # 根据 soil_type_no 获取土壤层。只允许有一个土壤层，否则报错。
    sql = "select * from soil_layers where soil_type_no=? order by layer_no"
    r  = cursor.execute(sql, (soil_type_no,))
    rows = r.fetchall()
    if len(rows) == 0:
        msg = "No record found."
        raise PCSEError(grid, msg)
    elif len(rows) > 1:
        msg = ("Number of soil layers > 1. Not possible for unlayered " +
               "waterbalance module. Use 'fetch_soiltype_multilayer'") 
        raise PCSEError(grid, msg)
    else:
        soildata["RDMSOL"] = float(rows[0].thickness)
        soil_group_no = rows[0].soil_group_no
    
    # 获取该土壤层的理化属性
    # 参数代码：(wofost参数名, 数据库名)
    soil_parameters = [("CRAIRC", "CRITICAL_AIR_CONTENT"),
                       ("K0", "HYDR_CONDUCT_SATUR"),
                       ("SOPE", "MAX_PERCOL_ROOT_ZONE"),
                       ("KSUB", "MAX_PERCOL_SUBSOIL"),
                       ("SMFCF", "SOIL_MOISTURE_CONTENT_FC"),
                       ("SM0", "SOIL_MOISTURE_CONTENT_SAT"),
                       ("SMW", "SOIL_MOISTURE_CONTENT_WP")]
    # table_soil_pg = Table('soil_physical_group',metadata, autoload=True)
    sql = "select * from soil_physical_group where soil_group_no=? and parameter_code=?"
    for (wofost_soil_par, db_soil_par) in soil_parameters:
        r = cursor.execute(sql, (soil_group_no, db_soil_par))
        row = r.fetchone()
        if row is None:
            msg = "Parameter %s not found" % db_soil_par
            raise PCSEError(grid, msg)
        soildata[wofost_soil_par] = float(row.parameter_xvalue)

    return soildata


class AgroManagementDataProvider(list):
    """从PCSE数据库 CROP_CALENDAR 表提供农艺管理数据的类。

    :param engine: 提供数据库访问的SqlAlchemy engine对象
    :param grid_no: 整型网格ID，对应表中的grid_no字段
    :param crop_no: 作物的整型ID，对应表中的crop_no字段
    :param campaign_year: 整型年度，对应表中的YEAR字段。
           作物生长期参考作物开始年份。对于跨年作物，start_date 可能在收获年份的前一年。
    
    注意：本类仅用于内部PCSE数据库，不应用于CGMS数据库。
    """
    agro_management_template = """
          - {campaign_start_date}:
                CropCalendar:
                    crop_name: '{crop_name}'
                    variety_name: '{variety_name}'
                    crop_start_date: {crop_start_date}
                    crop_start_type: {crop_start_type}
                    crop_end_date: {crop_end_date}
                    crop_end_type: {crop_end_type}
                    max_duration: {duration}
                TimedEvents: null
                StateEvents: null
        """

    def __init__(self, DBconn, grid_no, crop_no, campaign_year):
        list.__init__(self)
        self.grid_no = int(grid_no)
        self.crop_no = int(crop_no)
        self.campaign_year = int(campaign_year)
        self.crop_name = fetch_crop_name(DBconn, self.crop_no)

        cursor = DBconn.cursor()
        sql = "select * from crop_calendar where grid_no=? and crop_no=? and year=?"
        r = cursor.execute(sql, (self.grid_no, self.crop_no, self.campaign_year))
        row = r.fetchone()
        if not row:
            msg = f"Failed deriving crop calendar for grid_no {self.grid_no}, crop_no {self.crop_no}, year {self.campaign_year}"
            raise PCSEError(msg)

        # 判定作物开始日期
        self.crop_start_date = check_date(row.crop_start_date)
        self.campaign_start_date = row.start_date

        # 判定开始类型。PCSE/WOFOST 仅支持sowing/emergence
        self.crop_start_type = str(row.crop_start_type).strip()
        if self.crop_start_type not in ["sowing","emergence"]:
            msg = "Unrecognized crop start type: %s" % self.crop_start_type
            raise PCSEError(msg)

        # 判定最大生长期
        self.max_duration = int(row.max_duration)

        # 判定结束类型以及生长季结束
        self.crop_end_type = str(row.crop_end_type).strip().lower()
        if self.crop_end_type not in ["harvest", "earliest", "maturity"]:
            msg = ("Unrecognized option for END_TYPE in table "
                   "CROP_CALENDAR: %s" % row.end_type)
            raise PCSEError(msg)

        if self.crop_end_type == "maturity":
            self.crop_end_date = "null"
        else:
            self.crop_end_date = check_date(row.crop_end_date)

        input = self._build_yaml_agromanagement()
        self._parse_yaml(input)

    def _build_yaml_agromanagement(self):
        """构建 YAML 农业管理字符串"""

        # 未从 CGMS 数据库获取 variety_name，因此我们自定义为 <crop_name>_<grid>_<year>
        variety_name = "%s_%s_%s" % (self.crop_name, self.grid_no, self.campaign_year)
        input = self.agro_management_template.format(
            campaign_start_date=self.campaign_start_date,
            crop_name=self.crop_name,
            variety_name=variety_name,
            crop_start_date=self.crop_start_date,
            crop_start_type=self.crop_start_type,
            crop_end_date=self.crop_end_date,
            crop_end_type=self.crop_end_type,
            duration=self.max_duration
        )
        return input

    def _parse_yaml(self, input):
        """解析输入的 YAML 字符串并赋值给 self"""
        try:
            items = yaml.safe_load(input)
        except yaml.YAMLError as e:
            msg = "Failed parsing agromanagement string %s: %s" % (input, e)
            raise PCSEError(msg)
        self.extend(items)


def fetch_sitedata(DBconn, grid, year):
    """根据指定的 grid 和 year 从数据库中提取站点数据。

    从 PCSE 数据库 'SITE' 表中提取站点数据，

    返回一个包含站点参数名和值对的字典。
    """

    cursor = DBconn.cursor()
    r = cursor.execute("select * from site where grid_no=? and year=?", (grid, year))
    row = r.fetchone()
    if row is not None:
        sitedata = {}
        sitedata['IFUNRN'] = float(row.ifunrn)
        sitedata['SSMAX'] = float(row.max_surface_storage)
        sitedata['NOTINF'] = float(row.not_infiltrating_fraction)
        sitedata['SSI'] = float(row.initial_surface_storage)
        sitedata['WAV'] = float(row.inital_water_availability)
        sitedata['SMLIM'] = float(row.smlim)
    else:
        raise RuntimeError("No rows found")

    return sitedata


class GridWeatherDataProvider(WeatherDataProvider):
    """从 CGMS 数据库的 GRID_WEATHER 表中检索气象数据。

    :param metadata: 提供数据库访问的 SqlAlchemy 元数据对象
    :param grid_no:  CGMS 网格 ID
    :param startdate: 检索从 startdate 开始的气象数据
        (datetime.date 对象)
    :param enddate: 检索截止到 enddate（含） 的气象数据
        (datetime.date 对象)
    :param recalc_ET: 设置为 True 时强制计算参考 ET 值。主要用于 CGMS 数据库中未计算时。
    :param use_cache: 设置为 False 时忽略读取/写入缓存文件。

    注意，所有气象数据会先从数据库中读取并存储于内部。因此类实例内不会持有数据库连接。因此可以对类实例进行 pickling。
    """
    # 阳光持续时间模型中的 Angstrom 参数默认值
    angstA = 0.29
    angstB = 0.49

    def __init__(self, DBconn, grid_no, start_date=None, end_date=None,
                 recalc_ET=False, use_cache=True):

        WeatherDataProvider.__init__(self)
        self.grid_no = int(grid_no)
        self.recalc_ET = recalc_ET
        self.use_cache = use_cache

        if not self._self_load_cache(self.grid_no) or self.use_cache is False:
            if start_date is None:
                start_date = dt.date(dt.MINYEAR, 1, 1)
            if end_date is None:
                end_date = dt.date(dt.MAXYEAR, 1, 1)
            self.start_date = self.check_keydate(start_date)
            self.end_date = self.check_keydate(end_date)
            self.timeinterval = (end_date - start_date).days + 1

            cursor = DBconn.cursor()

            # 获取位置信息（纬度/经度/海拔）
            self._fetch_location_from_db(cursor)

            # 获取气象数据
            self._fetch_grid_weather_from_db(cursor)

            # 描述
            self.description = "Weather data derived for grid_no: %i" % self.grid_no

            # 保存缓存文件
            if self.use_cache:
                fname = self._get_cache_filename(self.grid_no)
                self._dump(fname)

    def _get_cache_filename(self, grid_no):
        # 获取缓存文件名的方法
        fname = "%s_grid_%i.cache" % (self.__class__.__name__, grid_no)
        cache_filename = os.path.join(settings.METEO_CACHE_DIR, fname)
        return cache_filename

    def _self_load_cache(self, grid_no):
        """检查缓存文件是否存在并尝试加载。"""
        cache_fname = self._get_cache_filename(grid_no)
        if os.path.exists(cache_fname):
            r = os.stat(cache_fname)
            cache_file_date = dt.date.fromtimestamp(r.st_mtime)
            age = (dt.date.today() - cache_file_date).days
            if age < 1:
                try:
                    self._load(cache_fname)
                    return True
                except PCSEError:
                    pass
        return False

    def _fetch_location_from_db(self, cursor):
        """从'grid'表获取纬度，经度和海拔，然后赋值给self.latitude, self.longitude, self.elevation。"""

        # 从数据库中拉取当前网格编号的纬度值
        sql = "select latitude, longitude, altitude from grid where grid_no=?"
        r = cursor.execute(sql, (self.grid_no,))
        row = r.fetchone()
        if not row:
            raise PCSEError(f"Cannot find lat/lon for grid {self.grid_no}")

        self.latitude = float(row.latitude)
        self.longitude = float(row.longitude)
        self.elevation = float(row.altitude)

    def _fetch_grid_weather_from_db(self, cursor):
        """从'grid_weather'表中获取气象数据。"""

        try:
            sql = "select * from grid_weather where grid_no=? and day>=? and day<=?"
            r = cursor.execute(sql, (self.grid_no, self.start_date, self.end_date))
            rows = r.fetchall()

            c = len(rows)
            # 如果选中的记录数小于所需的时间区间，警告
            if c < self.timeinterval:
                msg = "Only %i records selected from table 'grid_weather' "+\
                       "for grid %i, period %s -- %s."
                self.logger.warn(msg % (c, self.grid_no, self.start_date,
                                        self.end_date))

            meteopackager = self._make_WeatherDataContainer
            for row in rows:
                DAY = self.check_keydate(row.day)
                t = {"DAY": DAY, "LAT": self.latitude,
                     "LON": self.longitude, "ELEV": self.elevation}
                wdc = meteopackager(row, t)
                self._store_WeatherDataContainer(wdc, DAY)
        except Exception as e:
            # 读取指定日期气象数据失败时抛出异常
            errstr = "Failure reading meteodata for day %s: %s" % (row.day, str(e))
            raise PCSEError(errstr)

    def _make_WeatherDataContainer(self, row, t):
        """处理grid_weather表的数据，同时包含单位换算。"""

        t.update({"TMAX": float(row.maximum_temperature),
                  "TMIN": float(row.minimum_temperature),
                  "VAP":  float(row.vapour_pressure),
                  "WIND": wind10to2(float(row.windspeed)),
                  "RAIN": float(row.rainfall)/10.,
                  "IRRAD": float(row.calculated_radiation)*1000.,
                  "SNOWDEPTH": safe_float(row.snow_depth)})

        # 是否重算ET相关值
        if not self.recalc_ET:
            t.update({"E0":  float(row.e0)/10.,
                      "ES0": float(row.es0)/10.,
                      "ET0": float(row.et0)/10.})
        else:
            e0, es0, et0 = reference_ET(ANGSTA=self.angstA,
                                        ANGSTB=self.angstB, **t)
            t.update({"E0":  e0/10.,
                      "ES0": es0/10.,
                      "ET0": et0/10.})

        wdc = WeatherDataContainer(**t)
        return wdc
