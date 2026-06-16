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
