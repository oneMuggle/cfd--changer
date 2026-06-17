"""SweepWizard 测试 — 4-step 向导 Step 1 完整 + Step 2/3/4 占位。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。

测试覆盖:
- 构造传入 ConfigStore,view.config_store 返回同一对象
- 修改 template / output_dir / naming → emit store_changed(new_store) 且新 store 字段已更新
- _sync_from_store() 重新从 store 拉值(用于外部 replace 后)
- _sync_from_store 期间 editingFinished 不应 emit store_changed
- Step 切换:_btn_next 推进 currentIndex,_btn_prev 回退,边界保护
- 取消按钮:_on_cancel 调用 parent.close()(有 parent)/ self.deleteLater()(无 parent)
- 步骤指示器:Step 1 时 _btn_prev 禁用
- 浏览按钮:弹 QFileDialog(用 monkeypatch 不弹真框)
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


# --- 构造 ----------------------------------------------------------------


def test_wizard_creates_from_config_store(qapp):
    """传入 ConfigStore,view.config_store 必须返回同一对象。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w.config_store is store


def test_wizard_default_construction_with_empty_store(qapp):
    """空 ConfigStore(空 template/output)也能正常构造。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store(template="", output_dir="", naming="case")
    w = SweepWizard(store)
    assert w._edit_tpl.text() == ""
    assert w._edit_out.text() == ""
    assert w._edit_naming.text() == "case"


def test_wizard_has_required_widgets(qapp):
    """骨架必须暴露 _edit_tpl / _edit_out / _edit_naming / _stack / 按钮。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w._edit_tpl is not None
    assert w._edit_out is not None
    assert w._edit_naming is not None
    assert w._stack is not None
    assert w._stack.count() == 4
    assert w._btn_prev is not None
    assert w._btn_next is not None
    assert w._btn_cancel is not None


# --- form -> store 数据流 -----------------------------------------------


def test_wizard_step1_template_edit_emits_store_changed(qapp):
    """修改 template → emit store_changed(new_store),新 store 的 template 已更新。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._edit_tpl.setText("new.inp")
    w._edit_tpl.editingFinished.emit()
    assert len(received) == 1
    assert received[0].template == "new.inp"
    # 其他字段保持原样
    assert received[0].output_dir == "/out"
    assert received[0].naming == "case"


def test_wizard_step1_output_dir_edit_emits_store_changed(qapp):
    """修改 output_dir → emit store_changed。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._edit_out.setText("/new_out")
    w._edit_out.editingFinished.emit()
    assert len(received) == 1
    assert received[0].output_dir == "/new_out"
    assert received[0].template == "t.inp"


def test_wizard_step1_naming_edit_emits_store_changed(qapp):
    """修改 naming → emit store_changed。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._edit_naming.setText("run_{mach}")
    w._edit_naming.editingFinished.emit()
    assert len(received) == 1
    assert received[0].naming == "run_{mach}"


def test_wizard_naming_empty_falls_back_to_case(qapp):
    """naming 清空 → fallback 到 "case"(store 里 naming = "case")。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._edit_naming.setText("   ")  # 只有空白
    w._edit_naming.editingFinished.emit()
    # 若当前 store.naming 已经是 "case",则 _emit_store 不会 emit (new == old)
    # 这里 store 初始 naming="case",所以应当不 emit
    assert received == []


def test_wizard_naming_empty_emits_when_differs(qapp):
    """naming 从 "case" 改成空白 → emit,naming fallback 到 "case",等效于无变化。"""
    # 关键点:naming 字段永远不会是空字符串(总是 fallback "case")
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store(naming="custom")
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._edit_naming.setText("")
    w._edit_naming.editingFinished.emit()
    assert len(received) == 1
    assert received[0].naming == "case"


def test_wizard_no_emit_on_unchanged_field(qapp):
    """用户编辑了又改回原值 → _emit_store 检测 new == old,不发信号。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    # 把 template 改成 "new.inp" 再改回 "t.inp" —— setText 一次不会触发 editingFinished
    # 我们直接触发一次 editingFinished 即可
    w._edit_tpl.setText("t.inp")  # 等于原值
    w._edit_tpl.editingFinished.emit()
    assert received == []


# --- store -> form 数据流 -----------------------------------------------


def test_wizard_sync_from_store_updates_fields(qapp):
    """外部 replace 后 _sync_from_store() 把新值拉回 widget。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    new_store = store.replace(template="x.inp", output_dir="/d2", naming="n2")
    w._sync_from_store(new_store)
    assert w._edit_tpl.text() == "x.inp"
    assert w._edit_out.text() == "/d2"
    assert w._edit_naming.text() == "n2"


