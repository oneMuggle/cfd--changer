"""SweepForm import-compat shim 测试。

DEPRECATED: use SweepFormView directly. This test guards the backward-compat alias
so old import paths keep working.

测试覆盖:
- ``from inp_tool_gui.widgets.sweep_form import SweepForm`` 仍可工作
- ``SweepForm`` 是 ``SweepFormView`` 的子类
- 新代码传 ``ConfigStore`` 给 ``SweepForm`` 也可工作(与 SweepFormView 一致)
- 旧调用 ``SweepForm(sweep_ctrl)`` 仍能工作(降级为最小 ConfigStore,best-effort)
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    """整个测试模块共享一个 QApplication。"""
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_sweep_form_import_compat_still_works(qapp):
    """`from .sweep_form import SweepForm` 仍可工作(转发到 SweepFormView)。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    assert issubclass(SweepForm, SweepFormView), (
        "SweepForm shim must subclass SweepFormView"
    )


def test_sweep_form_compat_accepts_config_store(qapp):
    """新代码传 ConfigStore 给 SweepForm 也可工作(与 SweepFormView 一致)。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.models.config_store import ConfigStore
    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case",
        preset_ref=None, sweeps={}, conditions=(),
    )
    form = SweepForm(store)
    assert form.config_store is store


def test_sweep_form_compat_accepts_legacy_controller(qapp):
    """旧调用 `SweepForm(sweep_ctrl)` 仍能工作(降级为最小 ConfigStore)。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController

    ctrl = SweepController()
    form = SweepForm(ctrl)
    # 不应抛异常;form 的 store 字段是 ConfigStore(空)
    assert form.config_store.template == ""
    assert form.config_store.output_dir == ""
    assert form.config_store.naming == "case"


def test_sweep_form_compat_accepts_legacy_controller_with_loaded_sweep(qapp):
    """legacy SweepController 加载了 sweep 后,Shim 提取 template/output_dir/naming。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController

    ctrl = SweepController()
    ctrl.load_from_dict({
        "template": "x.inp",
        "output_dir": "/out_dir",
        "naming": "case_{alpha}",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    form = SweepForm(ctrl)
    assert form.config_store.template == "x.inp"
    assert form.config_store.output_dir == "/out_dir"
    assert form.config_store.naming == "case_{alpha}"


def test_sweep_form_compat_emits_store_changed(qapp):
    """SweepForm shim 继承 store_changed 信号,用户编辑字段也会 emit。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.models.config_store import ConfigStore

    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case",
        preset_ref=None, sweeps={}, conditions=(),
    )
    form = SweepForm(store)
    received = []
    form.store_changed.connect(lambda s: received.append(s))
    form._edit_tpl.setText("new.inp")
    form._edit_tpl.editingFinished.emit()
    assert len(received) == 1
    assert received[0].template == "new.inp"


def test_legacy_sweep_form_still_importable(qapp):
    """历史实现 ``_LegacySweepForm`` 仍可导入(回归测试用)。"""
    from inp_tool_gui.widgets.sweep_form import _LegacySweepForm
    assert _LegacySweepForm is not None
    # 公开的 SweepForm 是兼容 shim,不是 _LegacySweepForm 本身
    from inp_tool_gui.widgets.sweep_form import SweepForm
    assert SweepForm is not _LegacySweepForm
