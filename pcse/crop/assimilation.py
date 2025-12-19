# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl) 与 Herman Berghuijs (herman.berghuijs@wur.nl)，2024年1月
"""实现用于PCSE的|CO2|同化的SimulationObjects。
"""
from __future__ import print_function
from math import sqrt, exp, cos, pi
from collections import deque

from ..traitlets import Instance, Float 

from ..util import limit, astro, doy, AfgenTrait
from ..base import ParamTemplate, SimulationObject, RatesTemplate


def totass8(AMAX_LNB, AMAX_REF, AMAX_SLP, DAYL, CO2AMAX, TMPF, EFF, KN, LAI, NLV, KDIF, AVRAD, DIFPP, DSINBE, SINLD, COSLD):
    """ 本过程通过对时间进行高斯积分，计算每日总的冠层CO2总同化量。在一天中的三个不同时刻，计算辐射并用于计算瞬时冠层同化量，之后进行积分。有关此过程的更多信息见Spitters等（1988）。AMAX在assim过程中计算。

    形式参数:  (I=输入, O=输出, C=控制, IN=初始化, T=时间)
    名称        类型    含义                                         单位      类别
    ----        ----    -------                                      -----    -----
    AMAX_LNB   低于该值的比叶氮无净同化                              Cr     |kg ha-1|
    AMAX_REF   参考条件和高比叶氮下的最大叶CO2同化速率               TCr    |kg ha-1 hr-1|
    AMAX_SLP   AMAX对参考条件下比叶氮含量线性反应的斜率               Cr     |kg hr-1 kg-1|
    DAYL       R4      天文日长（基准=0度）                          h         I
    EFF        R4      初始光能利用效率                         kg CO2/J/ha/h m2 s  I
    KN         R4      冠层氮衰减系数                                 -         I
    LAI        R4      叶面积指数                                  ha/ha      I
    KDIF       R4      散射光的衰减系数                                        I
    AVRAD      R4      日总短波辐射                              J m-2 d-1   I
    DIFPP      R4      垂直于光方向的散射辐射                      J m-2 s-1  I
    DSINBE     R4      有效太阳高度的日总和                          s         I
    SINLD      R4      太阳高度正弦的季节偏移                         -         I
    COSLD      R4      太阳高度正弦的振幅                             -         I
    DTGA       R4      日总同化量                              kg CO2/ha/d   O

    ========== ===== =============================================== =============== =====
     名称       类型     含义                                          单位          类别
    ========== ===== =============================================== =============== =====
    AMAX_LNB    Cr    低于该值的比叶氮无净同化                       |kg ha-1|       -
    AMAX_REF    TCr   参考条件和高比叶氮下的最大叶CO2同化速率        |kg ha-1 hr-1|  -
    AMAX_SLP    Cr    AMAX对参考条件下比叶氮含量线性反应的斜率       |kg hr-1 kg-1|  -
    DAYL        R4    天文日长（基准=0度）                               h             I
    EFF         R4    初始光能利用效率                                kg CO2/J/ha/h  I
                                                                        m2 s
    KN          R4    冠层氮衰减系数                                    -             I
    LAI         R4    叶面积指数                                       ha/ha          I
    KDIF        R4    散射光的衰减系数                                                  I
    AVRAD       R4    日总短波辐射                                    J m-2 d-1      I
    DIFPP       R4    垂直于光方向的散射辐射                          J m-2 s-1      I
    DSINBE      R4    有效太阳高度的日总和                             s             I
    SINLD       R4    太阳高度正弦的季节偏移                            -             I
    COSLD       R4    太阳高度正弦的振幅                                -             I
    DTGA        R4    日总同化量                                     kg CO2/ha/d      O
    ========== ===== =============================================== =============== =====

    作者: Daniel van Kraalingen
    日期: 1991年4月

    Python版本:
    作者: Allard de Wit
    日期：2011年9月

    AMAX计算方式更新:
    作者: Herman Berghuijs
    日期: 2024年1月

    """
    # 高斯积分点与权重
    XGAUSS = [0.1127017, 0.5000000, 0.8872983]
    WGAUSS = [0.2777778, 0.4444444, 0.2777778]

    # 仅在同化量不为零时才进行计算
    DTGA = 0.
    if (LAI > 0. and DAYL > 0.):
        for i in range(3):
            HOUR   = 12.0+0.5*DAYL*XGAUSS[i]
            SINB   = max(0.,SINLD+COSLD*cos(2.*pi*(HOUR+12.)/24.))
            PAR    = 0.5*AVRAD*SINB*(1.+0.4*SINB)/DSINBE
            PARDIF = min(PAR,SINB*DIFPP)
            PARDIR = PAR-PARDIF
            FGROS = assim8(AMAX_LNB, AMAX_REF, AMAX_SLP, CO2AMAX, TMPF, EFF, KN, LAI, NLV, KDIF, SINB, PARDIR, PARDIF)
            DTGA += FGROS*WGAUSS[i]
    DTGA *= DAYL

    return DTGA