def test_wizard_sync_from_store_blocks_signals(qapp):
    """_sync_from_store 期间 editingFinished 不应 emit store_changed。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    new_store = store.replace(template="x.inp")
    w._sync_from_store(new_store)
    assert received == []


# --- 步骤切换 -----------------------------------------------------------


def test_wizard_step1_prev_disabled(qapp):
    """Step 1 时 _btn_prev 必须禁用。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w._stack.currentIndex() == 0
    assert w._btn_prev.isEnabled() is False
    assert w._btn_next.isEnabled() is True


def test_wizard_next_button_advances_step(qapp):
    """点 _btn_next → currentIndex +1,prev 启用。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    w._btn_next.click()
    assert w._stack.currentIndex() == 1
    assert w._btn_prev.isEnabled() is True


def test_wizard_on_next_advances(qapp):
    """_on_next() 等价于点 _btn_next(覆盖直接调方法的路径)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    w._on_next()
    assert w._stack.currentIndex() == 1


def test_wizard_on_next_boundary(qapp):
    """在 Step 4(index=3)再点 next → 保持 index=3,不溢出。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    w._stack.setCurrentIndex(3)
    w._on_next()
    assert w._stack.currentIndex() == 3


def test_wizard_on_prev_boundary(qapp):
    """在 Step 1(index=0)再点 prev → 保持 index=0。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w._stack.currentIndex() == 0
    w._on_prev()
    assert w._stack.currentIndex() == 0


def test_wizard_step2_3_4_are_placeholders(qapp):
    """Steps 2/3/4 是 QWidget 页面(非 None,index 1/2/3 都有 widget)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    for i in range(1, 4):
        page = w._stack.widget(i)
        assert page is not None


# --- 取消按钮 -----------------------------------------------------------


def test_wizard_cancel_closes_parent(qapp):
    """有 parent 时,_on_cancel() 调 parent.close() 而非 deleteLater。"""
    from PySide2.QtWidgets import QDialog
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    parent = QDialog()
    store = _make_store()
    w = SweepWizard(store, parent=parent)
    # 不弹真框
    w._on_cancel()
    # QDialog.close() 默认 hide() + accept,这里用 isVisible 验证
    assert parent.isVisible() is False


def test_wizard_cancel_no_parent_calls_delete_later(qapp):
    """无 parent 时,_on_cancel() 调 self.deleteLater() —— 不应崩。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    # deleteLater 只是排到事件循环末尾,直接调不崩就行
    w._on_cancel()
    # 不抛异常即通过


# --- 浏览按钮(monkeypatch QFileDialog) ----------------------------------


def test_wizard_browse_template_emits_store_changed(qapp, monkeypatch):
    """点 _btn_tpl(选 mcfd.inp)→ _edit_tpl 填路径 + emit store_changed。"""
    from PySide2.QtWidgets import QFileDialog
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("/picked/template.inp", "")),
    )
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._btn_tpl.click()
    assert w._edit_tpl.text() == "/picked/template.inp"
    assert any(s.template == "/picked/template.inp" for s in received)


def test_wizard_browse_template_cancel_no_emit(qapp, monkeypatch):
    """点 _btn_tpl 但用户在 QFileDialog 选 Cancel(空路径)→ 不 emit。"""
    from PySide2.QtWidgets import QFileDialog
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._btn_tpl.click()
    assert received == []


def test_wizard_browse_output_emits_store_changed(qapp, monkeypatch):
    """点 _btn_out(选目录)→ _edit_out 填路径 + emit store_changed。"""
    from PySide2.QtWidgets import QFileDialog
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: "/picked/out"),
    )
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._btn_out.click()
    assert w._edit_out.text() == "/picked/out"
    assert any(s.output_dir == "/picked/out" for s in received)


