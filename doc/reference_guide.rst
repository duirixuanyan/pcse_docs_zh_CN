.. include:: abbreviations.txt

###############
参考指南
###############

PCSE 概述
===================

Python 作物模拟环境（PCSE）是在瓦赫宁根早期方法基础上开发的，特别是 Fortran Simulation Environment。`FSE manual <http://edepot.wur.nl/35555>`_
(van Kraalingen, 1995) 对 Euler 积分原理及其在作物模拟模型中的应用进行了非常好的概述。因此，这里不再详细讨论。

尽管如此，PCSE 也尝试在这些方法的基础上做出改进，
通过将仿真逻辑分离为若干
在 (作物) 模型实现中发挥作用的独立组件：

 1. 仿真的动态部分由专用的模拟 `Engine` 负责，它处理初始化、
    土壤和植物模块的速率/状态更新顺序，
    并负责跟踪时间、获取气象数据以及
    调用 agromanager 模块。
 2. 土壤/植物系统微分方程的求解及模型状态的更新由
    实现 (生物) 物理过程（如物候发育或 |CO2| 同化）的 SimulationObjects 负责。
 3. 包含了 AgroManager 模块，负责
    发出农业管理操作（如播种、收获、
    灌溉等）的信号。
 4. PCSE 组件之间的通信可以通过将变量导出到共享状态对象，
    或通过实现信号机制进行，任何 PCSE 对象均可广播和接收这些信号。
 5. 提供了多种工具用于提供气象数据以及
    从文件或数据库读取参数值。

接下来将对 PCSE 中各组件进行概述。

The Engine
==========

PCSE 引擎提供了进行仿真的环境。该引擎负责读取模型配置，初始化模型组件，通过调用 SimulationObjects 推动仿真进程，调用农业管理单元，跟踪时间，提供所需的气象数据，并在仿真期间存储模型变量以便后续输出。引擎本身是通用的，可以用于在 PCSE 中定义的任何模型。引擎调用的不同元素可以在下图中看到，这展示了引擎所调用的各个组成部分。

.. figure:: figures/PCSE_Engine_structure.png
   :align: center
   :width: 500 px



.. _ContinuousSimulation:

PCSE中的连续仿真
-----------------------------

为了实现连续仿真，引擎采用与 FSE 相同的方法：使用固定一天的时间步长进行 Euler 积分。下图展示了连续仿真的原理和各个步骤的执行顺序。

.. figure:: figures/continuous_simulation.png
   :align: center
   :width: 500 px

   连续仿真中各项计算的顺序，采用 Euler 积分方法
   （引自 Van Kraalingen, 1995）。

上图中过程循环所示的步骤在仿真 `Engine` 中实现，仿真 `Engine` 完全与模型逻辑本身分离。此外，还可以看出，在仿真开始之前，引擎需要完成初始化，该过程包括几个步骤：

1. 加载模型配置；
2. 初始化 AgroManager 模块，并调用以确定仿真序列的开始和结束；
3. 用仿真序列的起始和结束日初始化计时器；
4. 初始化模型配置中指定的土壤组件；
5. 获取起始日当天的气象变量；
6. 调用 AgroManager 以触发当日预定的管理事件；
7. 根据初始状态和驱动变量计算初始变化率；
8. 最后，可以收集输出，用于保存仿真的初始状态和变化率。

之后仿真的下一个循环将以将计时器更新到下一个时间步（如一天）开始。接着，将前一日的变化率积分到状态变量上，并获取当前日的驱动变量。最后，根据新的驱动变量和更新后的模型状态重新计算变化率，如此循环往复。

当满足某一结束条件时，仿真循环将终止。通常， `AgroManager` 模块会遇到农事活动的结束，并发送一个终止信号，从而终止整个仿真。

引擎所需的输入
--------------------------

启动引擎需要四个输入：

1. 一个天气数据提供者，为引擎提供每日的气象变量值。相关的天气数据提供方法见 `Weather data providers`_ 章节概述。
2. 一组参数，用于对模拟土壤和作物过程的 SimulationObjects 进行参数化。模型参数可以来自不同来源，如文件或数据库。PCSE 使用三组模型参数：作物参数、土壤参数和场地参数。最后一类为与土壤或作物无关的辅助参数，大气 CO2 浓度就是场地参数的一个典型例子。尽管分为三组参数，所有参数都使用 `ParameterProvider`
   封装，从而为不同参数集提供统一的访问接口。更多内容请参见 `Data providers for parameter values`_ 章节。
3. 作物管理信息，用于安排在仿真过程中执行的农业管理操作。详细内容参见 `The AgroManager`_ 及 `Data providers for agromanagement`_ 相关章节。
4. 一个配置文件，用于指定仿真的详细信息，比如用于作物、土壤和农业管理仿真的组件，以及应存储为最终和中间输出的结果及其他相关细节。


引擎配置文件
--------------------------

引擎需要一个配置文件，用于指定在仿真中应使用哪些组件及其他补充信息。通过示例来说明最为直观，比如用于潜在作物生产的 WOFOST 7.2 模型的配置文件::

    # -*- coding: utf-8 -*-
    # 版权所有 (c) 2004-2021 Wageningen Environmental Research
    # Allard de Wit (allard.dewit@wur.nl), 2021年8月
    """WOFOST 7.2 潜在产量仿真的 PCSE 配置文件

    本配置文件定义了用于潜在产量仿真的土壤和作物组件。
    """

    from pcse.soil.classic_waterbalance import WaterbalancePP
    from pcse.crop.wofost72 import Wofost72
    from pcse.agromanager import AgroManager

    # 用于水分平衡的模块
    SOIL = WaterbalancePP

    # 用于作物模拟本身的模块
    CROP = Wofost72

    # 用于农事管理操作的模块
    AGROMANAGEMENT = AgroManager

    # 需要在OUTPUT信号处保存的变量
    # 如果不需要任何输出，请设为空列表
    OUTPUT_VARS = ["DVS","LAI","TAGP", "TWSO", "TWLV", "TWST",
                   "TWRT", "TRA", "RD", "SM", "WWLOW"]
    # OUTPUT信号输出的间隔，可以为"daily"|"dekadal"|"monthly"|"weekly"
    # 如果选择daily输出，可以通过OUTPUT_INTERVAL_DAYS设置连续输出的天数间隔。
    # 对于dekadal和monthly输出，则忽略OUTPUT_INTERVAL_DAYS的设置。
    OUTPUT_INTERVAL = "daily"
    OUTPUT_INTERVAL_DAYS = 1
    # 星期设置：星期一为0，星期日为6
    OUTPUT_WEEKDAY = 0

    # 在CROP_FINISH信号处保存的汇总变量
    # 如果不需要任何汇总输出，请设为空列表
    SUMMARY_OUTPUT_VARS = ["DVS","LAIMAX","TAGP", "TWSO", "TWLV", "TWST",
                           "TWRT", "CTRAT", "RD", "DOS", "DOE", "DOA",
                           "DOM", "DOH", "DOV", "CEVST"]

    # 在TERMINATE信号处保存的汇总变量
    # 如果不需要任何终止输出，请设为空列表
    TERMINAL_OUTPUT_VARS = []

