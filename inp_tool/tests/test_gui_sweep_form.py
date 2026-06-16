"""SweepController.update_field + SweepForm 实时编辑(v0.16.1 整合版)。

- 单元测试:SweepController.update_field(纯 Python,不依赖 PySide2)
- widget 测试:SweepForm 的实时编辑字段 + YAML 加载自动填充
"""
from inp_tool_gui.controllers.sweep_controller import SweepController
import pytest


# --- SweepController.update_field 单元测试(无 PySide2 依赖) ---------


def test_sweep_controller_update_template():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("template", "y.inp")
    assert sc.template == "y.inp"


def test_sweep_controller_update_sweeps_axis():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("sweeps.alpha", [0, 5, 10, 15])
    assert sc.case_count == 4


def test_sweep_controller_update_naming():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    sc.update_field("naming", "run_{alpha}")
    assert sc.case_count == 3


def test_sweep_controller_update_invalid_field_raises():
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    with pytest.raises(KeyError):
        sc.update_field("nonexistent_field", "x")


def test_sweep_controller_update_before_load_raises():
    sc = SweepController()
    with pytest.raises(RuntimeError):
        sc.update_field("template", "x.inp")


# --- SweepForm widget 测试(需要 QApplication) ------------------------


@pytest.fixture(scope="module")
def qapp():
    """整个测试模块共享一个 QApplication。"""
    from PySide2.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_sweep_form_has_template_editor(qapp):
    """SweepForm 构造后,_edit_tpl 已从 controller 拉取到模板路径。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    form = SweepForm(sc)
    assert form._edit_tpl.text() == "x.inp"


def test_sweep_form_has_three_top_labels(qapp):
    """顶部 3 行各有 QLabel 显示中文模板路径/输出目录/命名模式。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool.i18n_gui import tg

    sc = SweepController()
    sc.load_from_dict({
        "template": "x.inp",
        "output_dir": "out",
        "sweeps": {"alpha": [0, 1, 2]},
    })
    form = SweepForm(sc)

    from PySide2.QtWidgets import QLabel
    labels = form.findChildren(QLabel)
    label_texts = {lbl.text() for lbl in labels}

    # 期望包含 3 个 i18n 文本
    assert tg("sweep.lbl.template") in label_texts
    assert tg("sweep.lbl.output") in label_texts
    assert tg("sweep.lbl.naming") in label_texts


