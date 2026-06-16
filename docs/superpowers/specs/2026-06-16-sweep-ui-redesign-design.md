**Status:** Draft (待用户 review)
**Date:** 2026-06-16
**Scope:** inp_tool_gui「批量算例」标签页 — 整体架构重设计
**Audience:** 维护者(单人项目 onemuggle)
**Goal:** 把「批量算例」从「单页表单 + 自由文本值」升级为「配置/视图分离 + 三视图(向导/自由表单/YAML)+ Preset 库 + 条件依赖」的系统化设计,**覆盖 4 个核心痛点**:枚举子集 sweep、变量发现/验证、依赖/条件 sweep、复用/Preset 库。允许打破旧 YAML 格式契约(自动迁移兜底)。

---

# Sweep UI 整体架构重设计

> 本文是 **umbrella spec**;具体的子设计(变量发现、condition 表达式、Preset 库 schema)在 §11 列出后单独立 spec。
> 本文范围 = 「批量算例」整个交互系统的模块边界 + 数据流 + 关键 schema + UI 框架 + 阶段交付。
> 历史: 2026-06-16 sweep-tab-ux-redesign + PR #48 (enum cell 可编辑) 是本文的前置子项目,本文把它们吸收进更大的体系。

---

## §1 背景与目标

### 1.1 现状(`sweep_form.py` v0.17,PR #48 后)

| 模块 | 文件 | 现状 | 痛点 |
|---|---|---|---|
| Widget | `inp_tool_gui/widgets/sweep_form.py` (~640 行) | 单页表单,combo + line edit | 1 个 widget 同时承担 view + controller 信号逻辑,行数膨胀 |
| Controller | `inp_tool_gui/controllers/sweep_controller.py` | 包装 CaseSweep + load/save | 与 widget 双向耦合(`_sweep` 内部属性被 widget 直接读) |
| 变量发现 | `inp_tool_gui/widgets/sweep_var_combo.py` | `enumerate_vars()` 纯函数 | 平铺列表,无搜索/分组,变量多时眼花 |
| 引擎 | `inp_tool/sweep.py` | `expand_cartesian` + 枚举识别 | 缺少 condition 原语、preset 引用 |
| YAML 格式 | (隐式 v1) | `sweeps: {key: [values]}` | 不能表达 range/preset 引用/condition |

### 1.2 目标

| 维度 | 当前 | 目标 |
|---|---|---|
| 视图数 | 1(单页表单) | 3(向导 / 自由表单 / YAML),tab 切换 |
| 数据流 | widget ↔ controller 双向信号 | 单向:View → ConfigStore → 其他 View 自动同步 |
| 枚举子集 | 输入框手动删值 | 独立 checklist 多选 |
| 变量发现 | 平铺列表 + combo 搜索无 | 树形分组 + 实时搜索 + metadata 展示 |
| 条件依赖 | ❌ 不支持 | ✅ v2 YAML + 向导 step 3 + 引擎层 predicate |
| Preset 库 | 仅保存为 .yaml | ✅ 用户级 + 团队级 preset 库 + 拖入即用 |
| 键盘效率 | 鼠标为主 | Ctrl+1/2/3 切视图,Ctrl+S 存盘,Ctrl+R 运行 |
| YAML schema | v1(只 list) | v2(+ range + preset 引用 + conditions) |

### 1.3 不在范围

- ❌ 不改 `.inp` 解析层(`inp_tool/parser.py` / `model.py`)
- ❌ 不改 `inp_tool.api` (FastAPI 后端)
- ❌ 不改 pyproject 依赖(继续 PySide2 + PyYAML)
- ❌ 不改其他标签页(文件/检测/对比/后处理)布局
- ❌ 不做云端 preset 同步(仅本地 + 可选 Git 团队目录)
- ❌ 不做实时多人协作
- ❌ 不引入 Monaco(本地仅用 QScintilla 或纯 QPlainTextEdit 加 schema lint)

---

## §2 架构与边界

### 2.1 三层分离

