from math import sqrt
import numpy as np

from ..traitlets import Float, Int, Instance, Bool
from ..decorators import prepare_rates, prepare_states
from ..util import limit
from ..base import ParamTemplate, StatesTemplate, RatesTemplate, \
     SimulationObject
from .. import exceptions as exc
from .. import signals

from .soil_profile import SoilProfile

REFERENCE_TEST_RUN = False  # 由测试过程设置

class WaterBalanceLayered_PP(SimulationObject):
    _default_RD = Float(10.)  # 默认生根深度为10厘米
    _RDold = _default_RD
    _RDM = Float(None)
    
    # 上次降雨天数计数器
    DSLR = Float(1)
    
    # 前一天的降雨量
    RAINold = Float(0)

    # 土壤对象和参数提供者的占位符
    soil_profile = None

    # 标记一个新作物是否开始
    crop_start = Bool(False)

    class Parameters(ParamTemplate):
        pass

    class StateVariables(StatesTemplate):
        SM = Instance(np.ndarray)
        WC = Instance(np.ndarray)
        WTRAT = Float(-99.)
        EVST = Float(-99.)

    class RateVariables(RatesTemplate):
        EVS = Float(-99.)
        WTRA = Float(-99.)

    def initialize(self, day, kiosk, parvalues):
        self.soil_profile = SoilProfile(parvalues)
        parvalues._soildata["soil_profile"] = self.soil_profile

        # 最大生根深度
        self._RDM = self.soil_profile.get_max_rootable_depth()
        self.soil_profile.validate_max_rooting_depth(self._RDM)

        SM = np.zeros(len(self.soil_profile))
        WC = np.zeros_like(SM)
        for il, layer in enumerate(self.soil_profile):
            SM[il] = layer.SMFCF
            WC[il] = SM[il] * layer.Thickness
        
        WTRAT = 0.
        EVST = 0.

        states = { "WC": WC, "SM":SM, "EVST": EVST, "WTRAT": WTRAT}
        self.rates = self.RateVariables(kiosk, publish="EVS")      
        self.states = self.StateVariables(kiosk, publish=["WC", "SM", "EVST"], **states)

    @prepare_rates
    def calc_rates(self, day, drv):
        r = self.rates
        # 蒸腾和土壤/地表水分蒸发最大速率由作物蒸散模块计算
        # 如果作物尚未出苗，则设置TRA=0，直接采用潜在的土壤/水分蒸发速率
        # 因为没有冠层遮荫
        if "TRA" not in self.kiosk:
            r.WTRA = 0.
            EVSMX = drv.ES0
        else:
            r.WTRA = self.kiosk["TRA"]
            EVSMX = self.kiosk["EVSMX"]

        # 实际蒸发速率

        if self.RAINold >= 1:
            # 如果前一天降雨量大于等于1厘米，则视为土壤蒸发最大
            r.EVS = EVSMX
            self.DSLR = 1.
        else:
            # 否则，土壤蒸发为距离上次降雨天数(DSLR)的函数
            self.DSLR += 1
            EVSMXT = EVSMX * (sqrt(self.DSLR) - sqrt(self.DSLR - 1))
            r.EVS = min(EVSMX, EVSMXT + self.RAINold)

        # 记录降雨量以跟踪土壤表面湿润度，并在需要时重置DSLR
        self.RAINold = drv.RAIN
        
    @prepare_states
    def integrate(self, day, delt=1.0):
        self.states.SM = self.states.SM
        self.states.WC = self.states.WC

        # 累计的蒸腾和土壤蒸发量
        self.states.EVST += self.rates.EVS * delt
        self.states.WTRAT += self.rates.WTRA * delt
        

