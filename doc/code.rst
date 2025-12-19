.. include:: abbreviations.txt

##################
代码文档说明
##################

阅读方法
===========

API 文档为 PCSE 源代码分发包中的所有 SimulationObject、AncillaryObject 以及实用程序例程的接口与内部结构提供了说明。所有 SimulationObject 和 AncillaryObject 的描述结构一致，主要包括以下内容：

    1. 对对象的简要描述
    2. 接口中参数的名称（位置参数与关键字参数）
    3. 该对象所需仿真参数的表格
    4. SimulationObject 的状态变量表
    5. SimulationObject 的速率变量表
    6. SimulationObject 发送或接收的信号
    7. 对其他 SimulationObject 状态或速率变量的外部依赖
    8. 在何种情况下抛出哪些异常

当某些部分对所描述的对象不适用时，可以省略对应部分。

仿真参数表包含以下列：

    1. 参数名称
    2. 参数描述
    3. 参数类型。以三字符代码表示，含义如下：第一个字符表示参数是标量 **(S)** 还是表格 **(T)**，第二和第三个字符用于补充说明
    4. 参数的物理单位

状态/速率变量表包含以下列：

    1. 变量名称
    2. 变量描述
    3. 该变量是否会在 kiosk 中发布：Y|N
    4. 变量的物理单位

最后，所有对象的公开方法也将进行说明。

引擎与模型
=================

引擎
---------------------

.. automodule:: pcse.engine
    :members:

    .. :private-members:
    .. :special-members:
    .. :undoc-members:
    .. :member-order: bysource

模型
---------------------

.. automodule:: pcse.models
    :members:


.. _AgromanagementCode:

农事管理模块
======================

以下例程实现了 PCSE 的 agromanagement 系统，包括 crop calendars、rotations、state 和 timed events。关于如何从文件或数据库结构读取 agromanagement 数据，请参见 :ref:`reading file input <Input>` 和 :ref:`database tools <DBtools>` 章节。

.. autoclass:: pcse.agromanager.AgroManager
    :members:

.. autoclass:: pcse.agromanager.CropCalendar
    :members:

.. autoclass:: pcse.agromanager.TimedEventsDispatcher
    :members:

.. autoclass:: pcse.agromanager.StateEventsDispatcher
    :members:


计时器
=========

.. autoclass:: pcse.timer.Timer
    :members:

土壤过程模块
====================

土壤水分平衡模块
---------------------

PCSE 提供了多个土壤水分平衡模块：
    1. WaterbalancePP：用于非水分胁迫（即水分不受限）条件下的模拟。
    2. WaterbalanceFD：在自由排水土壤条件下，用于水分受限条件下的模拟。
    3. SnowMAUS：用于模拟积雪的形成与融化过程。
    4. 分层水分平衡模型：实现了潜在条件、自由排水下水分受限条件下的分层水分动态模拟。目前该模型尚不支持浅层地下水对土壤水分的影响，这一功能将在未来实现。

.. autoclass:: pcse.soil.WaterbalancePP

.. autoclass:: pcse.soil.WaterbalanceFD

.. autoclass:: pcse.soil.WaterBalanceLayered

.. autoclass:: pcse.soil.soil_profile.SoilProfile

.. autoclass:: pcse.soil.soil_profile.SoilLayer

.. autoclass:: pcse.soil.SnowMAUS

氮和碳模块
---------------------------

PCSE 提供了两个用于土壤中氮和碳的模块：
    1. 简单的 N_Soil_Dynamics 模块，仅将氮作为一个可用氮库进行模拟，不考虑淋洗、挥发等动态过程。
    2. SNOMIN 模块（土壤矿质与无机氮模块），基于分层土壤碳氮平衡，需要配合分层土壤水分平衡模块使用。它包括了土壤中完整的氮动态过程，同时考虑有机质和有机肥（如粪肥）对土壤氮供应的影响。

.. autoclass:: pcse.soil.N_Soil_Dynamics

.. autoclass:: pcse.soil.SNOMIN


WOFOST 作物模拟过程
=======================

物候
---------

.. autoclass:: pcse.crop.phenology.DVS_Phenology


.. autoclass:: pcse.crop.phenology.Vernalisation


干物质分配
------------

