"""DiffController + DiffViewer + SweepForm 单元测试(Phase 5)。

不在真实显示器上运行 — 用 ``QT_QPA_PLATFORM=offscreen`` 强制 headless。
"""
import os
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from inp_tool_gui.controllers.diff_controller import DiffController
from inp_tool_gui.controllers.sweep_controller import SweepController


# --- fixture -------------------------------------------------------------


@pytest.fixture(scope="session")
def qapp():
    from PySide2.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def two_inp_files(tmp_path):
    """写两个 .inp(A,B)到 tmp,返回 (path_a, path_b)。"""
    inp_a = textwrap.dedent(
        """\
        title Hello
        begin physics
          reftem 300.0
          reynolds 1.0e6
        end physics
        """
    )
    inp_b = textwrap.dedent(
        """\
        title Hello
        begin physics
          reftem 350.0
          reynolds 1.0e6
        end physics
        """
    )
    pa = tmp_path / "a.inp"
    pb = tmp_path / "b.inp"
    pa.write_text(inp_a, encoding="utf-8")
    pb.write_text(inp_b, encoding="utf-8")
    return str(pa), str(pb)


# --- DiffController ------------------------------------------------------


def test_diff_controller_load_pair(two_inp_files):
    """load_pair 后 change_count > 0(reftem 改了)。"""
    a, b = two_inp_files
    dc = DiffController()
    rep = dc.load_pair(a, b)
    assert dc.has_pair is True
    assert dc.change_count > 0
    assert any("reftem" in str(e) for e in rep.changes)


def test_diff_controller_unified_text(two_inp_files):
    """unified_text 含 +/- 标记。"""
    a, b = two_inp_files
    dc = DiffController()
    dc.load_pair(a, b)
    text = dc.unified_text()
    assert "--- " in text
    assert "+++ " in text
    assert "- " in text
    assert "+ " in text


def test_diff_controller_no_changes(tmp_path):
    """两个完全相同文件 → change_count = 0。"""
    inp = textwrap.dedent(
        """\
        title Hello
        begin physics
          reftem 300.0
        end physics
        """
    )
    pa = tmp_path / "a.inp"
    pb = tmp_path / "b.inp"
    pa.write_text(inp, encoding="utf-8")
    pb.write_text(inp, encoding="utf-8")
    dc = DiffController()
    dc.load_pair(str(pa), str(pb))
    assert dc.change_count == 0


def test_diff_controller_no_load_returns_zero():
    """未 load_pair → change_count=0,unified 返 '(未加载)'。"""
    dc = DiffController()
    assert dc.change_count == 0
    assert dc.unified_text() == "(未加载)"


# --- DiffViewer ----------------------------------------------------------


def test_diff_viewer_load_paths_displays_changes(qapp, two_inp_files):
    """load_paths 后 _lbl_changes 含数字,_view HTML 含 +/- 颜色标记。"""
    a, b = two_inp_files
    dc = DiffController()
    from inp_tool_gui.widgets.diff_viewer import DiffViewer

    viewer = DiffViewer(dc)
    try:
        viewer.load_paths(a, b)
        n = dc.change_count
        assert f"{n}" in viewer._lbl_changes.text()
        html = viewer._view.toHtml()
        # Qt 把 #c00 → #cc0000, #0a0 → #00aa00(扩展为完整 hex)
        assert "#cc0000" in html or "#c00" in html
        assert "#00aa00" in html or "#0a0" in html
    finally:
        viewer.deleteLater()


# --- SweepForm -----------------------------------------------------------


@pytest.fixture
def sweep_yaml_path(tmp_path, sample_inp):
    """写一个 sweep.yaml 引用 sample_inp,返回 yaml 路径。"""
    p = tmp_path / "sweep.yaml"
    p.write_text(
        "# minimal yaml\n"
        f"template: {sample_inp}\n"
        f"output_dir: {tmp_path / 'out'}\n"
        "sweeps:\n"
        "  alpha: [0.0, 2.0, 4.0]\n"
        "naming: alpha{alpha}\n"
        "freestream:\n"
        "  enabled: false\n",
        encoding="utf-8",
    )
    return str(p)


def test_sweep_form_load_yaml_populates_config(qapp, sweep_yaml_path):
    """load_yaml 后 case_count=3,_lbl_tpl 含 sample 路径。"""
    sc = SweepController()
    from inp_tool_gui.widgets.sweep_form import SweepForm

    form = SweepForm(sc)
    try:
        form.load_yaml(sweep_yaml_path)
        assert sc.is_loaded is True
        assert sc.case_count == 3
        assert form._lbl_cases.text() == "3"
    finally:
        form.deleteLater()


def test_sweep_form_run_dry_fills_table(qapp, sweep_yaml_path):
    """load + run(dry=True) 后 _table 有 3 行。"""
    sc = SweepController()
    from inp_tool_gui.widgets.sweep_form import SweepForm

    form = SweepForm(sc)
    try:
        form.load_yaml(sweep_yaml_path)
        form.run_sync(dry=True)
        assert sc.last_report is not None
        assert len(sc.last_report.cases) == 3
        assert form._table.rowCount() == 3
        assert "alpha" in form._table.item(0, 0).text()
    finally:
        form.deleteLater()