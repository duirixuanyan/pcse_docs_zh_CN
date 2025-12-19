# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
"""在WOFOST中实现物候发育模型

此文件中定义的类:
- DVS_Phenology: 实现物候发育的相关算法
- Vernalisation: 
"""
import datetime

from ..traitlets import Float, Int, Instance, Enum, Bool
from ..decorators import prepare_rates, prepare_states

from ..util import limit, daylength, AfgenTrait
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject, VariableKiosk
from .. import signals
from .. import exceptions as exc

#-------------------------------------------------------------------------------
class Vernalisation(SimulationObject):
    """
    由于春化作用导致的物候发育变化。

    这里的春化处理基于Lenny van Bussel（2011）的工作，这又基于Wang和Engel（1998）。其基本原理是冬小麦需要若干天处于最适温度范围内以完成春化需求。在满足春化需求之前，作物的发育会被延迟。

    春化速率（VERNR）由温度响应函数VERNRTB决定。在最适温度范围内，春化状态（VERN）每天增加1。物候发育的减缓根据基本和饱和春化需求（VERNBASE和VERNSAT）计算。减缓因子（VERNFAC）在VERNBASE和VERNSAT之间线性缩放。

    设置了一个临界发育阶段（VERNDVS），当DVS达到该值时，春化作用的影响被终止。这是为了提高模型的稳定性，避免由于VERNSAT设置过高导致抽穗期永远无法到达。如果发生这种情况，会向日志文件写入警告。

    * Van Bussel, 2011. From field to globe: Upscaling of crop growth modelling.
      Wageningen博士论文. http://edepot.wur.nl/180295
    * Wang and Engel, 1998. Simulation of phenological development of wheat
      crops. Agric. Systems 58:1 pp 1-24

    *模拟参数* （在cropdata字典中提供）

    ======== ============================================= =======  ============
     名称       描述                                         类型      单位
    ======== ============================================= =======  ============
    VERNSAT  饱和春化需求                                   SCr      天
    VERNBASE 基本春化需求                                   SCr      天
    VERNRTB  春化速率作为日均温的函数                       TCr      -
    VERNDVS  达到此发育阶段后终止春化作用                   SCr      -
    ======== ============================================= =======  ============

    **状态变量**

    ============ ================================================= ==== ========
     名称         描述                                             公布  单位
    ============ ================================================= ==== ========
    VERN         春化状态                                           N    天
    DOV          完成春化需求的日期                                 N    -
    ISVERNALISED 指示春化需求是否已经满足的标志                     Y    -
    ============ ================================================= ==== ========

    **速率变量**

    =======  ================================================= ==== ============
     名称       描述                                           公布     单位
    =======  ================================================= ==== ============
    VERNR    春化速率                                           N     -
    VERNFAC  由于春化作用导致发育速率的减缓因子                 Y     -
    =======  ================================================= ==== ============

    **外部依赖：**

    ============ =============================== ========================== =====
     名称         描述                              提供者                  单位
    ============ =============================== ========================== =====
    DVS          发育阶段。                           Phenology              -
                 仅用于判断是否达到春化作用
                 （VERNDVS）对应的临界阶段。
    ============ =============================== ========================== =====
    """
    # 辅助变量，用于指示 DVS > VERNDVS
    _force_vernalisation = Bool(False)

    class Parameters(ParamTemplate):
        VERNSAT = Float(-99.)     # 饱和春化需求
        VERNBASE = Float(-99.)    # 基本春化需求
        VERNRTB = AfgenTrait()    # 春化速率关于日均温的响应函数
        VERNDVS = Float(-99.)     # 达到春化完成的关键DVS

    class RateVariables(RatesTemplate):
        VERNR = Float(-99.)        # 春化速率
        VERNFAC = Float(-99.)      # 物候发育的减缓因子

    class StateVariables(StatesTemplate):
        VERN = Float(-99.)              # 春化状态
        DOV = Instance(datetime.date)   # 达到春化需求的日期
        ISVERNALISED =  Bool()          # 达到VERNSAT为True，如果DVS>VERNDVS被强制为True

    #---------------------------------------------------------------------------
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 仿真起始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param cropdata: 带有WOFOST作物数据键值对的字典

        """
        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk, publish=["VERNFAC"])
        self.kiosk = kiosk

        # 定义初始状态变量
        self.states = self.StateVariables(kiosk, VERN=0., VERNFAC=0.,
                                          DOV=None, ISVERNALISED=False,
                                          publish=["ISVERNALISED"])
    #---------------------------------------------------------------------------
    @prepare_rates
    def calc_rates(self, day, drv):
        rates = self.rates
        states = self.states
        params = self.params

        DVS = self.kiosk["DVS"]
        if not states.ISVERNALISED:
            if DVS < params.VERNDVS:
                rates.VERNR = params.VERNRTB(drv.TEMP)
                r = (states.VERN - params.VERNBASE)/(params.VERNSAT-params.VERNBASE)
                rates.VERNFAC = limit(0., 1., r)
            else:
                rates.VERNR = 0.
                rates.VERNFAC = 1.0
                self._force_vernalisation = True
        else:
            rates.VERNR = 0.
            rates.VERNFAC = 1.0
    #---------------------------------------------------------------------------
    @prepare_states
    def integrate(self, day, delt=1.0):
        states = self.states
        rates = self.rates
        params = self.params
        
        states.VERN += rates.VERNR
        
        if states.VERN >= params.VERNSAT:  # 达到春化需求
            states.ISVERNALISED = True
            if states.DOV is None:
                states.DOV = day
                msg = "Vernalization requirements reached at day %s."
                self.logger.info(msg % day)

        elif self._force_vernalisation:  # 达到春化关键DVS
            # 强制完成春化，但不设置DOV
            states.ISVERNALISED = True

            # 写入日志，警告发生了强制春化
            msg = ("Critical DVS for vernalization (VERNDVS) reached " +
                   "at day %s, " +
                   "but vernalization requirements not yet fulfilled. " +
                   "Forcing vernalization now (VERN=%f).")
            self.logger.warning(msg % (day, states.VERN))

        else:  # 用于物候发育的减缓因子
            states.ISVERNALISED = False

#-------------------------------------------------------------------------------
class DVS_Phenology(SimulationObject):
    """
    实现WOFOST作物发育（物候）发展算法。

    WOFOST中的物候发育使用一个无量纲标度来表示，该标度在出苗时取0，开花（Anthesis）时取1，成熟时取2。这种物候发育方式主要适用于谷物类作物。所有其他用WOFOST模拟的作物也被强制使用该方案，尽管这对所有作物可能并不都合适。例如，对马铃薯来说，发育阶段1表示块茎形成的开始，而不是开花。

    物候发育主要受温度控制，在开花之前还可以受到日长和春化作用的影响。开花后，只有温度影响发育速率。

    **模拟参数**

    =======  ============================================= =======  ============
     名称      描述                                         类型       单位
    =======  ============================================= =======  ============
    TSUMEM   从播种到出苗的温度积（积温）                   SCr        |C| day
    TBASEM   出苗的基温                                     SCr        |C|
    TEFFMX   出苗的最大有效温度                             SCr        |C|
    TSUM1    从出苗到开花的温度积                           SCr        |C| day
    TSUM2    从开花到成熟的温度积                           SCr        |C| day
    IDSL     发育方案选项开关                               SCr        -
             温度控制(IDSL=0)，包括日长(IDSL=1)             SCr
             或包括春化（IDSL>=2）
    DLO      发育的最适日长                                 SCr        hr
    DLC      发育的临界日长                                 SCr        hr
    DVSI     出苗时的初始发育阶段                           SCr        -
             通常为零，但对于移栽作物（如水稻）可更高
    DVSEND   最终发育阶段                                   SCr        -
    DTSMTB   日均温响应函数（温度对发育的贡献）             TCr        |C|
    =======  ============================================= =======  ============

    **状态变量**

    =======  ================================================= ==== ============
     名称      描述                                            公共      单位
    =======  ================================================= ==== ============
    DVS      发育阶段                                           Y        - 
    TSUM     积温                                               N    |C| day
    TSUME    出苗积温                                           N    |C| day
    DOS      播种日期                                           N        - 
    DOE      出苗日期                                           N        - 
    DOA      开花日期                                           N        - 
    DOM      成熟日期                                           N        - 
    DOH      收获日期                                           N        -
    STAGE    当前物候阶段，取值如下：                           N        -
             `emerging|vegetative|reproductive|mature`
    =======  ================================================= ==== ============

    **速率变量**

    =======  ================================================= ==== ============
     名称      描述                                            公共      单位
    =======  ================================================= ==== ============
    DTSUME   出苗积温的增加量                                   N    |C|
    DTSUM    开花/成熟积温的增加量                              N    |C|
    DVR      发育速度                                           Y    |day-1|
    =======  ================================================= ==== ============

    **外部依赖：**

    无  

    **信号发送或处理**

    当达到成熟并且end_type为'maturity'或'earliest'时，`DVS_Phenology`发送`crop_finish`信号。
    """
    # 用于起止类型和春化模块的占位符
    vernalisation = Instance(Vernalisation)

    class Parameters(ParamTemplate):
        TSUMEM = Float(-99.)  # 出苗所需的积温
        TBASEM = Float(-99.)  # 出苗基温
        TEFFMX = Float(-99.)  # 出苗最大有效温度
        TSUM1  = Float(-99.)  # 出苗到开花的积温
        TSUM2  = Float(-99.)  # 开花到成熟的积温
        IDSL   = Float(-99.)  # 日长敏感性开关（1为敏感，2为包括春化）
        DLO    = Float(-99.)  # 发育最适日长
        DLC    = Float(-99.)  # 发育临界日长
        DVSI   = Float(-99.)  # 初始发育阶段
        DVSEND = Float(-99.)  # 最终发育阶段
        DTSMTB = AfgenTrait() # 发育阶段的温度响应函数
                              # 
        CROP_START_TYPE = Enum(["sowing", "emergence"])
        CROP_END_TYPE = Enum(["maturity", "harvest", "earliest"])

    #-------------------------------------------------------------------------------
    class RateVariables(RatesTemplate):
        DTSUME = Float(-99.)  # 出苗积温的增加量
        DTSUM  = Float(-99.)  # 开花/成熟积温的增加量
        DVR    = Float(-99.)  # 发育速度

    #-------------------------------------------------------------------------------
    class StateVariables(StatesTemplate):
        DVS = Float(-99.)  # 发育阶段
        TSUM = Float(-99.)  # 积温状态量
        TSUME = Float(-99.)  # 出苗积温状态量
        # 注册物候事件的状态量
        DOS = Instance(datetime.date) # 播种日期
        DOE = Instance(datetime.date) # 出苗日期
        DOA = Instance(datetime.date) # 开花日期
        DOM = Instance(datetime.date) # 成熟日期
        DOH = Instance(datetime.date) # 收获日期
        STAGE = Enum(["emerging", "vegetative", "reproductive", "mature"])

    #---------------------------------------------------------------------------
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的开始日期
        :param kiosk: 此 PCSE 实例的变量仓库
        :param parvalues: `ParameterProvider` 对象，提供参数的键/值对
        """

        self.params = self.Parameters(parvalues)
        self.rates = self.RateVariables(kiosk)
        self.kiosk = kiosk

        self._connect_signal(self._on_CROP_FINISH, signal=signals.crop_finish)

        # 定义初始状态量
        DVS, DOS, DOE, STAGE = self._get_initial_stage(day)
        self.states = self.StateVariables(kiosk, publish="DVS",
                                          TSUM=0., TSUME=0., DVS=DVS,
                                          DOS=DOS, DOE=DOE, DOA=None, DOM=None,
                                          DOH=None, STAGE=STAGE)

        # 对于 IDSL=2 初始化春化模块
        if self.params.IDSL >= 2:
            self.vernalisation = Vernalisation(day, kiosk, parvalues)
    
    #---------------------------------------------------------------------------
    def _get_initial_stage(self, day):
        """定义作物初始发育阶段、返回 DVS, DOS, DOE, STAGE"""
        p = self.params

        # 定义初始发育阶段类型（emergence/sowing），并设置相应的播种/出苗日期（DOS/DOE）
        if p.CROP_START_TYPE == "emergence":
            STAGE = "vegetative"  # 初始阶段为营养生长期
            DOE = day             # 出苗日期等于当前日期
            DOS = None            # 播种日期未知
            DVS = p.DVSI          # 初始发育阶段
            
            # 发送出苗信号
            self._send_signal(signals.crop_emerged)

        elif p.CROP_START_TYPE == "sowing":
            STAGE = "emerging"    # 初始阶段为出苗期
            DOS = day             # 播种日期等于当前日期
            DOE = None            # 出苗日期未知
            DVS = -0.1            # 初始发育阶段值-0.1

        else:
            msg = "Unknown start type: %s" % p.CROP_START_TYPE
            raise exc.PCSEError(msg)
            
        return DVS, DOS, DOE, STAGE

    #---------------------------------------------------------------------------
    @prepare_rates
    def calc_rates(self, day, drv):
        """计算作物物候发育的速率变量"""
        p = self.params
        r = self.rates
        s = self.states

        # 日长度敏感性（日照对发育的影响因子）
        DVRED = 1.
        if p.IDSL >= 1:
            DAYLP = daylength(day, drv.LAT) # 计算白昼长度
            DVRED = limit(0., 1., (DAYLP - p.DLC)/(p.DLO - p.DLC))  # 根据临界日长修正

        # 春化作用
        VERNFAC = 1.
        if p.IDSL >= 2:
            if s.STAGE == 'vegetative':  # 只在营养生长阶段考虑春化
                self.vernalisation.calc_rates(day, drv)   # 调用春化率计算
                VERNFAC = self.kiosk["VERNFAC"]           # 获取春化因子

        # 生育发育速率
        if s.STAGE == "emerging":
            r.DTSUME = limit(0., (p.TEFFMX - p.TBASEM), (drv.TEMP - p.TBASEM)) # 出苗积温增量
            r.DTSUM = 0.
            r.DVR = 0.1 * r.DTSUME/p.TSUMEM                                    # 出苗发育速率

        elif s.STAGE == 'vegetative':
            r.DTSUME = 0.
            r.DTSUM = p.DTSMTB(drv.TEMP) * VERNFAC * DVRED    # 积温增量，包含春化和日长影响
            r.DVR = r.DTSUM/p.TSUM1                           # 营养生长发育速率

        elif s.STAGE == 'reproductive':
            r.DTSUME = 0.
            r.DTSUM = p.DTSMTB(drv.TEMP)    # 生殖生长期的积温增量
            r.DVR = r.DTSUM/p.TSUM2         # 生殖生长发育速率
        elif s.STAGE == 'mature':
            r.DTSUME = 0.
            r.DTSUM = 0.
            r.DVR = 0.
        else:  # 问题：未定义发育阶段
            msg = "Unrecognized STAGE defined in phenology submodule: %s"
            raise exc.PCSEError(msg, self.states.STAGE)
        
        msg = "Finished rate calculation for %s"
        self.logger.debug(msg % day)
        
    #---------------------------------------------------------------------------
    @prepare_states
    def integrate(self, day, delt=1.0):
        """更新状态变量并检查作物物候阶段
        """

        p = self.params
        r = self.rates
        s = self.states

        # 积分春化模块
        if p.IDSL >= 2:
            if s.STAGE == 'vegetative':
                self.vernalisation.integrate(day, delt)
            else:
                self.vernalisation.touch()

        # 积分物候状态
        s.TSUME += r.DTSUME
        s.DVS += r.DVR
        s.TSUM += r.DTSUM

        # 检查是否进入新阶段
        if s.STAGE == "emerging":
            if s.DVS >= 0.0:
                self._next_stage(day)
                s.DVS = 0.
        elif s.STAGE == 'vegetative':
            if s.DVS >= 1.0:
                self._next_stage(day)
                s.DVS = 1.0
        elif s.STAGE == 'reproductive':
            if s.DVS >= p.DVSEND:
                self._next_stage(day)
                s.DVS = p.DVSEND
        elif s.STAGE == 'mature':
            pass
        else: # 问题：未定义阶段
            msg = "No STAGE defined in phenology submodule"
            raise exc.PCSEError(msg)
            
        msg = "Finished state integration for %s"
        self.logger.debug(msg % day)

    #---------------------------------------------------------------------------
    def _next_stage(self, day):
        """将 states.STAGE 移动到下一个物候阶段"""
        s = self.states
        p = self.params

        current_STAGE = s.STAGE
        if s.STAGE == "emerging":
            s.STAGE = "vegetative"
            s.DOE = day
            # 发送作物出苗信号
            self._send_signal(signals.crop_emerged)
            
        elif s.STAGE == "vegetative":
            s.STAGE = "reproductive"
            s.DOA = day
                        
        elif s.STAGE == "reproductive":
            s.STAGE = "mature"
            s.DOM = day
            if p.CROP_END_TYPE in ["maturity","earliest"]:
                self._send_signal(signal=signals.crop_finish,
                                  day=day, finish_type="maturity",
                                  crop_delete=True)
        elif s.STAGE == "mature":
            msg = "Cannot move to next phenology stage: maturity already reached!"
            raise exc.PCSEError(msg)

        else: # 问题：未定义阶段
            msg = "No STAGE defined in phenology submodule."
            raise exc.PCSEError(msg)
        
        msg = "Changed phenological stage '%s' to '%s' on %s"
        self.logger.info(msg % (current_STAGE, s.STAGE, day))

    #---------------------------------------------------------------------------
    def _on_CROP_FINISH(self, day, finish_type=None):
        """处理设置收获日(DOH)的事件。虽然DOH并不严格与物候相关（而是管理相关），但这里是最合理的放置位置。
        """
        if finish_type in ['harvest', 'earliest']:
            self._for_finalize["DOH"] = day
