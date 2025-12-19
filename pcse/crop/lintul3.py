# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 瓦赫宁根环境研究中心，瓦赫宁根大学和研究中心
# Wim de Winter(Wim.deWinter@wur.nl)，2015年4月
"""
LINTUL3
"""
from math import exp

from ..base import SimulationObject, ParamTemplate, RatesTemplate
from ..base import StatesWithImplicitRatesTemplate as StateVariables
from ..traitlets import Float, Instance, Bool
from ..decorators import prepare_rates, prepare_states
from ..util import limit, AfgenTrait
from ..crop.phenology import DVS_Phenology as Phenology
from ..exceptions import CarbonBalanceError, NutrientBalanceError
from .. import signals

# 一些lambda函数用于明确单位换算。
cm2mm = lambda x: x*10.
joule2megajoule = lambda x: x/1e6
m2mm = lambda x: x*1000

class Lintul3(SimulationObject):
    """
    LINTUL3 是一个作物模型, 其通过作物拦截的光合有效辐射(PAR)与光能利用率(LUE)来计算生物量生产。该模型是在 LINTUL2 (用于模拟潜在和水分受限的作物生长)的基础上进行修改，加入了氮素限制。模型中氮胁迫通过氮营养指数(NNI)来定义：即作物实际氮浓度与临界氮浓度的比值。模型通过降低 LUE、减少叶面积(LA)，或上述两者组合的方式，来模拟氮胁迫对作物生长的影响，并以独立的数据集进行评估。不过，因为研究对象为水稻，本研究未考虑水分受限因素。本文针对水稻情境描述模型、检验氮胁迫影响生长的假设，并详细介绍模型校准以及在亚洲多变环境下不同氮肥水平(0-400 kgNha-1)独立数据集上的测试。校准和测试结果通过图形、均方根偏差(RMSD)和平均绝对偏差(AAD)进行对比。总体而言，总地上部生物量校准和测试的平均绝对偏差低于26%，但个别实验最高可达41%。总体来看，模型能够较好地反映未施肥处理下的氮胁迫现象，但在施肥处理之间响应有所不同。

    **氮需求、吸收与胁迫**

    当土壤中氮素供应低于最优水平时，作物氮需求无法满足，从而导致作物氮浓度低于最优水平。作物氮浓度低于临界值时即发生氮胁迫。氮胁迫会降低生物量生产速率，最终降低产量。实际的氮含量指的是超出残留氮(细胞结构组成部分)的氮素累积量。临界氮含量是最大值的一半。这三个基准点的氮素含量均包含叶片和茎秆的氮素，而不包括根系，这是因为地上绿色部分(含叶绿素)对于光合作用更为重要。但在计算氮需求和吸收量时，地下部分同样计入。

    参考文献：
    M.E. Shibu, P.A. Leffelaar, H. van Keulena, P.K. Aggarwal (2010). LINTUL3,
    a simulation model for nitrogen-limited situations: application to rice.
    Eur. J. Agron. (2010) http://dx.doi.org/10.1016/j.eja.2010.01.003


    *参数说明*

    ======== ================================================  =====
     名称      说明                                             单位
    ======== ================================================  =====
    DVSI     初始生育进程(DVS)                                   -
    DVSDR    叶和根开始死亡的生育进程阈值                         -
    DVSNLT   超过该发育阶段后不再吸收养分                         -
    DVSNT    氮素向贮藏器官转运开始的发育阶段                     -
    FNTRT    从根向贮藏器官转运的氮占从叶和茎到
             贮藏器官氮转移总量的比例                             -
    FRNX     临界氮浓度为最大氮浓度的比例                         -
    K        光衰减系数                                         m²/m²
    LAICR    临界叶面积指数，超出后叶片发生相互遮荫，             °C/d
    LRNR     根的最大氮浓度为叶的比例                            g/g
    LSNR     茎的最大氮浓度为叶的比例                            g/g
    LUE      光能利用率                                          g/MJ
    NLAI     氮胁迫对叶面积指数下降的系数(苗期)                   -
    NLUE     氮胁迫下LUE降低系数                                 -
    NMAXSO   贮藏器官氮浓度最大值                                g/g
    NPART    氮胁迫对叶生物量降低的系数                          -
    NSLA     氮胁迫下SLA减少的系数                               -
    RDRNS    氮胁迫导致叶干重死亡的相对死亡速率                  1/d
    RDRRT    根的相对死亡速率                                    1/d
    RDRSHM   遮阴导致叶片最大死亡速率                            1/d
    RGRL     叶面积指数在指数生长期的相对生长速率                 °C/d
    RNFLV    叶片残留氮浓度                                     g/g
    RNFRT    根的残留氮浓度                                     g/g
    RNFST    茎的残留氮浓度                                     g/g
    ROOTDM   最大根系深度                                        m
    RRDMAX   根系最大生长速率                                    m/d
    SLAC     比叶面积常数                                        m²/g
    TBASE    作物发育基温                                        °C
    TCNT     氮转运时间系数                                      d
    TRANCO   蒸腾常数，表示作物耐旱水平                          mm/d
    TSUMAG   叶片衰老的温度积                                    °C.d
    WCFC     田间持水量(0.03 MPa)                                m³/m³
    WCST     全部饱和时的含水量                                  m³/m³
    WCWET    缺氧胁迫临界含水量                                  m³/m³
    WCWP     萎蔫点含水量(1.5 MPa)                               m³/m³
    WMFAC    水分管理(False =灌溉至田间持水量, True=灌至饱和)     (bool)
    RNSOIL   土壤有机质矿化每天能提供的氮量
    ======== ================================================  =====


    *表格参数*

    ======== ================================================= ======================
     名称     说明                                             单位
    ======== ================================================= ======================
    FLVTB    生物量分配系数                                     -
    FRTTB    生物量分配系数                                     -
    FSOTB    生物量分配系数                                     -
    FSTTB    生物量分配系数                                     -
    NMXLV    叶片最大氮浓度(随发育进程变化),                   kg N kg-1干物质
             据其推导茎和根,单位为干物质
    RDRT     叶片相对死亡速率(随发育进程变化)                   1/d
    SLACF    叶面积修正函数，随发育进程(DVS)变化。              -
             参考: Drenth, H., ten Berge, H.F.M.               
             and Riethoven, J.J.M. 1994, p.10.                 
             (完整参考见Observed data.)
    ======== ================================================= ======================

    *初始状态*

    ======== ================================================  =====
     名称      说明                                             单位
    ======== ================================================  =====
    ROOTDI   初始根系深度                                        m
    NFRLVI   叶片初始氮含量分数                                  gN/gDM
    NFRRTI   根初始氮含量分数                                    gN/gDM
    NFRSTI   茎初始氮含量分数                                    gN/gDM
    WCI      初始土壤含水量                                      m³/³
    WLVGI    绿色叶片初始质量                                    g/m²
    WSTI     茎初始质量                                          g/m²
    WRTLI    根初始质量                                          g/m²
    WSOI     贮藏器官初始质量                                    g/m²
    ======== ================================================  =====


    **状态变量:**

    =========== ===================================== ==== ===========
     名称         说明                                Pbl    单位
    =========== ===================================== ==== ===========
    ANLV        叶片实际氮含量
    ANRT        根实际氮含量
    ANSO        贮藏器官实际氮含量
    ANST        茎实际氮含量
    CUMPAR      PAR累计值
    LAI         叶面积指数                            *      m²/m²
    NLOSSL      叶片累计氮损失
    NLOSSR      根累计氮损失
    NUPTT       总氮素吸收量                                  gN/m²
    ROOTD       根系深度                              *       m
    TNSOIL      可被作物吸收的土壤无机氮量
    WDRT        死根(?)                                         g/m²
    WLVD        死叶量                                          g/m²
    WLVG        绿色叶片质量                                    g/m²
    WRT         根质量                                          g/m²
    WSO         贮藏器官质量                                    g/m²
    WST         茎质量                                          g/m²
    TAGBM       地上部总生物量                                  g/m²
    TGROWTH     总生物量增长(地上+地下)                         g/m²
    =========== ===================================== ==== ===========

    **生长速率变量:**

    =========== ========================================= ==== ===============
     名称         说明                                    Pbl    单位
    =========== ========================================= ==== ===============
     PEVAP       潜在土壤蒸发速率                          Y   |mmday-1|
     PTRAN       潜在作物蒸腾速率                          Y   |mmday-1|
     TRAN        实际作物蒸腾速率                          N   |mmday-1|
     TRANRF      蒸腾抑制因子(计算值)                      N   -
     RROOTD      根生长速率                                Y   |mday-1|
    =========== ========================================= ==== ===============
    """


    # 作物模拟的子模块组件
    pheno = Instance(SimulationObject)
    # 用于存放 _on_APPLY_N 事件处理函数中实际施氮速率的占位符
    FERTNS = 0.0
    # 叶面积指数初值占位符
    LAII = 0.
    # 绿色叶片、茎、根和贮藏器官初始氮含量的占位符
    ANLVI = 0.
    ANSTI = 0.
    ANRTI = 0.
    ANSOI = 0.

    # 主要作物模拟层面相关的参数、速率和状态
    class Parameters(ParamTemplate):
        DVSI   = Float(-99.)   # 作物初始发育阶段
        DVSDR  = Float(-99)    # 叶片和根开始死亡的发育阶段
        DVSNLT = Float(-99)    # N极限发育阶段
        DVSNT  = Float(-99)    # N阈值发育阶段
        FNTRT  = Float(-99)    # 根系N转运量占叶片和茎总N转运量的比例
        FRNX   = Float(-99)    # 最佳N浓度/最大N浓度
        K      = Float(-99)    # 光衰减系数
        LAICR  = Float(-99)    # 临界叶面积指数（遮荫发生的LAI），单位(℃·d)-1
        LRNR   = Float(-99)    # 
        LSNR   = Float(-99)    # 
        LUE    = Float(-99)    # 光能利用率
        NLAI   = Float(-99)    # N胁迫期对LAI减少的系数（苗期）
        NLUE   = Float(-99)    # N沿冠层分布的消光系数
        NMAXSO = Float(-99)    # 
        NPART  = Float(-99)    # N胁迫对叶片生物量减少的系数
        NSLA   = Float(-99)    # N胁迫对比叶面积（SLA）减少的系数
        RDRSHM = Float(-99)    # 遮荫导致叶片最大相对死亡率
        RGRL   = Float(-99)    # 指数生长期叶面积总相对增长率
        RNFLV  = Float(-99)    # 叶片剩余N浓度
        RNFRT  = Float(-99)    # 根剩余N浓度
        RNFST  = Float(-99)    # 茎剩余N浓度
        ROOTDM = Float(-99)    # 水稻最大根深
        RRDMAX = Float(-99)    # 水稻根系生长深度最大日增长速率（m d-1）
        SLAC   = Float(-99)    # 比叶面积常数
        TBASE  = Float(-99)    # 春小麦基温
        TCNT   = Float(-99)    # N转运时间系数（天）
        TRANCO = Float(-99)    # 蒸腾常数（mm/day），表示小麦耐旱性水平
        TSUMAG = Float(-99)    # 叶片衰老的温度积
        WCFC   = Float(-99)    # 田间持水量下的土壤含水量（0.03 MPa）m3/m3
        WCI    = Float(-99)    # 初始土壤含水量（cm3水/cm3土壤）
        WCST   = Float(-99)    # 土壤完全饱和时的含水量 m3/m3
        WCWET  = Float(-99)    # 氧气胁迫临界含水量 [m3/m3]
        WCWP   = Float(-99)    # 凋萎点含水量（1.5MPa）m3/m3
        WMFAC  = Bool(False)    # 水分管理（0=灌溉到田间持水量，1=灌溉至饱和）
        RDRNS  = Float(-99)    # N胁迫导致叶片死亡的相对速率
        RDRRT  = Float(-99)    # 根相对死亡率
        RDRRT  = Float(-99)    # 根相对死亡率        

        FLVTB  = AfgenTrait()  # 分配系数
        FRTTB  = AfgenTrait()  # 分配系数
        FSOTB  = AfgenTrait()  # 分配系数
        FSTTB  = AfgenTrait()  # 分配系数
        NMXLV  = AfgenTrait()  # 叶片最大N浓度（随发育阶段变化）
        RDRT   = AfgenTrait()  # 
        SLACF  = AfgenTrait()  # 随发育阶段DVS变化的叶面积修正函数

        ROOTDI = Float(-99)   # 根系初始深度[m]
        NFRLVI = Float(-99)   # 叶片初始N分数(g N/g干重)
        NFRRTI = Float(-99)   # 根初始N分数(g N/g干重)
        NFRSTI = Float(-99)   # 茎初始N分数(g N/g干重)
        WLVGI  = Float(-99)   # 绿色叶片初始质量
        WSTI   = Float(-99)   # 茎初始质量
        WRTLI  = Float(-99)   # 根初始质量
        WSOI   = Float(-99)   # 贮藏器官初始质量

        RNMIN = Float(-99)    # 土壤矿化速率 (g N/m2/天)
        
    class Lintul3States(StateVariables):
        LAI = Float(-99.) # 叶面积指数
        ANLV = Float(-99.) # 叶片实际氮含量
        ANST = Float(-99.) # 茎实际氮含量
        ANRT = Float(-99.) # 根实际氮含量
        ANSO = Float(-99.) # 贮藏器官实际氮含量
        NUPTT = Float(-99.) # 一段时间内累计氮摄取量 (g N m-2)
        NLOSSL = Float(-99.) # 叶片氮损失总量
        NLOSSR = Float(-99.) # 根氮损失总量
        WLVG  = Float(-99.) # 绿色叶片质量
        WLVD  = Float(-99.) # 死叶质量
        WST = Float(-99.) # 茎质量
        WSO = Float(-99.) # 贮藏器官质量
        WRT = Float(-99.) # 根质量
        ROOTD = Float(-99.) # 实际根深 [m]
        TGROWTH = Float(-99.) # 总生长量
        WDRT = Float(-99.) # 死根质量
        CUMPAR = Float(-99.) # 积累的光合有效辐射量
        TNSOIL = Float(-99.) # 作物可吸收的无机氮含量
        TAGBM = Float(-99.) # 地上部分总生物量 [g/m-2]
        NNI = Float(-99) # 氮营养指数

    # 这些速率（PEVAP，TRAN）并未直接与状态变量相连，但需发布（RROOTD）以供水分平衡模块使用。因此，我们在此显式定义它们。
    class Lintul3Rates(RatesTemplate):
        PEVAP = Float()
        PTRAN = Float()
        TRAN = Float()
        TRANRF = Float()
        RROOTD = Float()


    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟起始日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parvalues: 提供键值参数对的`ParameterProvider`对象
        """
        self.kiosk = kiosk
        self.params = self.Parameters(parvalues)
        self.rates = self.Lintul3Rates(self.kiosk,
                                       publish=["PEVAP", "TRAN", "RROOTD"])

        self._connect_signal(self._on_APPLY_N, signals.apply_n)

        # 初始化作物物候模块
        self.pheno = Phenology(day, kiosk, parvalues)

        # 计算初始叶面积指数（LAI）
        p = self.params
        SLACFI = p.SLACF(p.DVSI)
        ISLA = p.SLAC * SLACFI
        self.LAII = p.WLVGI * ISLA

        # 叶片、茎、根和贮藏器官的初始氮含量 (g/m2)
        self.ANLVI = p.NFRLVI * p.WLVGI
        self.ANSTI = p.NFRSTI * p.WSTI
        self.ANRTI = p.NFRRTI * p.WRTLI
        self.ANSOI = 0.0

        # 生成包含“默认”初始状态（例如为零）的字典
        init = self.Lintul3States.initialValues()

        # 初始化状态变量
        init["LAI"] = self.LAII
        init["ANLV"] = self.ANLVI
        init["ANST"] = self.ANSTI
        init["ANRT"] = self.ANRTI
        init["WLVG"] = p.WLVGI
        init["WST"] = p.WSTI
        init["WSO"] = p.WSOI
        init["WRT"] = p.WRTLI
        init["ROOTD"] = p.ROOTDI

        # 初始化状态对象
        self.states = self.Lintul3States(kiosk, publish=["LAI", "ROOTD"], **init)
        # 初始化与状态变量相关的速率
        self.states.initialize_rates()

    def _on_APPLY_N(self, amount, recovery):
        """接收氮肥施用信号，amount为施加的氮素（g N m-2），recovery为回收系数。"""
        self.FERTNS = amount * recovery

    @prepare_rates
    def calc_rates(self, day, drv):

        p = self.params
        s = self.states
        r = self.rates

        DELT    = 1

        DVS     = self.pheno.get_variable("DVS")
        TSUM    = self.pheno.get_variable("TSUM")

        DTR     = joule2megajoule(drv.IRRAD)
        PAR     = DTR * 0.50
        DAVTMP  = 0.5 * (drv.TMIN + drv.TMAX)
        DTEFF   = max(0., DAVTMP - p.TBASE)
        
        # 潜在蒸发和蒸腾速率:
        r.PEVAP, r.PTRAN = self._calc_potential_evapotranspiration(drv)

        # 根区的含水量
        WC = self.kiosk["WC"]

        # 实际蒸腾速率:
        r.TRAN = self._calc_actual_transpiration(r.PTRAN, WC)

        """
        作物物候

        作物生长发育（即营养器官和生殖器官出现的顺序和速率）是以物候发育阶段（DVS）作为热积之函数进行定义的，其中热积是累计日有效温度。日有效温度为作物平均温度高于作物特定基温（如水稻为8°C）的部分。有些作物或品种具有光周期敏感性，即在营养生长期内，开花不仅与温度有关，还取决于当天白昼长度。
        """
        self.pheno.calc_rates(day, drv)
        crop_stage = self.pheno.get_variable("STAGE")

        # 如果尚未出苗，则无需继续，因为此时仅运行物候发育。
        if crop_stage == "emerging":
            return  # 地上部作物尚未计算

        # 下面的代码仅在出苗后执行

        # 叶片、茎、根和贮藏器官中的可转移氮素。
        ATNLV, ATNST, ATNRT, ATN = self.translocatable_N()

        # 叶片因衰老/老化的相对死亡速率。
        RDRTMP = p.RDRT(DAVTMP)

        # 植物体内活的营养部位总生物量。
        TBGMR = s.WLVG + s.WST

        # 平均残留氮浓度。
        NRMR = (s.WLVG * p.RNFLV + s.WST * p.RNFST) / TBGMR

        # 叶片的最大氮浓度（作为发育阶段的函数），茎和根的最大浓度由此推得。
        NMAXLV  = p.NMXLV(DVS)
        NMAXST  = p.LSNR * NMAXLV
        NMAXRT  = p.LRNR * NMAXLV

        # 叶片和茎的最大氮浓度。
        NOPTLV  = p.FRNX * NMAXLV
        NOPTST  = p.FRNX * NMAXST

        # 植株的最大氮含量。
        NOPTS   = NOPTST * s.WST
        NOPTL   = NOPTLV * s.WLVG
        NOPTMR  = (NOPTL + NOPTS)/TBGMR

        # 植物体绿色部位的总氮含量。
        NUPGMR  = s.ANLV + s.ANST

        # 氮素营养指数。
        """
        氮素胁迫

        当作物体内氮浓度低于无胁迫生长所需的临界值时，作物被认为经历了氮素胁迫。为了量化作物对氮素不足的响应，定义了氮素营养指数（NNI），其值范围从0（最大氮素匮乏）到1（无氮素匮乏）：

        NNI = (实际作物[N] - 残留[N]) / (临界[N] - 残留[N])

        临界作物氮浓度是保证叶片和茎部生长不受限制所需的最低冠层氮浓度，通常取为最大氮浓度的一半。Zhen 和 Leigh (1990) 的研究为这种假设提供了实验依据：当植物的氮素需求被满足以保证最大生长时，植物中会有大量硝酸盐积累，且在不同生育阶段，超过临界氮浓度的硝酸盐平均值约为50%。
        """
        NFGMR = NUPGMR / TBGMR
        NNI = limit(0.001, 1.0, ((NFGMR-NRMR)/(NOPTMR-NRMR)))

        # -------- 植物器官生长速率与干物质生产 -------*
        #  在（水分和氮素）无胁迫条件下的生物量分配函数
        """
        生物量分配

        作物生长期间任何时刻形成的生物量在器官间分配（见图1），即根、茎、叶和贮藏器官，分配因子作为发育阶段的函数给出（见图2）（Drenth等，1994），从而给出各器官的生长速率：

        dW/dt[i] = Pc[i] * dW / dt

        其中(dW/dt)为生物量增长速率（g/m²·d）；(dW/dt)[i]和Pc[i]分别为器官i的生长速率（g/m²·d）和分配因子（g器官/g生物量）。移栽时植株幼苗叶、茎、根重为模型输入参数。这些器官的重量随时间变化，通过积分其净生长速率（即生长速率减去死亡速率，后者为生理年龄、遮荫和胁迫的函数）得到。
        """
        FRTWET = p.FRTTB(DVS)
        FLVT = p.FLVTB(DVS)
        FSTT = p.FSTTB(DVS)
        FSOT = p.FSOTB(DVS)


        """
        叶面积发展

        LAI（叶面积指数）的变化历程分为两个阶段：苗期的指数生长阶段（叶面积发展受温度控制）和随叶生物量增加的线性阶段（Spitters, 1990；Spitters和Schapendonk, 1990）。衰老引起的叶片死亡可因遮荫和/或胁迫而加剧，导致叶面积的相应损失。特异叶面积（SLA）用于将枯死叶生物量转换为叶面积损失。衰老导致的叶片死亡仅在开花后发生，速率受作物生理年龄影响（采用自ORYZA2000，Bouman等，2001）。叶片因过度生长产生的相互遮阴也会导致叶片死亡。遮荫导致的叶片死亡，由最大死亡速率和叶面积超过临界LAI（4.0）的相对比例确定（Spitters, 1990；Spitters和Schapendonk, 1990）。叶面积净增长速率（dLAI/dt）为生长速率和死亡速率的差值：

        dLAI/dt = dGLAI / dt - dDLAI / dt

        其中(dGLAI/dt)为叶面积生长速率，(dDLAI/dt)为叶面积死亡速率。
        """
        # 比叶面积（m2/g）。
        SLA = p.SLAC * p.SLACF(DVS) * exp(-p.NSLA * (1.-NNI))

        # 水分胁迫下的生长抑制函数（实际蒸腾/潜在蒸腾）
        r.TRANRF = r.TRAN / r.PTRAN if (r.PTRAN != 0) else 1

        # 根和地上部分分配的相对修正因子。
        FRT, FLV, FST, FSO = self.dryMatterPartitioningFractions(p.NPART, r.TRANRF, NNI, FRTWET, FLVT, FSTT, FSOT)

        # 植物总生长速率。
        RGROWTH = self.totalGrowthRate(DTR, r.TRANRF, NNI)

        # 叶的总生长速率和LAI。
        GLV    = FLV * RGROWTH

        # 叶面积指数的日增长量。
        GLAI = self._growth_leaf_area(DTEFF, self.LAII, DELT, SLA, GLV, WC, DVS, r.TRANRF, NNI)

        # 叶片相对死亡速率。
        DLV, DLAI = self.deathRateOfLeaves(TSUM, RDRTMP, NNI, SLA)

        # 叶面积的净变化速率。
        RLAI   = GLAI - DLAI

        # 根的总生长速率
        """
        根的生长

        根系的特征是垂直向土壤剖面延伸。出苗或水稻移栽时初始化根系深度。氮素胁迫（NNI）对作物生长的影响通过对叶面积和光能利用效率的作用表现出来。根以恒定速率每日伸长，直至开花，只要土壤水分高于永久萎蔫点（PWP）；当土壤干旱至低于PWP或达到预设最大根系深度时，生长停止（Spitters和Schapendonk, 1990；Farré等，2000）。
        """
        r.RROOTD = min(p.RRDMAX,  p.ROOTDM - s.ROOTD) if (WC > p.WCWP) else 0.0

        # 叶和根死亡导致的氮损失
        DRRT = 0. if (DVS < p.DVSDR) else s.WRT * p.RDRRT
        RNLDLV = p.RNFLV * DLV
        RNLDRT = p.RNFRT * DRRT

        # 根、叶、茎和贮藏器官的相对总生长速率
        RWLVG, RWRT, RWST, RWSO = self.relativeGrowthRates(RGROWTH, FLV, FRT, FST, FSO, DLV, DRRT)


        """
        氮素需求

        作物总氮素需求等于各器官的氮需求之和（不包括贮藏器官，其氮需求通过从其它器官（即根、茎、叶）转运获得）（图3）。
        各器官的氮素需求计算为其最大氮含量与实际氮含量之差。最大氮含量定义为冠层发育阶段的函数（Drenth等, 1994）。
        作物的总氮需求（TNdem: g m-2 d-1）为：

        TNdem = sum(Nmax,i - ANi / dt)

        其中，Nmax,i 是第i个器官的最大氮浓度（gN/g生物量，i为叶、茎和根），Wi为第i个器官的重量（g生物量/m2），ANi为第i个器官的实际氮含量（gN/m2）。
        """

        # 叶、根和茎贮藏器官的氮需求
        NDEMLV   =  max(NMAXLV   * s.WLVG - s.ANLV, 0.)
        NDEMST   =  max(NMAXST   * s.WST  - s.ANST, 0.)
        NDEMRT   =  max(NMAXRT   * s.WRT  - s.ANRT, 0.)
        NDEMSO  =  max(p.NMAXSO * s.WSO  - s.ANSO, 0.) / p.TCNT

        # 向贮藏器官的氮供应
        NSUPSO  = ATN / p.TCNT if (DVS > p.DVSNT) else 0.0

        # 谷粒的氮吸收速率
        RNSO    =  min(NDEMSO, NSUPSO)

        # 总氮需求
        NDEMTO  = max(0.0, (NDEMLV + NDEMST + NDEMRT))

        """
        收获时75-90%的氮吸收发生在开花前，在高肥力条件下，开花后氮吸收可贡献高达25%，但全部最终进入谷粒（以蛋白质形式）。
        因此，这部分氮素不会影响生物量形成过程中的氮胁迫计算。
        因此假定氮的吸收在开花时终止，因为开花后营养器官中的氮含量几乎不再增加。
        """

        # 抽穗前扎根土层水分不足时氮吸收受限，抽穗后不再从土壤吸收
        NLIMIT  = 1.0 if (DVS < p.DVSNLT) and (WC >= p.WCWP) else 0.0

        NUPTR   = (max(0., min(NDEMTO, s.TNSOIL))* NLIMIT ) / DELT

        # 叶、茎、根氮的转运
        RNTLV   = RNSO* ATNLV/ ATN
        RNTST   = RNSO* ATNST/ ATN
        RNTRT   = RNSO* ATNRT/ ATN

        # 将氮素总吸收速率（NUPTR）分配到叶、茎和根
        RNULV, RNUST, RNURT = self.N_uptakeRates(NDEMLV, NDEMST, NDEMRT, NUPTR, NDEMTO)

        RNST    = RNUST-RNTST
        RNRT    = RNURT-RNTRT-RNLDRT

        # 各器官氮变化速率
        RNLV    = RNULV-RNTLV-RNLDLV

        # ****************土壤-作物氮供应*****************************
        """
        土壤-作物氮平衡

        土壤中无机氮的平衡为矿化和/或施肥增加的氮量与作物吸收和损失移除的氮量之差。土壤中氮的净变化速率（dN/dt，g m-2 d-1）为：

        dN/dt[soil]= Nmin + (FERTN * NRF) - dNU/dt

        其中 Nmin 为通过矿化和生物固氮提供的氮，FERTN 为施肥氮施用速率，NRF 为施肥氮利用率，dNU/dt 为作物吸收氮速率，其计算为土壤供应氮量和作物氮需求的最小值。
        """

        # 土壤无机氮因施肥、矿化和作物吸收而变化
        RNSOIL = self.FERTNS/DELT - NUPTR + p.RNMIN
        self.FERTNS = 0.0

        # 总叶重
        WLV     = s.WLVG + s.WLVD

        # 碳、氮平衡
        CBALAN = (s.TGROWTH + (p.WRTLI + p.WLVGI + p.WSTI + p.WSOI)
                         - (WLV + s.WST + s.WSO + s.WRT + s.WDRT))

        NBALAN = (s.NUPTT + (self.ANLVI + self.ANSTI + self.ANRTI + self.ANSOI)
                  - (s.ANLV + s.ANST + s.ANRT + s.ANSO + s.NLOSSL + s.NLOSSR))

        s.rLAI    = RLAI
        s.rANLV   = RNLV
        s.rANST   = RNST
        s.rANRT   = RNRT
        s.rANSO   = RNSO
        s.rNUPTT  = NUPTR
        s.rNLOSSL = RNLDLV
        s.rNLOSSR = RNLDRT
        s.rWLVG   = RWLVG
        s.rWLVD   = DLV
        s.rWST    = RWST
        s.rWSO    = RWSO
        s.rWRT    = RWRT
        s.rROOTD  = r.RROOTD
        s.rTGROWTH = RGROWTH
        s.rWDRT   = DRRT
        s.rCUMPAR = PAR
        s.rTNSOIL = RNSOIL

        if abs(NBALAN) > 0.0001:
            raise NutrientBalanceError("Nitrogen un-balance in crop model at day %s" % day)
        
        if abs(CBALAN) > 0.0001:
            raise CarbonBalanceError("Carbon un-balance in crop model at day %s" % day)

    @prepare_states
    def integrate(self, day, delt=1.0):
        # 在出苗之前不需要继续，因为此时只运行物候。
        # 只需运行 touch() 以确保 kiosk 中所有状态变量都可用

        self.pheno.integrate(day, delt)
        if self.pheno.get_variable("STAGE") == "emerging":
            self.touch()
            return

        # 对 states 对象自动执行积分
        s = self.states
        s.integrate(delta=1.)

        # 计算一些派生状态
        s.TAGBM = s.WLVG + s.WLVD + s.WST + s.WSO

    def _calc_potential_evapotranspiration(self, drv):
        """计算作物的潜在蒸发和蒸腾。"""
        ES0 = cm2mm(drv.ES0)
        ET0 = cm2mm(drv.ET0)
        pevap = exp(-0.5 * self.states.LAI) * ES0
        pevap = max(0., pevap)
        ptran = (1. - exp(-0.5 * self.states.LAI)) * ET0
        ptran = max(0., ptran)
        return pevap, ptran

    def _calc_actual_transpiration(self, PTRAN, WC):
        """计算实际的蒸发和蒸腾速率。"""
        p = self.params
                
        # 临界含水量
        WCCR = p.WCWP + max( 0.01, PTRAN/(PTRAN + p.TRANCO) * (p.WCFC - p.WCWP))
          
        # 如果稻田土壤被淹：假定土壤永久饱和，
        # 高含水量对作物总生长速率没有影响，因为水稻有通气组织。
        # 因此 FR 如下表达：
          
        if p.WMFAC:
            if (WC > WCCR):
                FR = 1.
            else:
                FR = limit( 0., 1., (WC - p.WCWP) / (WCCR - p.WCWP))
        
        # 如果土壤灌溉但未被淹：假定土壤含水量处于田间持水量，
        # 影响作物总生长速率的临界含水量如下注释所示：
        else:
            if (WCCR <= WC <= p.WCWET):  # 处于临界值之间
                FR = 1.0
            elif (WC < WCCR):                
                FR = limit( 0., 1., (WC - p.WCWP)/(WCCR - p.WCWP))
            else:
                FR = limit( 0., 1., (p.WCST - WC)/(p.WCST - p.WCWET))
        
        return PTRAN * FR

    def _growth_leaf_area(self, DTEFF, LAII,  DELT, SLA, GLV, WC, DVS, TRANRF, NNI):
        """该子程序计算叶面积指数的日增量。"""

        p = self.params
        LAI = self.states.LAI
        
        #---- 生育后期的生长:
        GLAI = SLA * GLV

        #---- 幼苗期的生长:
        if ((DVS  <  0.2) and (LAI  <  0.75)):
            GLAI = (LAI * (exp(p.RGRL * DTEFF * DELT) - 1.)/ DELT )* TRANRF* exp(-p.NLAI* (1.0 - NNI))

        #---- 幼苗出土当天的生长:
        if ((LAI == 0.) and (WC > p.WCWP)):
            GLAI = LAII / DELT  
        
        return GLAI

    def dryMatterPartitioningFractions(self, NPART, TRANRF, NNI, FRTWET, FLVT, FSTT, FSOT):
        """ 计算干物质分配系数：叶片、茎和贮藏器官。"""

        p = self.params
        NRF = exp(-p.NLUE * (1.0 - NNI))
        if(TRANRF  <  NRF):
            # 水分胁迫比氮胁迫更严重，分配遵循LINTUL2*的原始假设
            FRTMOD = max(1., 1./(TRANRF+0.5))
            FRT    = FRTWET * FRTMOD
            FSHMOD = (1.-FRT) / (1.-FRT/FRTMOD)
            FLV    = FLVT * FSHMOD
            FST    = FSTT * FSHMOD
            FSO    = FSOT * FSHMOD
        else:
            # 氮胁迫比水分胁迫更严重，减少分配到叶片的生物量会分配到根
            FLVMOD = exp(-NPART* (1.0-NNI))
            FLV    = FLVT * FLVMOD
            MODIF  = (1.-FLV)/(1.-(FLV/FLVMOD))
            FST    = FSTT *  MODIF
            FRT    = FRTWET* MODIF
            FSO    = FSOT *  MODIF
    
        return FRT, FLV, FST, FSO # FLVMOD removed from signature - WdW
    
    def totalGrowthRate(self, DTR, TRANRF, NNI):
        """计算总生长速率。

        Monteith (1977)、Gallagher 和 Biscoe (1978) 及 Monteith (1990) 表明，每单位截获光合有效辐射（LUE，光能利用效率，g 干物质 MJ-1）形成的生物量相对稳定。
        因此，最大日生长速率可定义为截获的光合有效辐射（PAR，|MJm-2d-1|）与LUE的乘积。

        截获的PAR取决于入射太阳辐射、光合有效的比例（0.5）（Monteith 和 Unsworth, 1990；Spitters, 1990），
        以及根据Lambert Beer定律取决于LAI（|m2|叶面积 |m-2| 土壤）：

        :math:`Q = 0.5 Q0 (1 - e^{-k LAI})`

        其中 *Q* 为截获的PAR（|MJm-2d-1|），*Q0* 为每日总辐射（|MJm-2d-1|），*k*为冠层中PAR的衰减系数。
        """
        
        p = self.params
        PARINT = 0.5 * DTR * (1.- exp(-p.K * self.states.LAI))
        RGROWTH = p.LUE * PARINT
        NRF = exp(-p.NLUE * (1.0 - NNI))
        GRF = 1.0
        if(TRANRF  <=  NRF):
            # 水分胁迫比氮胁迫更严重，分配遵循LINTUL2*的原始假设
            GRF = TRANRF
        else:
            # 氮胁迫比水分胁迫更严重，减少分配到叶片的生物量会分配到根
            GRF = NRF
        RGROWTH *= GRF
        return RGROWTH

    def relativeGrowthRates(self, RGROWTH, FLV, FRT, FST, FSO, DLV, DRRT):
        """计算根、叶、茎和贮藏器官的相对总生长速率。"""
      
        RWLVG = RGROWTH * FLV - DLV      # 叶子的生长速率
        RWRT  = RGROWTH * FRT - DRRT     # 根的生长速率
        RWST  = RGROWTH * FST            # 茎的生长速率
        RWSO  = RGROWTH * FSO            # 贮藏器官的生长速率

        return RWLVG, RWRT, RWST, RWSO

    def N_uptakeRates(self, NDEML, NDEMS, NDEMR, NUPTR, NDEMTO):
        """计算总氮吸收速率（NUPTR）在叶、茎和根中的分配。"""
      
        if (NDEMTO > 0):
            RNULV = (NDEML / NDEMTO)* NUPTR  # 分配到叶子的氮吸收速率
            RNUST = (NDEMS / NDEMTO)* NUPTR  # 分配到茎的氮吸收速率
            RNURT = (NDEMR / NDEMTO)* NUPTR  # 分配到根的氮吸收速率

            return RNULV, RNUST, RNURT
        else:
            return 0.0, 0.0, 0.0

    def translocatable_N(self):      
        """计算各器官可转运的氮。"""
        s = self.states
        p = self.params
        ATNLV = max (0., s.ANLV - s.WLVG * p.RNFLV)                     # 叶片可转运氮
        ATNST = max (0., s.ANST - s.WST  * p.RNFST)                     # 茎可转运氮
        ATNRT = min((ATNLV + ATNST) * p.FNTRT, s.ANRT - s.WRT * p.RNFRT) # 根可转运氮
        ATN   = ATNLV +  ATNST + ATNRT                                  # 总可转运氮
        
        return ATNLV, ATNST, ATNRT, ATN

    def deathRateOfLeaves(self, TSUM, RDRTMP, NNI, SLA):
        """计算由于年龄、遮荫和氮胁迫导致的叶片死亡速率。"""
      
        p = self.params
        s = self.states
        
        RDRDV = 0. if (TSUM < p.TSUMAG) else RDRTMP    # 由于发育（年龄）导致的叶片死亡速率
        
        RDRSH = max(0., p.RDRSHM * (s.LAI - p.LAICR) / p.LAICR) # 遮荫导致的死亡速率
        RDR   = max(RDRDV, RDRSH)                               # 取较大者作为实际速率
        
        if (NNI  <  1.):
            DLVNS   = s.WLVG * p.RDRNS * (1. - NNI) # 氮胁迫导致的叶片死亡
            DLAINS  = DLVNS * SLA                   # 氮胁迫导致的叶面积损失
        else:
            DLVNS   = 0.
            DLAINS  = 0.
        
        DLVS  = s.WLVG * RDR      # 非氮胁迫导致的叶片死亡
        DLAIS = s.LAI * RDR       # 非氮胁迫导致的叶面积损失
        
        DLV   = DLVS + DLVNS      # 总叶片死亡速率
        DLAI  = DLAIS + DLAINS    # 总叶面积损失
    
        return DLV, DLAI