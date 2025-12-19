.. include:: abbreviations.txt

#####################################
新功能与修复总览
#####################################

**********************
PCSE 6.0 新增内容
**********************

与 5.5 版本相比，PCSE 6.0 带来了一些重大变更。

首先，WOFOST 7.3 和 8.1 随 PCSE 6.0 一同发布。WOFOST 7.3 包含了大气 |CO2| 响应和生物量再分配。WOFOST 8.1 实现了作物的完整氮素动态。此外，本次发布还引入了新的多层水分平衡以及一种名为 `SNOMIN` （土壤矿质和无机氮模块）的碳/氮平衡。同时，WOFOST 8.0-beta 在 PCSE 6.0 中已被弃用，这也意味着不再支持作物生长受 P/K 限制的仿真。

WOFOST 7.3 与 8.1 已与新引入的 SNOMIN 碳/氮平衡和新的多层水分平衡相结合。但现有（较简单的）水分和平衡氮素模型依然可用，并在许多情况下仍然非常有用。例如，对于教学目的或数据缺乏的地区，可以优先采用简单方法。因此，WOFOST 7.3 和 8.1 支持多种作物/土壤模型的组合。为了实现这些组合，PCSE 中的模型编码遵循如下规则::

    <modelname><version>_<productionlevel>_<waterbalance>_<nutrientbalance>

其中各个占位符的含义如下：
 - <modelname>: Wofost、Lintul、Lingra 或任何其他已包含的模型
 - <version>: 各自模型版本号，包括主版本号和次版本号，例如 Wofost 7.2 的 "72"
 - <productionlevel>: 农业生态生产水平指示符，可为
   "PP": 潜力生产水平, "WLP": 限水生产水平 或 "NWLP": 限氮水生产水平
 - <waterbalance>: 所用水分平衡类型，可为 "CWB": 经典（简单）水分平衡，或 "MLWB": 更复杂的多层水分平衡
 - <nutrientbalance>: 所用营养平衡类型，可为 "CNB": 经典（简单）氮素平衡，或 "SNOMIN": 复杂的碳/氮平衡

根据生产水平，代码中的水分平衡和氮素平衡部分可以省略。例如，WOFOST 7.3 潜力生产模型编码为 "Wofost73_PP"，而最复杂的 WOFOST 8.1 变种模型编码为 "Wofost81_NWLP_MLWB_SNOMIN"。后者结合了 WOFOST 8.1 作物动态、多层水分平衡和 SNOMIN 碳/氮平衡。

系统的其它更改包括：

 - 所有数据提供者均已移动至 `pcse.input`，只有 CGMS 数据提供者仍位于 `pcse.db`
 - 所有 WOFOST 7.2 的模型已按照上述编码规则重命名。因此，"pcse.models.Wofost72_WLP_FD" 现在变为 "pcse.models.Wofost72_WLP_CWB"，但旧名称仍可正常使用以避免破坏旧代码。



**********************
PCSE 5.5 新增内容
**********************

PCSE 5.5 包含以下新功能：

- 包含了 WOFOST 8.0 版本（beta），提供了潜力 (PP)、限水 (WLP) 以及养分+水分双重限制 (NWLP) 三种模型变体。请注意，所有模型变体中都包含了 N/P/K 动态过程，但对于 PP 和 WLP 变体，N/P/K 的供应被假定为无限。本版本为 beta 版，是因为目前针对 N/P/K 限制生长的实验数据测试还有限。尽管如此，N/P/K 的动态过程基于其他模型中的成熟原理，并采用稀释曲线的概念，来定义作物中 N/P/K 的最大、临界和残余浓度。
- 现已完整实现 LINGRA 和 LINGRA-N 草地模拟模型。该模型可用于估算黑麦草的生产力。
- WOFOST 7.1 已升级为 7.2，主要是为了与 https://wofost.readthedocs.io 上的最新系统描述保持一致。不过，依赖于导入 WOFOST 7.1 的旧代码仍能正常运行。
- 现在可以将 WOFOST 7.2 的物候模块作为独立模型进行导入。当校准仅限于物候时，这将大幅提高模型性能。
- 已将 FAO 水分需求满足指数作为模型纳入。

