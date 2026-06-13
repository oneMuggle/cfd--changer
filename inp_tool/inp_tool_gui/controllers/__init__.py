"""Controllers:业务逻辑层,与 Qt 解耦,只依赖 inp_tool core。

controller 是"纯 Python"层,易测(不实例化 QApplication);
widget 是"纯 Qt"层,只负责渲染 + signal 转发。
"""
