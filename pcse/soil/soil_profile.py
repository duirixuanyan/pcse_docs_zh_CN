from math import sqrt
import numpy as np
from ..traitlets import Float, Int, Instance, Enum, Unicode, Bool, HasTraits, List
from ..util import limit, Afgen, merge_dict, DotMap

from .. import exceptions as exc


class pFCurve(Afgen):
    """Pf 曲线应检查如下：
    - 数组长度为偶数
    - 至少有 3 对 xy 值
    - pF 应当以 pF = -1 开始，以 pF = 6 结束
    - 随着 pF 增大，SM/cond 的值应减少

    """
    pass


class MFPCurve(Afgen):
    """使用对 pfCurve 的高斯积分法计算基质流势

    """
    elog10 = 2.302585092994
    Pgauss = (0.0469100770, 0.2307653449, 0.5000000000, 0.7692346551, 0.9530899230)
    Wgauss = (0.1184634425, 0.2393143352, 0.2844444444, 0.2393143352, 0.1184634425)

    def __init__(self, SMfromPF, CONDfromPF):
        SMfromPF = np.array(SMfromPF)
        CONDfromPF = pFCurve(CONDfromPF)
        MFPfromPF = np.zeros_like(SMfromPF)

        # 在最大 pF 处，MFP 置零
        MFPfromPF[-1] = 0.
        MFPfromPF[-2] = SMfromPF[-2]

        for ip in range(len(SMfromPF) - 3, 0, -2):
            # 拷贝对应的 pF 值
            MFPfromPF[ip - 1] = SMfromPF[ip - 1]
            # 对 PF 区间进行积分
            add = 0.0
            DeltaPF = SMfromPF[ip + 1] - SMfromPF[ip - 1]
            for i in range(len(self.Pgauss)):
                PFg = SMfromPF[ip - 1] + self.Pgauss[i] * DeltaPF
                CON = 10.0 ** CONDfromPF(PFg)
                add += CON * 10.0 ** PFg * self.elog10 * self.Wgauss[i]
            MFPfromPF[ip] = add * DeltaPF + MFPfromPF[ip + 2]
        Afgen.__init__(self, MFPfromPF)