如你所见，配置文件采用纯 python 代码编写。
首先，它定义了 *SOIL*、*CROP* 和 *AGROMANAGEMENT* 这些占位符，用于指定在模拟这些过程时应使用的组件。这些占位符实际上就是指向在配置文件开头导入的模块。

.. note::
    配置文件中的模块必须使用完整限定名进行导入，不能使用相对导入。

其次，需要定义在模型运行期间（OUTPUT 信号期间）要保存的变量（*OUTPUT_VARS*），以及常规输出间隔的详细信息。
接着，可以定义每个作物周期结束时生成的汇总输出 *SUMMARY_OUTPUT_VARS*。最后，在整个模拟结束时，可以收集输出（*TERMINAL_OUTPUT_VARS*）。

.. note::
    PCSE 包中已包含模型的配置文件位于包内的 'conf/' 文件夹。当 Engine 启动并指定配置文件名称时，会在该文件夹中查找对应文件。
    这意味着，如果你想要使用自己的（修改过的）配置文件启动 Engine，你 *必须* 指定配置文件的绝对路径，否则 Engine 无法找到该文件。

模型与引擎的关系
--------------------

模型与引擎一起处理，因为模型实际上就是经过预配置的 Engine。任何模型都可以通过使用相应的配置文件启动 Engine 来运行。唯一的区别在于，模型可以包含处理模型特定特性的专用方法。
此类功能无法在 Engine 中实现，因为事先并不知道模型的具体细节。


SimulationObjects（模拟对象）
===========================

PCSE 使用 SimulationObjects 将作物模拟模型中构成逻辑实体的部分分组为单独的程序代码片段。通过这种方式，作物模拟模型被划分为实现特定生物物理过程（如物候、同化、呼吸等）的若干部分。Simulation objects 还可以组合起来，形成可模拟整个作物或土壤剖面的组件。

这种方法有以下几个优点：

#. 用于特定目的的模型代码被组织在一起，更易于阅读、理解和维护。
#. 一个 SimulationObject 只包含所需的参数、速率和状态变量。相比之下，单一结构代码通常很难（至少第一眼）判断这些变量属于哪个生物物理过程。
#. 将过程实现隔离可以减少依赖关系，更重要的是，依赖关系在代码中变得清晰，便于修改各个 SimulationObject。
#. 可以通过比较输出与预期结果（例如单元测试），对 SimulationObject 进行单独测试。
#. SimulationObjects 可以与实现相同目的但采用不同生物物理方法的其他对象互换。例如，只需替换负责 |CO2| 同化的 SimulationObject，就能将 WOFOST 同化方法简单替换为光能利用效率或水分利用效率等更简单的方法。


SimulationObject 的特点
------------------------------------

每个 SimulationObject 都以相同的方式定义，并包含一些标准部分和方法，以便于理解和阅读。每个 SimulationObject 都有参数，用于定义数学关系；有状态变量，用于定义系统的状态；还有速率变量，用于描述每个时间步之间状态的变化速率。此外，一个 SimulationObject 还可以包含其他 SimulationObject ，以共同组成一个逻辑结构。最后，SimulationObject 必须实现初始化、速率计算和变化率积分的独立代码部分。可选地，还可以添加一个在模拟结束时调用的收尾步骤。

一个 SimulationObject 的框架如下：

.. code-block:: python

    class CropProcess(SimulationObject):

        class Parameters(ParamTemplate):
            PAR1 = Float()
            # 此处定义更多参数

        class StateVariables(StatesTemplate):
            STATE1 = Float()
            # 此处定义更多状态变量

        class RateVariables(RatesTemplate):
            RATE1 = Float()
            # 此处定义更多速率变量

        def initialize(self, day, kiosk, parametervalues):
            """用给定的参数值初始化 SimulationObject。"""
            self.params = self.Parameters(parametervalues)
            self.rates = self.RateVariables(kiosk)
            self.states = self.StateVariables(kiosk, STATE1=0., publish=["STATE1"])

        @prepare_rates
        def calc_rates(self, day, drv):
            """根据当前状态和驱动变量（drv）计算变化速率。"""

            # 用降雨量（drv.RAIN）作为速率计算的简单示例
            self.rates.RATE1 = self.params.PAR1 * drv.RAIN

        @prepare_states
        def integrate(self, day, delt):
            """对当前状态变量上的变化速率积分，并乘以时间步长。"""
            self.states.STATE1 += self.rates.RATE1 * delt

        @prepare_states
        def finalize(self, day):
            """在模拟完成时进行一些最终计算。"""


程序逻辑的严格分离借鉴自 Fortran Simulation Environment (FSE, `Rappoldt and Van Kraalingen 1996 <http://edepot.wur.nl/4411>`_ 和 `Van Kraalingen 1995 <http://edepot.wur.nl/35555>`_)，这一点对于保证模拟结果的正确性至关重要。不同类型的计算（积分、驱动变量和速率计算）必须严格分开。换句话说，首先应更新所有状态变量，随后计算所有驱动变量，之后再计算所有变化率。如果不严格遵循这一规则，可能会导致部分速率基于当前时刻的状态，另一些则基于前一时刻的状态。与 FSE 系统和 `FORTRAN implementation of WOFOST <https://github.com/ajwdewit/wofost>`_ 相比， `initialize()`、 `calc_rates()`、 `integrate()` 和 `finalize()` 四个部分分别对应 *ITASK* 编号 1、2、3、4。