def assim8(AMAX_LNB, AMAX_REF, AMAX_SLP, CO2AMAX, TMPF, EFF, KN, LAI, NLV, KDIF, SINB, PARDIR, PARDIF):
    """
    本子程序通过在作物冠层深度上执行高斯积分计算作物整体的总CO2同化速率FGROS。
    在冠层的三个不同深度（即不同的LAI值）下，对于给定的光合有效辐射通量，计算同化速率，
    随后对深度积分。更多关于该例程的信息可参考 Spitters 等人 (1988)。
    输入变量 SINB、PARDIR 和 PARDIF 在 TOTASS 例程中计算。AMAX基于比叶氮(SLN)计算。

    调用的子程序与函数: 无。
    调用本例程的函数: TOTASS。

    作者: D.W.G. van Kraalingen, 1986
    更新: H.N.C. Berghuijs, 2024

    Python版本:
    Allard de Wit, 2011
    """

    # 高斯积分点与权重
    XGAUSS = [0.1127017, 0.5000000, 0.8872983]
    WGAUSS = [0.2777778, 0.4444444, 0.2777778]

    SCV = 0.2

    # 13.2 衰减系数 KDIF, KDIRBL, KDIRT
    REFH = (1.-sqrt(1.-SCV))/(1.+sqrt(1.-SCV))
    REFS = REFH*2./(1.+1.6*SINB)
    KDIRBL = (0.5/SINB)*KDIF/(0.8*sqrt(1.-SCV))
    KDIRT = KDIRBL*sqrt(1.-SCV)

    # 13.3 对LAI做三点高斯积分
    FGROS = 0.
    for i in range(3):
        LAIC = LAI*XGAUSS[i]

        # 冠层内梯度计算AMAX (ORYZA方法)
        if(LAI >= 0.01):
            SLN = NLV * KN * exp(-KN * LAIC) / (1 - exp(-KN * LAI))
        else:
            SLN = NLV/LAI

        AMAX =  CO2AMAX * TMPF * min(AMAX_REF , max(0, AMAX_SLP * (SLN - AMAX_LNB)))

        # 各层吸收的散射辐射(VISDF)、来自直射光的透射(VIST)和直射辐射(VISD)
        VISDF  = (1.-REFS)*PARDIF*KDIF  *exp(-KDIF  *LAIC)
        VIST   = (1.-REFS)*PARDIR*KDIRT *exp(-KDIRT *LAIC)
        VISD   = (1.-SCV) *PARDIR*KDIRBL*exp(-KDIRBL*LAIC)

        # 阴影叶片吸收的通量 (W/m2) 及其同化量
        VISSHD = VISDF+VIST-VISD
        FGRSH  = AMAX*(1.-exp(-VISSHD*EFF/max(2.0, AMAX)))

        # 直射光下与太阳直射光垂直的叶片所吸收的光及阳光区叶面积同化量
        VISPP  = (1.-SCV)*PARDIR/SINB
        if (VISPP <= 0.):
            FGRSUN = FGRSH
        else:
            FGRSUN = AMAX*(1.-(AMAX-FGRSH) \
                     *(1.-exp(-VISPP*EFF/max(2.0,AMAX)))/ (EFF*VISPP))

        # 阳光区叶面积分数(FSLLA)及局部同化速率(FGL)
        FSLLA  = exp(-KDIRBL*LAIC)
        FGL    = FSLLA*FGRSUN+(1.-FSLLA)*FGRSH

        # 积分
        FGROS += FGL*WGAUSS[i]

    FGROS  = FGROS*LAI
    return FGROS

