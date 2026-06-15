# inp_tool GUI 优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升 inp_tool 桌面 GUI 的人机工程 —— 中文 UI、批量算例实时编辑、字段说明/搜索、文件夹/文件双模式。

**Architecture:**
- 复用现有 `inp_tool.i18n` 机制扩展 GUI 字符串(新增 `gui.*` 命名空间),默认 `zh`。
- 批量算例新增"实时表单"页签,与 YAML/JSON 文件加载并列;两边改动通过 `SweepController.update_field()` 实时同步。
- 字段说明用 `dict[block, dict[keyword, help_zh]]` 常量;搜索栏通过 `QTreeWidgetItem.setHidden()` 实现过滤。
- 文件加载新增"模式选择对话框"(默认文件夹模式),`FileController` 增加 `open_case_dir()` 入口 + 完整性检查。
- 批量算例 per_dir 模式生成时复用 `source_dir` 模板(已存在),补全"必含文件"检查。

**Tech Stack:** Python 3.8 (LTS), PySide2, inp_tool core, pytest (TDD, ≥80% 覆盖率), `inp_tool.i18n`。

**目标版本:** inp_tool_gui v0.16.0(在 v0.15.2-dev 之上)

---

## 涉及文件清单

| 类别 | 路径 | 责任 |
|---|---|---|
| 新建 | `inp_tool/inp_tool/i18n_gui.py` | GUI 字符串字典 + `tg()` 函数 |
| 新建 | `inp_tool/inp_tool/field_help.py` | 字段含义字典 |
| 新建 | `inp_tool/inp_tool_gui/widgets/field_search_bar.py` | 树形过滤搜索框组件 |
| 新建 | `inp_tool/inp_tool_gui/widgets/sweep_live_form.py` | Sweep 实时编辑表单 |
| 新建 | `inp_tool/inp_tool_gui/widgets/open_mode_dialog.py` | "打开模式"选择弹窗 |
| 修改 | `inp_tool/inp_tool_gui/main_window.py` | 用 i18n 包裹硬编码字符串;打开流程接入 OpenModeDialog |
| 修改 | `inp_tool/inp_tool_gui/controllers/file_controller.py` | 增加 `open_case_dir()` 与 `validate_case_dir()` |
| 修改 | `inp_tool/inp_tool_gui/controllers/sweep_controller.py` | 增加 `update_field()` 支持实时表单回写 |
| 修改 | `inp_tool/inp_tool_gui/widgets/inp_tree.py` | 接入 `FieldSearchBar` + `field_help` 提示 |
| 修改 | `inp_tool/inp_tool_gui/widgets/sweep_form.py` | 接入 `SweepLiveForm` 标签页,共用同一 SweepController |
| 修改 | `inp_tool/inp_tool_gui/widgets/detect_panel.py` | i18n 化(补漏) |
| 修改 | `inp_tool/inp_tool_gui/widgets/postprocess_panel.py` | i18n 化(同上) |
| 新建 | `inp_tool/tests/test_gui_i18n.py` | i18n 字符串字典完整性测试 |
| 新建 | `inp_tool/tests/test_field_help.py` | field_help 字典 key 存在性测试 |
| 新建 | `inp_tool/tests/test_gui_field_search.py` | 搜索框过滤行为测试 |
| 新建 | `inp_tool/tests/test_gui_sweep_live_form.py` | 实时表单 → controller 同步测试 |
| 新建 | `inp_tool/tests/test_gui_open_mode.py` | OpenModeDialog + FileController.open_case_dir 集成测试 |
| 新建 | `inp_tool/tests/test_gui_case_validation.py` | 算例完整性检查测试 |

---

## Task 1: 扩展 i18n 模块支持 GUI 字符串

**Files:**
- Modify: `inp_tool/inp_tool/i18n.py`(不变,只读)
- Create: `inp_tool/inp_tool/i18n_gui.py`
- Create: `inp_tool/tests/test_gui_i18n.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_gui_i18n.py
from inp_tool.i18n_gui import MESSAGES_GUI, tg, supported_keys


def test_messages_gui_has_zh_and_en():
    assert "zh" in MESSAGES_GUI
    assert "en" in MESSAGES_GUI


def test_zh_and_en_have_same_keys():
    zh = set(MESSAGES_GUI["zh"].keys())
    en = set(MESSAGES_GUI["en"].keys())
    missing_in_en = zh - en
    missing_in_zh = en - zh
    assert not missing_in_en, f"en 缺 key: {missing_in_en}"
    assert not missing_in_zh, f"zh 缺 key: {missing_in_zh}"


def test_tg_returns_zh_by_default():
    assert tg("menu.file") == "文件(&F)"


def test_tg_returns_en_after_set():
    from inp_tool.i18n_gui import set_gui_lang
    set_gui_lang("en")
    try:
        assert tg("menu.file") == "&File"
    finally:
        set_gui_lang("zh")


def test_tg_with_placeholder():
    assert "{n}".format(n=3) in tg("status.lines", n=3)


def test_supported_keys_returns_zh_keys():
    keys = supported_keys()
    assert "menu.file" in keys
    assert "sweep.btn.load_yaml" in keys
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_i18n.py -v
```
预期: `ModuleNotFoundError: No module named 'inp_tool.i18n_gui'`

- [ ] **Step 3: 创建 i18n_gui.py**

