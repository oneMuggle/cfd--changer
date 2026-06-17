# 14 — Sweep UI v2(三视图 tab 整合架构)

> **Status:** Implemented in Phase 7(umbrella spec `2026-06-16-sweep-ui-redesign-design.md` §2 / §3 / §4 / §5)
**模块:** `inp_tool_gui` 三层分离(View → ConfigStore → Controller → Engine)+ `inp_tool.sweep` v2 引擎 + `inp_tool_gui.preset_library` preset 库
**对应源码:** `inp_tool/inp_tool_gui/{main_window.py, models/, controllers/, widgets/, preset_library.py}` + `inp_tool/inp_tool/sweep.py` v2 段

---

## 1. 架构概览

Sweep UI v2 是对「批量算例」标签页的**整体重设计**,把原本单页表单(`sweep_form.py`,~640 行)升级为**三层分离 + 单向数据流**的现代 GUI 架构。

```
┌──────────────────────────────────────────────────────────────────┐
│  View 层 (PySide2)                                               │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐           │
│  │ WizardView  │  │ FormView     │  │ YamlEditorView │           │
│  │ (4 步)      │  │ (单页紧凑)    │  │ (3 pane)       │           │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘           │
│         └──── 三者共享 ConfigStore ───────────┘                  │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ ConfigStore (frozen dataclass, copy-on-update)         │      │
│  │  + PresetSidebar (3 视图共享)                          │      │
│  └────────────────────────────────────────────────────────┘      │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ SweepControllerV2 (纯 Python, 无 PySide2 依赖)         │      │
│  │   load_yaml / dump_yaml / upgrade_v1_to_v2            │      │
│  │   PresetLibrary (CRUD + seed_default_presets)          │      │
│  └────────────────────────────────────────────────────────┘      │
│                              │                                   │
│                              ▼                                   │
│  ┌────────────────────────────────────────────────────────┐      │
│  │ Engine (inp_tool.sweep)                               │      │
│  │   expand_cartesian (v1, 保留)                         │      │
│  │   expand_with_conditions (v2, 新增)                   │      │
│  │   parse_condition / evaluate_condition (v2)            │      │
│  └────────────────────────────────────────────────────────┘      │
└──────────────────────────────────────────────────────────────────┘
```

**核心数据流规则**:
1. 任意 View 修改 → `ConfigStore.replace(...)` → 返回新 `ConfigStore` 实例
2. store holder emit `config_changed(new)`
3. 其他 View 收到 `config_changed` → 调 `store.to_<view_format>()` → 重新渲染

**禁止**:
- View A 直接调 View B 的方法
- Controller 直接读 widget 属性
- ConfigStore 包含任何 PySide2 类型

---

## 2. ConfigStore(`inp_tool_gui/models/config_store.py`)

`ConfigStore` 是**不可变**的 sweep 配置容器,所有修改通过 `replace()` 系列方法返回新实例(类似 React 的 state reducer 模式)。

```python
@dataclass(frozen=True)
class AxisSpec:
    """单轴值规范。kind 决定 values / range_* 字段语义。"""
    kind: str                              # "enum_subset" | "explicit_list" | "range" | "csv_str"
    values: Tuple[Any, ...] = ()
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_step: Optional[float] = None

@dataclass(frozen=True)
class ConfigStore:
    template: str
    output_dir: str
    naming: str
    preset_ref: Optional[str]
    sweeps: Dict[str, AxisSpec] = field(default_factory=dict)
    conditions: Tuple[ConditionalRule, ...] = ()

    def replace(self, **kwargs) -> "ConfigStore":
        return dataclasses.replace(self, **kwargs)

    def replace_sweep(self, key: str, spec: AxisSpec) -> "ConfigStore": ...
    def remove_sweep(self, key: str) -> "ConfigStore": ...
    def add_condition(self, rule: ConditionalRule) -> "ConfigStore": ...
```

**设计要点**:
- `frozen=True` 禁止 in-place 修改,所有改动都返回新对象(便于 `config_changed` 信号)
- `case_count` property 实时预估笛卡尔积 case 数(无 conditions 过滤),用于 UI 显示
- `replace_sweep` / `remove_sweep` / `add_condition` 是常用修改的便捷封装(内部调 `replace`)
- 无 PySide2 依赖,纯 stdlib,Controller/CLI 也能复用

---

