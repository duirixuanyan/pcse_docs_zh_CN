# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
import unittest
from datetime import date

from ..crop.abioticdamage import FROSTOL, CrownTemperature
from ..base import VariableKiosk
from .test_data import frostol_testdata

#------------------------------------------------------------------------------
class Test_FROSTOL(unittest.TestCase):
    """FROSTOL 测试套件。
    
    测试数据由 Anne Kari Bergjord 提供。
    """

    test_vars = ["LT50T","RH","RDH_TEMP","RDH_RESP","RDH_TSTR"]
    def setUp(self):
        self.testdata = frostol_testdata
        # 从第一条测试数据记录获取参数值
        r = self.testdata[1]
        parvalues = {"LT50C":r.LT50C,
                    "IDSL":2,
                    "FROSTOL_D":r.FROSTOL_D,
                    "FROSTOL_H":r.FROSTOL_H,
                    "FROSTOL_R":r.FROSTOL_R,
                    "FROSTOL_S":r.FROSTOL_S,
                    "FROSTOL_SDBASE":0.,
                    "FROSTOL_SDMAX":12.5,
                    "FROSTOL_KILLCF":1.019,
                    "ISNOWSRC":1,
                    "CROWNTMPA":0.5,
                    "CROWNTMPB":0.2}
        # 设置变量管理器并注册变量
        self.kiosk = VariableKiosk()
        self.kiosk.register_variable(0, "ISVERNALISED", type="S", publish=True)
        self.kiosk.register_variable(0, "SNOWDEPTH", type="S", publish=True)
        # 初始化 FROSTOL
        dummyday = date(2000,1,1)
        self.frostol = FROSTOL(dummyday, self.kiosk, parvalues)
        self.crowntemp = CrownTemperature(dummyday, self.kiosk, parvalues, testing=True)

    #@unittest.skip("FROSTOL test failing because of problem with test")
    def runTest(self):
        for day in range(1, 252):
            # 参考数据和驱动变量
            drvref = self.testdata[day]

            # 在变量管理器中设置值
            vern = False if (drvref.fV < 0.99) else True
            self.kiosk.set_variable(0, "ISVERNALISED", vern)
            self.kiosk.set_variable(0, "SNOWDEPTH", drvref.snow_depth)

            # 计算速率
            self.crowntemp(day, drvref)
            self.frostol.calc_rates(day, drvref)

            # 断言模拟结果与参考值几乎相等
            for var in self.test_vars:
                refvalue = getattr(drvref, var)
                modvalue = self.frostol.get_variable(var)
                self.assertTrue(abs(refvalue - modvalue) < 0.5)

            # 积分
            self.frostol.integrate(day)

def suite():
    """ 该函数定义了本模块中所有测试 """
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Test_FROSTOL))
    return suite

if __name__ == '__main__':
   unittest.TextTestRunner(verbosity=2).run(suite())