```python
# inp_tool/inp_tool/i18n_gui.py
"""GUI 专用 i18n(与 REPL i18n 独立)。

用法:
    from inp_tool.i18n_gui import tg, set_gui_lang
    set_gui_lang("zh")  # 默认
    tg("menu.file")  # "文件(&F)"
"""
from __future__ import annotations
import os
from typing import Any, Dict, List

_DEFAULT_LANG = os.environ.get("INP_TOOL_LANG", "zh")
if _DEFAULT_LANG not in ("zh", "en"):
    _DEFAULT_LANG = "zh"
_CURRENT_LANG: str = _DEFAULT_LANG

# 命名空间:
# - menu.* / act.* / tab.* / toolbar.* / status.* 主框架
# - dialog.*  弹窗标题/过滤
# - sweep.*   sweep 标签页
# - detect.*  detect 标签页
# - tree.*    InpTreeWidget + 搜索框
# - postprocess.*  后处理面板
# - open_mode.*    打开模式选择
# - case_check.*   算例完整性检查
MESSAGES_GUI: Dict[str, Dict[str, str]] = {
    "zh": {
        "menu.file": "文件(&F)",
        "menu.edit": "编辑(&E)",
        "menu.sweep": "Sweep(&W)",
        "menu.detect": "检测(&D)",
        "menu.help": "帮助(&H)",
        "act.open": "打开(&O)...",
        "act.save": "保存(&S)",
        "act.save_as": "另存为(&A)...",
        "act.exit": "退出(&X)",
        "act.undo": "撤销(&U)",
        "act.redo": "重做(&R)",
        "act.sweep": "批量算例(&W)...",
        "act.detect": "检测方程/湍流(&D)",
        "act.about": "关于(&A)...",
        "toolbar.main": "主工具栏",
        "status.no_file": "(未打开文件)",
        "status.lines": "{n} 行",
        "tab.file": "文件(&E)",
        "tab.detect": "检测(&T)",
        "tab.sweep": "Sweep(&S)",
        "tab.sweep_live": "实时编辑(&L)",
        "tab.diff": "对比(&D)",
        "tab.postprocess": "后处理(&P)",
        "dialog.open_title": "打开 mcfd.inp",
        "dialog.open_inp_filter": "mcfd.inp (*.inp);;所有文件 (*)",
        "dialog.open_failed_title": "打开失败",
        "dialog.save_title": "另存为",
        "dialog.save_failed_title": "保存失败",
        "dialog.no_file": "请先打开一个 .inp 文件。",
        "sweep.btn.load_yaml": "加载 YAML...",
        "sweep.btn.load_json": "加载 JSON...",
        "sweep.btn.run_dry": "运行(Dry)",
        "sweep.btn.run": "运行",
        "sweep.btn.force": "强制覆盖",
        "sweep.btn.save_config": "保存为 YAML",
        "sweep.lbl.template": "模板:",
        "sweep.lbl.output": "输出目录:",
        "sweep.lbl.naming": "命名:",
        "sweep.lbl.case_count": "case 数:",
        "sweep.lbl.empty": "(未加载)",
        "sweep.lbl.short": "(略)",
        "sweep.col.case_id": "case_id",
        "sweep.col.path": "path",
        "sweep.col.params": "params",
        "sweep.col.applied": "applied",
        "sweep.title.cfg": "当前配置",
        "sweep.title.sweeps_axes": "Sweep 轴(键=值列表,逗号分隔)",
        "sweep.run_failed": "Sweep 失败:\n{err}",
        "sweep.load_failed_yaml": "无法解析 YAML:\n{err}",
        "sweep.load_failed_json": "无法解析 JSON:\n{err}",
        "sweep.live.sync_ok": "已同步到 SweepController",
        "sweep.live.sync_fail": "同步失败:{err}",
        "sweep.live.need_template": "请先填模板路径",
        "sweep.live.need_output": "请先填输出目录",
        "sweep.live.invalid_axis": "轴 {key} 的值不是合法列表/标量:{val}",
        "detect.btn.run": "运行检测",
        "detect.btn.preset_turb": "应用 SST k-ω",
        "detect.btn.preset_2t": "应用 双温度(2T)",
        "detect.btn.preset_species": "应用 多组分",
        "detect.lbl.summary_empty": "尚未运行检测",
        "detect.title.report": "检测报告",
        "detect.title.notes": "方程检测告警(notes)",
        "detect.title.sweep_warn": "Sweep Axis 告警",
        "detect.title.rec": "推荐字段",
        "detect.lbl.empty": "(无)",
        "detect.lbl.rec_empty": "(无推荐字段 — 关键字段已齐备)",
        "detect.btn.apply": "应用",
        "tree.search.placeholder": "搜索字段(关键字或值片段)",
        "tree.search.btn_clear": "清空",
        "tree.search.hits_zero": "无匹配字段",
        "tree.lbl.top": "顶层语句",
        "tree.lbl.blocks": "块",
        "postprocess.title.case_dirs": "算例目录:",
        "postprocess.btn.add": "添加算例",
        "postprocess.btn.run_extract": "提取气动力",
        "postprocess.btn.run_convergence": "生成收敛报告",
        "postprocess.btn.run_report": "生成 Excel",
        "postprocess.btn.run_plot": "生成收敛图",
        "postprocess.btn.run_all": "一键全部",
        "postprocess.lbl.op": "工况点:",
        "postprocess.lbl.sref": "参考面积 Sref:",
        "postprocess.lbl.lref": "参考长度 Lref:",
        "postprocess.lbl.xref": "Xref:",
        "postprocess.lbl.yref": "Yref:",
        "postprocess.lbl.zref": "Zref:",
        "postprocess.lbl.xcg": "质心 Xcg:",
        "open_mode.title": "选择打开方式",
        "open_mode.label": "要打开的是单个 .inp 文件,还是一个完整的算例目录?",
        "open_mode.file_radio": "文件模式(只打开 .inp)",
        "open_mode.folder_radio": "文件夹模式(打开完整算例)",
        "open_mode.folder_hint": "文件夹模式会校验 mcfd.inp 完整性,推荐用于批量算例。",
        "open_mode.remember": "记住我的选择",
        "open_mode.ok": "确定",
        "open_mode.cancel": "取消",
        "case_check.title": "算例完整性检查",
        "case_check.ok": "✓ 算例完整,可用于 sweep 生成",
        "case_check.missing_inp": "✗ 缺少 mcfd.inp",
        "case_check.missing_pbs": "⚠ 缺少 PBS 脚本(批量提交时无法直接 qsub)",
        "case_check.missing_geometry": "⚠ 缺少几何文件(请确认 tri/plt 文件存在)",
        "case_check.parse_error": "✗ mcfd.inp 解析失败:{err}",
        "case_check.empty_axes": "⚠ 批量算例轴为空,请确认 .inp 已正确加载",
    },
    "en": {
        "menu.file": "&File",
        "menu.edit": "&Edit",
        "menu.sweep": "S&weep",
        "menu.detect": "&Detect",
        "menu.help": "&Help",
        "act.open": "&Open...",
        "act.save": "&Save",
        "act.save_as": "Save &As...",
        "act.exit": "E&xit",
        "act.undo": "&Undo",
        "act.redo": "&Redo",
        "act.sweep": "S&weep Cases...",
        "act.detect": "Detect Equations/&Turbulence",
        "act.about": "&About...",
        "toolbar.main": "Main Toolbar",
        "status.no_file": "(no file open)",
        "status.lines": "{n} lines",
        "tab.file": "&File",
        "tab.detect": "&Detect",
        "tab.sweep": "&Sweep",
        "tab.sweep_live": "&Live Edit",
        "tab.diff": "&Diff",
        "tab.postprocess": "&Post",
        "dialog.open_title": "Open mcfd.inp",
        "dialog.open_inp_filter": "mcfd.inp (*.inp);;All files (*)",
        "dialog.open_failed_title": "Open Failed",
        "dialog.save_title": "Save As",
        "dialog.save_failed_title": "Save Failed",
        "dialog.no_file": "Please open a .inp file first.",
        "sweep.btn.load_yaml": "Load YAML...",
        "sweep.btn.load_json": "Load JSON...",
        "sweep.btn.run_dry": "Run (Dry)",
        "sweep.btn.run": "Run",
        "sweep.btn.force": "Force Overwrite",
        "sweep.btn.save_config": "Save as YAML",
        "sweep.lbl.template": "Template:",
        "sweep.lbl.output": "Output Dir:",
        "sweep.lbl.naming": "Naming:",
        "sweep.lbl.case_count": "Case count:",
        "sweep.lbl.empty": "(not loaded)",
        "sweep.lbl.short": "(omitted)",
        "sweep.col.case_id": "case_id",
        "sweep.col.path": "path",
        "sweep.col.params": "params",
        "sweep.col.applied": "applied",
        "sweep.title.cfg": "Current Config",
        "sweep.title.sweeps_axes": "Sweep axes (key=list-of-values, comma-separated)",
        "sweep.run_failed": "Sweep failed:\n{err}",
        "sweep.load_failed_yaml": "Failed to parse YAML:\n{err}",
        "sweep.load_failed_json": "Failed to parse JSON:\n{err}",
        "sweep.live.sync_ok": "Synced to SweepController",
        "sweep.live.sync_fail": "Sync failed: {err}",
        "sweep.live.need_template": "Please fill in template path first",
        "sweep.live.need_output": "Please fill in output directory first",
        "sweep.live.invalid_axis": "Axis {key} value is not a valid list/scalar: {val}",
        "detect.btn.run": "Run Detection",
        "detect.btn.preset_turb": "Apply SST k-ω",
        "detect.btn.preset_2t": "Apply Two-Temperature (2T)",
        "detect.btn.preset_species": "Apply Multi-Species",
        "detect.lbl.summary_empty": "Detection not run yet",
        "detect.title.report": "Detection Report",
        "detect.title.notes": "Equation Detection Warnings (notes)",
        "detect.title.sweep_warn": "Sweep Axis Warnings",
        "detect.title.rec": "Recommended Fields",
        "detect.lbl.empty": "(none)",
        "detect.lbl.rec_empty": "(no recommendations — key fields are complete)",
        "detect.btn.apply": "Apply",
        "tree.search.placeholder": "Search fields (keyword or value fragment)",
        "tree.search.btn_clear": "Clear",
        "tree.search.hits_zero": "No matching fields",
        "tree.lbl.top": "Top-level Statements",
        "tree.lbl.blocks": "Blocks",
        "postprocess.title.case_dirs": "Case directories:",
        "postprocess.btn.add": "Add Case",
        "postprocess.btn.run_extract": "Extract Aero",
        "postprocess.btn.run_convergence": "Gen Convergence Report",
        "postprocess.btn.run_report": "Gen Excel",
        "postprocess.btn.run_plot": "Gen Convergence Plot",
        "postprocess.btn.run_all": "All-in-One",
        "postprocess.lbl.op": "Operating point:",
        "postprocess.lbl.sref": "Sref:",
        "postprocess.lbl.lref": "Lref:",
        "postprocess.lbl.xref": "Xref:",
        "postprocess.lbl.yref": "Yref:",
        "postprocess.lbl.zref": "Zref:",
        "postprocess.lbl.xcg": "Xcg:",
        "open_mode.title": "Choose Open Mode",
        "open_mode.label": "Are you opening a single .inp file, or a complete case directory?",
        "open_mode.file_radio": "File mode (open .inp only)",
        "open_mode.folder_radio": "Folder mode (open complete case)",
        "open_mode.folder_hint": "Folder mode validates mcfd.inp integrity, recommended for batch sweeps.",
        "open_mode.remember": "Remember my choice",
        "open_mode.ok": "OK",
        "open_mode.cancel": "Cancel",
        "case_check.title": "Case Integrity Check",
        "case_check.ok": "✓ Case is complete, ready for sweep",
        "case_check.missing_inp": "✗ Missing mcfd.inp",
        "case_check.missing_pbs": "⚠ Missing PBS script (cannot qsub directly)",
        "case_check.missing_geometry": "⚠ Missing geometry file (verify tri/plt files exist)",
        "case_check.parse_error": "✗ mcfd.inp parse failed: {err}",
        "case_check.empty_axes": "⚠ Sweep axes are empty — verify .inp is loaded",
    },
}


def get_gui_lang() -> str:
    return _CURRENT_LANG


def set_gui_lang(lang: str) -> None:
    global _CURRENT_LANG
    if lang not in MESSAGES_GUI:
        raise ValueError(
            f"i18n_gui: unsupported language {lang!r} "
            f"(supported: {sorted(MESSAGES_GUI.keys())})"
        )
    _CURRENT_LANG = lang


def tg(key: str, **kwargs: Any) -> str:
    """GUI 字符串取当前语言,支持 {name} 占位符(同 t())。"""
    msg = MESSAGES_GUI[_CURRENT_LANG].get(key)
    if msg is None:
        other = "en" if _CURRENT_LANG == "zh" else "zh"
        if key in MESSAGES_GUI[other]:
            raise KeyError(
                f"i18n_gui: missing key {key!r} in {_CURRENT_LANG!r} "
                f"(present in {other!r})"
            )
        raise KeyError(f"i18n_gui: missing key {key!r} in any language")
    if kwargs:
        return msg.format(**kwargs)
    return msg


def supported_keys() -> List[str]:
    return sorted(MESSAGES_GUI["zh"].keys())
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_i18n.py -v
```
预期: 6 passed

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/i18n_gui.py inp_tool/tests/test_gui_i18n.py
git commit -m "feat(gui): add i18n_gui module with zh/en string dict for GUI"
```

---

## Task 2: 创建字段说明字典(field_help)

**Files:**
- Create: `inp_tool/inp_tool/field_help.py`
- Create: `inp_tool/tests/test_field_help.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_field_help.py
from inp_tool.field_help import get_help, known_blocks, known_keywords


