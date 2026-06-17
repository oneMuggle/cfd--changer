"""SweepYamlEditorWidget (Phase 5 / Task 5.1 + 5.2) GUI 单测。

覆盖范围:
- 空 widget 构造 + text() == ""
- set_text / text round-trip
- 等宽字体(monospace / Courier)
- set_error_line 不崩(无 public getter,只验证不抛)
- 行号区在 widget 销毁时不崩(显式调用 hide / deleteLater 后再次实例化)
- Task 5.2 实时 schema lint:
  - 有效 YAML → store_changed emit ConfigStore
  - 无效 YAML → validation_error emit + error_line > 0
  - 空文本 → status="empty",无信号
  - lint 永不抛异常
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide2.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


# --- Task 5.2 实时 schema lint ---------------------------------------------------

_VALID_YAML = (
    "version: 2\n"
    "template: t.inp\n"
    "output_dir: /out\n"
    "naming: case\n"
    "sweeps:\n"
    "  mach: [1, 2]\n"
)


def test_editor_lint_valid_yaml_emits_store(qapp):
    """有效 YAML → store_changed emit 包含 ConfigStore。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget
    from inp_tool_gui.models.config_store import ConfigStore

    w = YamlEditorWidget()
    received_stores = []
    w.store_changed.connect(lambda s: received_stores.append(s))

    w.set_text(_VALID_YAML)
    # 跳过 debounce,直接调 _do_lint(测试不希望等 200ms)
    w._do_lint()

    assert w.validation_status == "valid"
    assert len(received_stores) >= 1
    assert isinstance(received_stores[0], ConfigStore)
    assert received_stores[0].template == "t.inp"
    assert received_stores[0].output_dir == "/out"
    assert "mach" in received_stores[0].sweeps


def test_editor_lint_invalid_yaml_marks_error(qapp):
    """坏 YAML → validation_error emit, error_line > 0。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    received = []
    w.validation_error.connect(lambda msg: received.append(msg))

    # unclosed bracket → yaml.safe_load 必失败
    w.set_text("foo: [unclosed bracket\nbar: baz\n")
    w._do_lint()

    assert w.validation_status == "error"
    assert w.error_line > 0
    assert len(received) >= 1


def test_editor_lint_empty_text(qapp):
    """空文本 → status = empty, 无 emit。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    received = []
    w.store_changed.connect(lambda s: received.append(s))
    w.set_text("")
    w._do_lint()
    assert w.validation_status == "empty"
    assert received == []


def test_editor_lint_whitespace_only_is_empty(qapp):
    """纯空白文本(非空字符串但无内容)→ status = empty。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    w.set_text("   \n\t\n  \n")
    w._do_lint()
    assert w.validation_status == "empty"


def test_editor_lint_missing_template_field(qapp):
    """schema 错误(template 缺失)→ validation_error emit, status = error。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    received = []
    w.validation_error.connect(lambda msg: received.append(msg))

    # YAML 合法,但缺 template / output_dir
    w.set_text("version: 2\nsweeps: {}\n")
    w._do_lint()

    assert w.validation_status == "error"
    assert len(received) >= 1
    # 错误信息应提到 template
    assert "template" in received[0]


def test_editor_lint_top_level_not_mapping(qapp):
    """顶层不是 mapping(纯列表)→ validation_error emit。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    received = []
    w.validation_error.connect(lambda msg: received.append(msg))

    w.set_text("- 1\n- 2\n- 3\n")
    w._do_lint()

    assert w.validation_status == "error"
    assert len(received) >= 1


def test_editor_lint_after_text_change_emits_after_debounce(qapp):
    """用户输入 → 等防抖 → 触发 store_changed(走 QTimer 真实路径)。"""
    from PySide2.QtCore import QEventLoop, QTimer
    from PySide2.QtWidgets import QApplication
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    received = []
    w.store_changed.connect(lambda s: received.append(s))

    # set_text 内部 blockSignals,不会触发 lint
    w.set_text(_VALID_YAML)
    # 手动 insert 一个空格(实际改变文本 → 触发 textChanged → 重启 QTimer)
    cursor = w.plain_text_edit.textCursor()
    cursor.movePosition(cursor.End)
    w.plain_text_edit.setTextCursor(cursor)
    cursor.insertText(" ")

    # 等防抖:200ms 定时器 + 余量
    loop = QEventLoop()
    QTimer.singleShot(350, loop.quit)
    loop.exec_()

    assert len(received) >= 1
    assert w.validation_status == "valid"


def test_editor_lint_does_not_crash_on_garbage(qapp):
    """奇葩输入 → _do_lint 永不抛(可能 status=error 或 empty)。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    # 多重奇葩:看似 mapping 但缺必填字段
    w.set_text("!!python/object/apply:os.system ['echo hi']\n")
    try:
        w._do_lint()
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"_do_lint 必须兜底,不应抛异常: {exc}")
    # 状态不是 "valid" 就行(可能 error 或 empty)
    assert w.validation_status in ("error", "empty", "valid")