class WaterBalanceLayered(SimulationObject):
    """
    实现了多层土壤水分平衡，用于估算作物生长和水分胁迫的土壤供水能力。

    传统的自由排水型水量平衡存在一些重要局限性，比如无法考虑剖面内土壤质地差异及其对水流的影响。此外，单层水分平衡模型中，降雨或灌溉会立刻为作物所用，这种物理行为并不正确，往往导致作物在降雨后恢复过快，因为所有根系都能立刻获取下渗水。因此，随着土壤数据的细化，需要更真实的水分平衡来更好地模拟土壤过程及其对作物生长的影响。

    多层土壤水分平衡在计算复杂度、模拟的真实性和数据可获得性之间达到了折中。模型依然以每日为步长运行，但实现了基于水力势和土壤导水率的上下水流的概念。后者被组合为所谓的基质通量势（Matric Flux Potential）。模型计算土壤中两种类型的水流：

      (1) "干流量"，来自基质通量势（如层间吸力梯度）
      (2) "湿流量"，由当前层传导性和向下重力作用下产生

    显然，只有干流量可能为负（即向上流）。在干旱情况下，干流量反映了大的水势梯度（但忽略重力）。湿流量仅考虑重力，在土壤较湿时占主导。干、湿流量取最大值作为向下流动量，并对其进行如下限制以防止：
    (a) 过饱和；
    (b) 含水量低于田间持水量。
    向上的流动就是为负的干流量。在这种情况下，其大小仅为实现层间势平衡所需量的一定比例，同时要考虑到下方来的上行流量的贡献。

    土壤分层可变，但受以下限制：

    - 层厚不能太小。实践中，顶层不应小于10~20 cm，否则需要小于一天的步长，因为降雨会快速填满上层导致地表径流，而模型无法在单日步长内处理全部渗透。
    - 作物最大可生根深度需与层边界一致，防止根直接从根系下方取水。当然，通过上行水流，下层水可以逐步变得可利用。

    当前Python实现尚未包含浅层地下水的影响，未来版本将补充该功能。

    有关基质通量势的介绍，可参见：

        Pinheiro, Everton Alves Rodrigues, 等. “A Matric Flux Potential Approach to Assess Plant Water
        Availability in Two Climate Zones in Brazil.” Vadose Zone Journal, 17卷1期, 2018年1月, 1–10页.
        https://doi.org/10.2136/vzj2016.09.0083

    **注意**：当前版本（2024年4月）的代码实现偏向“Fortran风格”，这是为了与原有Fortran90版本对照查验。当确认实现无误后，可将其重构为更函数式结构，而不是现在这种冗长且循环繁多的写法。


    **模拟参数:**

    除下表参数外，多层水分平衡还需一个 `SoilProfileDescription` 对象，提供各土壤层的属性。详情参见 `SoilProfile`、`SoilLayer` 类。

    ========== ============================================  ====================
     名称      描述                                            单位
    ========== ============================================  ====================
    NOTINF     降雨未渗入土壤的最大比例                         -
    IFUNRN     是否降雨未渗入比例为暴雨量的函数(1)或否(0)         -
    SSI        初始地表水层厚度                                 cm
    SSMAX      最大地表水层厚度                                 cm
    SMLIM      顶层最大土壤含水量                               cm3/cm3
    WAV        土壤初始水量                                     cm
    ========== ============================================  ====================


    **状态变量:**

    =======  ===============================================  ============
     名称      描述                                                单位
    =======  ===============================================  ============
    WTRAT     水分平衡累计的总蒸腾损失                        cm
              与CTRTAT变量不同, 后者仅统计作物周期蒸腾
    EVST      土壤表面总蒸发量                                cm
    EVWT      水面总蒸发量                                    cm
    TSR       地表径流总量                                    cm
    RAINT     总降雨量（有效+无效）                            cm
    WDRT      根系生长带来的根区水分增量                      cm
    TOTINF    入渗总量                                        cm
    TOTIRR    有效灌溉总量                                    cm

    SM        各土壤层体积含水量（数组）                       -
    WC        各土壤层水量（数组）                            cm
    W         根区水量                                        cm
    WLOW      亚土层水量（当前根系深度到最大根系深度间）        cm
    WWLOW     剖面总水量（WWLOW=WLOW + W）                     cm
    WBOT      最大根区以下且不可利用的水量                     cm
    WAVUPP    根区内可用水（高于萎蔫点的部分）                 cm
    WAVLOW    潜在根区（当前根系以下）可用水                   cm
    WAVBOT    最大根区以下可用水                               cm
    SS        地表储水层（水膜）                               cm
    SM_MEAN   根区平均含水量                                   cm3/cm3
    PERCT     根区向亚土层渗漏总量                              cm
    LOSST     流失到更深土层的总水量                           cm
    =======  ===============================================  ============


    **速率变量**

    ========== ========================================  ====================
     名称      描述                                         单位
    ========== ========================================  ====================
    Flow        各层间水流速率                              cm/天
    RIN         地表入渗速率                                cm/天
    WTRALY      各层蒸腾速率（数组）                        cm/天
    WTRA        各层累计总作物蒸腾速率                      cm/天
    EVS         土壤表面蒸发速率                            cm/天
    EVW         开水面蒸发速率                              cm/天
    RIRR        灌溉速率                                    cm/天
    DWC         各层净增减水量（数组）                      cm/天
    DRAINT      降雨累积量变化                              cm/天
    DSS         地表储水变化量                              cm/天
    DTSR        表面径流速率                                cm/天
    BOTTOMFLOW  剖面底部水流速率                            cm/天
    ========== ========================================  ====================
    """
    _default_RD = Float(10.)  # 默认根系深度为10厘米
    _RDold = _default_RD
    _RINold = Float(0.)
    _RIRR = Float(0.)
    _DSLR = Int(None)
    _RDM = Float(None)
    _RAIN = Float(None)
    _WCI = Float(None)

    # 最大流动迭代次数和所需精度
    MaxFlowIter = 50
    TinyFlow = 0.001

    # 最大向上流动为达到各层平衡所需量的50%
    # 参见 Kees Rappoldt 文档第80页
    UpwardFlowLimit = 0.50

    # 土壤对象和参数提供者的占位符
    soil_profile = None
    parameter_provider = None

    # 指示新作物已开始
    crop_start = Bool(False)

    class Parameters(ParamTemplate):
        IFUNRN = Int(None)
        NOTINF = Float(None)
        SSI = Float(None)
        SSMAX = Float(None)
        SMLIM = Float(None)
        WAV = Float(None)

    class StateVariables(StatesTemplate):
        WTRAT = Float(None)
        EVST = Float(None)
        EVWT = Float(None)
        TSR = Float(None)
        RAINT = Float(None)
        WDRT = Float(None)
        TOTINF = Float(None)
        TOTIRR = Float(None)
        CRT = Float(None)
        SM = Instance(np.ndarray)
        SM_MEAN = Float(None)
        WC = Instance(np.ndarray)
        W = Float(None)
        WLOW = Float(None)
        WWLOW = Float(None)
        WBOT = Float(None)
        WAVUPP = Float(None)
        WAVLOW = Float(None)
        WAVBOT = Float(None)
        SS = Float(None)
        BOTTOMFLOWT = Float(None)


    class RateVariables(RatesTemplate):
        Flow = Instance(np.ndarray)
        RIN = Float(None)
        WTRALY = Instance(np.ndarray)
        WTRA = Float(None)
        EVS = Float(None)
        EVW = Float(None)
        RIRR = Float(None)
        DWC = Instance(np.ndarray)
        DRAINT = Float(None)
        DSS = Float(None)
        DTSR = Float(None)
        BOTTOMFLOW = Float(None)

    def initialize(self, day, kiosk, parvalues):

        self.soil_profile = SoilProfile(parvalues)
        parvalues._soildata["soil_profile"] = self.soil_profile

        # 最大可生根深度
        RDMsoil = self.soil_profile.get_max_rootable_depth()
        if REFERENCE_TEST_RUN:
            # 作物根系深度（RDMCR）在开始时需要与fortran代码结果对比
            self._RDM = min(parvalues["RDMCR"], RDMsoil)
        else:
            self._RDM = self.soil_profile.get_max_rootable_depth()
        self.soil_profile.validate_max_rooting_depth(self._RDM)

        self.params = self.Parameters(parvalues)
        p = self.params

        # 保存参数提供者，因为需要用它检索新的作物开始时的最大根系深度
        self.parameter_provider = parvalues

        self.soil_profile.determine_rooting_status(self._default_RD, self._RDM)

        if self.soil_profile.GroundWater:
            raise NotImplementedError("Groundwater influence not yet implemented.")
        else:
            # AVMAX - 层的最大可用水量
            # 首先计算此项以实现在根系顶部区域的水分均匀分布
            # 如果WAV较小，注意根区初始SM的单独限制
            TOPLIM = 0.0
            LOWLIM = 0.0
            AVMAX = []
            for il, layer in enumerate(self.soil_profile):
                if layer.rooting_status in ["rooted", "partially rooted"]:
                    # 检查SMLIM是否在边界内
                    SML = limit(layer.SMW, layer.SM0, p.SMLIM)
                    AVMAX.append((SML - layer.SMW) * layer.Thickness)   # 可用水量，单位cm
                    # 即使是部分生根，整个层的容量也计入TOPLIM
                    # 这意味着ILR层的含水量设置为完全生根。如有轻微根系生长、每个时间步的数值混合后，该水分将变为可用
                    TOPLIM += AVMAX[il]
                elif layer.rooting_status == "potentially rooted":
                    # 根区下方，最大水量为饱和（见一层模型WLOW的代码）
                    # 全层容量也计入LOWLIM
                    SML = layer.SM0
                    AVMAX.append((SML - layer.SMW) * layer.Thickness)   # 可用水量，单位cm
                    LOWLIM += AVMAX[il]
                else:  # 处于潜在生根区下方
                    break

        if p.WAV <= 0.0:
            # 没有可用水分
            TOPRED = 0.0
            LOWRED = 0.0
        elif p.WAV <= TOPLIM:
            # 可用水分分布在1..ILR层，这些层是生根的或者接近生根的
            # 按比例WAV / TOPLIM进行分配
            TOPRED = p.WAV / TOPLIM
            LOWRED = 0.0
        elif p.WAV < TOPLIM + LOWLIM:
            # 可用水分能充满潜在生根区
            # 生根区填满；其余部分比例递减
            TOPRED = 1.0
            LOWRED = (p.WAV-TOPLIM) / LOWLIM
        else:
            # 水分无法完全分配；所有层“满”
            TOPRED = 1.0
            LOWRED = 1.0

        W = 0.0    ; WAVUPP = 0.0
        WLOW = 0.0 ; WAVLOW = 0.0
        SM = np.zeros(len(self.soil_profile))
        WC = np.zeros_like(SM)
        Flow = np.zeros(len(self.soil_profile) + 1)
        for il, layer in enumerate(self.soil_profile):
            if layer.rooting_status in ["rooted", "partially rooted"]:
                # 分配给ILR的部分水不一定实际在根区，但随着根生长（以及每步的数值混合），很快会变为可用
                SM[il] = layer.SMW + AVMAX[il] * TOPRED / layer.Thickness
                W += SM[il] * layer.Thickness * layer.Wtop
                WLOW += SM[il] * layer.Thickness * layer.Wpot
                # 可用水分
                WAVUPP += (SM[il] - layer.SMW) * layer.Thickness * layer.Wtop
                WAVLOW += (SM[il] - layer.SMW) * layer.Thickness * layer.Wpot
            elif layer.rooting_status == "potentially rooted":
                SM[il] = layer.SMW + AVMAX[il] * LOWRED / layer.Thickness
                WLOW += SM[il] * layer.Thickness * layer.Wpot
                # 可用水分
                WAVLOW += (SM[il] - layer.SMW) * layer.Thickness * layer.Wpot
            else:
                # 最大根区以下，将SM含量设为萎蔫点
                SM[il] = layer.SMW
            WC[il] = SM[il] * layer.Thickness

            # 将地下水位设远一些以便清晰；这还能防止根系生长例程在到达地下水时停止根生长
            ZT = 999.0

        # 土壤蒸发，距上次降雨的天数
        top_layer = self.soil_profile[0]
        top_layer_half_wet = top_layer.SMW + 0.5 * (top_layer.SMFCF - top_layer.SMW)
        self._DSLR = 5 if SM[0] <= top_layer_half_wet else 1

        # 水分平衡的所有累加变量初始化为零
        states = {"WTRAT": 0., "EVST": 0., "EVWT": 0., "TSR": 0., "WDRT": 0.,
                  "TOTINF": 0., "TOTIRR": 0., "BOTTOMFLOWT": 0.,
                  "CRT": 0., "RAINT": 0., "WLOW": WLOW, "W": W, "WC": WC, "SM":SM,
                  "SS": p.SSI, "WWLOW": W+WLOW, "WBOT":0., "SM_MEAN": W/self._default_RD,
                  "WAVUPP": WAVUPP, "WAVLOW": WAVLOW, "WAVBOT":0.
                  }
        self.states = self.StateVariables(kiosk, publish=["WC", "SM", "EVST"], **states)

        # 剖面含水量的初始值
        self._WCI = WC.sum()

        # 速率变量
        self.rates = self.RateVariables(kiosk, publish=["RIN", "Flow", "EVS"])
        self.rates.Flow = Flow

        # 连接 CROP_START/CROP_FINISH/IRRIGATE 信号
        self._connect_signal(self._on_CROP_START, signals.crop_start)
        self._connect_signal(self._on_CROP_FINISH, signals.crop_finish)
        self._connect_signal(self._on_IRRIGATE, signals.irrigate)


    @prepare_rates
    def calc_rates(self, day, drv):
        p = self.params
        s = self.states
        k = self.kiosk
        r = self.rates

        delt = 1.0

        # 如果有新作物开始，则更新生根设置
        if self.crop_start:
            self.crop_start = False
            self._setup_new_crop()

        # 灌溉速率（RIRR）
        r.RIRR = self._RIRR
        self._RIRR = 0.

        # 复制降雨量用于 RAINT 的累加
        self._RAIN = drv.RAIN

        # 作物蒸腾速率及土壤/地表水最大蒸发速率
        if "TRALY" in self.kiosk:
            # 蒸腾速率及土壤与地表水最大蒸发速率
            # 由作物蒸散发模块计算，从kiosk读取
            WTRALY = k.TRALY
            r.WTRA = k.TRA
            EVWMX = k.EVWMX
            EVSMX = k.EVSMX
        else:
            # 如果作物尚未出苗，则将 WTRALY/TRA 设为0，并直接使用
            # 潜在土壤/水面蒸发速率，因为没有冠层遮荫
            WTRALY = np.zeros_like(s.SM)
            r.WTRA = 0.
            EVWMX = drv.E0
            EVSMX = drv.ES0

        # 实际蒸发速率
        r.EVW = 0.
        r.EVS = 0.
        if s.SS > 1.:
            # 如果地表储水 > 1cm，则从地表水层蒸发
            r.EVW = EVWMX
        else:
            # 否则假定从土壤表面蒸发
            if self._RINold >= 1:
                # 如果前一天入渗量 >= 1cm，假定土壤最大蒸发
                r.EVS = EVSMX
                self._DSLR = 1
            else:
                # 否则土壤蒸发受“自上次降雨天数”（DSLR）影响
                EVSMXT = EVSMX * (sqrt(self._DSLR + 1) - sqrt(self._DSLR))
                r.EVS = min(EVSMX, EVSMXT + self._RINold)
                self._DSLR += 1

        # 计算所有土层的导水率和基质通量势
        pF = np.zeros_like(s.SM)
        conductivity = np.zeros_like(s.SM)
        matricfluxpot = np.zeros_like(s.SM)
        for i, layer in enumerate(self.soil_profile):
            pF[i] = layer.PFfromSM(s.SM[i])
            conductivity[i] = 10**layer.CONDfromPF(pF[i])
            matricfluxpot[i] = layer.MFPfromPF(pF[i])
            if self.soil_profile.GroundWater:
                raise NotImplementedError("Groundwater influence not yet implemented.")

        # 潜在可入渗降雨
        if p.IFUNRN == 0:
            RINPRE = (1. - p.NOTINF) * drv.RAIN
        else:
            # 入渗为暴雨量（NINFTB）的函数
            RINPRE = (1. - p.NOTINF * self.NINFTB(drv.RAIN)) * drv.RAIN


        # 二阶段预入渗速率（RINPRE），包括地表储水和灌溉
        RINPRE = RINPRE + r.RIRR + s.SS
        if s.SS > 0.1:
            # 有地表储水时，入渗受 SOPE 限制
            AVAIL = RINPRE + r.RIRR - r.EVW
            RINPRE = min(self.soil_profile.SurfaceConductivity, AVAIL)

        # 每一层顶部的最大流量
        # ------------------------------------------
        # 向下的水流有两种计算方式：
        # (1) 基于基质通量势的“干流”（dry flow）
        # (2) 基于当前土层水力导率和重力的“湿流”（wet flow）
        # 显然，只有干流可能为负（即：向上）。干流反映了干旱条件下势能的巨大梯度（但不考虑重力），而湿流只考虑重力，在潮湿条件下起主导作用。下渗流量取干流和湿流的最大值，然后再进一步限制，以防止
        # (a) 过度饱和 和 (b) 含水量低于田间持水量。
        #
        # 向上的水流就是负值的干流。在这种情况下，流量被限制在达到各土层等势所需量的一定比例，但同时要考虑下层传递上来的向上流动的贡献。因此，当有地下水上升时，只要吸力梯度足够大，这个向上流就会被传递到上层。

        FlowMX = np.zeros(len(s.SM) + 1)
        # 首先获得通过最底层下边界的水流
        if self.soil_profile.GroundWater:
            raise NotImplementedError("Groundwater influence not yet implemented.")
        #    使用旧的毛细上升（capillairy rise）方案来估算向/从地下水的水流
        #    注意，该方法返回毛细上升为正值，向下渗流为负值，这和 WATFDGW 模块中的定义正好相反。

        # is = SubSoilType
        # if (ZT >= LBSL(NSL)) then
        #     # 地下水位在分层系统之下；调用旧的毛细上升计算子程序
        #     # 层的PF位置取在下边界上方 1/3 * TSL 处；这样对于地下水接近底层时结果较为合理
        #     call SUBSOL (PF(NSL), ZT-LBSL(NSL)+TSL(NSL)/3.0, SubFlow, Soil(is)%CONDfromPF, Soil(is)%ilCOND)
        #     # write (*,*) 'call SUBSOL ', PF(NSL), ZT-LBSL(NSL)+TSL(NSL)/3.0, SubFlow
        #     if (SubFlow >= 0.0) then
        #         # 毛细上升受限于达到平衡所需的水量：
        #         # 步骤1：计算ZT与层顶之间所有空气体积达到平衡时的水气差
        #         EqAir   = WSUB0 - WSUB + (WC0(NSL)-WC(NSL))
        #         # 步骤2：找到与上述平衡空气体积对应的地下水位
        #         ZTeq1   = (LBSL(NSL)-TSL(NSL)) + AFGEN(Soil(is)%HeightFromAir, EquilTableLEN, EqAir)
        #         # 步骤3：该水位通常应低于当前水位（否则不应有毛细上升），但若子程序 SUBSOL 用了层中点，有时也会有偏差
        #         ZTeq2   = MAX(ZT, ZTeq1)
        #         # 步骤4：用这个 ZTeq2 计算该土层的平衡含水量
        #         WCequil = AFGEN(Soil(is)%WaterFromHeight, EquilTableLEN, ZTeq2-LBSL(NSL)+TSL(NSL)) - &
        #                   AFGEN(Soil(is)%WaterFromHeight, EquilTableLEN, ZTeq2-LBSL(NSL))
        #         # 步骤5：用该平衡量限制向上流速
        #         FlowMX(NSL+1) = -1.0 * MIN (SubFlow, MAX(WCequil-WC(NSL),0.0)/DELT)
        #     else:
        #         # 向下流动；下覆土层的充气孔隙度限制向下流动
        #         AirSub = (ZT-LBSL(NSL))*SubSM0 - AFGEN(Soil(is)%WaterFromHeight, EquilTableLEN, ZT-LBSL(NSL))
        #         FlowMX(NSL+1) = MIN (ABS(SubFlow), MAX(AirSub,0.0)/DELT)
        #         # write (*,*) 'Limiting downward flow: AirSub, FlowMX(NSL+1) = ', AirSub, FlowMX(NSL+1)
        # else:
        #     # 地下水位在分层系统内部；不再有向下流动
        #     FlowMX(NSL+1) = 0.0
        else:
            # 最底层的导水率限制了流量。田间持水量以下时无下渗，因此下边界处的下渗流量可近似为：
            FlowMX[-1] = max(self.soil_profile[-1].CondFC, conductivity[-1])

        # 排水计算
        DMAX = 0.0

        LIMDRY = np.zeros_like(s.SM)
        LIMWET = np.zeros_like(s.SM)
        TSL = [l.Thickness for l in self.soil_profile]
        for il in reversed(range(len(s.SM))):
            # 限制向下渗流速率
            # == 湿润条件：土壤导水率较高
            #    土壤导水率仅由重力引起
            #    该限制仅适用于向下流动
            # == 干旱条件：基质流势梯度决定
            #    干旱条件下基质流势梯度较大
            #    允许有一定的向上流动
            if il == 0:  # 表层土壤层
                LIMWET[il] = self.soil_profile.SurfaceConductivity
                LIMDRY[il] = 0.0
            else:
                # 湿润条件下的限制为单位梯度
                LIMWET[il] = (TSL[il-1]+TSL[il]) / (TSL[il-1]/conductivity[il-1] + TSL[il]/conductivity[il])

                # 按基质流势梯度计算干流
                if self.soil_profile[il-1] == self.soil_profile[il]:
                    # il-1和il两层为同一土壤类型：流量通过两层的基质流势梯度估算
                    LIMDRY[il] = 2.0 * (matricfluxpot[il-1]-matricfluxpot[il]) / (TSL[il-1]+TSL[il])
                    if LIMDRY[il] < 0.0:
                        # 向上流速；需要使两层含水量相等所需的水量计算在下方
                        MeanSM = (s.WC[il-1] + s.WC[il]) / (TSL[il-1]+TSL[il])
                        EqualPotAmount = s.WC[il-1] - TSL[il-1] * MeanSM  # 应为负值，与流速符号一致
                else:
                    # 采用二分法迭代搜索层边界的pF值
                    il1  = il-1; il2 = il
                    PF1  = pF[il1]; PF2 = pF[il2]
                    MFP1 = matricfluxpot[il1]; MFP2 = matricfluxpot[il2]
                    for z in range(self.MaxFlowIter):  # 此处计数只用于迭代次数
                        PFx = (PF1 + PF2) / 2.0
                        Flow1 = 2.0 * (+ MFP1 - self.soil_profile[il1].MFPfromPF(PFx)) / TSL[il1]
                        Flow2 = 2.0 * (- MFP2 + self.soil_profile[il2].MFPfromPF(PFx)) / TSL[il2]
                        if abs(Flow1-Flow2) < self.TinyFlow:
                            # 已达到足够精度
                            break
                        elif abs(Flow1) > abs(Flow2):
                            # 第1层流量较大，PFx应向PF1方向移动
                            PF2 = PFx
                        elif abs(Flow1) < abs(Flow2):
                            # 第2层流量较大，PFx应向PF2方向移动
                            PF1 = PFx
                    else:  # 未break，迭代失败
                        msg = 'WATFDGW: LIMDRY flow iteration failed. Are your soil moisture and ' + \
                              'conductivity curves decreasing with increasing pF?'
                        raise exc.PCSEError(msg)
                    LIMDRY[il] = (Flow1 + Flow2) / 2.0

                    if LIMDRY[il] < 0.0:
                        # 向上流速；需要使势能一致所需的量下方计算
                        Eq1 = -s.WC[il2]; Eq2 = 0.0
                        for z in range(self.MaxFlowIter):
                            EqualPotAmount = (Eq1 + Eq2) / 2.0
                            SM1 = (s.WC[il1] - EqualPotAmount) / TSL[il1]
                            SM2 = (s.WC[il2] + EqualPotAmount) / TSL[il2]
                            PF1 = self.soil_profile[il1].SMfromPF(SM1)
                            PF2 = self.soil_profile[il2].SMfromPF(SM2)
                            if abs(Eq1-Eq2) < self.TinyFlow:
                                # 已达到足够精度
                                break
                            elif PF1 > PF2:
                                # 上层吸力较大，需更大交换量
                                Eq2 = EqualPotAmount
                            else:
                                # 下层吸力较大，需减少交换量
                                Eq1 = EqualPotAmount
                        else:
                            msg = "WATFDGW: Limiting amount iteration in dry flow failed. Are your soil moisture " \
                                  "and conductivity curves decreasing with increase pF?"
                            raise exc.PCSEError(msg)

            FlowDown = True  # 默认向下流动
            if LIMDRY[il] < 0.0:
                # 向上流（负值！）受达到平衡所需量一定比例的限制
                FlowMax = max(LIMDRY[il], EqualPotAmount * self.UpwardFlowLimit)
                if il > 0:
                    # 向上流动受限于目标土层达到平衡/田间持水量所需的量
                    # if (il==2) write (*,*) '2: ',FlowMax, LIMDRY(il), EqualPotAmount * UpwardFlowLimit
                    if self.soil_profile.GroundWater:
                        # 有地下水时土壤不会排水至低于地下水平衡含水量
                        # FCequil = MAX(WCFC(il-1), EquilWater(il-1))
                        raise NotImplementedError("Groundwater influence not implemented yet.")
                    else:
                        # 自由排水
                        FCequil = self.soil_profile[il-1].WCFC

                    TargetLimit = WTRALY[il-1] + FCequil - s.WC[il-1]/delt
                    if TargetLimit > 0.0:
                        # 目标层干燥，低于田间持水量；限制向上流动
                        FlowMax = max(FlowMax, -1.0 * TargetLimit)
                        # 向上流减少当前层含水量，不需再防止过饱和
                        # 流量仅受限于避免负含水量
                        FlowMX[il] = max(FlowMax, FlowMX[il+1] + WTRALY[il] - s.WC[il]/delt)
                        FlowDown = False
                    elif self.soil_profile.GroundWater:
                        # 目标层湿润，高于田间持水量。由于基质势模型不考虑重力，此“湿润”向上流动被忽略
                        FlowMX[il] = 0.0
                        FlowDown = True
                    else:
                        # 目标层湿润，无地下水，自由排水模型下向上流被拒绝
                        # 允许下渗，自由排水模型适用
                        FlowDown = True

            if FlowDown:
                # 最大向下流速（LIMWET始终为正数）
                FlowMax = max(LIMDRY[il], LIMWET[il])
                # 防止当前土层过饱和
                # 最大上边界流量 = 下边界流量 + 饱和亏缺 + 植物吸水
                FlowMX[il] = min(FlowMax, FlowMX[il+1] + (self.soil_profile[il].WC0 - s.WC[il])/delt + WTRALY[il])
        # end for

        r.RIN = min(RINPRE, FlowMX[0])

        # 在允许干旱向上流动的情况下，各土层对土壤蒸发的贡献
        EVSL = np.zeros_like(s.SM)
        for il, layer in enumerate(self.soil_profile):
            if il == 0:
                EVSL[il] = min(r.EVS, (s.WC[il] - layer.WCW) / delt + r.RIN - WTRALY[il])
                EVrest = r.EVS - EVSL[il]
            else:
                Available = max(0.0, (s.WC[il] - layer.WCW)/delt - WTRALY[il])
                if Available >= EVrest:
                    EVSL[il] = EVrest
                    EVrest   = 0.0
                    break
                else:
                    EVSL[il] = Available
                    EVrest   = EVrest - Available
        # 如果整个剖面变成风干，则减少蒸发
        # 在NSL土层的下边界没有蒸发通量
        r.EVS = r.EVS - EVrest

        # 将土层对EVS的贡献转化为向上的通量
        # 各土层边界的蒸发流（取正值!!!!）
        NSL = len(s.SM)
        EVflow = np.zeros_like(FlowMX)
        EVflow[0] = r.EVS
        for il in range(1, NSL):
            EVflow[il] = EVflow[il-1] - EVSL[il-1]
        EVflow[NSL] = 0.0  # 见上方注释

        # 限制向下流动以避免低于田间持水量/平衡含水量
        Flow = np.zeros_like(FlowMX)
        r.DWC = np.zeros_like(s.SM)
        Flow[0] = r.RIN - EVflow[0]
        for il, layer in enumerate(self.soil_profile):
            if self.soil_profile.GroundWater:
                # 土壤不会排水至低于地下水平衡含水量
                #WaterLeft = max(self.WCFC[il], EquilWater[il])
                raise NotImplementedError("Groundwater influence not implemented yet.")
            else:
                # 自由排水
                WaterLeft = layer.WCFC
            MXLOSS = (s.WC[il] - WaterLeft)/delt               # 最大损失
            Excess = max(0.0, MXLOSS + Flow[il] - WTRALY[il])  # 剩余水量（为正则有剩余）
            Flow[il+1] = min(FlowMX[il+1], Excess - EVflow[il+1])  # 注意负值（向上流动）不受影响
            # 变化率
            r.DWC[il] = Flow[il] - Flow[il+1] - WTRALY[il]

        # 剖面底部的流量
        r.BOTTOMFLOW = Flow[-1]

        if self.soil_profile.GroundWater:
            # 地下水影响
            # DWBOT = LOSS - Flow[self.NSL+1]
            # DWSUB = Flow[self.NSL+1]
            raise NotImplementedError("Groundwater influence not implemented yet.")

        # 计算地表水储量和地表径流的变化率
        # SStmp为无法入渗且可能储存在地表的水层。这里假设RAIN_NOTINF自动进入地表储水（最终成为径流）
        SStmp = drv.RAIN + r.RIRR - r.EVW - r.RIN
        # 地表水储量的变化率受SSMAX - SS限制
        r.DSS = min(SStmp, (p.SSMAX - s.SS))
        # SStmp的剩余部分流向地表径流
        r.DTSR = SStmp - r.DSS
        # 降雨速率
        r.DRAINT = drv.RAIN

        self._RINold = r.RIN
        r.Flow = Flow

    @prepare_states
    def integrate(self, day, delt):
        p = self.params
        s = self.states
        k = self.kiosk
        r = self.rates

        # 各土层的水量；土壤含水量
        SM = np.zeros_like(s.SM)
        WC = np.zeros_like(s.WC)
        for il, layer in enumerate(self.soil_profile):
            WC[il] = s.WC[il] + r.DWC[il] * delt
            SM[il] = WC[il] / layer.Thickness
        # 注意：不能直接将WC[il]替换为s.WC[il]，否则kiosk不会被更新，因为traitlets不能监控list/array的内部变化。
        # 因此必须赋值如下：
        s.SM = SM
        s.WC = WC

        # 累计总蒸腾量
        s.WTRAT += r.WTRA * delt

        # 累计表层水层和/或土壤的总蒸发量
        s.EVWT += r.EVW * delt
        s.EVST += r.EVS * delt

        # 降雨、灌溉和入渗的合计
        s.RAINT += self._RAIN
        s.TOTINF += r.RIN * delt
        s.TOTIRR += r.RIRR * delt

        # 地表储水和径流
        s.SS += r.DSS * delt
        s.TSR += r.DTSR * delt

        # 剖面底部流失水量
        s.BOTTOMFLOWT += r.BOTTOMFLOW * delt

        # 根区的渗漏量；根据模式不同有不同解释
        if self.soil_profile.GroundWater:
            # 有地下水时，该流量既可为渗漏也可为毛管上升
            if r.PERC > 0.0:
                s.PERCT = s.PERCT + r.PERC * delt
            else:
                s.CRT = s.CRT - r.PERC * delt
        else:
            # 无地下水时，该流量总称为渗漏
            s.CRT = 0.0

        # 根区变化
        RD = self._determine_rooting_depth()
        if abs(RD - self._RDold) > 0.001:
            self.soil_profile.determine_rooting_status(RD, self._RDM)

        # 计算有根区、潜在有根区及无根区的土壤水汇总
        W = 0.0 ; WAVUPP = 0.0
        WLOW = 0.0 ; WAVLOW = 0.0
        WBOT = 0.0 ; WAVBOT = 0.0
        # 获取W、WLOW和可用水量
        for il, layer in enumerate(self.soil_profile):
            W += s.WC[il] * layer.Wtop
            WLOW += s.WC[il] * layer.Wpot
            WBOT += s.WC[il] * layer.Wund
            WAVUPP += (s.WC[il] - layer.WCW) * layer.Wtop
            WAVLOW += (s.WC[il] - layer.WCW) * layer.Wpot
            WAVBOT += (s.WC[il] - layer.WCW) * layer.Wund

        # 更新状态
        s.W = W
        s.WLOW = WLOW
        s.WWLOW = s.W + s.WLOW
        s.WBOT = WBOT
        s.WAVUPP = WAVUPP
        s.WAVLOW = WAVLOW
        s.WAVBOT = WAVBOT

        # 保存已经确定层含水量所用的根系深度
        self._RDold = RD

        s.SM_MEAN = s.W/RD

    @prepare_states
    def finalize(self, day):
        s = self.states
        p = self.params
        if self.soil_profile.GroundWater:
            # 地下水版本水分平衡校验
            # WBALRT_GW = TOTINF + CRT + WI - W + WDRT - EVST - TRAT - PERCT
            # WBALTT_GW = SSI + RAINT + TOTIRR + WI - W + WZI - WZ - TRAT - EVWT - EVST - TSR - DRAINT - SS
            pass
        else:
            # 自由排水版本水分平衡校验
            checksum = (p.SSI - s.SS  # 地表蓄水变化量
                        + self._WCI - s.WC.sum()  # 土壤水分变化量
                        + s.RAINT + s.TOTIRR  # 系统的入水量
                        - s.WTRAT - s.EVWT - s.EVST - s.TSR - s.BOTTOMFLOWT  # 系统的出水量
                        )
            if abs(checksum) > 0.0001:
                msg = "Waterbalance not closing on %s with checksum: %f" % (day, checksum)
                raise exc.WaterBalanceError(msg)

    def _determine_rooting_depth(self):
        """确定根系深度（RD）的合适取值

        该函数包含了用于确定水分平衡剖面有根（上层）区域深度的逻辑。详细描述见代码注释。
        """
        if "RD" in self.kiosk:
            return self.kiosk["RD"]
        else:
            # 保持RD为默认值
            return self._default_RD

    def _on_CROP_START(self):
        self.crop_start = True

    def _on_CROP_FINISH(self):
        pass
        # self.in_crop_cycle = False
        # self.rooted_layer_needs_reset = True

    def _on_IRRIGATE(self, amount, efficiency):
        self._RIRR = amount * efficiency

    def _setup_new_crop(self):
        """获取作物最大可生长根系深度并进行校验、更新根系状态，
        以便能够正确计算土壤水分平衡汇总状态。
        """
        self._RDM = self.parameter_provider["RDMCR"]
        self.soil_profile.validate_max_rooting_depth(self._RDM)
        self.soil_profile.determine_rooting_status(self._default_RD, self._RDM)
