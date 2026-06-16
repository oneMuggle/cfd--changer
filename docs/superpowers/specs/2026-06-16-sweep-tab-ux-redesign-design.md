**Status:** Draft (待用户 review)
**Date:** 2026-06-16
**Scope:** inp_tool_gui Sweep 标签页(批量算例)
**Audience:** 维护者(单人项目 onemuggle)
**Goal:** 把 Sweep 标签页从「自由文本填表」升级为「带变量发现 + 类型约束 + 失效保护」的工程化表单,**不破坏**后端 sweep 系统 / 不改 .inp 解析层 / 不改 YAML 旧契约

---

# Sweep 标签页 UX 重构设计

## §1 背景与目标

### 1.1 现状(`sweep_form.py` v0.16.1)

- 顶部 3 个 `QLineEdit`(模板 / 输出 / 命名)**无前置 label**,用户不知输入啥
- 轴表是 2 列 `QTableWidget`:**第 0 列是自由 `QTableWidgetItem`**,用户键入的轴名不与模板 .inp 关联
- 值列是 `,` 分隔纯文本,**无类型 / 范围约束**
- 类型推断只在 `_collect_to_dict` → `_parse_scalar` 静默执行,UI 层不显示结果
- 模板切换 / 加载旧 YAML 后,**未知轴静默保留**,运行时报错才暴露

### 1.2 目标

| 维度 | 当前 | 目标 |
|---|---|---|
| 顶部输入框前置 label | ❌ 无 | ✅ 3 个 label(模板 / 输出 / 命名) |
| 轴名来源 | 自由键入 | ✅ 从模板 .inp 自动发现 + 3 个枚举轴(下拉选) |
| 值类型校验 | ❌ 无 | ✅ int / float / str 失焦校验,枚举值下拉 |
| 范围约束 | ❌ | ❌ 仍不做(YAGNI,`.inp` 不存 min/max) |
| 失效轴保护 | ❌ 静默 | ✅ 红底标记 + 禁用运行 + 鼠标悬停提示 |
| 加载旧 YAML | ❌ 静默 | ✅ 与模板切换一致:红底 + 禁用 |
| 空模板兜底 | — | ✅ 仅枚举轴可选,`.inp` 变量列表为空 |

### 1.3 不在范围

- ❌ 不改后端 sweep 系统(`inp_tool/sweep.py`):枚举识别 / 笛卡尔积 / CaseSweep 解析逻辑全部不动
- ❌ 不改 YAML 旧契约:旧 YAML 含未知轴仍可加载(只是 GUI 标记失效)
- ❌ 不做 min/max 范围约束(`.inp` 不存)
- ❌ 不改核心解析层(`inp_tool/parser.py` / `model.py`)
- ❌ 不改 `controllers/sweep_controller.py` 已暴露 API(`load_from_dict` / `load_from_yaml` / `load_from_json` / `case_count` / `last_report` / `template`)
- ❌ 不重写整个 Sweep 表单(只改交互细节,保留「加载 / 保存 / 运行 / 结果表」结构)

---

## §2 架构 & 组件

### 2.1 涉及文件

| 文件 | 改动类型 | 用途 |
|---|---|---|
| `inp_tool_gui/widgets/sweep_form.py` | **重构** | 顶部 label + QComboBox cell + 类型校验 |
| `inp_tool_gui/widgets/sweep_var_combo.py` | **新增** | `VarSpec` dataclass + `enumerate_vars(template_path)` 纯函数(无 PySide2,可在测试中独立 import) |
| `inp_tool_gui/controllers/sweep_controller.py` | **小扩** | 新增 `available_vars(template_path) -> List[VarSpec]`(import sweep_var_combo + 加 cache) |
| `inp_tool/i18n_gui.py` | 加 key | `sweep.lbl.template/output/naming` + 错误提示 |
| `inp_tool/tests/test_gui_sweep_form.py` | **扩** | 新场景:combo / 类型 / 失效轴 / 未知轴 |
| `inp_tool/tests/test_gui_sweep_var_combo.py` | **新增** | 变量发现 + 类型元数据单测 |

