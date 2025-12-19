# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import sys, os
from collections import namedtuple
import sqlite3

from .tests.db_input import GridWeatherDataProvider, fetch_soildata, fetch_sitedata, fetch_cropdata, \
    AgroManagementDataProvider
from .base import ParameterProvider
from .models import Wofost72_PP, Wofost72_WLP_CWB
from .settings import settings


def namedtuple_factory(cursor, row):
    """为命名元组创建一个SQLite行工厂。

    参见: https://docs.python.org/3/library/sqlite3.html#how-to-create-and-use-row-factories
    """
    fields = [column[0] for column in cursor.description]
    cls = namedtuple("Row", fields)
    return cls._make(row)


def start_wofost(grid=31031, crop=1, year=2000, mode='wlp'):
    """为内部演示数据库启动WOFOST实例提供便捷接口。
    
    如果不带参数调用，函数将连接到演示数据库，
    并为西班牙（grid_no=31031）在2000年初始化冬小麦（cropno=1）
    的有限水分生产（mode='wlp'）
    
    
    :param grid: 网格编号，默认为31031
    :param crop: 作物编号，默认为1（演示数据库中的冬小麦）
    :param year: 开始年份，默认为2000
    :param mode: 生产模式（'pp' 或 'wlp'），默认为 'wlp'

    示例::
    
        >>> import pcse
        >>> wofsim = pcse.start_wofost(grid=31031, crop=1, year=2000, 
        ...   mode='wlp')
        >>> 
        >>> wofsim
        <pcse.models.Wofost71_WLP_FD at 0x35f2550>
        >>> wofsim.run(days=300)
        >>> wofsim.get_variable('tagp')
        15261.752187075261
    """

    # 打开数据库连接
    db_location = os.path.join(settings.PCSE_USER_HOME, "pcse.db")
    DBconn = sqlite3.connect(db_location)
    DBconn.row_factory = namedtuple_factory

    # 从数据库获取输入数据
    agromanagement = AgroManagementDataProvider(DBconn, grid, crop, year)
    sited  = fetch_sitedata(DBconn, grid, year)
    cropd = fetch_cropdata(DBconn, grid, year, crop)
    soild = fetch_soildata(DBconn, grid)
    parvalues = ParameterProvider(sitedata=sited, soildata=soild, cropdata=cropd)

    wdp = GridWeatherDataProvider(DBconn, grid_no=grid)
                             
    # 初始化PCSE/WOFOST
    mode = mode.strip().lower()
    if mode == 'pp':
        wofsim = Wofost72_PP(parvalues, wdp, agromanagement)
    elif mode == 'wlp':
        wofsim = Wofost72_WLP_CWB(parvalues, wdp, agromanagement)
    else:
        msg = "Unrecognized mode keyword: '%s' should be one of 'pp'|'wlp'" % mode
        raise RuntimeError(msg)
    return wofsim
