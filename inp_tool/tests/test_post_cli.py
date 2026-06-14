"""``inp-tool post`` CLI 子命令集成测试。

测试覆盖:
- ``inp-tool post --help`` 列出 5 个子命令
- ``post extract <case_dir>`` 基础调用
- ``post convergence <case_dir>`` 生成 convergence_report.txt
- ``post report <case_dir>`` 写 xlsx(需 [post])
- ``post plot <case_dir>`` 写 png(需 [post])
- ``post all <case_dir>`` 一站式
- 缺参 → 退出码 2 + usage
- 不存在的 case_dir → 友好错误

测试方式:走 ``inp_tool.cli.main(argv)`` 直接调用,避免 subprocess 启动开销。
"""
from __future__ import annotations

from pathlib import Path

import pytest


# ============================================================================
# Fixture:复制 reference case 到 tmp,避免污染 git-tracked fixture
# ============================================================================

FIXTURE_CASE = (
    Path(__file__).resolve().parent
    / "fixtures" / "reference" / "case"
)


@pytest.fixture
def case_dir(tmp_path):
    """复制 fixture case 到 tmp_path,提供独立可写工作目录。"""
    import shutil
    dst = tmp_path / "case"
    dst.mkdir()
    for name in ("mcfd.inp", "mcfd.info1", "mcfd.bc"):
        shutil.copy(FIXTURE_CASE / name, dst / name)
    return dst


# ============================================================================
# inp-tool post --help
# ============================================================================

class TestPostHelp:
    def test_post_help_lists_subcommands(self, capsys):
        from inp_tool.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["post", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "extract" in out
        assert "convergence" in out
        assert "report" in out
        assert "plot" in out
        assert "all" in out

    def test_post_no_subcommand_exits_2(self, capsys):
        """``inp-tool post`` 无子命令 → argparse 退出码 2。"""
        from inp_tool.cli import main
        with pytest.raises(SystemExit) as exc:
            main(["post"])
        assert exc.value.code == 2


# ============================================================================
# post extract
# ============================================================================

class TestPostExtract:
    def test_extract_basic(self, case_dir, capsys):
        from inp_tool.cli import main
        rc = main(["post", "extract", str(case_dir), "--op", "1"])
        assert rc == 0
        out = capsys.readouterr().out
        # 输出应该包含 case 名或 Fx 或 Ma
        assert ("case" in out.lower()) or ("fx" in out.lower()) or ("ma" in out.lower())

    def test_extract_with_geometry(self, case_dir):
        from inp_tool.cli import main
        rc = main([
            "post", "extract", str(case_dir),
            "--op", "1", "--sref", "2.0", "--lref", "1.5",
        ])
        assert rc == 0

    def test_extract_with_ref_center(self, case_dir):
        from inp_tool.cli import main
        rc = main([
            "post", "extract", str(case_dir),
            "--op", "1",
            "--sref", "1.0", "--lref", "1.0",
            "--xref", "0.5", "--yref", "0.0", "--zref", "0.0",
        ])
        assert rc == 0

    def test_extract_multi_op(self, case_dir):
        from inp_tool.cli import main
        rc = main([
            "post", "extract", str(case_dir), "--op", "1,2",
        ])
        assert rc == 0

    def test_extract_missing_case_dir(self, tmp_path, capsys):
        """不存在的 case_dir → 退出码非 0,有清晰错误。"""
        from inp_tool.cli import main
        nonexistent = tmp_path / "no_such_case"
        rc = main(["post", "extract", str(nonexistent), "--op", "1"])
        assert rc != 0


# ============================================================================
# post convergence
# ============================================================================

class TestPostConvergence:
    def test_convergence_basic_writes_report(self, case_dir, tmp_path):
        from inp_tool.cli import main
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        rc = main([
            "post", "convergence", str(case_dir),
            "--op", "1",
            "--out", str(out_dir),
            "--min-window", "1",  # fixture 只 2 步,放宽 min_window 才能算
        ])
        assert rc == 0
        # 应生成 convergence_report.txt
        report = out_dir / "convergence_report.txt"
        assert report.is_file()

    def test_convergence_report_has_case_name(self, case_dir, tmp_path):
        from inp_tool.cli import main
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        rc = main([
            "post", "convergence", str(case_dir),
            "--op", "1",
            "--out", str(out_dir),
            "--min-window", "1",
        ])
        assert rc == 0
        report = (out_dir / "convergence_report.txt").read_text(encoding="utf-8")
        assert case_dir.name in report or "case" in report.lower()

    def test_convergence_data_insufficient_does_not_crash(self, case_dir, tmp_path):
        """fixture 只 2 步,默认 min_window=100 → 数据不足,不应崩溃。"""
        from inp_tool.cli import main
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        rc = main([
            "post", "convergence", str(case_dir),
            "--op", "1",
            "--out", str(out_dir),
        ])
        # 应能跑完(报告会说"数据不足")
        assert rc == 0


# ============================================================================
# post report ([post] extras)
# ============================================================================

class TestPostReport:
    def test_report_writes_xlsx(self, case_dir, tmp_path):
        """需要 openpyxl;若未装跳过。"""
        pytest.importorskip("openpyxl")
        from inp_tool.cli import main
        out = tmp_path / "Force.xlsx"
        rc = main([
            "post", "report", str(case_dir),
            "--op", "1",
            "--out", str(out),
        ])
        assert rc == 0
        assert out.is_file()
        assert out.stat().st_size > 0


# ============================================================================
# post plot ([post] extras)
# ============================================================================

class TestPostPlot:
    def test_plot_writes_png(self, case_dir, tmp_path):
        """需要 matplotlib;若未装跳过。"""
        pytest.importorskip("matplotlib")
        from inp_tool.cli import main
        out = tmp_path / "conv.png"
        rc = main([
            "post", "plot", str(case_dir),
            "--op", "1",
            "--out", str(out),
            "--min-window", "1",
        ])
        assert rc == 0
        assert out.is_file()


# ============================================================================
# post all
# ============================================================================

class TestPostAll:
    def test_all_runs_full_pipeline(self, case_dir, tmp_path):
        """``post all`` 顺序跑 extract + convergence + (report+plot if [post])。"""
        pytest.importorskip("openpyxl")
        pytest.importorskip("matplotlib")
        from inp_tool.cli import main
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        rc = main([
            "post", "all", str(case_dir),
            "--op", "1",
            "--sref", "1.0", "--lref", "1.0",
            "--out-dir", str(out_dir),
            "--min-window", "1",
        ])
        assert rc == 0
        # 应生成各种输出
        assert (out_dir / "convergence_report.txt").is_file()
        assert (out_dir / "ForceReport.xlsx").is_file()
        assert (out_dir / "convergence_plot.png").is_file()


# ============================================================================
# 多 case 批量
# ============================================================================

class TestPostBatchCases:
    """传多个 case_dir 应该都处理。"""

    def test_extract_two_cases(self, case_dir, tmp_path):
        from inp_tool.cli import main
        # 复制成第二个 case
        import shutil
        case2 = tmp_path / "case_02"
        shutil.copytree(case_dir, case2)
        rc = main([
            "post", "extract",
            str(case_dir), str(case2),
            "--op", "1",
        ])
        assert rc == 0