### 2.2 VarSpec 数据类(sweep_var_combo.py 定义,纯 Python,无 PySide2)

```python
from dataclasses import dataclass
from typing import Optional, Tuple

@dataclass(frozen=True)
class VarSpec:
    """单变量的 UI 描述。

    - 枚举轴: block/keyword/value_idx 全为 None,enum_values 填合法 enum
    - 普通 .inp 变量: 填 block + keyword + value_idx,enum_values 为 None
    """
    key: str                                  # combobox 显示的标识符
    label: str                                # 类型化后的可读 label,如 "physics.reynolds [float] = 1.0e6"
    kind: str                                 # "enum" | "int" | "float" | "str"
    enum_values: Optional[Tuple[str, ...]] = None
    block: Optional[str] = None
    keyword: Optional[str] = None
    value_idx: Optional[int] = None
```

**关键约定**
- `key` 格式:**枚举轴** 用原轴名(`turbulence` / `energy` / `gas`);**普通轴** 用 `block.keyword[idx]` 形式(如 `physics.reynolds[0]`),同名多值用方括号表示值索引
- `kind` 顺序:enum > int > float > str(继承 `inp_tool.model.infer_type` 的 bool > int > float > str,但**本设计不暴露 bool**,因为 sweep 轴语义上更接近「物理参数」,布尔直接走 str)
- `label` 拼接规则:普通轴 = `"{block}.{keyword}[{idx}] [{kind}] = {template_value}"`;枚举轴 = `"{key} (枚举:{value1,value2,...})"`

### 2.3 controller 新方法

```python
class SweepController:
    def __init__(self):
        self._sweep = None
        self._last_report = None
        self._var_cache: Dict[Optional[str], List[VarSpec]] = {}

    def available_vars(self, template_path: Optional[str]) -> List[VarSpec]:
        """根据当前模板路径返回可选变量列表(枚举轴 + .inp 变量)。

        - template_path 为空 → 仅 3 个枚举轴
        - template_path 存在但解析失败 → 返回仅枚举轴(不缓存错误)
        - 否则 → 解析 .inp,列出所有 (block, keyword, value_idx) 组合

        缓存策略:同一 template_path(用 str 规范化)只解析一次。
        """
```

**缓存不变量**
- `template_path=None` 始终返回相同的「仅枚举轴」列表(共享 cache key)
- 文件被外部修改后(罕见),用户需重启 GUI 才能看到新变量 — 文档说明
- 解析失败的路径**不** 进 cache(避免错误信息持久化);下次调用时重试

### 2.4 widget 层 UI 决策

| 决策 | 选择 |
|---|---|
| 顶部 3 个输入框 | 加 `QLabel` 前置,i18n key 化 |
| 轴表第 0 列 | `QComboBox` 替代 `QTableWidgetItem`,用 `setCellWidget` 嵌入 |
| 轴表第 1 列 | `QLineEdit` 替代 `QTableWidgetItem`,用 `setCellWidget` 嵌入 |
| 枚举轴值 cell | **不可编辑** `QLabel`(显示「,」分隔的合法 enum 值) |
| 普通轴值 cell | `QLineEdit`,失焦校验 |
| 失效轴视觉 | 行背景色 `#FFD6D6`(浅红),tooltip 解释 |

---

## §3 数据流

### 3.1 两条独立流

```
[模板路径 QLineEdit 失焦]
    └─→ controller.缓存 template
        └─→ 触发 _refresh_axes_options()
            └─→ controller.available_vars(self._template)
            └─→ 重建每行 QComboBox items(仅 items,不动已选 key)

[用户改 QComboBox]
    └─→ 更新行对应的 VarSpec
        └─→ 按 kind 重置值 cell(enum 变 label / int/float/str 变 QLineEdit)
        └─→ 触发 _sync_form_to_controller(现有)
```

