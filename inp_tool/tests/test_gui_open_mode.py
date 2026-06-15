# tests/test_gui_open_mode.py
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


def test_open_mode_dialog_default_folder(qapp):
    from inp_tool_gui.widgets.open_mode_dialog import OpenModeDialog, Mode
    dlg = OpenModeDialog()
    assert dlg.selected_mode() == Mode.FOLDER


def test_open_mode_dialog_user_picks_file(qapp):
    from inp_tool_gui.widgets.open_mode_dialog import OpenModeDialog, Mode
    dlg = OpenModeDialog()
    dlg._radio_file.setChecked(True)
    assert dlg.selected_mode() == Mode.FILE
