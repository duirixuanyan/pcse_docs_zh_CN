快速入门
===============

本指南将帮助你安装 PCSE，并提供一些示例，帮助你开始建模。这些示例目前主要集中在应用 WOFOST 和 LINTUL3 作物模拟模型，尽管在未来 PCSE 里可能还会提供其他作物模拟模型。

需要注意的是，下面这些示例也可以作为 Jupyter notebooks 在我的 github 页面中找到: https://github.com/ajwdewit/pcse_notebooks


交互式 PCSE/WOFOST 会话
----------------------------------

展示 PCSE 最简单的方法是从 PCSE 中导入 WOFOST 并在交互式 Python 会话中运行。我们会使用 `start_wofost()` 脚本，它会连接一个演示数据库，该数据库包含南西班牙某网格位置的气象数据、土壤数据、作物数据和管理数据。

初始化 PCSE/WOFOST 并推进模型状态
..................................................

我们先在南西班牙某地以2000年为例，在有限水分条件下，启动一个用于冬小麦模拟的 WOFOST 对象::

    >>> wofost_object = pcse.start_wofost()
    >>> type(wofost_object)
    <class 'pcse.models.Wofost72_WLP_CWB'>

你已经在 Python 解释器中成功初始化了一个 PCSE/WOFOST 对象，目前它处于初始状态，等待进行模拟。现在我们可以推进模型状态，比如前进 1 天::

    >>> wofost_object.run()

通常只推进 1 天作物模拟并不是很有用，所以你也可以指定要模拟的天数::

    >>> wofost_object.run(days=10)

获取状态变量和率变量的信息
..................................................
可以通过在 PCSE 对象上使用 `get_variable()` 方法，来获取模型计算出的状态变量或率变量的信息。
例如，要获取当前模型状态下叶面积指数的数值，可以这样做::

    >>> wofost_object.get_variable('LAI')
    0.28708095263317146 
    >>> wofost_object.run(days=25)
    >>> wofost_object.get_variable('LAI')
    1.5281215808337203

这表明在模拟推进 11 天后，LAI 的值为 0.287。当我们将时间再推进 25 天后，LAI 增加到了 1.528。`get_variable` 方法可以获取模型中定义的任意状态或率变量。最后，我们可以让模型持续运行，直到作物成熟或到达收获日期，最终结束本轮作物生长周期::

    >>> wofost_object.run_till_terminate()

接下来我们可以在每个时间步（'output'）获取模拟结果::

    >>> output = wofost_object.get_output()

现在可以使用 pandas 包将模拟输出转换为 dataframe，这样更容易处理，也便于导出为不同类型的文件。例如，可以导出为一个 excel 文件，如下（格式参见此文件 :download:`downloads/wofost_results.xls`）：

    >>> import pandas as pd
    >>> df = pd.DataFrame(output)
    >>> df.to_excel("wofost_results.xls")

最后，我们可以获取作物生长周期结束时的结果（summary results），并查看这些信息：

    >>> summary_output = wofost_object.get_summary_output()
    >>> msg = "Reached maturity at {DOM} with total biomass {TAGP} kg/ha "\
    "and a yield of {TWSO} kg/ha."
    >>> print(msg.format(**summary_output[0]))
    Reached maturity at 2000-05-31 with total biomass 15261.7521735 kg/ha and a yield of 7179.80460783 kg/ha.

    >>> summary_output
    [{'CTRAT': 22.457536342947606,
      'DOA': datetime.date(2000, 3, 28),
      'DOE': datetime.date(2000, 1, 1),
      'DOH': None,
      'DOM': datetime.date(2000, 5, 31),
      'DOS': None,
      'DOV': None,
      'DVS': 2.01745939841335,
      'LAIMAX': 6.132711275237731,
      'RD': 60.0,
      'TAGP': 15261.752173534584,
      'TWLV': 3029.3693107257263,
      'TWRT': 1546.990661062695,
      'TWSO': 7179.8046078262705,
      'TWST': 5052.578254982587}]

使用自定义输入数据运行 PCSE/WOFOST
------------------------------------------

要使用你自己的数据源运行 PCSE/WOFOST（以及一般的 PCSE 模型），你需要三种不同类型的输入：

1. 用于对不同模型组件参数化的模型参数。通常包括一套作物参数（如果是轮作，则有多套），一套土壤参数，以及一套站点参数。最后一类提供与特定地点相关的辅助参数。
2. 由气象数据表示的驱动变量，这些数据可以来源于多种渠道。
3. 农业管理措施（ agromanagement actions ），用于指定将由 PCSE 模拟的田块上发生的农场活动。

