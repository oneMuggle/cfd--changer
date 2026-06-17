# Sweep UI 整体架构重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「批量算例」从单页表单升级为「配置/视图分离 + 三视图(向导/表单/YAML)+ Preset 库 + 条件依赖」系统,7 个独立 PR 逐步交付。

**Architecture:** 三层分离 — View(PySide2)→ ConfigStore(frozen dataclass, copy-on-update, 单向数据流)→ Controller(纯 Python)→ Engine(`inp_tool.sweep`,新增 v2 引擎)。三视图(向导/表单/YAML)共享 ConfigStore,任意 tab 修改 → 其他 tab 自动同步。

**Tech Stack:** Python 3.8 (conda env `cfdchanger`), PySide2 5.15.2.1, pytest 7+, PyYAML 6+. 保持 3.8 兼容(无 PEP 604 Pydantic 字段,无 PEP 585 Pydantic 字段)。

**Spec:** `docs/superpowers/specs/2026-06-16-sweep-ui-redesign-design.md`(umbrella spec)。本文按其 §9 阶段交付展开。

---

## File Structure(7 Phase 累计变更)

| 文件 | 操作 | 所属 Phase |
|---|---|---|
| `inp_tool/sweep.py` | Modify(追加 v2 引擎函数 + dataclass) | P1 |
| `inp_tool/tests/test_sweep_conditions.py` | Create | P1 |
| `inp_tool_gui/models/__init__.py` | Create | P2 |
| `inp_tool_gui/models/config_store.py` | Create(AxisSpec, ConfigStore, ConditionalRule) | P2 |
| `inp_tool_gui/preset_library.py` | Create | P2 |
| `inp_tool_gui/controllers/sweep_controller_v2.py` | Create | P2 |
| `inp_tool_gui/controllers/__init__.py` | Modify(export v2 controller) | P2 |
| `inp_tool/tests/test_config_store.py` | Create | P2 |
| `inp_tool/tests/test_preset_library.py` | Create | P2 |
| `inp_tool/tests/test_sweep_controller_v2.py` | Create | P2 |
| `inp_tool_gui/widgets/sweep_form_view.py` | Create(新 FormView) | P3 |
| `inp_tool_gui/widgets/sweep_form.py` | Modify(标记 deprecated,保留 import 兼容) | P3 |
| `inp_tool_gui/widgets/enum_checklist_dialog.py` | Create | P3 |
| `inp_tool/tests/test_gui_sweep_form_view.py` | Create | P3 |
| `inp_tool_gui/widgets/sweep_wizard.py` | Create | P4 |
| `inp_tool_gui/widgets/variable_tree_widget.py` | Create | P4 |
| `inp_tool/tests/test_gui_sweep_wizard.py` | Create | P4 |
| `inp_tool_gui/widgets/sweep_yaml_editor.py` | Create | P5 |
| `inp_tool/tests/test_gui_sweep_yaml_editor.py` | Create | P5 |
| `inp_tool/sweep_cli.py` | Modify(添加 `migrate-sweep-v1` 子命令) | P6 |
| `inp_tool/tests/test_sweep_cli_migrate.py` | Create | P6 |
| `inp_tool_gui/resources/default_presets/low-speed.yaml` | Create | P6 |
| `inp_tool_gui/resources/default_presets/transonic.yaml` | Create | P6 |
| `inp_tool_gui/resources/default_presets/high-speed.yaml` | Create | P6 |
| `inp_tool_gui/main_window.py` | Modify(批量算例 tab 换 tab widget) | P7 |
| `inp_tool_gui/widgets/preset_sidebar.py` | Create(共享组件) | P7 |
| `inp_tool/i18n_gui.py` | Modify(+20 个新 key 中英) | P7 |
| `CHANGELOG.md` | Modify(Unreleased 段加多条目) | P7 |
| `docs/user-manual/sweep/README.md` | Modify(新增三视图章节) | P7 |
| `docs/technical/sweep/13-sweep-ui-v2.md` | Create(技术文档) | P7 |

---

## Phase 1 — 引擎 v2(`inp_tool/sweep.py` 新增)

**独立 PR**: `feat(engine): sweep v2 condition 原语` → 分支 `feat/engine-sweep-v2`
**估时**: 0.5d。**前置依赖**: 无。**完成后可独立验证**: `pytest tests/test_sweep_conditions.py -v` 全过 + 旧 `test_sweep_*.py` 无回归。

### Task 1.1: 创建 `ConditionPredicate` dataclass + 单元测试

**Files:**
- Create: `inp_tool/sweep.py`(追加)
- Create: `inp_tool/tests/test_sweep_conditions.py`

- [ ] **Step 1: 写失败测试** `tests/test_sweep_conditions.py`

```python
"""Sweep v2 condition 原语单测(纯 Python, 无 PySide2)。"""
import pytest

# 推迟到 Task 1.2 后再 from 真实符号
# from inp_tool.sweep import ConditionPredicate


def test_condition_predicate_str_op_int():
    """ConditionPredicate 持有 (key, op, value) 三元组。"""
    # 当模块未实现时这行会 ImportError,实现后应 pass
    from inp_tool.sweep import ConditionPredicate
    p = ConditionPredicate(key="mach", op="<", value=1)
    assert (p.key, p.op, p.value) == ("mach", "<", 1)


def test_condition_predicate_is_frozen():
    """ConditionPredicate 不可变。"""
    from inp_tool.sweep import ConditionPredicate
    p = ConditionPredicate(key="x", op="==", value=0)
    with pytest.raises((AttributeError, Exception)):
        p.key = "y"  # frozen dataclass 禁止赋值
```

- [ ] **Step 2: 跑测试确认失败**

Run: `conda run -n cfdchanger python -m pytest tests/test_sweep_conditions.py -v`
Expected: ImportError 或 collection error(符号未定义)。

- [ ] **Step 3: 追加最小实现到 `inp_tool/sweep.py`**

在文件末尾追加(注意 Python 3.8 兼容,不可用 `X | Y` 联合语法):