### 3.2 关键不变量

1. `available_vars` 是**纯函数 + 缓存**;同一 template_path(字符串相等)不重复解析 .inp
2. controller 缓存 `_template` 字段**独立**于 `CaseSweep.template`(后者是 sweep 业务字段,由 `load_from_dict` 设置)
3. **切换模板时**:只重建 combobox items,**不** 自动修改已选行(失效警告机制处理,见 §4.3)
4. **`_sync_form_to_controller` 不动**:现有 `editingFinished` / `itemChanged` 触发逻辑保留,只是数据源 cell 变了

### 3.3 流程图

```
用户输入模板路径
    │
    ▼
QLineEdit.editingFinished
    │
    ▼
_sync_form_to_controller  (现有,不动)
    │
    ▼
controller.load_from_dict(...)
    │
    ▼
_refresh_axes_options()   (新增)
    │
    ▼
controller.available_vars(template)
    │
    ▼
遍历每行 → setCellWidget(0, new QComboBox(items=varspecs))
         → setCellWidget(1, new QLineEdit 或 QLabel by kind)
         → 检查失效(已在 varspecs.key 集合的保留;不在的红底)
```

---

## §4 UI 行为 & 校验

### 4.1 顶部 3 个输入框(全加前置 label)

```
[模板路径]   [________________________] [浏览...]
[输出目录]   [________________________] [浏览...]
[命名模式]   [case_{alpha}_{mach}___________]
```

| Label i18n key | 默认中文 |
|---|---|
| `sweep.lbl.template` | 「模板路径」 |
| `sweep.lbl.output` | 「输出目录」 |
| `sweep.lbl.naming` | 「命名模式」 |

### 4.2 轴表 — QTableWidget 2 列 + Cell Editor

| 列 | 控件 | 行为 |
|---|---|---|
| 0 — 变量 | `QComboBox` (setCellWidget) | items 来自 `controller.available_vars(template)`;currentText 变即触发 cell change |
| 1 — 值 | `QLineEdit` (setCellWidget) | 文本框,失焦校验;**枚举轴**自动变成不可编辑 label |

### 4.3 类型校验(失焦时)

| VarSpec.kind | 输入格式 | 校验逻辑 | 失败反馈 |
|---|---|---|---|
| `enum` | 不可编辑(显示「,」分隔的合法 enum 值标签) | combobox 选即约束 | 无运行时错误 |
| `int` | 整数,「,」分隔 | `int(s.strip())` 全部成功 | 红色 cell 背景 + 状态栏「轴 X 第 N 个值不是整数」 |
| `float` | 浮点,「,」分隔(支持 `1.0` / `1e6` / `1.0d-3`) | `float(s.replace('d','e').replace('D','E'))` 全部成功 | 同上,提示「不是浮点数」 |
| `str` | 任意文本,「,」分隔 | 无校验(空字符串允许) | — |

**复用现有工具**:
- 整数 / 浮点校验直接调 `inp_tool.value_editor._convert` 的 `int` / `float` 分支
- 不重写类型推断,避免与 `inp_tool.model.infer_type` 行为分叉

### 4.4 失效轴警告机制(模板切换 / 加载 YAML)

**触发条件**:
- (a) 用户改模板路径并失焦
- (b) `_load_yaml_path` / `_load_json_path` 加载完

**流程**:
1. 调 `controller.available_vars(self._template)` 取当前合法 key 集合
2. 遍历所有已填行:
   - 行的 combobox currentText 在合法集合 → 正常显示
   - **不在合法集合** → 整行背景色 `#FFD6D6`,tooltip「此变量不在当前模板中,请删除或重新选模板」
3. 状态栏:`「有 N 个轴未识别,无法运行」`(N > 0 时)
4. 「运行 / Dry run」按钮:`setEnabled(N == 0)`,鼠标悬停 tooltip 解释

