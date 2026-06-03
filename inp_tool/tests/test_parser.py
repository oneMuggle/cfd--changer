"""inp_tool.parser 单元测试。"""
import pytest

from inp_tool import parse, parse_file
from inp_tool.model import Block, InpFile, Stmt, Value, infer_type


# ========== infer_type ==========
def test_infer_type_int():
    assert infer_type("1") == 1
    assert infer_type("0") == 0
    assert infer_type("-1") == -1


def test_infer_type_float():
    assert infer_type("1.0") == 1.0
    assert infer_type("-1.5") == -1.5


def test_infer_type_scientific():
    assert infer_type("1.5e-5") == 1.5e-5
    # Fortran 风格
    assert infer_type("1.0d-5") == 1.0e-5
    assert infer_type("1.0D-5") == 1.0e-5
    assert infer_type("1.0d+5") == 1.0e5


def test_infer_type_str():
    assert infer_type("hello") == "hello"
    assert infer_type("") == ""


# ========== parse() 基础 ==========
def test_parse_empty():
    inp = parse("")
    assert isinstance(inp, InpFile)
    assert inp.block_list == []
    assert inp.top_stmts == []


def test_parse_simple_block():
    text = """system begin
mc_filecopy a.bin b.bin
system end
"""
    inp = parse(text)
    assert inp.get_block("system") is not None
    assert inp.get("system", "mc_filecopy") is not None


def test_parse_top_statements():
    text = """infsets 3
verbose on
"""
    inp = parse(text)
    assert len(inp.top_stmts) == 2
    assert inp.top_stmts[0].keyword == "infsets"
    assert inp.top_stmts[0].values[0].typed == 3
    assert inp.top_stmts[1].keyword == "verbose"
    assert inp.top_stmts[1].values[0].typed == "on"


def test_parse_block_with_values():
    text = """tsteps begin
ntstep 200000
cflbot 0.001
tsteps end
"""
    inp = parse(text)
    assert inp.get("tsteps", "ntstep") == 200000
    assert inp.get("tsteps", "cflbot") == 0.001


def test_parse_header_comments():
    text = """# Header comment 1
# Header comment 2

tsteps begin
ntstep 100
tsteps end
"""
    inp = parse(text)
    assert len(inp.header_comments) >= 2
    assert any("Header" in c for c in inp.header_comments)


# ========== 多行 values 复合 Stmt ==========
def test_multiline_values_composite():
    """seq.# 主行 + values 子行合并为 children。"""
    text = """infsets 3
seq.# 1 #vals 4 title test1
values 1 2 3 4
seq.# 2 #vals 2 title test2
values 100 200
seq.# 3 #vals 3 title test3
values 10 20 30
"""
    inp = parse(text)
    seq_stmts = [s for s in inp.top_stmts if s.keyword.startswith("seq")]
    assert len(seq_stmts) == 3
    # 每个 seq 挂载一个 values child
    assert len(seq_stmts[0].children) == 1
    assert seq_stmts[0].children[0].keyword == "values"
    assert seq_stmts[0].children[0].values_typed == [1, 2, 3, 4]
    assert seq_stmts[1].children[0].values_typed == [100, 200]


# ========== 重复同名块 ==========
def test_duplicate_blocks_preserved():
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
    inp = parse(text)
    sys_blocks = inp.all_blocks("system")
    assert len(sys_blocks) == 2
    assert len(inp.block_list) == 3


# ========== 行尾注释 ==========
def test_comment_after_preserved():
    text = """tsteps begin
ntstep 200000  # 默认值
cflbot 0.001   # 时间步收敛阈值
tsteps end
"""
    inp = parse(text)
    cfl_stmt = inp.get_block("tsteps").get_stmt("cflbot")
    assert cfl_stmt is not None
    assert "#" in cfl_stmt.comment_after


# ========== 字符串值带空格(防御性测试) ==========
def test_string_values_no_quote_splits():
    """无引号时按空白拆分(已记录的 v0.2 行为)。"""
    text = """tsteps begin
comment this is a test
tsteps end
"""
    inp = parse(text)
    stmt = inp.get_block("tsteps").get_stmt("comment")
    assert stmt.values_typed == ["this", "is", "a", "test"]


# ========== 真实样本 ==========
def test_parse_sample_inp(sample_inp):
    """examples/ 下的样本可正常解析。"""
    inp = parse_file(str(sample_inp))
    assert isinstance(inp, InpFile)
    assert len(inp.block_list) > 0


@pytest.mark.external
def test_multiline_values_real(external_inp_dir):
    """真实 mcfd.inp 包含 ≥13 个 seq.# 多行 values。"""
    inp = parse_file(str(external_inp_dir / "mcfd (2).inp"))
    seq_stmts = [s for s in inp.top_stmts if s.keyword.startswith("seq")]
    assert len(seq_stmts) >= 13
    assert len(seq_stmts[0].children) > 0


@pytest.mark.external
def test_duplicate_blocks_real(external_inp_dir):
    inp = parse_file(str(external_inp_dir / "mcfd.inp"))
    sys_blocks = inp.all_blocks("system")
    assert len(sys_blocks) >= 1


@pytest.mark.external
def test_all_files_parse(external_inp_dir):
    """54 个真实样本全部能解析。"""
    inps = sorted(external_inp_dir.glob("*.inp"))
    failed = []
    for p in inps:
        try:
            inp = parse_file(str(p))
            assert isinstance(inp.block_list, list)
            assert isinstance(inp.top_stmts, list)
        except Exception as e:
            failed.append((p.name, str(e)))
    assert not failed, f"{len(failed)} files failed: {failed[:3]}"
