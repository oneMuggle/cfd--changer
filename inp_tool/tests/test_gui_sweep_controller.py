"""SweepController 单元测试(纯 Python,无需 PySide2)。

阶段 5 的 controller 部分,提前到阶段 2 commit 以便最大化 GREEN 验证。
包装 :mod:`inp_tool.sweep` 的 :class:`CaseSweep` + :func:`generate`。

注意:用 ``dry_run=True`` 不写盘,避免污染 examples/sweep_cases/。
"""
from pathlib import Path

import pytest

from inp_tool_gui.controllers.sweep_controller import SweepController

DATA_DIR = Path(__file__).parent.parent / "examples"


# --- 初始状态 ---------------------------------------------------------


def test_initial_state_unloaded():
    """新建的 SweepController 未 load。"""
    sc = SweepController()
    assert sc.is_loaded is False
    assert sc.template is None
    assert sc.case_count == 0
    assert sc.last_report is None


# --- load -------------------------------------------------------------


def test_load_from_dict_minimal():
    """用最小 dict 构造。"""
    sc = SweepController()
    cfg = {
        "template": str(DATA_DIR / "mcfd_v2_modified.inp"),
        "output_dir": str(DATA_DIR / "sweep_cases"),
        "sweeps": {"alpha": [0.0, 4.0]},
    }
    cs = sc.load_from_dict(cfg)
    assert cs is not None
    assert sc.is_loaded is True
    assert sc.template == cfg["template"]
    assert sc.case_count == 2  # 2 alpha values


def test_load_from_json_demo():
    """用 examples/sweep_demo.json 构造。"""
    sc = SweepController()
    sc.load_from_json(str(DATA_DIR / "sweep_demo.json"))
    assert sc.is_loaded is True
    # demo 有 alpha=[0,4,8] × beta=[0] × mach=[0.6,0.8] = 6 cases
    assert sc.case_count == 6


def test_load_from_yaml_demo():
    """用 examples/sweep_demo.yaml 构造。"""
    sc = SweepController()
    sc.load_from_yaml(str(DATA_DIR / "sweep_demo.yaml"))
    assert sc.is_loaded is True
    # yaml: alpha=[0,4,8] × beta=[0] × mach=[0.6,0.8] × T=[288.15] × p=[101325] = 6
    assert sc.case_count == 6


def test_load_replaces_previous():
    """二次 load 替换前一次的状态,last_report 重置。"""
    sc = SweepController()
    sc.load_from_dict({"template": str(DATA_DIR / "mcfd_v2_modified.inp"),
                       "output_dir": str(DATA_DIR / "sweep_cases"),
                       "sweeps": {"alpha": [0.0]}})
    assert sc.case_count == 1

    sc.load_from_dict({"template": str(DATA_DIR / "mcfd_v2_modified.inp"),
                       "output_dir": str(DATA_DIR / "sweep_cases"),
                       "sweeps": {"alpha": [0.0, 1.0, 2.0]}})
    assert sc.case_count == 3


# --- preview ---------------------------------------------------------


def test_preview_returns_explicit_cases():
    """preview() 返 List[ExplicitCase] 不写盘。"""
    sc = SweepController()
    sc.load_from_json(str(DATA_DIR / "sweep_demo.json"))
    cases = sc.preview()
    assert len(cases) == 6
    for c in cases:
        assert hasattr(c, "values")
        assert isinstance(c.values, dict)
        assert "alpha" in c.values
        assert "mach" in c.values


def test_preview_unloaded_raises():
    """未 load 调 preview 应报错。"""
    sc = SweepController()
    with pytest.raises(RuntimeError):
        sc.preview()


# --- run (dry_run) ---------------------------------------------------


def test_run_dry_run_returns_report():
    """run(dry_run=True) 不写盘,返 SweepReport,total == case_count。"""
    sc = SweepController()
    sc.load_from_json(str(DATA_DIR / "sweep_demo.json"))
    rep = sc.run(dry_run=True)
    assert rep is not None
    assert rep.total == 6
    assert sc.last_report is rep


def test_run_dry_run_no_files_written(tmp_path, monkeypatch):
    """dry_run 不写任何文件,即使 chdir 到 tmp。"""
    import os
    monkeypatch.chdir(tmp_path)
    sc = SweepController()
    sc.load_from_dict({
        "template": str(DATA_DIR / "mcfd_v2_modified.inp"),
        "output_dir": str(tmp_path / "out"),
        "sweeps": {"alpha": [0.0, 4.0]},
    })
    sc.run(dry_run=True)
    # tmp_path 应该是空的
    assert list(tmp_path.iterdir()) == []


def test_run_unloaded_raises():
    """未 load 调 run 应报错。"""
    sc = SweepController()
    with pytest.raises(RuntimeError):
        sc.run(dry_run=True)


def test_report_dict_after_run():
    """run 后 report_dict() 包含 cases 列表。"""
    sc = SweepController()
    sc.load_from_json(str(DATA_DIR / "sweep_demo.json"))
    sc.run(dry_run=True)
    d = sc.report_dict()
    assert d is not None
    assert d["total"] == 6
    assert len(d["cases"]) == 6
    first = d["cases"][0]
    assert "case_id" in first
    assert "path" in first
    assert "params" in first
    assert "applied" in first
