"""``python -m inp_tool_gui`` 入口。

仅委托给 :func:`inp_tool_gui.app.main`,保持 entry 单一。
"""
import sys

from inp_tool_gui.app import main

if __name__ == "__main__":
    sys.exit(main())