def test_sweep_form_yaml_load_fills_fields(qapp, tmp_path):
    """load_yaml 后,表单字段应自动从 controller 回填。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    form = SweepForm(sc)
    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(
        "template: t.inp\n"
        "output_dir: o\n"
        "sweeps:\n"
        "  alpha: [0, 5]\n",
        encoding="utf-8",
    )
    form.load_yaml(str(yaml_file))
    assert form._edit_tpl.text() == "t.inp"
    assert form._edit_out.text() == "o"
    assert form._axes_table.rowCount() == 1


# --- Task 7:轴表 cell widget 化测试 ---------------------------------


def test_sweep_form_axes_table_uses_combobox_cells(qapp):
    """轴表第 0 列 cell 是 QComboBox(非 QTableWidgetItem)。"""
    from PySide2.QtWidgets import QComboBox, QLabel, QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")  # 触发 cell widget 构造
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox), "got {}".format(type(cell))
    cell1 = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell1, (QLabel, QLineEdit))


def test_sweep_form_axes_combobox_populated_with_vars(qapp):
    """combobox items 来自 controller.available_vars(当前模板)。"""
    from PySide2.QtWidgets import QComboBox

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox)
    labels = [cell.itemText(i) for i in range(cell.count())]
    # 至少含 3 个枚举轴(label 形式为 "key (枚举:...)")
    assert any(lbl.startswith("turbulence") for lbl in labels)
    assert any(lbl.startswith("energy") for lbl in labels)
    assert any(lbl.startswith("gas") for lbl in labels)


# --- Task 8: 类型校验测试(int/float on edit finished) ----------------


def test_sweep_form_validates_int_axis_on_edit_finished(qapp, monkeypatch):
    """整型轴:输入 'abc' 失焦,状态栏报错。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="test.int_var",
        label="test.int_var [int] = 1",
        kind="int",
        block="test", keyword="int_var", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("test.int_var", "1")
    cell = form._axes_table.cellWidget(form._axes_table.rowCount() - 1, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("abc")
    cell.editingFinished.emit()
    status_text = form._lbl_status.text()
    assert "整数" in status_text or "int" in status_text.lower()


def test_sweep_form_accepts_float_d_notation(qapp, monkeypatch):
    """浮点轴接受 '1.0d-3' (FORTRAN 双精度写法)。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="test.float_var",
        label="test.float_var [float] = 1.0",
        kind="float",
        block="test", keyword="float_var", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("test.float_var", "1.0d-3")
    cell = form._axes_table.cellWidget(form._axes_table.rowCount() - 1, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("1.0d-3")
    cell.editingFinished.emit()
    text = form._lbl_status.text()
    assert "不是浮点" not in text


def test_sweep_form_orphan_axis_disables_run_button(monkeypatch):
    """失效轴(不在当前模板的)→ 红底 + 运行按钮禁用。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    def fake_available(template_path=None):
        return [VarSpec(
            key="good", label="good [int] = 1", kind="int",
            block="b", keyword="good", value_idx=0,
        )]
    monkeypatch.setattr(ctrl, "available_vars", fake_available)

    form._append_axis_row("good", "1")
    form._append_axis_row("orphan", "1")
    form._scan_orphan_axes()

    assert not form._btn_run.isEnabled()
    assert not form._btn_run_dry.isEnabled()
    assert "未识别" in form._lbl_status.text() or "失效" in form._lbl_status.text()


def test_sweep_form_no_orphan_no_disabled_message(monkeypatch):
    """无失效轴:状态栏无「未识别」字样。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    def fake_available(template_path=None):
        return [
            VarSpec(key="a", label="a [int] = 1", kind="int", block="b", keyword="a", value_idx=0),
            VarSpec(key="b", label="b [int] = 2", kind="int", block="b", keyword="b", value_idx=0),
        ]
    monkeypatch.setattr(ctrl, "available_vars", fake_available)
    form._append_axis_row("a", "1")
    form._append_axis_row("b", "2")
    form._scan_orphan_axes()
    assert "未识别" not in form._lbl_status.text()


# --- Task 10: 覆盖率补充测试 ----------------------------------------


def test_sweep_form_parse_scalar_returns_string():
    """_parse_scalar: 整型/浮点都失败时返回原字符串。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    assert SweepForm._parse_scalar("hello") == "hello"
    assert SweepForm._parse_scalar("v1.2.3") == "v1.2.3"
    assert SweepForm._parse_scalar("  abc  ") == "abc"


def test_sweep_form_parse_scalar_int_and_float():
    """_parse_scalar: 整型优先,失败再试浮点。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    assert SweepForm._parse_scalar("42") == 42
    assert isinstance(SweepForm._parse_scalar("42"), int)
    assert SweepForm._parse_scalar("3.14") == 3.14
    assert isinstance(SweepForm._parse_scalar("3.14"), float)
    assert SweepForm._parse_scalar("1e6") == 1e6


def test_sweep_form_collect_to_dict_missing_output_raises(qapp, monkeypatch):
    """_collect_to_dict: output 为空时抛 ValueError。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("t.inp")
    form._edit_out.setText("")  # 空

    import pytest
    with pytest.raises(ValueError):
        form._collect_to_dict()


def test_sweep_form_collect_to_dict_missing_template_raises(qapp):
    """_collect_to_dict: template 为空时抛 ValueError。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    import pytest

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("")  # 空
    form._edit_out.setText("out")

    with pytest.raises(ValueError):
        form._collect_to_dict()


def test_sweep_form_collect_to_dict_invalid_scalar_raises(qapp, monkeypatch):
    """_collect_to_dict: 值 cell 含无法解析的元素时抛 ValueError(带原值提示)。

    通过 monkey-patch _parse_scalar 强制抛 ValueError 触发 except 分支。
    """
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec
    import pytest

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("t.inp")
    form._edit_out.setText("out")
    fake_spec = VarSpec(
        key="my.var", label="my.var", kind="str",
        block="b", keyword="v", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("my.var", "abc")
    # 强制 _parse_scalar 抛错
    def boom(_s):
        raise ValueError("simulated parse failure")
    monkeypatch.setattr(SweepForm, "_parse_scalar", staticmethod(boom))
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    with pytest.raises(ValueError) as ei:
        form._collect_to_dict()
    assert "my.var" in str(ei.value)


def test_sweep_form_collect_to_dict_enum_cell(qapp, monkeypatch):
    """_collect_to_dict: enum cell 是 QLabel,值取自 spec.enum_values。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("t.inp")
    form._edit_out.setText("out")
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    d = form._collect_to_dict()
    assert d["sweeps"]["turbulence"] == ["sst", "kw", "sa"]


def test_sweep_form_collect_to_dict_spec_none_skip(qapp, monkeypatch):
    """_collect_to_dict: 行的 spec 为 None(空 combobox) 时跳过该行。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("t.inp")
    form._edit_out.setText("out")
    # 不 append 任何行 → 0 行
    d = form._collect_to_dict()
    assert d["sweeps"] == {}


def test_sweep_form_spec_for_row_combo_no_key(qapp, monkeypatch):
    """_spec_for_row: combobox 没设 currentData 时返回 None。"""
    from PySide2.QtWidgets import QComboBox

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    # 插入一个空 combo 的行
    form._axes_table.insertRow(0)
    empty_combo = QComboBox(form)
    form._axes_table.setCellWidget(0, 0, empty_combo)
    assert form._spec_for_row(0) is None


def test_sweep_form_spec_for_row_returns_none_for_non_combo(qapp):
    """_spec_for_row: 第 0 列不是 QComboBox 时返回 None。"""
    from PySide2.QtWidgets import QLabel

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._axes_table.insertRow(0)
    form._axes_table.setCellWidget(0, 0, QLabel("not a combo", form))
    assert form._spec_for_row(0) is None


def test_sweep_form_validate_value_cell_empty_returns_none(qapp, monkeypatch):
    """_validate_value_cell: 值为空时直接返回 None(不校验)。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="my.int", label="my.int [int] = 1", kind="int",
        block="b", keyword="int", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("my.int", "")
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("")  # 空
    assert form._validate_value_cell(0) is None


def test_sweep_form_validate_value_cell_float_failure(qapp, monkeypatch):
    """_validate_value_cell: float kind, 非数字 + 非 FORTRAN d 写法时失败。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="my.float", label="my.float [float] = 1.0", kind="float",
        block="b", keyword="float", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("my.float", "1.0")
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("1.0, abc, 2.0")
    err = form._validate_value_cell(0)
    assert err is not None
    assert "my.float" in err


def test_sweep_form_validate_value_cell_label_returns_none(qapp, monkeypatch):
    """_validate_value_cell: cell 不是 QLineEdit(enum QLabel) 时直接返回 None。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    # enum cell 是 QLabel → 跳过校验
    assert form._validate_value_cell(0) is None


def test_sweep_form_scan_orphan_skips_spec_none_row(qapp, monkeypatch):
    """_scan_orphan_axes: 第 0 列不是 combo 的行(spec None)直接跳过。"""
    from PySide2.QtWidgets import QLabel

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    # 注入一行没 combo 的行
    form._axes_table.insertRow(0)
    form._axes_table.setCellWidget(0, 0, QLabel("placeholder", form))
    n = form._scan_orphan_axes()
    assert n == 0


def test_sweep_form_on_axis_changed_recreates_cell(qapp, monkeypatch):
    """_on_axis_changed: 切换 combobox 选中的变量后,值 cell 会被重建。"""
    from PySide2.QtWidgets import QComboBox

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    int_spec = VarSpec(
        key="my.int", label="my.int [int] = 1", kind="int",
        block="b", keyword="int", value_idx=0,
    )
    flt_spec = VarSpec(
        key="my.float", label="my.float [float] = 1.0", kind="float",
        block="b", keyword="float", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [int_spec, flt_spec],
    )
    form._append_axis_row("my.int", "5")
    combo = form._axes_table.cellWidget(0, 0)
    assert isinstance(combo, QComboBox)
    # 切到 my.float
    for i in range(combo.count()):
        if combo.itemData(i) == "my.float":
            combo.setCurrentIndex(i)
            break
    # 切完后值 cell 应当是 QLineEdit(因为 my.float 是 float 不是 enum)
    from PySide2.QtWidgets import QLineEdit
    new_cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(new_cell, QLineEdit)


def test_sweep_form_make_combo_keeps_orphan_key(qapp, monkeypatch):
    """_make_combo_for_row: spec 的 key 不在当前模板的 specs 中时,作为 orphan 保留在 combobox 头部。"""
    from PySide2.QtWidgets import QComboBox

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    int_spec = VarSpec(
        key="valid", label="valid [int] = 1", kind="int",
        block="b", keyword="v", value_idx=0,
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [int_spec],
    )
    orphan = VarSpec(
        key="orphan.key", label="orphan.key (未知)", kind="str",
        block=None, keyword=None, value_idx=None,
    )
    combo = form._make_combo_for_row(orphan)
    assert isinstance(combo, QComboBox)
    keys = [combo.itemData(i) for i in range(combo.count())]
    assert "orphan.key" in keys
    # 应被设为 current
    assert combo.currentData() == "orphan.key"


def test_sweep_form_mark_row_normal_clears_style(qapp):
    """_mark_row_normal: 清除红底 style。"""
    from PySide2.QtWidgets import QLabel

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._axes_table.insertRow(0)
    w0 = QLabel("c0", form)
    w1 = QLabel("c1", form)
    w0.setStyleSheet("background-color: #FFD6D6;")
    w1.setStyleSheet("background-color: #FFD6D6;")
    form._axes_table.setCellWidget(0, 0, w0)
    form._axes_table.setCellWidget(0, 1, w1)
    form._mark_row_normal(0)
    assert w0.styleSheet() == ""
    assert w1.styleSheet() == ""


def test_sweep_form_load_json_fills_fields(qapp, tmp_path):
    """load_json 后,表单字段应自动从 controller 回填。"""
    import json
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    form = SweepForm(sc)
    json_file = tmp_path / "test.json"
    json_file.write_text(
        json.dumps({
            "template": "t.inp",
            "output_dir": "o",
            "sweeps": {"alpha": [0, 5]},
        }),
        encoding="utf-8",
    )
    form.load_json(str(json_file))
    assert form._edit_tpl.text() == "t.inp"
    assert form._edit_out.text() == "o"
    assert form._axes_table.rowCount() == 1


def test_sweep_form_refresh_table_with_no_report(qapp):
    """_refresh_table: last_report 为 None 时清空表。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    form = SweepForm(sc)
    form._refresh_table()
    assert form._table.rowCount() == 0


def test_sweep_form_update_status_when_not_loaded(qapp):
    """_update_status: 未 load 时运行按钮应禁用、状态栏空、case 数 0。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    sc = SweepController()
    form = SweepForm(sc)
    form._update_status()
    assert not form._btn_run.isEnabled()
    assert not form._btn_run_dry.isEnabled()
    assert form._lbl_status.text() == ""


# --- Bug fix: enum 值列表应可编辑(允许子集/自定义) -----------------


def test_sweep_form_enum_value_cell_is_qlineedit(qapp, monkeypatch):
    """Bug fix: enum kind 的值 cell 必须是 QLineEdit,不是 QLabel。

    旧实现把 enum cell 渲染为 QLabel(只读),用户无法做子集 sweep,
    引擎 `_normalize_axis_value` 虽然支持任意子集。
    """
    from PySide2.QtWidgets import QLabel, QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit), (
        "enum 值 cell 应为 QLineEdit,got {}".format(type(cell).__name__)
    )
    assert not isinstance(cell, QLabel), "enum cell 不应是 QLabel"