## 3. Sweep YAML v2 schema(`inp_tool_gui/controllers/sweep_controller_v2.py`)

`SweepControllerV2` 负责 v1 ↔ v2 YAML 互转 + 升级,见 spec §3。下面是 v2 schema 关键点:

```yaml
version: 2                         # 必填,缺失或 1 → 自动升级
template: /path/to/template.inp
output_dir: /path/to/output
naming: case_{mach}_{reynolds}     # 默认 "case"
preset: my-team/incompressible-baseline   # 可选,引用 preset 库

sweeps:                            # Dict[str, AxisSpec]
  turbulence: [sst, kw]            # 枚举子集(str 列表)
  mach:
    range: [0.5, 1.5, 0.25]        # range: [min, max, step]
  reynolds: [1e5, 5e5, 1e6]        # 显式 list(数值/字符串)
  alpha: "0, 5, 10, 15, 20"        # 字符串形式(内部 split(","))

conditions:                        # 可选
  - when: {mach: "<1"}
    then:
      disable_axes: [turbulence]    # 跳过该轴 sweep
  - when: {reynolds: ">=5e5"}
    then:
      set_extra: {turb_init: "yes"} # 注入额外 .inp 修改
```

**AxisSpec 五种 kind**(`SweepControllerV2._parse_sweeps` 判定):

| YAML 形式 | 判定后 kind | 适用 |
|---|---|---|
| `[v1, v2, ...]` 元素全 str | `enum_subset` | 枚举子集 |
| `[v1, v2, ...]` 元素全数值 | `explicit_list` | 数值显式列表 |
| `{range: [min, max, step]}` | `range` | 数值等差 |
| `"0, 5, 10"`(字符串) | `csv_str` | 逗号分隔解析 |
| `{expr: "..."}` | `expression` | 预留,本期不实现 |

**v1 → v2 自动升级**:`SweepControllerV2._upgrade_v1()` 给旧 YAML 加 `version: 2` + `conditions: []` + `preset: None`,不破坏老配置。

**CLI 迁移**:`inp-tool migrate-sweep-v1 src dst` 子命令显式把 v1 文件写到 v2(由 `inp_tool/sweep_cli.py:cmd_migrate_sweep_v1` 处理)。

---

## 4. 4 步向导(`inp_tool_gui/widgets/sweep_wizard*.py`)

Wizard 拆为 4 个独立 widget,每个 step 维护自己的 UI 但**共享 ConfigStore** + 各自 emit `store_changed` 统一汇入。

| Step | 文件 | 内容 | 关键控件 |
|---|---|---|---|
| 1 | `sweep_wizard.py`(主)+ step 1 inline | 模板与输出 | `QLineEdit` × 3 + 浏览按钮 + i18n label |
| 2 | `sweep_wizard_step2.py` | 选轴 + 设值 | 左 `VariableTreeWidget` / 右已选轴列表(每轴值 widget 按 kind 切换) |
| 3 | `sweep_wizard_step3.py` | 条件依赖 when/then | 条件列表 + 「添加条件」按钮 + 子表单 |
| 4 | `sweep_wizard_step4.py` | 预览 + 运行 | case 数预估 + dry run 表格 + Run 按钮 |

**值 widget 智能(per axis.kind)**:
- `enum_subset` → 弹 `EnumChecklistDialog` 多选 checklist
- `range` → 3 个 `QSpinBox`(min/max/step)
- `explicit_list` / `csv_str` → `QPlainTextEdit` 多行,逗号分隔

每个 step 修改后 emit `store_changed(new)` → main_window 把新 store 推给其他 2 个 View 同步。

---

## 5. YAML 编辑器(`inp_tool_gui/widgets/sweep_yaml_editor*.py`)

3-pane 容器(`SweepYamlEditorView`):

```
┌──────────────────────────────────────────────────┐
│  [QPlainTextEdit + YamlHighlighter + 行号]        │  ← 主区
├──────────┬───────────────────────────┬───────────┤
│ Variable │  主区(同上)               │ Case 预览  │
│ Tree     │                           │ (实时)    │
│          │                           │           │
│ Preset   │                           │           │
│ Sidebar  │                           │           │
└──────────┴───────────────────────────┴───────────┘
```

