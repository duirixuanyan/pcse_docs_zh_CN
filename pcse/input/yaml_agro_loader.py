__author__ = 'wit015'
import sys, os
import yaml
from .. import exceptions as exc

class YAMLAgroManagementReader(list):
    """读取PCSE agromanagement文件（YAML格式）。

    :param fname: agromanagement文件的文件名。如果fname不是绝对路径或相对路径，则假定文件位于当前工作目录。
    """

    def __init__(self, fname):
        fname_fp = os.path.normpath(os.path.abspath(fname))
        if not os.path.exists(fname_fp):
            msg = "Cannot find agromanagement file: %s" % fname_fp
            raise exc.PCSEError(msg)

        # UTF-8打开
        # with open(fname) as fp:
        with open(fname, 'r', encoding='utf-8') as fp:
            try:
                r = yaml.safe_load(fp)
            except yaml.YAMLError as e:
                msg = "Failed parsing agromanagement file %s: %s" % (fname_fp, e)
                raise exc.PCSEError(msg)

        list.__init__(self, r['AgroManagement'])

    def __str__(self):
        return yaml.dump(self, default_flow_style=False)
