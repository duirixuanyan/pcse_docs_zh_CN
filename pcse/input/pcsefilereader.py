# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2014 Alterra, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2014年4月
import copy
import os, sys
import inspect
import textwrap

class PCSEFileReader(dict):
    """PCSE格式参数文件的读取器。

    本类是`CABOFileReader`的替代。后者可用于读取CABO格式的参数文件，但该格式有相当严重的限制：只支持字符串、整型、浮点型和数组参数。不支持，用于指定参数为日期（只能以字符串的形式指定）。

    `PCSEFileReader`是一个功能更强大的参数文件创建工具，因为它利用了python解释器的能力，通过python中的`execfile`功能处理参数文件。这意味着在python脚本中能做的任何事情，在PCSE参数文件中也能实现。

    :param fname: 需要读取和解析的参数文件
    :returns: 包含参数键/值对的字典对象。

    *示例*

    下面是参数文件'parfile.pcse'的一个示例。参数可以以“CABO”的方式定义，也可以通过导入模块、将参数定义为日期或numpy数组，甚至对数组应用函数（例如`np.sin`）来使用高级功能::

        '''这是我的参数文件的头部。

        该文件来源如下
        * 用于演示PCSEFileReader的示例文件
        * 包含如何利用日期、数组和函数等功能的例子
        '''

        import numpy as np
        import datetime as dt

        TSUM1 = 1100
        TSUM2 = 900
        DTSMTB = [ 0., 0.,
                   5., 5.,
                  20., 25.,
                  30., 25.]
        AMAXTB = np.sin(np.arange(12))
        cropname = 'alfalfa'
        CROP_START_DATE = dt.date(2010,5,14)

    可通过如下语句读取::

        >>>fileparameters = PCSEFileReader('parfile.pcse')
        >>>print fileparameters['TSUM1']
        1100
        >>>print fileparameters['CROP_START_DATE']
        2010-05-14
        >>>print fileparameters
        PCSE parameter file contents loaded from:
        D:\\UserData\\pcse_examples\\parfile.pw

        这是我的参数文件的头部。

        该文件来源如下
        * 用于演示PCSEFileReader的示例文件
        * 包含如何利用日期、数组和函数等功能的例子
        DTSMTB: [0.0, 0.0, 5.0, 5.0, 20.0, 25.0, 30.0, 25.0] (<type 'list'>)
        CROP_START_DATE: 2010-05-14 (<type 'datetime.date'>)
        TSUM2: 900 (<type 'int'>)
        cropname: alfalfa (<type 'str'>)
        AMAXTB: [ 0.          0.84147098  0.90929743  0.14112001 -0.7568025
          -0.95892427  -0.2794155   0.6569866   0.98935825  0.41211849
          -0.54402111 -0.99999021] (<type 'numpy.ndarray'>)
        TSUM1: 1100 (<type 'int'>)
    """

    def __init__(self, fname):
        dict.__init__(self)

        # 构建参数文件的完整路径并检查文件是否存在
        cwd = os.getcwd()
        self.fname_fp = os.path.normpath(os.path.join(cwd, fname))
        if not os.path.exists(self.fname_fp):
            msg = "Could not find parameter file '%s'" % self.fname_fp
            raise RuntimeError(msg)

        # 编译并执行文件内容
        # bytecode = compile(open(self.fname_fp).read(), self.fname_fp, 'exec')
        # 使用 UTF-8 编码打开文件并编译
        bytecode = compile(open(self.fname_fp, encoding='utf-8').read(), 
                        self.fname_fp, 'exec')
        exec(bytecode, {}, self)

        # 移除self中所有是python模块的成员
        keys = list(self.keys())
        for k in keys:
            if inspect.ismodule(self[k]):
                self.pop(k)

        # 如果文件中有头部（例如__doc__），则保存之。
        if "__doc__" in self:
            header = self.pop("__doc__")
            if len(header) > 0:
                self.header = header
                if self.header[-1] != "\n":
                    self.header += "\n"
        else:
            self.header = None

    def __str__(self):
        printstr = "PCSE parameter file contents loaded from:\n"
        printstr += "%s\n\n" % self.fname_fp
        if self.header is not None:
            printstr += self.header
        for k in self:
             r = "%s: %s (%s)" % (k, self[k], type(self[k]))
             printstr += (textwrap.fill(r, subsequent_indent="  ") + "\n")
        return printstr

    def copy(self):
        """
        重载继承自dict的copy方法（该方法返回一个字典）。本方法保留类及.header等属性。
        """
        return copy.copy(self)