**关键组件**:
- `YamlEditor`(`sweep_yaml_editor.py`):`QPlainTextEdit` + 等宽字体 + 当前行高亮
- `YamlHighlighter`:关键词着色(`version` / `template` / `sweeps` / `conditions` / `disable_axes` / `set_extra` 等)
- `LineNumberArea`:自绘行号侧栏(`paintEvent` + `updateRequest`)
- **200ms debounce schema lint**:文本变更后 debounce 200ms → `yaml.safe_load` + `SweepControllerV2._parse` → 失败则底部状态栏 `✗ line N: <error>` + 错误行号侧栏红点;成功则推回 store

```
文本变更 → QTimer(200ms 单次) → 触发 lint
                              → 成功:store.replace(...)
                              → 失败:状态栏 + 红点,不写 store
```

**Preset Sidebar**(共享组件 `widgets/preset_sidebar.py`):
- 3 个 View 都嵌入同一 `PresetSidebar`
- 树形展示 `PresetLibrary.list()` 结果,分组:「我的」/「团队:<dir>」/「最近」
- 双击 = 加载到当前 ConfigStore(merge 语义见 spec §3.4)
- 右键菜单:打开位置 / 删除(仅 user preset)/ 编辑

---

## 6. Preset 库(`inp_tool_gui/preset_library.py`)

### 6.1 存储位置

| 类型 | 路径 |
|---|---|
| 用户 preset | `~/.config/cfd--changer/presets/<name>.yaml` |
| 团队 preset | `~/.config/cfd--changer/config.yaml` 里的 `team_preset_dirs: [...]`,默认空 |

### 6.2 preset 文件 schema

```yaml
version: 2
name: incompressible-baseline
tags: [baseline, low-speed]
created_at: 2026-06-16T10:00:00
updated_at: 2026-06-16T10:00:00
author: onemuggle        # 可选

sweeps:
  turbulence: [sst, kw]
  mach:
    range: [0.0, 0.6, 0.2]

conditions: []
```

**不含** `template` / `output_dir` / `naming`(preset 与具体模板无关)。

### 6.3 3 个默认 preset + 启动 seed

首次启动 GUI 时,`main_window.py` 调 `PresetLibrary.seed_default_presets(user_dir)`,把包内 3 个 `resources/default_presets/*.yaml` 复制到 `~/.config/cfd--changer/presets/`:

| Preset | 用途 | 关键 sweeps |
|---|---|---|
| `low-speed-baseline` | 亚音速算例 | `mach: [0.0, 0.6, 0.2]` + 空 conditions |
| `transonic-baseline` | 跨音速算例 | `mach: [0.8, 1.2, 0.1]` + 2 个 conditions(避免湍流越界) |
| `high-speed-baseline` | 高超声速算例 | `mach: [2.0, 5.0, 1.0]` + 温度 ramp |

资源读取用 `pkgutil.get_data(__package__, ...)`(Python 3.8 兼容,避开 PEP 302 `__loader__.get_data` 在不同环境的行为差异)。

### 6.4 PresetLibrary API(纯 Python,无 Qt)

```python
class PresetLibrary:
    def list(self) -> List[PresetMeta]: ...            # 含 source: "user" | "team:<name>"
    def get(self, ref: str) -> PresetContent: ...     # ref = "name" 或 "team:<name>"
    def save(self, name: str, content: ..., *, overwrite: bool = False) -> Path: ...
    def delete(self, ref: str) -> None: ...           # 仅 user 可删
    def search(self, query: str) -> List[PresetMeta]: ...
    def seed_default_presets(self, user_dir: Path) -> int: ...  # 首次启动 copy 内置
```

错误:
- 不存在 ref → `KeyError`
- 同名 user preset 已存在 + 未传 overwrite → `FileExistsError`
- 删 team preset → `PermissionError`

---

## 7. 引擎 v2 改造(`inp_tool/sweep.py`)

### 7.1 condition 原语

```python
@dataclass(frozen=True)
class ConditionPredicate:
    """单变量 op val。"""
    key: str
    op: str                  # "<" | "<=" | "==" | "!=" | ">=" | ">"
    value: Any               # YAML 推断类型(int/float/str/bool)

@dataclass(frozen=True)
class ConditionWhen:
    """多变量 AND;predicates 空 → 永真。"""
    predicates: Tuple[ConditionPredicate, ...] = ()

@dataclass(frozen=True)
class ConditionThen:
    disable_axes: Tuple[str, ...] = ()              # 该 case 跳过这些轴
    set_extra: Tuple[Tuple[str, str], ...] = ()      # 该 case 注入 (k,v)

@dataclass(frozen=True)
class ConditionalRule:
    when: ConditionWhen
    then: ConditionThen
```