在第二个示例中，我们将在 Wageningen（荷兰）对甜菜进行模拟，并且我们将一步一步地从多个不同的数据源读取输入数据，而不是使用预先配置好的 `start_wofost()` 脚本。对于这个例子，我们假定数据文件都在 `D:\\userdata\\pcse_examples` 目录下，所有参数文件可以通过解压此压缩包获取 :download:`downloads/quickstart_part2.zip`。

首先，我们将导入必要的模块并定义数据目录::

    >>> import os
    >>> import pcse
    >>> import matplotlib.pyplot as plt
    >>> data_dir = r'D:\userdata\pcse_examples'

作物参数
...............

作物参数包括参数名称和对应的参数值，这些参数用于作物模拟模型各组件的参数化。这些值是关于物候、生长同化、呼吸、生物量分配等作物特有的信息。甜菜的参数文件取自 `WOFOST Control Centre`_ 的作物文件。

.. _WOFOST Control Centre: http://www.wageningenur.nl/wofost

在 Wageningen 的许多模型中，作物参数通常以 CABO 格式提供，可以用 `TTUTIL <http://edepot.wur.nl/17847>`_ FORTRAN 库读取。PCSE 尽量保证向后兼容，并提供 :ref:`CABOFileReader <CABOFileReader>` 用于读取 CABO 格式的参数文件。
`CABOFileReader` 返回一个包含参数名和参数值对的字典::

    >>> from pcse.input import CABOFileReader
    >>> cropfile = os.path.join(data_dir, 'sug0601.crop')
    >>> cropdata = CABOFileReader(cropfile)
    >>> print(cropdata)

打印 `cropdata` 字典时，可以看到文件头及所有参数和它们的值。

土壤参数
...............

soildata 字典提供与土壤类型和土壤物理属性相关的参数名称/值对。参数的数量会根据用于模拟的土壤水分平衡类型而变化。在本例中，我们将使用自由排水土壤的水分平衡，并使用中等细沙的土壤文件： `ec3.soil`。此文件同样取自 `WOFOST Control Centre`_ 的土壤文件::

    >>> soilfile = os.path.join(data_dir, 'ec3.soil')
    >>> soildata = CABOFileReader(soilfile)

站点参数
...............

站点参数提供一些与作物和土壤无关的辅助参数。例如，水分平衡的初始条件，像初始土壤含水量 (WAV) 以及初始和最大地表水储量 (SSI, SSMAX)。此外，大气 CO2 浓度也是典型的站点参数。目前，我们可以直接在 Python 命令行上用简单的 python 字典来定义这些参数。但更方便的做法是使用 :ref:`WOFOST72SiteDataProvider <WOFOST72SiteDataProvider>`，它记录了站点参数并为其提供合理的默认值::

    >>> from pcse.input import WOFOST72SiteDataProvider
    >>> sitedata = WOFOST72SiteDataProvider(WAV=100)
    >>> print(sitedata)
    {'SMLIM': 0.4, 'NOTINF': 0, 'SSI': 0.0, 'SSMAX': 0.0, 'IFUNRN': 0, 'WAV': 100.0}

最后，我们需要使用 `ParameterProvider` 将不同的参数集合打包到一个变量中。这是因为 PCSE 期望用一个变量来包含所有参数值。采用这种方式还有个额外好处：如果需要运行多次模拟且参数值略有不同，可以很方便地对参数值进行覆盖：

     >>> from pcse.base import ParameterProvider
     >>> parameters = ParameterProvider(cropdata=cropdata, soildata=soildata, sitedata=sitedata)

农业管理（AgroManagement）
..............

农业管理（agromanagement）输入提供了农事活动的开始日期、作物模拟的 start_date/start_type、作物模拟的 end_date/end_type，以及作物模拟的最大持续天数。设置最大持续天数主要是为了避免由于温度积要求过高等原因导致非现实的超长模拟。