class WOFOST81_Assimilation(SimulationObject):
    """实现WOFOST/SUCROS风格同化过程的类，包括对大气CO2浓度变化以及叶片含氮量对最大同化速率影响的考虑。

    WOFOST 通过作物吸收的辐射量和单叶片的光合作用-光响应曲线计算作物的日总|CO2|同化速率。该响应依赖于温度和叶片年龄。吸收的辐射量由总入射辐射和叶面积计算得出。日总|CO2|同化速率通过对叶层和全天的同化速率积分获得。

    *模拟参数* （需在cropdata字典中提供）:

    =========  ============================================= =======  ============
     名称        描述                                         类型      单位
    =========  ============================================= =======  ============
    AMAX_LNB   低于该值时没有总光合的单位叶氮含量              Cr      |kg ha-1|
    AMAX_REF   参考条件下且单位叶氮含量高时叶CO2最大同化速率     TCr     |kg ha-1 hr-1|
    AMAX_SLP   参考条件下AMAX与单位叶氮含量线性响应的斜率        Cr      |kg hr-1 kg-1|
    KN         冠层中氮的衰减系数                             Cr       -
    EFFTB      单叶片光能利用效率, 随日均温的函数               TCr     |kg ha-1 hr-1 /(J m-2 s-1)|
    KDIFTB     散射可见光衰减系数，随DVS的函数                  TCr      -
    TMPFTB     AMAX随日均温的降低因子                           TCr      -
    TMPFTB     AMAX随日最低温度的降低因子                       TCr      -
    CO2AMAXTB  大气CO2浓度对AMAX的校正因子                      TCr      -
    CO2EFFTB   大气CO2浓度对EFF的校正因子                       TCr      -
    CO2        大气CO2浓度                                      SCr      ppm
    =========  ============================================= =======  ============

    *状态变量与速率变量*

    `WOFOST_Assimilation` 不包含状态或速率变量，但计算的同化速率将直接由 `__call__()` 方法返回。

    *传递或处理的信号*

    无

    *外部依赖:*

    =======  ============================ ================  ============
     名称      描述                         提供模块           单位
    =======  ============================ ================  ============
    DVS      作物发育阶段                   DVS_Phenology     -
    LAI      叶面积指数                     leaf_dynamics     -
    NLV      叶片氮含量                     n_dynamics        |kg ha-1|
    =======  ============================ ================  ============
    """

    _TMNSAV = Instance(deque)

    class Parameters(ParamTemplate):
        AMAX_LNB = Float(-99.)
        AMAX_REF = Float(-99.)
        AMAX_SLP = Float(-99.)
        EFFTB = AfgenTrait()
        KDIFTB = AfgenTrait()
        TMPFTB = AfgenTrait()
        TMNFTB = AfgenTrait()
        CO2AMAXTB = AfgenTrait()
        CO2EFFTB = AfgenTrait()
        CO2 = Float(-99.)
        KN = Float()

    def initialize(self, day, kiosk, cropdata):
        """
        :param day: 模拟起始日期
        :param kiosk: 此Engine实例的kiosk变量
        :param cropdata: 包含作物数据键值对的字典
        :returns: 使用__call__()方法返回同化速率
        """

        self.params = self.Parameters(cropdata)
        self.kiosk = kiosk
        self._TMNSAV = deque(maxlen=7)

    def __call__(self, day, drv):
        p = self.params
        k = self.kiosk

        # 从kiosk中获取发布的状态变量
        DVS = k.DVS
        LAI = k.LAI
        NLV = k.NamountLV

        # 最低气温的7天滑动平均值
        self._TMNSAV.appendleft(drv.TMIN)
        TMINRA = sum(self._TMNSAV)/len(self._TMNSAV)

        # 2.19 光周期天长
        DAYL, DAYLP, SINLD, COSLD, DIFPP, ATMTR, DSINBE, ANGOT = astro(day, drv.LAT, drv.IRRAD)

        # 日干物质生产

        # 计算AMAX的CO2和温度响应因子
        CO2AMAX = p.CO2AMAXTB(p.CO2)
        TMPF = p.TMPFTB(drv.TEMP)

        # 总光合速率及对亚最优日均温度和CO2浓度的修正
        KDIF = p.KDIFTB(DVS)
        CO2EFFTB = p.CO2EFFTB(p.CO2)        
        EFF  = p.EFFTB(drv.DTEMP) * CO2EFFTB

        DTGA = totass8(p.AMAX_LNB, p.AMAX_REF, p.AMAX_SLP, DAYL, CO2AMAX, TMPF, EFF, p.KN, LAI, NLV, KDIF, drv.IRRAD, DIFPP, DSINBE, SINLD, COSLD)

        # 对于低最低气温的修正
        DTGA *= p.TMNFTB(TMINRA)

        # 以kg CH2O/公顷为单位的同化量
        PGASS = DTGA * 30./44.

        return PGASS