def test_get_help_known_field():
    help_zh = get_help("physics", "reftem")
    assert "温度" in help_zh


def test_get_help_unknown_field_returns_empty():
    assert get_help("nonexistent_block", "x") == ""
    assert get_help("physics", "nonexistent_keyword") == ""


def test_known_blocks_includes_physics():
    assert "physics" in known_blocks()


def test_known_keywords_physics_block():
    keys = known_keywords("physics")
    assert "reftem" in keys
    assert "reynolds" in keys


def test_help_text_length_reasonable():
    for block, kw in [("physics", "reftem"), ("guiopts", "aero_ma"),
                      ("guiopts", "aero_alpha"), ("guiopts", "aero_beta")]:
        text = get_help(block, kw)
        assert 0 < len(text) <= 200
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_field_help.py -v
```
预期: `ModuleNotFoundError`

- [ ] **Step 3: 实现 field_help.py**

```python
# inp_tool/inp_tool/field_help.py
"""mcfd.inp 字段含义字典(中文)。

约定:
    帮助文本面向 CFD 工程师,简明扼要(≤ 200 字)。
    不在字典中的字段返回空串 → UI 上不显示 tooltip。
"""
from typing import Dict, Tuple

FIELD_HELP: Dict[str, Dict[str, str]] = {
    "physics": {
        "reftem": "参考温度(K)。无量纲化用,典型值 288.15 或 300.0。",
        "reynolds": "参考雷诺数。基于 Lref 与参考粘性系数。",
        "gammat": "湍流模型 gamma 系数(SST k-ω 默认 5/9)。",
    },
    "guiopts": {
        "aero_ma": "来流马赫数 Ma。0.3 以下不可压,0.3-0.8 跨声速,>1 超声速。",
        "aero_alpha": "迎角(度)。正值为抬头。",
        "aero_beta": "侧滑角(度)。对称工况通常为 0。",
        "aero_temp": "来流静温(K)。",
        "aero_pres": "来流静压(Pa)。",
        "aero_Re": "来流雷诺数(基于 Lref)。",
    },
    "chemistry": {
        "model": "气体模型。常见:air5, air7, n2, o2, 11species_air。",
    },
    "turbulence": {
        "model": "湍流模型关键字,如 komega, sst, sa。",
    },
    "equation": {
        "energy": "能量方程开关。.true. 开启, .false. 关闭。",
        "turbulence": "湍流方程开关。",
        "chemistry": "组分输运开关。",
        "two_temperature": "双温度模型开关(电子温度独立求解)。",
    },
    "output": {
        "frequency": "输出频率(步数)。每 N 步写一次结果。",
    },
    "iteration": {
        "max_iter": "最大迭代步数。",
        "cfl": "CFL 数。显式格式典型 1-5。",
    },
    "grid": {
        "filename": "网格文件名(相对路径)。",
    },
}


def get_help(block: str, keyword: str) -> str:
    """取某 block.keyword 的中文说明;无记录返回空串。"""
    block_dict = FIELD_HELP.get(block)
    if not block_dict:
        return ""
    return block_dict.get(keyword, "")


def known_blocks() -> Tuple[str, ...]:
    return tuple(FIELD_HELP.keys())


def known_keywords(block: str) -> Tuple[str, ...]:
    block_dict = FIELD_HELP.get(block, {})
    return tuple(block_dict.keys())
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_field_help.py -v
```
预期: 5 passed

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/field_help.py inp_tool/tests/test_field_help.py
git commit -m "feat(gui): add field_help dictionary for known inp keywords"
```

---

## Task 3: 创建树形搜索框组件

**Files:**
- Create: `inp_tool/inp_tool_gui/widgets/field_search_bar.py`
- Create: `inp_tool/tests/test_gui_field_search.py`

- [ ] **Step 1: 写失败的测试**