农业管理输入采用一种特殊的语法 `YAML`_ 进行定义，这种语法易于表示更复杂的结构，适用于描述农业管理。Wageningen 地区甜菜的农业管理文件为 `sugarbeet_calendar.agro`，可以通过 :ref:`YAMLAgroManagementReader <YAMLAgroManagementReader>` 读取：

    >>> from pcse.input import YAMLAgroManagementReader
    >>> agromanagement_file = os.path.join(data_dir, 'sugarbeet_calendar.agro')
    >>> agromanagement = YAMLAgroManagementReader(agromanagement_file)
    >>> print(agromanagement)
     !!python/object/new:pcse.fileinput.yaml_agro_loader.YAMLAgroManagementReader
     listitems:
     - 2000-01-01:
         CropCalendar:
           crop_name: sugarbeet
           variety_name: sugar_beet_601
           crop_start_date: 2000-04-05
           crop_start_type: emergence
           crop_end_date: 2000-10-20
           crop_end_type: harvest
           max_duration: 300
         StateEvents: null
         TimedEvents: null

每日气象观测数据
..........................

运行模拟需要每日的气象变量。在 PCSE 中有多种气象数据提供方式，详见
:ref:`weather data providers <Weather data providers>` 章节。

本例中我们将使用 NASA Power 数据库的气象数据，
该数据库提供分辨率为 0.5 度（约 50 公里）的全球气象数据。
我们将从 Power 数据库获取 Wageningen 地区的数据。
注意：首次从 NASA Power 服务器获取气象数据大约需要 30 秒：

    >>> from pcse.input import NASAPowerWeatherDataProvider
    >>> wdp = NASAPowerWeatherDataProvider(latitude=52, longitude=5)
    >>> print(wdp)
    Weather data provided by: NASAPowerWeatherDataProvider
    --------Description---------
    NASA/POWER CERES/MERRA2 Native Resolution Daily Data
    ----Site characteristics----
    Elevation:    3.5
    Latitude:  52.000
    Longitude:  5.000
    Data available for 1984-01-01 - 2024-03-20
    Number of missing days: 0

导入、初始化和运行 PCSE 模型
................................................

在 PCSE 的内部，使用仿真 `engine` 来运行作物模拟。该 engine 需要一个配置文件，用于指定模拟所需的作物、土壤和农业管理的各个组成部分。因此，任何 PCSE 模型都可以通过导入 `engine` 并结合相应的参数、气象数据以及农业管理初始化后，来启动模拟。

然而，由于很多 PCSE 用户只需要特定的模型配置（例如用于潜在产量模拟的 WOFOST 模型），因此在 `pcse.models` 中提供了预先配置好的 Engines。以甜菜为例，我们将导入用于水分受限情景的 WOFOST 模型，采用经典的土壤水分平衡法。该方法假设土壤为自由排水，并模拟土壤水分动态：

    >>> from pcse.models import Wofost72_WLP_CWB
    >>> wofsim = Wofost72_WLP_CWB(parameters, wdp, agromanagement)

然后我们可以运行模拟，并展示一些最终结果，比如抽穗和收获日期（DOA，DOH）、总生物量（TAGP）和最大叶面积指数（LAIMAX）。
接下来，可以通过在 WOFOST 对象上使用 `get_output()` 方法，获取每日模拟输出的时间序列::

    >>> wofsim.run_till_terminate()
    >>> output = wofsim.get_output()
    >>> len(output)
    294

由于输出是以字典列表的形式返回的，因此需要从输出列表中提取这些变量::

    >>> varnames = ["day", "DVS", "TAGP", "LAI", "SM"]
    >>> tmp = {}
    >>> for var in varnames:
    >>>     tmp[var] = [t[var] for t in output]

最后，可以使用 `MatPlotLib`_ 绘图库生成一些 WOFOST 变量的图形，比如作物发育进程（DVS）、总生物量（TAGP）、叶面积指数（LAI）和根区土壤含水量（SM）::

    >>> day = tmp.pop("day")
    >>> fig, axes = plt.subplots(nrows=2, ncols=2, figsize=(10,8))
    >>> for var, ax in zip(["DVS", "TAGP", "LAI", "SM"], axes.flatten()):
    >>>     ax.plot_date(day, tmp[var], 'b-')
    >>>     ax.set_title(var)
    >>> fig.autofmt_xdate()
    >>> fig.savefig('sugarbeet.png')

.. _MatPlotLib: http://matplotlib.org/

上述代码会生成类似下图所示的模拟结果图像。这个示例的完整 Python 脚本可以在这里下载 :download:`downloads/quickstart_demo2.py`

.. image:: figures/sugarbeet.png


.. _RunningLINTUL3:

使用 PCSE/LINTUL3 进行模拟
--------------------------------------

