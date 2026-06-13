# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for inp_tool GUI (PySide2 based, Win7 兼容)
#
# v0.10 新增。与 CLI spec (inp_tool.spec) 并列,共享 inp_tool core 零依赖。
#
# 用法:
#   pip install ".[gui-build]"
#   pyinstaller --clean --noconfirm inp_tool_gui.spec
#   ./dist/inp-tool-gui            # Linux
#   dist\inp-tool-gui.exe          # Windows(含 Win7 SP1)
#
# 跨平台编译:Windows 二进制必须 Windows 上编(无交叉编译)。
# Win7 验证:用户在物理机 / 虚拟机双击 EXE,跑 win7 自测 checklist。
#
# PySide2 hook:
# - PyInstaller 自带 hook-PySide2.* 覆盖大部分 Qt 子模块
# - hiddenimports 加 QtCore/QtGui/QtWidgets 显式列出以防漏
# - plugins 目录(qml/qsvg 等)Qt 启动时动态加载,PyInstaller 默认会包含

import sys
from pathlib import Path

block_cipher = None

# ----------------------------------------------------------------------
# 1. Analysis
# ----------------------------------------------------------------------
a = Analysis(
    ['inp_tool_gui/__main__.py'],
    pathex=[],
    binaries=[],
    # GUI 不打包 examples/web(资源不需要;用户用 QFileDialog 选)
    datas=[],
    hiddenimports=[
        # inp_tool core(必)
        'inp_tool',
        'inp_tool.parser',
        'inp_tool.writer',
        'inp_tool.diff',
        'inp_tool.model',
        'inp_tool.sweep',
        # GUI 包(独立,不进 core)
        'inp_tool_gui',
        'inp_tool_gui.app',
        'inp_tool_gui.main_window',
        'inp_tool_gui.controllers',
        'inp_tool_gui.controllers.file_controller',
        'inp_tool_gui.controllers.edit_controller',
        'inp_tool_gui.controllers.sweep_controller',
        'inp_tool_gui.controllers.detect_controller',
        'inp_tool_gui.controllers.diff_controller',
        'inp_tool_gui.widgets',
        'inp_tool_gui.widgets.inp_tree',
        'inp_tool_gui.widgets.value_editor',
        'inp_tool_gui.widgets.detect_panel',
        'inp_tool_gui.widgets.preset_dialog',
        'inp_tool_gui.widgets.sweep_form',
        'inp_tool_gui.widgets.diff_viewer',
        # PySide2 子模块(QApplication / QtCore / QtGui / QtWidgets 启动必需)
        'PySide2',
        'PySide2.QtCore',
        'PySide2.QtGui',
        'PySide2.QtWidgets',
        'PySide2.QtPrintSupport',
        # shiboken2(Python ↔ C++ 绑定运行时)
        'shiboken2',
        # yaml(sweep 内部可选 import;若用户装了 [yaml] 还要保证打包)
        'yaml',
        'setuptools._vendor.backports',
        'setuptools._vendor.backports.tarfile',
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
# 2. EXE: 单文件输出(Win7 兼容)
# ----------------------------------------------------------------------
exe_name = 'inp-tool-gui.exe' if sys.platform.startswith('win') else 'inp-tool-gui'

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
    # GUI 模式:console=False(Win)避免后台黑窗
    # 但开发期想看 PyInstaller stderr,可临时改 True
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,           # 后续可加 .ico
)