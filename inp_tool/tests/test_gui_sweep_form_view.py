"""SweepFormView 测试 — ConfigStore 单向数据流的 FormView。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造传入 ConfigStore,view.config_store 返回同一对象
- 修改 template → emit store_changed(new_store) 且新 store 的 template 已更新
- 修改 output_dir / naming → emit store_changed
- _sync_from_store() 重新从 store 拉值(用于外部 replace 后)
- 默认空 store 也能构造
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _make_store(template="t.inp", output_dir="/out", naming="case",
                preset_ref=None, sweeps=None, conditions=()):
    from inp_tool_gui.models.config_store import ConfigStore
    return ConfigStore(
        template=template,
        output_dir=output_dir,
        naming=naming,
        preset_ref=preset_ref,
        sweeps=sweeps or {},
        conditions=conditions,
    )


def test_sweep_form_view_creates_from_config_store(qapp):
    """传入 ConfigStore,view.config_store 必须返回同一对象。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    assert view.config_store is store


def test_sweep_form_view_emits_store_changed_on_field_edit(qapp):
    """修改 template → emit store_changed(new_store),新 store 的 template 已更新。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    received = []
    view.store_changed.connect(lambda s: received.append(s))
    view._edit_tpl.setText("new.inp")
    view._edit_tpl.editingFinished.emit()
    assert len(received) == 1
    assert received[0].template == "new.inp"
    # 其他字段保持原样
    assert received[0].output_dir == "/out"
    assert received[0].naming == "case"


def test_sweep_form_view_emits_on_output_dir_edit(qapp):
    """修改 output_dir → emit store_changed。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    received = []
    view.store_changed.connect(lambda s: received.append(s))
    view._edit_out.setText("/new_out")
    view._edit_out.editingFinished.emit()
    assert len(received) == 1
    assert received[0].output_dir == "/new_out"
    assert received[0].template == "t.inp"


def test_sweep_form_view_emits_on_naming_edit(qapp):
    """修改 naming → emit store_changed。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    received = []
    view.store_changed.connect(lambda s: received.append(s))
    view._edit_naming.setText("run_{mach}")
    view._edit_naming.editingFinished.emit()
    assert len(received) == 1
    assert received[0].naming == "run_{mach}"


def test_sweep_form_view_sync_from_store_updates_fields(qapp):
    """外部 replace 后 _sync_from_store() 把新值拉回 widget。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    new_store = store.replace(template="x.inp", output_dir="/d2", naming="n2")
    view._sync_from_store(new_store)
    assert view._edit_tpl.text() == "x.inp"
    assert view._edit_out.text() == "/d2"
    assert view._edit_naming.text() == "n2"


def test_sweep_form_view_sync_from_store_blocks_signals(qapp):
    """_sync_from_store 期间 editingFinished 不应 emit store_changed。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    received = []
    view.store_changed.connect(lambda s: received.append(s))
    new_store = store.replace(template="x.inp")
    view._sync_from_store(new_store)
    assert received == []


def test_sweep_form_view_default_construction_with_empty_store(qapp):
    """空 sweeps 的 ConfigStore 也能正常构造(无 axes 列表渲染异常)。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store(sweeps={})
    view = SweepFormView(store)
    assert view._axes_table.rowCount() == 0
    assert view._table.columnCount() == 4  # case_id / path / params / applied


def test_sweep_form_view_has_required_widgets(qapp):
    """骨架必须暴露 _edit_tpl / _edit_out / _edit_naming / _axes_table / _table。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    store = _make_store()
    view = SweepFormView(store)
    assert view._edit_tpl is not None
    assert view._edit_out is not None
    assert view._edit_naming is not None
    assert view._axes_table is not None
    assert view._table is not None


def test_sweep_form_view_renders_axes_from_store(qapp):
    """传 sweeps={k: spec} 时,axes_table 渲染 1 行,AxisSpec 信息保留。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="explicit_list", values=(1, 2, 3))
    store = _make_store(sweeps={"mach": spec})
    view = SweepFormView(store)
    assert view._axes_table.rowCount() == 1