LINTUL 模型（Light INTerception and UtiLisation，光拦截与利用）是一个简单的通用作物模型，通过假设光能利用效率为常数，模拟作物通过光拦截和利用过程的干物质生产。在 PCSE 中，LINTUL 系列模型已经被实现，包括 LINTUL3 模型，可用于在水分受限和氮素受限条件下模拟作物产量。

在第三个示例中，我们将使用 LINTUL3 模型，对荷兰的春小麦在水分受限和氮素受限状况下的生产进行模拟。我们同样假设数据文件存放在 `D:\\userdata\\pcse_examples` 目录下，所有必要的参数文件可以通过解压此压缩包获得 :download:`downloads/quickstart_part3.zip`。此外，本指南也提供 IPython notebook 版本：:download:`downloads/running_LINTUL3.ipynb`。

首先，我们需要导入所需的模块，并定义数据目录。还要假设你的系统上已经安装了 `matplotlib`_、 `pandas`_ 和 `PyYAML`_ 这几个包。::

    >>> import os
    >>> import pcse
    >>> import matplotlib.pyplot as plt
    >>> import pandas as pd
    >>> import yaml
    >>> data_dir = r'D:\userdata\pcse_examples'

.. _pandas: http://pandas.pydata.org
.. _PyYAML: http://pyyaml.org/wiki/PyYAML

与前面的示例类似，要运行 PCSE/LINTUL3 模型，我们需要定义三类输入（参数、气象数据和农业管理）。

读取模型参数
........................
可以像前面的实例一样，通过 `PCSEFileReader` 从输入文件中直接读取模型参数::

    >>> from pcse.input import PCSEFileReader
    >>> crop = PCSEFileReader(os.path.join(data_dir, "lintul3_springwheat.crop"))
    >>> soil = PCSEFileReader(os.path.join(data_dir, "lintul3_springwheat.soil"))
    >>> site = PCSEFileReader(os.path.join(data_dir, "lintul3_springwheat.site"))

但是，PCSE 模型期望接收一组合并后的参数，因此需要用 `ParameterProvider` 将其合并：

    >>> from pcse.base import ParameterProvider
    >>> parameterprovider = ParameterProvider(soildata=soil, cropdata=crop, sitedata=site)

读取气象数据
....................
用于读取气象数据，我们将使用 ExcelWeatherDataProvider。该 WeatherDataProvider 使用与 CABO 天气文件几乎相同的文件格式，但将数据存储在 MicroSoft Excel 文件中，这使得天气文件更容易创建和更新::

    >>> from pcse.input import ExcelWeatherDataProvider
    >>> weatherdataprovider = ExcelWeatherDataProvider(os.path.join(data_dir, "nl1.xlsx"))
    >>> print(weatherdataprovider)
    Weather data provided by: ExcelWeatherDataProvider
    --------Description---------
    Weather data for:
    Country: Netherlands
    Station: Wageningen, Location Haarweg
    Description: Observed data from Station Haarweg in Wageningen
    Source: Meteorology and Air Quality Group, Wageningen University
    Contact: Peter Uithol
    ----Site characteristics----
    Elevation:    7.0
    Latitude:  51.970
    Longitude:  5.670
    Data available for 2004-01-02 - 2008-12-31
    Number of missing days: 32

定义农业管理
.......................
农业管理（agromanagement）的定义需要更多解释，因为 agromanagement 是 PCSE 中一个相对复杂的部分。PCSE 的农业管理定义采用一种称为 `YAML`_ 的格式，当前示例的定义如下：

.. code:: yaml

    Version: 1.0.0
    AgroManagement:
    - 2006-01-01:
        CropCalendar:
            crop_name: wheat
            variety_name: spring-wheat
            crop_start_date: 2006-03-31
            crop_start_type: emergence
            crop_end_date: 2006-08-20
            crop_end_type: earliest
            max_duration: 300
        TimedEvents:
        -   event_signal: apply_n
            name:  Nitrogen application table
            comment: All nitrogen amounts in g N m-2
            events_table:
            - 2006-04-10: {amount: 10, recovery: 0.7}
            - 2006-05-05: {amount:  5, recovery: 0.7}
        StateEvents: null

.. _YAML: http://yaml.org/