在使用模块化代码时，一个复杂的问题是如何组织 SimulationObject 间的通信。例如， `evapotranspiration` SimulationObject 需要从 `leaf_dynamics` SimulationObject 获取叶面积指数的信息，以计算作物蒸腾值。在 PCSE 中，不同 SimulationObject 的通信由所谓的 `VariableKiosk` 负责。之所以使用 kiosk 这个比喻，是因为 SimulationObject 会将它们的速率和/或状态变量（或其中一部分）发布到 kiosk，其他 SimulationObject 随后可以从 kiosk 请求变量值，而不需要了解是哪个 SimulationObject 发布了该变量。因此，VariableKiosk 由所有 SimulationObject 共享，并且在 SimulationObject 初始化时必须提供。

有关 variable kiosk 及模型组件之间其他通信方式的详细说明，请参阅 `Exchanging data between model components`_ 一节。

模拟参数
--------

通常，SimulationObject 具有一个或多个参数，这些参数应当定义为 `ParamTemplate` 类的子类。虽然参数也可以直接作为 SimulationObject 定义的一部分指定，但从 `ParamTemplate` 派生子类有几个优点。首先，参数必须被初始化，若缺失某个参数，会抛出带有明确信息的异常。其次，参数被初始化为只读属性，在模拟过程中不能更改。因此，这种方式下参数值不会被偶然覆盖。

模型参数通过调用 Parameters 类定义并提供包含键值对的字典来初始化参数。

状态/速率变量
------------

状态变量和速率变量的定义有许多共同特性。速率和状态变量应当分别定义为继承自 `RatesTemplate` 和 `StatesTemplate` 的类属性。以这种方式定义的速率变量和状态变量名称在所有模型组件中 **必须** 唯一，若在模型组合中出现重复变量名称，会导致异常。

这两个类的实例都需要将 VariableKiosk 作为第一个输入参数，用于注册所定义的变量。此外，变量可以通过 `publish` 关键字进行发布，如上述示例中 *STATE1* 的做法。发布变量意味着该变量会在 VariableKiosk 中可用，其他组件可以根据变量名称来获取它。速率类和状态类的主要区别在于，状态类要求你在调用时通过关键字参数提供状态的初始值。如果未提供初始值，将会抛出异常。

包含速率变量和状态变量的对象实例默认是只读的。为了更改速率或状态的值，实例必须被解锁。为此，需要在 `calc_rates()` 和 `integrate()` 方法前分别加上装饰器 `@prepare_rates` 和 `@prepare_states`，它们负责解锁与锁定 states 和 rates 实例。通过这种方式，速率变量只能在计算速率的调用期间更改，此时状态变量为只读。类似地，状态变量只能在状态更新期间更改，而变化率会被锁定。该机制保证了速率/状态的更新顺序正确。

最后，RatesTemplate 的实例还拥有一个额外方法，名为 `zerofy()`，而 StatesTemplate 的实例则有一个名为 `touch()` 的额外方法。调用 `zerofy()` 通常由引擎完成，明确将所有变化率设为零。对 states 对象调用 `touch()` 仅在状态变量无需更新但希望确保已发布的状态变量仍然在 VariableKiosk 可用时才有用。


AgroManager（农事管理器）
=========================

农事管理是 PCSE 的一个重要组成部分，主要用于模拟农田中发生的各种农事过程。为了让作物生长，农民首先需要耕地和播种。随后，他们要合理安排管理措施，包括灌溉、除草、养分施用、病虫害防治以及最终的收获。所有这些操作都需要在特定日期安排执行，或者与特定的作物生育阶段、土壤和气象条件相关。此外，还必须提供例如灌溉量或养分量等具体参数。

在早期版本的 WOFOST 中，农事管理的选项仅限于播种和收获。一方面，这是因为农事管理通常被假定为“最优”执行，因此不需要详细的农事操作。另一方面，实现农事管理本身也相对复杂，因为农事管理主要由一次性事件组成，而非持续发生的事件。因此，农事管理并不适合传统的模拟循环，参见 :ref:`ContinuousSimulation`。

从技术实现角度来看，通过传统的速率计算和状态更新函数来实现这些事件并不理想。例如，如果要表示一次养分施用事件，就需要传递多个额外参数，例如养分种类、施用量和利用效率。这有几个缺点：首先，只有少数 SimulationObject 会使用这些信息，而大多数对象对此没有需求。其次，养分施用通常在作物生长期只会发生一两次。例如，在一个为期 200 天的生长周期里，有 198 天这些参数都毫无意义。然而，它们依然需要出现在函数调用中，从而降低了计算效率和代码可读性。因此，PCSE 对农事管理事件采用了完全不同的实现方法，该方法基于信号机制（参见 :ref:`Broadcasting signals`）。

.. _refguide_agromanagement:

PCSE中农事管理的定义
--------------------

在PCSE中定义农事管理不是很复杂，首先需要定义一个由多个“campaign”组成的序列。每个campaign从一个指定的日历日期（calendar date）开始，并在下一个campaign开始时结束。每个campaign包含零个或一个作物历（crop calendar）、零个或多个定时事件（timed events）以及零个或多个状态事件（state events）。作物历用于指定作物的时间安排（如播种、收获），定时事件和状态事件则用于指定基于时间（具体日期）或基于某一模型状态变量（如作物发育阶段）的管理措施。作物历和事件定义仅在其所属的campaign内有效。

在PCSE中定义农事管理的数据格式为YAML。YAML是一种优化人类可读性的通用格式，同时也具有类似XML的强大功能。然而，PCSE中的农事管理定义并不一定局限于YAML，也可以从数据库等方式读取。

