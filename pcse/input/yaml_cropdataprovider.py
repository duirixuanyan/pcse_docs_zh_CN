# -*- coding: utf-8 -*-
# 版权所有 (c) 2004-2022 Wageningen Environmental Research，Wageningen-UR
# Allard de Wit (allard.dewit@wur.nl), 2022年8月
import logging
import os, sys
import pickle
import posixpath
import time

import yaml
import requests

from ..models import Wofost72_PP
from ..base import MultiCropDataProvider
from .. import exceptions as exc
from .. import settings
from ..util import version_tuple


class YAMLCropDataProvider(MultiCropDataProvider):
    """
    一个用于读取存储在YAML格式中的作物参数集的作物数据提供者。

        :param model: 从`pcse.models`导入的`model`。这将允许YAMLCropDataProvider针对每个模型版本选择正确的分支。如果未提供，则默认使用`pcse.models.Wofost72_PP`。
        :param fpath: 包含YAML文件的目录的完整路径
        :param repository: 包含YAML文件的仓库URL。该URL应为*raw* 内容（例如以'https://raw.githubusercontent.com'开头）
        :param force_reload: 如果为True，则忽略缓存文件并重新加载所有参数（默认False）。

    此作物数据提供者可以读取和存储多个作物的参数集，这与大多数其他只能保存单一作物数据的提供者不同。因此，该作物数据提供者适用于在不同作物类型间进行轮作，因为数据提供者可以切换当前激活的作物。

    最基本的用法是无需参数调用YAMLCropDataProvider。它将从我的github仓库 https://github.com/ajwdewit/WOFOST_crop_parameters/tree/wofost72 拉取WOFOST 7.2的作物参数::

        >>> from pcse.input import YAMLCropDataProvider
        >>> p = YAMLCropDataProvider()
        >>> print(p)
        作物参数已加载自: https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost72
        YAMLCropDataProvider - 未设置作物和品种：未激活作物参数集！

    若需指定特定模型和版本，只需将模型传递给CropDataProvider::
        >>> from pcse.models import Wofost81_PP
        >>> p = YAMLCropDataProvider(Wofost81_PP)
        >>> print(p)
        作物参数已加载自: https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost81
        作物和品种未设置：未激活作物参数集！

    所有作物和品种已从YAML文件加载，但尚未激活任何作物。因此，需要激活特定的作物与品种：

        >>> p.set_active_crop('wheat', 'Winter_wheat_101')
        >>> print(p)
        作物参数已加载自: https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost81
        YAMLCropDataProvider - 当前激活作物 'wheat'，品种为 'Winter_wheat_101'
        可用作物参数:
         {'DTSMTB': [0.0, 0.0, 30.0, 30.0, 45.0, 30.0], 'NLAI_NPK': 1.0, 'NRESIDLV': 0.004,
         'KCRIT_FR': 1.0, 'RDRLV_NPK': 0.05, 'TCPT': 10, 'DEPNR': 4.5, 'KMAXRT_FR': 0.5,
         ...
         ...
         'TSUM2': 1194, 'TSUM1': 543, 'TSUMEM': 120}

    此外，也可以从本地文件系统加载YAML参数文件::

        >>> p = YAMLCropDataProvider(fpath=r"D:\\UserData\\sources\\WOFOST_crop_parameters")
        >>> print(p)
        YAMLCropDataProvider - 未设置作物和品种：未激活作物参数集！

    最后，可以通过指定你的github仓库URL来拉取你fork的仓库的数据::

        >>> p = YAMLCropDataProvider(repository=\"https://raw.githubusercontent.com/<your_account>/WOFOST_crop_parameters/<branch>/\")

    为了提升参数加载性能，YAMLCropDataProvider会创建一个缓存文件，该文件比直接从YAML读取恢复速度更快。
    当从本地文件系统读取YAML文件时，将确保在本地YAML文件被更新后重新创建缓存文件。然而，需要强调的是当从URL获取参数时无法做到这一点，
    存在从过时缓存文件读取参数的风险。默认情况下，缓存文件将在7天后被重新创建，如需强制更新，请使用`force_reload=True`强制从URL加载参数。
    """
    model_version_branches = yaml.safe_load(f"""
    WOFOST:
        "7.2": https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost72
        "7.3": https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost73
        "8.0": https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost80
        "8.1": https://raw.githubusercontent.com/ajwdewit/WOFOST_crop_parameters/wofost81
    LINGRA:
        "1.0": https://raw.githubusercontent.com/ajwdewit/lingra_crop_parameters/lingra10
    """)

    current_crop_name = None
    current_variety_name = None

    # 数据提供者与YAML参数文件版本的兼容性
    compatible_version = "1.0.0"

    def __init__(self, model=Wofost72_PP, fpath=None, repository=None, force_reload=False):
        MultiCropDataProvider.__init__(self)

        # 如果强制重新加载或加载缓存失败
        if force_reload is True or self._load_cache(fpath, model) is False:

            if fpath is not None:
                self.repository = os.path.abspath(fpath)
                self.read_local_repository(fpath)

            elif repository is not None:
                self.repository = repository
                self.read_remote_repository(repository)

            else:
                try:
                    self.repository = self.model_version_branches[model.__cropmodel__][model.__cropmodelversion__]
                    self.logger.info("Using crop parameter repository defined for %s",  self.repository)
                    self.read_remote_repository(self.repository)
                except Exception as e:
                    msg = f"Error reading crop parameter repository for {model.__cropmodel__} version {model.__cropmodelversion__}: {e}"
                    raise exc.PCSEError(msg)

            # 缓存模型、版本、仓库、兼容版本和参数数据到本地
            with open(self._get_cache_fname(fpath), "wb") as fp:
                dmp = (model.__cropmodel__, model.__cropmodelversion__, self.repository, self.compatible_version, self._store)
                pickle.dump(dmp, fp, pickle.HIGHEST_PROTOCOL)

    def read_local_repository(self, fpath):
        """
        从本地文件系统读取作物 YAML 文件

        :param fpath: YAML 文件在文件系统上的位置
        """
        yaml_file_names = self._get_yaml_files(fpath)
        for crop_name, yaml_fname in yaml_file_names.items():
            # 用UTF-8打开
            # with open(yaml_fname) as fp:
            with open(yaml_fname, encoding='utf-8') as fp:
                parameters = yaml.safe_load(fp)
            self._check_version(parameters, crop_fname=yaml_fname)
            self._add_crop(crop_name, parameters)

    def read_remote_repository(self, repository):
        """
        从远程 git 仓库读取作物参数文件

        :param repository: 仓库的 url，指向可以获取原始输入文件的地址。
            例如 GitHub: https://raw.githubusercontent.com/<username>/WOFOST_crop_parameters/<branchname>
        :return:
        """

        url = posixpath.join(repository, "crops.yaml")
        response = requests.get(url)
        crop_types = yaml.safe_load(response.text)["available_crops"]

        for crop_name in crop_types:
            url = posixpath.join(repository, crop_name + ".yaml")
            response = requests.get(url)
            parameters = yaml.safe_load(response.text)
            self._check_version(parameters, crop_name)
            self._add_crop(crop_name, parameters)

    def _get_cache_fname(self, fpath):
        """
        返回 CropDataProvider 缓存文件的文件名。
        """
        cache_fname = "%s.pkl" % self.__class__.__name__
        if fpath is None:
            cache_fname_fp = os.path.join(settings.METEO_CACHE_DIR, cache_fname)
        else:
            cache_fname_fp = os.path.join(fpath, cache_fname)
        return cache_fname_fp

    def _load_cache(self, fpath, model):
        """如果可能，加载缓存文件并返回True，否则返回False。
        """
        try:
            cache_fname_fp = self._get_cache_fname(fpath)
            if not os.path.exists(cache_fname_fp):
                return False

            # 获取缓存文件的修改日期
            cache_date = os.stat(cache_fname_fp).st_mtime
            # 如果缓存文件早于7天前，则重新加载
            if cache_date < time.time() - (7 * 86400):
                return False

            # 这里检查缓存文件是否反映了YAML文件的内容。
            # 这只适用于文件，不适用于github仓库
            if fpath is not None:
                yaml_file_names = self._get_yaml_files(fpath)
                yaml_file_dates = [os.stat(fn).st_mtime for crop,fn in yaml_file_names.items()]
                # 确保缓存文件比任何YAML文件都新
                if any([d > cache_date for d in yaml_file_dates]):
                    return False

            # 现在开始加载缓存文件
            with open(cache_fname_fp, "rb") as fp:
                cropmodel, cropmodelversion, self.repository, version, store = pickle.load(fp)

            if cropmodel == model.__cropmodel__ and cropmodelversion == model.__cropmodelversion__ and \
                version_tuple(version) == version_tuple(self.compatible_version):
                self._store = store
                self.clear()
                return True

        except Exception as e:
            pass

        return False

    def _check_version(self, parameters, crop_fname):
        """检查参数输入的版本与此数据提供程序支持的版本是否一致。

        如果参数集不兼容，则引发异常。

        :param parameters: 通过YAML加载的参数集
        """
        try:
            v = parameters['Version']
            if version_tuple(v) != version_tuple(self.compatible_version):
                msg = "Version supported by %s is %s, while parameter set version is %s!"
                raise exc.PCSEError(msg % (self.__class__.__name__, self.compatible_version, parameters['Version']))
        except Exception as e:
            msg = f"Version check failed on crop parameter file: {crop_fname}"
            raise exc.PCSEError(msg)

    def _add_crop(self, crop_name, parameters):
        """为给定作物存储不同品种的参数集。
        """
        variety_sets = parameters["CropParameters"]["Varieties"]
        self._store[crop_name] = variety_sets

    def _get_yaml_files(self, fpath):
        """返回指定路径下所有以*.yaml结尾的文件。
        """
        fname = os.path.join(fpath, "crops.yaml")
        if not os.path.exists(fname):
            msg = f"Cannot find 'crops.yaml' at {fname}"
            raise exc.PCSEError(msg)
        # 用UTF-8打开
        # crop_names = yaml.safe_load(open(fname))["available_crops"]
        crop_names = yaml.safe_load(open(fname, encoding='utf-8'))["available_crops"]
        crop_yaml_fnames = {crop: os.path.join(fpath, crop + ".yaml") for crop in crop_names}
        for crop, fname in crop_yaml_fnames.items():
            if not os.path.exists(fname):
                msg = f"Cannot find yaml file for crop '{crop}': {fname}"
                raise RuntimeError(msg)
        return crop_yaml_fnames

    def set_active_crop(self, crop_name, variety_name):
        """设置内部字典中指定作物名称和品种名称的参数

        在设置前会先清空内部字典中已激活的作物参数集。

        :param crop_name: 作物名称
        :param variety_name: 给定作物的品种名称
        """
        self.clear()
        if crop_name not in self._store:
            msg = f"Crop name '{crop_name}' not available in {self.__class__.__name__}"
            raise exc.PCSEError(msg)
        variety_sets = self._store[crop_name]
        if variety_name not in variety_sets:
            msg = f"Variety name '{variety_name}' not available for crop '{crop_name}' in {self.__class__.__name__}"
            raise exc.PCSEError(msg)

        self.current_crop_name = crop_name
        self.current_variety_name = variety_name

        # 从输入中获取参数名称和值（忽略描述和单位）
        parameters = {k: v[0] for k, v in variety_sets[variety_name].items() if k != "Metadata"}
        # 用此品种的参数值更新内部字典
        self.update(parameters)

    def get_crops_varieties(self):
        """返回可用作物及其每个作物下品种的名称。

        :return: 一个字典，格式为 {'crop_name1': ['variety_name1', 'variety_name2', ...],
                                   'crop_name2': [...]} 
        """
        return {k: v.keys() for k, v in self._store.items()}

    def print_crops_varieties(self):
        """在屏幕上打印所有可用作物及其品种的列表。
        """
        msg = ""
        for crop, varieties in self.get_crops_varieties().items():
            msg += f"crop '{crop}', available varieties:\n"
            for var in varieties:
                msg += f" - '{var}'\n"
        print(msg)

    def __str__(self):
        if not self:
            msg = f"Crop parameters loaded from: {self.repository}\n" \
                  f"Crop and variety not set: no active crop parameter set!\n"
            return msg
        else:
            msg = f"Crop parameters loaded from: {self.repository}\n"
            msg += "%s - current active crop '%s' with variety '%s'\n" % \
                   (self.__class__.__name__, self.current_crop_name, self.current_variety_name)
            msg += "Available crop parameters:\n %s" % str(dict.__str__(self))
            return msg

    @property
    def logger(self):
        # 获取对应模块和类的日志对象
        loggername = "%s.%s" % (self.__class__.__module__,
                                self.__class__.__name__)
        return logging.getLogger(loggername)