```
┌─────────────────────────────────────────────────────────────┐
│  View 层 (PySide2)                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐     │
│  │ WizardView  │  │ FormView     │  │ YamlEditorView │     │
│  │ (4-step)    │  │ (单页紧凑)    │  │ (YAML + sidebar)│     │
│  └──────┬──────┘  └──────┬───────┘  └────────┬───────┘     │
│         └──── 三者共享 ConfigStore ───────────┘              │
│                              │                               │
│                              ▼                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ ConfigStore (frozen dataclass, copy-on-update)        │   │
│  │   fields: template, output_dir, naming, preset_ref,   │   │
│  │           sweeps: Dict[str, AxisSpec],                │   │
│  │           conditions: List[ConditionalRule]            │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│                              ▼                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ SweepController (纯 Python, 无 PySide2 依赖)          │   │
│  │   load_from_dict / dump_to_dict / load_yaml_v2 /      │   │
│  │   dump_yaml_v2 / validate / upgrade_v1_to_v2         │   │
│  └──────────────────────────────────────────────────────┘   │
│                              │                               │
│                              ▼                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Engine (inp_tool.sweep)                               │   │
│  │   expand_cartesian (v1, 保留)                         │   │
│  │   expand_with_conditions (v2, 新增)                   │   │
│  │   parse_condition (AST, 新增)                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**单向数据流规则**:
1. 任意 View 修改 → `ConfigStore.replace(...)` → 返回新 ConfigStore 实例
2. View 把新 ConfigStore 推回 store holder;store holder emit `config_changed(new)`
3. 其他 View 收到 `config_changed` → 调 `store.to_<view_format>()` → 重新渲染自己

**不允许**:View A 直接调 View B 的方法、Controller 直接读 widget 属性。

### 2.2 模块清单

| 模块 | 文件(规划) | 依赖 | 职责 |
|---|---|---|---|
| `ConfigStore` | `inp_tool_gui/models/config_store.py` | dataclasses, copy | 不可变配置 + replace |
| `AxisSpec` | 同上 | — | 单轴值规范(enum/range/list) |
| `ConditionalRule` | 同上 | — | 单条 (when, then) |
| `SweepController` (新) | `inp_tool_gui/controllers/sweep_controller_v2.py` | ConfigStore, engine | 加载/校验/迁移/YAML v2 I/O |
| `PresetLibrary` | `inp_tool_gui/preset_library.py` | pathlib, yaml | 文件级 preset CRUD |
| `WizardView` | `inp_tool_gui/widgets/sweep_wizard.py` | ConfigStore | 4 步向导 |
| `FormView` | `inp_tool_gui/widgets/sweep_form.py`(重写内部) | ConfigStore | 单页表单 |
| `YamlEditorView` | `inp_tool_gui/widgets/sweep_yaml_editor.py` | ConfigStore | YAML 编辑 + sidebar |
| `Engine v2` | `inp_tool/sweep.py`(追加) | — | condition + 笛卡尔积过滤 |

**文件大小约束**(CLAUDE.md §4):每个 widget ≤ 800 行,典型 200-400。`sweep_form.py` 当前 640 行,重写后预计拆为 `sweep_form_view.py` + 共享 helpers。

### 2.3 边界规则

| 不允许 | 原因 |
|---|---|
| View 直接 import `inp_tool.sweep` | 引擎层与 UI 隔离,只通过 Controller |
| Controller import 任何 PySide2 widget | 控制器可被 CLI 复用,纯 Python |
| ConfigStore 含 PySide2 类型 | 同上 |
| PresetLibrary import Controller | PresetLibrary 只读写 YAML 文件,无业务逻辑 |
| View 跨 tab 直接通信 | 必须经过 ConfigStore.emit |

---

## §3 Sweep YAML v2 schema

### 3.1 schema 定义

```yaml
# sweep.yaml — v2
version: 2  # 必填,缺失或 1 → 自动升级

template: /path/to/template.inp   # string, 必填
output_dir: /path/to/output       # string, 必填
naming: case_{mach}_{reynolds}    # string, 默认 "case"

# (可选) preset 引用;preset 内容展开为 sweeps + conditions,再被本文件覆盖
preset: my-team/incompressible-baseline

sweeps:                           # Dict[str, AxisSpec]
  turbulence: [sst, kw]           # 枚举子集:list of valid enum values
  mach:
    range: [0.5, 1.5, 0.25]       # range: [min, max, step]
  reynolds: [1e5, 5e5, 1e6]       # 显式 list (数值或字符串)
  alpha: "0, 5, 10, 15, 20"        # 字符串形式也接受,内部 split(",") 解析