def test_sweep_form_enum_value_cell_prefilled(qapp, monkeypatch):
    """enum 值 cell 初始文本预填全部 enum_values(逗号分隔),用户可编辑删减。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    assert cell.text() == "sst, kw, sa"


def test_sweep_form_enum_value_user_can_subset(qapp, monkeypatch):
    """用户编辑 enum cell 删去某个值,_collect_to_dict 应反映子集。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._edit_tpl.setText("t.inp")
    form._edit_out.setText("out")
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("sst, kw")  # 用户只想要 sst 和 kw,不要 sa
    d = form._collect_to_dict()
    assert d["sweeps"]["turbulence"] == ["sst", "kw"]


def test_sweep_form_value_cell_exists_when_spec_none(qapp, monkeypatch):
    """Bug fix: spec 为 None(空 combo)时,值 cell 也应创建为默认 QLineEdit。

    旧实现 `if spec is not None: setCellWidget(r, 1, cell)` —— 若 spec 为 None
    则 cell 永远 None,用户无法编辑。
    """
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    # monkeypatch 让 available_vars 返回空列表(对应 spec 为 None 的场景)
    monkeypatch.setattr(
        ctrl, "available_vars", lambda template_path=None: []
    )
    form._append_axis_row("", "")
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit), (
        "spec 为 None 时值 cell 也应存在(默认 QLineEdit),got {}".format(
            type(cell).__name__ if cell is not None else "None"
        )
    )


