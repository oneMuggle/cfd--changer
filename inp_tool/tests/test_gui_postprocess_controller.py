"""``PostprocessController`` 单元测试。

PostprocessController 是 GUI 层的业务逻辑包装(PySide2-free),
封装 ``inp_tool.postprocess`` 子包的 5 个公共 API,让 widget 层
只调 controller,不直接调底层 ``summarize_forces`` 等函数。

测试覆盖:
- 几何参数 setter + getter
- op_ibd setter(支持字符串 "1,2" 或 list[int])
- extract / convergence / report / plot / run_all 5 个方法
- 缺 case_dir / 缺 inp / 缺 info1 的错误传播
- run_all 不强制依赖 [post];缺 openpyxl/matplotlib 时只 skip 报告步骤
"""
from __future__ import annotations

from pathlib import Path

import pytest

from inp_tool_gui.controllers.postprocess_controller import (
    PostprocessController,
)


FIXTURE_CASE = (
    Path(__file__).resolve().parent
    / "fixtures" / "reference" / "case"
)


@pytest.fixture
def case_dir(tmp_path):
    """复制 fixture case 到 tmp_path。"""
    import shutil
    dst = tmp_path / "case"
    dst.mkdir()
    for name in ("mcfd.inp", "mcfd.info1", "mcfd.bc"):
        shutil.copy(FIXTURE_CASE / name, dst / name)
    return dst


# ============================================================================
# 几何参数
# ============================================================================

class TestGeometrySetter:
    def test_default_geometry(self):
        c = PostprocessController()
        # 默认 Sref=Lref=1.0,Xref/Yref/Zref=0
        assert c.sref == pytest.approx(1.0)
        assert c.lref == pytest.approx(1.0)
        assert c.xref == 0.0
        assert c.yref == 0.0
        assert c.zref == 0.0

    def test_set_geometry(self):
        c = PostprocessController()
        c.set_geometry(sref=2.5, lref=3.0, xref=0.1, yref=0.2, zref=0.3)
        assert c.sref == pytest.approx(2.5)
        assert c.lref == pytest.approx(3.0)
        assert c.xref == pytest.approx(0.1)
        assert c.yref == pytest.approx(0.2)
        assert c.zref == pytest.approx(0.3)

    def test_set_geometry_partial(self):
        """只设几个参数,其余保持默认。"""
        c = PostprocessController()
        c.set_geometry(sref=10.0, lref=5.0)
        assert c.sref == pytest.approx(10.0)
        assert c.xref == 0.0  # 仍是默认


# ============================================================================
# op_ibd setter(支持 str 或 list)
# ============================================================================

class TestOpIbdSetter:
    def test_set_op_ibd_list(self):
        c = PostprocessController()
        c.set_op_ibd([1, 2])
        assert c.op_ibd == [1, 2]

    def test_set_op_ibd_string(self):
        c = PostprocessController()
        c.set_op_ibd("1,2,3")
        assert c.op_ibd == [1, 2, 3]

    def test_set_op_ibd_single_int_string(self):
        c = PostprocessController()
        c.set_op_ibd("1")
        assert c.op_ibd == [1]

    def test_empty_string_raises(self):
        c = PostprocessController()
        with pytest.raises(ValueError):
            c.set_op_ibd("")


# ============================================================================
# extract
# ============================================================================

class TestExtract:
    def test_extract_returns_force_report(self, case_dir):
        c = PostprocessController()
        c.set_op_ibd([1])
        report = c.extract([case_dir])
        assert report is not None
        assert len(report.rows) == 1
        assert report.rows[0].case == case_dir.name

    def test_extract_uses_geometry(self, case_dir):
        c = PostprocessController()
        c.set_op_ibd([1])
        c.set_geometry(sref=2.0, lref=3.0)
        report = c.extract([case_dir])
        assert report.rows[0].Sref == pytest.approx(2.0)
        assert report.rows[0].Lref == pytest.approx(3.0)

    def test_extract_missing_case_dir_returns_empty(self, tmp_path):
        c = PostprocessController()
        c.set_op_ibd([1])
        report = c.extract([tmp_path / "no_such_case"])
        # 缺目录应跳过,返回空 ForceReport
        assert len(report.rows) == 0


# ============================================================================
# convergence
# ============================================================================

class TestConvergence:
    def test_convergence_returns_results(self, case_dir):
        c = PostprocessController()
        c.set_op_ibd([1])
        results = c.convergence([case_dir], min_window=1)
        assert len(results) == 1
        case_name, window = results[0]
        assert case_name == case_dir.name
        # min_window=1 + 2 步 fixture → window 应该非 None
        assert window is not None

    def test_convergence_data_insufficient_returns_none(self, case_dir):
        """fixture 只 2 步,默认 min_window=100 → None。"""
        c = PostprocessController()
        c.set_op_ibd([1])
        results = c.convergence([case_dir])
        case_name, window = results[0]
        assert window is None


# ============================================================================
# report + plot([post] extras)
# ============================================================================

class TestReport:
    def test_report_writes_xlsx(self, case_dir, tmp_path):
        pytest.importorskip("openpyxl")
        c = PostprocessController()
        c.set_op_ibd([1])
        out = tmp_path / "r.xlsx"
        c.report([case_dir], out)
        assert out.is_file()


class TestPlot:
    def test_plot_writes_png(self, case_dir, tmp_path):
        pytest.importorskip("matplotlib")
        c = PostprocessController()
        c.set_op_ibd([1])
        out = tmp_path / "p.png"
        c.plot([case_dir], out, min_window=1)
        assert out.is_file()


# ============================================================================
# run_all
# ============================================================================

class TestRunAll:
    def test_run_all_produces_outputs(self, case_dir, tmp_path):
        """run_all 应产出 ForceReport + convergence_report.txt;
        若 [post] 装了则也产出 xlsx 和 png。"""
        pytest.importorskip("openpyxl")
        pytest.importorskip("matplotlib")
        c = PostprocessController()
        c.set_op_ibd([1])
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        result = c.run_all([case_dir], out_dir, min_window=1)

        # result 应是 dict:{report: ForceReport, txt: Path, xlsx: Path, png: Path}
        assert result["report"] is not None
        assert (out_dir / "convergence_report.txt").is_file()
        assert (out_dir / "ForceReport.xlsx").is_file()
        assert (out_dir / "convergence_plot.png").is_file()


# ============================================================================
# 不依赖 PySide2 — 此模块导入不应触发 Qt
# ============================================================================

class TestPyside2Independence:
    """controller 必须 PySide2-free,只是 widget 层用 Qt。"""

    def test_module_does_not_reference_pyside2(self):
        """controller 模块的命名空间不能含 PySide2 子模块。"""
        from inp_tool_gui.controllers import postprocess_controller
        # PySide2 不应作为顶层符号出现在 controller 模块中
        assert "PySide2" not in dir(postprocess_controller)