```python
# tests/test_gui_field_search.py
import pytest
from PySide2.QtWidgets import QApplication, QTreeWidget, QTreeWidgetItem
from inp_tool_gui.widgets.field_search_bar import FieldSearchBar


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_filter_hides_non_matching(qapp):
    tree = QTreeWidget()
    tree.setHeaderLabels(["字段"])
    parent = QTreeWidgetItem(["physics"])
    a = QTreeWidgetItem(["reftem"])
    b = QTreeWidgetItem(["reynolds"])
    parent.addChild(a)
    parent.addChild(b)
    tree.addTopLevelItem(parent)

    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reftem")
    assert not a.isHidden()
    assert b.isHidden()


def test_filter_substring_match(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["reftem"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reft")
    assert not a.isHidden()


def test_filter_empty_shows_all(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    b = QTreeWidgetItem(["y"])
    tree.addTopLevelItem(a)
    tree.addTopLevelItem(b)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("")
    assert not a.isHidden()
    assert not b.isHidden()


def test_filter_shows_parents_of_matches(qapp):
    tree = QTreeWidget()
    parent = QTreeWidgetItem(["physics"])
    child = QTreeWidgetItem(["reftem"])
    parent.addChild(child)
    tree.addTopLevelItem(parent)

    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("reftem")
    assert not child.isHidden()
    assert not parent.isHidden()


def test_clear_resets(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    bar.attach(tree)
    bar.set_query("zzz")
    assert a.isHidden()
    bar.set_query("")
    assert not a.isHidden()


def test_no_match_count_signal(qapp):
    tree = QTreeWidget()
    a = QTreeWidgetItem(["x"])
    tree.addTopLevelItem(a)
    bar = FieldSearchBar()
    received = []
    bar.match_count_changed.connect(lambda n: received.append(n))
    bar.attach(tree)
    bar.set_query("zzz")
    assert 0 in received
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_field_search.py -v
```
预期: `ModuleNotFoundError`

- [ ] **Step 3: 实现 field_search_bar.py**

```python
# inp_tool/inp_tool_gui/widgets/field_search_bar.py
"""FieldSearchBar:挂在 :class:`QTreeWidget` 顶部的搜索框,实时过滤 item。

行为:
- 输入文本 → 所有 item 的 text(0) 做子串匹配
- 匹配项 setHidden(False);不匹配的 setHidden(True)
- 父节点:若有任一子项匹配,父节点也保持可见
- 清空 → 全部显示
- emit ``match_count_changed(int)``:当前可见 item 数
"""
from typing import Optional

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from inp_tool.i18n_gui import tg


class FieldSearchBar(QWidget):
    """树形搜索框。"""

    match_count_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tree: Optional[QTreeWidget] = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(tg("tree.search.placeholder"))
        self._edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._edit, 1)

        self._btn_clear = QPushButton(tg("tree.search.btn_clear"), self)
        self._btn_clear.clicked.connect(self._edit.clear)
        layout.addWidget(self._btn_clear)

    def attach(self, tree: QTreeWidget) -> None:
        """绑定一棵要过滤的树。"""
        self._tree = tree

    def set_query(self, text: str) -> None:
        """程序化设置搜索词(测试用,等同用户在编辑框输入)。"""
        self._edit.setText(text)

    def _on_text_changed(self, text: str) -> None:
        if self._tree is None:
            return
        text_lower = text.lower()
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            self._filter_item(top, text_lower)

        visible = self._count_visible(self._tree)
        self.match_count_changed.emit(visible)

    def _filter_item(self, item: QTreeWidgetItem, text_lower: str) -> bool:
        own_match = text_lower in item.text(0).lower() if text_lower else True
        any_child_visible = False
        for i in range(item.childCount()):
            child = item.child(i)
            child_visible = self._filter_item(child, text_lower)
            any_child_visible = any_child_visible or child_visible

        visible = own_match or any_child_visible
        item.setHidden(not visible)
        return visible

    def _count_visible(self, tree: QTreeWidget) -> int:
        n = 0

        def walk(item: QTreeWidgetItem) -> None:
            nonlocal n
            if not item.isHidden():
                n += 1
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(tree.topLevelItemCount()):
            walk(tree.topLevelItem(i))
        return n
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_field_search.py -v
```
预期: 6 passed

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool_gui/widgets/field_search_bar.py \
        inp_tool/tests/test_gui_field_search.py
git commit -m "feat(gui): add FieldSearchBar with recursive tree filter"
```

---

## Task 4: 把搜索框 + field_help 接入 InpTreeWidget

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/inp_tree.py`
- Modify: `inp_tool/inp_tool/tests/test_gui_inp_tree.py`(补测试)

- [ ] **Step 1: 写失败的测试 — tooltip 已挂载**

```python
# 加到 tests/test_gui_inp_tree.py 末尾
from inp_tool.model import InpFile, Block, Statement, Value
from PySide2.QtCore import Qt


def test_value_item_has_tooltip_from_field_help(qapp):
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget
    inp = InpFile()
    inp.top_stmts.append(
        Statement(keyword="reftem", values=[Value(raw="300.0", typed=300.0)])
    )
    tree = InpTreeWidget()
    tree.populate(inp)
    top = tree.topLevelItem(0)  # "顶层语句"
    stmt_item = top.child(0)
    value_item = stmt_item.child(0)
    tip = value_item.toolTip(0)
    assert "温度" in tip  # field_help 里 reftem 的说明


def test_value_item_no_tooltip_for_unknown_field(qapp):
    from inp_tool_gui.widgets.inp_tree import InpTreeWidget
    inp = InpFile()
    inp.top_stmts.append(
        Statement(keyword="zzz_unknown_xxx", values=[Value(raw="1.0", typed=1.0)])
    )
    tree = InpTreeWidget()
    tree.populate(inp)
    top = tree.topLevelItem(0)
    stmt_item = top.child(0)
    value_item = stmt_item.child(0)
    assert value_item.toolTip(0) == ""  # 无说明 → 无 tooltip
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_inp_tree.py -v
```
预期: 2 个新测试失败

- [ ] **Step 3: 修改 inp_tree.py**

在 `inp_tree.py` 文件头部增加导入:

```python
# 头部新增
from inp_tool.field_help import get_help
from inp_tool.i18n_gui import tg
```

修改 `_make_value_item` 增加 tooltip:

```python
def _make_value_item(
    self,
    block_idx: int,
    stmt_idx: int,
    value_idx: int,
    keyword: str,
    value: Any,
    block_name: str = "",   # 新增参数
) -> QTreeWidgetItem:
    raw = getattr(value, "raw", str(value))
    item = QTreeWidgetItem([raw, "value", raw])
    item.setData(
        0,
        Qt.UserRole,
        (_VALUE_ROLE, block_idx, stmt_idx, value_idx, keyword),
    )
    # v0.16:接 field_help,挂 tooltip
    help_text = get_help(block_name, keyword) if block_name else ""
    if help_text:
        tip = f"{block_name}.{keyword}\n{help_text}"
        for col in range(3):
            item.setToolTip(col, tip)
    return item
```

修改 `populate` 把 block_name 传进去 + 替换硬编码标签:

```python
def populate(self, inp: InpFile) -> None:
    self.clear()
    self._inp = inp
    # 顶层语句父节点
    top_parent = QTreeWidgetItem([tg("tree.lbl.top")])
    top_parent.setData(0, Qt.UserRole, (_PARENT_ROLE, "top"))
    self.addTopLevelItem(top_parent)
    for stmt_idx, stmt in enumerate(inp.top_stmts):
        stmt_item = self._make_stmt_item(-1, stmt_idx, stmt.keyword)
        top_parent.addChild(stmt_item)
        for vi, v in enumerate(stmt.values):
            stmt_item.addChild(
                self._make_value_item(-1, stmt_idx, vi, stmt.keyword, v,
                                      block_name="<top>")
            )
    # 块父节点
    blk_parent = QTreeWidgetItem([tg("tree.lbl.blocks")])
    blk_parent.setData(0, Qt.UserRole, (_PARENT_ROLE, "blocks"))
    self.addTopLevelItem(blk_parent)
    for blk_idx, block in enumerate(inp.block_list):
        label = self._block_label(blk_idx, block.name)
        blk_item = QTreeWidgetItem([label])
        blk_item.setData(0, Qt.UserRole, (_BLOCK_ROLE, blk_idx, block.name))
        blk_parent.addChild(blk_item)
        for stmt_idx, stmt in enumerate(block.statements):
            stmt_item = self._make_stmt_item(blk_idx, stmt_idx, stmt.keyword)
            blk_item.addChild(stmt_item)
            for vi, v in enumerate(stmt.values):
                stmt_item.addChild(
                    self._make_value_item(blk_idx, stmt_idx, vi, stmt.keyword, v,
                                          block_name=block.name)
                )
    self.expandAll()
```

