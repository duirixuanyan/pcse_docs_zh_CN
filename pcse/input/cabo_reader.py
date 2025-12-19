# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2014 Alterra, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2014年4月
import copy
import re

from ..exceptions import PCSEError

class XYPairsError(PCSEError):
    pass

class LengthError(PCSEError):
    pass

class DuplicateError(PCSEError):
    pass

class CABOFileReader(dict):
    """读取包含模型参数定义的CABO文件。

    Wageningen作物模型的参数定义通常采用CABO格式编写。本类读取内容、解析参数名/值，并以字典形式返回。

    :param fname: 需要读取和解析的参数文件名
    :returns: 类似字典的对象，包含参数的键/值对。

    注意：本类尚未完全支持CABO文件的所有特性。例如，对布尔值、日期/时间和表格参数的解析尚未实现，会导致错误。

    CABO文件的头部（以首行为**标记）会被读取，可通过get_header()方法获取，也可直接打印返回的字典。

    *示例*

    一个名为'parfile.cab'的参数文件如下::

        ** CROP DATA FILE for use with WOFOST Version 5.4, June 1992
        **
        ** WHEAT, WINTER 102
        ** Regions: Ireland, central en southern UK (R72-R79),
        **          Netherlands (not R47), northern Germany (R11-R14)
        CRPNAM='Winter wheat 102, Ireland, N-U.K., Netherlands, N-Germany'
        CROP_NO=99
        TBASEM   = -10.0    ! lower threshold temp. for emergence [cel]
        DTSMTB   =   0.00,    0.00,     ! daily increase in temp. sum
                    30.00,   30.00,     ! as function of av. temp. [cel; cel d]
                    45.00,   30.00
        ** maximum and minimum concentrations of N, P, and K
        ** in storage organs        in vegetative organs [kg kg-1]
        NMINSO   =   0.0110 ;       NMINVE   =   0.0030

    可通过如下语句读取::

        >>>fileparameters = CABOFileReader('parfile.cab')
        >>>print fileparameters['CROP_NO']
        99
        >>>print fileparameters
        ** CROP DATA FILE for use with WOFOST Version 5.4, June 1992
        **
        ** WHEAT, WINTER 102
        ** Regions: Ireland, central en southern UK (R72-R79),
        **          Netherlands (not R47), northern Germany (R11-R14)
        ------------------------------------
        TBASEM: -10.0 <type 'float'>
        DTSMTB: [0.0, 0.0, 30.0, 30.0, 45.0, 30.0] <type 'list'>
        NMINVE: 0.003 <type 'float'>
        CROP_NO: 99 <type 'int'>
        CRPNAM: Winter wheat 102, Ireland, N-U.K., Netherlands, N-Germany <type 'str'>
        NMINSO: 0.011 <type 'float'>
    """

    # 用于解析标量、表格和字符串参数的正则表达式(RE)模式
    scpar = r"[a-zA-Z0-9_]+[\s]*=[\s]*[a-zA-Z0-9_.\-]+"
    tbpar = r"[a-zA-Z0-9_]+[\s]*=[\s]*[0-9,.\s\-+]+"
    strpar = r"[a-zA-Z0-9_]+[\s]*=[\s]*'.*?'"

    def _remove_empty_lines(self, filecontents):
        # 移除文件内容中的空行
        t = []
        for line in filecontents:
            line = line.strip(" \n\r")
            if len(line)>0:
                t.append(line)
        return t

    def _remove_inline_comments(self, filecontents):
        # 移除行尾的注释内容
        t = []
        for line in filecontents:
            line = line.split("!")[0]
            line.strip()
            if len(line) > 0:
                t.append(line)
        return t

    def _is_comment(self, line):
        # 判断当前行是否为注释行（以*号开头）
        if line.startswith("*"):
            return True
        else:
            return False

    def _find_header(self, filecontents):
        """
        解析并提取以'*'标记的文件头部信息。
        文件开头连续以'*'标记的行为头部，其余以'*'标记的行将被删除。
        """

        header = []
        other_contents = []
        inheader = True
        for line in filecontents:
            if inheader is True:
                if self._is_comment(line):
                    header.append(line)
                else:
                    other_contents.append(line)
                    inheader = False
            else:
                if self._is_comment(line):
                    pass
                else:
                    other_contents.append(line)
        return (header, other_contents)

    def _parse_table_values(self, parstr):
        """
        解析表格参数，将其转换为浮点数列表
        """

        tmpstr = parstr.strip()
        valuestrs = tmpstr.split(",")
        if len(valuestrs) < 4:
            raise LengthError((len(valuestrs), valuestrs))
        if (len(valuestrs) % 2) != 0:
            raise XYPairsError((len(valuestrs), valuestrs))

        tblvalues = []
        for vstr in valuestrs:
            value = float(vstr)
            tblvalues.append(value)
        return tblvalues

    def _find_parameter_sections(self, filecontents):
        # 返回定义float、string及table型参数的各自部分
        scalars = ""
        strings = ""
        tables = ""

        for line in filecontents:
            if line.find("'") != -1: # 字符串参数
                strings += (line + " ")
            elif line.find(",") != -1: # 表格参数
                tables += (line + " ")
            else:
                scalars += (line + " ")

        return scalars, strings, tables

    def _find_individual_pardefs(self, regexp, parsections):
        """
        将字符串分割为单独的参数定义
        """
        par_definitions = re.findall(regexp, parsections)
        rest = re.sub(regexp, "", parsections)
        rest = rest.replace(";", "")
        if rest.strip() != "":
            msg = "Failed to parse the CABO file!\n" +\
                  ("Found the following parameter definitions:\n %s" % par_definitions) + \
                  ("Failed to parse:\n %s" % rest)
            raise PCSEError(msg)
        return par_definitions

    def __init__(self, fname):
        # 用UTF-8打开
        # with open(fname) as fp:
        with open(fname, 'r', encoding='utf-8') as fp:
            filecontents = fp.readlines()
        filecontents = self._remove_empty_lines(filecontents)
        filecontents = self._remove_inline_comments(filecontents)

        if len(filecontents) == 0:
            msg = "Empty CABO file!"
            raise PCSEError(msg)

        # 分割文件头和参数部分
        self.header, filecontents = self._find_header(filecontents)

        # 使用字符串方法查找参数部分
        scalars, strings, tables = self._find_parameter_sections(filecontents)

        # 解析为单独的参数定义
        scalar_defs = self._find_individual_pardefs(self.scpar, scalars)
        table_defs = self._find_individual_pardefs(self.tbpar, tables)
        string_defs = self._find_individual_pardefs(self.strpar, strings)

        # 解析单个参数定义为名称和值
        for parstr in scalar_defs:
            try:
                parname, valuestr = parstr.split("=")
                parname = parname.strip()
                if valuestr.find(".") != -1:
                    value = float(valuestr)
                else:
                    value = int(valuestr)
                self[parname] = value
            except (ValueError) as exc:
                msg = "Failed to parse parameter, value: %s, %s"
                raise PCSEError(msg % (parstr, valuestr))

        for parstr in string_defs:
            try:
                parname, valuestr = parstr.split("=", 1)
                parname = parname.strip()
                value = (valuestr.replace("'","")).replace('"','')
                self[parname] = value
            except (ValueError) as exc:
                msg = "Failed to parse parameter, value: %s, %s"
                raise PCSEError(msg % (parstr, valuestr))

        for parstr in table_defs:
            parname, valuestr = parstr.split("=")
            parname = parname.strip()
            try:
                value = self._parse_table_values(valuestr)
                self[parname] = value
            except (ValueError) as exc:
                msg = "Failed to parse table parameter %s: %s" % (parname, valuestr)
                raise PCSEError(msg)
            except (LengthError) as exc:
                msg = "Failed to parse table parameter %s: %s. \n" % (parname, valuestr)
                msg += "Table parameter should contain at least 4 values "
                msg += "instead got %i"
                raise PCSEError(msg % exc.value[0])
            except (XYPairsError) as exc:
                msg = "Failed to parse table parameter %s: %s\n" % (parname, valuestr)
                msg += "Parameter should be have even number of positions."
                raise XYPairsError(msg)

    def __str__(self):
        """
        将对象以字符串形式输出（包括文件头与参数）
        """
        msg = ""
        for line in self.header:
            msg += line+"\n"
        msg += "------------------------------------\n"
        for key, value in self.items():
            msg += ("%s: %s %s\n" % (key, value, type(value)))
        return msg

    def copy(self):
        """
        覆写继承自 dict 的 copy 方法（原方法返回dict）
        这样可以保留类本身及如 .header 这样的属性
        """
        return copy.copy(self)
