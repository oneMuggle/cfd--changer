"""SweepController.update_field + SweepForm 实时编辑(v0.16.1 整合版)。

- 单元测试:SweepController.update_field(纯 Python,不依赖 PySide2)
- widget 测试:SweepForm 的实时编辑字段 + YAML 加载自动填充
"""
from inp_tool_gui.controllers.sweep_controller import SweepController
import pytest


# --- SweepController.update_field 单元测试(无 PySide2 依赖) ---------


def test_sweep_controller_update_template():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("template", "y.inp")
    assert sc.template == "y.inp"


def test_sweep_controller_update_sweeps_axis():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("sweeps.alpha", [0, 5, 10, 15])
    assert sc.case_count == 4


def test_sweep_controller_update_naming():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("naming", "run_{alpha}")
    assert sc.case_count == 3


def test_sweep_controller_update_invalid_field_raises():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    with pytest.raises(KeyError):
        sc.update_field("nonexistent_field", "x")


def test_sweep_controller_update_before_load_raises():
    sc = SweepController()
    with pytest.raises(RuntimeError):
        sc.update_field("template", "x.inp")


# --- SweepForm widget 测试(需要 QApplication) ------------------------

import pytest


@pytest.fixture(scope="module")
def qapp():
    """整个测试模块共享一个 QApplication。"""
    from PySide2.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_sweep_form_has_template_editor(qapp):
    """SweepForm 构造后,_edit_tpl 已从 controller 拉取到模板路径。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    form = SweepForm(sc)
    assert form._edit_tpl.text() == "x.inp"


def test_sweep_form_has_three_top_labels(qapp):
    """顶部 3 行各有 QLabel 显示中文模板路径/输出目录/命名模式。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool.i18n_gui import tg

    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    form = SweepForm(sc)

    from PySide2.QtWidgets import QLabel
    labels = form.findChildren(QLabel)
    label_texts = {lbl.text() for lbl in labels}

    # 期望包含 3 个 i18n 文本
    assert tg("sweep.lbl.template") in label_texts
    assert tg("sweep.lbl.output") in label_texts
    assert tg("sweep.lbl.naming") in label_texts


def test_sweep_form_yaml_load_fills_fields(qapp, tmp_path):
    """load_yaml 后,表单字段应自动从 controller 回填。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    form = SweepForm(sc)
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(
        "template: t.inp\n"
        "output_dir: o\n"
        "sweeps:\n"
        "  alpha: [0, 5]\n",
        encoding="utf-8",
    )
    form.load_yaml(str(yaml_file))
    assert form._edit_tpl.text() == "t.inp"
    assert form._edit_out.text() == "o"
    assert form._axes_table.rowCount() == 1


# --- Task 7:轴表 cell widget 化测试 ---------------------------------


def test_sweep_form_axes_table_uses_combobox_cells(qapp):
    """轴表第 0 列 cell 是 QComboBox(非 QTableWidgetItem)。"""
    from PySide2.QtWidgets import QComboBox, QLabel, QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")  # 触发 cell widget 构造
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox), "got {}".format(type(cell))
    cell1 = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell1, (QLabel, QLineEdit))


def test_sweep_form_axes_combobox_populated_with_vars(qapp):
    """combobox items 来自 controller.available_vars(当前模板)。"""
    from PySide2.QtWidgets import QComboBox

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox)
    labels = [cell.itemText(i) for i in range(cell.count())]
    # 至少含 3 个枚举轴(label 形式为 "key (枚举:...)")
    assert any(lbl.startswith("turbulence") for lbl in labels)
    assert any(lbl.startswith("energy") for lbl in labels)
    assert any(lbl.startswith("gas") for lbl in labels)


# --- Task 8: 类型校验测试(int/float on edit finished) ----------------


def test_sweep_form_validates_int_axis_on_edit_finished(qapp, monkeypatch):
    """整型轴:输入 'abc' 失焦,状态栏报错。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="test.int_var",
        label="test.int_var [int] = 1",
        kind="int",
        block="test", keyword="int_var", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("test.int_var", "1")
    cell = form._axes_table.cellWidget(form._axes_table.rowCount() - 1, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("abc")
    cell.editingFinished.emit()
    status_text = form._lbl_status.text()
    assert "整数" in status_text or "int" in status_text.lower()


def test_sweep_form_accepts_float_d_notation(qapp, monkeypatch):
    """浮点轴接受 '1.0d-3' (FORTRAN 双精度写法)。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="test.float_var",
        label="test.float_var [float] = 1.0",
        kind="float",
        block="test", keyword="float_var", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("test.float_var", "1.0d-3")
    cell = form._axes_table.cellWidget(form._axes_table.rowCount() - 1, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("1.0d-3")
    cell.editingFinished.emit()
    text = form._lbl_status.text()
    assert "不是浮点" not in text


def test_sweep_form_orphan_axis_disables_run_button(monkeypatch):
    """失效轴(不在当前模板的)→ 红底 + 运行按钮禁用。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    def fake_available(template_path=None):
        return [VarSpec(
            key="good", label="good [int] = 1", kind="int",
            block="b", keyword="good", value_idx=0,
        )]
    monkeypatch.setattr(ctrl, "available_vars", fake_available)

    form._append_axis_row("good", "1")
    form._append_axis_row("orphan", "1")
    form._scan_orphan_axes()

    assert not form._btn_run.isEnabled()
    assert not form._btn_run_dry.isEnabled()
    assert "未识别" in form._lbl_status.text() or "失效" in form._lbl_status.text()


def test_sweep_form_no_orphan_no_disabled_message(monkeypatch):
    """无失效轴:状态栏无「未识别」字样。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    def fake_available(template_path=None):
        return [
            VarSpec(key="a", label="a [int] = 1", kind="int", block="b", keyword="a", value_idx=0),
            VarSpec(key="b", label="b [int] = 2", kind="int", block="b", keyword="b", value_idx=0),
        ]
    monkeypatch.setattr(ctrl, "available_vars", fake_available)
    form._append_axis_row("a", "1")
    form._append_axis_row("b", "2")
    form._scan_orphan_axes()
    assert "未识别" not in form._lbl_status.text()
