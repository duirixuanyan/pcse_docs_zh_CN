PCSE 背景
==================

瓦赫宁根的作物模型
-------------------------

`Python Crop Simulation Environment` 的开发源于需要对瓦赫宁根开发的作物模拟模型进行重新实现。许多瓦赫宁根的作物模拟模型最初是用 FORTRAN77 或 `FORTRAN Simulation Translator (FST)` 开发的。尽管这种方式产生了高质量且计算性能良好的模型，但 FORTRAN 语言固有的限制也越来越明显：

* 模型的结构通常较为单一，内部各部分高度耦合。替换某部分为其他模拟方法并不容易。

* 模型依赖于基于文件的输入/输出（I/O），这很难调整。例如，在 FORTRAN 中与数据库的接口开发非常繁琐。

* 一般来说，对于像 FORTRAN 这样的低级语言，即使是很简单的功能也需要写很多代码，而且容易出错，尤其是对于只具备有限编程开发经验的农学家和作物科学家来说更是如此。

为了解决以上这些局限性，开发了 Python Crop Simulation Environment (PCSE)。它为开发模拟模型提供了一个环境，并内置了多种作物模拟模型的实现。PCSE 采用纯 Python 编写，这使得它更加灵活、易于修改和扩展，可以方便地与数据库、图形用户界面、可视化工具以及数值/统计包集成。PCSE 还有若干有趣的特点：

* 采用纯 Python 实现。核心系统本身只依赖很少的标准库之外的包。但是很多数据提供者需要另外安装特定包。这些包大多数可以通过 Python Package Index (PyPI) 自动安装（如 `SQLAlchemy`, `PyYAML`, `openpyxl`, `requests`），而模型输出结果的处理则推荐用 `pandas` DataFrames 完成。

* 模块化设计，可以灵活快捷地新增或更换组件，同时具备一个简洁但功能强大的模块间变量通信方法。

* 类似于 FST，PCSE 通过显式区分参数、变化率变量和状态变量来促进良好模型设计。除此之外，PCSE 会自动负责模块初始化、变化率的计算、状态变量的更新及仿真结束时需要的动作。

* 输入/输出与模拟模型本身完全隔离。因此，PCSE 的模型能轻松读取和写入文本文件、数据库，以及如 HDF 或 NetCDF 这类科学数据格式。此外，PCSE 模型还可很容易地嵌入，例如 docker 容器，以构建基于作物模型的 web API。

* 内置的程序模块测试功能，确保系统的完整性

为什么选择 Python
-----------------
PCSE 最初的开发主要是出于科学研究的需要，希望能够快速适应模型并测试新想法。
在科学领域中，Python 正迅速成为实现算法、可视化和探索性分析的工具，这得益于其清晰的语法和易用性。另一个优点是 Python 的 C 实现可以很容易与 FORTRAN 编写的例程接口，因此许多 FORTRAN 例程可以被 PCSE 实现的模拟模型重用。

目前有许多用于数值分析的包（如 NumPy, SciPy）、可视化的包（如 MatPlotLib, Chaco）、分布式计算的包（如 IPython, pyMPI）以及数据库接口的包（如 SQLAlchemy）。此外，对于统计分析，还可以通过 Rpy 或 Rserve 等与 R-project 建立接口。最后，Python 是一种开源解释型编程语言，几乎可以运行于任何硬件和操作系统上。

鉴于上述原因，很快就认识到 Python 是一个很好的选择。虽然 PCSE 是为科学目的开发的，但它已经被用于生产环境的各项任务，并被集成进基于容器的 web 服务。

PCSE 的发展历史
----------------

在 4.1 版本之前，PCSE 被称为 "PyWOFOST"，其主要目标是提供 WOFOST 作物模拟模型的 Python 实现。
然而，随着系统的发展，事实证明该系统可以用于实现、扩展或混合（作物）模拟模型。因此，名称 "PyWOFOST" 就显得太局限了，于是选用了 Python Crop Simulation Environment 这个名字，与 FORTRAN Simulation Environment (FSE) 相呼应。

PCSE 的局限性
-------------------

PCSE 也有它的局限性，具体包括以下几个方面：

* 速度：灵活性是要付出代价的；PCSE 的运行速度明显慢于用 FORTRAN 或其他编译型语言编写的等效模型。

* PCSE 的模拟方法目前仅限于固定日步长的矩形（Euler）积分。当然，如果需要，模块的内部步长可以设置得更细。

* 没有图形用户界面。不过，虽然没有用户图形界面，可以通过与 `pandas <http://pandas.pydata.org/>`_ 包以及 `Jupyter notebook <https://jupyter.org/>`_ 结合来部分弥补。PCSE 的输出可以很容易地转换为 pandas 的 `DataFrame`，进而在 Jupyter notebook 中显示图表。参见我整理的 `examples using PCSE <https://github.com/ajwdewit/pcse_notebooks>`_ 示例笔记本集。

许可证
-------

PCSE 的源代码以 European Union Public License (EUPL) 1.2 版发布，或者在欧洲委员会批准后使用 EUPL 的随后的版本（“许可”）。
除非遵守许可协议，否则您不得使用本软件。许可协议可在此获取：https://joinup.ec.europa.eu/community/eupl/og_page/eupl

PCSE 包包含了一些取自其他开源项目或在其基础上修改过的模块：

* 来自 http://pydispatcher.sourceforge.net/ 的 `pydispatch` 模块，遵循 BSD 风格的许可协议分发。

* `traitlets` 模块取自并改编自 `IPython` 项目 (https://ipython.org/)，同样遵循 BSD 风格的许可协议。PCSE 基于此单独创建了一个专用版本的 `traitlets`，可在 `here <https://pypi.org/project/traitlets-pcse/>`_ 获取。

具体的许可条款请参见这两个项目的项目主页。