为AgroManager准备输入数据的结构可以通过下面的示例来直观理解。以下示例定义了三个campaign，第一个从1999-08-01开始，第二个从2000-09-01开始，最后一个campaign从2001-03-01开始。第一个campaign包括了一个冬小麦的作物历（winter-wheat），作物在指定的crop_start_date（1999-09-15）进行播种。在这一campaign期间，有两个灌溉的定时事件分别发生在2000-05-25和2000-06-30。此外，还有三个基于发育阶段（DVS 0.3、0.6和1.12）的施肥状态事件（event_signal: apply_n）。

第二个campaign没有作物历、定时事件和状态事件。这代表这是一个裸地阶段，仅进行水分平衡模拟。第三个campaign是用于青贮玉米（fodder maize），在2001-04-15播种，包含两个定时事件系列（一组为灌溉，另一组为氮肥施用），没有状态事件。此时模拟的结束日期为2001-11-01（2001-04-15 + 200天）。

一个农事管理定义文件的示例::

    AgroManagement:
    - 1999-08-01:
        CropCalendar:
            crop_name: wheat
            variety_name: winter-wheat
            crop_start_date: 1999-09-15
            crop_start_type: sowing
            crop_end_date:
            crop_end_type: maturity
            max_duration: 300
        TimedEvents:
        -   event_signal: irrigate
            name:  Timed irrigation events
            comment: All irrigation amounts in cm
            events_table:
            - 2000-05-25: {amount: 3.0, efficiency=0.7}
            - 2000-06-30: {amount: 2.5, efficiency=0.7}
        StateEvents:
        -   event_signal: apply_n
            event_state: DVS
            zero_condition: rising
            name: DVS-based N application table for the simple N balance
            comment: all fertilizer amounts in kg/ha
            events_table:
            - 0.3: {N_amount : 1, N_recovery=0.7}
            - 0.6: {N_amount: 11, N_recovery=0.7}
            - 1.12: {N_amount: 21, N_recovery=0.7}
    - 2000-09-01:
        CropCalendar:
        TimedEvents:
        StateEvents
    - 2001-03-01:
        CropCalendar:
            crop_name: maize
            variety_name: fodder-maize
            crop_start_date: 2001-04-15
            crop_start_type: sowing
            crop_end_date:
            crop_end_type: maturity
            max_duration: 200
        TimedEvents:
        -   event_signal: irrigate
            name:  Timed irrigation events
            comment: All irrigation amounts in cm
            events_table:
            - 2001-06-01: {amount: 2.0, efficiency=0.7}
            - 2001-07-21: {amount: 5.0, efficiency=0.7}
            - 2001-08-18: {amount: 3.0, efficiency=0.7}
            - 2001-09-19: {amount: 2.5, efficiency=0.7}
        -   event_signal: apply_n
            name:  Timed N application table for the simple N balance
            comment: All fertilizer amounts in kg/ha
            events_table:
            - 2001-05-25: {N_amount : 50, N_recovery=0.7}
            - 2001-07-05: {N_amount : 70, N_recovery=0.7}
        StateEvents:

作物历
--------------

作物历的定义将传递给 `CropCalendar` 对象，该对象负责在 PCSE 模拟期间存储、检查、开始和结束作物生长周期。
在每一个时间步，都将调用 `CropCalendar` 的实例，并且按照其参数中定义的日期启动相应的操作：

- 播种/出苗：会发送 `crop_start` 信号，并包含启动新作物模拟对象所需的参数（crop_name、variety_name、crop_start_type 和 crop_end_type）
- 成熟/收获：作物周期通过发送 `crop_finish` 信号及相应参数来结束。

如需了解作物历的详细描述，可参见代码文档中关于 `CropCalendar` 的章节 :ref:`Agromanagement <AgromanagementCode>`。

定时事件
------------

定时事件是在特定日期发生的管理操作。由于 PCSE 的模拟以日为时间步，因此可以轻松地按日期安排这些操作。
定时事件以事件信号、名称和注释为特征，这些信息可用于描述事件，最后还包括一个事件表，
该表列出事件发生的日期以及需要传递的参数。

请注意，当有多个事件连接到同一日期时，它们触发的顺序是不确定的。

如需了解定时事件的详细描述，可参见代码文档中关于 `TimedEventsDispatcher` 的章节 :ref:`Agromanagement <AgromanagementCode>`。


状态事件
------------

状态事件是与特定模型状态相关的管理操作。例如，某些营养物施用操作需要在作物达到特定生育阶段时执行，或仅在土壤干燥时进行灌溉。PCSE 对于状态事件有灵活的定义，一个事件可以关联到 PCSE 中定义的任意变量。

每个状态事件由 `event_signal`、 `event_state`（例如，触发该事件的模型状态）和 `zero condition` 进行定义。此外，还可以提供可选的名称和注释。最后，events_table 指定在模型状态值达到何时触发该事件。 `events_table` 是一个列表，为每个状态提供对应使用该 event_signal 需要传递的参数。

管理状态事件相较于定时事件更为复杂，因为 PCSE 无法预先确定这些事件将在何时被触发。
为了确定状态事件发生的时间步，PCSE 使用了 `zero-crossing` 的概念。
这意味着当 (`model_state` - `event_state`) 等于零或越过零时，状态事件将被触发。 `zero_condition` 用于定义如何进行该越过。 `zero_condition` 的取值可以是：

* `rising`: 当 (`model_state` - `event_state`) 从负值向零或正值变化时，事件被触发。
* `falling`: 当 (`model_state` - `event_state`) 从正值向零或负值变化时，事件被触发。
* `either`: 当 (`model_state` - `event_state`) 从任意方向接近或越过零时，事件被触发。

请注意，当多个事件关联到相同状态值时，它们被触发的顺序是不确定的。

关于状态事件的详细描述，请参阅代码文档中 StateEventsDispatcher 的章节 :ref:`Agromanagement <AgromanagementCode>`。


确定模拟的开始和结束日期
------------------------------