conditions:                       # List[ConditionalRule], 可选
  - when: {mach: "<1"}
    then:
      disable_axes: [turbulence]   # 该 case 跳过 turbulence 的 sweep 维度
  - when: {reynolds: ">=5e5"}
    then:
      set_extra: {turb_init: "yes"} # 该 case 注入额外 mcfd.inp 修改
```

### 3.2 AxisSpec 三态

`AxisSpec.kind` 的判定 **依赖 key 的上下文**(从 `available_vars(template_path)` 查):key 是已知 enum 类型 → list 形式为 `enum_subset`;否则 → `explicit_list`。YAML 解析器只产出原始 list,实际 `kind` 由 `controller.normalize_axis(key, raw_list)` 在加载时打标。

| YAML 形式 | Python `AxisSpec.kind`(经 key 上下文判定后) | 适用 |
|---|---|---|
| `[v1, v2, ...]`(元素全 str) | key 是枚举 → `enum_subset`<br>key 不是枚举 → `explicit_list` (str) | 枚举子集 / 字符串显式列表 |
| `[v1, v2, ...]`(元素全 数值) | `explicit_list` (numeric) | 数值显式列表 |
| `{range: [min, max, step]}` | `range` | 数值等差 |
| `{range: [min, max]}`(两元素) | `linspace` | 数值等分 N 点(预留,本期不实现) |
| `"0, 5, 10"`(字符串) | `csv_str` | 同 explicit_list,内部 split(",") |
| `{expr: "..."}` | `expression` | **预留本期不实现** |

**关键约束**:若 key 是枚举但 YAML 写了 `enum_subset` 之外的非法值,`controller.normalize_axis` 抛 `ValueError("unknown enum value '{x}' for axis '{key}'; expected one of {valid}")`(见 §6.3)。

### 3.3 ConditionalRule 表达式语法

`when.<key>` 的值是字符串 `"<op><val>"`,`<op>` ∈ `{<, <=, ==, !=, >=, >}`。

**支持**:
- 单变量单 op:`{mach: "<1"}`
- 多变量 AND(逗号分隔,逻辑 AND):`{mach: "<1", reynolds: ">=1e6"}`

**不支持(本期)**:
- OR / NOT / 括号嵌套 / 函数调用

**解析**:`parse_condition(when_dict)` 把 raw 字符串解析成结构化的 `ConditionPredicate(key, op, value)`(见 §6.1)。value 按 YAML 推断类型(int / float / str / bool)。

`then` 字段:
- `disable_axes: [key1, ...]` — 该 case 跳过这些轴的 sweep(等价于笛卡尔积过滤掉)
- `set_extra: {keyword: value, ...}` — 该 case 生成时注入额外 .inp 修改(通过 `inp_tool.editor` API)

### 3.4 preset 引用语义

```
preset: my-team/foo
```

1. 启动时,从 `PresetLibrary` 读 `foo.yaml`
2. 把 foo 的 sweeps + conditions 合并到当前 spec 的同名项(本文件覆盖 preset 的)
3. preset 不含 template/output_dir(preset 是抽象模板,与具体模板无关)
4. preset 可以级联引用 preset(最多 1 层,防循环)

### 3.5 版本与迁移

| 读到的文件 | 行为 |
|---|---|
| 无 `version` 字段 | 当 v1 处理,自动 `upgrade_v1_to_v2()` 后走 v2 路径 |
| `version: 1` | 同上 |
| `version: 2` | 直接走 v2 路径 |
| `version: 3+` | 报"schema 太新,无法读取"(给用户友好提示) |

写盘永远写 v2(单向前向,无回退)。

---

## §4 UI 三视图系统

### 4.1 视图 Tab 切换

顶部一行 tab:`[ 向导 ] [ 自由表单 ] [ YAML ]`,默认「向导」。

```
┌─────────────────────────────────────────────────────────────────┐
│ 批量算例    [ 向导 ] [ 自由表单 ] [ YAML ]   [Preset] [运行]    │
├─────────────────────────────────────────────────────────────────┤
│ <当前 tab 内容>                                                 │
├─────────────────────────────────────────────────────────────────┤
│ 状态: 12 cases  |  模板: /path/t.inp  |  v2 schema  ✓            │
└─────────────────────────────────────────────────────────────────┘
```

切换 tab 时**保留 ConfigStore**,只换渲染方式。

### 4.2 向导视图(4 步)

| Step | 内容 | 关键控件 |
|---|---|---|
| 1. 模板与输出 | template / output_dir / naming | 路径选择 + i18n label |
| 2. 选择 sweep 轴 | 左:变量树(分组 + 搜索) / 右:已选轴列表 | 变量树拖入 + 每轴值 widget |
| 3. (可选)条件依赖 | 条件列表,每条 when/then 子表单 | "添加条件" 按钮 |
| 4. 预览与运行 | case 数预估 + dry run 表格 + 运行按钮 | 大预览表 |

**值 widget 智能(per axis.kind)**:
- `enum_subset` → 弹出 checklist 多选 dialog(参考 `QListWidget` + `setSelectionMode(MultiSelect)`)
- `range` → 3 个 spinbox(min/max/step)
- `explicit_list` → 多行 QPlainTextEdit,逗号分隔

### 4.3 自由表单视图

**单页紧凑布局**,继承 PR #48 后的 cell widget 模型:
- 每行 = combo(变量) + 值 widget(按 kind 智能切换) + 删除按钮
- 顶部:Preset 切换器(`[ 默认 ▾ ] [保存] [管理]`)
- 底部:case 预估 + 运行按钮

### 4.4 YAML 视图

- 主区:`QPlainTextEdit`(等宽字体,行号,当前行高亮)+ YAML syntax 简单高亮(关键词着色)
- 左 sidebar:变量树 + preset 树
- 右 sidebar:实时 case 预览(随 YAML 文本变更重算)
- 底部:schema 校验状态(`✓ valid` / `✗ line N: ...`)

**校验机制**:YAML 文本变更后,后台跑 `yaml.safe_load` + `ConfigStore.from_dict()`,失败则显示错误,不让用户保存。

### 4.5 键盘快捷键

| 键 | 行为 |
|---|---|
| `Ctrl+1` | 切到向导 |
| `Ctrl+2` | 切到自由表单 |
| `Ctrl+3` | 切到 YAML |
| `Ctrl+S` | 保存当前 spec 为 YAML(弹保存对话框) |
| `Ctrl+R` | 运行(dry run 模式) |
| `Ctrl+Shift+R` | 实际运行 |
| `Ctrl+Shift+P` | 打开 preset 库管理对话框 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做(ConfigStore 历史栈) |

**撤销/重做**:ConfigStore 维护 `history: List[ConfigStore]`,容量 50。任意 View 修改 → push 历史。

---

## §5 Preset 库

### 5.1 存储

| 类型 | 位置 |
|---|---|
| 用户 preset | `~/.config/cfd--changer/presets/<name>.yaml` |
| 团队 preset | 由 `~/.config/cfd--changer/config.yaml` 里的 `team_preset_dirs: [...]` 列表决定,默认空 |

### 5.2 preset 文件 schema

```yaml
# presets/<name>.yaml
version: 2
name: incompressible-baseline
tags: [baseline, low-speed]
created_at: 2026-06-16T10:00:00
updated_at: 2026-06-16T10:00:00
author: onemuggle   # 可选

