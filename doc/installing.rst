安装 PCSE
===============

需求与依赖
-----------------------------

PCSE 正在 Ubuntu Linux 18.04 和 Windows 10 平台上使用 python 3.9 和 python 3.10 进行开发。
由于 Python 是跨平台的语言，PCSE 可以在 Linux、Windows 或 Mac OSX 上同样良好地运行。
在安装 PCSE 之前，您的系统上必须已经安装 Python，我们将在下文中展示如何操作。
PCSE 依赖于一些其他的 python 包，具体如下::

- SQLAlchemy<2.0
- PyYAML>=3.11
- openpyxl>=3.0
- requests>=2.0.0
- pandas>=0.20
- traitlets-pcse==5.0.0.dev

列表中的最后一个包是对 `traitlets`_ 包的修改版本，PCSE 使用它所提供的额外功能。

.. _Enthought Canopy: https://www.enthought.com/products/canopy/
.. _Anaconda: https://store.continuum.io/cshop/anaconda/
.. _PythonXY: https://python-xy.github.io/
.. _HomeBrew: http://brew.sh
.. _traitlets: https://traitlets.readthedocs.io/en/stable/

配置您的 python 环境
----------------------------------

配置 PCSE 的 python 环境，一种便捷的方法是通过 `Anaconda`_ python 发行版。
在本 PCSE 文档中，所有 PCSE 的安装和使用示例均基于 Windows 10 平台。

首先，我们建议您下载并安装 `MiniConda`_ python 发行版。它提供了最小的 python 环境，我们将用来为 PCSE 启动专用环境。在本指南的其余部分，我们假设您使用 Windows 10 并安装 64 位的 python 3 版 miniconda（``Miniconda3-latest-Windows-x86_64.exe``）。我们即将创建的环境不仅包含了 PCSE 所需依赖，还包含了许多其他有用的包，例如 `IPython`_、`Pandas`_ 和 `Jupyter notebook`_。这些包也将在“入门”部分使用。

.. _MiniConda: http://conda.pydata.org/miniconda.html
.. _Pandas: http://pandas.pydata.org/
.. _Jupyter notebook: https://jupyter.org/
.. _IPython: https://ipython.org/

安装完 MiniConda 后，你应该打开命令行窗口，检查 *conda* 是否已正确安装：

.. code-block:: doscon

    (base) C:\>conda info

         active environment : base
        active env location : C:\data\Miniconda3
                shell level : 1
           user config file : C:\Users\wit015\.condarc
     populated config files : C:\Users\wit015\.condarc
              conda version : 23.11.0
        conda-build version : not installed
             python version : 3.8.18.final.0
                     solver : libmamba (default)
           virtual packages : __archspec=1=x86_64
                              __conda=23.11.0=0
                              __win=0=0
           base environment : C:\data\Miniconda3  (writable)
          conda av data dir : C:\data\Miniconda3\etc\conda
      conda av metadata url : None
               channel URLs : https://conda.anaconda.org/conda-forge/win-64
                              https://conda.anaconda.org/conda-forge/noarch
                              https://repo.anaconda.com/pkgs/main/win-64
                              https://repo.anaconda.com/pkgs/main/noarch
                              https://repo.anaconda.com/pkgs/r/win-64
                              https://repo.anaconda.com/pkgs/r/noarch
                              https://repo.anaconda.com/pkgs/msys2/win-64
                              https://repo.anaconda.com/pkgs/msys2/noarch
              package cache : C:\data\Miniconda3\pkgs
                              C:\Users\wit015\.conda\pkgs
                              C:\Users\wit015\AppData\Local\conda\conda\pkgs
           envs directories : C:\data\Miniconda3\envs
                              C:\Users\wit015\.conda\envs
                              C:\Users\wit015\AppData\Local\conda\conda\envs
                   platform : win-64
                 user-agent : conda/23.11.0 requests/2.31.0 CPython/3.8.18 Windows/10 Windows/10.0.19045 solver/libmamba conda-libmamba-solver/23.11.1 libmambapy/1.5.3
              administrator : False
                 netrc file : None
               offline mode : False


现在我们将使用 Conda 环境文件来重建我们用于开发和运行 PCSE 的 python 环境。首先你需要下载 conda 环境文件 (:download:`downloads/py3_pcse.yml`)。该环境包含 Jupyter notebook 和 IPython，这些是在 `getting started` 部分和示例 notebook 中需要用到的。请将环境文件保存在一个临时位置，例如 ``d:\temp\make_env\``。现在我们将用 ``conda env create`` 命令创建一个专用虚拟环境，并用 ``-f py3_pcse.yml`` 参数指定环境文件，如下所示：