agromanager 的任务是根据提供给 Engine 的 agromanagement 定义来确定模拟的开始和结束日期。
从 agromanagement 定义中获取开始日期非常直接，因为这就是第一个 campaign 的开始日期。
然而，获取结束日期则复杂一些，因为有几种可能的方式。
第一种方式是通过在 agromanagement 定义中添加一个“尾部空 campaign”来显式定义模拟的结束日期。
下面给出了一个包含“尾部空 campaign”的 agromanagement 定义示例（YAML 格式）。该示例会让模拟运行至 2001-01-01::

    Version: 1.0.0
    AgroManagement:
    - 1999-08-01:
        CropCalendar:
            crop_name: wheat
            variety_name: winter-wheat
            crop_start_date: 1999-09-15
            crop_start_type: sowing
            crop_end_date:
            crop_end_type: maturity
            max_duration: 300
        TimedEvents:
        StateEvents:
    - 2001-01-01:


第二种方式是没有尾部的空 campaign，在这种情况下，模拟的结束日期将从作物历和/或已安排的定时事件中获取。在下方的示例中，结束日期将会是 2000-08-05，因为这是收获日期，并且在该日期之后没有安排任何定时事件::

    Version: 1.0.0
    AgroManagement:
    - 1999-09-01:
        CropCalendar:
            crop_name: wheat
            variety_name: winter-wheat
            crop_start_date: 1999-10-01
            crop_start_type: sowing
            crop_end_date: 2000-08-05
            crop_end_type: harvest
            max_duration: 330
        TimedEvents:
        -   event_signal: irrigate
            name:  Timed irrigation events
            comment: All irrigation amounts in cm
            events_table:
            - 2000-05-01: {amount: 2, efficiency: 0.7}
            - 2000-06-21: {amount: 5, efficiency: 0.7}
            - 2000-07-18: {amount: 3, efficiency: 0.7}
        StateEvents:

如果没有提供收获日期，并且作物持续到成熟，作物历中的结束日期将被估算为 `crop_start_date` 加上 `max_duration`。

请注意，在 agromanagement 定义中，如果最后一个 campaign 包含了 state events 的定义，则*必须*提供一个尾部空 campaign，否则无法确定模拟的结束日期。下面的 campaign 定义虽然合法（但很奇怪），但由于无法确定模拟的结束日期，因此会导致出错::

    Version: 1.0
    AgroManagement:
    - 2001-01-01:
        CropCalendar:
        TimedEvents:
        StateEvents:
        -   event_signal: irrigate
            event_state: SM
            zero_condition: falling
            name: irrigation scheduling on volumetric soil moisture content
            comment: all irrigation amounts in cm
            events_table:
            - 0.25: {amount: 2, efficiency: 0.7}

模型组件间数据交换
========================================

在处理模块化代码时，一个复杂因素是如何在不同组件之间交换模型状态或其他数据。PCSE 实现了两种基本的方法来交换变量：

1. VariableKiosk，主要用于在模型组件之间交换状态/速率变量，在模拟过程中每一周期都需要更新状态/速率变量。
2. 利用信号，可以被任何 PCSE 对象广播和接收，主要用于在模型仿真过程中响应事件时广播信息。

VariableKiosk 变量寄存器
-----------------

VariableKiosk 是 PCSE 中的一个重要组成部分，并且它会在 Engine 启动时被创建。PCSE 中几乎所有对象都会接收 VariableKiosk 的引用，并且它包含许多功能，这些功能乍一看可能不是很明显或被忽视。

首先，
VariableKiosk 会注册 *所有* 作为 StateVariables 或 RateVariables 类的属性所定义的状态和速率变量。这样做时，它还确保了变量名称的唯一性；在单一 Engine 的组件层级结构内，不能有两个同名的状态/速率变量。这样强制唯一性是为了避免组件间变量发布或检索时出现名称冲突。例如，
`engine.get_variable("LAI")` 会获取作物的叶面积指数。然而，如果存在两个名为 "LAI" 的变量，就无法分辨到底取得的是哪一个。甚至不能保证在不同的函数调用或模型运行之间取得的是同一个变量。

其次，VariableKiosk 负责在模型组件间交换状态和速率变量。由 RateVariables 和 StateVariables 对象所发布的变量，在变量被赋值时立即可用于 VariableKiosk。在 PCSE 内部，被发布的变量会有一个触发器与其关联，将其值复制到 VariableKiosk。因此，VariableKiosk 不应被视为共享状态对象，而应该被视为包含变量名/值对副本的缓存。
此外，对 Kiosk 中变量的更新是受到保护的。只有注册并发布变量的 SimulationObject 能够更改其在 Kiosk 中的值。
所有其他 SimulationObject 只能查询其值而无法更改。因此，两个进程不可能通过 VariableKiosk 同时操作同一个变量。

在 kiosk 中保存变量副本的一个潜在危险是，这些副本可能不再反映实际值，例如由于状态未及时更新。在这种情况下，状态的值在 kiosk 中“滞后”，这可能导致模拟错误。为避免此类问题，kiosk 会定期“刷新”其内容。刷新后，变量仍然在 kiosk 中注册，但它们的值变为未定义。变量的刷新由引擎负责，并且会分别针对速率变量和状态变量进行。在所有状态变量更新完后，所有速率变量将被刷新；当速率计算步骤结束后，kiosk 中的所有状态变量将被刷新。一方面，这一过程有助于确保计算按正确的顺序进行。另一方面，这也意味着为了让一个状态变量在 kiosk 中保持可用，即使该速率为零，其值也 *必须* 通过对应速率进行更新！

VariableKiosk 的最后一个重要功能，是作为 PCSE 对象广播信号时的发送者 ID。每个被广播的信号都有一个发送者 ID 和零个或多个接收者。每个 PCSE 仿真对象的实例都被配置为只监听发送者 ID 是自身 VariableKiosk 的那些信号。由于 VariableKiosk 对于每个 Engine 的实例是唯一的，这确保了在同一个 PCSE 会话中同时运行的两个引擎不会“监听”彼此的信号，而只会接收自己的信号。这一原则在运行模型集合（如多个 Engine）时尤为关键，因为不同集合成员之间广播的信号应该互不干扰。

在实际使用中，PCSE 用户几乎无需直接处理 VariableKiosk；变量可以通过在初始化速率/状态变量时使用 `publish=[<var1>,<var2>,...]` 关键字进行发布，从 VariableKiosk 获取变量值则可以像普通字典查找一样操作。更多有关 VariableKiosk 的细节，参见 :ref:`BaseClasses` 部分的描述。