替换硬编码标签 `_LBL_TOP` / `_LBL_BLOCKS`:

```python
# 删除
# _LBL_TOP = "顶层语句"
# _LBL_BLOCKS = "块"

# 改为(保留作为属性,值来自 i18n 实时取)
def _lbl_top(self) -> str:
    return tg("tree.lbl.top")

def _lbl_blocks(self) -> str:
    return tg("tree.lbl.blocks")
```

把内部所有 `self._LBL_TOP` 引用改为 `self._lbl_top()`,所有 `self._LBL_BLOCKS` 引用改为 `self._lbl_blocks()`(位置:`_walk_to_value_item`, `_find_top_by_label`, `_locate`)。

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_inp_tree.py -v
```
预期: 全部通过(含原有 + 2 个新增)

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool_gui/widgets/inp_tree.py \
        inp_tool/tests/test_gui_inp_tree.py
git commit -m "feat(gui): wire field_help tooltips and i18n labels into InpTreeWidget"
```

---

## Task 5: SweepController 增加 update_field + 实时表单

**Files:**
- Modify: `inp_tool/inp_tool_gui/controllers/sweep_controller.py`
- Create: `inp_tool/inp_tool_gui/widgets/sweep_live_form.py`
- Create: `inp_tool/tests/test_gui_sweep_live_form.py`

- [ ] **Step 1: 写失败的测试 — SweepController.update_field**

```python
# tests/test_gui_sweep_live_form.py
from inp_tool_gui.controllers.sweep_controller import SweepController
import pytest


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
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_sweep_live_form.py -v
```
预期: `AttributeError`

- [ ] **Step 3: 修改 sweep_controller.py — 追加 update_field 方法**

在 `SweepController` 类末尾追加:

```python
    # --- 实时编辑(实时表单用)----------------------------------------

    def update_field(self, key: str, value: Any) -> None:
        """实时修改某个字段并重新构造内部 CaseSweep。

        支持的 key:
            - "template" / "output_dir" / "naming" / "naming_ext"
            - "source_dir" / "copy_strategy" / "exclude"
            - "sweeps.<axis>"    单个 axis 值
            - "sweeps_dict"      整个 sweeps dict 替换

        Raises:
            KeyError: 未知 key
            RuntimeError: 未 load 配置
        """
        if self._sweep is None:
            raise RuntimeError("未 load sweep 配置,无法 update_field")

        # 从当前 CaseSweep 反构 dict(走 to_dict;若不存在则手写)
        d = _sweep_to_dict(self._sweep)

        if "." in key:
            head, _, tail = key.partition(".")
            if head == "sweeps":
                d.setdefault("sweeps", {})[tail] = value
            else:
                raise KeyError(f"不支持的复合字段 {key!r}")
        else:
            if key in ("template", "output_dir", "naming", "naming_ext",
                       "source_dir", "copy_strategy", "exclude"):
                d[key] = value
            elif key == "sweeps_dict":
                d["sweeps"] = dict(value)
            else:
                raise KeyError(f"未知字段 {key!r}")

        self._sweep = CaseSweep.from_dict(d)
        self._last_report = None
```

在文件底部(模块级)添加辅助:

```python
def _sweep_to_dict(cs: CaseSweep) -> Dict[str, Any]:
    """把 CaseSweep 实例转回 dict,供 update_field 改写后重建。"""
    # 优先用 CaseSweep 自带 to_dict
    if hasattr(cs, "to_dict") and callable(cs.to_dict):
        return cs.to_dict()
    # 兜底:从 dataclass 字段拼
    from dataclasses import asdict
    d = asdict(cs)
    # asdict 会把 enum 转为 enum 实例,from_dict 期望字符串;copy_strategy 特判
    if "copy_strategy" in d and hasattr(d["copy_strategy"], "value"):
        d["copy_strategy"] = d["copy_strategy"].value
    return d
```

- [ ] **Step 4: 实现 sweep_live_form.py**

```python
# inp_tool/inp_tool_gui/widgets/sweep_live_form.py
"""SweepLiveForm:实时编辑 sweep 配置的表单(v0.16 新增)。"""
from typing import Optional, Dict, List

from PySide2.QtCore import Qt
from PySide2.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool_gui.controllers.sweep_controller import SweepController
from inp_tool.i18n_gui import tg


class SweepLiveForm(QWidget):
    """Sweep 实时编辑表单。"""

    def __init__(
        self,
        sweep_ctrl: SweepController,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._sweep_ctrl = sweep_ctrl
        self._build_ui()
        self._sync_from_controller()

    def sync_from_controller(self) -> None:
        """从 controller 拉取最新 dict,刷新表单(供外部修改后回灌)。"""
        self._sync_from_controller()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # 模板路径
        tpl_row = QHBoxLayout()
        self._edit_tpl = QLineEdit(self)
        self._edit_tpl.editingFinished.connect(self._on_sync)
        self._btn_tpl = QPushButton("浏览...", self)
        self._btn_tpl.clicked.connect(self._pick_template)
        tpl_row.addWidget(self._edit_tpl, 1)
        tpl_row.addWidget(self._btn_tpl)
        root.addLayout(tpl_row)

        # 输出目录
        out_row = QHBoxLayout()
        self._edit_out = QLineEdit(self)
        self._edit_out.editingFinished.connect(self._on_sync)
        self._btn_out = QPushButton("浏览...", self)
        self._btn_out.clicked.connect(self._pick_output)
        out_row.addWidget(self._edit_out, 1)
        out_row.addWidget(self._btn_out)
        root.addLayout(out_row)

        # naming
        self._edit_naming = QLineEdit(self)
        self._edit_naming.editingFinished.connect(self._on_sync)
        root.addWidget(self._edit_naming)

        # Sweep 轴表
        axes_box = QGroupBox(tg("sweep.title.sweeps_axes"), self)
        axes_layout = QVBoxLayout(axes_box)
        self._axes_table = QTableWidget(0, 2, self)
        self._axes_table.setHorizontalHeaderLabels(["轴名", "值列表(逗号分隔)"])
        self._axes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        axes_layout.addWidget(self._axes_table)
        self._btn_add_axis = QPushButton("添加轴", self)
        self._btn_add_axis.clicked.connect(self._add_axis_row)
        axes_layout.addWidget(self._btn_add_axis)
        root.addWidget(axes_box, 1)

        # 同步状态
        self._lbl_status = QLabel("", self)
        root.addWidget(self._lbl_status)

        # 保存为 YAML
        self._btn_save_yaml = QPushButton(tg("sweep.btn.save_config"), self)
        self._btn_save_yaml.clicked.connect(self._save_yaml)
        root.addWidget(self._btn_save_yaml)

    def _sync_from_controller(self) -> None:
        if not self._sweep_ctrl.is_loaded:
            return
        self._edit_tpl.blockSignals(True)
        self._edit_out.blockSignals(True)
        self._edit_naming.blockSignals(True)
        self._edit_tpl.setText(self._sweep_ctrl.template or "")
        out = getattr(self._sweep_ctrl._sweep, "output_dir", "")
        self._edit_out.setText(str(out) if out else "")
        naming = getattr(self._sweep_ctrl._sweep, "naming", "")
        self._edit_naming.setText(str(naming) if naming else "")
        sweeps = self._sweep_ctrl._sweep.sweeps
        self._axes_table.setRowCount(0)
        for k, v in sweeps.values.items():
            self._append_axis_row(k, v)
        self._edit_tpl.blockSignals(False)
        self._edit_out.blockSignals(False)
        self._edit_naming.blockSignals(False)

    def _collect_to_dict(self) -> Dict:
        if not self._edit_tpl.text().strip():
            raise ValueError(tg("sweep.live.need_template"))
        if not self._edit_out.text().strip():
            raise ValueError(tg("sweep.live.need_output"))
        sweeps_dict: Dict[str, List] = {}
        for r in range(self._axes_table.rowCount()):
            key_item = self._axes_table.item(r, 0)
            val_item = self._axes_table.item(r, 1)
            if not key_item or not val_item:
                continue
            key = key_item.text().strip()
            if not key:
                continue
            raw = val_item.text().strip()
            try:
                vals: List = [_parse_scalar(x) for x in raw.split(",") if x.strip()]
            except ValueError as e:
                raise ValueError(tg("sweep.live.invalid_axis", key=key, val=raw)) from e
            sweeps_dict[key] = vals
        return {
            "template": self._edit_tpl.text().strip(),
            "output_dir": self._edit_out.text().strip(),
            "naming": self._edit_naming.text().strip() or "case",
            "sweeps": sweeps_dict,
        }

    def _on_sync(self) -> None:
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            self._lbl_status.setText(str(e))
            return
        try:
            self._sweep_ctrl.load_from_dict(d)
            self._lbl_status.setText(tg("sweep.live.sync_ok"))
        except Exception as e:
            self._lbl_status.setText(tg("sweep.live.sync_fail", err=str(e)))

    def _save_yaml(self) -> None:
        try:
            d = self._collect_to_dict()
        except ValueError as e:
            QMessageBox.warning(self, tg("sweep.btn.save_config"), str(e))
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tg("sweep.btn.save_config"), "sweep.yaml",
            "YAML (*.yaml *.yml);;所有文件 (*)"
        )
        if not path:
            return
        import yaml
        try:
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(d, f, allow_unicode=True, sort_keys=False)
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))
            return
        self._lbl_status.setText(f"已保存:{path}")

    def _pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tg("sweep.lbl.template"), "", "mcfd.inp (*.inp)"
        )
        if path:
            self._edit_tpl.setText(path)
            self._on_sync()

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tg("sweep.lbl.output"))
        if path:
            self._edit_out.setText(path)
            self._on_sync()

    def _add_axis_row(self) -> None:
        self._append_axis_row("", "")

    def _append_axis_row(self, key: str, val) -> None:
        r = self._axes_table.rowCount()
        self._axes_table.insertRow(r)
        self._axes_table.setItem(r, 0, QTableWidgetItem(key))
        if isinstance(val, list):
            text = ", ".join(str(x) for x in val)
        else:
            text = str(val) if val is not None else ""
        self._axes_table.setItem(r, 1, QTableWidgetItem(text))
        self._axes_table.itemChanged.connect(lambda *_: self._on_sync())


def _parse_scalar(s: str):
    s = s.strip()
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s
```