def test_wizard_browse_output_cancel_no_emit(qapp, monkeypatch):
    """点 _btn_out 但用户取消(空路径)→ 不 emit。"""
    from PySide2.QtWidgets import QFileDialog
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory",
        staticmethod(lambda *a, **k: ""),
    )
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._btn_out.click()
    assert received == []


# --- Step 2(选轴 + 设值)— Task 4.3 ------------------------------------


def test_wizard_step2_widget_present(qapp):
    """wizard 必须暴露 _step2(SweepWizardStep2 实例)。"""
    from inp_tool_gui.widgets.sweep_wizard_step2 import SweepWizardStep2
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert isinstance(w._step2, SweepWizardStep2)


def test_wizard_step2_initial_table_empty(qapp):
    """初始 store.sweeps 为空 → 表格无 row。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w._step2._table.rowCount() == 0
    assert w._step2.selected == {}


def test_wizard_step2_refresh_from_store_populates_table(qapp):
    """外部 replace → step2 表格重建。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import AxisSpec
    store = _make_store()
    w = SweepWizard(store)
    new_store = store.replace_sweep(
        "mach", AxisSpec(kind="range", range_min=0, range_max=2, range_step=1),
    )
    w._sync_from_store(new_store)
    assert w._step2._table.rowCount() == 1
    # 第 0 行第 0 列是 "mach"
    key_item = w._step2._table.item(0, 0)
    assert key_item.text() == "mach"


def test_wizard_step2_add_axis_via_method(qapp):
    """调 step2.add_axis('turbulence') → store_changed 触发,sweeps dict 更新。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore
    from inp_tool_gui.widgets.sweep_wizard_step2 import SweepWizardStep2
    store = ConfigStore(template="t", output_dir="o", naming="case",
                        preset_ref=None, sweeps={}, conditions=())
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2.add_axis("turbulence")  # 直接调方法 (不需要真实拖拽)
    assert any("turbulence" in s.sweeps for s in received)
    assert w._store.sweeps.get("turbulence") is not None  # 最新 store
    # 表格也加了 row
    assert w._step2._table.rowCount() == 1
    # step2 内部 _selected 也更新
    assert "turbulence" in w._step2.selected


def test_wizard_step2_remove_axis_emits(qapp):
    """删除一个轴 → store_changed 触发。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    store = ConfigStore(
        template="t", output_dir="o", naming="case",
        preset_ref=None,
        sweeps={"mach": AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)},
        conditions=(),
    )
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2.remove_axis("mach")
    assert any("mach" not in s.sweeps for s in received)
    assert "mach" not in w._store.sweeps
    assert w._step2._table.rowCount() == 0


def test_wizard_step2_add_duplicate_axis_no_op(qapp):
    """重复 add 同一个 key → 不应触发 store_changed(去重)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = ConfigStore(template="t", output_dir="o", naming="case",
                        preset_ref=None, sweeps={}, conditions=())
    w = SweepWizard(store)
    # 先 set_vars 让 step2 知道有哪些变量可选
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2.add_axis("mach")
    w._step2.add_axis("mach")  # duplicate
    assert len(received) == 1


def test_wizard_step2_remove_nonexistent_axis_no_op(qapp):
    """remove_axis 不存在的 key → 不 emit。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2.remove_axis("not_there")
    assert received == []


def test_wizard_step2_default_spec_for_enum(qapp):
    """add_axis('turbulence') 用 VarSpec.enum_values 推断 enum_subset(全选)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="turbulence", label="turbulence", kind="enum",
                enum_values=("sst", "kw", "sa"),
                block=None, keyword=None, value_idx=None),
    ])
    w._step2.add_axis("turbulence")
    spec = w._store.sweeps["turbulence"]
    assert spec.kind == "enum_subset"
    assert set(spec.values) == {"sst", "kw", "sa"}


def test_wizard_step2_default_spec_for_int(qapp):
    """add_axis('mach') 用 VarSpec.kind='int' 推断 range[0,2,step=1]。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    w._step2.add_axis("mach")
    spec = w._store.sweeps["mach"]
    assert spec.kind == "range"
    assert spec.range_min == 0
    assert spec.range_max == 2
    assert spec.range_step == 1


