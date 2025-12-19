# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2024年3月
from collections import namedtuple
from math import exp

from ..traitlets import Float, Int, Instance
from ..decorators import prepare_rates, prepare_states
from ..base import ParamTemplate, StatesTemplate, SimulationObject,\
     VariableKiosk
from .. import exceptions as exc
from warnings import warn
from ..util import AfgenTrait


# 包含分配系数的namedtuple模板
class PartioningFactors(namedtuple("partitioning_factors", "FR FL FS FO")):
    pass

class DVS_Partitioning(SimulationObject):
    """
    基于发育阶段（DVS）进行同化物分配的类。

    `DVS_partioning` 利用基于作物发育阶段的固定分配表，计算同化物分配到根、茎、叶和贮藏器官中的比例。可用的同化物首先根据FRTB的数值分为地下和地上部分。第二阶段根据FLTB（叶）、FSTB（茎）、FOTB（贮藏器官）进行进一步分配。

    由于分配比例由状态变量`DVS`决定，因此这些比例本身也视为状态变量。

    **模拟参数** （需在cropdata字典中提供）:
    
    =======  ============================================= =======  ============
     Name     描述                                           类型      单位
    =======  ============================================= =======  ============
    FRTB     随发育阶段变化的分配到根的比例函数               TCr       -
    FSTB     随发育阶段变化的分配到茎的比例函数               TCr       -
    FLTB     随发育阶段变化的分配到叶的比例函数               TCr       -
    FOTB     随发育阶段变化的分配到贮藏器官的比例函数         TCr       -
    =======  ============================================= =======  ============
    

    **状态变量**

    =======  ================================================= ==== ============
     名称      描述                                            Pbl      单位
    =======  ================================================= ==== ============
    FR        分配到根的比例                                     Y       -
    FS        分配到茎的比例                                     Y       -
    FL        分配到叶的比例                                     Y       -
    FO        分配到贮藏器官的比例                               Y       -
    =======  ================================================= ==== ============

    **速率变量**

    无

    **信号发送或接收**

    无

    **外部依赖**

    =======  =================================== =================  ============
     名称      描述                                 提供方             单位
    =======  =================================== =================  ============
    DVS      作物发育阶段                           DVS_Phenology      -
    =======  =================================== =================  ============
    
    *抛出异常*

    如果某天分配到叶、茎和贮藏器官的系数之和不等于'1'，则会抛出PartitioningError异常。
    """
    
    class Parameters(ParamTemplate):
        FRTB   = AfgenTrait()
        FLTB   = AfgenTrait()
        FSTB   = AfgenTrait()
        FOTB   = AfgenTrait()

    class StateVariables(StatesTemplate):
        FR = Float(-99.)
        FL = Float(-99.)
        FS = Float(-99.)
        FO = Float(-99.)
        PF = Instance(PartioningFactors)
    
    def initialize(self, day, kiosk, parvalues):
        """
        :param day: 模拟的起始日期
        :param kiosk: 本PCSE实例的变量kiosk
        :param parvalues: `ParameterProvider`对象，提供参数的键/值对
        """

        self.params = self.Parameters(parvalues)
        self.kiosk = kiosk

        # 初始分配系数 (pf)
        DVS = self.kiosk["DVS"]
        FR = self.params.FRTB(DVS)
        FL = self.params.FLTB(DVS)
        FS = self.params.FSTB(DVS)
        FO = self.params.FOTB(DVS)

        # 打包分配系数为元组
        PF = PartioningFactors(FR, FL, FS, FO)
        
        # 初始状态变量
        self.states = self.StateVariables(kiosk, publish=["FR","FL","FS","FO"],
                                          FR=FR, FL=FL, FS=FS, FO=FO, PF=PF)
        self._check_partitioning()
        
    def _check_partitioning(self):
        """检查分配系数之和是否有误。"""

        FR = self.states.FR
        FL = self.states.FL
        FS = self.states.FS
        FO = self.states.FO
        checksum = FR+(FL+FS+FO)*(1.-FR) - 1.
        if abs(checksum) >= 0.0001:
            msg = ("Error in partitioning!\n")
            msg += ("Checksum: %f, FR: %5.3f, FL: %5.3f, FS: %5.3f, FO: %5.3f\n" \
                    % (checksum, FR, FL, FS, FO))
            self.logger.error(msg)
            warn(msg)
#             raise exc.PartitioningError(msg)

    @prepare_states
    def integrate(self, day, delt=1.0):
        """根据发育阶段(DVS)更新分配系数"""

        params = self.params
        
        DVS = self.kiosk["DVS"]
        self.states.FR = params.FRTB(DVS)
        self.states.FL = params.FLTB(DVS)
        self.states.FS = params.FSTB(DVS)
        self.states.FO = params.FOTB(DVS)
        
        # 打包分配系数为元组
        self.states.PF = PartioningFactors(self.states.FR, self.states.FL,
                                           self.states.FS, self.states.FO)

        self._check_partitioning()  
    
    def calc_rates(self, day, drv):
        """
        根据当前DVS返回分配系数。
        """
        # rate的计算对分配无影响，因为它是一个派生状态
        return self.states.PF