- [ ] **Step 5: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_sweep_live_form.py -v
```
预期: 5 passed(controller 测试)

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool_gui/controllers/sweep_controller.py \
        inp_tool/inp_tool_gui/widgets/sweep_live_form.py \
        inp_tool/tests/test_gui_sweep_live_form.py
git commit -m "feat(gui): add SweepLiveForm for real-time sweep config editing"
```

---

## Task 6: 打开模式对话框 + FileController 文件夹模式

**Files:**
- Create: `inp_tool/inp_tool_gui/widgets/open_mode_dialog.py`
- Modify: `inp_tool/inp_tool_gui/controllers/file_controller.py`
- Create: `inp_tool/tests/test_gui_open_mode.py`

- [ ] **Step 1: 写失败的测试**

```python
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
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_open_mode.py -v
```
预期: 全部失败(模块不存在)

- [ ] **Step 3: 实现 open_mode_dialog.py**

```python
# inp_tool/inp_tool_gui/widgets/open_mode_dialog.py
"""OpenModeDialog:选择打开方式的弹窗(文件/文件夹)。

默认 folder 模式。
"""
from enum import Enum
from typing import Optional

from PySide2.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg


class Mode(str, Enum):
    FILE = "file"
    FOLDER = "folder"


class OpenModeDialog(QDialog):
    """打开方式选择弹窗。"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tg("open_mode.title"))

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tg("open_mode.label"), self))

        self._radio_file = QRadioButton(tg("open_mode.file_radio"), self)
        self._radio_folder = QRadioButton(tg("open_mode.folder_radio"), self)
        self._radio_folder.setChecked(True)
        layout.addWidget(self._radio_file)
        layout.addWidget(self._radio_folder)

        self._hint = QLabel(tg("open_mode.folder_hint"), self)
        self._hint.setStyleSheet("color: gray;")
        layout.addWidget(self._hint)

        self._chk_remember = QCheckBox(tg("open_mode.remember"), self)
        layout.addWidget(self._chk_remember)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        btns.button(QDialogButtonBox.Ok).setText(tg("open_mode.ok"))
        btns.button(QDialogButtonBox.Cancel).setText(tg("open_mode.cancel"))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_mode(self) -> Mode:
        return Mode.FOLDER if self._radio_folder.isChecked() else Mode.FILE

    def remember_choice(self) -> bool:
        return self._chk_remember.isChecked()
```

- [ ] **Step 4: 修改 file_controller.py — 增加 open_case_dir + CaseValidation**

在 `FileController` 顶部加 import + dataclass,以及新方法:

```python
# 新增 import
from dataclasses import dataclass, field
from typing import List

from inp_tool import parser  # 已有


@dataclass
class CaseValidationIssue:
    code: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class CaseValidation:
    ok: bool
    issues: List[CaseValidationIssue] = field(default_factory=list)


class CaseValidationError(Exception):
    """算例目录不完整时抛的异常。"""

    def __init__(self, validation: CaseValidation) -> None:
        self.validation = validation
        msgs = [f"[{i.code}] {i.message}" for i in validation.issues
                if i.severity == "error"]
        super().__init__("算例完整性检查失败:\n" + "\n".join(msgs))


class FileController:
    def __init__(self) -> None:
        self._inp: Optional[InpFile] = None
        self._path: Optional[Path] = None
        self._case_dir: Optional[Path] = None
        self._case_validation: Optional[CaseValidation] = None

    @property
    def current_case_dir(self) -> Optional[Path]:
        return self._case_dir

    @property
    def case_validation(self) -> Optional[CaseValidation]:
        return self._case_validation

    def open_case_dir(self, path) -> InpFile:
        """打开一个完整算例目录(必须是含 mcfd.inp 的目录)。"""
        p = Path(path)
        if not p.is_dir():
            raise CaseValidationError(CaseValidation(
                ok=False, issues=[
                    CaseValidationIssue(
                        "not_a_dir", f"{p} 不是目录", "error"),
                ]))
        validation = self._validate_case_dir(p)
        errors = [i for i in validation.issues if i.severity == "error"]
        if errors:
            raise CaseValidationError(validation)
        try:
            self._inp = parser.parse_file(str(p / "mcfd.inp"))
        except Exception as e:
            validation.issues.append(CaseValidationIssue(
                "parse_error", str(e), "error"))
            raise CaseValidationError(validation)
        self._path = p / "mcfd.inp"
        self._case_dir = p
        self._case_validation = validation
        return self._inp

    def _validate_case_dir(self, p: Path) -> CaseValidation:
        issues: List[CaseValidationIssue] = []
        inp_path = p / "mcfd.inp"
        if not inp_path.is_file():
            issues.append(CaseValidationIssue(
                "missing_inp", "缺少 mcfd.inp", "error"))
        pbs = list(p.glob("*.pbs"))
        if not pbs:
            issues.append(CaseValidationIssue(
                "missing_pbs", "缺少 PBS 脚本", "warning"))
        geom_files = list(p.glob("*.tri")) + list(p.glob("*.plt"))
        if not geom_files:
            issues.append(CaseValidationIssue(
                "missing_geometry", "缺少几何文件", "warning"))
        return CaseValidation(
            ok=not any(i.severity == "error" for i in issues),
            issues=issues,
        )
```