.. autoclass:: pcse.crop.partitioning.DVS_Partitioning


|CO2| 同化过程
------------------

.. autoclass:: pcse.crop.assimilation.WOFOST72_Assimilation

.. autoclass:: pcse.crop.assimilation.WOFOST73_Assimilation

.. autoclass:: pcse.crop.assimilation.WOFOST81_Assimilation


维持呼吸作用
-----------------------
.. autoclass:: pcse.crop.respiration.WOFOST_Maintenance_Respiration

蒸散作用
------------------
.. autoclass:: pcse.crop.evapotranspiration.Evapotranspiration

.. autoclass:: pcse.crop.evapotranspiration.EvapotranspirationCO2

.. autoclass:: pcse.crop.evapotranspiration.EvapotranspirationCO2Layered

.. autofunction:: pcse.crop.evapotranspiration.SWEAF

    
叶片动态
-------------
.. autoclass:: pcse.crop.leaf_dynamics.WOFOST_Leaf_Dynamics

.. autoclass:: pcse.crop.leaf_dynamics.WOFOST_Leaf_Dynamics_N

.. autoclass:: pcse.crop.leaf_dynamics.CSDM_Leaf_Dynamics

根系动态
-------------
.. autoclass:: pcse.crop.root_dynamics.WOFOST_Root_Dynamics

茎秆动态
-------------
.. autoclass:: pcse.crop.stem_dynamics.WOFOST_Stem_Dynamics

贮藏器官动态
----------------------
.. autoclass:: pcse.crop.storage_organ_dynamics.WOFOST_Storage_Organ_Dynamics

作物氮素动态
---------------

.. autoclass:: pcse.crop.n_dynamics.N_Crop_Dynamics
.. autoclass:: pcse.crop.nutrients.N_Demand_Uptake
.. autoclass:: pcse.crop.nutrients.N_Stress


非生物胁迫损伤
--------------
.. autoclass:: pcse.crop.abioticdamage.FROSTOL

.. autoclass:: pcse.crop.abioticdamage.CrownTemperature


LINGRA牧草生长过程模拟
====================================

.. automodule:: pcse.crop.lingra

总体草地模型
-----------------------

.. autoclass:: pcse.crop.lingra.LINGRA

源/库限制生长
--------------------------

.. autoclass:: pcse.crop.lingra.SourceLimitedGrowth

.. autoclass:: pcse.crop.lingra.SinkLimitedGrowth

氮素动态
-----------------

.. autoclass:: pcse.crop.lingra_ndynamics.N_Demand_Uptake

.. autoclass:: pcse.crop.lingra_ndynamics.N_Stress

.. autoclass:: pcse.crop.lingra_ndynamics.N_Crop_Dynamics

LINTUL作物模拟过程
====================================

.. autoclass:: pcse.crop.lintul3.Lintul3
    :members:


.. Crop simulation processes for the ALCEPAS model
.. ===============================================


.. _BaseClasses:

基类
============

这些基类定义了PCSE内部主要的功能实现。除了 `VariableKiosk` 和 `WeatherDataContainer` 以外，其余所有类都不建议直接调用，应通过继承方式使用。


VariableKiosk（变量信息亭）
-------------
.. autoclass:: pcse.base.VariableKiosk
    :members:


参数、速率和状态的基类
---------------------------------------------

.. autoclass:: pcse.base.StatesTemplate
    :members:

.. autoclass:: pcse.base.RatesTemplate
    :members:

.. autoclass:: pcse.base.ParamTemplate
    :members:

气象数据的基础类和工具类
-----------------------------------------

.. autoclass:: pcse.base.WeatherDataProvider
    :members:

.. autoclass:: pcse.base.WeatherDataContainer
    :members:

配置加载
---------------------
.. autoclass:: pcse.base.ConfigurationLoader
    :members:

.. _Signals:

信号定义
===============
.. automodule:: pcse.signals
    :members:
    

辅助代码
==============

本节介绍用于从文件或数据库中读取气象数据和参数值的工具。


.. _Input:
数据提供器
--------------

`pcse.input` 模块包含了所有用于读取气象文件、参数文件和农事管理文件的类。

.. _NASAPowerWeatherDataProvider:
.. autoclass:: pcse.input.NASAPowerWeatherDataProvider