sweeps:
  turbulence: [sst, kw]
  mach:
    range: [0.0, 0.6, 0.2]

conditions: []
```

**不含** `template` / `output_dir` / `naming`(preset 与具体模板无关)。

### 5.3 PresetLibrary API(纯 Python,无 Qt)

```python
class PresetLibrary:
    def __init__(self, user_dir: Path, team_dirs: List[Path]) -> None: ...
    def list(self) -> List[PresetMeta]: ...           # 含来源标记 (user | team:<name>)
    def get(self, ref: str) -> PresetContent: ...    # ref = "name" 或 "team:<name>"
    def save(self, name: str, content: PresetContent, *, overwrite: bool = False) -> Path: ...
    def delete(self, ref: str) -> None: ...          # 仅允许删 user preset
    def search(self, query: str) -> List[PresetMeta]: ...  # 搜 name + tags
```

错误:
- 不存在的 ref → `KeyError`
- 同名 user preset 已存在 + 未传 overwrite → `FileExistsError`
- 删 team preset → `PermissionError`

### 5.4 GUI 集成

- 侧边栏(向导/表单/YAML 三视图都有)显示 preset 树,分组:`我的` / `团队:<dir>` / `最近`
- 双击 = 加载到当前 ConfigStore(merge semantics 见 §3.4)
- 拖到已选轴列表 = 替换 sweeps
- 右键菜单:打开位置 / 删除(仅 user preset)/ 编辑

---

## §6 引擎层改造(`inp_tool/sweep.py`)

### 6.1 新增 API

```python
# 解析后的中间表示(由 parse_condition 产出)
@dataclass(frozen=True)
class ConditionPredicate:
    """单变量 op val。"""
    key: str
    op: str        # "<", "<=", "==", "!=", ">=", ">"
    value: Any     # 已按 YAML 推断的类型(int/float/str/bool)