**关键不变**:
- 加载 YAML 仍**保留**未知轴(不删),但红底 + 禁用 — 与用户的「警告 + 保留」决定一致
- 用户可手动删除失效行,或重新选模板让轴重新合法

### 4.5 空模板兜底

- 模板路径为空 → `controller.available_vars(None)` 返回 3 个枚举轴 → 表格 combobox 只这 3 项
- 用户可正常添加 `turbulence` / `energy` / `gas` 轴并运行
- `.inp` 变量不会出现(因为没模板可解析)

### 4.6 运行时机

| 条件 | 运行按钮 | 提示 |
|---|---|---|
| 模板为空 + 无轴 | 禁用 | 状态栏「请先填模板路径或加轴」 |
| 有失效轴(N > 0) | 禁用 | tooltip「请先修复失效轴」 |
| 全部合法 + 至少 1 个轴 | 启用 | 正常 |
| 值类型错误(单元级) | **仍可运行** | 后端 `_normalize_axis_value` 再校验一次,UI 提示是前置;YAML 加载 / 实时编辑时不阻断 |

---

## §5 测试策略

### 5.1 现有测试基线

- `inp_tool/tests/test_gui_sweep_form.py` — 已有(需保留并扩展)
- `inp_tool/tests/test_gui_sweep_controller.py` — 已有(需保留并扩展)
- `inp_tool/tests/test_sweep*.py` — 20+ 文件,后端覆盖已厚(**不动**)

### 5.2 新增 / 修改

| 测试文件 | 测试场景 |
|---|---|
| `test_gui_sweep_var_combo.py` (新) | (a) `available_vars(None)` 返回 3 个枚举轴,kind 全部 enum,enum_values 非空;(b) `available_vars("不存在的路径.inp")` 返回仅枚举轴,不抛异常;(c) `available_vars(valid_path)` 列出 .inp 变量,key 格式为 `block.keyword[idx]`,label 含模板当前值;(d) 同 template_path 第二次调用不重复解析(测 cache 命中,可注入 mock);(e) VarSpec 不可变(frozen=True) |
| `test_gui_sweep_form.py` (扩) | (a) 顶部 3 个 label 存在且显示 i18n 文案;(b) 模板变更后 combobox items 更新(测 `_refresh_axes_options` 触发);(c) 枚举轴 cell 不可编辑、显示合法值列表;(d) 整型轴输入「abc」红框 + 状态栏报错,运行按钮禁用;(e) 浮点轴输入「1.0d-3」接受;(f) 浮点轴输入「abc」红框;(g) 失效轴红底 + 运行按钮禁用 + tooltip 含「未识别」;(h) 空模板时 combobox 只有 3 个枚举轴项;(i) 加载含未知轴的 YAML 红底 + 禁用运行;(j) 删除失效行后状态栏 N 减 1 |
| `test_gui_sweep_controller.py` (扩) | (a) `available_vars` 缓存命中(同 path 二次调用不打文件);(b) cache key 用 `str(path)` 规范化(Windows / Linux 路径分隔差异) |

### 5.3 覆盖率目标

- 维持 / 达到 ≥ 80%(CLAUDE.md / 测试规则)
- TDD 顺序:
  1. 先写 `test_gui_sweep_var_combo.py` 5 个场景 → 红灯
  2. 最小实现 `available_vars` + `VarSpec` → 绿灯
  3. 写 `test_gui_sweep_form.py` 扩展 10 个场景 → 红灯
  4. 重构 `sweep_form.py`(加 label / combo cell / 类型校验) → 绿灯
  5. 写 `test_gui_sweep_controller.py` 缓存场景 → 红灯 → 补 `__init__` 缓存字段 → 绿灯

### 5.4 兼容性测试

- 跑全量 `test_sweep*.py` 确保后端不破
- 跑 `test_gui_main_window.py` 确保主窗口集成不破
- 跑 `test_gui_main_window_integration.py` 确保 4 标签页集成不破

---

## §6 风险与权衡

