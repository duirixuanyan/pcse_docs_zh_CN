# -*- coding: utf-8 -*-
#
# PyWofost 文档构建配置文件，由 sphinx-quickstart 于 2012年7月1日23:03:43 创建。
#
# 当使用 execfile() 执行本文件时，当前目录被设置为该文件所在目录。
#
# 注意：本自动生成文件中未包含所有可能的配置项。
#
# 所有配置项都有默认值；被注释掉的部分仅用于展示默认值。

import sys, os
import datetime

# 添加 PCSE 的 python 路径
pwd = os.path.dirname(__file__)
path = os.path.abspath(os.path.join(pwd, ".."))
sys.path.append(path)
version_full = __import__("pcse").__version__
version_short = version_full[0:3]

# 如果 autodoc 的扩展（或需要文档化的模块）在其他目录下，请在此添加这些目录到 sys.path。
# 如果该目录是相对于文档根目录的，请使用 os.path.abspath 将其转换为绝对路径，如下所示。
#sys.path.insert(0, os.path.abspath('.'))

# -- 通用配置 -----------------------------------------------------

# 如果文档需要指定最小 Sphinx 版本，请在此处说明。
#needs_sphinx = '1.0'

# 在此处添加需要的 Sphinx 扩展模块名，作为字符串。可以是 Sphinx 自带的扩展（命名为 'sphinx.ext.*'），也可以是自定义扩展。
extensions = ['sphinx.ext.autodoc', 'sphinx.ext.todo', 'sphinx.ext.coverage',
              'sphinx.ext.mathjax', 'sphinx.ext.viewcode', 'sphinx.ext.autosectionlabel']

# 在此添加包含模板的路径，路径相对于本目录。
templates_path = ['_templates']

# 指定源文件的后缀名。
source_suffix = '.rst'

# 指定源文件的编码方式。
source_encoding = 'utf-8-sig'

# 指定主 toctree 文档。
master_doc = 'index'

# 项目的基本信息。
project = u'Python Crop Simulation Environment'
author = 'Allard de Wit'
this_year = datetime.date.today().year
copyright = '%s, %s' % (this_year, author)


# 项目版本信息，用于替换 |version| 和 |release| 变量，同时在生成文档的多个地方使用。
#
# 简短的 X.Y 版本号。
version = version_full
# 完整版本号，包括 alpha/beta/rc 标签。
release = version_short

# Sphinx 自动生成内容时采用的语言。具体支持的语言请参考文档。
#language = None

# 有两种方式替换 |today| ：设置 today 为某个非 False 的值，则直接使用；
#today = ''
# 否则使用 today_fmt 作为 strftime 的格式化字符串。
#today_fmt = '%B %d, %Y'

# 要忽略的文件和文件夹模式（相对于源目录）。
exclude_patterns = ['_build']

# reST 默认角色（用于诸如 `text` 这样的标记），适用于所有文档。
#default_role = None

# 如果为 True，':func:' 等交叉引用文本会自动添加括号 '()'。
#add_function_parentheses = True

# 如果为 True，所有说明单元标题（如 .. function::）前会加上当前模块名。
#add_module_names = True

# 如果为 True，sectionauthor 和 moduleauthor 指令会在输出中显示。默认会被忽略。
#show_authors = False

# 使用的 Pygments（代码高亮）风格名称。
pygments_style = 'sphinx'

# 模块索引排序时要忽略的前缀列表。
#modindex_common_prefix = []


# -- HTML 输出选项 ----------------------------------------------------------

# 用于 HTML 和 HTML Help 页面的主题。可用主题列表请查阅文档。
#html_theme = 'sphinxdoc'
html_theme = "sphinx_rtd_theme"

# 主题选项是主题特有的，用于进一步自定义外观。各主题可用选项请查阅文档。
#html_theme_options = {}

# 添加包含自定义主题的路径（相对于此目录）。
#html_theme_path = ["."]

# Sphinx 文档集的名称。如果为 None，则默认为 "<project> v<release> documentation"。
#html_title = None

# 导航栏的短标题。默认与 html_title 相同。
#html_short_title = None

# 侧边栏顶部显示的图片文件名（相对于此目录）。
#html_logo = None