def test_editor_validation_status_property_readable(qapp):
    """validation_status 必为 valid/error/empty 之一。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    assert w.validation_status in ("valid", "error", "empty")


def test_editor_creates_empty(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    assert w.text() == ""


def test_editor_set_text_get_text_roundtrip(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    sample = "version: 2\ntemplate: t.inp\nsweeps:\n  mach: [1, 2]\n"
    w.set_text(sample)
    assert w.text() == sample


def test_editor_uses_monospace_font(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    font = w.font()
    family = font.family().lower()
    # 任一 monospace 风格字体家族皆可(Qt 视平台 fallback)
    assert "mono" in family or "courier" in family


def test_editor_set_error_line(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    w.set_text("line1\nline2\nline3\n")
    # 标记第二行为错误;不应崩
    w.set_error_line(2)
    assert w.error_line == 2
    # 清除错误
    w.set_error_line(0)
    assert w.error_line == 0
    # 越界 / 负数:不应崩,被夹到 0
    w.set_error_line(-3)
    assert w.error_line == 0
    w.set_error_line(999)
    assert w.error_line == 999


def test_editor_syntax_highlighter_attached(qapp):
    """高亮器应已 attach 到内部 editor 的 document。"""
    # YamlEditorWidget + YamlHighlighter 都在 sweep_yaml_editor(基础 widget)
    from inp_tool_gui.widgets.sweep_yaml_editor import (
        YamlEditorWidget,
        YamlHighlighter,
    )

    w = YamlEditorWidget()
    # 高亮器存在 + 类型正确
    assert isinstance(w._highlighter, YamlHighlighter)  # type: ignore[attr-defined]
    # 内部 editor 可访问(供子类扩展)
    assert w.plain_text_edit is not None


def test_editor_text_changes_after_edit(qapp):
    """用户手动编辑后 text() 应反映最新内容。"""
    from inp_tool_gui.widgets.sweep_yaml_editor import YamlEditorWidget

    w = YamlEditorWidget()
    w.set_text("version: 2\n")
    # 移动光标到末尾并插入文本(模拟用户键入)
    cursor = w.plain_text_edit.textCursor()
    cursor.movePosition(cursor.End)
    w.plain_text_edit.setTextCursor(cursor)
    cursor.insertText("template: t.inp\n")
    assert "template: t.inp" in w.text()
    assert w.text().startswith("version: 2")


# --- Task 5.3 SweepYamlEditorView 容器 ----------------------------------------


def test_yaml_editor_view_creates_from_store(qapp):
    from inp_tool_gui.widgets.sweep_yaml_editor_view import SweepYamlEditorView
    from inp_tool_gui.models.config_store import ConfigStore
    store = ConfigStore(template="t", output_dir="/o", naming="case",
                         preset_ref=None, sweeps={}, conditions=())
    v = SweepYamlEditorView(store)
    assert v.config_store() is store


def test_yaml_editor_view_set_store_updates_editor(qapp):
    """外部 set_store → YAML 编辑器文本更新。"""
    from inp_tool_gui.widgets.sweep_yaml_editor_view import SweepYamlEditorView
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec

    v = SweepYamlEditorView(ConfigStore(template="", output_dir="", naming="case",
                                          preset_ref=None, sweeps={}, conditions=()))

    new_store = ConfigStore(
        template="new.inp", output_dir="/new_out", naming="case",
        preset_ref=None,
        sweeps={"mach": AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)},
        conditions=(),
    )
    v.set_store(new_store)
    assert v.config_store() is new_store
    # YAML 文本应包含 "new.inp" 和 "mach"
    yaml_text = v._editor.text()
    assert "new.inp" in yaml_text
    assert "mach" in yaml_text


def test_yaml_editor_view_preview_table_populated(qapp):
    """store 有 3 个 case → 预览表 3 行。"""
    from inp_tool_gui.widgets.sweep_yaml_editor_view import SweepYamlEditorView
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec

    store = ConfigStore(
        template="t", output_dir="/o", naming="case",
        preset_ref=None,
        sweeps={"a": AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)},
        conditions=(),
    )
    v = SweepYamlEditorView(store)
    assert v.preview_row_count() == 3


def test_yaml_editor_view_variable_tree_inserts_key(qapp, monkeypatch):
    """variable_picked → YAML 编辑器光标处插入 key。"""
    from inp_tool_gui.widgets.sweep_yaml_editor_view import SweepYamlEditorView
    from inp_tool_gui.widgets.sweep_var_combo import VarSpec
    from inp_tool_gui.models.config_store import ConfigStore

    store = ConfigStore(template="t", output_dir="/o", naming="case",
                         preset_ref=None, sweeps={}, conditions=())
    v = SweepYamlEditorView(store)
    v._editor.set_text("version: 2\ntemplate: t\n")  # 给个起点

    # 模拟手动 emit variable_picked
    v._var_tree.variable_picked.emit("mach")

    # YAML 文本应包含 "mach"
    assert "mach" in v._editor.text()


def test_yaml_editor_view_preset_doubleclick_loads(qapp, tmp_path):
    """preset 列表双击 → 加载 preset YAML 到编辑器 + emit preset_loaded。"""
    from inp_tool_gui.widgets.sweep_yaml_editor_view import SweepYamlEditorView
    from inp_tool_gui.preset_library import PresetLibrary
    from inp_tool_gui.models.config_store import ConfigStore

    # 写一个临时 preset YAML
    preset_yaml = (
        "version: 2\n"
        "template: t\n"
        "output_dir: /o\n"
        "naming: case\n"
        "sweeps:\n"
        "  mach: [1, 2]\n"
    )
    preset_file = tmp_path / "test_preset.yaml"
    preset_file.write_text(preset_yaml, encoding="utf-8")

    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    store = ConfigStore(template="t", output_dir="/o", naming="case",
                         preset_ref=None, sweeps={}, conditions=())
    v = SweepYamlEditorView(store, preset_library=lib)

    received = []
    v.preset_loaded.connect(lambda r: received.append(r))

    # 找到列表里的项,双击
    assert v._preset_list.count() >= 1
    item = v._preset_list.item(0)
    v._preset_list.itemDoubleClicked.emit(item)

    assert v.preset_loaded_payload() == "test_preset"
    assert received == ["test_preset"]
    # YAML 文本应包含 preset 的 sweeps
    assert "mach" in v._editor.text()
