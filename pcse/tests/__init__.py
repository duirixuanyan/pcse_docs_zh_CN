# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
""" PCSE的测试集合。
"""
import unittest
import warnings

from . import test_assimilation
from . import test_abioticdamage
from . import test_partitioning
from . import test_evapotranspiration
from . import test_respiration
from . import test_wofost72
from . import test_penmanmonteith
from . import test_agromanager
from . import test_lintul3

def make_test_suite(dsn=None):
    """组装测试套件并返回
    """
    allsuites = unittest.TestSuite([
                                    test_abioticdamage.suite(),
                                    # test_assimilation.suite(),  # 跳过该测试，因为测试输入不包含TMIN
                                    test_partitioning.suite(),
                                    test_evapotranspiration.suite(),
                                    test_respiration.suite(),
                                    test_penmanmonteith.suite(),
                                    test_agromanager.suite(),
                                    test_wofost72.suite(),
                                    # test_lintul3.suite(),
                                    ])
    return allsuites

def test_all(dsn=None):
    """组装测试套件并通过TextTestRunner运行测试
    """
    allsuites = make_test_suite(dsn)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        unittest.TextTestRunner(verbosity=2).run(allsuites)
