"""inp_tool.writer 单元测试(round-trip + to_text + write_bytes)。"""
import os
import tempfile
from pathlib import Path

import pytest

from inp_tool import parse, parse_file, write, write_bytes
from inp_tool.writer import to_text


# ========== to_text() 基础 ==========
def test_to_text_empty():
    inp = parse("")
    assert to_text(inp) == ""


def test_to_text_roundtrip_simple():
    text = """tsteps begin
ntstep 100
cflbot 0.01
tsteps end
"""
    s = to_text(parse(text))
    assert "tsteps begin" in s
    assert "ntstep 100" in s
    assert "cflbot 0.01" in s
    assert "tsteps end" in s


def test_to_text_preserves_comments():
    text = """tsteps begin
ntstep 200000  # 默认值
cflbot 0.001   # 时间步
tsteps end
"""
    s = to_text(parse(text))
    assert "# 默认值" in s
    assert "# 时间步" in s


def test_to_text_preserves_children():
    text = """infsets 3
seq.# 1 #vals 2 title test
values 1 2
"""
    s = to_text(parse(text))
    assert "values 1 2" in s


# ========== write() ==========
def test_write_creates_file(tmp_path: Path):
    """write() 写出 UTF-8 文件,可被 parse_file() 读回。"""
    inp = parse("tsteps begin\nntstep 500\ntsteps end\n")
    out = tmp_path / "case.inp"
    write(inp, str(out))
    assert out.exists()
    assert out.read_text(encoding="utf-8").strip().startswith("tsteps begin")
    # 读回,值应一致
    inp2 = parse_file(str(out))
    assert inp2.get("tsteps", "ntstep") == 500


def test_write_modify_then_roundtrip(tmp_path: Path):
    """set() → write() → parse() 后值已更新,块结构保留。"""
    text = """tsteps begin
ntstep 100
cflbot 0.01
tsteps end
physics begin
gasnam Air
refvel 10.0
physics end
"""
    inp = parse(text)
    inp.set("tsteps", "cflbot", 0.005)
    inp.set("physics", "gasnam", "N2")
    out = tmp_path / "case_modified.inp"
    write(inp, str(out))

    inp2 = parse_file(str(out))
    assert inp2.get("tsteps", "cflbot") == 0.005
    assert inp2.get("physics", "gasnam") == "N2"
    # 唯一块名集合一致
    names1 = {b.name for b in inp.block_list}
    names2 = {b.name for b in inp2.block_list}
    assert names1 == names2


# ========== write_bytes() ==========
def test_write_bytes_matches_write(tmp_path: Path):
    """write_bytes(inp, path) 落盘的 bytes 与 write() 一致。"""
    inp = parse("tsteps begin\nntstep 200\ntsteps end\n")
    out_write = tmp_path / "write.inp"
    out_bytes = tmp_path / "bytes.inp"
    write(inp, str(out_write))
    write_bytes(inp, str(out_bytes))  # noqa: F841 - 验证不抛异常
    # 两个文件内容应一致
    assert out_write.read_bytes() == out_bytes.read_bytes()


# ========== 真实样本 round-trip ==========
def test_roundtrip_sample_inp(tmp_path: Path, sample_inp: Path):
    """examples/ 样本 → 修改 → write → parse,值与 children 保留。"""
    inp = parse_file(str(sample_inp))
    inp.set("tsteps", "cflbot", 0.123)
    out = tmp_path / "rt.inp"
    write(inp, str(out))

    inp2 = parse_file(str(out))
    assert inp2.get("tsteps", "cflbot") == 0.123
    # children (seq.# values) 应保留
    seq1 = [s for s in inp.top_stmts if s.keyword.startswith("seq")]
    seq2 = [s for s in inp2.top_stmts if s.keyword.startswith("seq")]
    if seq1 and seq1[0].children:
        assert len(seq2[0].children) == len(seq1[0].children)