.. code-block:: doscon

    (C:\Miniconda3) D:\temp\make_env>conda env create -f py3_pcse.yml
    Fetching package metadata .............
    Solving package specifications: .
    intel-openmp-2 100% |###############################| Time: 0:00:00   6.39 MB/s

    ... Lots of output here

    Installing collected packages: traitlets-pcse
    Successfully installed traitlets-pcse-5.0.0.dev0
    #
    # To activate this environment, use:
    # > activate py3_pcse
    #
    # To deactivate an active environment, use:
    # > deactivate
    #
    # * for power-users using bash, you must source
    #

你现在可以激活你的环境（注意命令提示符中会多出 ``(py3_pcse)``）:

.. code-block:: doscon

    D:\temp\make_env>conda activate py3_pcse
    Deactivating environment "C:\Miniconda3"...
    Activating environment "C:\Miniconda3\envs\py3_pcse"...

    (py3_pcse) D:\temp\make_env>

安装 PCSE
---------------

安装 PCSE 最简单的方法是通过 python 包索引（ `PyPI`_）。
通过 PyPI 安装主要适用于你希望在自己的脚本中使用 PCSE 提供的功能，但不打算修改或为 PCSE 做贡献的情况。使用 `pip` 包管理器可以从 python 包索引搜索、下载并安装对应包到你的 python 环境中（如下以 PCSE 6.0.0 为例）：


.. code-block:: doscon

    (py3_pcse) D:\temp\make_env>pip install pcse

    Collecting pcse
      Downloading https://files.pythonhosted.org/packages/8c/92/d4444cce1c58e5a96f4d6dc9c0e042722f2136df24a2750352e7eb4ab053/PCSE-5.4.0.tar.gz (791kB)
        100% |¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦¦| 798kB 1.6MB/s
    Requirement already satisfied: numpy>=1.6.0 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (1.15.1)
    Requirement already satisfied: SQLAlchemy>=0.8.0 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (1.2.11)
    Requirement already satisfied: PyYAML>=3.11 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (3.13)
    Requirement already satisfied: xlrd>=0.9.3 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (1.1.0)
    Requirement already satisfied: xlwt>=1.0.0 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (1.3.0)
    Requirement already satisfied: requests>=2.0.0 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (2.19.1)
    Requirement already satisfied: pandas>=0.20 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (0.23.4)
    Requirement already satisfied: traitlets-pcse==5.0.0.dev in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pcse) (5.0.0.dev0)
    Requirement already satisfied: chardet<3.1.0,>=3.0.2 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from requests>=2.0.0->pcse) (3.0.4)
    Requirement already satisfied: idna<2.8,>=2.5 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from requests>=2.0.0->pcse) (2.7)
    Requirement already satisfied: certifi>=2017.4.17 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from requests>=2.0.0->pcse) (2018.8.24)
    Requirement already satisfied: urllib3<1.24,>=1.21.1 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from requests>=2.0.0->pcse) (1.23)
    Requirement already satisfied: python-dateutil>=2.5.0 in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pandas>=0.20->pcse) (2.7.3)
    Requirement already satisfied: pytz>=2011k in c:\miniconda3\envs\py3_pcse\lib\site-packages (from pandas>=0.20->pcse) (2018.5)
    Requirement already satisfied: six in c:\miniconda3\envs\py3_pcse\lib\site-packages (from traitlets-pcse==5.0.0.dev->pcse) (1.11.0)
    Requirement already satisfied: decorator in c:\miniconda3\envs\py3_pcse\lib\site-packages (from traitlets-pcse==5.0.0.dev->pcse) (4.3.0)
    Requirement already satisfied: ipython-genutils in c:\miniconda3\envs\py3_pcse\lib\site-packages (from traitlets-pcse==5.0.0.dev->pcse) (0.2.0)
    Building wheels for collected packages: pcse
      Running setup.py bdist_wheel for pcse ... done
      Stored in directory: C:\Users\wit015\AppData\Local\pip\Cache\wheels\2f\e6\2c\3952ff951dffea5ab2483892edcb7f9310faa319d050d3be6c
    Successfully built pcse
    twisted 18.7.0 requires PyHamcrest>=1.9.0, which is not installed.
    mkl-random 1.0.1 requires cython, which is not installed.
    mkl-fft 1.0.4 requires cython, which is not installed.
    Installing collected packages: pcse
    Successfully installed pcse-6.0.0