.. _OpenMeteoWeatherDataProvider:
.. autoclass:: pcse.input.OpenMeteoWeatherDataProvider

.. _CABOWeatherDataProvider:
.. autoclass:: pcse.input.CABOWeatherDataProvider

.. _ExcelWeatherDataProvider:
.. autoclass:: pcse.input.ExcelWeatherDataProvider

.. _CSVWeatherDataProvider:
.. autoclass:: pcse.input.CSVWeatherDataProvider

.. _CABOFileReader:
.. autoclass:: pcse.input.CABOFileReader

.. _PCSEFileReader:
.. autoclass:: pcse.input.PCSEFileReader

.. _YAMLAgroManagementReader:
.. autoclass:: pcse.input.YAMLAgroManagementReader

.. _YAMLCropDataProvider:
.. autoclass:: pcse.input.YAMLCropDataProvider

.. _WOFOST72SiteDataProvider:
.. autoclass:: pcse.input.WOFOST72SiteDataProvider

.. _WOFOST73SiteDataProvider:
.. autoclass:: pcse.input.WOFOST73SiteDataProvider

.. _WOFOST81SiteDataProvider_classic:
.. autoclass:: pcse.input.WOFOST81SiteDataProvider_Classic

.. _WOFOST81SiteDataProvider_SNOMIN:
.. autoclass:: pcse.input.WOFOST81SiteDataProvider_SNOMIN


简单或虚拟数据提供器
--------------------

这类数据提供器适用于在不需要或不便用单独文件或数据库时提供参数值。例如，在模拟潜在生产条件时，土壤参数的具体数值无关紧要，但模型仍然必须获得一些参数值。

.. _DummySoilDataProvider:
.. autoclass:: pcse.util.DummySoilDataProvider


.. _DBtools:

数据库工具
------------------

.. note::
    从 PCSE 6.0.10 版本开始，CGMS 数据库的数据提供器已被移除，因为它们强制 PCSE 依赖 SQLAlchemy ，而这会导致与其他软件包的兼容性问题。此外， SQLAlchemy 并不是运行 PCSE 所必需的，而且这些数据库工具本身的使用也比较有限。

数据库工具包含从欧洲 `Crop Growth Monitoring System <CGMS>`_ 各版本实现的数据库结构中，提取农事管理、参数值和气象变量的函数和类。

注意，数据提供器只具备 *读取* 数据的功能，这里没有 *写入* 模拟结果到 CGMS 数据库的工具。这样做是有意安排的，因为写入数据通常比较复杂，而我们的经验是使用专门的数据库导入工具更加高效，比如 ORACLE 的 `SQLLoader`_ 或 MySQL 的 ``load data infile`` 语法。

.. _SQLLoader: 

http://www.oracle.com/technetwork/database/enterprise-edition/sql-loader-overview-095816.html

.. _CGMS: 

https://ec.europa.eu/jrc/en/mars

.. _CGMS8tools:



便捷例程
--------------------

这些例程用于方便地启动 WOFOST 模拟，便于演示和教程使用。它们可以作为编写自己脚本的示例，但没有其他重要作用。

.. autofunction:: pcse.start_wofost.start_wofost


杂项工具
----------------------

包含许多功能各异的杂项函数，例如用于线性插值的 Arbitrary Function Generator (*AfGen*)，以及用于计算 Penman、Penman/Monteith 参考蒸散量、 Angstrom 方程、还有如日长等天文计算的函数。

.. autofunction:: pcse.util.reference_ET
.. autofunction:: pcse.util.penman_monteith
.. autofunction:: pcse.util.penman
.. autofunction:: pcse.util.check_angstromAB
.. autofunction:: pcse.util.wind10to2
.. autofunction:: pcse.util.angstrom
.. autofunction:: pcse.util.doy
.. autofunction:: pcse.util.limit
.. autofunction:: pcse.util.daylength
.. autofunction:: pcse.util.astro
.. autofunction:: pcse.util.merge_dict
.. autoclass:: pcse.util.Afgen
    :members:
.. autofunction:: pcse.util.is_a_month
.. autofunction:: pcse.util.is_a_dekad
.. autofunction:: pcse.util.is_a_week
.. autofunction:: pcse.util.load_SQLite_dump_file
