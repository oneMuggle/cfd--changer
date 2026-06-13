"""DetectController adapter 测试(Phase v0.13):用真实 detect_equations。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def small_inp():
    """构造含 physics block 的最小 InpFile。"""
    from inp_tool.model import Block, InpFile, Stmt, Value

    inp = InpFile()
    b = Block(name="physics", begin_line=1, end_line=10)
    b.statements = [
        Stmt(keyword="reftem", values=[Value(raw="300.0")], line=1),
        Stmt(keyword="reynolds", values=[Value(raw="1.0e6")], line=2),
        Stmt(keyword="tnoneq_numeqns", values=[Value(raw="0")], line=3),
    ]
    inp.block_list = [b]
    return inp


# --- 新 API 属性 -------------------------------------------------------


def test_run_returns_adapter_with_eq_report(qapp, small_inp):
    """run 后 last_report 是 DetectionReport,内部 wrap EquationSystemReport。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp)
    assert rep is not None
    assert hasattr(rep, "_eq")
    assert rep.turbulence_model is not None
    assert rep.energy_model is not None
    assert rep.gas_model is not None


def test_run_with_intended_axes(qapp, small_inp):
    """run(intended_axes={'turbulence': 'sst'}) 不抛,warnings 在 sweeps_equation_warnings。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp, intended_axes={"turbulence": "sst"})
    assert isinstance(rep.sweeps_equation_warnings, list)


# --- 向后兼容:旧属性 --------------------------------------------------


def test_has_chemistry_zero_for_no_chemistry_block(qapp, small_inp):
    """has_chemistry 由 chemistry 块数派生。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp)
    assert rep.has_chemistry is False
    assert rep.chemistry_blocks == 0


def test_has_chemistry_true_when_chemistry_block_present(qapp, small_inp):
    """加 1 个 chemistry block → has_chemistry=True。"""
    from inp_tool.model import Block
    from inp_tool_gui.controllers.detect_controller import DetectController

    small_inp.block_list.append(Block(name="chemistry", begin_line=20, end_line=30))
    dc = DetectController()
    rep = dc.run(small_inp)
    assert rep.has_chemistry is True
    assert rep.chemistry_blocks == 1


def test_is_two_temperature_true_for_2t(qapp):
    """physics.tnoneq_numeqns=1 → is_two_temperature=True。"""
    from inp_tool.model import Block, InpFile, Stmt, Value
    from inp_tool_gui.controllers.detect_controller import DetectController

    inp = InpFile()
    b = Block(name="physics", begin_line=1, end_line=10)
    b.statements = [
        Stmt(keyword="tnoneq_numeqns", values=[Value(raw="1")], line=1),
        Stmt(keyword="vibtem", values=[Value(raw="300")], line=2),
    ]
    inp.block_list = [b]

    dc = DetectController()
    rep = dc.run(inp)
    assert rep.is_two_temperature is True
    assert rep.energy_model.value == "2T"


# --- summary_zh + recommended_fields ------------------------------------


def test_summary_zh_contains_energy(qapp, small_inp):
    """summary_zh() 含 '能量=' 前缀(真实 EquationSystemReport.summary_zh)。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp)
    s = rep.summary_zh()
    assert "能量=" in s
    assert "湍流=" in s


def test_recommended_fields_returns_tuples(qapp, small_inp):
    """recommended_fields 仍返 List[Tuple[block, keyword, value, note]](旧 API)。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp)
    fields = rep.recommended_fields
    assert isinstance(fields, list)
    for item in fields:
        assert isinstance(item, tuple)
        assert len(item) == 4  # (block, keyword, value, note)


# --- n_species 新增 ----------------------------------------------------


def test_n_species_default_zero(qapp, small_inp):
    """无 chemistry block 时 n_species=0。"""
    from inp_tool_gui.controllers.detect_controller import DetectController

    dc = DetectController()
    rep = dc.run(small_inp)
    assert rep.n_species == 0