.. _Broadcasting signals:

Broadcasting signals
--------------------

PCSE 中用于传递信息的第二种机制是通过广播信号以响应事件。这非常类似于用户界面工具包的工作方式，在用户界面工具包中，事件处理程序会被连接到某些事件上，比如鼠标点击或者按钮被按下。而在 PCSE 中，事件则与 AgroManager 的管理操作、timer 模块的输出信号、仿真的终止等相关。

PCSE 中的信号在 `signals` 模块中定义，任何需要访问信号的模块都可以很方便地导入该模块。信号仅仅被定义为字符串，但任何可哈希的对象类型都可以。处理信号的大部分工作都在于设置接收器。接收器通常是 SimulationObject 上的一个方法，在信号被广播时将会被调用。该方法会在对象初始化时与信号连接。这很容易通过一个例子来描述::

    mysignal = "My first signal"

    class MySimObj(SimulationObject):

        def initialize(self, day, kiosk):
            self._connect_signal(self.handle_mysignal, mysignal)

        def handle_mysignal(self, arg1, arg2):
            print "Value of arg1, arg2: %s, %s" % (arg1, arg2)

        def send_mysignal(self):
            self._send_signal(signal=mysignal, arg2="A", arg1=2.5)

在上面的示例中， `initialize()` 部分将 `handle_mysignal()` 方法与类型为 `mysignal` 的信号进行连接，该信号包含两个参数 `arg1` 和 `arg2`。当对象初始化后，调用 `send_mysignal()` 时，处理函数会打印出这两个参数的值::

    >>> from pcse.base import VariableKiosk
    >>> from datetime import date
    >>> d = date(2000,1,1)
    >>> v = VariableKiosk()
    >>> obj = MySimObj(d, v)
    >>> obj.send_mysignal()
    Value of arg1, arg2: 2.5, A
    >>>

请注意，用于接收信号的方法 `_connect_signal()` 和发送信号的方法 `_send_signal()` 之所以可用，是因为继承了 `SimulationObject`。这两个方法在可与信号一起传递的位置参数和关键字参数方面非常灵活。有关更多详细信息，请参见 :ref:`Signals <Signals>` 模块的文档，以及提供此功能的 `PyDispatcher <http://pydispatcher.sourceforge.net/>`_ 包的文档。




PCSE中的气象数据
====================

气象必需变量
--------------------------

为了运行作物模拟，引擎需要用于驱动被模拟过程的气象变量。PCSE 需要以下每日气象变量：

========= ========================================================= ===============
名称        描述                                                     单位
========= ========================================================= ===============
TMAX      日最高温度                                                 |C|
TMIN      日最低温度                                                 |C|
VAP       日平均水汽压                                               |hPa|
WIND      2米高度处的日平均风速                                       |msec-1|
RAIN      降水量（降雨，或有雪/冰雹时为水当量）                        |cmday-1|
IRRAD     日全球辐射量                                               |Jm-2day-1|
SNOWDEPTH 积雪深度（可选）                                           |cm|
========= ========================================================= ===============

积雪深度为气象可选变量，仅在需要估算作物霜冻伤害影响时（如果启用此功能）使用。如果无法每天获得观测数据， `SnowMAUS`模块也可以模拟积雪深度。此外还有一些基于上述变量推导得到的气象变量：

====== ========================================================= ===============
名称   描述                                                       单位
====== ========================================================= ===============
E0     Penman公式下自由水面潜在蒸发量                               |cmday-1|
ES0    Penman公式下裸土潜在蒸发量                                   |cmday-1|
ET0    Penman或Penman-Monteith公式下参考作物冠层的潜在蒸发量         |cmday-1|
TEMP   日均温（(TMIN + TMAX)/2）                                   |C|
DTEMP  日间平均温度（(TEMP + TMAX)/2）                              |C|
TMINRA TMIN的7日滑动平均值                                          |C|
====== ========================================================= ===============


PCSE中气象数据的使用方式
--------------------------------

为了向仿真引擎提供气象数据，PCSE 引入了 `WeatherDataProvider` 的概念。它可以从多种来源获取气象数据，但为引擎提供统一的数据访问接口。这个原理可以通过一个基于“快速入门”部分中提供的气象数据文件的示例来进行解释
:download:`downloads/quickstart_part3.zip`。在本例中，我们将使用 ExcelWeatherDataProvider 从 Excel 文件 `nl1.xlsx` 中读取气象数据::

    >>> import pcse
    >>> from pcse.input import ExcelWeatherDataProvider
    >>> wdp = ExcelWeatherDataProvider('nl1.xlsx')

我们可以直接使用 `print()` 打印气象数据提供者，以获得其内容的概览::

    >>> print(wdp)
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

此外，我们还可以用日期对象调用气象数据提供器，以获取该日期对应的 `WeatherDataContainer` 对象::

    >>> from datetime import date
    >>> day = date(2006,7,3)
    >>> wdc = wdp(day)

同样，我们可以打印 WeatherDataContainer 来显示其内容::

    >>> print(wdc)
    Weather data for 2006-07-03 (DAY)
    IRRAD:  29290000.00  J/m2/day
     TMIN:        17.20   Celsius
     TMAX:        29.60   Celsius
      VAP:        12.80       hPa
     RAIN:         0.00    cm/day
       E0:         0.77    cm/day
      ES0:         0.69    cm/day
      ET0:         0.72    cm/day
     WIND:         2.90     m/sec
    Latitude  (LAT):    51.97 degr.
    Longitude (LON):     5.67 degr.
    Elevation (ELEV):    7.0 m.

对于单个气象元素，可以通过标准的点号 Python 语法访问::

    >>> print(wdc.TMAX)
    29.6

最后，为了方便起见，WeatherDataProvider 还可以通过表示日期的字符串调用。
该字符串可以是 YYYYMMDD 或 YYYYDDD 格式::

    >>> print wdp("20060703")
    Weather data for 2006-07-03 (DAY)
    IRRAD:  29290000.00  J/m2/day
     TMIN:        17.20   Celsius
     TMAX:        29.60   Celsius
      VAP:        12.80       hPa
     RAIN:         0.00    cm/day
       E0:         0.77    cm/day
      ES0:         0.69    cm/day
      ET0:         0.72    cm/day
     WIND:         2.90     m/sec
    Latitude  (LAT):    51.97 degr.
    Longitude (LON):     5.67 degr.
    Elevation (ELEV):    7.0 m.