agromanagement 的定义以 `Version:` 开头，表示 agromanagement 文件的版本号，而实际定义则是在 `AgroManagement:` 标签之后开始。接下来必须提供一个日期，用于设定本次生产活动（以及仿真的开始时间）。每个生产活动由零个或一个 CropCalendars 和零个或多个 TimedEvents 和/或 StateEvents 组成。CropCalendar 用于定义作物名称、variety_name、播种日期、收获日期等，而 Timed/StateEvents 用于定义与特定日期或模型状态相关联的操作。

在当前示例中，生产活动开始于 2006-01-01，其中有一个 spring-wheat 的作物历，作物从 2006-03-31 出苗，收获日期为 2006-08-20，或在该日期前作物达到成熟时提前收获。接下来定义了两个定时施氮肥事件，分别在 2006-04-10 和 2006-05-05。当前示例没有状态事件。更多关于所有可能性的详细说明，请参考 Reference Guide（第3章）中 AgroManagement 部分。

agromanagement 的定义需要通过 YAMLAgroManagementReader 进行加载：

    >>> from pcse.input import YAMLAgroManagementReader
    >>> agromanagement = YAMLAgroManagementReader(os.path.join(data_dir, "lintul3_springwheat.amgt"))
    >>> print(agromanagement)
    !!python/object/new:pcse.fileinput.yaml_agro_loader.YAMLAgroManagementReader
    listitems:
    - 2006-01-01:
        CropCalendar:
          crop_end_date: 2006-10-20
          crop_end_type: earliest
          crop_name: wheat
          variety_name: spring-wheat
          crop_start_date: 2006-03-31
          crop_start_type: emergence
          max_duration: 300
        StateEvents: null
        TimedEvents:
        - comment: All nitrogen amounts in g N m-2
          event_signal: apply_n
          events_table:
          - 2006-04-10:
              amount: 10
              recovery: 0.7
          - 2006-05-05:
              amount: 5
              recovery: 0.7
          name: Nitrogen application table


启动和运行 LINTUL3 模型
......................................
现在我们已经拥有了所有的参数、气象数据和 agromanagement 信息，可以开始运行 LINTUL3 模型::

    >>> from pcse.models import LINTUL3
    >>> lintul3 = LINTUL3(parameterprovider, weatherdataprovider, agromanagement)
    >>> lintul3.run_till_terminate()

接下来，我们可以很容易地通过 get_output() 方法获取模型输出，并将其转换为 pandas DataFrame：:

    >>> output = lintul3.get_output()
    >>> df = pd.DataFrame(output).set_index("day")
    >>> df.tail()
                     DVS       LAI     NUPTT       TAGBM     TGROWTH  TIRRIG  \
    day
    2006-07-28  1.931748  0.384372  4.705356  560.213626  626.053663       0
    2006-07-29  1.953592  0.368403  4.705356  560.213626  626.053663       0
    2006-07-30  1.974029  0.353715  4.705356  560.213626  626.053663       0
    2006-07-31  1.995291  0.339133  4.705356  560.213626  626.053663       0
    2006-08-01  2.014272  0.326169  4.705356  560.213626  626.053663       0

                   TNSOIL  TRAIN  TRAN  TRANRF  TRUNOF      TTRAN        WC  \
    day
    2006-07-28  11.794644  375.4     0       0       0  71.142104  0.198576
    2006-07-29  11.794644  376.3     0       0       0  71.142104  0.197346
    2006-07-30  11.794644  376.3     0       0       0  71.142104  0.196293
    2006-07-31  11.794644  381.6     0       0       0  71.142104  0.198484
    2006-08-01  11.794644  381.7     0       0       0  71.142104  0.197384

                     WLVD       WLVG        WRT         WSO         WST
    day
    2006-07-28  88.548865  17.687197  16.649830  184.991591  268.985974
    2006-07-29  89.284828  16.951234  16.150335  184.991591  268.985974
    2006-07-30  89.962276  16.273785  15.665825  184.991591  268.985974
    2006-07-31  90.635216  15.600845  15.195850  184.991591  268.985974
    2006-08-01  91.233828  15.002234  14.739974  184.991591  268.985974

最后，如果你的环境支持绘图，我们可以用几条命令从 pandas DataFrame 可视化结果：

    >>> fig, axes = plt.subplots(nrows=9, ncols=2, figsize=(16,40))
    >>> for key, axis in zip(df.columns, axes.flatten()):
    >>>     df[key].plot(ax=axis, title=key)
    >>> fig.autofmt_xdate()
    >>> fig.savefig(os.path.join(data_dir, "lintul3_springwheat.png"))

.. image:: downloads/lintul3_springwheat.png
