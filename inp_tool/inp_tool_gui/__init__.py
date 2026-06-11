"""inp_tool_gui: PySide2 桌面 GUI 包(v0.10 Win7 兼容)。

设计原则:
- 零侵入核心:``inp_tool`` core 仍是零依赖,GUI 包是可选并列包
- 复用 core API:GUI 只 ``import inp_tool`` 调用 ``parser/writer/diff/sweep``,不重新实现
- 独立 spec:打包走 ``inp_tool_gui.spec``,与 CLI 的 ``inp_tool.spec`` 互不干扰
"""

__version__ = "0.10.0-dev"