def totass7(DAYL, AMAX, EFF, LAI, KDIF, AVRAD, DIFPP, DSINBE, SINLD, COSLD):
    """
    本过程通过对时间进行高斯积分，计算每日总的总CO2同化量。在一天内三个不同时点计算辐射，并用于计算瞬时冠层同化量，随后进行积分。有关本过程的更多信息见Spitters等人（1988）。
    形式参数:（I=输入，O=输出，C=控制，IN=初始化，T=时间）
    名称     类型    含义                                单位         类别
    ----     ----    ----                                ----         ----
    DAYL     R4      天文日长（基准=0度）                小时          I
    AMAX     R4      光饱和下同化速率                  kg CO2/ha叶/小时 I
    EFF      R4      初始光能利用效率                  kg CO2/J/ha/h m2 s I
    LAI      R4      叶面积指数                        ha/ha          I
    KDIF     R4      散射光的消光系数                                  I
    AVRAD    R4      日短波辐射                         J m-2 d-1     I
    DIFPP    R4      垂直于光方向的散射辐射量           J m-2 s-1     I
    DSINBE   R4      有效太阳高度的日总和                 s            I
    SINLD    R4      太阳高度正弦的季节偏移量             -            I
    COSLD    R4      太阳高度正弦的振幅                   -            I
    DTGA     R4      每日总总同化量                 kg CO2/ha/d      O
    作者: Daniel van Kraalingen
    日期: 1991年4月
    Python版本:
    作者: Allard de Wit
    日期: 2011年9月
    """

    # 高斯积分点和权重
    XGAUSS = [0.1127017, 0.5000000, 0.8872983]
    WGAUSS = [0.2777778, 0.4444444, 0.2777778]

    # 只有在同化量不为零时计算（即AMAX > 0，LAI > 0，DAYL > 0）
    DTGA = 0.
    if (AMAX > 0. and LAI > 0. and DAYL > 0.):
        for i in range(3):
            HOUR   = 12.0+0.5*DAYL*XGAUSS[i]
            SINB   = max(0.,SINLD+COSLD*cos(2.*pi*(HOUR+12.)/24.))
            PAR    = 0.5*AVRAD*SINB*(1.+0.4*SINB)/DSINBE
            PARDIF = min(PAR,SINB*DIFPP)
            PARDIR = PAR-PARDIF
            FGROS = assim7(AMAX,EFF,LAI,KDIF,SINB,PARDIR,PARDIF)
            DTGA += FGROS*WGAUSS[i]
    DTGA *= DAYL

    return DTGA


