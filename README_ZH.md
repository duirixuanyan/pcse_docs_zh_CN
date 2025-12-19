<h1 align="center">pcse_docs_zh_CN</h1>

<p align="center">
  <a href="/README_ZH.md"><strong>简体中文</strong></a> / <a href="/README.md"><strong>English</strong></a> 
</p>

<p align="center">
  PCSE 文档的简体中文翻译。
</p>

> 中文翻译基于 [PCSE version: 6.0.12（2025年11月6日）](https://github.com/ajwdewit/pcse/tree/3b232476dd1215c0218c4251882e991c4fc12ead)

## 中文手册

我在 [GitHub Releases](https://github.com/duirixuanyan/pcse_docs_zh_CN/releases) 上提供中文手册的下载。

也可以在 [readthedocs](https://pcse-docs-zh-cn.readthedocs.io/zh-cn/latest/) 上查看。

## PCSE手册

可以在 [PCSE 6.0 documentation](https://pcse.readthedocs.io/en/stable/) 上查看。

## PCSE代码

可以在 [Python Crop Simulation Environment - PCSE](https://github.com/ajwdewit/pcse) 上查看。

## PCSE notebook

可以在 [A collection of PCSE notebooks](https://github.com/ajwdewit/pcse_notebooks) 上查看。

## 翻译过程

### 翻译rst文件

位置在pcse_docs_zh_CN\doc

### 翻译代码中的注释

代码位置在pcse_docs_zh_CN\pcse

我是在cursor中用自动选择的模型翻译的，提示词如下:

```txt
翻译为中文，不要添加或修改`符号，**特别注意::符号必须原样保留，不能简化为:或中文冒号：`**，`部分不翻译，..部分不翻译，*和`和``前后的空格保留，标题要翻译
```

### 修改代码注释中的表格

搜索代码注释中的 `====` ，将简单表对齐，确保正常显示。可以用[Online reStructuredText editor](https://rsted.info.ucl.ac.be/)预览。

## 构建方法

```bash
# 安装Sphinx
pip install Sphinx

# 修改位置，进入目录
cd "G:\GitHub\pcse_docs_zh_CN\doc"

# 开始编译
.\make.bat html
```