| 风险 | 缓解 |
|---|---|
| `setCellWidget` 替换 cell 后 `itemChanged` 信号不触发 | 用 `currentIndexChanged` 信号替代(cell widget 自己的信号) |
| 切换模板时重建 combobox,已选的 currentText 可能丢失 | 重建后用「已选 key」反查 items 中匹配的,设为 current;不匹配则红底失效 |
| 缓存 .inp 解析结果,文件外部修改不感知 | 文档说明 + 状态栏可加「刷新变量」按钮(YAGNI 先不做) |
| 自由文本轴名彻底废除,旧工作流被破坏 | YAML / 加载旧 GUI 输出 100% 兼容(只标记失效,不删);但用户不能再键入新轴名 — 这是**设计决定**(用户「不要自由输入」) |
| QComboBox items 多时(>50)性能 | 单个 .inp 变量数 ≪ 100,实测无问题;若未来超,加 combobox 内置 filter |
| 「运行按钮禁用」 vs 「失效应禁用 vs 类型错不禁用」 规则不一致 | 文档化:失效轴=结构错(必须修);类型错=内容错(后端兜底) |

---

## §7 验收标准

实现完成后,以下 5 条全部满足才视为完成:

1. **顶部 3 个 label 可见**:启动 GUI,打开 Sweep 标签页,可见「模板路径 / 输出目录 / 命名模式」三个 label
2. **轴名可下拉选**:在 `examples/mcfd.inp` 上添加轴,combobox 弹出含所有 `block.keyword[idx]` 项 + 3 个枚举轴
3. **类型校验生效**:整型轴输入「abc」,失焦后 cell 红底 + 状态栏「不是整数」;浮点轴输入「1.0d-3」接受
4. **失效轴保护**:加载含未知轴的 YAML,该行红底 + 运行按钮禁用 + tooltip 解释
5. **覆盖率**:新增 + 修改测试覆盖 ≥ 80%(全仓覆盖率不下降)

---

## §8 实施步骤(待 writing-plans 阶段细化)

> 这里是**粗粒度**步骤,具体每步的「文件 + 签名 + 测试」留到 writing-plans skill 输出。

- [ ] 步骤 1:在 `inp_tool_gui/widgets/sweep_var_combo.py` 定义 `VarSpec` dataclass + `enumerate_vars(template_path)` 纯函数
- [ ] 步骤 2:在 `SweepController` 加 `available_vars` 包装(calls `enumerate_vars` + cache)
- [ ] 步骤 3:写 `test_gui_sweep_var_combo.py` 5 个场景 + 实现
- [ ] 步骤 4:在 `i18n_gui.py` 加 `sweep.lbl.template/output/naming` + 错误提示 key
- [ ] 步骤 5:重构 `sweep_form.py` — 顶部 label
- [ ] 步骤 6:重构 `sweep_form.py` — 轴表 QComboBox cell + QLineEdit cell
- [ ] 步骤 7:重构 `sweep_form.py` — 类型校验(失焦)
- [ ] 步骤 8:重构 `sweep_form.py` — 失效轴扫描 + 红底 + 禁用运行
- [ ] 步骤 9:写 `test_gui_sweep_form.py` 扩展 10 个场景
- [ ] 步骤 10:写 `test_gui_sweep_controller.py` 缓存场景
- [ ] 步骤 11:跑全量测试 + 检查覆盖率
- [ ] 步骤 12:更新 CHANGELOG / docs/user-manual/ 对应章节

---

## §9 参考

- 探索小结:见本次 brainstorming 阶段的代码探索(`sweep_form.py` / `sweep_controller.py` / `sweep.py` / `model.py`)
- 现有 spec:`docs/superpowers/specs/2026-06-15-project-optimization-roadmap-design.md`
- 测试模式:参考 `test_gui_sweep_form.py` 现有 offscreen 风格
- I18n key 命名:沿用 `sweep.lbl.*` / `sweep.live.*` / `sweep.btn.*` 既有前缀