### 7.2 解析与求值

```python
def parse_condition(when_dict: Dict[str, str]) -> ConditionWhen:
    """{'mach': '<1', 'reynolds': '>=1e6'} → ConditionWhen(predicates=(...))"""

def evaluate_condition(when: ConditionWhen, case: Dict[str, Any]) -> bool:
    """AND 语义:全部 predicate 满足才 True;case 缺 key → False;空 predicates → True"""
```

**value 类型推断**(`_infer_value`):`true/false` → bool;`int()` 成功 → int;`float()` 成功 → float;其余 str。

### 7.3 expand_with_conditions(first-match-wins, miss → keep)

```python
@dataclass(frozen=True)
class ExpandedCase:
    """含 set_extra;disable_axes 已过滤(不出现)。"""
    values: Dict[str, Any]
    extras: Tuple[Tuple[str, str], ...] = ()

def expand_with_conditions(
    spec: SweepSpec,
    conditions: Tuple[ConditionalRule, ...] = (),
) -> List[ExpandedCase]:
    """v2 展开:笛卡尔积 + condition 过滤 + disable_axes/set_extra 应用。"""
```

**关键语义**:
- 对笛卡尔积每个 case 找**第一条** `when` 命中的 rule(first-match-wins,后续 rule 不再评估)
- `then.disable_axes` 应用:从 `case.values` 删除这些轴
- `then.set_extra` 应用:写入 `case.extras`(后续 sweep 生成器在 apply 时把它注入到生成的 .inp 文件)
- **miss → keep**:若没有任何 rule 命中,该 case 保留原样,不被条件过滤掉
- 旧 `expand_cartesian(spec: SweepSpec)` 保留,继续给 v1 YAML / 旧测试用

### 7.4 错误处理

| 情况 | 行为 |
|---|---|
| condition 中 op 未知 | `ValueError("unknown operator 'foo'")` |
| condition 引用不存在的轴 | `ValueError(f"unknown axis '{key}' in condition")` |
| range 的 step = 0 | `ValueError("range step must be non-zero")` |
| range 的 min > max | `ValueError("range min must be <= max")` |
| 枚举子集含未声明值 | `ValueError(f"unknown enum value '{x}' for axis '{key}'")` |

---

## 8. 三视图 tab 整合(`inp_tool_gui/main_window.py`)

### 8.1 main_window 改造

把原本的「批量算例」标签页(单 `SweepFormView`)替换为**嵌套 `QTabWidget`**:

```python
self.sweep_tabs = QTabWidget()
self.sweep_tabs.addTab(self.wizard_view,    tg("sweep.tab.wizard"))
self.sweep_tabs.addTab(self.form_view,      tg("sweep.tab.form"))
self.sweep_tabs.addTab(self.yaml_view,      tg("sweep.tab.yaml"))
```

3 个子 view **共享同一个 `ConfigStore` 实例**(由 main_window 持有,通过 setter 注入)。

### 8.2 单向数据流

```python
# main_window 启动时
self.config_store = ConfigStore(template="", output_dir="", naming="case",
                                preset_ref=None, sweeps={}, conditions=())
self.wizard_view.set_store(self.config_store)
self.form_view.set_store(self.config_store)
self.yaml_view.set_store(self.config_store)

# 各 view 修改后
self.wizard_view.store_changed.connect(self._on_store_changed)

def _on_store_changed(self, new_store: ConfigStore) -> None:
    self.config_store = new_store
    self.form_view.refresh_from_store()
    self.yaml_view.refresh_from_store()
```

切 tab 保留 ConfigStore,只换渲染方式(不重新加载文件)。

### 8.3 快捷键

| 键 | 行为 | 实现 |
|---|---|---|
| `Ctrl+1` | 切到「向导」 | `QShortcut(QKeySequence("Ctrl+1"), self, lambda: self.sweep_tabs.setCurrentIndex(0))` |
| `Ctrl+2` | 切到「自由表单」 | 同上,index=1 |
| `Ctrl+3` | 切到「YAML」 | 同上,index=2 |
| `Ctrl+S` | 保存当前 spec 为 YAML | 弹保存对话框 → `SweepControllerV2.dump_yaml` |
| `Ctrl+R` | Dry run | `SweepController.run(dry_run=True)` |
| `Ctrl+Shift+R` | 实际运行 | `SweepController.run(dry_run=False)` |
| `Ctrl+Shift+P` | 打开 preset 库管理 | 弹 preset 管理对话框 |