def assim7(AMAX, EFF, LAI, KDIF, SINB, PARDIR, PARDIF):
    """
    本过程通过对冠层深度进行高斯积分，计算整个作物的总CO2同化速率FGROS。在冠层内三个不同深度（即LAI的不同取值）处，计算给定光合有效辐射通量下的同化速率，并进行深度整合。有关本过程的更多信息见Spitters等人（1988）。输入变量SINB、PARDIR和PARDIF由TOTASS过程计算。
    调用的子程序和函数：无。
    被TOTASS过程调用。
    作者：D.W.G. van Kraalingen, 1986
    Python版本：
    Allard de Wit, 2011
    """
    # 高斯积分点和权重
    XGAUSS = [0.1127017, 0.5000000, 0.8872983]
    WGAUSS = [0.2777778, 0.4444444, 0.2777778]

    SCV = 0.2

    # 13.2 消光系数 KDIF, KDIRBL, KDIRT
    REFH = (1.-sqrt(1.-SCV))/(1.+sqrt(1.-SCV))
    REFS = REFH*2./(1.+1.6*SINB)
    KDIRBL = (0.5/SINB)*KDIF/(0.8*sqrt(1.-SCV))
    KDIRT = KDIRBL*sqrt(1.-SCV)

    # 13.3 LAI三点高斯积分
    FGROS = 0.
    for i in range(3):
        LAIC = LAI*XGAUSS[i]
        # 吸收的散射辐射 (VISDF)、来自直射源的光 (VIST) 和直射光 (VISD)
        VISDF  = (1.-REFS)*PARDIF*KDIF  *exp(-KDIF  *LAIC)
        VIST   = (1.-REFS)*PARDIR*KDIRT *exp(-KDIRT *LAIC)
        VISD   = (1.-SCV) *PARDIR*KDIRBL*exp(-KDIRBL*LAIC)

        # 阴蔽叶片吸收的通量 (W/m2) 及其同化量
        VISSHD = VISDF+VIST-VISD
        FGRSH  = AMAX*(1.-exp(-VISSHD*EFF/max(2.0, AMAX)))

        # 与直射光垂直的叶片吸收直射光及阳照叶面积同化
        VISPP  = (1.-SCV)*PARDIR/SINB
        if (VISPP <= 0.):
            FGRSUN = FGRSH
        else:
            FGRSUN = AMAX*(1.-(AMAX-FGRSH) \
                     *(1.-exp(-VISPP*EFF/max(2.0,AMAX)))/ (EFF*VISPP))

        # 阳照叶面积比例 (FSLLA) 及局部同化速率 (FGL)
        FSLLA  = exp(-KDIRBL*LAIC)
        FGL    = FSLLA*FGRSUN+(1.-FSLLA)*FGRSH

        # 积分
        FGROS += FGL*WGAUSS[i]

    FGROS  = FGROS*LAI
    return FGROS