@dataclass(frozen=True)
class ConditionWhen:
    """多变量 AND 关系;predicates 空 → 永真。"""
    predicates: Tuple[ConditionPredicate, ...]

@dataclass(frozen=True)
class ConditionThen:
    disable_axes: Tuple[str, ...] = ()              # 该 case 跳过这些轴
    set_extra: Tuple[Tuple[str, str], ...] = ()    # 该 case 注入 (key,value) 到 .inp

@dataclass(frozen=True)
class ConditionalRule:
    when: ConditionWhen
    then: ConditionThen

def parse_condition(when_dict: Dict[str, str]) -> ConditionWhen:
    """YAML 原始 when: {key: '<op><val>'} → 解析后的 ConditionWhen。
    例: {'mach': '<1', 'reynolds': '>=1e6'}
        → ConditionWhen(predicates=(
              ConditionPredicate('mach', '<', 1),
              ConditionPredicate('reynolds', '>=', 1e6),
          ))
    """

def evaluate_condition(when: ConditionWhen, case: Dict[str, Any]) -> bool: ...

def expand_with_conditions(
    spec: "SweepSpecV2",  # 新版 spec,含 sweeps + conditions
) -> List[ExpandedCase]:
    ...

@dataclass(frozen=True)
class ExpandedCase:
    """含 set_extra 应用结果;disable_axes 已过滤(不出现)。"""
    values: Dict[str, Any]              # case 主体
    extras: Dict[str, str] = ()         # 该 case 注入到 .inp 的 (k,v) 对

# 旧 API 保留:
def expand_cartesian(spec: SweepSpec) -> List[Dict[str, Any]]: ...  # v1 路径
```

**语义要点**:
- `evaluate_condition` 多 predicate → 全部 AND;空 predicates → True
- `expand_with_conditions` 对笛卡尔积每个 case 跑所有 condition 的 `when`;若某 condition 不满足 → 跳过该 case;满足 → 应用 `then`:从 case.values 删除 `disable_axes` 列、`extras` 字段填 `set_extra` 的内容
- `set_extra` 仅是字面量键值对(暂不支持表达式);后续 sweep 生成器在 apply 时把它注入到生成的 .inp 文件(通过 `inp_tool.editor` API)

### 6.2 兼容性

- `expand_cartesian(spec: SweepSpec)` 保持现有签名不变(继续给 v1 YAML 用)
- `expand_with_conditions(spec: SweepSpecV2)` 是新函数
- 控制器层根据 spec.version 选择调用哪个

### 6.3 错误处理

| 情况 | 行为 |
|---|---|
| condition 中 op 未知 | 抛 `ValueError("unknown operator 'foo'")` |
| condition 引用不存在的轴 | 抛 `ValueError(f"unknown axis '{key}' in condition")` |
| range 的 step = 0 | 抛 `ValueError("range step must be non-zero")` |
| range 的 min > max | 抛 `ValueError("range min must be <= max")` |
| 枚举子集含未声明值 | 抛 `ValueError(f"unknown enum value '{x}' for axis '{key}'; expected one of {valid}")` |

---

## §7 迁移路径

### 7.1 v1 → v2 自动升级

读取 YAML 时:

```python
def upgrade_v1_to_v2(v1_dict: Dict[str, Any]) -> Dict[str, Any]:
    v2 = dict(v1_dict)
    v2["version"] = 2
    # sweeps 全部按 explicit_list 处理(v1 只有这一种)
    v2.setdefault("conditions", [])
    v2.setdefault("preset", None)
    return v2