也可以使用 YYYYDDD 格式::

    >>> print wdp("2006183")
    Weather data for 2006-07-03 (DAY)
    IRRAD:  29290000.00  J/m2/day
     TMIN:        17.20   Celsius
     TMAX:        29.60   Celsius
      VAP:        12.80       hPa
     RAIN:         0.00    cm/day
       E0:         0.77    cm/day
      ES0:         0.69    cm/day
      ET0:         0.72    cm/day
     WIND:         2.90     m/sec
    Latitude  (LAT):    51.97 degr.
    Longitude (LON):     5.67 degr.
    Elevation (ELEV):    7.0 m.


PCSE 中的数据提供者
===================

为了进行模拟，PCSE 需要接收气象、参数值和农艺管理等输入数据。为获取这些所需输入，已经编写了多个数据提供者，可以从多种不同的数据源读取这些输入。此外，特别注意避免对某一特定数据库和文件格式的依赖。因此，PCSE 与特定的文件格式或数据库之间没有直接关联。这确保了可以使用多种数据来源，包括简单文件、关系型数据库以及互联网资源。

.. _Weather data providers:

气象数据提供者
--------------

PCSE 默认提供了多种气象数据提供者。首先，PCSE 包含基于文件的气象数据提供者，通过磁盘上的输入文件获取数据。:ref:`CABOWeatherDataProvider <CABOWeatherDataProvider>` 以及 :ref:`ExcelWeatherDataProvider <ExcelWeatherDataProvider>` 使用 `CABO Weather System`_ 定义的数据结构。ExcelWeatherDataProvider 的优势是数据可以存储在 Excel 文件中，这比 CABOWeatherDataProvider 的 ASCII 文件更易处理。此外，还有一种支持简单 CSV 数据格式的气象数据提供者 :ref:`CSVWeatherDataProvider <CSVWeatherDataProvider>`。

此外， `OpenMeteo`_ 公司提供了一个免费的 API（有一定限制），可以检索地球上任意地点的气象时间序列数据。历史数据基于 ERA5，天气预报数据来自包括 ECMWF 在内的多个不同提供者。PCSE 现在内置了 :ref:`OpenMeteoWeatherDataProvider <OpenMeteoWeatherDataProvider>`，可以通过该 API 获取气象信息。

最后，农业气候学中还提供了由 `NASA Power database`_ 发布的全球气象数据，分辨率为 0.25x0.25 度。PCSE 提供了 :ref:`NASAPowerWeatherDataProvider <NASAPowerWeatherDataProvider>`，能够根据给定的经纬度，从互联网获取 NASA Power 的数据。



.. _CABO Weather System: http://edepot.wur.nl/43010
.. _NASA Power database: http://power.larc.nasa.gov
.. _European Crop Growth Monitoring System: http://marswiki.jrc.ec.europa.eu/agri4castwiki/index.php/Weather_Monitoring
.. _OpenMeteo: https://open-meteo.com/

.. _Data providers for parameter values:

作物参数值
---------------------

PCSE 针对作物参数有一个专门的数据提供者::ref:`YAMLCropDataprovider <YAMLCropDataprovider>`。
与通用数据提供者不同的是，
该数据提供者可以读取和存储多种作物的参数集，而通用数据提供者只能存放单一作物参数集。
因此，这个作物数据提供者特别适合于运行有多种作物轮作的情景，因为它能够切换当前激活的作物。

最基本的用法是，不带参数调用 YAMLCropDataProvider。它会
从 github 仓库 https://github.com/ajwdewit/WOFOST_crop_parameters
获取作物参数::

    >>> from pcse.input import YAMLCropDataProvider
    >>> p = YAMLCropDataProvider()
    >>> print(p)
    YAMLCropDataProvider - crop and variety not set: no activate crop parameter set!

此时，所有作物和品种的参数都已从 github 仓库加载，但尚未设置激活的作物。
因此，我们可以激活某个特定作物及其品种：

    >>> p.set_active_crop('wheat', 'Winter_wheat_101')
    >>> print(p)
    YAMLCropDataProvider - current active crop 'wheat' with variety 'Winter_wheat_101'
    Available crop parameters:
     {'DTSMTB': [0.0, 0.0, 30.0, 30.0, 45.0, 30.0], 'NLAI_NPK': 1.0, 'NRESIDLV': 0.004,
     'KCRIT_FR': 1.0, 'RDRLV_NPK': 0.05, 'TCPT': 10, 'DEPNR': 4.5, 'KMAXRT_FR': 0.5,
     ...
     ...
     'TSUM2': 1194, 'TSUM1': 543, 'TSUMEM': 120}

实际操作时，通常 **无需手动激活作物参数集**，因为 AgroManager 可以自动完成此操作。
只需在农业管理定义中设置合适的 `crop_name` 和 `variety_name`，在模型模拟过程中
将自动激活对应的作物和品种::

    AgroManagement:
    - 1999-08-01:
        CropCalendar:
            crop_name: wheat
            variety_name: Winter_wheat_101
            crop_start_date: 1999-09-15
            crop_start_type: sowing
            crop_end_date:
            crop_end_type: maturity
            max_duration: 300
        TimedEvents:
        StateEvents:

此外，还可以从本地文件系统加载 YAML 参数文件::

    >>> p = YAMLCropDataProvider(fpath=r"D:\UserData\sources\WOFOST_crop_parameters")
    >>> print(p)
    YAMLCropDataProvider - crop and variety not set: no activate crop parameter set!

最后，也可以通过指定 github 仓库的 URL，从你自己 fork 的仓库拉取数据::

    >>> p = YAMLCropDataProvider(repository="https://raw.githubusercontent.com/<your_account>/WOFOST_crop_parameters/master/")

注意，该 URL 应当指向原始文件所在的位置。对于 github，这些 URL 一般以 `https://raw.githubusercontent` 开头，对于其他系统（如 gitlab），请参考其手册。

