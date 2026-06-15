"""SweepController.update_field + SweepLiveForm 实时编辑(阶段 5)。

纯 Python 单元测试,不依赖 PySide2。
"""
from inp_tool_gui.controllers.sweep_controller import SweepController
import pytest


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
