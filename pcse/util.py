# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""PCSE的杂项工具
"""
import os, sys
import datetime
import copy
import platform
import tempfile
import logging
from math import log10, cos, sin, asin, sqrt, exp, pi, radians
from collections import namedtuple
from bisect import bisect_left
import sqlite3
if sys.version_info > (3,8):
    from collections.abc import Iterable
else:
    from collections import Iterable

import dotmap
from . import exceptions as exc
from .traitlets import TraitType

Celsius2Kelvin = lambda x: x + 273.16
hPa2kPa = lambda x: x/10.

# 在温度 temp [℃] 时的饱和水汽压 [kPa]
SatVapourPressure = lambda temp: 0.6108 * exp((17.27 * temp) / (237.3 + temp))

# 用于返回ASTRO结果的命名元组
astro_nt = namedtuple("AstroResults", "DAYL, DAYLP, SINLD, COSLD, DIFPP, "
                                      "ATMTR, DSINBE, ANGOT")


def reference_ET(DAY, LAT, ELEV, TMIN, TMAX, IRRAD, VAP, WIND,
                 ANGSTA, ANGSTB, ETMODEL="PM", **kwargs):
    """计算参考蒸散发量 E0、ES0 和 ET0。

    自由水面（E0）和裸土（ES0）的蒸发量采用修正的 Penman 方法计算，作物冠层的参考蒸散发量则可以用
    修正的 Penman 方法或 Penman-Monteith 方法（后者为默认）。

    输入变量::

        DAY     -  Python 的 datetime.date 对象                      -
        LAT     -  站点纬度                                      度
        ELEV    -  海拔高度                                       米
        TMIN    -  最低气温                                       摄氏度
        TMAX    -  最高气温                                       摄氏度
        IRRAD   -  日短波辐射                                 J m-2 d-1
        VAP     -  24 小时平均水汽压                              百帕
        WIND    -  2 米高度 24 小时平均风速                         m/s
        ANGSTA  -  Angstrom 公式经验常数                            -
        ANGSTB  -  Angstrom 公式经验常数                            -
        ETMODEL -  指示冠层参考ET的计算方法（Penman-Monteith (PM) 或 修正Penman (P)）PM|P

    输出为元组 (E0, ES0, ET0)::

        E0      -  Penman 潜在蒸发（自由水面） [mm/d]
        ES0     -  Penman 潜在蒸发（潮湿裸土面） [mm/d]
        ET0     -  Penman 或 Penman-Monteith 潜在蒸散发（作物冠层） [mm/d]

