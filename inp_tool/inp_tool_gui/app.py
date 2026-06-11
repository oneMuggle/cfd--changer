"""inp_tool_gui.app:QApplication 入口与主窗口构造。

设计:
- ``build_window()`` 纯函数,返回 :class:`QMainWindow` 实例(不显示、不入事件循环),
  供 ``main()`` 和单元测试复用。
- ``main(argv)`` 构造 :class:`QApplication` + 显示窗口 + 进入 ``exec_()``,返回 exit code。
- ``__main__.py`` 调用 ``main()``,可由 ``python -m inp_tool_gui`` 启动。
"""
import sys
from typing import Optional, Sequence

from PySide2.QtWidgets import QApplication, QMainWindow

APP_NAME = "inp-tool-gui"
APP_VERSION = "0.10.0-dev"
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 720


def build_window() -> QMainWindow:
    """构造主窗口(不显示,不入事件循环)。

    阶段 1 仅设置标题与初始尺寸;阶段 2 起将替换为 ``MainWindow``。
    """
    window = QMainWindow()
    window.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
    window.resize(DEFAULT_WIDTH, DEFAULT_HEIGHT)
    return window


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
