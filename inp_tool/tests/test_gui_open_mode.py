# tests/test_gui_open_mode.py
"""FileController 算例目录测试。

OpenModeDialog 相关的 widget 测试在 v0.16.1 移除(主窗口拆菜单为
"打开文件 / 打开文件夹" 两项后,不再弹选择模式对话框,直接走对应入口)。
OpenModeDialog widget 本身保留(供可能外部引用),但本测试不再覆盖。
"""
import pytest
from PySide2.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_file_controller_open_case_dir(qapp, tmp_path):
    from inp_tool_gui.controllers.file_controller import FileController
    inp = tmp_path / "mcfd.inp"
    inp.write_text("reftem 300.0\n")
    fc = FileController()
    fc.open_case_dir(tmp_path)
    assert fc.is_open
    assert fc.current_case_dir == tmp_path
    assert fc.case_validation is not None
    assert fc.case_validation.ok is True


def test_file_controller_case_dir_missing_inp(qapp, tmp_path):
    from inp_tool_gui.controllers.file_controller import (
        FileController, CaseValidationError,
    )
    fc = FileController()
    with pytest.raises(CaseValidationError) as exc:
        fc.open_case_dir(tmp_path)
    assert "mcfd.inp" in str(exc.value)


def test_file_controller_case_dir_warning_geometry(qapp, tmp_path):
    from inp_tool_gui.controllers.file_controller import FileController
    inp = tmp_path / "mcfd.inp"
    inp.write_text("reftem 300.0\n")
    fc = FileController()
    fc.open_case_dir(tmp_path)
    warn_codes = [i.code for i in fc.case_validation.issues
                  if i.severity == "warning"]
    assert "missing_geometry" in warn_codes