**********************
PCSE 5.4 新增内容
**********************

PCSE 5.4 包含以下新功能：

- PCSE 现在完全兼容 python3（>3.4），同时仍兼容 python 2.7.14
- NASAPOWERWeatherDataProvider 已升级以适配新的 API

**********************
PCSE 5.3 新增内容
**********************

PCSE 5.3 包含以下新功能：

- WOFOST 作物参数已被重组为新的数据结构和文件格式（如 YAML），可从 github_ 获取。PCSE 5.3 提供了 :ref:`YAMLCropDataProvider <YAMLCropDataProvider>` 用于读取新参数文件。YAMLCropDataProvider 可与 AgroManager 结合用于指定轮作的参数集。
- 新增了 :ref:`CGMSEngine <Engine and models>`，它模仿了传统 CGMS 的行为。这意味着模型可以运行到指定日期。当达到成熟或收获时，所有状态变量的值将被保留，并保持不变直到指定日期。
- CGMS 天气数据提供者添加了缓存功能，这对于重复运行非常有用，因为天气数据只需从 CGMS 数据库检索一次即可。

已修复的一些 bug：

- NASA POWER 数据库从 http:// 切换到了 https://，因此需要更新 NASAPowerWeatherDataProvider。
- 在运行作物轮作时，发现 python 未能及时回收作物仿真对象。现已通过显式调用垃圾回收器解决了该问题。

.. _github: https://github.com/ajwdewit/WOFOST_crop_parameters

**********************
PCSE 5.2 的新增内容
**********************

PCSE 版本 5.2 包含以下新功能：

- 在 PCSE 中实现了 LINTUL3 模型。LINTUL3 是一个用于模拟受限水和受限氮条件下作物生长的简单作物生长模型。
- 在 WOFOST 中实现了新的 N/P/K 限制模块，可以模拟 N/P/K 限制对作物生长的影响。
- 新增了 :ref:`AgroManager <refguide_agromanagement>` ，大大提升了 PCSE 对农业管理的处理能力。新版 agromanager 可以灵活组合种植历、定时事件与状态事件，包括跨多个作季轮作。AgroManager 采用基于 YAML 的新格式来存储农业管理定义。
- WOFOST 的限水生产模拟现在支持利用新版 AgroManager 进行灌溉操作。已添加示例 notebook 讲解不同灌溉方案的用法。
- 支持从 CGMS8 和 CGMS14 数据库读取输入数据

5.2.5 版本的更改：

- 修正了 agromanager 在 crop_end_type="earliest" 或 "harvest" 时出现的问题
- 为 CGMS 天气数据提供者添加了缓存功能
- 新增了 CGMSEngine，用于模拟传统 CGMS 行为：作季结束后，调用 _run() 会增加 DAY，但内部状态变量不再改变，但仍可查询并保存在 OUTPUT 中。

**********************
PCSE 5.1 的新增内容
**********************

PCSE 版本 5.1 包含以下新功能：

- 支持从 CGMS12 数据库读取输入数据（天气、土壤、作物参数）。CGMS 是作物生长监测系统（Crop Growth Monitoring System）的缩写，由 WEnR 与欧盟联合研究中心（MARS 单元）合作开发，用于欧洲的作物监测与产量预报。它利用数据库结构存储天气数据和模型模拟结果，PCSE 可读取这些数据。数据库定义详见 MARSwiki_ 。
- ExcelWeatherDataProvider：在 PCSE 5.2 之前，天气数据唯一的文件格式是 CABO 天气格式，由 :ref:`CABOWeatherDataProvider <CABOWeatherDataProvider>` 读取。虽然该格式有详细文档，但每年都要新建一个文件，容易出错且较为繁琐。因此，创建了 :ref:`ExcelWeatherDataProvider <ExcelWeatherDataProvider>` ，它可直接读取 Microsoft Excel 文件作为输入。示例 Excel 天气文件见此处： :download:`downloads/nl1.xlsx` 。


.. _MARSwiki: http://marswiki.jrc.ec.europa.eu/agri4castwiki/index.php/Appendix_5:_CGMS_tables