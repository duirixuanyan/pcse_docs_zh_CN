# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""该模块定义了在整个PCSE/WOFOST模型上运行单元测试的代码。

各个组件的单元测试包含在这些组件的源文件中。

此处定义的类:
* WofostBenchmarkRetriever
* WofostOutputRetriever
* WofostTestingTemplate（以及用于测试的派生类）

此处定义的函数:
* run_units_tests

"""
import os
import random
import unittest

import pandas as pd
import sqlite3

from .run_wofost import run_wofost
from ..settings import settings


def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}


class WofostBenchmarkRetriever:
    """用于检索PCSE WOFOST的基准结果。
    
    本类从PCSE数据库中检索基准结果，这些基准用于对WOFOST输出进行单元测试（基准测试）。
    基准数据存储在表"wofost_unittest_benchmarks"中。
    
    示例：
    retriever = WofostBenchmarkRetriever('数据源名称', crop, grid, mode)
    benchmark_data = retriever('development_stage')
    """

    def __init__(self, dsn, crop, grid, mode='pp'):
        DBconn = sqlite3.connect(dsn)
        DBconn.row_factory = dict_factory
        sql = f"select * from wofost_unittest_benchmarks where crop_no=? and grid_no=? and " \
              f"simulation_mode=? and member_id=?"
        cursor = DBconn.cursor()
        r = cursor.execute(sql, (crop, grid, mode, 0))
        df = pd.DataFrame(r.fetchall())
        self.df_benchmarks = df.set_index("day")
        DBconn.close()
        self.crop = crop
        self.grid = grid
        self.mode = mode
        self.member_id = 0
    
    def __call__(self, variable):
        """检索指定变量的基准数据: [(day, variable),..]"""
        if not variable in self.df_benchmarks.columns:
            msg = f"variable {variable} not available in DataFrame!"
            raise RuntimeError(msg)

        rows = self.df_benchmarks[[variable]].to_records()
        return rows


class WofostOutputRetriever:
    """用于检索Wofost模拟的结果。
    
    本类从表'sim_results_timeseries'中检索Wofost模拟结果。
    这些结果随后将与基准数据进行比较，以进行单元测试。
    本过程假设表'sim_results_timeseries'中仅存在单一模拟（grid, crop, year），
    因为没有对(grid, crop, year)进行筛选。
    
    示例:
    retriever = WofostOutputRetriever('数据源名称')
    
    one_day = retriever(date(2000,1,1), 'development_stage')
    last_day = retriever.getWofostOutputLastDay('development_stage')
    """

    def __init__(self, dsn):
        DBconn = sqlite3.connect(dsn)
        DBconn.row_factory = dict_factory
        sql = f"select * from sim_results_timeseries"
        cursor = DBconn.cursor()
        r = cursor.execute(sql)
        df = pd.DataFrame(r.fetchall())
        self.df_sim_results = df.set_index("day")
        self.maxday = self.df_sim_results.index.max()
        DBconn.close()

    def __call__(self, day, variable):
        """返回指定日的指定WOFOST变量。"""

        ix = self.df_sim_results.index == day
        if not ix.any():
            msg = f"cannot find simulation results for day {day} and variable {variable}"
            raise RuntimeError(msg)
        value = self.df_sim_results.loc[ix, variable][0]
        return float(value)


class WofostTestingTemplate(unittest.TestCase):
    """执行WOFOST单元测试的模板。
    
    该模板定义了setUp()和runTest()，这是所有WOFOST单元测试运行所共有的。
    大部分功能来自于对'unittest.TestCase'的子类化。
    注意每个单元测试都只是此模板的子类。只有crop, grid, year和mode是特定于测试的，
    因此以测试类属性的形式定义。
    
    为防止因不同python版本、数据库和CPU架构导致的错误FAILS，生物量值只校验到一位或三位小数精度。    
    """

    benchmark_vars = [("DVS",3), ("TRA",3), ("RD",3),("SM", 3), ("LAI",2),
                      ("TAGP",1),("TWLV",1),("TWST",1),("TWSO",1),("TWRT",1)]

    def __init__(self, testname):
        db_location = os.path.join(settings.PCSE_USER_HOME, "pcse.db")
        self.dsn = os.path.normpath(db_location)
        unittest.TestCase.__init__(self, testname)
        
    def setUp(self):
        "设置模拟，以验证结果"
        run_wofost(dsn=self.dsn, crop=self.crop, year=self.year,
                     grid=self.grid, mode=self.mode, clear_table=True)
        self.OutputRetriever = WofostOutputRetriever(dsn=self.dsn)
        self.BenchmarkRetriever = WofostBenchmarkRetriever(dsn=self.dsn,
                                                             crop=self.crop,
                                                             grid=self.grid,
                                                             mode=self.mode)

    def run_benchmark(self, var_to_benchmark, precision):
        benchmark_data = self.BenchmarkRetriever(var_to_benchmark)
        msg = "Failure to retrieve benchmark data."
        self.assertTrue(len(benchmark_data) > 0, msg)
        n_assert = 0
        for (day, benchmark) in benchmark_data:
            value = self.OutputRetriever(day, var_to_benchmark)
            if value is None:
                continue
            diff = float(abs(value - benchmark))
            assertmsg = "Test day, variable %s, %s: %f vs %f" % \
                        (day, var_to_benchmark, benchmark, value)
            self.assertAlmostEqual(diff, 0., precision, assertmsg)
            n_assert += 1
        # 检查是否进行了任何断言。这可能由于缺失记录（如旬/月输出）、
        # 变量名拼写错误，或数据库中该变量全为NULL（如None）而未断言。
        msg = "No data found in sim_results_timeseries table for variable '%s'"
        msg = msg % var_to_benchmark
        self.assertGreater(n_assert, 0, msg)

    def runTest(self):
        for eachvar, precision in self.benchmark_vars:
            self.run_benchmark(eachvar, precision)


class TestPotentialWinterWheat(WofostTestingTemplate):
    crop = 1
    year = 2000
    grid = 31031
    mode = "pp"
        

class TestWaterlimitedWinterWheat(WofostTestingTemplate):
    crop = 1
    year = 2000
    grid = 31031
    mode = "wlp"


class TestPotentialGrainMaize(WofostTestingTemplate):
    crop = 2
    year = 2000
    grid = 31031
    mode = "pp"


class TestWaterlimitedGrainMaize(WofostTestingTemplate):
    crop = 2
    year = 2000
    grid = 31031
    mode = "wlp"


class TestPotentialSpringBarley(WofostTestingTemplate):
    crop = 3
    year = 2000
    grid = 31031
    mode = "pp"


class TestWaterlimitedSpringBarley(WofostTestingTemplate):
    crop = 3
    year = 2000
    grid = 31031
    mode = "wlp"


class TestPotentialPotato(WofostTestingTemplate):
    crop = 7
    year = 2000
    grid = 31031
    mode = "pp"
        

class TestWaterlimitedPotato(WofostTestingTemplate):
    crop = 7
    year = 2000
    grid = 31031
    mode = "wlp"


class TestPotentialWinterRapeseed(WofostTestingTemplate):
    crop = 10
    year = 2000
    grid = 31031
    mode = "pp"


class TestWaterlimitedWinterRapeseed(WofostTestingTemplate):
    crop = 10
    year = 2000
    grid = 31031
    mode = "wlp"


class TestPotentialSunflower(WofostTestingTemplate):
    crop = 11
    year = 2000
    grid = 31031
    mode = "pp"
        

class TestWaterlimitedSunflower(WofostTestingTemplate):
    crop = 11
    year = 2000
    grid = 31031
    mode = "wlp"


def suite():
    """返回PCSE/WOFOST模型的单元测试。

    关键字参数:
    dsn : 应使用的数据库的SQLAlchemy数据源名称。
    """

    suite = unittest.TestSuite()
    tests = [TestPotentialWinterWheat('runTest'),
             TestWaterlimitedWinterWheat('runTest'),
             TestPotentialGrainMaize('runTest'),
             TestWaterlimitedGrainMaize('runTest'),
             TestPotentialSpringBarley('runTest'),
             TestWaterlimitedSpringBarley('runTest'),
             TestPotentialPotato('runTest'),
             TestWaterlimitedPotato('runTest'),
             TestPotentialWinterRapeseed('runTest'),
             TestWaterlimitedWinterRapeseed('runTest'),
             TestPotentialSunflower('runTest'),
             TestWaterlimitedSunflower('runTest')]

    # 随机打乱测试顺序，以测试在不同执行顺序下是否会获得不同的结果。
    random.shuffle(tests)
    suite.addTests(tests)
    return suite
