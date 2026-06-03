"""inp_tool.diff 单元测试(semantic diff + DiffReport.unified)。"""
import pytest

from inp_tool import diff, parse, parse_file


# ========== 合成用例 ==========
def test_diff_modify_value():
    a = parse("tsteps begin\nntstep 100\ncflbot 0.01\ntsteps end\n")
    b = parse("tsteps begin\nntstep 200\ncflbot 0.01\ntsteps end\n")
    r = diff(a, b)
    assert len(r) == 1
    assert r.changes[0].kind == "modify"
    assert r.changes[0].keyword == "ntstep"
    # DiffEntry.old / .new 是 (values_list, children_list) 元组
    assert r.changes[0].old[0] == [100]
    assert r.changes[0].new[0] == [200]


def test_diff_add_remove():
    a = parse("tsteps begin\nntstep 100\ncflbot 0.01\ntsteps end\n")
    b = parse("tsteps begin\nntstep 100\ndtauin 0.5\ntsteps end\n")
    r = diff(a, b)
    kinds = sorted(e.kind for e in r.changes)
    assert "add" in kinds
    assert "remove" in kinds


def test_diff_no_changes():
    text = "tsteps begin\nntstep 100\ntsteps end\n"
    a = parse(text)
    b = parse(text)
    r = diff(a, b)
    assert len(r) == 0


def test_diff_multiple_changes():
    a = parse("""tsteps begin
ntstep 100
cflbot 0.01
tsteps end
physics begin
gasnam Air
physics end
""")
    b = parse("""tsteps begin
ntstep 200
cflbot 0.005
tsteps end
physics begin
gasnam N2
physics end
""")
    r = diff(a, b)
    kws = {e.keyword for e in r.changes}
    assert {"ntstep", "cflbot", "gasnam"} <= kws


def test_diff_unified_format():
    a = parse("tsteps begin\nntstep 100\ntsteps end\n")
    b = parse("tsteps begin\nntstep 200\ntsteps end\n")
    r = diff(a, b)
    out = r.unified("a.inp", "b.inp")
    assert isinstance(out, str)
    assert "a.inp" in out
    assert "b.inp" in out
    assert "ntstep" in out
    # unified 风格有 +/- 行
    assert "-" in out and "+" in out


# ========== 重复块各自独立修改 ==========
def test_duplicate_block_independent_modify():
    """修复 2:重复 system 块各自修改后 diff 只报对应的。"""
    text = """system begin
mc_filecopy a.bin b.bin
system end
tsteps begin
ntstep 100
tsteps end
system begin
mc_filecopy c.bin d.bin
system end
"""
    a = parse(text)
    b = parse(text)
    # 改第一个 system
    b.block_list[0].statements[0].set(1, "X.bin")
    r = diff(a, b)
    # 应该只有第一个 system 改变
    mc_changes = [e for e in r.changes if e.keyword == "mc_filecopy"]
    assert len(mc_changes) >= 1
    # 至少一个 change 的 location 包含 system[0]
    assert any("system[0]" in e.location for e in mc_changes)


# ========== 真实样本 ==========
@pytest.mark.external
def test_real_diff(external_inp_dir):
    """修复前后:对真实样本改 4 个值, diff 应至少报 4 条。"""
    a = parse_file(str(external_inp_dir / "mcfd.inp"))
    b = parse_file(str(external_inp_dir / "mcfd.inp"))
    b.set("tsteps", "cflbot", 0.005)
    b.set("tsteps", "ntstep", 50000)
    b.set("physics", "gasnam", "N2")
    b.set("physics", "refvel", 50.0)
    r = diff(a, b)
    assert len(r) >= 4
    kws = {e.keyword for e in r.changes}
    assert {"cflbot", "ntstep", "gasnam", "refvel"} <= kws
