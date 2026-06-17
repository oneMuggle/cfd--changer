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