# 用作文档 favicon 的图像文件名（在静态路径下）。
# 此文件应为 Windows 图标文件(.ico)，且尺寸为 16x16 或 32x32 像素。
#html_favicon = None

# 在此处添加包含自定义静态文件（如样式表）的路径，相对于本目录。
# 这些文件会在内置静态文件后复制，因此命名为 "default.css" 的文件会覆盖内置的同名文件。
#html_static_path = ['_static']

# 如果非空字符串，则会在每页底部插入 '最后更新：' 时间戳，格式由指定的 strftime 格式字符串决定。
#html_last_updated_fmt = '%b %d, %Y'

# 如果为 True，SmartyPants 会将引号和破折号转换为排印上更正确的字符实体。
#html_use_smartypants = True

# 自定义侧边栏模板，将文档名称映射到模板名称。
#html_sidebars = {}

# 需要渲染为页面的额外模板，将页面名称映射到模板名称。
#html_additional_pages = {}

# 如果为 False，则不生成模块索引。
#html_domain_indices = True

# 如果为 False，则不生成索引页面。
#html_use_index = True

# 如果为 True，索引会按每个首字母分拆为单独页面。
#html_split_index = False

# 如果为 True，页面会添加 reST 源文件的链接。
#html_show_sourcelink = True

# 如果为 True，则 HTML 页脚会显示 "Created using Sphinx"。默认值为 True。
#html_show_sphinx = True

# 如果为 True，则 HTML 页脚会显示 "(C) Copyright ..."。默认值为 True。
#html_show_copyright = True

# 如果为 True，则会输出一个 OpenSearch 描述文件，且所有页面会包含指向它的 <link> 标签。
# 此选项的值必须是最终 HTML 所服务的基础 URL。
#html_use_opensearch = ''

# 这是 HTML 文件的文件名后缀（如 ".xhtml"）。
#html_file_suffix = None

# HTML 帮助文档生成器的输出文件基本名。
htmlhelp_basename = 'PCSEdoc'


# -- LaTeX 输出选项 --------------------------------------------------

latex_elements = {
# 纸张大小（'letterpaper' 或 'a4paper'）。
'papersize': 'a4paper',

# 字体大小（'10pt'、'11pt' 或 '12pt'）。
'pointsize': '11pt',

# LaTeX 前导码中添加的其他内容。
#'preamble': '',
}

# 将文档树分组为 LaTeX 文件。元组列表
# （起始源文件、目标名称、标题、作者、文档类型 [howto/manual]）。
latex_documents = [
  ('index', 'PCSE.tex', u'PCSE Documentation',
   u'Allard de Wit', 'manual'),
]

# 用于在标题页顶部显示的图片文件名（相对于本目录）。
#latex_logo = None

# 对于 "manual" 文档，若为 True，则顶层标题为“部分”（parts）而不是“章节”（chapters）。
#latex_use_parts = False

# 如果为 True，内部链接后会显示页码引用。
#latex_show_pagerefs = False

# 如果为 True，外部链接后会显示 URL 地址。
#latex_show_urls = False

# 需要作为附录添加到所有手册文档的文档。
#latex_appendices = []

# 如果为 False，则不生成模块索引。
#latex_domain_indices = True


# -- 手册页输出选项 ------------------------------------------------------------

# 每个手册页一个条目。元组列表
# (起始源文件，名称，描述，作者，手册部分)。
man_pages = [
    ('index', 'PCSE', u'PCSE Documentation',
     [u'Allard de Wit'], 1)
]

# 如果为 True，则在外部链接后显示 URL 地址。
#man_show_urls = False


# -- Texinfo 输出选项 ---------------------------------------------------------

# 将文档树分组为 Texinfo 文件。元组列表
# (起始源文件，目标名称，标题，作者，
#  目录菜单项，描述，类别)
texinfo_documents = [
  ('index', 'PCSE', u'PCSE Documentation',
   u'Allard de Wit', 'PCSE', 
   'PCSE is used to implement the WOFOST crop simulation.',
   'Miscellaneous'),
]

# 需要作为附录添加到所有手册文档的文档。
#texinfo_appendices = []

# 如果为 False，则不生成模块索引。
#texinfo_domain_indices = True

# 如何显示 URL 地址：'footnote'（脚注）、'no'（不显示）或 'inline'（内联）。
#texinfo_show_urls = 'footnote'
