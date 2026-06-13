"""GUI 烟雾测试(阶段 1)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless,
所以这套测试可在 CI / 服务器上无障碍通过。

只验证:
- ``inp_tool_gui.app`` 模块可 import
- 暴露的常量正确
- ``build_window()`` 不抛异常 + 标题/尺寸符合预期
- ``__main__`` 模块有可调用的 ``main()``
"""
import os

# 在 import Qt 任何东西之前设置 platform,避免 X server / Wayland 失败
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_app_constants_exposed():
    """版本号与名称暴露给 pyproject / spec 使用。"""
    from inp_tool_gui.app import APP_NAME, APP_VERSION

    assert APP_NAME == "inp-tool-gui"
    assert APP_VERSION == "0.10.0-dev"


def test_build_window_smoke():
    """``build_window()`` 不抛异常,标题与尺寸正确。"""
    from PySide2.QtWidgets import QApplication
    from inp_tool_gui.app import (
        APP_NAME,
        APP_VERSION,
        DEFAULT_HEIGHT,
        DEFAULT_WIDTH,
        build_window,
    )

    # QApplication 单例:已有就复用,没有就建一个
    app = QApplication.instance() or QApplication([])
    assert app is not None

    window = build_window()
    try:
        assert window.windowTitle() == f"{APP_NAME} v{APP_VERSION}"
        assert window.width() == DEFAULT_WIDTH
        assert window.height() == DEFAULT_HEIGHT
    finally:
        window.close()
        window.deleteLater()


def test_main_module_importable():
    """``inp_tool_gui.__main__`` 有可调用的 ``main``。"""
    from inp_tool_gui import __main__ as gui_main

    assert hasattr(gui_main, "main")
    assert callable(gui_main.main)