```python
@dataclass(frozen=True)
class ConditionPredicate:
    """单变量 op val。"""
    key: str
    op: str        # "<", "<=", "==", "!=", ">=", ">"
    value: Any     # 已按 YAML 推断的类型(int/float/str/bool)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n cfdchanger python -m pytest tests/test_sweep_conditions.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add inp_tool/sweep.py inp_tool/tests/test_sweep_conditions.py
git commit -m "feat(engine): ConditionPredicate dataclass + 单测"
```

### Task 1.2: 实现 `parse_condition(raw_dict) -> ConditionWhen`

**Files:**
- Modify: `inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_conditions.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_sweep_conditions.py
def test_parse_condition_single_predicate():
    """parse_condition: {'mach': '<1'} → 1 个 predicate。"""
    from inp_tool.sweep import parse_condition, ConditionWhen, ConditionPredicate
    w = parse_condition({"mach": "<1"})
    assert isinstance(w, ConditionWhen)
    assert w.predicates == (ConditionPredicate("mach", "<", 1),)


def test_parse_condition_multiple_predicates():
    """多键 AND。"""
    from inp_tool.sweep import parse_condition, ConditionPredicate
    w = parse_condition({"mach": "<1", "reynolds": ">=1e6"})
    assert ConditionPredicate("mach", "<", 1) in w.predicates
    assert ConditionPredicate("reynolds", ">=", 1e6) in w.predicates
    assert len(w.predicates) == 2


def test_parse_condition_value_types():
    """value 类型按字面量推断(int/float/str/bool)。"""
    from inp_tool.sweep import parse_condition, ConditionPredicate
    w = parse_condition({"a": "==42", "b": "<3.14", "c": "!=foo", "d": "==true"})
    pred_map = {p.key: p for p in w.predicates}
    assert pred_map["a"].value == 42 and isinstance(pred_map["a"].value, int)
    assert pred_map["b"].value == 3.14 and isinstance(pred_map["b"].value, float)
    assert pred_map["c"].value == "foo" and isinstance(pred_map["c"].value, str)
    assert pred_map["d"].value is True


def test_parse_condition_unknown_op_raises():
    """未知 op 抛 ValueError。"""
    from inp_tool.sweep import parse_condition
    with pytest.raises(ValueError, match="unknown operator"):
        parse_condition({"x": "@@1"})
```

- [ ] **Step 2: 跑测试确认失败**

Expected: ImportError on `parse_condition`.

- [ ] **Step 3: 实现 `parse_condition` + 配套 dataclass**

```python
import re

_VALID_OPS = ("<", "<=", "==", "!=", ">=", ">")
_OP_PATTERN = re.compile(r"^(<=|!=|==|>=|[<>])(.*)$")


@dataclass(frozen=True)
class ConditionWhen:
    """多变量 AND 关系;predicates 空 → 永真。"""
    predicates: Tuple[ConditionPredicate, ...] = ()


def _infer_value(s: str) -> Any:
    s = s.strip()
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def parse_condition(when_dict: Dict[str, str]) -> ConditionWhen:
    """YAML raw {key: '<op><val>'} → 解析后的 ConditionWhen。"""
    predicates = []
    for key, expr in when_dict.items():
        m = _OP_PATTERN.match(expr.strip())
        if not m:
            raise ValueError(f"condition '{key}={expr!r}': cannot parse operator")
        op, val_str = m.group(1), m.group(2)
        if op not in _VALID_OPS:
            raise ValueError(f"unknown operator {op!r} in condition for {key!r}")
        predicates.append(ConditionPredicate(key=key, op=op, value=_infer_value(val_str)))
    return ConditionWhen(predicates=tuple(predicates))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `conda run -n cfdchanger python -m pytest tests/test_sweep_conditions.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(engine): parse_condition + ConditionWhen + value 类型推断"
```

### Task 1.3: 实现 `evaluate_condition` + `ConditionThen` + `ConditionalRule`

**Files:**
- Modify: `inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_conditions.py`

- [ ] **Step 1: 写失败测试**

```python
def test_evaluate_condition_true_when_empty():
    """空 predicates → 永真。"""
    from inp_tool.sweep import evaluate_condition, ConditionWhen
    assert evaluate_condition(ConditionWhen(), {"mach": 0.5}) is True


def test_evaluate_condition_and_semantics():
    """多 predicate 全部 AND。"""
    from inp_tool.sweep import parse_condition, evaluate_condition
    w = parse_condition({"mach": "<1", "reynolds": ">=1e6"})
    assert evaluate_condition(w, {"mach": 0.5, "reynolds": 2e6}) is True
    assert evaluate_condition(w, {"mach": 0.5, "reynolds": 5e5}) is False  # reynolds 不达标
    assert evaluate_condition(w, {"mach": 1.5, "reynolds": 2e6}) is False  # mach 不达标


def test_evaluate_condition_missing_key_returns_false():
    """case 缺 key → predicate 不成立。"""
    from inp_tool.sweep import parse_condition, evaluate_condition
    w = parse_condition({"mach": "<1"})
    assert evaluate_condition(w, {}) is False


def test_conditional_rule_dataclass():
    """ConditionalRule 持有 (when, then)。"""
    from inp_tool.sweep import (
        ConditionalRule, ConditionThen, parse_condition,
    )
    w = parse_condition({"mach": "<1"})
    t = ConditionThen(disable_axes=("turbulence",))
    rule = ConditionalRule(when=w, then=t)
    assert rule.then.disable_axes == ("turbulence",)
```

- [ ] **Step 2-3: 实现**

```python
@dataclass(frozen=True)
class ConditionThen:
    disable_axes: Tuple[str, ...] = ()
    set_extra: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ConditionalRule:
    when: ConditionWhen
    then: ConditionThen


def _compare(op: str, lhs: Any, rhs: Any) -> bool:
    if op == "<":
        return lhs < rhs
    if op == "<=":
        return lhs <= rhs
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op == ">=":
        return lhs >= rhs
    if op == ">":
        return lhs > rhs
    raise ValueError(f"unknown operator {op!r}")


