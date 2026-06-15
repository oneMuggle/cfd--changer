"""inp_tool_gui.app:QApplication 入口与主窗口构造。

设计:
- ``build_window()`` 纯函数,返回 :class:`MainWindow` 实例(不显示、不入事件循环),
  供 ``main()`` 和单元测试复用。
- ``main(argv)`` 构造 :class:`QApplication` + 显示窗口 + 进入 ``exec_()``,返回 exit code。
- ``__main__.py`` 调用 ``main()``,可由 ``python -m inp_tool_gui`` 启动。
"""
import sys
from typing import Optional, Sequence

from PySide2.QtWidgets import QApplication, QMainWindow

APP_NAME = "inp-tool-gui"
APP_VERSION = "0.10.0-dev"
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800


def build_window() -> QMainWindow:
    """构造主窗口(不显示,不入事件循环)。

    v0.10 集成版:挂载完整 :class:`MainWindow`(5 controllers + 4 标签页 +
    菜单/工具栏/状态栏)。``MainWindow`` 在 :mod:`inp_tool_gui.main_window` 内
    定义,此处内嵌 import 以保持 ``app`` 模块零循环依赖。
    """
    from inp_tool_gui.main_window import MainWindow
    return MainWindow()


def main(argv: Optional[Sequence[str]] = None) -> int:
    """GUI 入口:启动事件循环,返回 exit code。"""
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    window = build_window()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