### 8.4 启动 seed

`main_window.__init__` 末尾:

```python
preset_dir = Path.home() / ".config" / "cfd--changer" / "presets"
team_dirs = self._load_team_preset_dirs()      # 从 config.yaml 读
self.preset_library = PresetLibrary(user_dir=preset_dir, team_dirs=team_dirs)
self.preset_library.seed_default_presets(preset_dir)  # 首次启动 copy 3 个
```

`seed_default_presets` 幂等:若 `user_dir/<name>.yaml` 已存在则跳过(不覆盖用户修改)。

---

## 9. 已知限制

| 限制 | 原因 | 后续计划 |
|---|---|---|
| `expand_with_conditions` 的 `set_extra` 仅字面量 k=v | 不支持表达式(避免引入 eval) | 待 v2.1 加 safe expression |
| YAML 编辑器无代码补全 | `QScintilla` 跨平台不可靠 | 后续可换 Monaco(浏览器)或 LSP |
| preset 团队共享走 Git,无 conflict resolution | UI 提示用户手动 merge | spec §13 已列,不在本期 |
| 撤销/重做栈未实现(本期不交付) | 历史栈 50 条 + UI 集成工作量较大 | spec §11 列为 P7 后子项目 |
| wizard step 3 condition 表达式不支持 OR/NOT/嵌套 | spec §3.3 显式限制 | 后续按需扩展 |
| 3 视图同步在 YAML lint 失败时不同步 | 避免「错值写回 store」 | 已实现(见 §5) |

---

## 10. 后续工作(不在本期范围)

- 撤销/重做历史栈(50 条上限,ConfigStore 持有)
- 实时协作(Git conflict resolution UI)
- Sweep 结果可视化(参数 → 性能曲线 / 热力图)
- 多模板对比 sweep(同一 sweep 配置套不同模板)
- 远程执行 sweep(Linux server + 本地 GUI 控制)
- 与外部工具(HFSS / OpenFOAM / StarCCM+)的参数同步

---

## 11. 测试覆盖(本期新增)

| 测试文件 | 用例数 | 覆盖 |
|---|---|---|
| `inp_tool/tests/test_sweep_conditions.py` | 16+ | condition 原语 + expand_with_conditions + first-match-wins |
| `inp_tool/tests/test_config_store.py` | 12+ | frozen + replace + case_count |
| `inp_tool/tests/test_preset_library.py` | 10+ | CRUD + team source + search + seed |
| `inp_tool/tests/test_sweep_controller_v2.py` | 8+ | YAML v1/v2 + round-trip + 升级 |
| `inp_tool/tests/test_sweep_cli_migrate.py` | 4+ | `migrate-sweep-v1` CLI |
| `inp_tool/tests/test_gui_enum_checklist.py` | 4+ | EnumChecklistDialog 多选 |
| `inp_tool/tests/test_gui_sweep_form_view.py` | 10+ | FormView 单向数据流 + store_changed |
| `inp_tool/tests/test_gui_sweep_wizard.py` | 8+ | 4 步流程 + step 间数据流 |
| `inp_tool/tests/test_gui_sweep_yaml_editor.py` | 6+ | lint + 高亮 + debounce |

累计 +80 用例,旧 sweep 测试零回归。

---

## 12. 关联文档

- 上游 spec: [`../../superpowers/specs/2026-06-16-sweep-ui-redesign-design.md`](../../superpowers/specs/2026-06-16-sweep-ui-redesign-design.md)(umbrella spec)
- 实现 plan: [`../../superpowers/plans/2026-06-16-sweep-ui-redesign-plan.md`](../../superpowers/plans/2026-06-16-sweep-ui-redesign-plan.md)(7 phase 拆分)
- 用户视角: [`../../user-manual/sweep/README.md`](../../user-manual/sweep/README.md) §三视图使用
- 引擎层: [`02-sweep-architecture.md`](02-sweep-architecture.md)
- v1 sweep 灵活化(已归档): [`09-sweep-flexible.md`](09-sweep-flexible.md)