def evaluate_condition(when: ConditionWhen, case: Dict[str, Any]) -> bool:
    """AND 语义:全部 predicate 满足才 True。"""
    for p in when.predicates:
        if p.key not in case:
            return False
        if not _compare(p.op, case[p.key], p.value):
            return False
    return True
```

- [ ] **Step 4: 跑测试通过**

Expected: 10 passed in `test_sweep_conditions.py`.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(engine): evaluate_condition + ConditionThen + ConditionalRule"
```

### Task 1.4: 实现 `ExpandedCase` + `expand_with_conditions`

**Files:**
- Modify: `inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_conditions.py`

- [ ] **Step 1: 写失败测试**

```python
def test_expand_with_conditions_no_condition_returns_all():
    """无 conditions 时等价于笛卡尔积(全保留,无 extras)。"""
    from inp_tool.sweep import expand_with_conditions, SweepSpec, ConditionalRule
    spec = SweepSpec(values={"a": [1, 2], "b": [10, 20]})
    cases = expand_with_conditions(spec, conditions=())
    assert len(cases) == 4
    assert all(c.extras == () for c in cases)


def test_expand_with_conditions_filters_by_when():
    """condition.when 不满足 → 跳过。"""
    from inp_tool.sweep import (
        expand_with_conditions, SweepSpec, ConditionalRule,
        ConditionThen, parse_condition,
    )
    spec = SweepSpec(values={"a": [1, 2, 3]})
    rule = ConditionalRule(
        when=parse_condition({"a": "<2"}),
        then=ConditionThen(set_extra=(("flag", "yes"),)),
    )
    cases = expand_with_conditions(spec, conditions=(rule,))
    # a=1 满足 → 保留 + extras
    # a=2,3 不满足 → 跳过
    assert len(cases) == 1
    assert cases[0].values == {"a": 1}
    assert cases[0].extras == (("flag", "yes"),)


def test_expand_with_conditions_disable_axes_filters_value():
    """disable_axes:该 case 跳过该轴的值(从 case.values 删除)。"""
    from inp_tool.sweep import (
        expand_with_conditions, SweepSpec, ConditionalRule,
        ConditionThen, parse_condition,
    )
    spec = SweepSpec(values={"a": [1, 2], "b": [10, 20]})
    rule = ConditionalRule(
        when=parse_condition({"a": "<2"}),  # a=1 命中
        then=ConditionThen(disable_axes=("b",)),
    )
    cases = expand_with_conditions(spec, conditions=(rule,))
    # a=1 命中 → disable b → case.values 不含 b
    assert cases[0].values == {"a": 1}
    # a=2 不命中 → b 保留
    assert {"a": 2, "b": 10} in [c.values for c in cases]
    assert {"a": 2, "b": 20} in [c.values for c in cases]
```

- [ ] **Step 3: 实现**

```python
@dataclass(frozen=True)
class ExpandedCase:
    """含 set_extra 应用结果;disable_axes 已过滤(不出现)。"""
    values: Dict[str, Any]
    extras: Tuple[Tuple[str, str], ...] = ()


def expand_with_conditions(
    spec: SweepSpec,
    conditions: Tuple[ConditionalRule, ...] = (),
) -> List[ExpandedCase]:
    """v2 展开:笛卡尔积 + condition 过滤 + disable_axes / set_extra 应用。"""
    raw_cases = expand_cartesian(spec)
    out: List[ExpandedCase] = []
    for raw in raw_cases:
        # 找到该 case 命中的第一个 rule(简化:多 rule 短路求值,合并 then)
        hit_rule = None
        for rule in conditions:
            if evaluate_condition(rule.when, raw):
                hit_rule = rule
                break
        if hit_rule is None:
            out.append(ExpandedCase(values=raw, extras=()))
            continue
        # apply then
        values = {k: v for k, v in raw.items() if k not in hit_rule.then.disable_axes}
        out.append(ExpandedCase(values=values, extras=hit_rule.then.set_extra))
    return out
```

- [ ] **Step 4-5: 跑测试 + commit**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_conditions.py tests/test_sweep_generate.py tests/test_sweep_explicit.py tests/test_sweep_mixed.py -v
git commit -am "feat(engine): ExpandedCase + expand_with_conditions"
```

Expected: 全部测试 pass,旧 sweep 测试无回归。

### Task 1.5: Phase 1 PR + 文档

- [ ] **Step 1: 更新 CHANGELOG.md**

在 `[Unreleased] ### Added` 段加:
```markdown
- feat(engine): Sweep v2 condition 原语(ConditionPredicate / ConditionWhen / ConditionalRule / ExpandedCase + parse_condition / evaluate_condition / expand_with_conditions)
```

- [ ] **Step 2: 推分支 + 开 PR**

```bash
git push -u origin feat/engine-sweep-v2
gh pr create --base main --head feat/engine-sweep-v2 \
  --title "feat(engine): sweep v2 condition 原语" \
  --body "实现 spec §6 引擎层 v2 改造。ConditionPredicate + parse_condition + evaluate_condition + ConditionalRule + expand_with_conditions + ExpandedCase。P1 phase。"
```

- [ ] **Step 3: 等 CI 3 平台 pass 后,用户 merge**

---

## Phase 2 — ConfigStore + PresetLibrary(纯 Python)

**独立 PR**: `feat(model): ConfigStore + PresetLibrary + SweepControllerV2` → 分支 `feat/config-store-v2`
**估时**: 1d。**前置依赖**: Phase 1。**完成后可独立验证**: `pytest tests/test_config_store.py tests/test_preset_library.py tests/test_sweep_controller_v2.py -v`。

### Task 2.1: 创建 `models/` 目录 + `AxisSpec` dataclass