class WOFOST72_Assimilation(SimulationObject):
    """实现WOFOST/SUCROS型同化例程的类。
    
    WOFOST通过吸收的辐射和单个叶片的光合作用-光响应曲线，计算作物的日总|CO2|同化速率。该响应取决于温度和叶龄。吸收的辐射量由总入射辐射和叶面积计算得出。日总|CO2|同化量通过对叶层和一天内的同化速率积分获得。
      
    *模拟参数*
    
    =======  ============================================= =======  ============
     名称      描述                                         类型      单位
    =======  ============================================= =======  ============
    AMAXTB   叶片最大|CO2|同化速率，DVS的函数                TCr     |kg ha-1 hr-1|
             关于DVS
    EFFTB    单叶光能利用效率，日均温度的函数                TCr     |kg ha-1 hr-1 /(J m-2 s-1)|
             关于日平均温度                                   
    KDIFTB   散射可见光的消光系数，DVS的函数                 TCr      -
             关于DVS
    TMPFTB   AMAX关于日均温度的修正因子                      TCr      -
             关于日平均温度
    TMNFTB   AMAX关于日最低温度的修正因子                    TCr      -
             关于日最低温度
    =======  ============================================= =======  ============
    
    *状态和速率变量*
    
    `WOFOST_Assimilation` 通过 `__call__()` 方法直接返回潜在总同化速率 'PGASS'，但也作为速率变量包含在内。

     **速率变量:**
    
    =======  ================================================ ==== =============
     名称      描述                                           公有      单位
    =======  ================================================ ==== =============
    PGASS    潜在同化速率                                     N    |kg CH2O ha-1 d-1|
    =======  ================================================ ==== =============
    
    *发送或处理的信号*
    
    无
        
    
    *外部依赖项:*
    
    =======  ================================ =================  ============
     名称      描述                              提供者               单位
    =======  ================================ =================  ============
    DVS      作物发育阶段                        DVS_Phenology          -
    LAI      叶面积指数                          Leaf_dynamics          -
    =======  ================================ =================  ============
    """

    _TMNSAV = Instance(deque)

    class Parameters(ParamTemplate):
        AMAXTB = AfgenTrait()
        EFFTB  = AfgenTrait()
        KDIFTB = AfgenTrait()
        TMPFTB = AfgenTrait()
        TMNFTB = AfgenTrait()

    class RateVariables(RatesTemplate):
        PGASS = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟开始日期
        :param kiosk: 当前PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，以键/值对的形式提供参数
        :returns: 使用__call__()返回的同化速率，单位：|kg ha-1 d-1|
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk
        self._TMNSAV = deque(maxlen=7)
    
    def __call__(self, day, drv):
        p = self.params
        k = self.kiosk

        # TMIN的7天滑动平均
        self._TMNSAV.appendleft(drv.TMIN)
        TMINRA = sum(self._TMNSAV)/len(self._TMNSAV)

        # 光周期日长度
        DAYL, DAYLP, SINLD, COSLD, DIFPP, ATMTR, DSINBE, ANGOT = astro(day, drv.LAT, drv.IRRAD)

        # 总同化速率及对日平均温度不理想情况的修正
        AMAX = p.AMAXTB(k.DVS)
        AMAX *= p.TMPFTB(drv.DTEMP)
        KDIF = p.KDIFTB(k.DVS)
        EFF = p.EFFTB(drv.DTEMP)
        DTGA = totass7(DAYL, AMAX, EFF, k.LAI, KDIF, drv.IRRAD, DIFPP, DSINBE, SINLD, COSLD)

        # 对最低温度抑制潜力的修正
        DTGA *= p.TMNFTB(TMINRA)

        # 按kg CH2O/ha单位的同化量
        PGASS = DTGA * 30./44.
        
        return PGASS


