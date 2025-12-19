# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import os, sys
import glob
import calendar
import numpy as np
import datetime as dt
import warnings

from ..base import WeatherDataContainer, WeatherDataProvider
from ..util import reference_ET, angstrom, check_angstromAB
from ..exceptions import PCSEError

class CABOWeatherDataProvider(WeatherDataProvider):
    """CABO天气文件读取器。
    
    :param fname: 要读取的CABO天气文件的根文件名
    :param fpath: 查找文件的路径，可以是绝对路径或相对路径
    :keyword ETmodel: "PM"|"P" 用于选择Penman-Monteith或Penman方法来计算参考蒸散发，默认为"PM"
    :keyword distance: 气象变量的最大发电距离，默认为1天
    :returns: 类函数对象，通过日期索引提供气象记录
    
    使用FORTRAN或FST编写的Wageningen作物模型通常使用CABO天气系统 (http://edepot.wur.nl/43010)
    来存储和读取天气数据。此类实现了CABO天气文件的读取器，并且实现了额外的功能，如在缺失值时进行
    天气数据插值，将日照时数转换为全球辐射估算，以及使用Penman方法计算水体、土壤和作物的参考
    蒸散发值（E0、ES0、ET0）。
    
    与旧的CABOWE系统的不同之处在于，Python实现会读取并存储某个测站可用的所有文件（如年份），
    而不是在跨越年份时加载新的文件。
    
    .. 注意::
        CABOWeatherDataProvider对CABO天气文件中的单位执行了一些转换，以提高与WOFOST的兼容性:
        
        - 水汽压从kPa转换为hPa
        - 辐射从kJ/m2/day转换为J/m2/day
        - 降雨从mm/day转换为cm/day
        - 所有蒸发/蒸散速率也将以cm/day返回
    
    *示例*
    
    文件 'nl1.003' 提供了2003年Wageningen测站的天气数据，该文件可以在WOFOST模型分发包的
    cabowe/文件夹中找到。可以使用以下方式读取该文件::
    
        >>> weather_data = CABOWeatherDataProvider('nl1', fpath="./meteo/cabowe")
        >>> print weather_data(datetime.date(2003,7,26))
        Weather data for 2003-07-26 (DAY)
        IRRAD:  12701000.00  J/m2/day
         TMIN:        15.90   Celsius
         TMAX:        23.00   Celsius
          VAP:        16.50       hPa
         WIND:         3.00     m/sec
         RAIN:         0.12    cm/day
           E0:         0.36    cm/day
          ES0:         0.32    cm/day
          ET0:         0.31    cm/day
        Latitude  (LAT):    51.97 degr.
        Longitude (LON):     5.67 degr.
        Elevation (ELEV):    7.0 m.

    另外，上述print命令中的日期也可以指定为格式为YYYYMMDD或YYYYDDD的字符串。
    """
    # 天气变量的顺序、名称和转换系数
    variables = [("IRRAD",1e3, "J/m2/day"),("TMIN",1,"Celsius"),
                 ("TMAX",1,"Celsius"),("VAP",10,"hPa"),
                 ("WIND",1,"m/sec"), ("RAIN",0.1,"cm/day")]
    # Kj/m2/day的辐射量或日照时数
    has_sunshine = False
    # 状态行和观测数据的无数据值
    status_no_data = -999.
    weather_no_data = -99.
    # 起始年份和结束年份
    firstyear = None
    lastyear = None
    # CABO文件起始的第一天
    first_date = None
    # 用于存储数据的临时数组
    potential_records = None
    tmp_data = None

    def __init__(self, fname, fpath=None, ETmodel="PM", distance=1):
        WeatherDataProvider.__init__(self)

        self.ETmodel = ETmodel

        # 构建搜索路径
        search_path = self._construct_search_path(fname, fpath)
        # 查找可用的文件
        CABOWE_files, available_years, cache_file = self._find_CABOWEfiles(search_path)

        # 如果找不到缓存文件，则开始加载CABOWE文件
        if not self._load_cache_file(cache_file, CABOWE_files):
            self.tmp_data = self._calc_arraysize()

            # 遍历文件，读取表头和位置信息
            # 然后将气象数据读入tmp_data数组
            prev_cb_file = None
            for yr, cb_file in zip(available_years, CABOWE_files):
                header, loc_par, records = self._read_file(cb_file)
                # 只从第一个CABOWE文件获取表头信息
                if self.description is None:
                    self.description = header
                self._set_location_parameters(loc_par, cb_file, prev_cb_file)

                for rec in records:
                    if len(rec.strip()) == 0:
                        continue
                    if rec.startswith("-999"):
                        # 状态行，无具体数据
                        continue
                    self._proc_weather_record(rec, yr)
                prev_cb_file = cb_file

            # 将日照时数转换为全球辐射
            self._check_angstrom()
            # 进行插值，间隔由distance决定（默认1天）
            self._interpolate_timeseries(distance)
            self._make_WeatherDataContainers()

            # 将数据写入二进制缓存文件
            self._write_cache_file(search_path)

            # 删除临时数据存储的数组
            delattr(self, "tmp_data")

    def _load_cache_file(self, cache_file, CABOWE_files):
        """使用cPickle从二进制文件中加载气象数据。

        还会检查是否有任何 CABOWE 文件的修改/创建日期比 cache_file 更新。
        如果是这样则从原始 CABOWE 文件重新加载气象数据。
        
        如果加载成功返回 True，否则返回 False。
        """
        # 如果没有定义 cache_file 则直接返回 False
        if cache_file is None:
            return False

        # 如果任何 CABOWE 文件的日期 > 缓存文件：丢弃缓存文件并返回 False，从原始文件重新加载
        # 获取 CABOWE 文件的最后修改日期
        cb_dates = []
        for cb_file in CABOWE_files:
            r = os.stat(cb_file)
            cb_dates.append(r.st_mtime)
        # 获取缓存文件的修改日期
        cache_date = os.stat(cache_file).st_mtime
        if any([cbd > cache_date for cbd in cb_dates]):
            try:
                os.remove(cache_file)
            except OSError as exc:
                msg = "Failed to remove cache file '%s' due to: %s" % (cache_file, exc)
                warnings.warn(msg)
            return False
        else:
            # 否则，从缓存文件中加载数据并存储到内部
            try:
                self._load(cache_file)
                return True
            except Exception as e:
                msg = "Cache file failed loading! Try to delete cache file: %s"
                self.logger.warn(msg, cache_file)
                return False

    def _write_cache_file(self, search_path):
        """将从 CABOWE 文件加载的数据以二进制文件形式使用 cPickle 写入"""
        cache_fname = search_path + ".cache"
        self._dump(cache_fname)

    def _construct_search_path(self, fname, fpath):
        """构建查找文件的路径"""
        if fpath is None:
            # 假设 CABOWE 文件在当前文件夹
            p = os.path.join(os.getcwd(), fname)
        elif os.path.isabs(fpath):
            # 指定了绝对路径
            p = os.path.join(fpath, fname)
        else:
            # 假设路径是相对于当前文件夹
            p = os.path.join(os.getcwd(), fpath, fname)

        return os.path.normpath(p)

    def _proc_weather_record(self, rec, fileyr):
        """处理一条记录并将值插入到数组的正确位置"""
        values = rec.split()
        try:
            year = int(values[1])
            doy  = int(values[2])
            weather_obs = np.array(values[3:], dtype=np.float64)
        except (ValueError,IndexError) as exc:
            msg = ("Failed to parse line: %s" % rec)
            raise RuntimeError(msg)
        
        # 检查文件内容中的年份与文件名年份是否一致
        if year != fileyr:
            msg = "File with year %s contains record for year %s"
            raise PCSEError(msg % (fileyr, year))

        # 根据从第一天算起的天数计算在tmp_array中的位置
        rec_date = dt.date(year, 1, 1) + dt.timedelta(days=(doy-1))
        arraypos = (rec_date - self.first_date).days
        
        # 将数据插入到数组的正确位置
        self.tmp_data[:, arraypos] = weather_obs
            
    def _interpolate_timeseries(self, distance=1):
        """
        使用线性插值方法填补缺失数据（降雨量数据不进行插值）。

        distance 指定插值距离：distance=1 只允许在前后各有一天数据时插值，
        distance=2 允许两天缺失时插值，依此类推。默认值为 1。
        """
        # 用于设定插值距离的卷积核
        kernel = np.ones((1 + distance*2))

        # 跟踪 self.tmp_data 中缺失值的数组
        has_data = np.ones_like(self.tmp_data)
        # 找到与 self.weather_no_data（如 -99.）相等的缺失观测值，将其设置为 np.nan
        index = np.where(self.tmp_data == self.weather_no_data)
        has_data[index] = 0
        self.tmp_data[index] = np.nan
        # 查找 CABOWE 文件中完全缺失的记录（这些尚未插入 tmp_data，因此为 np.nan）
        # （tmp_data 初始化时为 np.nan）
        index = np.where(np.isnan(self.tmp_data) == True )
        has_data[index] = 0

        for i, (var, cf, unit) in enumerate(self.variables):
            if var == "RAIN":
                # 对降雨资料不进行插值
                continue
            timeseries_hasdata = has_data[i,:].flatten()
            if timeseries_hasdata.sum() == timeseries_hasdata.size:
                # 无缺失值
                continue
            timeseries = self.tmp_data[i,:].flatten()
            r = np.convolve(timeseries_hasdata, kernel, mode='same')
            
            # 找到可插值的位置：hasdata==0 并且相邻数据点不少于2个
            # 排除第一个和最后一个记录
            index = (timeseries_hasdata==0)*(r>=2)
            index[0]  = False
            index[-1] = False
            if True not in index:
                # 没有可以插值的位置
                continue
                
            # 确定插值位置和用于插值的已知值 (x, xp, yp)
            xrange = np.arange(self.potential_records, dtype=np.float64)
            x  = xrange[index]
            xp = xrange[(timeseries_hasdata == 1)]
            yp = timeseries[(timeseries_hasdata == 1)]
            y_int = np.interp(x,xp,yp)

            # 将插值结果放回 tmp_data 中
            self.tmp_data[i, x.astype(np.int32)] = y_int
    

    def _make_WeatherDataContainers(self):
        """将 self.tmp_data 中的数据转换为 WeatherDataContainers，并以日期为键存储在类字典中。
        
        包含 np.nan 值的不完整记录将被跳过。
        如果辐射测量以日照时数提供，则使用 Angstrom 方程估算总辐射。
        最后，为每条完整记录计算参考蒸散发量。
        """
        
        # 生成气象数据容器的原型
        #wdc_proto = self._build_WeatherDataContainer()
        
        for i in range(self.potential_records):
            rec = self.tmp_data[:, i]
            if True in np.isnan(rec):
                # 不完整记录：跳过
                continue

            # 根据数组中的位置推导日期
            thisdate = self.first_date + dt.timedelta(days=i)
            t = {"DAY": thisdate, "LAT": self.latitude, 
                 "LON": self.longitude, "ELEV": self.elevation}
            
            for obs, (name, cf, unit) in zip(rec, self.variables):
                if name == "IRRAD" and self.has_sunshine is True:
                    obs = angstrom(thisdate, self.latitude, obs, self.angstA, self.angstB)
                    # angstrom 函数以 J/m2/day 为单位，无需转换系数
                    t[name] = float(obs)
                else:
                    t[name] = float(obs)*cf
            
            # 以 mm/day 单位计算参考蒸散发量
            try:
                E0, ES0, ET0 = reference_ET(thisdate, t["LAT"], t["ELEV"], t["TMIN"], t["TMAX"], t["IRRAD"],
                                            t["VAP"], t["WIND"], self.angstA, self.angstB, self.ETmodel)
            except ValueError as e:
                msg = (("Failed to calculate reference ET values on %s. " % thisdate) +
                       ("With input values:\n %s.\n" % str(t)) +
                       ("Due to error: %s" % e))
                raise PCSEError(msg)

            # 用 ET 结果更新记录，并转换为 cm/day
            t.update({"E0": E0/10., "ES0": ES0/10., "ET0": ET0/10.})

            # 从字典 t 构建气象数据容器
            wdc = WeatherDataContainer(**t)

            # 将 wdc 添加到当前日期的字典中
            self._store_WeatherDataContainer(wdc, thisdate)
        
    def _calc_arraysize(self):
        """返回大小基于数据最小/最大年份的 NaN 数组。"""
        self.potential_records = 0
        for yr in range(self.firstyear, self.lastyear+1):
            if calendar.isleap(yr):
                self.potential_records += 366
            else:
                self.potential_records += 365
        t_ar = np.empty((6,self.potential_records), dtype=np.float64)
        t_ar[:] = np.nan
        
        return t_ar

    def _set_location_parameters(self, line, cb_file, prev_cb_file):
        """解析、检查并分配位置参数。"""
        strvalues = line.split()
        if len(strvalues) != 5:
            msg = "Did not find 5 values on location parameter line of file %s"
            raise PCSEError(msg % cb_file)
        
        parnames = ["longitude", "latitude", "elevation", "angstA", "angstB"]
        for parname, strvalue in zip(parnames, strvalues):
            try:
                fvalue = float(strvalue)
                current_value = getattr(self, parname)
                if current_value is None:
                    setattr(self, parname, fvalue)
                else:
                    if abs(current_value - fvalue) > 0.001:
                        raise AttributeError
            except ValueError as e:
                msg = "Failed to parse location parameter %s on file %s, value: %s"
                raise PCSEError(msg % (parname, cb_file, strvalue))
            except AttributeError as e:
                msg = "Inconsistent '%s' location parameter in file %s compared to file %s."
                raise PCSEError(msg % (parname, cb_file, prev_cb_file))
    
    def _check_angstrom(self):
        """检查 Angstrom 参数的一致性。

        当 A 和 B 都大于 0 时，设置 self.has_sunshine=True。
        """
        if self.angstA > 0 and self.angstB > 0:
            self.has_sunshine=True
            
        self.angstA = abs(self.angstA)
        self.angstB = abs(self.angstB)
        check_angstromAB(self.angstA, self.angstB)

    def _read_file(self, fname):
        # 使用 UTF-8 打开文件
        # with open(fname) as fp:
        with open(fname, 'r', encoding='utf-8') as fp:
            lines = fp.readlines()
        header = []
        location_par = None
        records = []
        for line in lines:
            l = line.strip()
            if l.startswith("*"):
                header.append(l)
            else:
                if location_par is None:
                    location_par = l
                else:
                    records.append(l)
        return (header, location_par, records)
    
    def _find_CABOWEfiles(self, search_path):
        """在给定路径查找 CABOWE 文件。

        同时排序列表，检查缺失年份并设置 self.firstyear/self.lastyear 和 self.first_date。
        """
        
        cachefile = search_path + ".cache"
        if not os.path.exists(cachefile):
            cachefile = None

        CABOWEfiles = sorted(glob.glob(search_path+".[0-9][0-9][0-9]"))
        if len(CABOWEfiles) == 0:
            path, tail = os.path.split(search_path+".???")
            msg = "No CABO Weather files found when searching for '%s' at %s"
            raise PCSEError(msg % (tail, path))

        available_years = []
        for Cfile in CABOWEfiles:
            path, ext = os.path.splitext(Cfile)
            ext = ext[1:]
            if ext.startswith("9"):
                weather_year = 1000 + int(ext)
            else:
                weather_year = 2000 + int(ext)
            available_years.append(weather_year)

        self.firstyear = min(available_years)
        self.lastyear = max(available_years)
        self.first_date = dt.date(self.firstyear, 1, 1)

        # 检查是否有年份缺失，如果有则写入日志警告
        all_years = set(range(self.firstyear, self.lastyear+1))
        diff = all_years.difference(set(available_years))
        if len(diff) > 0:
            msg = "No CABOWE files found for year(s): %s" % list(diff)
            warnings.warn(msg)

        return CABOWEfiles, available_years, cachefile