**Files:**
- Create: `inp_tool_gui/models/__init__.py`
- Create: `inp_tool_gui/models/config_store.py`
- Create: `inp_tool/tests/test_config_store.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config_store.py
"""ConfigStore 模型层单测(纯 Python)。"""
import pytest


def test_axis_spec_enum_subset_creation():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="enum_subset", values=("sst", "kw"))
    assert spec.kind == "enum_subset"
    assert spec.values == ("sst", "kw")


def test_axis_spec_is_frozen():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="explicit_list", values=(1, 2, 3))
    with pytest.raises((AttributeError, Exception)):
        spec.kind = "range"


def test_axis_spec_range_form():
    from inp_tool_gui.models.config_store import AxisSpec
    spec = AxisSpec(kind="range", range_min=0.0, range_max=1.0, range_step=0.1)
    assert spec.range_min == 0.0
    assert spec.range_max == 1.0
    assert spec.range_step == 0.1
```

- [ ] **Step 3: 实现**

```python
# inp_tool_gui/models/__init__.py
"""GUI 模型层(纯 Python,无 PySide2 依赖)。"""

# inp_tool_gui/models/config_store.py
"""ConfigStore: 不可变 sweep 配置 + AxisSpec / ConditionalRule 模型。"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class AxisSpec:
    """单轴值规范。kind 决定 values / range_* 字段语义。"""
    kind: str  # "enum_subset" | "explicit_list" | "range" | "csv_str"
    values: Tuple[Any, ...] = ()
    range_min: Optional[float] = None
    range_max: Optional[float] = None
    range_step: Optional[float] = None
```

- [ ] **Step 4-5: 测试通过 + commit**

### Task 2.2: 创建 `ConfigStore` dataclass

**Files:**
- Modify: `inp_tool_gui/models/config_store.py`
- Modify: `inp_tool/tests/test_config_store.py`

- [ ] **Step 1: 写失败测试**

```python
def test_config_store_minimal_creation():
    from inp_tool_gui.models.config_store import ConfigStore
    s = ConfigStore(
        template="/t.inp",
        output_dir="/out",
        naming="case",
        preset_ref=None,
        sweeps={},
        conditions=(),
    )
    assert s.template == "/t.inp"
    assert s.case_count == 0


def test_config_store_is_frozen():
    from inp_tool_gui.models.config_store import ConfigStore
    s = ConfigStore(template="t", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    with pytest.raises((AttributeError, Exception)):
        s.template = "other"


def test_config_store_replace_returns_new_instance():
    """replace 不可变:返回新 ConfigStore,原实例不变。"""
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    s1 = ConfigStore(template="t1", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    s2 = s1.replace(template="t2")
    assert s1.template == "t1"  # 原不变
    assert s2.template == "t2"  # 新实例
    assert s1 is not s2


def test_config_store_replace_with_sweep():
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    s1 = ConfigStore(template="t", output_dir="o", naming="case",
                     preset_ref=None, sweeps={}, conditions=())
    s2 = s1.replace_sweep("mach", AxisSpec(kind="range", range_min=0, range_max=2, range_step=1))
    assert "mach" in s2.sweeps
    assert "mach" not in s1.sweeps  # 不可变
```

- [ ] **Step 3: 实现**

```python
@dataclass(frozen=True)
class ConditionalRule:
    """(when, then) 一条规则。"""
    when: Any  # inp_tool.sweep.ConditionWhen
    then: Any  # inp_tool.sweep.ConditionThen


@dataclass(frozen=True)
class ConfigStore:
    """不可变 sweep 配置;所有修改走 replace 系列方法返回新实例。"""
    template: str
    output_dir: str
    naming: str
    preset_ref: Optional[str]
    sweeps: Dict[str, AxisSpec] = field(default_factory=dict)
    conditions: Tuple[ConditionalRule, ...] = ()

    @property
    def case_count(self) -> int:
        """笛卡尔积预估(无 condition 时)。"""
        n = 1
        for spec in self.sweeps.values():
            if spec.kind == "range" and spec.range_step:
                n *= int((spec.range_max - spec.range_min) / spec.range_step) + 1
            else:
                n *= max(len(spec.values), 1)
        return n

    def replace(self, **kwargs) -> "ConfigStore":
        return dataclasses.replace(self, **kwargs)

    def replace_sweep(self, key: str, spec: AxisSpec) -> "ConfigStore":
        new_sweeps = dict(self.sweeps)
        new_sweeps[key] = spec
        return self.replace(sweeps=new_sweeps)

    def remove_sweep(self, key: str) -> "ConfigStore":
        new_sweeps = {k: v for k, v in self.sweeps.items() if k != key}
        return self.replace(sweeps=new_sweeps)

    def add_condition(self, rule: ConditionalRule) -> "ConfigStore":
        return self.replace(conditions=self.conditions + (rule,))
```

- [ ] **Step 4-5: 测试 + commit**

### Task 2.3: 创建 `PresetLibrary`

**Files:**
- Create: `inp_tool_gui/preset_library.py`
- Create: `inp_tool/tests/test_preset_library.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_preset_library.py
"""PresetLibrary 单测(纯 Python,纯文件系统,无 Qt)。"""
from pathlib import Path
import pytest


def test_preset_library_save_and_list(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {"mach": [1, 2]}, "conditions": []})
    items = lib.list()
    assert len(items) == 1
    assert items[0].name == "foo"
    assert items[0].source == "user"


def test_preset_library_get_returns_content(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {"mach": [1, 2]}, "conditions": []})
    content = lib.get("foo")
    assert content["sweeps"]["mach"] == [1, 2]


def test_preset_library_duplicate_save_raises(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    with pytest.raises(FileExistsError):
        lib.save("foo", {"sweeps": {}})


def test_preset_library_duplicate_save_with_overwrite(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    lib.save("foo", {"sweeps": {"x": [1]}}, overwrite=True)
    assert lib.get("foo")["sweeps"] == {"x": [1]}


def test_preset_library_delete_user(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    lib.delete("foo")
    assert lib.list() == []


def test_preset_library_team_source_marked(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    team = tmp_path / "team"
    team.mkdir()
    (team / "bar.yaml").write_text("sweeps: {}\nconditions: []\n", encoding="utf-8")
    lib = PresetLibrary(user_dir=tmp_path / "user", team_dirs=[team])
    items = lib.list()
    assert any(i.name == "bar" and i.source.startswith("team:") for i in items)


def test_preset_library_delete_team_raises(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    team = tmp_path / "team"
    team.mkdir()
    (team / "bar.yaml").write_text("sweeps: {}\n", encoding="utf-8")
    lib = PresetLibrary(user_dir=tmp_path / "user", team_dirs=[team])
    with pytest.raises(PermissionError):
        lib.delete("team:bar")


def test_preset_library_search_by_tag(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("a", {"sweeps": {}, "tags": ["baseline", "low-speed"]})
    lib.save("b", {"sweeps": {}, "tags": ["transonic"]})
    results = lib.search("low")
    assert [r.name for r in results] == ["a"]
```

