import copy

class DummySoilDataProvider(dict):
    """该类用于为潜在产量模拟提供一些虚拟的土壤参数。

    潜在产量水平的模拟与土壤无关。然而，模型仍然需要一些参数值。
    此数据提供者为这种情况提供了一些硬编码的参数值。
    """
    _defaults = {"SMFCF":0.3,
                 "SM0":0.4,
                 "SMW":0.1,
                 "RDMSOL":120,
                 "CRAIRC":0.06,
                 "K0":10.,
                 "SOPE":10.,
                 "KSUB":10.}

    def __init__(self):
        dict.__init__(self)
        self.update(self._defaults)

    def copy(self):
        """
        重写继承自 dict.copy 的方法，dict.copy 返回一个 dict。
        此方法则保留了类和诸如 .header 这样的属性。
        """
        return copy.copy(self)