class SoilLayer(HasTraits):
    """包含由多层水分平衡和SNOMIN要求的每层土壤的固有参数和衍生参数。

    :param layer: 一个包含该土壤层参数值的定义，详见下表。
    :param PFFieldcapacity: 定义田间持水量的pF值
    :param PFWiltingPoint: 定义萎蔫点的pF值

    每一层都需要定义以下属性。

    =============== ================================================================  =======================
    名称              描述                                                            单位
    =============== ================================================================  =======================
    CONDfromPF      饱和度以下条件下，水力传导率的以10为底的对数值关于pF的表型函数     log10(cm water d-1), -
    SMfromPF        土壤含水量关于pF的表型函数                                         m3 water m-3 soil, -
    Thickness       土层厚度                                                          cm
    FSOMI           初始土壤有机质含量比例                                             kg OM kg-1 soil
    CNRatioSOMI     初始土壤有机质C:N比                                                kg C kg-1 N
    RHOD            土壤容重                                                          g soil cm-3 soil
    Soil_pH         土壤层pH值                                                        -
    CRAIRC          根系通气所需的临界空隙率                                           m3 air m-3 soil
    =============== ================================================================  =======================


    根据土壤层定义，上表参数可推导出以下衍生属性。

    =============== ================================================================  =======================
    名称            描述                                                              单位
    =============== ================================================================  =======================
    PFfromSM        提供SMfromPF反映曲线的Afgen表                                      m3 water m-3 soil, -
    MFPfromPF       描述基质流势关于pF（水力头）关系的Afgen表                         cm2 d-1
    SM0             饱和状态(pF = -1)时的体积含水量                                   m3 water m-3 soil
    SMW             萎蔫点时的体积含水量                                               m3 water m-3 soil
    SMFCF           田间持水量时的体积含水量                                           m3 water m-3 soil
    WC0             饱和状态(pF = -1)时的水分总量（cm）                                cm water
    WCW             萎蔫点时的水分总量（cm）                                           cm water
    WCFC            田间持水量时水分总量（cm）                                         cm water
    CondFC          田间持水量下的土壤水力传导率                                       cm water d-1
    CondK0          饱和状态下的土壤水力传导率                                         cm water d-1
    =============== ================================================================  =======================

    最后，`rooting_status` 被初始化为 None（初始化时尚未知）。
    """
    SMfromPF = Instance(pFCurve)  # 土壤含水量关于pF的函数
    CONDfromPF = Instance(pFCurve)  # 水力传导率关于pF的函数
    PFfromSM = Instance(Afgen)  # SMfromPF的反函数
    MFPfromPF = Instance(MFPCurve)  # 基质流势关于pF的函数
    CNRatioSOMI = Float()  # 初始土壤有机质C:N比
    FSOMI = Float()  # 初始土壤有机质含量比例
    RHOD = Float()  # 土壤容重
    Soil_pH = Float()  # 土壤层pH
    CRAIRC = Float()  # 临界空隙率
    Thickness = Float()
    rooting_status = Enum(["rooted","partially rooted","potentially rooted","never rooted",])

    def __init__(self, layer, PFFieldCapacity, PFWiltingPoint):
        self.SMfromPF = pFCurve(layer.SMfromPF)
        self.CONDfromPF = pFCurve(layer.CONDfromPF)
        self.PFfromSM = self._invert_pF(layer.SMfromPF)
        self.MFPfromPF = MFPCurve(layer.SMfromPF, layer.CONDfromPF)
        self.CNRatioSOMI = layer.CNRatioSOMI
        self.FSOMI = layer.FSOMI
        self.RHOD = layer.RHOD
        self.CRAIRC = layer.CRAIRC
        self.Soil_pH = layer.Soil_pH

        if 5 <= layer.Thickness <= 250:
            self.Thickness = layer.Thickness
        else:
            msg = "Soil layer should have thickness between 5 and 250 cm. Current value: %f" % layer.Thickness
            raise exc.PCSEError(msg)

        self.SM0 = self.SMfromPF(-1.0)
        self.SMFCF = self.SMfromPF(PFFieldCapacity)
        self.SMW = self.SMfromPF(PFWiltingPoint)
        self.WC0 = self.SM0 * self.Thickness
        self.WCW = self.SMW * self.Thickness
        self.WCFC = self.SMFCF * self.Thickness
        self.CondFC = 10.0 ** self.CONDfromPF(PFFieldCapacity)
        self.CondK0 = 10.0 ** self.CONDfromPF(-1.0)
        self.rooting_status = None

        # 根据pF曲线计算本层的哈希值
        self._hash = hash((tuple(layer.SMfromPF), tuple(layer.CONDfromPF)))

    @property
    def Thickness_m(self):
        return self.Thickness * 1e-2

    @property
    def RHOD_kg_per_m3(self):
        return self.RHOD * 1e-3 * 1e06

    def _invert_pF(self, SMfromPF):
        """将SMfromPF表反转以获得由SM推导的pF
        """
        l = []
        for t in zip(reversed(SMfromPF[1::2]), reversed(SMfromPF[0::2])):
            l.extend(t)
        return Afgen(l)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return (
                self.__class__ == other.__class__ and
                self._hash == other._hash
        )