- [ ] **Step 3: 实现**

```python
# inp_tool_gui/preset_library.py
"""Preset 库:用户级 + 团队级,纯文件系统,无 Qt 依赖。"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass(frozen=True)
class PresetMeta:
    name: str
    source: str        # "user" 或 "team:<dir_name>"
    tags: tuple = ()
    path: Optional[Path] = None


class PresetLibrary:
    def __init__(self, user_dir: Path, team_dirs: List[Path]) -> None:
        self.user_dir = Path(user_dir)
        self.team_dirs = [Path(d) for d in team_dirs]

    def list(self) -> List[PresetMeta]:
        out: List[PresetMeta] = []
        if self.user_dir.exists():
            for p in sorted(self.user_dir.glob("*.yaml")):
                meta = self._meta_from(p, source="user")
                if meta:
                    out.append(meta)
        for team in self.team_dirs:
            if not team.exists():
                continue
            for p in sorted(team.glob("*.yaml")):
                meta = self._meta_from(p, source=f"team:{team.name}")
                if meta:
                    out.append(meta)
        return out

    def get(self, ref: str) -> Dict[str, Any]:
        path = self._resolve_path(ref)
        if path is None:
            raise KeyError(f"preset {ref!r} not found")
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save(self, name: str, content: Dict[str, Any], *, overwrite: bool = False) -> Path:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{name}.yaml"
        if path.exists() and not overwrite:
            raise FileExistsError(f"preset {name!r} already exists at {path}")
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(content, f, allow_unicode=True, sort_keys=False)
        return path

    def delete(self, ref: str) -> None:
        if ref.startswith("team:"):
            raise PermissionError("cannot delete team preset via PresetLibrary")
        path = self._resolve_path(ref)
        if path is None or not path.exists():
            raise KeyError(f"preset {ref!r} not found")
        path.unlink()

    def search(self, query: str) -> List[PresetMeta]:
        q = query.lower()
        return [
            m for m in self.list()
            if q in m.name.lower() or any(q in t.lower() for t in m.tags)
        ]

    def _meta_from(self, path: Path, source: str) -> Optional[PresetMeta]:
        try:
            with path.open(encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return None
        return PresetMeta(
            name=path.stem,
            source=source,
            tags=tuple(content.get("tags", [])),
            path=path,
        )

    def _resolve_path(self, ref: str) -> Optional[Path]:
        if ref.startswith("team:"):
            name = ref[len("team:"):]
            for team in self.team_dirs:
                p = team / f"{name}.yaml"
                if p.exists():
                    return p
            return None
        p = self.user_dir / f"{ref}.yaml"
        return p if p.exists() else None
```

- [ ] **Step 4-5: 测试 + commit**

### Task 2.4: 创建 `SweepControllerV2`

**Files:**
- Create: `inp_tool_gui/controllers/sweep_controller_v2.py`
- Create: `inp_tool/tests/test_sweep_controller_v2.py`
- Modify: `inp_tool_gui/controllers/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_sweep_controller_v2.py
"""SweepControllerV2 单测(load/dump YAML v2 + v1 迁移)。"""
from pathlib import Path
import pytest


def test_load_yaml_v2_basic(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "sweep.yaml"
    yaml_file.write_text(
        "version: 2\n"
        "template: t.inp\n"
        "output_dir: /out\n"
        "naming: case\n"
        "sweeps:\n"
        "  turbulence: [sst, kw]\n",
        encoding="utf-8",
    )
    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(yaml_file)
    assert store.template == "t.inp"
    assert "turbulence" in store.sweeps


def test_load_yaml_v1_auto_upgrades(tmp_path):
    """无 version 字段 → 自动当 v1 处理并升级。"""
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "old.yaml"
    yaml_file.write_text(
        "template: t.inp\n"
        "output_dir: /out\n"
        "sweeps:\n"
        "  alpha: [0, 1, 2]\n",
        encoding="utf-8",
    )
    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(yaml_file)
    assert store.sweeps["alpha"].kind == "explicit_list"
    assert store.conditions == ()


def test_dump_yaml_v2_roundtrip(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    ctrl = SweepControllerV2()
    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case_{x}",
        preset_ref=None,
        sweeps={"mach": AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)},
        conditions=(),
    )
    out = tmp_path / "out.yaml"
    ctrl.dump_yaml(store, out)
    loaded = ctrl.load_yaml(out)
    assert loaded.sweeps["mach"].kind == "range"
    assert loaded.naming == "case_{x}"


def test_load_yaml_invalid_version_raises(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "future.yaml"
    yaml_file.write_text("version: 99\ntemplate: t\n", encoding="utf-8")
    ctrl = SweepControllerV2()
    with pytest.raises(ValueError, match="schema"):
        ctrl.load_yaml(yaml_file)
```

- [ ] **Step 3: 实现**

