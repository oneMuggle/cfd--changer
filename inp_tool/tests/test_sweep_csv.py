"""
PR #1 阶段 5:CSV loader

测试目标:
- CaseSweep.from_csv 解析 CSV
- 数值类型推断(空值 / 非数字 → 清晰错误)
- 错误信息含行号 + 列名
- 表头强制(无表头 CSV 不支持,本次)
- 编码处理(UTF-8 优先,GBK fallback)
"""
from __future__ import annotations
import os
import pytest

from inp_tool.sweep import (
    CaseSweep, ExplicitCase, generate,
)


# ======================================================================
# CSV loader 基础
# ======================================================================
class TestCsvLoaderBasic:
    def test_from_csv_minimal(self, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text(
            "alpha,beta,mach\n"
            "10,5,0.6\n"
            "10,8,0.6\n"
            "20,10,0.6\n"
            "20,15,0.6\n",
            encoding="utf-8",
        )
        cs = CaseSweep.from_csv(
            str(csv),
            template="t.inp",
            output_dir=str(tmp_path / "out"),
        )
        assert cs.template == "t.inp"
        assert cs.output_dir == str(tmp_path / "out")
        # 4 ExplicitCase, 无 CartesianSpec
        assert len(cs.specs) == 4
        assert all(isinstance(s, ExplicitCase) for s in cs.specs)

    def test_from_csv_with_naming_and_manifest(self, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text("alpha,beta\n0,0\n5,0\n", encoding="utf-8")
        cs = CaseSweep.from_csv(
            str(csv),
            template="t.inp",
            output_dir="out",
            naming="case_a{alpha:02.0f}.inp",
            manifest_path="out/manifest.json",
        )
        assert cs.naming == "case_a{alpha:02.0f}.inp"
        assert cs.manifest_path == "out/manifest.json"

    def test_from_csv_materialize_preserves_order(self, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text(
            "alpha,beta\n"
            "10,5\n"
            "10,8\n"
            "20,10\n",
            encoding="utf-8",
        )
        cs = CaseSweep.from_csv(
            str(csv), template="t.inp", output_dir="out",
        )
        flat = cs.materialize()
        assert [c.values for c in flat] == [
            {"alpha": 10.0, "beta": 5.0},
            {"alpha": 10.0, "beta": 8.0},
            {"alpha": 20.0, "beta": 10.0},
        ]


# ======================================================================
# CSV loader 数值推断
# ======================================================================
class TestCsvTypeInference:
    def test_integer_columns_inferred_as_float(self, tmp_path):
        """CSV 列名为 'niter' 等整数场景,也能解析(转 float)"""
        csv = tmp_path / "cases.csv"
        csv.write_text("alpha,niter\n0,1000\n5,2000\n", encoding="utf-8")
        cs = CaseSweep.from_csv(
            str(csv), template="t.inp", output_dir="out",
        )
        flat = cs.materialize()
        # 即使是整数字面量,也转 float(统一语义)
        assert flat[0].values == {"alpha": 0.0, "niter": 1000.0}

    def test_extra_columns_in_csv_kept(self, tmp_path):
        """CSV 中所有列都进 values(用户可放任何字段名)"""
        csv = tmp_path / "cases.csv"
        csv.write_text(
            "alpha,beta,custom_field\n"
            "0,0,hello\n",  # 自定义列 custom_field
            encoding="utf-8",
        )
        cs = CaseSweep.from_csv(
            str(csv), template="t.inp", output_dir="out",
        )
        flat = cs.materialize()
        assert flat[0].values["custom_field"] == "hello"


# ======================================================================
# CSV loader 错误处理
# ======================================================================
class TestCsvErrors:
    def test_empty_csv_raises(self, tmp_path):
        csv = tmp_path / "empty.csv"
        csv.write_text("", encoding="utf-8")
        with pytest.raises((ValueError, KeyError)):
            CaseSweep.from_csv(
                str(csv), template="t.inp", output_dir="out",
            )

    def test_non_numeric_value_raises_with_line_number(self, tmp_path):
        csv = tmp_path / "bad.csv"
        csv.write_text(
            "alpha,beta\n"
            "0,0\n"
            "5,foo\n"  # 第 3 行 foo 不是数字
            "10,3\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError) as exc_info:
            CaseSweep.from_csv(
                str(csv), template="t.inp", output_dir="out",
            )
        # 错误信息应含行号
        assert "row 3" in str(exc_info.value) or "line 3" in str(exc_info.value)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CaseSweep.from_csv(
                str(tmp_path / "nonexistent.csv"),
                template="t.inp", output_dir="out",
            )


# ======================================================================
# CSV loader + generate() 集成
# ======================================================================
class TestCsvGenerate:
    def test_generate_from_csv(self, sample_inp, tmp_path):
        csv = tmp_path / "cases.csv"
        csv.write_text(
            "alpha,beta,mach,T,p\n"
            "10,5,0.6,288.15,101325\n"
            "10,8,0.6,288.15,101325\n"
            "20,10,0.6,288.15,101325\n"
            "20,15,0.6,288.15,101325\n",
            encoding="utf-8",
        )
        cs = CaseSweep.from_csv(
            str(csv),
            template=str(sample_inp),
            output_dir=str(tmp_path / "out"),
            naming="case_a{alpha:02.0f}_b{beta:02.0f}.inp",
        )
        report = generate(cs)
        assert report.total == 4
        names = sorted(os.path.basename(c.path) for c in report.cases)
        assert names == [
            "case_a10_b05.inp",
            "case_a10_b08.inp",
            "case_a20_b10.inp",
            "case_a20_b15.inp",
        ]


# ======================================================================
# 编码
# ======================================================================
class TestCsvEncoding:
    def test_utf8_default(self, tmp_path):
        csv = tmp_path / "utf8.csv"
        csv.write_text("alpha\n0\n5\n", encoding="utf-8")
        cs = CaseSweep.from_csv(
            str(csv), template="t.inp", output_dir="out",
        )
        flat = cs.materialize()
        assert flat[0].values == {"alpha": 0.0}