def test_wizard_step2_default_spec_unknown_key(qapp):
    """add_axis 对 step2 不认识的 key → explicit_list,空 tuple。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    # tree 是空的,key 'foo' 不在 _all_vars
    w._step2.add_axis("foo")
    spec = w._store.sweeps["foo"]
    assert spec.kind == "explicit_list"
    assert spec.values == ()


def test_wizard_step2_default_spec_for_float(qapp):
    """add_axis 用 VarSpec.kind='float' 推断 range[0.0, 2.0, step=1.0]。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="reynolds", label="reynolds [float]", kind="float",
                block="<top>", keyword="reynolds", value_idx=0),
    ])
    w._step2.add_axis("reynolds")
    spec = w._store.sweeps["reynolds"]
    assert spec.kind == "range"
    assert spec.range_min == 0.0
    assert spec.range_max == 2.0
    assert spec.range_step == 1.0


def test_wizard_step2_default_spec_for_csv_str_kind(qapp):
    """add_axis 用 VarSpec.kind='str'(非 enum/int/float)→ explicit_list。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="runtype", label="runtype [str]", kind="str",
                block="<top>", keyword="runtype", value_idx=0),
    ])
    w._step2.add_axis("runtype")
    spec = w._store.sweeps["runtype"]
    assert spec.kind == "explicit_list"
    assert spec.values == ()


def test_wizard_step2_add_button_click_adds_selected(qapp):
    """点 '添加选中' 按钮 → 把当前 tree 选中行加入已选轴。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    # 选中第一个 leaf(代表 mach)
    # 找到代表 mach 的 leaf item
    item = None
    for i in range(w._step2.tree.tree.topLevelItemCount()):
        group = w._step2.tree.tree.topLevelItem(i)
        for j in range(group.childCount()):
            child = group.child(j)
            if "mach" in child.text(0):
                item = child
                break
    assert item is not None
    w._step2.tree.tree.setCurrentItem(item)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2._btn_add.click()
    assert "mach" in w._store.sweeps
    assert any("mach" in s.sweeps for s in received)


def test_wizard_step2_add_button_no_selection_no_op(qapp):
    """点 '添加选中' 但 tree 无选中 → no-op,不 emit。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    # 清空 currentItem(默认无选中)
    w._step2.tree.tree.clearSelection()
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step2._btn_add.click()
    assert received == []


def test_wizard_step2_table_row_delete_button(qapp):
    """点删除按钮 → row 被移除 + emit store_changed。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    w._step2.add_axis("mach")
    assert w._step2._table.rowCount() == 1
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    # 拿到 cell widget 中的删除按钮并 click
    btn = w._step2._table.cellWidget(0, 2)
    btn.click()
    assert w._step2._table.rowCount() == 0
    assert any("mach" not in s.sweeps for s in received)


def test_wizard_step2_double_click_tree_adds_axis(qapp):
    """双击左侧 tree leaf → add_axis 自动触发,store 含该 key。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach [int]", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    # 找到代表 mach 的 leaf item 并触发 variable_picked 信号(模拟双击)
    w._step2.tree.variable_picked.emit("mach")
    assert "mach" in w._store.sweeps
    assert any("mach" in s.sweeps for s in received)


def test_wizard_step2_format_spec_text_range(qapp):
    """值列文本:range → 'range[min, max, step=step]'。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec
    from inp_tool_gui.widgets.sweep_wizard_step2 import _format_spec_text
    from inp_tool_gui.models.config_store import AxisSpec

    spec = AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)
    text = _format_spec_text(spec)
    assert "range" in text
    assert "0" in text and "2" in text and "1" in text


def test_wizard_step2_format_spec_text_values(qapp):
    """值列文本:enum_subset / explicit_list / csv_str → ', '.join(values)。"""
    from inp_tool_gui.widgets.sweep_wizard_step2 import _format_spec_text
    from inp_tool_gui.models.config_store import AxisSpec

    spec = AxisSpec(kind="enum_subset", values=("sst", "kw"))
    assert _format_spec_text(spec) == "sst, kw"

    spec = AxisSpec(kind="explicit_list", values=("a", "b", "c"))
    assert _format_spec_text(spec) == "a, b, c"