- [ ] **Step 5: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_open_mode.py -v
```
预期: 5 passed

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool_gui/widgets/open_mode_dialog.py \
        inp_tool/inp_tool_gui/controllers/file_controller.py \
        inp_tool/tests/test_gui_open_mode.py
git commit -m "feat(gui): add OpenModeDialog + FileController.open_case_dir"
```

---

## Task 7: 把 4 大特性接入 MainWindow

**Files:**
- Modify: `inp_tool/inp_tool_gui/main_window.py`
- Modify: `inp_tool/inp_tool/tests/test_gui_main_window_integration.py`(补 4 个新断言)

- [ ] **Step 1: 写失败的集成测试**

```python
# 加到 tests/test_gui_main_window_integration.py
import pytest
from pathlib import Path
from PySide2.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_has_search_bar_above_tree(qapp):
    from inp_tool_gui.main_window import MainWindow
    from inp_tool_gui.widgets.field_search_bar import FieldSearchBar
    win = MainWindow()
    assert len(win.findChildren(FieldSearchBar)) >= 1


def test_main_window_has_sweep_live_tab(qapp):
    from inp_tool_gui.main_window import MainWindow
    win = MainWindow()
    tab_titles = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    # 找到 Sweep 容器,里面有 File/Live 两个子 tab
    sweep_idx = None
    for i in range(win.tabs.count()):
        if "Sweep" in win.tabs.tabText(i) or "sweep" in win.tabs.tabText(i).lower():
            sweep_idx = i
            break
    assert sweep_idx is not None
    sweep_container = win.tabs.widget(sweep_idx)
    sub_titles = [sweep_container.tabText(j) for j in range(sweep_container.count())]
    assert any("实时" in t or "Live" in t for t in sub_titles)
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_main_window_integration.py -v
```
预期: 2 个新测试失败

- [ ] **Step 3: 修改 main_window.py**

替换所有硬编码中文(且不在 i18n_gui 字典里的)→ `tg()`。关键 diff:

```python
# 头部新增
from inp_tool.i18n_gui import tg
from inp_tool_gui.widgets.field_search_bar import FieldSearchBar
from inp_tool_gui.widgets.open_mode_dialog import OpenModeDialog, Mode
from inp_tool_gui.widgets.sweep_live_form import SweepLiveForm
from inp_tool_gui.controllers.file_controller import CaseValidationError


# 替换 setup_actions:
def _setup_actions(self) -> None:
    self.act_open = QAction(tg("act.open"), self)
    self.act_open.setShortcut(QKeySequence.Open)
    self.act_open.triggered.connect(self._on_open)

    self.act_save = QAction(tg("act.save"), self)
    self.act_save.setShortcut(QKeySequence.Save)
    self.act_save.triggered.connect(self._on_save)

    self.act_save_as = QAction(tg("act.save_as"), self)
    self.act_save_as.setShortcut(QKeySequence.SaveAs)
    self.act_save_as.triggered.connect(self._on_save_as)

    self.act_exit = QAction(tg("act.exit"), self)
    self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
    self.act_exit.triggered.connect(self.close)

    self.act_undo = QAction(tg("act.undo"), self)
    self.act_undo.setShortcut(QKeySequence.Undo)
    self.act_undo.triggered.connect(self._on_undo)

    self.act_redo = QAction(tg("act.redo"), self)
    self.act_redo.setShortcut(QKeySequence.Redo)
    self.act_redo.triggered.connect(self._on_redo)

    self.act_sweep = QAction(tg("act.sweep"), self)
    self.act_sweep.triggered.connect(self._on_sweep_action)

    self.act_detect = QAction(tg("act.detect"), self)
    self.act_detect.triggered.connect(self._on_detect_action)


# 替换 setup_menus
def _setup_menus(self) -> None:
    menubar = self.menuBar()
    m_file = menubar.addMenu(tg("menu.file"))
    m_file.addAction(self.act_open)
    m_file.addAction(self.act_save)
    m_file.addAction(self.act_save_as)
    m_file.addSeparator()
    m_file.addAction(self.act_exit)

    m_edit = menubar.addMenu(tg("menu.edit"))
    m_edit.addAction(self.act_undo)
    m_edit.addAction(self.act_redo)

    m_sweep = menubar.addMenu(tg("menu.sweep"))
    m_sweep.addAction(self.act_sweep)

    m_detect = menubar.addMenu(tg("menu.detect"))
    m_detect.addAction(self.act_detect)

    m_help = menubar.addMenu(tg("menu.help"))
    m_help.addAction(tg("act.about")).triggered.connect(self._on_about)


# 替换 setup_statusbar
def _setup_statusbar(self) -> None:
    bar = QStatusBar(self)
    self.setStatusBar(bar)
    self._status_path = QLabel(tg("status.no_file"))
    self._status_dirty = QLabel("")
    self._status_lines = QLabel("0 行")
    bar.addWidget(self._status_path, 1)
    bar.addPermanentWidget(self._status_dirty)
    bar.addPermanentWidget(self._status_lines)


# 替换 setup_central
def _setup_central(self) -> None:
    self.tabs = QTabWidget(self)
    self.tabs.setObjectName("CentralTabs")

    # v0.16:文件 tab = 搜索框 + InpTree
    from PySide2.QtWidgets import QVBoxLayout
    file_widget = QWidget(self)
    file_layout = QVBoxLayout(file_widget)
    file_layout.setContentsMargins(0, 0, 0, 0)
    self._search_bar = FieldSearchBar(file_widget)
    file_layout.addWidget(self._search_bar)
    self.tree_widget = InpTreeWidget(file_widget)
    self.tree_widget.value_edit_requested.connect(self._on_value_edit_requested)
    file_layout.addWidget(self.tree_widget, 1)
    self._search_bar.attach(self.tree_widget)
    self.tabs.addTab(file_widget, tg("tab.file"))

    self.detect_panel = DetectPanel(self.detect_ctrl, self.edit_ctrl, self)
    self.detect_panel.preset_requested.connect(self._on_preset_requested)
    self.tabs.addTab(self.detect_panel, tg("tab.detect"))

    # v0.16:Sweep tab 改为 QTabWidget 子 tab
    sweep_container = QTabWidget(self)
    self.sweep_form = SweepForm(self.sweep_ctrl, sweep_container)
    sweep_container.addTab(self.sweep_form, tg("tab.sweep"))
    self.sweep_live_form = SweepLiveForm(self.sweep_ctrl, sweep_container)
    sweep_container.addTab(self.sweep_live_form, tg("tab.sweep_live"))
    self.tabs.addTab(sweep_container, tg("tab.sweep"))

    self.diff_viewer = DiffViewer(self.diff_ctrl, self)
    self.tabs.addTab(self.diff_viewer, tg("tab.diff"))

    from inp_tool_gui.controllers.postprocess_controller import PostprocessController
    from inp_tool_gui.widgets.postprocess_panel import PostprocessPanel
    self.postprocess_ctrl = PostprocessController()
    self.postprocess_panel = PostprocessPanel(self)
    self.postprocess_panel.run_requested.connect(self._on_postprocess_run)
    self.tabs.addTab(self.postprocess_panel, tg("tab.postprocess"))

    self.setCentralWidget(self.tabs)


# 替换 _on_open
def _on_open(self) -> None:
    dlg = OpenModeDialog(self)
    if dlg.exec_() != OpenModeDialog.Accepted:
        return
    mode = dlg.selected_mode()

    if mode == Mode.FOLDER:
        path = QFileDialog.getExistingDirectory(self, tg("dialog.open_title"))
        if not path:
            return
        try:
            self.file_ctrl.open_case_dir(path)
        except CaseValidationError as e:
            QMessageBox.critical(
                self, tg("case_check.title"),
                f"算例目录不完整:\n{str(e)}\n\n"
                "提示:可改用 文件模式 打开 mcfd.inp")
            return
        except Exception as exc:
            QMessageBox.critical(self, tg("dialog.open_failed_title"),
                                 f"无法解析:\n{exc}")
            return
        # 显示完整性检查结果
        v = self.file_ctrl.case_validation
        if v is not None:
            msg_lines = [tg("case_check.ok")] if v.ok else ["算例不完整"]
            for issue in v.issues:
                key = f"case_check.{issue.code}"
                try:
                    msg_lines.append(tg(key))
                except KeyError:
                    msg_lines.append(f"[{issue.severity}] {issue.message}")
            QMessageBox.information(
                self, tg("case_check.title"), "\n".join(msg_lines))
    else:
        path, _ = QFileDialog.getOpenFileName(
            self, tg("dialog.open_title"), str(Path.cwd()),
            tg("dialog.open_inp_filter"))
        if not path:
            return
        try:
            self.file_ctrl.open(path)
        except Exception as exc:
            QMessageBox.critical(self, tg("dialog.open_failed_title"),
                                 f"无法解析 {path}:\n{exc}")
            return

    self.edit_ctrl.mark_clean()
    self._refresh_after_open()


# 替换 _refresh_after_open
def _refresh_after_open(self) -> None:
    path = self.file_ctrl.current_path
    self._status_path.setText(str(path) if path else tg("status.no_file"))
    if path and path.exists():
        try:
            with open(str(path), "r", encoding="utf-8", errors="replace") as f:
                n_lines = sum(1 for _ in f)
            self._status_lines.setText(f"{n_lines} 行")
        except OSError:
            self._status_lines.setText("0 行")
    if self.file_ctrl.inp is not None:
        self.tree_widget.populate(self.file_ctrl.inp)
        self.detect_panel.run(self.file_ctrl.inp)
        self.tabs.setCurrentWidget(self.tree_widget)
    self._update_title()
    self._update_actions_enabled()
```

