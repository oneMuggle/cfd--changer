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