.. note:: Penman-Monteith 算法仅适用于参考冠层，因此不用于计算裸土和自由水面的参考值（ES0，E0）。

    背景是：Penman-Monteith 模型本质上是一个表面能量平衡模型，净太阳辐射被分配到潜热和感热通量（忽略土壤热通量）。
    为了估计这一分配，PM 方法通过将表面温度和气温联系起来来进行计算。然而，PM 模型的假设仅在进行分配的表面
    对潜热和感热通量而言相同时才成立。

    对于作物冠层，这一假设是成立的，因为叶片表面既是潜热（气孔）的释放面，也是感热（叶温）的释放面。
    对于土壤，这一假设不成立，因为随着土壤干燥，蒸发前锋很快跌至表面以下，分配表面不再相同。

    对于水体，PM 的假设同样不成立，因为水面温度与净入射辐射间没有直接关系，辐射被水柱吸收，同时水表面温度还受
    其他因素（混合等）影响。只有在极浅的水层（1 厘米）时，PM 方法才适用。

    对于裸土和自由水面，更推荐 Penman 模型。虽然它也存在部分上述问题，但经验风函数对裸土和自由水面的校准效果更好。

    最后，在作物模型中，自由水面和裸土的蒸发仅在播种前和水稻出苗早期等情况下有少量作用，因此对于 E0 和 ES0 的
    参考值无需进行高精度改进。
    """
    if ETMODEL not in ["PM", "P"]:
        msg = "Variable ETMODEL can have values 'PM'|'P' only."
        raise RuntimeError(msg)

    E0, ES0, ET0 = penman(DAY, LAT, ELEV, TMIN, TMAX, IRRAD, VAP, WIND,
                          ANGSTA, ANGSTB)
    if ETMODEL == "PM":
        ET0 = penman_monteith(DAY, LAT, ELEV, TMIN, TMAX, IRRAD, VAP, WIND)

    return E0, ES0, ET0


def penman(DAY, LAT, ELEV, TMIN, TMAX, AVRAD, VAP, WIND2, ANGSTA, ANGSTB):
    """
    基于 Penman 模型计算 E0、ES0、ET0。

    本函数计算来自自由水面 (E0)、湿裸土面 (ES0) 和作物冠层 (ET0) 的潜在蒸散（发）量，单位为 mm/d。
    计算方法遵循 Penman 的理论（Frere and Popov, 1979；Penman, 1948, 1956, 和 1963）。
    所调用的子程序和函数：ASTRO、LIMIT。

    输入变量::

        DAY     -  Python datetime.date 对象                                   -
        LAT     -  站点纬度                                     度
        ELEV    -  海拔高度                                    米
        TMIN    -  最低气温                                    摄氏度
        TMAX    -  最高气温                                    摄氏度
        AVRAD   -  日短波辐射                                J m-2 d-1
        VAP     -  24 小时平均水汽压                            百帕
        WIND2   -  2 米高度 24 小时平均风速                      m/s
        ANGSTA  -  Angstrom 公式经验常数                         -
        ANGSTB  -  Angstrom 公式经验常数                         -

    输出为元组 (E0, ES0, ET0)::

        E0      -  Penman 潜在蒸发（自由水面） [mm/d]
        ES0     -  Penman 潜在蒸发（潮湿裸土面） [mm/d]
        ET0     -  Penman 潜在蒸散发（作物冠层） [mm/d]
    """
    # 精密计测仪常数（mbar/摄氏度）
    # 水面、土壤表面和冠层的反照率
    # 水的汽化潜热（J/kg=J/mm）
    # 斯特藩-玻尔兹曼常数（单位：J/m2/d/K4，例如已乘以24*60*60）
    PSYCON = 0.67; REFCFW = 0.05; REFCFS = 0.15; REFCFC = 0.25
    LHVAP = 2.45E6; STBC =  5.670373E-8 * 24*60*60 # (=4.9E-3)

    # 预处理计算
    # 日均温和日较差（摄氏度）
    # 风函数中的Bu系数，依赖于日较差
    TMPA = (TMIN+TMAX)/2.
    TDIF = TMAX - TMIN
    BU = 0.54 + 0.35 * limit(0.,1.,(TDIF-12.)/4.)

    # 气压（mbar）
    # 精密计测仪常数（mbar/摄氏度）
    PBAR = 1013.*exp(-0.034*ELEV/(TMPA+273.))
    GAMMA = PSYCON*PBAR/1013.

    # 根据 Goudriaan (1977) 公式计算饱和水汽压
    # 饱和水汽压对温度的导数，即斜率（mbar/摄氏度）
    # 实测水汽压不应超过饱和水汽压
    SVAP = 6.10588 * exp(17.32491*TMPA/(TMPA+238.102))
    DELTA = 238.102*17.32491*SVAP/(TMPA+238.102)**2
    VAP = min(VAP, SVAP)

    # Penman 公式中的 n/N (RELSSD) 项，由 Angstrom 公式估算：
    # RI=RA(A+B*n/N) -> n/N=(RI/RA-A)/B，
    # 其中 RI/RA 由 ASTRO 返回的大气透过率确定
    r = astro(DAY, LAT, AVRAD)
    RELSSD = limit(0., 1., (r.ATMTR-abs(ANGSTA))/abs(ANGSTB))

    # Penman 公式中的各项，分别针对水面、土壤和冠层

    # 净长波辐射损失（J/m2/d），按 Brunt (1932)
    RB = STBC*(TMPA+273.)**4*(0.56-0.079*sqrt(VAP))*(0.1+0.9*RELSSD)

    # 吸收净辐射，转换为 mm/d
    RNW = (AVRAD*(1.-REFCFW)-RB)/LHVAP
    RNS = (AVRAD*(1.-REFCFS)-RB)/LHVAP
    RNC = (AVRAD*(1.-REFCFC)-RB)/LHVAP

    # 大气对蒸发的需求（mm/d）
    EA  = 0.26 * max(0.,(SVAP-VAP)) * (0.5+BU*WIND2)
    EAC = 0.26 * max(0.,(SVAP-VAP)) * (1.0+BU*WIND2)

    # Penman 公式 (1948)
    E0  = (DELTA*RNW+GAMMA*EA)/(DELTA+GAMMA)
    ES0 = (DELTA*RNS+GAMMA*EA)/(DELTA+GAMMA)
    ET0 = (DELTA*RNC+GAMMA*EAC)/(DELTA+GAMMA)

    # 保证参考蒸发量>=0
    E0  = max(0., E0)
    ES0 = max(0., ES0)
    ET0 = max(0., ET0)

    return E0, ES0, ET0


def penman_monteith(DAY, LAT, ELEV, TMIN, TMAX, AVRAD, VAP, WIND2):
    """基于 Penman-Monteith 模型计算参考作物蒸散量（ET0）。

     本函数计算参考作物冠层的潜在蒸散量（ET0），单位为 mm/d。计算方法遵循
     FAO 的分析，详见 FAO 报告
     `Guidelines for computing crop water requirements - FAO Irrigation
     and drainage paper 56 <http://www.fao.org/docrep/X0490E/x0490e00.htm#Contents>`_

    输入变量::

        DAY   -  Python datetime.date 类型                   -
        LAT   -  站点纬度                                 度
        ELEV  - 海拔高度                                    m
        TMIN  - 最低温度（最低气温）                         °C
        TMAX  - 最高温度（最高气温）                         °C
        AVRAD - 日均短波辐射                          J m-2 d-1
        VAP   - 24小时平均水汽压                            hPa
        WIND2 - 2米高度24小时平均风速                      m/s

    输出:

        ET0   - Penman-Monteith 潜在蒸散量
                参考作物冠层的蒸散速率                   [mm/d]
    """

    # 干湿表常数 (kPa/摄氏度)
    PSYCON = 0.665
    # 参考作物冠层的反照率和地表阻力 [sec/m]
    REFCFC = 0.23; CRES = 70.
    # 水的汽化潜热 [J/kg == J/mm]
    LHVAP = 2.45E6
    # 斯特藩-玻尔兹曼常数 (J/m2/d/K4, 已含 24*60*60)
    STBC = 4.903E-3
    # 土壤热通量 [J/m2/day]，此处显式为0
    G = 0.

    # 日均温度 (摄氏度)
    TMPA = (TMIN+TMAX)/2.

    # 水汽压单位从 hPa 转换为 kPa
    VAP = hPa2kPa(VAP)

    # 标准温度293K时的大气压 (kPa)
    T = 293.0
    PATM = 101.3 * pow((T - (0.0065*ELEV))/T, 5.26)

    # 干湿表常数 (kPa/摄氏度)
    GAMMA = PSYCON * PATM * 1.0E-3

    # 饱和蒸气压对平均温度的导数，即饱和蒸气压-温度曲线斜率 (kPa/摄氏度)
    SVAP_TMPA = SatVapourPressure(TMPA)
    DELTA = (4098. * SVAP_TMPA)/pow((TMPA + 237.3), 2)

    # 用最高/最低气温求日平均饱和水汽压 [kPa]
    SVAP_TMAX = SatVapourPressure(TMAX)
    SVAP_TMIN = SatVapourPressure(TMIN)
    SVAP = (SVAP_TMAX + SVAP_TMIN) / 2.

    # 实测水汽压不应超过饱和水汽压
    VAP = min(VAP, SVAP)

    # 长波辐射损失，按 Tmax、Tmin 计算（J/m2/d）
    # 初步净长波向外辐射（J/m2/d）
    STB_TMAX = STBC * pow(Celsius2Kelvin(TMAX), 4)
    STB_TMIN = STBC * pow(Celsius2Kelvin(TMIN), 4)
    RNL_TMP = ((STB_TMAX + STB_TMIN) / 2.) * (0.34 - 0.14 * sqrt(VAP))

    # 晴空辐射 [J/m2/DAY]，基于 Angot TOA 辐射
    # 由 astro() 计算获得
    r = astro(DAY, LAT, AVRAD)
    CSKYRAD = (0.75 + (2e-05 * ELEV)) * r.ANGOT

    if CSKYRAD > 0:
        # 最终净外出长波辐射 [J/m2/day]
        RNL = RNL_TMP * (1.35 * (AVRAD/CSKYRAD) - 0.35)

        # 参考面辐射蒸发当量 [mm/d]
        RN = ((1-REFCFC) * AVRAD - RNL)/LHVAP

        # 动力学蒸发当量（空气动力项）[mm/d]
        EA = ((900./(TMPA + 273)) * WIND2 * (SVAP - VAP))

        # 修正的干湿表常数 (gamma*)[kPa/°C]
        MGAMMA = GAMMA * (1. + (CRES/208.*WIND2))

        # 参考蒸散发 (ET0)，单位为 mm/天
        ET0 = (DELTA * (RN-G))/(DELTA + MGAMMA) + (GAMMA * EA)/(DELTA + MGAMMA)
        ET0 = max(0., ET0)
    else:
        ET0 = 0.

    return ET0


def check_angstromAB(xA, xB):
    """检查Angstrom系数的有效性。

    这是FORTRAN程序 'weather.for' 中 'WSCAB' 例程的 Python 版本。
    """
    MIN_A = 0.1
    MAX_A = 0.4
    MIN_B = 0.3
    MAX_B = 0.7
    MIN_SUM_AB = 0.6
    MAX_SUM_AB = 0.9
    A = abs(xA)
    B = abs(xB)
    SUM_AB = A + B
    if A < MIN_A or A > MAX_A:
        msg = "invalid Angstrom A value!"
        raise exc.PCSEError(msg)
    if B < MIN_B or B > MAX_B:
        msg = "invalid Angstrom B value!"
        raise exc.PCSEError(msg)
    if SUM_AB < MIN_SUM_AB or SUM_AB > MAX_SUM_AB:
        msg = "invalid sum of Angstrom A & B values!"
        raise exc.PCSEError(msg)

    return [A,B]


def wind10to2(wind10):
    """通过对数风速廓线，将10米处的风速换算为2米处风速。"""
    wind2 = wind10 * (log10(2./0.033) / log10(10/0.033))
    return wind2


def ea_from_tdew(tdew):
    """
    利用露点温度计算实际水汽压 ea [kPa]，使用FAO论文中的公式(14)。
    由于露点温度是使空气达到饱和时需降至的温度，因此实际水汽压等于该露点温度下的饱和水汽压。
    这种方法比用最低气温计算水汽压更为准确。

    摘自 Mark Richards 编写的 fao_et0.py

    参考文献:
    Allen, R.G., Pereira, L.S., Raes, D. and Smith, M. (1998) Crop
        evapotranspiration. Guidelines for computing crop water requirements,
        FAO 灌溉与排水论文56号

    参数:
    tdew - 露点温度 [摄氏度]
    """
    # 检查异常输入:
    if tdew < -95.0 or tdew > 65.0:
        # 这些界限合理吗？
        msg = 'tdew=%g is not in range -95 to +60 deg C' % tdew
        raise ValueError(msg)

    tmp = (17.27 * tdew) / (tdew + 237.3)
    ea = 0.6108 * exp(tmp)
    return ea


def vap_from_relhum(rh, temp):
    """根据给定温度和相对湿度计算实际水汽压

    :param rh: 相对湿度（百分比）
    :param temp: 计算相对湿度所对应的温度
    :return: 水汽压，单位为kPa
    """

    if not 0 <= rh <= 100:
        msg = "Relative humidity should be between 0 and 100"
        raise RuntimeError(msg)

    return SatVapourPressure(temp) * rh * 0.01


def angstrom(day, latitude, ssd, cA, cB):
    """利用Angstrom公式计算总辐射。

    总辐射根据日照时数，通过Angstrom公式计算:
    globrad = Angot * (cA + cB * (sunshine / daylength))

    :param day: 观测日期（date对象）
    :param latitude: 观测点纬度
    :param ssd: 观测日照时数
    :param cA: Angstrom A 参数
    :param cB: Angstrom B 参数
    :returns: 总辐射，单位J/m2/day
    """
    r = astro(day, latitude, 0)
    globrad = r.ANGOT * (cA + cB * (ssd / r.DAYL))
    return globrad


def doy(day):
    """将date或datetime对象转换为一年中的第几天（1月1日为第1天）"""
    # 检查day是否为date或datetime对象
    if isinstance(day, (datetime.date, datetime.datetime)):
        return day.timetuple().tm_yday
    else:
        msg = "Parameter day is not a date or datetime object."
        raise RuntimeError(msg)


def limit(vmin, vmax, v):
    """将v限定在最小值和最大值之间"""

    if vmin > vmax:
        raise RuntimeError("Min value (%f) larger than max (%f)" % (vmin, vmax))

    if v < vmin:       # v小于下限，返回下限值
        return vmin
    elif v < vmax:     # v在范围区间内，返回自身
        return v
    else:              # v大于上限，返回最大值
        return vmax


def daylength(day, latitude, angle=-4, _cache={}):
    """计算指定日期、纬度和基准角度下的日长。

    :param day:         date或datetime对象
    :param latitude:    观测点纬度
    :param angle:       光周期性日长的起止点，即太阳位于地平线下`angle`度时。默认值为-4度。

    本函数源自WOFOST的ASTRO.FOR例程，简化为仅包含日长计算。结果会被缓存以提高性能。
    """
    #from unum.units import h

    # 检查纬度范围
    if abs(latitude) > 90.:
        msg = "Latitude not between -90 and 90"
        raise RuntimeError(msg)

    # 从日期对象day计算一年中的第几天
    IDAY = doy(day)

    # 检查给定(day, latitude, angle)对应的daylength是否已经计算过。
    # 如果没有（如KeyError），则计算daylength，存入缓存并返回值。
    try:
        return _cache[(IDAY, latitude, angle)]
    except KeyError:
        pass

    # 常数
    RAD = radians(1.)

    # 计算日长
    ANGLE = angle
    LAT = latitude
    DEC = -asin(sin(23.45*RAD)*cos(2.*pi*(float(IDAY)+10.)/365.))
    SINLD = sin(RAD*LAT)*sin(DEC)
    COSLD = cos(RAD*LAT)*cos(DEC)
    AOB = (-sin(ANGLE*RAD)+SINLD)/COSLD

    # 日长
    if abs(AOB) <= 1.0:
        DAYLP = 12.0*(1.+2.*asin((-sin(ANGLE*RAD)+SINLD)/COSLD)/pi)
    elif AOB > 1.0:
        DAYLP = 24.0
    else:
        DAYLP =  0.0

    # 结果存入缓存
    _cache[(IDAY, latitude, angle)] = DAYLP

    return DAYLP


def astro(day, latitude, radiation, _cache={}):
    """python version of ASTRO routine by Daniel van Kraalingen.

    该子程序计算天文日长、日周期辐射特性，如大气透射率、散射辐射等。

    :param day:         date/datetime对象
    :param latitude:    观测点纬度
    :param radiation:   每日总入射辐射(J/m2/day)

    返回为`namedtuple`，字段和顺序如下::

        DAYL      天文日长 (基准=0度)     小时(h)
        DAYLP     天文日长 (基准=-4度)    小时(h)
        SINLD     太阳高度正弦的季节偏移   -
        COSLD     太阳高度正弦的振幅       -
        DIFPP     垂直于光线方向的散射辐射 J m-2 s-1
        ATMTR     每日大气透射率           -
        DSINBE    有效太阳高度的每日总和   秒(s)
        ANGOT     顶层大气安古特辐射      J m-2 d-1

    作者: Daniel van Kraalingen
    日期: 1991年4月

    Python版本
    作者: Allard de Wit
    日期: 2011年1月
    """

    # 检查纬度范围
    if abs(latitude) > 90.:
        msg = "Latitude not between -90 and 90"
        raise RuntimeError(msg)
    LAT = latitude

    # 根据日期获得一年中的第几天（IDAY）
    IDAY = doy(day)

    # 重新赋值辐射变量
    AVRAD = radiation

    # 检查给定(day, latitude, radiation)的变量是否已经在之前的运行中计算过
    # 如果没有（例如 KeyError），则计算这些变量，存入缓存并返回值
    try:
        return _cache[(IDAY, LAT, AVRAD)]
    except KeyError:
        pass

    # 常数定义
    RAD = radians(1.)
    ANGLE = -4.

    # 计算当天的赤纬角和太阳常数
    DEC = -asin(sin(23.45*RAD)*cos(2.*pi*(float(IDAY)+10.)/365.))
    SC  = 1370.*(1.+0.033*cos(2.*pi*float(IDAY)/365.))

    # 根据中间变量计算日长
    # 包括SINLD, COSLD和AOB
    SINLD = sin(RAD*LAT)*sin(DEC)
    COSLD = cos(RAD*LAT)*cos(DEC)
    AOB = SINLD/COSLD

    # 对于极高纬度和夏季与冬季的日子（极昼/极夜），
    # 增加一个限制，避免当日长达到24小时（夏季）或0小时（冬季）时发生数学错误

    # 基准=0度时的日长计算
    if abs(AOB) <= 1.0:
        DAYL  = 12.0*(1.+2.*asin(AOB)/pi)
        # 太阳高度正弦积分
        DSINB  = 3600.*(DAYL*SINLD+24.*COSLD*sqrt(1.-AOB**2)/pi)
        DSINBE = 3600.*(DAYL*(SINLD+0.4*(SINLD**2+COSLD**2*0.5))+
                 12.*COSLD*(2.+3.*0.4*SINLD)*sqrt(1.-AOB**2)/pi)
    else:
        if AOB >  1.0: DAYL = 24.0
        if AOB < -1.0: DAYL = 0.0
        # 太阳高度正弦积分
        DSINB = 3600.*(DAYL*SINLD)
        DSINBE = 3600.*(DAYL*(SINLD+0.4*(SINLD**2+COSLD**2*0.5)))

    # 基准=-4（ANGLE）度时的日长计算
    AOB_CORR = (-sin(ANGLE*RAD)+SINLD)/COSLD
    if abs(AOB_CORR) <= 1.0:
        DAYLP = 12.0*(1.+2.*asin(AOB_CORR)/pi)
    elif AOB_CORR > 1.0:
        DAYLP = 24.0
    elif AOB_CORR < -1.0:
        DAYLP = 0.0

    # 计算大气顶层的总辐射量及大气透射率
    ANGOT = SC*DSINB
    # 检查DAYL=0的情况，此时安古特辐射也为0
    if DAYL > 0.0:
        ATMTR = AVRAD/ANGOT
    else:
        ATMTR = 0.

    # 估算散射辐射比例
    if ATMTR > 0.75:
        FRDIF = 0.23
    elif (ATMTR <= 0.75) and (ATMTR > 0.35):
        FRDIF = 1.33-1.46*ATMTR
    elif (ATMTR <= 0.35) and (ATMTR > 0.07):
        FRDIF = 1.-2.3*(ATMTR-0.07)**2
    else:  # ATMTR <= 0.07
        FRDIF = 1.

    DIFPP = FRDIF*ATMTR*0.5*SC

    retvalue = astro_nt(DAYL, DAYLP, SINLD, COSLD, DIFPP, ATMTR, DSINBE, ANGOT)
    _cache[(IDAY, LAT, AVRAD)] = retvalue

    return retvalue


class Afgen(object):
    """模拟WOFOST中的AFGEN函数。

    :param tbl_xy: 包含XY值对的列表或数组，描述该函数
        其中X值应单调递增。

    返回在给定自变量值时的插值结果。

    例子::

        >>> tbl_xy = [0,0,1,1,5,10]
        >>> f =  Afgen(tbl_xy)
        >>> f(0.5)
        0.5
        >>> f(1.5)
        2.125
        >>> f(5)
        10.0
        >>> f(6)
        10.0
        >>> f(-1)
        0.0
    """

    def _check_x_ascending(self, tbl_xy):
        """检查x值是否严格递增。

        同时会截去由于CGMS数据库带来的末尾(0.,0.)对。
        """
        x_list = tbl_xy[0::2]
        y_list = tbl_xy[1::2]
        n = len(x_list)

        # 检查x区间是否连续递增
        rng = list(range(1, n))
        x_asc = [True if (x_list[i] > x_list[i-1]) else False for i in rng]

        # 检查序列中递增被打断的位置。只允许存在0或1处断点。此处使用异或操作'^'
        sum_break = sum([1 if (x0 ^ x1) else 0 for x0,x1 in zip(x_asc, x_asc[1:])])
        if sum_break == 0:
            x = x_list
            y = y_list
        elif sum_break == 1:
            x = [x_list[0]]
            y = [y_list[0]]
            for i,p in zip(rng, x_asc):
                if p is True:
                    x.append(x_list[i])
                    y.append(y_list[i])
        else:
            msg = ("X values for AFGEN input list not strictly ascending: %s"
                   % x_list)
            raise ValueError(msg)

        return x, y

    def __init__(self, tbl_xy):

        x_list, y_list = self._check_x_ascending(tbl_xy)
        x_list = self.x_list = list(map(float, x_list))
        y_list = self.y_list = list(map(float, y_list))
        intervals = list(zip(x_list, x_list[1:], y_list, y_list[1:]))
        self.slopes = [(y2 - y1)/(x2 - x1) for x1, x2, y1, y2 in intervals]

    def __call__(self, x):

        if x <= self.x_list[0]:
            return self.y_list[0]
        if x >= self.x_list[-1]:
            return self.y_list[-1]

        i = bisect_left(self.x_list, x) - 1
        v = self.y_list[i] + self.slopes[i] * (x - self.x_list[i])

        return v


class AfgenTrait(TraitType):
    """AFGEN表特征"""
    default_value = Afgen([0,0,1,1])
    into_text = "An AFGEN table of XY pairs"

    def validate(self, obj, value):
        if isinstance(value, Afgen):
           return value
        elif isinstance(value, Iterable):
           return Afgen(value)
        self.error(obj, value)


def merge_dict(d1, d2, overwrite=False):
    """合并d1和d2的内容并返回合并后的字典

    说明：

    * 输入字典d1和d2不会被修改。
    * 如果`overwrite=False`（默认），当存在重复键时将抛出`RuntimeError`；
      否则，d1中的已存在键在合并时会被d2中的对应键值覆盖。
    """
    # 注意：自python 3.3起，可部分用ChainMap替代
    if overwrite is False:
        sd1 = set(d1.keys())
        sd2 = set(d2.keys())
        intersect = sd1.intersection(sd2)
        if len(intersect) > 0:
            msg = "Dictionaries to merge have overlapping keys: %s"
            raise RuntimeError(msg % intersect)

    td = copy.deepcopy(d1)
    td.update(d2)
    return td


def is_a_month(day):
    """如果给定日期是该月的最后一天则返回True。"""

    if day.month==12:
        if day == datetime.date(day.year, day.month, 31):
            return True
    else:
        if (day == datetime.date(day.year, day.month+1, 1) -
                   datetime.timedelta(days=1)):
            return True
    return False


def is_a_week(day, weekday=0):
    """默认周一为每周的第一天。周一为0，周日为6。"""
    if day.weekday() == weekday:
        return True
    else:
        return False

def is_a_dekad(day):
    """如果日期在旬的边界，例如每月10日、20日或最后一天，则返回True。"""

    if day.month == 12:
        if day == datetime.date(day.year, day.month, 10):
            return True
        elif day == datetime.date(day.year, day.month, 20):
            return True
        elif day == datetime.date(day.year, day.month, 31):
            return True
    else:
        if day == datetime.date(day.year, day.month, 10):
            return True
        elif day == datetime.date(day.year, day.month, 20):
            return True
        elif (day == datetime.date(day.year, day.month+1, 1) -
                     datetime.timedelta(days=1)):
            return True
    return False


def load_SQLite_dump_file(dump_file_name, SQLite_db_name):
    """从转储文件<dump_file_name>建立一个SQLite数据库<SQLite_db_name>。"""

    with open(dump_file_name) as fp:
        sql_dump = fp.readlines()
    str_sql_dump = "".join(sql_dump)
    con = sqlite3.connect(SQLite_db_name)
    con.executescript(str_sql_dump)
    con.close()


def safe_float(x):
    """返回将x转换为float的值，如果失败则返回None。"""
    try:
        return float(x)
    except (ValueError, TypeError):
        return None


def check_date(indate):
        """
        检查日期的表示形式并尝试转换为datetime.date对象。

        支持以下格式：

        1. 一个date对象
        2. 一个datetime对象
        3. 格式为YYYYMMDD的字符串
        4. 格式为YYYYDDD的字符串
        5. 格式为YYYY-MM-DD的字符串
        """

        import datetime as dt
        if isinstance(indate, dt.datetime):
            return indate.date()
        elif isinstance(indate, dt.date):
            return indate
        elif isinstance(indate, str):
            skey = indate.strip()
            l = len(skey)
            if l==8:
                # 假设为YYYYMMDD
                dkey = dt.datetime.strptime(skey,"%Y%m%d")
                return dkey.date()
            elif l==7:
                # 假设为YYYYDDD
                dkey = dt.datetime.strptime(skey,"%Y%j")
                return dkey.date()
            elif l==10:
                # 假设为YYYY-MM-DD
                dkey = dt.datetime.strptime(skey,"%Y-%m-%d")
                return dkey.date()
            else:
                msg = "Input value not recognized as date: %s"
                raise KeyError(msg % indate)
        else:
            msg = "Input value not recognized as date: %s"
            raise KeyError(msg % indate)




def version_tuple(v):
    """
    从版本字符串创建版本元组，以便对版本进行一致比较。

    转换为元组是必要的，因为'2.12.9'比'2.7.8'高，但是::

    >>> '2.12.9' > '2.7.8'
    False

    实际需要的是：

    >>> version_tuple('2.12.9') > version_tuple('2.7.8')
    True
    """
    return tuple(map(int, (v.split("."))))


def get_user_home():
    """
    一个合理的、平台无关的方法用于获取用户主目录。
    如果PCSE运行在系统用户下，则返回tempfile.gettempdir()返回的临时目录。
    """
    user_home = None
    if platform.system() == "Windows":
        user = os.getenv("USERNAME")
        if user is not None:
            user_home = os.path.expanduser("~")
    elif platform.system() == "Linux" or platform.system() == "Darwin":
        user = os.getenv("USER")
        if user is not None:
            user_home = os.path.expanduser("~")
    else:
        msg = "Platform not recognized, using system temp directory for PCSE settings."
        logger = logging.getLogger("pcse")
        logger.warning(msg)

    if user_home is None:
        user_home = tempfile.gettempdir()

    return user_home


class DotMap(dotmap.DotMap):
    """DotMap 子类，默认关闭 _dynamic。
    """
    def __init__(self, *args, **kwargs):
        kwargs.update(_dynamic=False)
        super().__init__(*args, **kwargs)


class DummySoilDataProvider(dict):
    """该类为潜在产量模拟提供一些虚拟的土壤参数。

    潜在产量水平的模拟与土壤无关。但模型仍然需要一些参数值。
    这个数据提供者为这种情况提供一些硬编码的参数值。
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
        print("Using this class from pcse.util is deprecated, use pcse.input.DummySoilDataProvider")
        dict.__init__(self)
        self.update(self._defaults)

    def copy(self):
        """
        重写继承自 dict 的 copy 方法，后者返回一个 dict。
        该方法保留本类及其属性，如 .header。
        """
        return copy.copy(self)