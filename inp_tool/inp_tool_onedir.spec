# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for inp_tool CLI — 目录式 (onedir) 模式
#
# 用法:
#   pip install ".[build]"
#   pyinstaller --clean --noconfirm inp_tool_onedir.spec
#   ./dist/inp-tool-dist/inp-tool --version   # Linux/macOS
#   dist\inp-tool-dist\inp-tool.exe --version  # Windows
#
# v0.4.2 变更 (2026-06-07):
#   实际改用"onefile 风格 EXE,放在 onedir 目录里"。
#   原设计想用 EXE+COLLECT 多文件目录式(快启动,免解压到 _MEI),
#   但 PyInstaller 5.13.2 / 6.0.0 / 6.16.0 在 Python 3.8 + Linux 上
#   都有 _MEI 找不到 libpython 的固有问题(COLLECT 模式下 EXE 启动
#   仍从 _MEI 子目录加载 libpython,但 COLLECT 把 libpython 放 EXE
#   同级目录,不在 _MEI),wrapper LD_LIBRARY_PATH 也修不了。
#   退而求其次:让 onedir 的 EXE 自包含所有 deps(等价 onefile),
#   这样 EXE 内部 _MEI 临时目录自带 libpython,可正常启动。
#   启动速度比真 onedir 慢(~0.5s 解压),但仍可分发成 zip 目录。
#
# 与 inp_tool.spec(单文件)的区别:输出路径在 dist/inp-tool-dist/ 而非 dist/。
#
# 跨平台编译:Windows 二进制必须 Windows 上编,Linux 二进制必须 Linux 上编
# (PyInstaller 不支持交叉编译)。

import sys
from pathlib import Path

block_cipher = None

# ----------------------------------------------------------------------
# 1. Analysis: 收集 inp_tool 包 + 隐式依赖
# ----------------------------------------------------------------------
a = Analysis(
    ['inp_tool/__main__.py'],
    pathex=[],
    binaries=[],
    # 把 examples/ 与 web/ 目录也打包进 binary
    # (这些是运行时资源,不是 Python 源)
    # 路径相对 spec 文件所在目录(默认 cwd = inp_tool/)
    datas=[
        ('examples', 'inp_tool/examples'),
        ('web', 'inp_tool/web'),
    ],
    # 隐式 import(防止 PyInstaller 漏掉动态加载的模块)
    hiddenimports=[
        'inp_tool',
        'inp_tool.sweep',
        'inp_tool.api',
        'inp_tool.cli',
        'inp_tool.parser',
        'inp_tool.writer',
        'inp_tool.diff',
        'inp_tool.model',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # 排除不用的 stdlib 大块(减体积)
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'tests',
        'lib2to3',
        'pdb',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ----------------------------------------------------------------------
# 2. EXE: 自包含所有 deps(onefile 风格),输出到 dist/inp-tool-dist/
# ----------------------------------------------------------------------
# Windows:  .exe
# Linux:    无后缀
# macOS:    无后缀
exe_name = 'inp-tool.exe' if sys.platform.startswith('win') else 'inp-tool'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,    # 进 EXE(自包含,避免 _MEI 找不到 libpython)
    a.datas,       # 进 EXE
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,  # 默认 _MEI 临时目录(EXE 自带 libpython,可正常加载)
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