为了提升参数加载的性能，YAMLCropDataProvider 会创建一个缓存文件，相较于每次加载 YAML 文件，使用缓存可以极大缩短读取时间。当从本地文件系统读取 YAML 文件时，模块会确保在本地 YAML 文件更新后重新创建缓存文件。需要强调的是，*当参数是通过 URL 获取时，这种机制无法实现* ，有可能会从过时的缓存文件读取参数。在这种情况下，请使用 `force_reload=True` 参数来确保强制从 URL 加载最新参数。

通用数据提供者
----------------------

PCSE 为模拟模型中的参数值读取，提供了若干模块。所有参数数据提供者的基本理念都是返回一个 python 字典对象，将参数名和参数值作为键值对。该理念不依赖于参数来源，可以是本地文件、关系型数据库或互联网数据源。

PCSE 提供了两种基于文件的参数数据读取方式。第一种是 :ref:`CABOFileReader <CABOFileReader>` ，用于读取 CABO 格式参数文件，这类文件通常用于 FORTRAN 或 FST 模型。另一种更为灵活的读取器是 :ref:`PCSEFileReader <PCSEFileReader>` ，采用 python 语言自身作为语法。这也意味着 PCSE 参数文件可以使用所有 python 语法特性。

模型参数的封装
-------------------------------

如前文所述，PCSE 需要参数来定义土壤、作物以及一个额外的辅助类参数集合，称为 'site'。不过，PCSE 中的不同模块需求各异，有的只需要访问作物参数，有的则需要组合不同参数集中的值。例如，根系动力学模块会将最大根系深度计算为作物最大根系深度（作物参数）和土壤最大根系深度（土壤参数）两者中的较小值。

为了方便访问来自不同参数集的各种参数，所有参数都通过 `ParameterProvider` 对象组合，从而实现对所有可用参数的统一访问。此外，由于每个参数集合都采用基本的键/值对原则来访问名称和值，因此可以很方便地在 ParameterProvider 中组合来自不同来源的参数::

    >>> import os
    >>> import sqlalchemy as sa
    >>> from pcse.input import CABOFileReader, PCSEFileReader
    >>> from pcse.base import ParameterProvider
    >>> from pcse.db.pcse import fetch_sitedata
    >>> import pcse.settings

    # Retrieve crop data from a CABO file
    >>> cropfile = os.path.join(data_dir, 'sug0601.crop')
    >>> crop = CABOFileReader(cropfile)

    # Retrieve soildata from a PCSE file
    >>> soilfile = os.path.join(data_dir, 'lintul3_springwheat.soil')
    >>> soil = PCSEFileReader(soilfile)

    # Retrieve site data from the PCSE demo DB
    >>> db_location = os.path.join(pcse.settings.PCSE_USER_HOME, "pcse.db")
    >>> db_engine = sa.create_engine("sqlite:///" + db_location)
    >>> db_metadata = sa.MetaData(db_engine)
    >>> site = fetch_sitedata(db_metadata, grid=31031, year=2000)

    # Combine everything into one ParameterProvider object and print some values
    >>> params = ParameterProvider(sitedata=site, soildata=soil, cropdata=crop)
    >>> print(params["AMAXTB"]) # maximum leaf assimilation rate
    [0.0, 22.5, 1.0, 45.0, 1.13, 45.0, 1.8, 36.0, 2.0, 36.0]
    >>> print(params["DRATE"])  # maximum soil drainage rate
    30.0
    >>> print(params["WAV"])  # site-specific initial soil water amount
    10.0


.. _Data providers for agromanagement:

农事管理数据提供者
------------------

与气象和参数值类似，PCSE 也有多个用于农事管理（agromanagement）的数据提供者。农事管理的输入结构相比参数值或气象变量更加复杂。

在 PCSE 中，定义农事管理最全面的方式是使用 YAML 结构，这在上文  :ref:`defining agromanagement <refguide_agromanagement>` 部分中已进行了描述。为了读取这种数据结构，可以使用 :ref:`YAMLAgroManagementReader <YAMLAgroManagementReader>` 模块，并可直接将其作为输入传递给 Engine。

如果希望从 CGMS 数据库读取农事管理输入，请参见有关数据库工具 CGMS 的相关章节。需要注意的是，在 CGMS 数据库中对农事管理的支持仅限于作物历（crop calendars）。CGMS 数据库目前尚不支持定义状态或定时事件。

PCSE 全局设置
====================

PCSE 有许多设置定义了一些全局性的行为。例如，全局变量 PCSE_USER_HOME 用于定义用户的主文件夹位置。
这些设置保存在两个文件中：1）可以在 PCSE 安装目录的 `settings/` 文件夹下找到 `default_settings.py` ，此文件不应被更改。2） `user_settings.py`，位于用户主目录下的 `.pcse` 文件夹中。在 Windows 系统下，这通常为 `c:\\users\\<username>\\.pcse`，而在 Linux 系统下通常为 '/home/<username>/.pcse'。

要修改 PCSE 的全局设置，可以通过编辑 `user_settings.py` 文件，将需要修改的项目取消注释并修改其值。请注意，配置文件中的依赖关系需要遵循，因为默认设置和用户设置是分别解析的。

如需增加新的 PCSE 全局设置，只需在 `user_settings.py` 文件中添加新的条目。请注意，设置项应全部使用大写字母（ALL_CAPS）命名。设置文件中以 '_' 开头的变量名会被忽略，其它变量名则会生成警告并被忽略。

如果用户设置文件损坏，导致 PCSE 启动失败，建议删除用户主目录下 `.pcse` 文件夹中的 `user_settings.py` 文件。下次启动 PCSE 时， `user_settings.py` 会根据默认设置重新生成，并将所有设置注释掉。

在 PCSE 内，用户可以通过导入 settings 模块方便地访问所有设置：：

    >>> import pcse.settings
    >>> pcse.settings.PCSE_USER_HOME
    'C:\\Users\\wit015\\.pcse'
    >>> pcse.settings.METEO_CACHE_DIR
    'C:\\Users\\wit015\\.pcse\\meteo_cache'

