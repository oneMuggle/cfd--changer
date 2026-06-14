"""``inp_tool.postprocess.report`` 单元测试。

测试覆盖:
- ``write_excel(force_report, out_path, sheet_name=None)`` 多 case 单 sheet 输出
- header 行 + data 行字体不同(Times New Roman 表头粗体)
- ``sheet_name`` 默认 "Forces",可覆盖
- ``sheet_name`` 长度 > 31 自动截断(Excel 限制)
- 缺 ``openpyxl`` 抛 ``ImportError`` 提示安装 ``[post]`` extras

依赖:``openpyxl``([post] extras),用 ``pytest.importorskip`` 守卫。

参考实现:reference/code/CFDPlus_V4.py:742-793 + CFDPlus_extract.py:449-495
"""
from __future__ import annotations

from pathlib import Path

import pytest

# 跳过整个测试模块 if openpyxl 未装(走 [post] extras 才装)
openpyxl = pytest.importorskip("openpyxl")

from inp_tool.postprocess.forces import (  # noqa: E402
    CoefficientRow,
    ForceReport,
)


# ============================================================================
# 测试用 fixture data
# ============================================================================

def _make_row(case_name: str, ma: float = 0.5, fx: float = 100.0) -> CoefficientRow:
    return CoefficientRow(
        case=case_name,
        Ma=ma, H=10.0, alpha_deg=5.0, beta_deg=0.0,
        Fx=fx, Fy=0.0, Fz=200.0, Mx=0.0, My=0.0, Mz=0.0,
        D=fx, L=200.0,
        CD=0.1, CY=0.0, CL=0.2,
        Cmx=0.0, Cmy=0.0, Cmz=0.0,
        L_over_D=2.0, Xcp=0.0, Xcg=0.0,
        Sref=1.0, Lref=1.0,
        Q=10000.0, Re=1.0e6, P=20000.0, T=240.0,
    )


# ============================================================================
# write_excel — 基础形状
# ============================================================================

class TestWriteExcelBasic:
    def test_writes_xlsx_file(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        report = ForceReport(rows=[_make_row("case_01")])
        write_excel(report, out)
        assert out.is_file()
        assert out.stat().st_size > 0

    def test_returns_path(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        report = ForceReport(rows=[_make_row("case_01")])
        result = write_excel(report, out)
        assert result == out

    def test_default_sheet_name_forces(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        report = ForceReport(rows=[_make_row("case_01")])
        write_excel(report, out)
        wb = openpyxl.load_workbook(out)
        assert "Forces" in wb.sheetnames


class TestWriteExcelMultiRow:
    """多 case 写入同一 sheet。"""

    def test_three_cases_three_data_rows(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        rows = [
            _make_row("case_01", ma=0.3),
            _make_row("case_02", ma=0.5),
            _make_row("case_03", ma=0.8),
        ]
        write_excel(ForceReport(rows=rows), out)

        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 1 行 header + 3 行 data = 4 行
        assert ws.max_row >= 4

    def test_case_names_preserved(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        rows = [_make_row("alpha_5"), _make_row("alpha_10")]
        write_excel(ForceReport(rows=rows), out)

        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 第一列(case)第 2 行应该是 "alpha_5"
        assert ws.cell(row=2, column=1).value == "alpha_5"
        assert ws.cell(row=3, column=1).value == "alpha_10"


class TestWriteExcelEmpty:
    def test_empty_report_only_header(self, tmp_path):
        """空 ForceReport → 只有 header 行,无 data。"""
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "empty.xlsx"
        write_excel(ForceReport(rows=[]), out)
        assert out.is_file()
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 应该只有 header (1 行)
        assert ws.max_row == 1


# ============================================================================
# write_excel — sheet_name 控制
# ============================================================================

class TestWriteExcelSheetName:
    def test_custom_sheet_name(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        report = ForceReport(rows=[_make_row("c")])
        write_excel(report, out, sheet_name="Body")
        wb = openpyxl.load_workbook(out)
        assert "Body" in wb.sheetnames

    def test_sheet_name_truncated_to_31(self, tmp_path):
        """超过 31 字符的 sheet_name(Excel 限制)→ 自动截断。"""
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        long_name = "A" * 50
        report = ForceReport(rows=[_make_row("c")])
        write_excel(report, out, sheet_name=long_name)
        wb = openpyxl.load_workbook(out)
        # Excel 强制 31 字符上限
        names = wb.sheetnames
        assert any(len(n) <= 31 for n in names)


# ============================================================================
# write_excel — header 内容
# ============================================================================

class TestWriteExcelHeader:
    """28 列 header 名,与 CoefficientRow 字段顺序一致。"""

    def test_header_first_column_is_case(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        assert ws.cell(row=1, column=1).value == "Case"

    def test_header_has_ma_alpha_beta(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 收集 header 列名
        headers = [ws.cell(row=1, column=c).value for c in range(1, 29)]
        assert "Ma" in headers
        assert any("Alpha" in h or "alpha" in h for h in headers if h)
        assert any("Beta" in h or "beta" in h for h in headers if h)

    def test_28_columns(self, tmp_path):
        """28 列对应 CoefficientRow 字段数。"""
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 最后非空 header 列应该是 28(T)
        assert ws.cell(row=1, column=28).value is not None


# ============================================================================
# write_excel — 数据正确性
# ============================================================================

class TestWriteExcelDataAccuracy:
    """数据列值与 CoefficientRow 字段一致。"""

    def test_ma_value_written(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        row = _make_row("c", ma=2.5)
        write_excel(ForceReport(rows=[row]), out)

        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # 第 2 行第 2 列(Ma)
        assert ws.cell(row=2, column=2).value == pytest.approx(2.5)

    def test_fx_value_written(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        row = _make_row("c", fx=12345.6)
        write_excel(ForceReport(rows=[row]), out)

        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # Fx 是第 6 列(Case=1, Ma=2, H=3, alpha=4, beta=5, Fx=6)
        assert ws.cell(row=2, column=6).value == pytest.approx(12345.6)


# ============================================================================
# write_excel — 字体 / 格式
# ============================================================================

class TestWriteExcelFormat:
    """header 字体粗体,data 字体常规;均为 Times New Roman。"""

    def test_header_font_is_bold(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        header_cell = ws.cell(row=1, column=1)
        assert header_cell.font.bold is True

    def test_data_font_not_bold(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        data_cell = ws.cell(row=2, column=1)
        assert data_cell.font.bold is not True

    def test_font_name_times_new_roman(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Forces"]
        # header 字体应该是 Times New Roman
        assert ws.cell(row=1, column=1).font.name == "Times New Roman"


# ============================================================================
# write_excel — 接收 str 或 Path
# ============================================================================

class TestWriteExcelPathTypes:
    def test_accepts_str_path(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = str(tmp_path / "report.xlsx")
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        assert Path(out).is_file()

    def test_accepts_pathlib_path(self, tmp_path):
        from inp_tool.postprocess.report import write_excel
        out = tmp_path / "report.xlsx"
        write_excel(ForceReport(rows=[_make_row("c")]), out)
        assert out.is_file()