def test_wizard_step2_refresh_from_store_keeps_table_in_sync(qapp):
    """外部 replace → refresh_from_store → 表格 row 数 == len(store.sweeps)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import AxisSpec

    store = _make_store()
    w = SweepWizard(store)
    # 先 add 一个
    w._step2.add_axis("mach")
    assert w._step2._table.rowCount() == 1
    # 外部 replace:多了一个 axis
    new_store = w._store.replace_sweep(
        "reynolds",
        AxisSpec(kind="range", range_min=1e5, range_max=1e6, range_step=1e5),
    )
    w._sync_from_store(new_store)
    assert w._step2._table.rowCount() == 2
    assert "mach" in w._step2.selected
    assert "reynolds" in w._step2.selected


def test_wizard_step2_template_change_refreshes_tree(qapp):
    """Step 1 改 template → step2.tree 重新枚举。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store(template="")
    w = SweepWizard(store)
    # 初始 template 空 → 只 3 个枚举轴
    initial_count = len(w._step2.tree._all_vars)
    assert initial_count == 3  # turbulence/energy/gas

    # 改 template
    w._edit_tpl.setText("/some/file.inp")
    w._edit_tpl.editingFinished.emit()
    # 此时 template 已变化,但树不会自动重新枚举(避免阻塞 UI),
    # 需要 _sync_from_store 才会触发(模拟外部 replace 的路径)
    w._sync_from_store(w._store)
    # 现在 template 已变,set_template_path 会调 enumerate_vars
    # 对不存在的路径静默退回只枚举轴(3 个)
    assert w._step2.tree._template_path == "/some/file.inp"


def test_wizard_step2_table_columns(qapp):
    """表格 3 列:轴名 / 值 / 操作(列标题存在)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    store = _make_store()
    w = SweepWizard(store)
    w._step2.tree.set_vars([
        VarSpec(key="mach", label="mach", kind="int",
                block="<top>", keyword="mach", value_idx=0),
    ])
    w._step2.add_axis("mach")
    header = w._step2._table.horizontalHeader()
    # 3 列都有 label
    assert header.model().columnCount() == 3
    # 每行 3 个 cell(其中 _COL_OP 是 QPushButton widget)
    assert w._step2._table.item(0, 0) is not None  # key
    assert w._step2._table.item(0, 1) is not None  # value
    assert w._step2._table.cellWidget(0, 2) is not None  # delete button


# --- Step 3(条件依赖 when/then)— Task 4.4 -------------------------------


def test_wizard_step3_widget_present(qapp):
    """wizard 必须暴露 _step3(SweepWizardStep3 实例)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.widgets.sweep_wizard_step3 import SweepWizardStep3
    store = _make_store()
    w = SweepWizard(store)
    assert isinstance(w._step3, SweepWizardStep3)


def test_wizard_step3_initial_empty(qapp):
    """初始 store.conditions 为空 → row_count=0,空提示可见。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    store = _make_store()
    w = SweepWizard(store)
    assert w._step3.row_count() == 0
    # 没 row 时 _empty_lbl 应是 "shown"(用 isHidden 校验更稳:
    # setVisible 触发的 isVisible 需要 widget tree 已显示,headless 测试中不一定)。
    assert w._step3._empty_lbl.isHidden() is False


def test_wizard_step3_add_condition(qapp):
    """step3.add_condition('mach<1', disable_axes='turbulence') → store.conditions 长度+1。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore

    store = ConfigStore(template="t", output_dir="o", naming="case",
                        preset_ref=None, sweeps={}, conditions=())
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step3.add_condition(when_text="mach<1", disable_axes_text="turbulence")
    assert any(len(s.conditions) == 1 for s in received)
    assert len(w._store.conditions) == 1
    # verify content
    rule = w._store.conditions[0]
    assert rule.when.predicates[0].key == "mach"
    assert rule.then.disable_axes == ("turbulence",)