class SoilProfile(list):
    """
    该组件表示多层土壤水分平衡和SNOMIN所需的土壤剖面。

    :param parvalues: 一个 ParameterProvider 实例，用于获取土壤剖面描述，土壤参数应在`SoilProfileDescription`键下可用。

    本类本质上是一个容器，存储多个`SoilLayer`实例，并包含与根系生长、根系状态及根区水分提取等相关的附加逻辑。
    有关土壤层属性的详细信息请参考类 `SoilLayer` 的描述。

    土壤剖面的描述可通过YAML格式定义，下面给出了结构的示例。
    在该例中，首先在`SoilLayerTypes`段下定义三种土壤物理类型。
    然后，使用这些SoilLayerTypes来定义实际的剖面，包括2层10cm厚的TopSoil、3层分别为10、20和30cm厚的MidSoil、一层45cm厚的SubSoil，并最终以厚度200cm的SubSoilType结尾。
    仅最上面3层包含一定量的有机碳（FSOMI）。

    以下是土壤剖面数据结构的示例::

        SoilLayerTypes:
            TopSoil: &TopSoil
                SMfromPF: [-1.0,     0.366,
                            1.0,     0.338,
                            1.3,     0.304,
                            1.7,     0.233,
                            2.0,     0.179,
                            2.3,     0.135,
                            2.4,     0.123,
                            2.7,     0.094,
                            3.0,     0.073,
                            3.3,     0.059,
                            3.7,     0.046,
                            4.0,     0.039,
                            4.17,    0.037,
                            4.2,     0.036,
                            6.0,     0.02]
                CONDfromPF: [-1.0,     1.8451,
                              1.0,     1.02119,
                              1.3,     0.51055,
                              1.7,    -0.52288,
                              2.0,    -1.50864,
                              2.3,    -2.56864,
                              2.4,    -2.92082,
                              2.7,    -4.01773,
                              3.0,    -5.11919,
                              3.3,    -6.22185,
                              3.7,    -7.69897,
                              4.0,    -8.79588,
                              4.17,   -9.4318,
                              4.2,    -9.5376,
                              6.0,   -11.5376]
                CRAIRC:  0.090
                CNRatioSOMI: 9.0
                RHOD: 1.406
                Soil_pH: 7.4
                SoilID: TopSoil
            MidSoil: &MidSoil
                SMfromPF: [-1.0,     0.366,
                            1.0,     0.338,
                            1.3,     0.304,
                            1.7,     0.233,
                            2.0,     0.179,
                            2.3,     0.135,
                            2.4,     0.123,
                            2.7,     0.094,
                            3.0,     0.073,
                            3.3,     0.059,
                            3.7,     0.046,
                            4.0,     0.039,
                            4.17,    0.037,
                            4.2,     0.036,
                            6.0,     0.02]
                CONDfromPF: [-1.0,     1.8451,
                              1.0,     1.02119,
                              1.3,     0.51055,
                              1.7,    -0.52288,
                              2.0,    -1.50864,
                              2.3,    -2.56864,
                              2.4,    -2.92082,
                              2.7,    -4.01773,
                              3.0,    -5.11919,
                              3.3,    -6.22185,
                              3.7,    -7.69897,
                              4.0,    -8.79588,
                              4.17,   -9.4318,
                              4.2,    -9.5376,
                              6.0,   -11.5376]
                CRAIRC:  0.090
                CNRatioSOMI: 9.0
                RHOD: 1.406
                Soil_pH: 7.4
                SoilID: MidSoil_10
            SubSoil: &SubSoil
                SMfromPF: [-1.0,     0.366,
                            1.0,     0.338,
                            1.3,     0.304,
                            1.7,     0.233,
                            2.0,     0.179,
                            2.3,     0.135,
                            2.4,     0.123,
                            2.7,     0.094,
                            3.0,     0.073,
                            3.3,     0.059,
                            3.7,     0.046,
                            4.0,     0.039,
                            4.17,    0.037,
                            4.2,     0.036,
                            6.0,     0.02]
                CONDfromPF: [-1.0,     1.8451,
                              1.0,     1.02119,
                              1.3,     0.51055,
                              1.7,    -0.52288,
                              2.0,    -1.50864,
                              2.3,    -2.56864,
                              2.4,    -2.92082,
                              2.7,    -4.01773,
                              3.0,    -5.11919,
                              3.3,    -6.22185,
                              3.7,    -7.69897,
                              4.0,    -8.79588,
                              4.17,   -9.4318,
                              4.2,    -9.5376,
                              6.0,   -11.5376]
                CRAIRC:  0.090
                CNRatioSOMI: 9.0
                RHOD: 1.406
                Soil_pH: 7.4
                SoilID: SubSoil_10
        SoilProfileDescription:
            PFWiltingPoint: 4.2
            PFFieldCapacity: 2.0
            SurfaceConductivity: 70.0 # 表层导水率 cm / day
            SoilLayers:
            -   <<: *TopSoil
                Thickness: 10
                FSOMI: 0.02
            -   <<: *TopSoil
                Thickness: 10
                FSOMI: 0.02
            -   <<: *MidSoil
                Thickness: 10
                FSOMI: 0.01
            -   <<: *MidSoil
                Thickness: 20
                FSOMI: 0.00
            -   <<: *MidSoil
                Thickness: 30
                FSOMI: 0.00
            -   <<: *SubSoil
                Thickness: 45
                FSOMI: 0.00
            SubSoilType:
                <<: *SubSoil
                Thickness: 200
            GroundWater: null
    """
    
    def __init__(self, parvalues):
        list.__init__(self)

        sp = DotMap(parvalues["SoilProfileDescription"])
        for layer_properties in sp.SoilLayers:
            layer = SoilLayer(layer_properties, sp.PFFieldCapacity, sp.PFWiltingPoint)
            self.append(layer)
        for attr, value in sp.items():
            if attr == "SoilLayers":
                continue
            if attr == "SubSoilType":
                value = SoilLayer(value, sp.PFFieldCapacity, sp.PFWiltingPoint)
            setattr(self, attr, value)

    def determine_rooting_status(self, RD, RDM):
        """
        确定土壤各层的生根状态并更新各层权重。

        土层分为已生根、部分生根、潜在生根、从未生根四种状态。
        状态存储在 layer.rooting_status 中。

        注意：本方法要求最大根系深度与土层边界重合。

        :param RD: 当前根系深度
        :param RDM: 最大根系深度
        """
        upper_layer_boundary = 0
        lower_layer_boundary = 0
        for layer in self:
            lower_layer_boundary += layer.Thickness
            if lower_layer_boundary <= RD:
                layer.rooting_status = "rooted"
            elif upper_layer_boundary < RD < lower_layer_boundary:
                layer.rooting_status = "partially rooted"
            elif RD < lower_layer_boundary <= RDM:
                layer.rooting_status = "potentially rooted"
            else:
                layer.rooting_status = "never rooted"
            upper_layer_boundary = lower_layer_boundary

        self._compute_layer_weights(RD)

    def _compute_layer_weights(self, RD):
        """
        根据当前根系深度计算各土层的权重。

        :param RD: 当前根系深度
        """
        lower_layer_boundary = 0
        for layer in self:
            lower_layer_boundary += layer.Thickness
            if layer.rooting_status == "rooted":
                layer.Wtop = 1.0
                layer.Wpot = 0.0
                layer.Wund = 0.0
            elif layer.rooting_status == "partially rooted":
                layer.Wtop = 1.0 - (lower_layer_boundary - RD) / layer.Thickness
                layer.Wpot = 1.0 - layer.Wtop
                layer.Wund = 0.0
            elif layer.rooting_status == "potentially rooted":
                layer.Wtop = 0.0
                layer.Wpot = 1.0
                layer.Wund = 0.0
            elif layer.rooting_status == "never rooted":
                layer.Wtop = 0.0
                layer.Wpot = 0.0
                layer.Wund = 1.0
            else:
                msg = "Unknown rooting status: %s" % layer.rooting_status
                raise exc.PCSEError(msg)

    def validate_max_rooting_depth(self, RDM):
        """验证最大根系深度是否与某个土层边界重合。

        :param RDM: 最大可生根深度
        :return: True 或 False
        """
        tiny = 0.01
        lower_layer_boundary = 0
        for layer in self:
            lower_layer_boundary += layer.Thickness
            if abs(RDM - lower_layer_boundary) < tiny:
                break
        else:  # 没有遇到 break
            msg = "Current maximum rooting depth (%f) does not coincide with a layer boundary!" % RDM
            raise exc.PCSEError(msg)

    def get_max_rootable_depth(self):
        """返回土壤的最大可生根深度。

        这里我们假设最大可生根深度等于最后一个土层的下边界。

        :return: 最大可生根深度（单位：cm）
        """
        LayerThickness = [l.Thickness for l in self]
        LayerLowerBoundary = list(np.cumsum(LayerThickness))
        return max(LayerLowerBoundary)