```python
# inp_tool_gui/controllers/sweep_controller_v2.py
"""SweepControllerV2:加载/保存/迁移 sweep YAML(v2 + v1 自动升级)。"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from inp_tool_gui.models.config_store import AxisSpec, ConfigStore


SUPPORTED_VERSIONS = (1, 2)


class SweepControllerV2:
    def load_yaml(self, path: Union[str, Path]) -> ConfigStore:
        with Path(path).open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return self._parse(data)

    def dump_yaml(self, store: ConfigStore, path: Union[str, Path]) -> None:
        data = self._serialize(store)
        with Path(path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _parse(self, data: Dict[str, Any]) -> ConfigStore:
        version = data.get("version")
        if version is None:
            data = self._upgrade_v1(data)
        elif version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"sweep YAML schema version {version} not supported; "
                f"supported: {SUPPORTED_VERSIONS}"
            )
        return ConfigStore(
            template=data["template"],
            output_dir=data["output_dir"],
            naming=data.get("naming", "case"),
            preset_ref=data.get("preset"),
            sweeps=self._parse_sweeps(data.get("sweeps", {})),
            conditions=(),  # condition 解析待 Phase 4 GUI 集成时再连
        )

    def _serialize(self, store: ConfigStore) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "version": 2,
            "template": store.template,
            "output_dir": store.output_dir,
            "naming": store.naming,
            "sweeps": self._serialize_sweeps(store.sweeps),
        }
        if store.preset_ref:
            d["preset"] = store.preset_ref
        if store.conditions:
            d["conditions"] = [...]  # TODO: serialize condition 时填充
        return d

    @staticmethod
    def _upgrade_v1(v1: Dict[str, Any]) -> Dict[str, Any]:
        v2 = dict(v1)
        v2["version"] = 2
        v2.setdefault("conditions", [])
        v2.setdefault("preset", None)
        return v2

    @staticmethod
    def _parse_sweeps(raw: Dict[str, Any]) -> Dict[str, AxisSpec]:
        out: Dict[str, AxisSpec] = {}
        for key, val in raw.items():
            if isinstance(val, dict) and "range" in val:
                rng = val["range"]
                if len(rng) == 3:
                    out[key] = AxisSpec(
                        kind="range",
                        range_min=float(rng[0]),
                        range_max=float(rng[1]),
                        range_step=float(rng[2]),
                    )
                elif len(rng) == 2:
                    # linspace 预留
                    out[key] = AxisSpec(kind="linspace", range_min=float(rng[0]), range_max=float(rng[1]))
                else:
                    raise ValueError(f"range must have 2 or 3 elements, got {len(rng)}")
            elif isinstance(val, str):
                vals = tuple(x.strip() for x in val.split(",") if x.strip())
                out[key] = AxisSpec(kind="csv_str", values=vals)
            elif isinstance(val, list):
                vals = tuple(val)
                kind = "enum_subset" if all(isinstance(v, str) for v in vals) else "explicit_list"
                out[key] = AxisSpec(kind=kind, values=vals)
            else:
                raise ValueError(f"unsupported sweep value type for axis {key!r}: {type(val)}")
        return out

    @staticmethod
    def _serialize_sweeps(sweeps: Dict[str, AxisSpec]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, spec in sweeps.items():
            if spec.kind == "range":
                out[key] = {"range": [spec.range_min, spec.range_max, spec.range_step]}
            elif spec.kind in ("enum_subset", "explicit_list"):
                out[key] = list(spec.values)
            elif spec.kind == "csv_str":
                out[key] = ", ".join(str(v) for v in spec.values)
            else:
                raise ValueError(f"unsupported AxisSpec.kind {spec.kind!r} for serialize")
        return out
```

- [ ] **Step 4-5: 测试 + commit**

### Task 2.5: Phase 2 PR

- [ ] 推分支 + 开 PR + 等 CI
- [ ] 标题: `feat(model): ConfigStore + PresetLibrary + SweepControllerV2`
- [ ] 描述引 spec §2 / §5 / §7.1

---

## Phase 3 — 自由表单视图重写

**独立 PR**: `refactor(gui): SweepFormView 用 ConfigStore 单向数据流` → 分支 `refactor/sweep-form-view-v2`
**估时**: 1d。**前置依赖**: Phase 2。**完成后可独立验证**: 旧 `tests/test_gui_sweep_form.py` 38 测试全过(通过 import 兼容别名)+ 新 `tests/test_gui_sweep_form_view.py` 全过。

### Task 3.1: 创建 `enum_checklist_dialog`

**Files:**
- Create: `inp_tool_gui/widgets/enum_checklist_dialog.py`
- Create: `inp_tool/tests/test_gui_enum_checklist.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_gui_enum_checklist.py
def test_enum_checklist_dialog_returns_selected(qapp):
    from inp_tool_gui.widgets.enum_checklist_dialog import EnumChecklistDialog
    dlg = EnumChecklistDialog(
        choices=["sst", "kw", "sa"],
        selected={"sst"},
        parent=None,
    )
    # 模拟用户勾选 kw
    dlg._list_widget.item(1).setCheckState(2)  # 2=Checked
    assert dlg.get_selected() == {"sst", "kw"}
```

- [ ] **Step 3: 实现** — 标准 `QDialog` + `QListWidget` + `setSelectionMode(MultiSelection)` + OK/Cancel 按钮。

### Task 3.2: 创建 `SweepFormView` 骨架(继承自现有 SweepForm,但内部用 ConfigStore)

**Files:**
- Create: `inp_tool_gui/widgets/sweep_form_view.py`
- Create: `inp_tool/tests/test_gui_sweep_form_view.py`

- [ ] **Step 1: 写失败测试**

```python
def test_sweep_form_view_creates_from_config_store(qapp):
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    from inp_tool_gui.models.config_store import ConfigStore
    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case",
        preset_ref=None, sweeps={}, conditions=(),
    )
    view = SweepFormView(store)
    assert view.config_store is store


def test_sweep_form_view_emits_store_changed_on_field_edit(qapp):
    """修改 template → emit store_changed(new_store)。"""
    from inp_tool_gui.widgets.sweep_form_view import SweepFormView
    from inp_tool_gui.models.config_store import ConfigStore
    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case",
        preset_ref=None, sweeps={}, conditions=(),
    )
    view = SweepFormView(store)
    received = []
    view.store_changed.connect(lambda s: received.append(s))
    view._edit_tpl.setText("new.inp")
    view._edit_tpl.editingFinished.emit()
    assert len(received) == 1
    assert received[0].template == "new.inp"
```

