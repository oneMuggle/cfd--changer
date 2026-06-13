# 01. inp_tool_gui 包架构

> **版本:** v0.10.0 新增
> **面向:** 读 / 改 / 扩 GUI 代码的开发者
> **依赖:** PySide2 5.15.2.1(只在装 `[gui]` 时引入)

---

## 1. 概述

`inp_tool_gui/` 是与 `inp_tool/` core **并列**的独立包,不破坏 core 的零依赖承诺。

```
                 ┌────────────────────┐
                 │   inp_tool core    │  ← 零依赖(纯 stdlib)
                 │  parser / writer / │
                 │  model / diff /    │
                 │  sweep / wizard /  │
                 │  repl / cli / api  │
                 └────────────────────┘
                      ▲           ▲
                      │           │
            ┌─────────┘           └─────────┐
            │                              │
   ┌────────┴────────┐            ┌────────┴────────┐
   │  inp-tool CLI   │            │  inp-tool-gui   │  ← v0.10 新增
   │  inp-tool-api   │            │  inp_tool_gui/  │  ← PySide2
   └─────────────────┘            └─────────────────┘
```

**为什么独立包:**

1. **零依赖原则保持**:`from inp_tool import parser` 不会触发 `inp_tool/gui/` 的 import 链
2. **PyInstaller spec 干净**:`inp_tool_gui.spec` 与 `inp_tool.spec` 互不干扰
3. **可选安装边界清晰**:`pip install ".[gui]"` 只装 PySide2

---

## 2. 包结构

```
inp_tool_gui/
├── __init__.py
├── __main__.py            # python -m inp_tool_gui
├── app.py                 # QApplication 入口 + build_window()
├── main_window.py         # QMainWindow 主窗口(QTabWidget + 4 tabs)
├── controllers/           # MVC 业务逻辑层(零 PySide2 依赖)
│   ├── file_controller.py
│   ├── edit_controller.py
│   ├── sweep_controller.py
│   ├── detect_controller.py
│   └── diff_controller.py
└── widgets/               # Qt UI 层(纯展示)
    ├── inp_tree.py        # QTreeWidget 树形展示
    ├── value_editor.py    # QDialog 单值编辑
    ├── detect_panel.py    # 检测报告 + Preset 按钮
    ├── preset_dialog.py   # 3 类 Preset 应用对话框
    ├── sweep_form.py      # Sweep 配置表单 + 结果表
    └── diff_viewer.py     # 双栏 diff(unified)
```

**controllers 不依赖 PySide2**(纯 Python)。这让业务逻辑易测 — 99% 覆盖率,无需 offscreen Qt。

**widgets 依赖 controllers**(通过构造函数注入),不直接调 inp_tool core。

---

## 3. MVC 边界

### 3.1 三层职责

