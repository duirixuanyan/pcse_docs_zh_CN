from __future__ import print_function
import os
from .exceptions import PCSEError
import textwrap

class Rerunner(list):
    """用于读取和遍历 FSE 重运行文件的类。

    重运行文件用于使用不同输入执行多个模型运行。对于不易编写脚本和调整的 FSE 模型，这尤其有用。
    对于 PCSE 模型，这一功能意义不大，因为模型可以轻松嵌入在 python 循环中，以遍历输入值的组合。

    尽管如此，由于重运行文件的概念在瓦赫宁根仍然很流行，因此添加了此类，以方便喜欢使用重运行文件的用户。

    本类解析重运行文件，并将每个重运行作为字典列表存储。文件中每个新的重运行应以“RUNNAME='<run name>';”开头的行分隔。

    示例：

        >>>reruns = Rerunner('reruns.txt')
        >>>for rerun in reruns:
            # 这里进行处理..
    """

    def __init__(self, rerun_file):

        try:
            self.rerun_file_fp = os.path.abspath(rerun_file)
            with open(self.rerun_file_fp) as fp:
                lines = fp.readlines()
        except IOError as exc:
            msg = "Failed opening '%s': %s" % (self.rerun_file_fp, exc.message)
            raise PCSEError(msg)

        rerun_set = None
        try:
            for i, line in enumerate(lines):
                ln = i+1
                # 去除首尾空白字符
                line = line.strip() #.replace(" ","")
                if not line:  # 空行跳过
                    continue
                if line.startswith("*"):    # 以 * 开头为注释行跳过
                    continue
                # 检查分号结尾，可根据需要取消注释
                # if not line.endswith(";"):
                #     msg = "';' character missing on line %i" % ln
                #     raise PCSEError(msg)

                name, strvalue = line.split("=", 1)
                name = name.strip()
                value = eval(strvalue)

                # 新的运行块以 RUNNAM 开头
                if name.upper() == "RUNNAM":
                    if not rerun_set is None:
                        self.append(rerun_set)
                    rerun_set = {name: value}
                else:
                    rerun_set[name] = value

            # 添加最后一个 rerun_set
            if rerun_set is not None:
                self.append(rerun_set)

        except (SyntaxError, ValueError) as exc:
            msg = "Failed parsing line %i." % ln
            raise PCSEError(msg)

    def __str__(self):

        msg = "Rerun loaded from: %s\n" % self.rerun_file_fp
        if len(self) > 0:
            msg += ("Containing %i rerun sets\n" % len(self))
            d = "\n".join(textwrap.wrap("First rerun set: %s\n" % self[0], subsequent_indent="    "))
            msg += (d + "\n")
            d = "\n".join(textwrap.wrap("Last rerun set: %s\n" % self[-1], subsequent_indent="    "))
            msg += d
        else:
            msg += "File contains no rerun sets.\n"
        return msg
