# 06 — CLI + GUI

> `inp-tool post` CLI 子命令树 + PySide2 GUI panel 实现。

---

## 1. CLI 子命令(`cli_post.py`)

### 1.1 5 个子命令

```
inp-tool post extract       提取气动力 + 系数(零依赖)
inp-tool post convergence   CV 收敛分析 + 文本报告(零依赖)
inp-tool post report        Excel 输出(需 [post])
inp-tool post plot          收敛曲线 png(需 [post])
inp-tool post all           一站式(extract + conv + report + plot)
```

### 1.2 参数设计

**几何参数(extract / report / all 共享)**:
- `--sref FLOAT`(默认 1.0)
- `--lref FLOAT`(默认 1.0)
- `--xref/yref/zref FLOAT`(默认 0)
- `--xcg FLOAT`(默认 0,只填进输出列)

**收敛参数(convergence / plot / all 共享)**:
- `--cv-threshold FLOAT`(默认 0.001)
- `--window-fraction FLOAT`(默认 0.1)
- `--min-window INT`(默认 100)

**共有**:
- `case_dirs`(positional,nargs="+")
- `--op STR`(必需,"1" 或 "1,2,3")
- `--out PATH` / `--out-dir PATH`(默认 ./)
- `--quiet`

### 1.3 接入 cli.py

`cli.py::main()` 末尾通过独立模块注册:

```python
# v0.15.0 / Phase 5: post 子命令(独立模块避免 cli.py 膨胀)
from .cli_post import _register_post_subparser
_register_post_subparser(sub)
```

`cli_post.py` 内部 5 个 `cmd_post_*` 函数走 `set_defaults(func=...)` 派发模式,与项目其他 CLI 一致。

### 1.4 错误处理

| 场景 | 退出码 | 提示 |
|---|---|---|
| 缺 case_dir | 1 | `Error: case directory not found: <path>` |
| 缺参 `--op` | 2 | argparse usage |
| `--op` 不是 int(如 `--op abc`)| 2 | `--op must be comma-separated integers` |
| 缺 mcfd.inp / mcfd.info1 | 1 | `Warning: no valid cases found` |
| 缺 openpyxl(report/all)| 1 | `Error: install with: pip install inp-tool[post]` |
| 缺 matplotlib(plot/all)| 1 | 同上 |

`post all` 在 report/plot 缺包时**继续跑 extract + convergence**,只 Warning 跳过缺的步骤。

---

## 2. GUI panel(`inp_tool_gui/widgets/postprocess_panel.py`)

### 2.1 整体架构

PySide2 三层:
- **Widget(panel)**:UI 布局,信号槽接线,无业务逻辑
- **Controller**(`inp_tool_gui/controllers/postprocess_controller.py`):**PySide2-free** 业务逻辑,纯 Python
- **底层**(`inp_tool.postprocess`):算法

Widget 通过 `run_requested.emit(action, params)` 信号,把数据交给 main_window 的 `_on_postprocess_run` 槽方法,槽方法配置 controller 并执行。

### 2.2 PostprocessPanel

```python
class PostprocessPanel(QWidget):
    run_requested = Signal(str, dict)   # action_name, params_dict

    # 编程 API
    def add_case_dir(self, path): ...
    def get_case_dirs(self) -> List[Path]: ...
    def clear_cases(self): ...
    def set_op(self, op: str): ...
    def get_op(self) -> str: ...
    def set_geometry(self, sref=None, lref=None, ...): ...
    def get_geometry(self) -> Dict[str, float]: ...
    def append_log(self, message: str): ...
    def clear_log(self): ...
```

### 2.3 布局

```
┌────────────────────────────────────────────────┐
│ [选目录...] [清空]            Cases: N         │
│ ┌─ QListWidget ──────────────────────────┐   │
│ │ /path/to/case_01                       │   │
│ │ /path/to/case_02                       │   │
│ └────────────────────────────────────────┘   │
│                                                │
│ ┌─ 参考几何 & 积分 op ────────────────────┐  │
│ │ Sref (m²): [ 1.0   ]                    │  │
│ │ Lref (m):  [ 1.0   ]                    │  │
│ │ Xref (m):  [ 0.0   ]                    │  │
│ │ Yref (m):  [ 0.0   ]                    │  │
│ │ Zref (m):  [ 0.0   ]                    │  │
│ │ Xcg  (m):  [ 0.0   ]                    │  │
│ │ 积分 op:   [ 1     ]                    │  │
│ └──────────────────────────────────────────┘  │
│                                                │
│ [提取力] [收敛分析] [Excel] [收敛图] [全部]    │
│                                                │
│ ┌─ 日志区 (QPlainTextEdit) ───────────────┐  │
│ │ === extract ===                         │  │
│ │ 提取完成,1 个算例                        │  │
│ │   case: Ma=9.887, CD=0.12345, CL=...    │  │
│ └──────────────────────────────────────────┘  │
└────────────────────────────────────────────────┘
```

### 2.4 PostprocessController

**PySide2-free**,纯 Python:

```python
class PostprocessController:
    # 配置
    def set_geometry(sref=None, lref=None, ...): ...
    def set_op_ibd(value: Union[str, Sequence[int]]): ...

    # 5 方法
    def extract(case_dirs) -> ForceReport: ...
    def convergence(case_dirs, threshold=..., ...) -> [(case_name, window or None)]: ...
    def report(case_dirs, out_path) -> Path: ...           # 需 [post]
    def plot(case_dirs, out_path, threshold=..., ...) -> Path: ...  # 需 [post]
    def run_all(case_dirs, out_dir, ...) -> Dict[str, Any]: ...
```

`run_all` 在 `[post]` 缺时静默跳过 xlsx/png(只写 txt + 返回 ForceReport)。

### 2.5 信号槽连接(main_window.py)

```python
self.postprocess_ctrl = PostprocessController()
self.postprocess_panel = PostprocessPanel(self)
self.postprocess_panel.run_requested.connect(self._on_postprocess_run)
self.tabs.addTab(self.postprocess_panel, "后处理(&P)")

def _on_postprocess_run(self, action: str, params: dict) -> None:
    # 1. 校验:case_dirs 非空,否则 QMessageBox.warning
    # 2. 把 params 写进 self.postprocess_ctrl
    # 3. 按 action 派发:
    #    extract → ctrl.extract + 打印到日志
    #    convergence → QFileDialog 选目录 → ctrl.convergence + 写 txt
    #    report → QFileDialog 选 xlsx → ctrl.report
    #    plot → QFileDialog 选 png → ctrl.plot
    #    all → QFileDialog 选目录 → ctrl.run_all
    # 4. ImportError → QMessageBox.warning("缺依赖")
    # 5. 其他异常 → QMessageBox.critical + 日志
```

### 2.6 同步 vs 异步

**当前 v0.15.0:同步执行**(action 期间 GUI 卡住)。
- 单 case 数据量不大(< 1MB)时延迟可接受
- 大算例(1000+ 步 × 100 case)可能卡几秒

**v0.16+ 计划**:迁移到 `QThread` 后台,emit 进度信号到日志区。当前留 TODO 注释。

---

## 3. 测试

| 文件 | 测试数 | 平台 |
|---|---|---|
| `tests/test_post_cli.py` | 14 | 所有 |
| `tests/test_gui_postprocess_controller.py` | 16 | 所有(controller PySide2-free)|
| `tests/test_gui_postprocess_panel.py` | 9 | macOS 跳过(`--ignore-glob='tests/test_gui_*.py'`),Linux/Windows 跑 |

GUI 测试用 `QT_QPA_PLATFORM=offscreen` headless。