class DVS_Partitioning_N(SimulationObject):
    """基于发育阶段（DVS）和氮胁迫影响的同化物分配类。

    `DVS_Partitioning_NPK` 使用固定分配表，根据作物发育阶段计算同化物分配到根、茎、叶和贮藏器官的比例。与普通分配类的唯一区别在于考虑了氮胁迫对叶片分配（参数NPART）的影响。可用的同化物首先根据FRTB表被分成地上和地下部分，第二阶段再分配到叶（`FLTB`）、茎（`FSTB`）、贮藏器官（`FOTB`）。

    由于分配系数是由状态变量`DVS`决定的，因此其本身也被视为状态变量。

    **模拟参数** （需要在作物数据字典中提供）:

    =======  ============================================= =======  ============
     Name     描述                                          类型       单位
    =======  ============================================= =======  ============
    FRTB     根分配系数，作为发育阶段的函数                  TCr       -
    FSTB     茎分配系数，作为发育阶段的函数                  TCr       -
    FLTB     叶分配系数，作为发育阶段的函数                  TCr       -
    FOTB     贮藏器官分配系数，作为发育阶段的函数            TCr       -
    NPART    氮胁迫对叶生物量分配影响的系数                  SCR       -
    =======  ============================================= =======  ============

    **状态变量**

    =======  =========================================== ==== ============
     Name     描述                                       发布        单位
    =======  =========================================== ==== ============
    FR        分配到根的比例                               Y        -
    FS        分配到茎的比例                               Y        -
    FL        分配到叶的比例                               Y        -
    FO        分配到贮藏器官的比例                         Y        -
    =======  =========================================== ==== ============

    **速率变量**

    无

    **信号发送或处理**

    无

    **外部依赖：**

    =======  ================================  =============================  =============
     名称       描述                               提供者                        单位
    =======  ================================  =============================  =============
    DVS      作物发育阶段                        DVS_Phenology                    -
    TRA      实际蒸腾量                          Simple_Evapotranspiration       |mm day-1|
    TRAMX    最大蒸腾量                          Simple_Evapotranspiration       |mm day-1|
    NNI      氮营养指数                          npk_dynamics                     -
    =======  ================================  =============================  =============

    *抛出异常*

    如果某一天叶、茎和贮藏器官的分配系数之和不为1，则会抛出 PartitioningError 异常。
    """

    class Parameters(ParamTemplate):
        FRTB = AfgenTrait()
        FLTB = AfgenTrait()
        FSTB = AfgenTrait()
        FOTB = AfgenTrait()
        #NPART = Float(-99.)  # 氮胁迫对叶分配影响的系数

    class StateVariables(StatesTemplate):
        FR = Float(-99.)
        FL = Float(-99.)
        FS = Float(-99.)
        FO = Float(-99.)
        PF = Instance(PartioningFactors)

    def initialize(self, day, kiosk, parameters):
        """
        :param day: 模拟开始日期
        :param kiosk: 此PCSE实例的变量kiosk
        :param parameters: 包含WOFOST作物数据键值对的字典
        """
        self.params = self.Parameters(parameters)

        # 初始分配系数(pf)
        k = self.kiosk
        FR = self.params.FRTB(k.DVS)
        FL = self.params.FLTB(k.DVS)
        FS = self.params.FSTB(k.DVS)
        FO = self.params.FOTB(k.DVS)

        # 将分配因子打包成元组
        PF = PartioningFactors(FR, FL, FS, FO)

        # 初始状态
        self.states = self.StateVariables(kiosk, publish=["FR","FL","FS","FO"],
                                          FR=FR, FL=FL, FS=FS, FO=FO, PF=PF)
        self._check_partitioning()

    def _check_partitioning(self):
        """检查分配过程是否有误。"""

        FR = self.states.FR
        FL = self.states.FL
        FS = self.states.FS
        FO = self.states.FO
        checksum = FR+(FL+FS+FO)*(1.-FR) - 1.
        if abs(checksum) >= 0.0001:
            msg = ("Error in partitioning!\n")
            msg += ("Checksum: %f, FR: %5.3f, FL: %5.3f, FS: %5.3f, FO: %5.3f\n" \
                    % (checksum, FR, FL, FS, FO))
            self.logger.error(msg)
            raise exc.PartitioningError(msg)

    @prepare_states
    def integrate(self, day, delt=1.0):
        """
        根据发育阶段(DVS)以及水分和氧气胁迫更新分配系数。
        """

        p = self.params
        s = self.states
        k = self.kiosk

        FRTMOD = max(1., 1./(k.RFTRA + 0.5))
        s.FR = min(0.6, p.FRTB(k.DVS) * FRTMOD)
        s.FL = p.FLTB(k.DVS)
        s.FS = p.FSTB(k.DVS)
        s.FO = p.FOTB(k.DVS)

        # 将分配因子打包成元组
        s.PF = PartioningFactors(s.FR, s.FL, s.FS, s.FO)

        self._check_partitioning()

    def calc_rates(self, day, drv):
        """根据当前DVS返回分配因子。"""
        # 分配速率的计算不做任何事情，因为它是派生状态
        return self.states.PF