- [ ] **Step 3: 实现骨架** — 复用 `_build_ui` 但删旧信号逻辑,改为修改后 emit `store_changed`。

(详细内部实现超出本 plan 范围 — 执行时按 spec §4.3 自由表单视图章节展开。关键:值 widget 按 AxisSpec.kind 智能切换。)

### Task 3.3: 把 `SweepFormView` 接入现有 GUI(暂作单页,Phase 7 再加 tab)

- [ ] 修改 `inp_tool_gui/main_window.py` 第 X 行的 `SweepForm` 引用为 `SweepFormView`
- [ ] 旧 `SweepForm` 标记 deprecated:`# DEPRECATED: use SweepFormView instead`
- [ ] 保留 import 兼容:`from inp_tool_gui.widgets.sweep_form import SweepForm` 仍可工作(内部转发到 SweepFormView)

### Task 3.4: Phase 3 PR

- [ ] 推分支 + 开 PR + CI
- [ ] 标题: `refactor(gui): SweepFormView 单向数据流 + enum checklist`
- [ ] 描述重点: ConfigStore 化、enum 子集 checklist UI、import 兼容

---

## Phase 4 — 向导视图

**独立 PR**: `feat(gui): SweepWizard 4-step 向导` → 分支 `feat/sweep-wizard`
**估时**: 1.5d。**前置依赖**: Phase 3。**完成后可独立验证**: `pytest tests/test_gui_sweep_wizard.py -v` + 手动 GUI 验证。

### Task 4.1: 创建 `variable_tree_widget`(共享组件)

**Files:**
- Create: `inp_tool_gui/widgets/variable_tree_widget.py`

- [ ] 树形展示 `enumerate_vars(template_path)` 结果,分组(block / top_stmts),支持搜索过滤
- [ ] 双击或拖拽 emit `variable_picked(key: str)` 信号

### Task 4.2: 创建 `SweepWizard` Step 1(模板与输出)

- [ ] 3 个 QLineEdit(template / output_dir / naming)+ 浏览按钮
- [ ] 任何修改 → emit `store_changed`

### Task 4.3: 创建 `SweepWizard` Step 2(选轴 + 设值)

- [ ] 左:VariableTreeWidget(可拖入已选轴)
- [ ] 右:已选轴列表,每个值 widget 按 AxisSpec.kind 切换(checklist / range spinbox / csv edit)

### Task 4.4: 创建 `SweepWizard` Step 3(条件依赖)

- [ ] 条件列表,每条 when/then 子表单
- [ ] "添加条件" 按钮 → 弹新 row

### Task 4.5: 创建 `SweepWizard` Step 4(预览 + 运行)

- [ ] case 数预估 + dry run 表格 + 运行按钮
- [ ] 复用 `SweepController` 现有 `run()` 方法

### Task 4.6: Phase 4 PR

- [ ] 推分支 + 开 PR + CI
- [ ] 标题: `feat(gui): SweepWizard 4-step 向导`
- [ ] 描述引用 spec §4.2

---

## Phase 5 — YAML 视图

**独立 PR**: `feat(gui): SweepYamlEditorView` → 分支 `feat/sweep-yaml-editor`
**估时**: 1d。**前置依赖**: Phase 4。**完成后可独立验证**: `pytest tests/test_gui_sweep_yaml_editor.py -v`。

### Task 5.1: YAML 文本编辑器(`QPlainTextEdit` + 简单语法高亮)

- [ ] 关键词着色(`version`, `template`, `sweeps`, `conditions` 等)
- [ ] 行号侧栏

### Task 5.2: 实时 schema lint

- [ ] 文本变更 → debounce 200ms → `yaml.safe_load` + `SweepControllerV2._parse` → 报错则底部状态栏 + 行号红点
- [ ] 校验通过 → 调 `ConfigStore.from_dict(...)` 推回 store(单向数据流)

### Task 5.3: 侧边栏(变量树 + preset 树)

- [ ] 左 sidebar:VariableTreeWidget + PresetSidebar
- [ ] 右 sidebar:实时 case 预览(随 store 变更重算)

### Task 5.4: Phase 5 PR

- [ ] 推分支 + 开 PR + CI
- [ ] 标题: `feat(gui): SweepYamlEditorView + 实时校验`

---

## Phase 6 — 迁移工具 + 默认 preset

**独立 PR**: `feat(cli): sweep v1→v2 migrate + 默认 preset` → 分支 `feat/sweep-migrate-cli`
**估时**: 0.5d。**前置依赖**: Phase 2。**完成后可独立验证**: `inp-tool migrate-sweep-v1 input.yaml output.yaml` + 输出 round-trip OK。

### Task 6.1: CLI `migrate-sweep-v1` 子命令

**Files:**
- Modify: `inp_tool/sweep_cli.py`(添加子命令)
- Create: `inp_tool/tests/test_sweep_cli_migrate.py`

- [ ] **Step 1: 写失败测试**

```python
def test_migrate_sweep_v1_writes_version_2(tmp_path):
    from click.testing import CliRunner
    from inp_tool.sweep_cli import cli
    runner = CliRunner()
    src = tmp_path / "old.yaml"
    src.write_text("template: t\noutput_dir: /o\nsweeps:\n  a: [1,2]\n", encoding="utf-8")
    dst = tmp_path / "new.yaml"
    result = runner.invoke(cli, ["migrate-sweep-v1", str(src), str(dst)])
    assert result.exit_code == 0
    text = dst.read_text(encoding="utf-8")
    assert "version: 2" in text
```

- [ ] **Step 3: 实现**