| 层 | 职责 | 依赖 |
|---|---|---|
| **inp_tool core** | parse / write / diff / sweep 等纯逻辑 | stdlib only |
| **controllers/** | GUI 友好 API + undo 栈 + dirty 标志 | inp_tool core + dataclass |
| **widgets/** | Qt UI(展示 + 槽) | controllers + PySide2 |

**反向依赖禁止:** core 不能 import controllers / widgets(零依赖承诺)。
**横向依赖禁止:** widgets 之间不互相 import(只通过 main_window 串接)。

### 3.2 数据流(典型场景:用户双击 value 改字段)

```
1. user double-click value cell in InpTreeWidget
   ↓
2. InpTreeWidget._on_item_double_clicked
   ↓
3. InpTreeWidget.request_edit(item)
   ↓
4. emit value_edit_requested(block_idx, keyword, value_idx)
   ↓
5. MainWindow._on_value_edit_requested
   ↓
6. ValueEditorDialog.exec_()
   ↓
7. ValueEditorDialog.accept() → validate → new_value
   ↓
8. MainWindow: edit_ctrl.set_value(block_name, keyword, new_value, block_idx)
   ↓
9. EditController.set_value
   ↓
10. FileController.set_value → Block.set / Block.append (改 InpFile)
    ↓
11. EditController.push UndoEntry + mark dirty
    ↓
12. MainWindow._refresh_after_edit → InpTreeWidget.populate(inp) 重建树
```

---

## 4. Signal/Slot 约定

### 4.1 命名

| 模式 | 示例 | 说明 |
|---|---|---|
| `value_edit_requested` | block_idx + keyword + value_idx | 子 widget 请求编辑 |
| `preset_requested` | preset_name(str) | 子 widget 请求应用 preset |
| `*_changed` | data_changed | 数据变化 |
| `*_clicked` | button_clicked | 按钮点击(优先用内置 `clicked`) |

### 4.2 Item 数据约定(QTreeWidget)

在 `QTreeWidgetItem.setData(0, Qt.UserRole, ...)` 里塞 tuple:

| Item 类型 | UserRole | 示例 |
|---|---|---|
| 顶层父节点 | `("parent", "top"\|"blocks")` | `("parent", "top")` |
| block | `("block", block_idx, block_name)` | `("block", 0, "physics")` |
| stmt | `("stmt", block_idx, stmt_idx, keyword)` | `("stmt", 0, 2, "reftem")` |
| value | `("value", block_idx, stmt_idx, value_idx, keyword)` | `("value", -1, 0, 0, "title")` |

`block_idx = -1` 表示**顶层语句**;否则为 `inp.block_list` 中的索引。

---

## 5. Controllers 详解

### 5.1 FileController

```python
fc = FileController()
fc.open("mcfd.inp")         # parse + 存 _inp / _path
fc.set_value("physics", "reftem", 300.0, block_idx=0)
fc.save()                    # 写回 _path
```

**API:** `open / save / set_value / get_value / current_path / is_open / inp`

### 5.2 EditController

包装 FileController,自动推 undo:

```python
ec = EditController(fc)
ec.set_value("physics", "reftem", 300.0)  # 推 UndoEntry
ec.undo()                                   # 弹栈,值恢复
ec.redo()                                   # 重做
ec.is_dirty                                 # bool
```

`UndoEntry` dataclass:`(block_name, keyword, old_value, new_value, block_idx)`

### 5.3 SweepController

```python
sc = SweepController()
sc.load_from_yaml("sweep.yaml")
sc.case_count       # 3
sc.preview()        # List[ExplicitCase](dry)
sc.run(dry_run=False, force=True)  # SweepReport
sc.last_report.to_dict()
```

### 5.4 DetectController

```python
dc = DetectController()
rep = dc.run(inp)
rep.summary_zh()            # "检测到: ✓ 雷诺数 | ✓ 湍流(...)"
rep.recommended_fields      # [(block, keyword, value, note)]
```

**v0.10 简化版** — 基于关键字扫描;v0.9.1 完整 `detect_equations()` 上线后,本 controller 调它,API 不变。

### 5.5 DiffController

```python
diffc = DiffController()
diffc.load_pair("a.inp", "b.inp")
diffc.change_count        # N
diffc.unified_text()      # str(unified diff)
```

> 注:`from inp_tool.diff import DiffReport, diff as diff_fn` — 避开 `inp_tool/__init__.py` 把 `diff` 当函数 re-export 的命名冲突。

---

## 6. Widgets 详解

### 6.1 InpTreeWidget

```python
tree = InpTreeWidget()
tree.populate(inp)                              # 重建树
tree.value_edit_requested  # Signal(int, str, int)
tree.refresh_value("physics", "reftem", 0)      # 单行刷新
```

**Item 数据约定见 §4.2**。

### 6.2 ValueEditorDialog

```python
dlg = ValueEditorDialog(current_raw="300.0", current_typed=300.0)
if dlg.exec_() == QDialog.Accepted:
    new_value = dlg.new_value  # typed 值
```

**类型推断:** bool > int > float > str(bool 是 int 子类,须先判)。

**校验失败** → `super().accept()` 不被调,对话框保持打开,`_error_lbl` 显示错误;`result_accepted()` 返 False。
(不用 `QMessageBox.warning` 模态弹窗 — 那会在自动化测试里阻塞事件循环。)

### 6.3 DetectPanel + PresetDialog

DetectPanel:`run(inp)` 调 DetectController → 渲染 QFormLayout 报告 + QGroupBox 警告 + 推荐字段列表(每行"应用"按钮)。

PresetDialog:3 类 preset(turb / 2t / species),`accept()` 批量调 `EditController.set_value`。

### 6.4 SweepForm + DiffViewer

SweepForm:`load_yaml / load_json / run_sync(dry, force)`;结果用 `QTableWidget` 4 列展示 CaseResult。

DiffViewer:`load_paths(a, b)` 公开 API(供集成测试);`QTextBrowser.setHtml` 渲染带颜色 unified diff。

---

## 7. 启动流程

```
inp-tool-gui (console_script)
  ↓
inp_tool_gui/__main__.py:main()
  ↓
inp_tool_gui.app.main()
  ↓
build_window() → QApplication + MainWindow
  ↓
app.exec_()
```

**`build_window()`** 是测试友好的工厂方法 — 返回未显示的 `MainWindow` 实例,可被 `test_build_window_smoke` 等测试检查标题 / 尺寸。

---

## 8. 测试策略

| 层 | 工具 | 覆盖率目标 |
|---|---|---|
| **controllers/** | `pytest` + monkeypatch | 90%+ |
| **widgets/**(Qt) | `pytest` + `QT_QPA_PLATFORM=offscreen` | 60%+ |
| **smoke** | `app.build_window()` + close | 必过 |

**offscreen 平台:** 所有 GUI 测试在 CI / 服务器跑都不需要 X server。

**Monkeystubing 模式:** 测 `MainWindow._on_value_edit_requested` 时,用 monkeypatch 把 `inp_tool_gui.main_window.ValueEditorDialog` 替换成 `FakeDialog`(避免弹模态)。

---

## 9. 已知简化 / 待补(v0.11+)

- **DetectPanel 用关键字扫描** — v0.9.1 完整 `detect_equations()` 后切换
- **SweepForm 同步运行** — 后续加 QThread + `result_ready` signal(plan §5.6)
- **价值编辑后整树重建** — `_refresh_after_edit` 用 `populate` 重建;后续可改为 `refresh_value` 单行刷新
- **关闭时不弹"未保存"** — 加 `closeEvent` override + dirty 检查
- **右键菜单**(Edit / Add new / Delete / Copy value)— InpTreeWidget 暂未实现
- **撤销粒度** — 顶层语句的改值走单独的 undo 路径(block_name="<top>")

---

## 10. 与 Core 的兼容性

GUI 不修改 `parser / writer / model / diff / sweep` 的对外 API;所有改动都通过现有 API 完成(向后兼容)。

新增 imports(controllers 引用 core):

- `from inp_tool import parser, writer`
- `from inp_tool import sweep`
- `from inp_tool.diff import DiffReport, diff as diff_fn`
- `from inp_tool.model import InpFile, Block, Stmt, Value, infer_type`

> `from inp_tool import diff as diff_mod` **不能用** — `inp_tool/__init__.py` 把 `diff` 当函数 re-export。