```

写入 YAML 时:**永远写 v2**(单向前向)。不做 v2 → v1 回退。

### 7.2 旧 GUI 兼容

| 路径 | 行为 |
|---|---|
| 旧 `sweep_form.py` | 被新 `SweepFormView` 取代,但通过 import 兼容别名 `from inp_tool_gui.widgets.sweep_form import SweepForm` 保留(让集成测试不破) |
| 旧 `SweepController`(有 `_sweep` 等内部属性) | 保留为 `SweepControllerLegacy`,新代码用 `SweepControllerV2` |

### 7.3 迁移测试

- 加载 5 个真实老 sweep.yaml(从 `examples/` 和用户历史收集),确认 round-trip 后语义不变
- GUI 启动时检测 `~/.config/cfd--changer/migration_log.json` 是否提示过升级

---

## §8 测试策略

### 8.1 单元测试(纯 Python,无 Qt)

| 模块 | 测试数(预估) | 覆盖目标 |
|---|---|---|
| `ConfigStore.replace` 不可变性 | 5 | 100% |
| `ConfigStore` ↔ `dict` ↔ `YAML` round-trip | 8 | 95% |
| `parse_condition` AST | 6 | 100% |
| `evaluate_condition` 真值表 | 10 | 100% |
| `expand_with_conditions` 笛卡尔积 + 过滤 | 12 | 90%(含边界) |
| `PresetLibrary` CRUD | 8 | 95% |
| `upgrade_v1_to_v2` | 5 | 100% |

### 8.2 集成测试(需要 QApplication)

| 测试 | 数量 |
|---|---|
| 三 View ↔ ConfigStore 同步(改 A 看 B / C) | 3 |
| 向导 step 间数据流 | 4 |
| YAML 视图实时校验 + 错误高亮 | 3 |
| Preset 库 GUI 集成(双击 / 拖拽 / 删除) | 4 |

### 8.3 端到端测试

| 测试 | 数量 |
|---|---|
| 完整 sweep 工作流(向导→保存→加载→运行) | 2 |
| 迁移 E2E(老 YAML → 新 GUI → 运行) | 2 |
| 三 View 切换不丢数据 | 1 |

### 8.4 覆盖率目标

- `inp_tool_gui/models/`:**100%**(纯逻辑)
- `inp_tool_gui/controllers/sweep_controller_v2.py`:**95%**
- `inp_tool/sweep.py` 新增部分:**90%**
- 整体 GUI widgets:**80%**(Qt 信号相关允许分支覆盖)

### 8.5 i18n

- 新增 key 约 20 条(`sweep.wizard.stepN.*`, `sweep.condition.*`, `sweep.preset.*` 等)
- 中英两套;走现有 `tg()` 函数
- 不引入新 i18n 机制

---

## §9 阶段交付(独立 PR)

| Phase | 范围 | 不破坏什么 | 估时 | PR 边界 |
|---|---|---|---|---|
| **P1 引擎 v2** | `inp_tool/sweep.py` 新增 `ConditionWhen/Then/Rule` + `parse_condition` + `evaluate_condition` + `expand_with_conditions` + v2 schema dataclass | 旧 `expand_cartesian` 不动;旧 `CaseSweep.from_dict` 不动 | 0.5d | 引擎层,纯函数 |
| **P2 ConfigStore + PresetLibrary** | `models/config_store.py` + `preset_library.py` + `controllers/sweep_controller_v2.py` | 旧 `SweepForm` widget 不动;旧 controller 不动 | 1d | 纯 Python,无 GUI |
| **P3 自由表单视图重写** | `widgets/sweep_form_view.py`(新)+ 旧 sweep_form.py 保留 import 兼容 | 旧 sweep_form.py 仍可工作(主路径切到新) | 1d | UI 替换;旧 widget 标记 deprecated |
| **P4 向导视图** | `widgets/sweep_wizard.py` + 4-step 流程 | 同 P3 | 1.5d | UI 新增;不影响其他 tab |
| **P5 YAML 视图** | `widgets/sweep_yaml_editor.py` + sidebar + 实时校验 | 同 P3 | 1d | UI 新增 |
| **P6 迁移工具 + 默认 preset** | `cli migrate-v1` + 内置 3 个默认 preset | 不破 | 0.5d | CLI 命令 + 资源文件 |
| **P7 整合 + 文档** | 顶部 tab 接入、键位、CHANGELOG、user-manual、technical/sweep/ | 旧 tab 行为兜底 | 1d | UI 整合 + docs |

总估时:**~6.5 个工作日**。每 Phase 独立 PR + 3 平台 CI + 1 human review。

---

## §10 成功标准

1. **枚举子集**:用户能在 3 次点击内完成"只勾选 sst 和 kw",无需手敲或删字
2. **变量发现**:用户能在搜索框输入 `mach`,立即看到所有 mach 相关轴(分组显示)
3. **条件依赖**:用户能用向导 step 3 添加一条 `if mach < 1 then disable turbulence`,并在预览看到 case 数减少
4. **Preset 库**:用户能把当前 sweep 保存为 preset,下次启动自动出现在「我的」
5. **三视图同步**:在 YAML 视图改一个值,切到向导/表单立即看到同步
6. **键盘效率**:研究员用 `Ctrl+1/2/3` + `Ctrl+S` + `Ctrl+R` 完成一次 sweep 不需要摸鼠标
7. **迁移**:加载 v1 老 YAML 不报错,自动升级,行为不变
8. **测试**:新增代码覆盖率达 §8.4 目标

---

## §11 子 spec 入口(后续立专项)

本文是 umbrella spec。下列子主题本期不展开,实现 Phase 时各自立 spec:

| 子主题 | 拟立 spec 文件 | 实现 Phase |
|---|---|---|
| ConfigStore 数据模型 | `2026-06-XX-config-store-design.md` | P2 |
| PresetLibrary schema + 团队共享机制 | `2026-06-XX-preset-library-design.md` | P2 / P6 |
| condition 表达式语法详细语义 | `2026-06-XX-sweep-conditions-design.md` | P1 / P4 |
| YAML 编辑器 syntax highlight + schema lint | `2026-06-XX-yaml-editor-design.md` | P5 |
| 撤销/重做历史栈 | `2026-06-XX-config-undo-design.md` | P2 |
| 迁移工具 v1→v2 CLI | `2026-06-XX-migrate-v1-to-v2-design.md` | P6 |

---

## §12 风险与开放问题

| 风险/问题 | 影响 | 缓解 |
|---|---|---|
| `QScintilla` 跨平台可用性 | YAML 编辑器体验差 | 用 `QPlainTextEdit` + 自绘行号 + 关键词着色,不强依赖 QScintilla |
| 条件依赖的 AST 复杂度失控 | over-engineering | 显式限制:仅单 op + AND,不做 OR / 嵌套 / 函数 |
| Preset 团队共享的 Git 冲突 | 用户协作痛苦 | 提示冲突并要求手动 merge;不在本期内做自动 conflict resolution |
| 三视图同时维护带来 UI 代码膨胀 | 难以维护 | 公共组件(变量树、preset 侧栏)提取为独立 widget |
| v1 旧 controller 留作兼容增加负担 | 代码冗余 | P3 后旧 controller 不再被新代码引用,下个大版本删 |
| 撤销/重做栈内存占用 | 大 sweep 历史吃内存 | 上限 50 条;超过丢最早的 |
| 用户可能在 YAML 视图写错 schema | 报错体验差 | 实时 lint + 友好错误信息(指出 line + column + 期望值) |

---

## §13 后续工作(不在本期范围)

- 云端 preset 同步 / 团队协作
- 多模板对比 sweep(同一 sweep 配置套不同模板)
- Sweep 结果可视化(参数 → 性能曲线、热力图)
- Sweep 模板库(CFD 工程师共享的 preset 仓库)
- 与外部工具(HFSS / OpenFOAM / StarCCM+)的参数同步
- 远程执行 sweep(Linux server + 本地 GUI 控制)
