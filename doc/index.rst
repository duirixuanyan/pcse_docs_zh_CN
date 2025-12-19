.. PCSE documentation master file, created by
   sphinx-quickstart on Sun Jul  1 23:03:43 2012.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. include:: abbreviations.txt

PCSE：Python 作物模拟环境（The Python Crop Simulation Environment）
============================================

PCSE (Python Crop Simulation Environment) 是一个用于构建作物模拟模型的 Python 包，特别适用于在瓦赫宁根（荷兰）开发的作物模型。PCSE 提供了实现作物模拟模型的环境、读取辅助数据（气象、土壤、农艺管理）的工具，以及模拟生物物理过程（如物候、呼吸和蒸散）的组件。PCSE 也包含了
`WOFOST <http://www.wageningenur.nl/wofost>`_、 `LINGRA <https://edepot.wur.nl/336784>`_ 和
`LINTUL3 <https://models.pps.wur.nl/system/files/LINTUL-N-Shibu-article_1.pdf>`_
作物与草地模拟模型的实现，这些模型已在全球范围内广泛应用。例如，WOFOST 已经被应用于 MARS 作物产量预测系统，并在欧洲及其他地区用作作物监测和产量预测的业务系统。

最初，瓦赫宁根开发的模型通常使用 Fortran 或 Fortran Simulation Translator ( `FST`_ ) 编写。这两个工具都非常好，但随着时间推移，它们有些过时，而且难以与当今流行的许多工具（如容器、数据库、Web 等）集成。
像许多其他软件包一样，PCSE 的开发是为了方便我自己的科研工作。我希望有一个更易于使用、更具交互性且更灵活的工具，同时还能实现 FST 的严谨计算方法。为此，PCSE 用 Python 开发。Python 已成为科学研究领域的重要编程语言。
PCSE 可在 Python 3.6+ 版本上运行，也可以通过精简为核心系统后适配较低版本的 Python。例如，我们曾在 .NET 框架下通过 IronPython 2.7 运行 PCSE。

传统上，瓦赫宁根的作物模拟模型都是附带完整源代码提供的。PCSE 也不例外，其源代码是开源的，采用欧盟公共许可证 (European Union Public License) 授权。

.. _FST: https://www.sciencedirect.com/science/article/abs/pii/S1161030102001314

最新动态
----------

.. toctree::
   :maxdepth: 2

   whatsnew.rst

PCSE 中可用的作物模型
-----------------------------

.. toctree::
   :maxdepth: 2

   available_models.rst

用户指南
----------
.. toctree::
   :maxdepth: 2
   
   user_guide.rst

参考指南
---------------
.. toctree::
   :maxdepth: 2

   reference_guide.rst

代码文档
------------------

.. toctree::
   :maxdepth: 2

   code.rst

中文翻译基于 `PCSE version: 6.0.12（2025年11月6日） <https://github.com/ajwdewit/pcse/tree/3b232476dd1215c0218c4251882e991c4fc12ead>`_

本文档生成于 |date|/|time|.

索引和表格
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

