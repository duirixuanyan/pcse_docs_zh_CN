import os
from pathlib import Path
from .. import exceptions as exc
import textwrap


class ConfigurationLoader(object):
    """用于从PCSE配置文件加载模型配置的类

        :param config: 包含模型配置的文件名字符串
        """
    _required_attr = ("CROP", "SOIL", "AGROMANAGEMENT", "OUTPUT_VARS", "OUTPUT_INTERVAL",
                      "OUTPUT_INTERVAL_DAYS", "SUMMARY_OUTPUT_VARS")
    defined_attr = []
    model_config_file = None
    description = None

    def __init__(self, config):

        if not isinstance(config, (str, Path)):
            msg = ("Keyword 'config' should provide the name of the file (string or pathlib.Path)" +
                   "storing the configuration of the model PCSE should run.")
            raise exc.PCSEError(msg)

        # 检查模型配置文件是绝对路径还是相对路径
        # 如果不是，假设它位于PCSE分发版的 'conf/' 文件夹中
        config = Path(config)
        if config.is_absolute():
            mconf = config
        else:
            this_dir = Path(__file__).parent
            pcse_dir = this_dir.parent
            mconf = pcse_dir / "conf" / config
        model_config_file = mconf.resolve()

        # 检查配置文件是否存在
        if not model_config_file.exists():
            msg = "PCSE model configuration file does not exist: %s" % model_config_file
            raise exc.PCSEError(msg)
        # 保存以备后续使用
        self.model_config_file = model_config_file

        # 使用execfile加载文件
        try:
            loc = {}
            bytecode = compile(open(model_config_file).read(), model_config_file, 'exec')
            exec(bytecode, {}, loc)
        except Exception as e:
            msg = "Failed to load configuration from file '%s' due to: %s"
            msg = msg % (model_config_file, e)
            raise exc.PCSEError(msg)

        # 添加描述性头部以备后续使用
        if "__doc__" in loc:
            desc = loc.pop("__doc__")
            if len(desc) > 0:
                self.description = desc
                if self.description[-1] != "\n":
                    self.description += "\n"

        # 遍历配置文件中的属性
        for key, value in list(loc.items()):
            if key.isupper():
                self.defined_attr.append(key)
                setattr(self, key, value)

        # 检查是否有缺失的强制属性
        req = set(self._required_attr)
        diff = req.difference(set(self.defined_attr))
        if diff:
            msg = "One or more compulsory configuration items missing: %s" % list(diff)
            raise exc.PCSEError(msg)

    def __str__(self):
        # 将模型配置文件的信息输出为字符串
        msg = "PCSE ConfigurationLoader from file:\n"
        msg += "  %s\n\n" % self.model_config_file
        if self.description is not None:
            msg += ("%s Header of configuration file %s\n"% ("-"*20, "-"*20))
            msg += self.description
            if msg[-1] != "\n":
                msg += "\n"
            msg += ("%s Contents of configuration file %s\n"% ("-"*19, "-"*19))
        for k in self.defined_attr:
             r = "%s: %s" % (k, getattr(self, k))
             msg += (textwrap.fill(r, subsequent_indent="  ") + "\n")
        return msg

    def update_output_variable_lists(self, output_vars=None, summary_vars=None, terminal_vars=None):
        """
        # 更新配置文件中定义的输出变量列表

        # 这样做的好处是，有时你可能希望灵活地访问模型配置文件标准变量列表之外的其他模型变量。
        # 更优雅的方式是定义你自己的配置文件，但这种方式在jupyter notebook和探索性分析中特别灵活。

        # 注意：根据变量类型，表现会有所不同。list和string输入会扩展变量列表，而set/tuple输入会替换当前列表。

        :param output_vars: 要添加/替换到OUTPUT_VARS配置变量的变量名
        :param summary_vars: 要添加/替换到SUMMARY_OUTPUT_VARS配置变量的变量名
        :param terminal_vars: 要添加/替换到TERMINAL_OUTPUT_VARS配置变量的变量名
        """
        config_varnames = ["OUTPUT_VARS", "SUMMARY_OUTPUT_VARS", "TERMINAL_OUTPUT_VARS"]
        for varitems, config_varname in zip([output_vars, summary_vars, terminal_vars], config_varnames):
            if varitems is None:
                continue
            else:
                if isinstance(varitems, str):  # 字符串：扩展当前列表
                    getattr(self, config_varname).extend(varitems.split())
                elif isinstance(varitems, list):  # 列表：扩展当前列表
                    getattr(self, config_varname).extend(varitems)
                elif isinstance(varitems, (tuple, set)):  # 元组/集合：替换当前列表
                    setattr(self, config_varname, list(varitems))
                else:
                    msg = "Unrecognized input for `output_vars` to engine(): %s" % output_vars
                    print(msg)