def test_wizard_step3_remove_condition(qapp):
    """删除一个条件 → conditions 长度-1。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore
    from inp_tool.sweep import (
        ConditionalRule, ConditionThen, parse_condition,
    )

    cond = ConditionalRule(
        when=parse_condition({"mach": "<1"}),
        then=ConditionThen(disable_axes=("turbulence",)),
    )
    store = ConfigStore(template="t", output_dir="o", naming="case",
                        preset_ref=None, sweeps={}, conditions=(cond,))
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step3.remove_condition(0)
    assert any(len(s.conditions) == 0 for s in received)
    assert len(w._store.conditions) == 0
    assert w._step3.row_count() == 0


def test_wizard_step3_refresh_from_store(qapp):
    """refresh_from_store: store 有 2 个条件 → 2 行;清空 store → 0 行。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard
    from inp_tool_gui.models.config_store import ConfigStore
    from inp_tool.sweep import (
        ConditionalRule, ConditionThen, parse_condition,
    )

    cond1 = ConditionalRule(
        when=parse_condition({"mach": "<1"}), then=ConditionThen(),
    )
    cond2 = ConditionalRule(
        when=parse_condition({"reynolds": ">=1e6"}), then=ConditionThen(),
    )
    store = ConfigStore(
        template="t", output_dir="o", naming="case",
        preset_ref=None, sweeps={}, conditions=(cond1, cond2),
    )
    w = SweepWizard(store)
    assert w._step3.row_count() == 2

    # Replace store with empty
    w._set_store(store.replace(conditions=()))
    assert w._step3.row_count() == 0


def test_wizard_step3_add_button_creates_row(qapp):
    """点 "添加条件" 按钮 → 新 row 出现(空,不 emit)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w._step3._btn_add.click()
    assert w._step3.row_count() == 1
    # 空 row → 没 when → 不 emit
    assert received == []


def test_wizard_step3_invalid_when_no_emit(qapp):
    """无效 when 字符串 → add_condition 不 emit(解析失败时静默)。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    # 无 op
    w._step3.add_condition(when_text="mach")
    assert received == []


def test_wizard_step3_edit_row_emits(qapp):
    """row 已存在 → editing 改 when 触发 emit。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    # 先 add 一条
    w._step3.add_condition(when_text="mach<1", disable_axes_text="turbulence")
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    # 改 disable_axes
    row = w._step3._rows[0]
    row._edit_dis.setText("turbulence,energy")
    row._edit_dis.editingFinished.emit()
    assert any(
        len(s.conditions) == 1
        and s.conditions[0].then.disable_axes == ("turbulence", "energy")
        for s in received
    )


def test_wizard_step3_row_delete_button_emits(qapp):
    """row 自带删除按钮 → click → store_changed emit + row 消失。"""
    from inp_tool_gui.widgets.sweep_wizard import SweepWizard

    store = _make_store()
    w = SweepWizard(store)
    w._step3.add_condition(when_text="mach<1", disable_axes_text="turbulence")
    assert w._step3.row_count() == 1
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    row = w._step3._rows[0]
    row._btn_del.click()
    assert w._step3.row_count() == 0
    assert any(len(s.conditions) == 0 for s in received)


def test_wizard_step3_parse_predicates_helper(qapp):
    """_split_predicates:多 predicate / 单 predicate / 无 op / 空。"""
    from inp_tool_gui.widgets.sweep_wizard_step3 import _split_predicates

    assert _split_predicates("mach<1,reynolds>=1e6") == {
        "mach": "<1", "reynolds": ">=1e6",
    }
    assert _split_predicates("mach==42") == {"mach": "==42"}
    assert _split_predicates("") == {}
    assert _split_predicates("noopredicate") == {}
    assert _split_predicates("<1") == {}  # 无 key


def test_wizard_step3_parse_disable_axes_helper(qapp):
    """_parse_disable_axes:逗号分隔,空段跳过。"""
    from inp_tool_gui.widgets.sweep_wizard_step3 import _parse_disable_axes

    assert _parse_disable_axes("turbulence, energy") == ("turbulence", "energy")
    assert _parse_disable_axes("a,,b") == ("a", "b")
    assert _parse_disable_axes("") == ()


def test_wizard_step3_parse_set_extra_helper(qapp):
    """_parse_set_extra:key=value 列表,空/无 = 跳过。"""
    from inp_tool_gui.widgets.sweep_wizard_step3 import _parse_set_extra

    assert _parse_set_extra("turb_init=yes,scheme=roe") == (
        ("turb_init", "yes"), ("scheme", "roe"),
    )
    assert _parse_set_extra("a=1") == (("a", "1"),)
    assert _parse_set_extra("noequals") == ()
    assert _parse_set_extra("") == ()
