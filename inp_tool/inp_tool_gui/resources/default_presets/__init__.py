"""GUI 内置的默认 sweep preset 集合(随包分发)。

本目录下的 ``.yaml`` 文件会被 ``seed_default_presets()`` 拷到用户的
``~/.config/cfd--changer/presets/`` 作为首次启动的初始内容。
要新增默认 preset,只需把 ``.yaml`` 文件放到此目录,然后同步
``inp_tool_gui/preset_library.py`` 里的 ``_BUILTIN_PRESETS`` 元组。
"""
