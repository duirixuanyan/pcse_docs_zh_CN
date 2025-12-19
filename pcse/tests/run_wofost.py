# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen环境研究院, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月

import sqlite3
from collections import namedtuple
import pandas as pd

from .db_input import fetch_cropdata, fetch_sitedata, fetch_soildata, AgroManagementDataProvider, GridWeatherDataProvider
from ..base import ParameterProvider
from ..models import Wofost72_WLP_CWB, Wofost72_PP


def namedtuple_factory(cursor, row):
    """创建一个用于命名元组的SQLite行工厂。

    参见: https://docs.python.org/3/library/sqlite3.html#how-to-create-and-use-row-factories
    """
    fields = [column[0] for column in cursor.description]
    cls = namedtuple("Row", fields)
    return cls._make(row)


def run_wofost(dsn, crop, grid, year, mode, clear_table=False):
    """提供一个从PCSE数据库运行PCSE/WOFOST的便捷接口。
    
    调用run_wofost()将启动一个PCSE/WOFOST实例，并让其以给定的grid、crop、year和mode运行直到终止。
    可选地，它可以清空`sim_results_timeseries`和`sim_results_summary`表中的所有内容。
    
    :param dsn: 作为SQLAlchemy数据源名称的PCSE数据库
    :param crop: 作物编号
    :param grid: 网格编号
    :param year: 起始年份
    :param mode: 生产模式（'pp'或'wlp'）
    :param clear_table: 如果为True，则清空'tim_results_timeseries'和'sim_results_summary'表（默认为False）
    """

    # 打开数据库连接并清空输出表
    DBconn = sqlite3.connect(dsn)
    DBconn.row_factory = namedtuple_factory
    cursor = DBconn.cursor()
    if clear_table is True:
        cursor.execute("delete from sim_results_timeseries")
        cursor.execute("delete from sim_results_summary")
        cursor.close()

    # 从数据库获取输入数据
    sited = fetch_sitedata(DBconn, grid, year)
    cropd = fetch_cropdata(DBconn, grid, year, crop)
    soild = fetch_soildata(DBconn, grid)
    parameters = ParameterProvider(sitedata=sited, cropdata=cropd, soildata=soild)

    # 获取农事管理数据
    agromanagement = AgroManagementDataProvider(DBconn, grid, crop, year)

    # 获取气象数据
    wdp = GridWeatherDataProvider(DBconn, grid_no=grid)
                             
    # 初始化PCSE/WOFOST
    mode = mode.strip().lower()
    if mode == 'pp':
        wofsim = Wofost72_PP(parameters, wdp, agromanagement)
    elif mode == 'wlp':
        wofsim = Wofost72_WLP_CWB(parameters, wdp, agromanagement)
    else:
        msg = "Unrecognized mode keyword: '%s' should be one of 'pp'|'wlp'" % mode
        raise RuntimeError(msg, mode)

    wofsim.run_till_terminate()
    df_output = pd.DataFrame(wofsim.get_output())
    df_summary_output = pd.DataFrame(wofsim.get_summary_output())
    
    runid = {"grid_no":grid, "crop_no":crop, "year":year, "member_id":0,
             "simulation_mode":mode}
    for name, value in runid.items():
        df_output[name] = value
        df_summary_output[name] = value

    columns = ["grid_no", "crop_no", "year", "day", "simulation_mode", "member_id",
               "DVS", "LAI", "TAGP", "TWSO", "TWLV", "TWST", "TWRT", "TRA", "RD", "SM"]
    df_output = df_output[columns]
    df_output.to_sql("sim_results_timeseries", DBconn, index=False, if_exists='append')

    columns = ["grid_no", "crop_no", "year", "simulation_mode", "member_id",
               "DVS", "LAIMAX", "TAGP", "TWSO", "TWLV", "TWST", "TWRT", "CTRAT",
               "RD", "DOS", "DOE", "DOA", "DOM", "DOH", "DOV"]
    df_summary_output = df_summary_output[columns]
    df_summary_output.to_sql("sim_results_summary", DBconn, index=False, if_exists='append')

