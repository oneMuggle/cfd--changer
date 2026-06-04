# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for inp_tool CLI — 目录式 (onedir) 模式
#
# 用法:
#   pip install ".[build]"
#   pyinstaller --clean --noconfirm inp_tool_onedir.spec
#   ./dist/inp-tool-dist/inp-tool --version   # Linux/macOS
#   dist\inp-tool-dist\inp-tool.exe --version  # Windows
#
# 与 inp_tool.spec(单文件)的区别:此版本产出 dist/inp-tool-dist/ 目录
# 优点: 启动快(<0.5s,无需解压到临时目录)
# 缺点: 整个目录需打包成 zip 才能分发
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
# 2. EXE: 只含脚本本身(不含 binaries/datas)
# ----------------------------------------------------------------------
# binaries/datas 留给 COLLECT 放到目录里
exe_name = 'inp-tool.exe' if sys.platform.startswith('win') else 'inp-tool'

exe = EXE(
    pyz,
    a.scripts,
    [],         # 不放 binaries,留给 COLLECT
    [],         # 不放 datas,留给 COLLECT
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    # onedir 模式:runtime_tmpdir='.' 让 EXE 在自己所在目录解压,
    # 避免 _MEI 临时目录找不到 libpython (PyInstaller 5.x + Py3.8 已知问题)
    runtime_tmpdir='.',
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

# ----------------------------------------------------------------------
# 3. COLLECT: 收集 binaries + datas 到 dist/inp-tool-dist/ 目录
# ----------------------------------------------------------------------
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='inp-tool-dist',
)