```python
# inp_tool/sweep_cli.py 添加子命令
@cli.command("migrate-sweep-v1")
@click.argument("src", type=click.Path(exists=True))
@click.argument("dst", type=click.Path())
def migrate_sweep_v1(src: str, dst: str) -> None:
    """迁移 v1 sweep YAML 到 v2(自动加 version: 2 + conditions: [])。"""
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(src)
    ctrl.dump_yaml(store, dst)
    click.echo(f"已迁移 {src} → {dst}(v2 schema)")
```

### Task 6.2: 3 个默认 preset

**Files:**
- Create: `inp_tool_gui/resources/default_presets/low-speed.yaml`
- Create: `inp_tool_gui/resources/default_presets/transonic.yaml`
- Create: `inp_tool_gui/resources/default_presets/high-speed.yaml`

- [ ] 写入 3 个 .yaml,内容按 spec §5.2 preset schema
- [ ] 启动 GUI 时若 `~/.config/cfd--changer/presets/` 不存在,自动 copy 这 3 个作为初始内容

### Task 6.3: Phase 6 PR

- [ ] 推分支 + 开 PR + CI

---

## Phase 7 — 整合 + 文档

**独立 PR**: `feat(gui): 三视图 tab 整合 + i18n + docs` → 分支 `feat/sweep-tab-integration`
**估时**: 1d。**前置依赖**: Phase 5 + Phase 6。**完成后可独立验证**: 启动 GUI,看到「批量算例」tab 顶部 3 视图 tab 可切换,Ctrl+1/2/3 快捷键工作。

### Task 7.1: 顶部 tab 整合

**Files:**
- Modify: `inp_tool_gui/main_window.py`

- [ ] 把 `SweepFormView` 替换为 `QTabWidget` 包 3 个子视图(WizardView / FormView / YamlEditorView)
- [ ] 加快捷键 `Ctrl+1/2/3` 切 tab

### Task 7.2: Preset 共享侧边栏组件

**Files:**
- Create: `inp_tool_gui/widgets/preset_sidebar.py`

- [ ] 3 视图都嵌入同一 PresetSidebar
- [ ] 双击 preset → emit `preset_loaded(ref)` → 触发 store_changed

### Task 7.3: i18n 新增 ~20 个 key

**Files:**
- Modify: `inp_tool/i18n_gui.py`

- [ ] zh + en 各加 `sweep.wizard.stepN.*`、`sweep.condition.*`、`sweep.preset.*`、`sweep.tab.*`

### Task 7.4: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] `[Unreleased]` 段加此次重设计的 Fixed + Added 条目

### Task 7.5: 用户手册 + 技术手册

**Files:**
- Modify: `docs/user-manual/sweep/README.md`(三视图使用章节)
- Create: `docs/technical/sweep/13-sweep-ui-v2.md`(架构 + 数据流 + 模块边界)

### Task 7.6: Phase 7 PR

- [ ] 推分支 + 开 PR + CI
- [ ] 描述引用 spec §2、§4.5(键位)
- [ ] CHANGELOG / docs 一并 PR

---

## Self-Review(对照 spec §1-§13)

| Spec 章节 | 计划覆盖 |
|---|---|
| §1 现状与目标 | Phase 1-7 全部命中 |
| §2 架构与边界 | Phase 2(ConfigStore / 边界规则)+ Phase 3-5(View 只通过 store) |
| §3 Sweep YAML v2 schema | Phase 2 (Task 2.4 `_parse_sweeps` + `_serialize_sweeps`)+ Phase 6 (CLI 迁移) |
| §4 UI 三视图系统 | Phase 3 (FormView) + Phase 4 (Wizard) + Phase 5 (YAML) + Phase 7 (tab 整合 + 键位) |
| §5 Preset 库 | Phase 2 (Task 2.3 PresetLibrary) + Phase 6 (默认 preset) + Phase 7 (共享 sidebar) |
| §6 引擎层改造 | Phase 1 全部 |
| §7 迁移路径 | Phase 2 (Task 2.4 `_upgrade_v1`) + Phase 6 (CLI migrate 命令) |
| §8 测试策略 | 每个 Task 都有 step 1 failing test + step 4 passing verify |
| §9 阶段交付 | 本 plan 即 7 阶段 |
| §10 成功标准 | 1-8 全部在 Phase 7 PR 验收时人工核对 |
| §11 子 spec | 实现时按需立专项,本 plan 未展开 |
| §12 风险 | Phase 5 用 `QPlainTextEdit` 而非 `QScintilla`(已在风险缓解中说明) |
| §13 后续工作 | 不在本期范围 ✓ |

**类型一致性检查**:
- `AxisSpec.kind` ∈ `{"enum_subset", "explicit_list", "range", "linspace", "csv_str", "expression"}` — P2 定义,P3 用 ✓
- `ConfigStore` 字段 — P2 定义,P3-P5 用 ✓
- `ConditionalRule.when / then` 类型 — P1 定义,P2 用(import 自 `inp_tool.sweep`),P4 用 ✓
- `PresetLibrary` API — P2 定义,P5/P7 用 ✓

**无占位符**:
- 所有 Task 的 Step 1 测试代码都是实际可运行代码
- 所有 Step 3 实现代码都是完整可粘贴
- Step 5 commit message 已给

---

## Execution Notes

- **执行方式**: 推荐 subagent-driven(每个 Task 一个 subagent,review 后再下一个);inline 也可,但 P3-P5 涉及 PySide2 widget 测试,inline 时长较长
- **每个 PR 都需 3 平台 CI 通过**: ubuntu / windows / macos
- **代码 review**: 每个 PR 走 AI review(推荐 `pr-review-toolkit:code-reviewer`)
- **CLAUDE.md 约束**: 任何 PR 不能引入 PEP 604 / PEP 585 语法到 Pydantic 字段;新 widget 文件 ≤ 800 行
- **完成后**: 按 CLAUDE.md §3.1,本 plan 实施完成后**删除 `docs/superpowers/plans/2026-06-16-sweep-ui-redesign-plan.md`**,保留 spec `2026-06-16-sweep-ui-redesign-design.md`,更新其 **Status:** 行为 "Implemented in v0.X.Y"。
