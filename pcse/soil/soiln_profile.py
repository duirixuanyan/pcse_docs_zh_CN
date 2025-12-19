# -*- coding: utf-8 -*-
# Copyright (c) 2004-2024 Wageningen Environmental Research, Wageningen-UR
# Herman Berghuijs (herman.berghuijs@wur.nl) 和 Allard de Wit (allard.dewit@wur.nl)，2024年1月

from math import sqrt
import numpy as np
from ..traitlets import Float, Int, Instance, Enum, Unicode, Bool, HasTraits, List
from ..util import limit, Afgen, merge_dict, DotMap

from .. import exceptions as exc


class pFCurve(Afgen):
    """Pf 曲线需要检查：
    - 数组长度为偶数
    - 至少有3对 xy 数据
    - pF 应从 pF = -1 开始，到 pF=6 结束
    - 随着 pF 增大，SM/cond 的值应减小

    """
    pass

class SoilNLayer(HasTraits):
    """
    包含了 SNOMIN 所用每一土层的内在和派生属性。以下属性从 *.soil 输入文件读取，或者由读取到的变量推算出来，并针对每一土层定义：

    =============== ================================================ =======================
    名称             描述                                            单位
    =============== ================================================ =======================
    CNRatioSOMI     土壤有机质的初始C:N比                           kg C kg-1 N
    CONDfromPF      pF函数的10进制对数形式的不饱和导水率表          log10(cm water d-1), -
    FSOMI           土层中有机质的初始比例                          kg OM kg-1 soil
    PFFieldCapacity 土壤蓄水容重田间持水量所对应pF                  -
    PFWiltingPoint  土壤湿度达到永久萎蔫点所对应pF                  -
    RHOD            土壤的容重                                      g soil cm-3 soil
    SMfromPF        描述土壤湿度(pF)关系的表函数                    m3 water m-3 soil, -
    SMsat           饱和时的土壤含水量                              m3 water m-3 soil
    Soil_pH         土层的pH值                                      -
    Thickness       土层厚度                                        cm
    =============== ================================================ =======================
    """

    SMfromPF = Instance(pFCurve)  # 土壤湿度（SM）与pF的关系
    PFfromSM = Instance(Afgen)  # SMfromPF表的逆函数，用于由含水量求pF
    SMsat = Float()  # 土壤饱和含水量
    Thickness = Float()  # 土层厚度
    rooting_status = Enum(["rooted","partially rooted","potentially rooted","never rooted",])  # 根系状态

    # 土壤N模型参数

    def __init__(self, layer, PFFieldCapacity, PFWiltingPoint):
        self.SMfromPF = pFCurve(layer.SMfromPF)
        self.PFfromSM = self._invert_pF(layer.SMfromPF)

        if 5 <= layer.Thickness <= 250:
            self.Thickness = layer.Thickness
        else:
            msg = "Soil layer should have thickness between 5 and 250 cm. Current value: %f" % layer.Thickness
            raise exc.PCSEError(msg)

        self.SM0 = self.SMfromPF(-1.0)
        self.SMFCF = self.SMfromPF(PFFieldCapacity)
        self.SMW = self.SMfromPF(PFWiltingPoint)
        self.rooting_status = None
        self.Soil_pH = layer.Soil_pH

        self.CNRatioSOMI = layer.CNRatioSOMI
        self.FSOMI = layer.FSOMI
        self.RHOD = layer.RHOD

        # 计算本层的hash值
        self._hash = hash((tuple(layer.SMfromPF), tuple(layer.CONDfromPF)))

    @property
    def Thickness_m(self):
        # 返回土层厚度（单位：米）
        return self.Thickness * 1e-2

    @property
    def RHOD_kg_per_m3(self):
        # 返回土层密度（单位：kg/m3）
        return self.RHOD * 1e-3 * 1e06

    def _invert_pF(self, SMfromPF):
        """将SMfromPF表反转，用于根据含水量求pF"""
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

class SoilNProfile(list):
    
    def __init__(self, parvalues):
        list.__init__(self)

        sp = DotMap(parvalues["SoilProfileDescription"])
        for layer_properties in sp.SoilLayers:
            layer = SoilNLayer(layer_properties, sp.PFFieldCapacity, sp.PFWiltingPoint)
            self.append(layer)
        for attr, value in sp.items():
            if attr == "SoilLayers":
                continue
            if attr == "SubSoilType":
                value = SoilNLayer(value, sp.PFFieldCapacity, sp.PFWiltingPoint)
            setattr(self, attr, value)

    def determine_rooting_status(self, RD, RDM):
        """确定各土层的根系状态，并更新层权重。

        土层的根系状态可以为“已生根（rooted）”、“部分生根（partially rooted）”、“有潜力生根（potentially rooted）”或“未生根（never rooted）”。
        该状态存储于 layer.rooting_status。

        注意：本函数要求最大根系深度（RDM）正好位于某一土层的边界。

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
        """根据当前根系深度计算各层权重。

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
        """验证最大根系深度是否与某一土层边界重合。

        :param RDM: 最大可生根深度
        :return: True 或 False
        """
        tiny = 0.01
        lower_layer_boundary = 0
        for layer in self:
            lower_layer_boundary += layer.Thickness
            if abs(RDM - lower_layer_boundary) < tiny:
                break
        else:  # 没有break
            msg = "Current maximum rooting depth (%f) does not coincide with a layer boundary!" % RDM
            raise exc.PCSEError(msg)

    def get_max_rootable_depth(self):
        """返回土壤的最大可生根深度。

        这里假设最大可生根深度等于最后一层的下边界。

        :return: 最大可生根深度（单位：cm）
        """
        LayerThickness = [l.Thickness for l in self]
        LayerLowerBoundary = list(np.cumsum(LayerThickness))
        return max(LayerLowerBoundary)