class WOFOST73_Assimilation(SimulationObject):
    """实现WOFOST/SUCROS同化例程，并包含大气CO2变化影响的类。

    WOFOST根据被吸收的辐射和单叶片的光合作用-光响应曲线，计算作物的日总|CO2|同化速率。
    该响应取决于温度和叶龄。吸收的辐射通过总入射辐射和叶面积计算获得。日总|CO2|同化量通过对叶层和一天内的同化速率积分得到。

    大气|CO2|的影响通过对每一发育阶段的AMAX（参数CO2AMAXTB）和EFF（参数CO2EFFTB）施加经验修正实现。后两者都作为大气|CO2|浓度的函数定义。

    *模拟参数* （需在cropdata字典中提供）:

    =========  ============================================= =======  ============
     名称       描述                                          类型     单位
    =========  ============================================= =======  ============
    AMAXTB     单叶最大|CO2|同化速率，DVS的函数                TCr     |kg ha-1 hr-1|
               关于DVS
    EFFTB      单叶光能利用效率，日均温度的函数                TCr     |kg ha-1 hr-1 /(J m-2 s-1)|
               关于日平均温度
    KDIFTB     散射可见光的消光系数，DVS的函数                 TCr      -
               关于DVS
    TMPFTB     AMAX关于日均温度的修正因子                      TCr      -
               关于日平均温度
    TMPFTB     AMAX关于日最低温度的修正因子                    TCr      -
               关于日最低温度
    CO2AMAXTB  CO2浓度下AMAX的修正因子                        TCr      -
    CO2EFFTB   CO2浓度下EFF的修正因子                         TCr      -
    CO2        大气CO2浓度                                    SCr      ppm
    =========  ============================================= =======  ============

    *状态和速率变量*

    `WOFOST_Assimilation2` 没有状态/速率变量，但计算的同化速率直接由 `__call__()` 方法返回。

    *发送或处理的信号*

    无

    *外部依赖项:*

    =======  =================================== =================  ============
     名称     描述                                 提供者            单位
    =======  =================================== =================  ============
    DVS      作物发育阶段                         DVS_Phenology       -
    LAI      叶面积指数                           Leaf_dynamics       -
    =======  =================================== =================  ============
    """

    _TMNSAV = Instance(deque)

    class Parameters(ParamTemplate):
        AMAXTB = AfgenTrait()
        EFFTB = AfgenTrait()
        KDIFTB = AfgenTrait()
        TMPFTB = AfgenTrait()
        TMNFTB = AfgenTrait()
        CO2AMAXTB = AfgenTrait()
        CO2EFFTB = AfgenTrait()
        CO2 = Float(-99.)

    def initialize(self, day, kiosk, cropdata):
        """
        :param day: 模拟起始日期
        :param kiosk: 本Engine实例中的变量kiosk
        :param cropdata: 包含cropdata键/值对的字典
        :returns: 通过__call__()方法返回的同化速率
        """

        self.params = self.Parameters(cropdata)
        self.kiosk = kiosk
        self._TMNSAV = deque(maxlen=7)

    def __call__(self, day, drv):
        p = self.params
        k = self.kiosk

        # 从kiosk获取发布的状态量
        DVS = k.DVS
        LAI = k.LAI

        # 7天TMIN滑动平均
        self._TMNSAV.appendleft(drv.TMIN)
        TMINRA = sum(self._TMNSAV)/len(self._TMNSAV)

        # 2.19  光周期日长度
        DAYL, DAYLP, SINLD, COSLD, DIFPP, ATMTR, DSINBE, ANGOT = astro(day, drv.LAT, drv.IRRAD)

        # 日干物质生产量

        # 总同化及针对亚最优日平均温度和CO2浓度的修正
        AMAX = p.AMAXTB(DVS) * p.CO2AMAXTB(p.CO2)
        AMAX *= p.TMPFTB(drv.DTEMP)
        KDIF = p.KDIFTB(DVS)
        EFF  = p.EFFTB(drv.DTEMP) * p.CO2EFFTB(p.CO2)
        DTGA = totass7(DAYL, AMAX, EFF, LAI, KDIF, drv.IRRAD, DIFPP, DSINBE, SINLD, COSLD)

        # 针对低最低温度潜力的修正
        DTGA *= p.TMNFTB(TMINRA)

        # 以kg CH2O/ha计的同化量
        PGASS = DTGA * 30./44.

        return PGASS