如果你希望参与 PCSE 的开发或为其做出贡献，那么你应该在 GitHub 上 fork `PCSE repository`_，并通过 `git clone` 获取 PCSE 的本地副本。你可以参考 github_ 上的帮助文档，对于 Windows 或 Mac 用户，也可以使用 `GitHub Desktop`_ 应用程序。

.. _GitHub Desktop: https://desktop.github.com/
.. _GitHub: https://help.github.com/
.. _PCSE repository: https://github.com/ajwdewit/pcse
.. _PyPI: https://pypi.python.org/pypi/PCSE

PCSE 测试
------------

为了保证其完整性，PCSE 软件包内置了一定数量的内部测试，这些测试会随着 PCSE 的安装自动完成。此外，PCSE 的 git 仓库中还包含了大量位于 `test` 文件夹下的测试用例，这些测试更为全面，但运行时间较长（例如可能需要一小时以上）。内部测试为用户提供了一种快速方式，以确保不同组件产生的输出与预期结果一致。完整的测试集主要面向开发者使用。

内部测试所需的测试数据可以在 `pcse.tests.test_data` 包中找到，同时还包括一个 SQLite 数据库（pcse.db）。该数据库存放于你主目录下的 `.pcse` 文件夹内，并会在你第一次导入 PCSE 时自动创建。如果你手动删除该数据库文件，则在下次导入 PCSE 时会再次自动生成。

要运行 PCSE 的内部测试，需要启动 python 并导入 pcse：

.. code-block:: doscon

    (py3_pcse) C:\>python
    Python 3.10.14 | packaged by conda-forge | (main, Mar 20 2024, 12:40:08) [MSC v.1938 64 bit (AMD64)]
    Type 'copyright', 'credits' or 'license' for more information
    >>> import pcse
    Building PCSE demo database at: C:\Users\wit015\.pcse\pcse.db ... OK
    >>>

接下来，可以通过调用包顶层的 `test()` 函数来执行测试：

.. code-block:: doscon

    >>> pcse.test()
    runTest (pcse.tests.test_abioticdamage.Test_FROSTOL) ... ok
    runTest (pcse.tests.test_partitioning.Test_DVS_Partitioning) ... ok
    runTest (pcse.tests.test_evapotranspiration.Test_PotentialEvapotranspiration) ... ok
    runTest (pcse.tests.test_evapotranspiration.Test_WaterLimitedEvapotranspiration1) ... ok
    runTest (pcse.tests.test_evapotranspiration.Test_WaterLimitedEvapotranspiration2) ... ok
    runTest (pcse.tests.test_respiration.Test_WOFOSTMaintenanceRespiration) ... ok
    runTest (pcse.tests.test_penmanmonteith.Test_PenmanMonteith1) ... ok
    runTest (pcse.tests.test_penmanmonteith.Test_PenmanMonteith2) ... ok
    runTest (pcse.tests.test_penmanmonteith.Test_PenmanMonteith3) ... ok
    runTest (pcse.tests.test_penmanmonteith.Test_PenmanMonteith4) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager1) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager2) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager3) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager4) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager5) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager6) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager7) ... ok
    runTest (pcse.tests.test_agromanager.TestAgroManager8) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedGrainMaize) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedPotato) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedWinterRapeseed) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedWinterWheat) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialGrainMaize) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialWinterWheat) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialWinterRapeseed) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedSunflower) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialSpringBarley) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialSunflower) ... ok
    runTest (pcse.tests.test_wofost72.TestPotentialPotato) ... ok
    runTest (pcse.tests.test_wofost72.TestWaterlimitedSpringBarley) ... ok

    ----------------------------------------------------------------------
    Ran 30 tests in 22.482s

    OK

如果模型输出与期望输出一致，测试将报告 'OK'，否则将产生错误，并提供详细的回溯以指出问题发生的位置。请注意，当测试用例被增加或删除时，结果可能会与上面的输出有所不同。

此外，SQLAlchemy 可能会出现一个可以安全忽略的警告：

    C:\Miniconda3\envs\py3_pcse\lib\site-packages\sqlalchemy\sql\sqltypes.py:603: SAWarning:
    Dialect sqlite+pysqlite does *not* support Decimal objects natively, and SQLAlchemy must
    convert from floating point - rounding errors and other issues may occur. Please consider
    storing Decimal numbers as strings or integers on this platform for lossless storage.