def test_sweep_form_axes_table_value_col_is_qlineedit(qapp):
    """Bug fix: 值列 cell 一律是 QLineEdit(不论 spec.kind)。

    旧测试断言 `(QLabel, QLineEdit)` 都能接受,过于宽松。修复后必须是 QLineEdit。
    """
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)


def test_sweep_form_validate_enum_cell_bad_value(qapp, monkeypatch):
    """_validate_value_cell: enum cell 含非法值时报错,信息含非法值与合法值集合。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("sst, foo, bar")  # foo/bar 不在合法集合
    err = form._validate_value_cell(0)
    assert err is not None
    assert "foo" in err
    assert "bar" in err
    # 任意合法值都应出现在错误信息中(供用户参考)
    assert any(v in err for v in ("sst", "kw", "sa"))


def test_sweep_form_validate_enum_cell_subset_ok(qapp, monkeypatch):
    """_validate_value_cell: enum 子集(sst, kw)应通过校验,不被误报。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw", "sa"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("sst, kw")  # 合法子集
    err = form._validate_value_cell(0)
    assert err is None


def test_sweep_form_enum_tooltip_uses_dedicated_key(qapp, monkeypatch):
    """M1 review 修复:enum cell tooltip 走独立 i18n key,不从错误模板切 ;。"""
    from PySide2.QtWidgets import QLineEdit

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec
    from inp_tool.i18n_gui import tg

    ctrl = SweepController()
    form = SweepForm(ctrl)
    fake_spec = VarSpec(
        key="turbulence", label="turbulence", kind="enum",
        block=None, keyword=None, value_idx=None,
        enum_values=("sst", "kw"),
    )
    monkeypatch.setattr(
        ctrl, "available_vars",
        lambda template_path=None: [fake_spec],
    )
    form._append_axis_row("turbulence", [])
    cell = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell, QLineEdit)
    # tooltip 应等于独立 key 的取值(且不含未渲染的 {key}/{bad} 占位符)
    assert cell.toolTip() == tg("sweep.lbl.enum_tooltip")
    assert "{key}" not in cell.toolTip()
    assert "{bad}" not in cell.toolTip()
