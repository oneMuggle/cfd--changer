"""DetectController 单元测试(Phase 4)。"""
from inp_tool.model import Block, InpFile, Stmt, Value

from inp_tool_gui.controllers.detect_controller import DetectController


def _make_inp_with_physics(*stmts):
    """构造含 physics block 的 InpFile,stmts 是 (keyword, raw_value) 元组列表。"""
    inp = InpFile()
    b = Block(name="physics", begin_line=1, end_line=10)
    for kw, raw in stmts:
        b.statements.append(Stmt(keyword=kw, values=[Value(raw=raw)], line=1))
    inp.block_list = [b]
    return inp


def test_run_minimal_inp_returns_report():
    """空 InpFile → 报告全部 False。"""
    dc = DetectController()
    rep = dc.run(InpFile())
    assert rep.has_reftem is False
    assert rep.has_reynolds is False
    assert rep.has_turbulence is False
    assert rep.has_chemistry is False
    assert rep.is_two_temperature is False
    assert rep.turb_keywords == []
    assert rep.chemistry_blocks == 0


def test_detect_reftem_and_reynolds():
    """含 reftem + reynolds → 报告 True。"""
    inp = _make_inp_with_physics(
        ("reftem", "300.0"), ("reynolds", "1.0e6")
    )
    dc = DetectController()
    rep = dc.run(inp)
    assert rep.has_reftem is True
    assert rep.has_reynolds is True
    assert rep.summary_zh().startswith("检测到:")


def test_detect_turb_keywords():
    """含 turb/turbi/turbk → has_turbulence=True,关键字列表正确。"""
    inp = _make_inp_with_physics(
        ("reftem", "300.0"), ("reynolds", "1e6"),
        ("turbmodel", "sst"),
        ("turbi", "0.01"),
    )
    dc = DetectController()
    rep = dc.run(inp)
    assert rep.has_turbulence is True
    assert "turbmodel" in rep.turb_keywords
    assert "turbi" in rep.turb_keywords


def test_detect_chemistry_blocks():
    """2 个 chemistry block → has_chemistry=True, chemistry_blocks=2。"""
    inp = InpFile()
    inp.block_list = [
        Block(name="chemistry", begin_line=1, end_line=2),
        Block(name="chemistry", begin_line=3, end_line=4),
    ]
    dc = DetectController()
    rep = dc.run(inp)
    assert rep.has_chemistry is True
    assert rep.chemistry_blocks == 2


def test_detect_two_temperature_via_vibtem():
    """含 vibtem → is_two_temperature=True。"""
    inp = _make_inp_with_physics(("reftem", "300"), ("vibtem", "300"))
    dc = DetectController()
    rep = dc.run(inp)
    assert rep.is_two_temperature is True


def test_notes_added_when_turb_no_reynolds():
    """湍流存在但缺 reynolds → notes 含提示。"""
    inp = _make_inp_with_physics(("reftem", "300"), ("turbi", "0.01"))
    dc = DetectController()
    rep = dc.run(inp)
    assert any("reynolds" in n for n in rep.notes)


def test_recommended_fields_for_missing_physics():
    """缺 reynolds + reftem → 推荐字段含 (physics, reynolds, ...) 与 (physics, reftem, ...)。"""
    inp = _make_inp_with_physics(("turbi", "0.01"))
    dc = DetectController()
    rep = dc.run(inp)
    keys = {(b, k) for (b, k, _v, _note) in rep.recommended_fields}
    assert ("physics", "reynolds") in keys
    assert ("physics", "reftem") in keys


def test_no_recommended_fields_when_all_present():
    """reynolds + reftem 都有 → 推荐字段为空。"""
    inp = _make_inp_with_physics(
        ("reftem", "300"), ("reynolds", "1e6"), ("turbi", "0.01")
    )
    dc = DetectController()
    rep = dc.run(inp)
    assert rep.recommended_fields == []


def test_last_report_property():
    """run 后 last_report 是同一对象。"""
    inp = _make_inp_with_physics(("reftem", "300"))
    dc = DetectController()
    rep1 = dc.run(inp)
    assert dc.last_report is rep1
    rep2 = dc.run(inp)
    assert dc.last_report is rep2


def test_summary_zh_for_empty_inp():
    """空 InpFile → 摘要含 '未检测到'。"""
    dc = DetectController()
    rep = dc.run(InpFile())
    assert "未检测到" in rep.summary_zh()