- [ ] **Step 4: 跑全部 GUI 测试,确认 GREEN**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_main_window_integration.py \
                                       tests/test_gui_inp_tree.py \
                                       tests/test_gui_open_mode.py \
                                       tests/test_gui_field_search.py \
                                       tests/test_gui_sweep_live_form.py \
                                       tests/test_gui_i18n.py -v
```
预期: 全部通过

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool_gui/main_window.py \
        inp_tool/tests/test_gui_main_window_integration.py
git commit -m "feat(gui): wire search bar, sweep live form, open mode dialog into MainWindow"
```

---

## Task 8: 跑全套测试 + 覆盖率

**Files:** 无新增,只跑测试。

- [ ] **Step 1: 跑 inp_tool 全部测试**

```bash
conda run -n cfdchanger python -m pytest tests/ -v --tb=short
```
预期: 全部 PASS

- [ ] **Step 2: 跑 GUI 单独覆盖率**

```bash
conda run -n cfdchanger python -m pytest tests/test_gui_*.py tests/test_field_help.py \
  --cov=inp_tool_gui --cov=inp_tool.i18n_gui --cov=inp_tool.field_help \
  --cov-report=term-missing --cov-fail-under=80
```
预期: 覆盖率 ≥ 80%

- [ ] **Step 3: 手动 smoke test**

```bash
conda run -n cfdchanger python -m inp_tool_gui
```
操作清单:
1. 启动 GUI,确认所有菜单/按钮为中文
2. 工具栏"打开" → 弹"打开方式"对话框 → 默认选中"文件夹"
3. 选一个含 mcfd.inp 的算例目录 → 弹完整性检查结果
4. 切到"文件"标签,搜索框输入"reftem" → 树过滤到只剩 reftem
5. hover reftem 的 value → tooltip 显示"参考温度(K)..."
6. 切到"Sweep → 实时编辑"标签 → 填模板 + 输出 + 一个轴 → 同步状态变"已同步"
7. 切到"对比"标签 → 任意操作不崩

- [ ] **Step 4: 提交覆盖率报告**

```bash
git add docs/technical/09-gui-test-coverage.md
# 若该文件不存在则创建,内容是 cov 报告
git commit -m "docs(gui): add v0.16 GUI test coverage report"
```

---

## Task 9: 归档到技术文档 + 准备 release

**Files:**
- Create: `docs/technical/09-gui-ux-v0.16.md`
- Modify: `inp_tool/pyproject.toml`(version bump)

- [ ] **Step 1: 写技术文档章节**

`docs/technical/09-gui-ux-v0.16.md`:

```markdown
# GUI UX 优化(v0.16)

## 变更概览
- 中文 UI(默认),i18n 字典见 `inp_tool/i18n_gui.py`
- 字段说明:见 `inp_tool/field_help.py`(7 个 block / 14 个 keyword)
- 树形搜索:`FieldSearchBar` 实时过滤,父节点自动保留可见
- Sweep 实时编辑:`SweepLiveForm` 与 YAML/JSON 加载并列,共用 `SweepController`
- 文件夹/文件双模式:`OpenModeDialog` 默认文件夹,`FileController.open_case_dir()` + `CaseValidation` 校验
- 算例完整性检查:`mcfd.inp` 必含,`*.pbs` / `*.tri` / `*.plt` 警告

## 涉及文件
(列出 7 个新增 + 5 个修改)

## 测试
(贴 coverage 报告数字)
```

- [ ] **Step 2: 在 `docs/technical/README.md` 追加索引行**

```markdown
| 09 | GUI UX 优化 v0.16 | 中文 UI + 字段搜索 + 文件夹模式 |
```

- [ ] **Step 3: version bump in pyproject.toml**

```toml
version = "0.16.0-dev"  # 原 0.15.2-dev
```

- [ ] **Step 4: 删除本 plan 文件(完成归档)**

```bash
git rm docs/plans/2026-06-15_gui-ux-optimization.md
```

- [ ] **Step 5: Commit**

```bash
git add docs/technical/09-gui-ux-v0.16.md docs/technical/README.md \
        inp_tool/pyproject.toml
git commit -m "docs: archive v0.16 GUI UX optimization to technical/09"
```

---

## 风险评估

| 风险 | 等级 | 缓解 |
|---|---|---|
| QTreeWidget 嵌套 layout 的几何 bug | MEDIUM | 搜索框不放 InpTree 内部,放 MainWindow 的 file_widget 容器 |
| PySide2 3.8 兼容 | LOW | 沿用现有 PySide2 2.x,无新依赖 |
| i18n 字典漏 key | MEDIUM | test_gui_i18n 自动断言 zh/en 对称 |
| field_help 字典不全 | LOW | 漏了不影响功能,UI 上不显示 tooltip 而已 |
| OpenModeDialog 打断用户流程 | LOW | 提供"记住我的选择"checkbox |
| `CaseSweep.to_dict()` 不存在 | MEDIUM | Task 5 已写回退方案(_sweep_to_dict) |

## 完成定义(DoD)

- [ ] 全部 9 个 Task 的 checkbox 勾完
- [ ] 全部测试通过(pytest 100% pass)
- [ ] GUI 覆盖率 ≥ 80%
- [ ] 手动 smoke test 7 步全过
- [ ] 技术文档归档到 `docs/technical/09-gui-ux-v0.16.md`
- [ ] 原 plan 文件从 `docs/plans/` 删除
- [ ] commit 历史清晰(每 Task 一 commit)
- [ ] pyproject.toml version bump
