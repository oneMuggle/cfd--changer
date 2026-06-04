# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for inp_tool CLI (cross-platform: Linux/macOS/Windows)
#
# 用法:
#   pip install ".[build]"
#   pyinstaller --clean --noconfirm inp_tool.spec
#   ./dist/inp-tool --version   # Linux/macOS
#   dist\inp-tool.exe --version # Windows
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
    # 注意:有些 stdlib 模块被 setuptools/pkg_resources 间接依赖(email/xml),
    # 排除太激进会启动失败,这里只排除确定不用的:
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
# 2. EXE: 单文件输出
# ----------------------------------------------------------------------
# Windows:  .exe
# Linux:    无后缀
# macOS:    无后缀
exe_name = 'inp-tool.exe' if sys.platform.startswith('win') else 'inp-tool'

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # 不开 UPX(部分杀软误报)
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,        # CLI 工具,需要 stdout
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # 后续可加 .ico
)
