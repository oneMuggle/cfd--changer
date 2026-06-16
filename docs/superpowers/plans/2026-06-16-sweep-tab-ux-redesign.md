# Sweep 标签页 UX 重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `inp_tool_gui` 的 Sweep 标签页从「自由文本填表」升级为「带变量发现 + 类型约束 + 失效保护」的工程化表单,不动后端 sweep 系统 / 不动 .inp 解析层 / 不动 YAML 旧契约。

**Architecture:** 新增 `sweep_var_combo.py` 纯模块(`VarSpec` + `enumerate_vars` 纯函数,无 PySide2),SweepController 包装加 cache,SweepForm 重构 cell widget + 类型校验 + 失效扫描。复用 `inp_tool.model.infer_type` 和 `inp_tool.value_editor._convert` 的类型推断,避免行为分叉。

**Tech Stack:** PySide2 5.15.2.1(Qt for Python,Qt 5.15 末版 Win7 兼容);Python 3.8;pytest 7+;conda 环境 `cfdchanger`(严格隔离,`conda run -n cfdchanger` 前缀);现有 sweep 后端(`inp_tool.sweep` 1382 行,**不改**)。

**Spec:** `docs/superpowers/specs/2026-06-16-sweep-tab-ux-redesign-design.md`(commit 83d1fb0)

**Pre-conditions:**
- conda 环境 `cfdchanger` 已创建(Python 3.8.20)
- `inp_tool` 已 `pip install -e .[gui,api,dev]`
- 测试基线全绿:`conda run -n cfdchanger pytest tests/ -q`
- 当前在 `main` 分支;按项目约定,**开始任务 1 前**先建 feature 分支 `git switch -c feat/sweep-tab-ux-redesign`

---

## Task 1: VarSpec 数据类

**Files:**
- Create: `inp_tool/inp_tool_gui/widgets/sweep_var_combo.py`
- Test: `inp_tool/tests/test_gui_sweep_var_combo.py`

- [ ] **Step 1: 创建 feature 分支**

```bash
cd /home/fz/project/cfd--changer
git switch -c feat/sweep-tab-ux-redesign
git status   # 应在 feature 分支
```

- [ ] **Step 2: 写失败的测试**

创建 `inp_tool/tests/test_gui_sweep_var_combo.py`:

```python
"""VarSpec 数据类测试。"""
from inp_tool_gui.widgets.sweep_var_combo import VarSpec


def test_varspec_creation_minimal():
    """最小字段:key/label/kind 能创建。"""
    v = VarSpec(key="turbulence", label="turbulence (枚举)", kind="enum")
    assert v.key == "turbulence"
    assert v.label == "turbulence (枚举)"
    assert v.kind == "enum"
    assert v.enum_values is None
    assert v.block is None
    assert v.keyword is None
    assert v.value_idx is None


def test_varspec_creation_full():
    """全字段:普通 .inp 变量。"""
    v = VarSpec(
        key="physics.reynolds[0]",
        label="physics.reynolds[0] [float] = 1.0e6",
        kind="float",
        enum_values=None,
        block="physics",
        keyword="reynolds",
        value_idx=0,
    )
    assert v.block == "physics"
    assert v.keyword == "reynolds"
    assert v.value_idx == 0


def test_varspec_is_frozen():
    """frozen=True:不能修改字段。"""
    import dataclasses
    v = VarSpec(key="turbulence", label="turbulence", kind="enum")
    try:
        v.key = "other"
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("expected FrozenInstanceError")


def test_varspec_kind_literal_values():
    """kind 只接受 enum/int/float/str(本设计不暴露 bool)。"""
    for k in ("enum", "int", "float", "str"):
        v = VarSpec(key="x", label="x", kind=k)
        assert v.kind == k
```

- [ ] **Step 3: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**Expected:** ImportError 或 ModuleNotFoundError(`sweep_var_combo` 还没建)

- [ ] **Step 4: 写最小实现**

创建 `inp_tool/inp_tool_gui/widgets/sweep_var_combo.py`:

```python
"""Sweep 变量发现 + 类型元数据(纯 Python,无 PySide2)。

v0.17 引入,与 SweepController 配合:
- :class:`VarSpec` — 单变量 UI 描述(frozen dataclass)
- :func:`enumerate_vars` — 给定模板路径,返回 :class:`VarSpec` 列表
  (枚举轴 + .inp 变量)

不依赖 PySide2,可被 controller 和测试独立 import。
"""
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class VarSpec:
    """单变量的 UI 描述。

    - 枚举轴: block/keyword/value_idx 全为 None,enum_values 填合法 enum
    - 普通 .inp 变量: 填 block + keyword + value_idx,enum_values 为 None
    """
    key: str
    label: str
    kind: str
    enum_values: Optional[Tuple[str, ...]] = None
    block: Optional[str] = None
    keyword: Optional[str] = None
    value_idx: Optional[int] = None
```

- [ ] **Step 5: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**Expected:** 4 passed

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_var_combo.py inp_tool/tests/test_gui_sweep_var_combo.py
git commit -m "feat(gui): VarSpec 数据类(Sweep 变量发现第一步)"
```

---

## Task 2: enumerate_vars() 枚举轴部分

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_var_combo.py`
- Modify: `inp_tool/tests/test_gui_sweep_var_combo.py`

- [ ] **Step 1: 扩展测试,覆盖「无模板时仅枚举轴」**

在 `test_gui_sweep_var_combo.py` 末尾追加:

```python
from inp_tool_gui.widgets.sweep_var_combo import VarSpec, enumerate_vars


def test_enumerate_vars_none_template_returns_enum_only():
    """无模板路径:返回 3 个枚举轴,无 .inp 变量。"""
    specs = enumerate_vars(None)
    assert len(specs) == 3
    keys = {s.key for s in specs}
    assert keys == {"turbulence", "energy", "gas"}
    for s in specs:
        assert s.kind == "enum"
        assert s.enum_values is not None
        assert len(s.enum_values) >= 2
        assert s.block is None
        assert s.keyword is None
        assert s.value_idx is None


def test_enumerate_vars_none_template_enum_values_match_sweep_module():
    """3 个枚举轴的 enum_values 来自 inp_tool.sweep 的 _ENUM_AXES。"""
    from inp_tool.sweep import (
        TurbulenceModel, EnergyModel, GasModel,
    )
    specs = enumerate_vars(None)
    by_key = {s.key: s for s in specs}
    assert set(by_key["turbulence"].enum_values) == {
        e.value for e in TurbulenceModel
    }
    assert set(by_key["energy"].enum_values) == {
        e.value for e in EnergyModel
    }
    assert set(by_key["gas"].enum_values) == {
        e.value for e in GasModel
    }


def test_enumerate_vars_none_template_is_pure():
    """enumerate_vars(None) 是纯函数,无副作用(可重复调用)。"""
    a = enumerate_vars(None)
    b = enumerate_vars(None)
    assert a == b
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**Expected:** ImportError(`enumerate_vars` 未定义)

- [ ] **Step 3: 实现 enumerate_vars()(仅 None 路径)**

替换 `sweep_var_combo.py` 内容:

```python
"""Sweep 变量发现 + 类型元数据(纯 Python,无 PySide2)。"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

from inp_tool.sweep import (
    EnergyModel, GasModel, TurbulenceModel,
)


# 枚举轴定义: key -> Enum class
_ENUM_AXIS_CLASSES = {
    "turbulence": TurbulenceModel,
    "energy": EnergyModel,
    "gas": GasModel,
}


@dataclass(frozen=True)
class VarSpec:
    """单变量的 UI 描述。"""
    key: str
    label: str
    kind: str
    enum_values: Optional[Tuple[str, ...]] = None
    block: Optional[str] = None
    keyword: Optional[str] = None
    value_idx: Optional[int] = None


def _enum_axis_specs() -> List[VarSpec]:
    """构造 3 个枚举轴 VarSpec。"""
    out: List[VarSpec] = []
    for key, enum_cls in _ENUM_AXIS_CLASSES.items():
        values = tuple(e.value for e in enum_cls)
        label = "{} (枚举:{})".format(key, ",".join(values))
        out.append(VarSpec(
            key=key,
            label=label,
            kind="enum",
            enum_values=values,
        ))
    return out


def enumerate_vars(template_path: Optional[str]) -> List[VarSpec]:
    """根据模板路径返回 :class:`VarSpec` 列表。

    - template_path 为空(None 或空串)→ 仅 3 个枚举轴
    - template_path 存在但解析失败 → 仅 3 个枚举轴(不抛,本任务范围)
    - 否则 → 解析 .inp,枚举所有 (block, keyword, value_idx)
      (Task 3 实现)

    返回列表:枚举轴在前,.inp 变量在后;同 group 内顺序由实现定义。
    """
    if not template_path:
        return _enum_axis_specs()
    # 解析 .inp(后续 Task 3 实现)
    return _enum_axis_specs()  # 暂未实现
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**Expected:** 7 passed(4 + 3)

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_var_combo.py inp_tool/tests/test_gui_sweep_var_combo.py
git commit -m "feat(gui): enumerate_vars() 枚举轴部分"
```

---

## Task 3: enumerate_vars() .inp 解析部分

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_var_combo.py`
- Modify: `inp_tool/tests/test_gui_sweep_var_combo.py`

- [ ] **Step 1: 扩展测试,覆盖 .inp 解析**

在 `test_gui_sweep_var_combo.py` 末尾追加:

```python
import os
import pytest


# 共享 fixture:examples/mcfd.inp 的绝对路径
EXAMPLES_INP = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "examples", "mcfd.inp",
)


def test_enumerate_vars_invalid_path_returns_enum_only():
    """无效路径:返回仅枚举轴,不抛异常。"""
    specs = enumerate_vars("/不/存在/的/路径.inp")
    assert len(specs) == 3
    assert {s.key for s in specs} == {"turbulence", "energy", "gas"}


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_contains_enum_and_inp_vars():
    """真实 .inp 解析:返回枚举轴 + .inp 变量,key 格式为 block.keyword[idx]。"""
    specs = enumerate_vars(EXAMPLES_INP)
    keys = {s.key for s in specs}
    # 枚举轴必须在前 3
    enum_keys = {s.key for s in specs if s.kind == "enum"}
    assert enum_keys == {"turbulence", "energy", "gas"}
    # .inp 变量 key 格式: block.keyword 或 block.keyword[idx]
    for s in specs:
        if s.kind == "enum":
            continue
        assert "." in s.key, "非枚举轴 key 缺 block 路径: {}".format(s.key)
        # label 含 [kind] 信息
        assert "[" in s.label and "]" in s.label
        # block / keyword / value_idx 三件套齐全
        assert s.block is not None
        assert s.keyword is not None
        assert s.value_idx is not None
        # kind ∈ {int, float, str}
        assert s.kind in ("int", "float", "str")


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_label_includes_template_value():
    """label 含模板当前值,如 'physics.reynolds[0] [float] = 1.0e6'。"""
    specs = enumerate_vars(EXAMPLES_INP)
    # 找任一 float 变量验证
    float_vars = [s for s in specs if s.kind == "float"]
    if not float_vars:
        pytest.skip("examples/mcfd.inp 不含 float 变量")
    s = float_vars[0]
    # label 末尾是 " = <value>"
    assert " = " in s.label
    # 切开后,右边就是模板当前值的字符串
    _, _, raw = s.label.rpartition(" = ")
    assert raw  # 非空
    # raw 应该能 round-trip 到 s.kind 对应的类型
    if s.kind == "float":
        float(raw.replace("d", "e").replace("D", "E"))
    elif s.kind == "int":
        int(raw)


@pytest.mark.skipif(
    not os.path.exists(EXAMPLES_INP),
    reason="examples/mcfd.inp 不存在(此环境缺 fixture)",
)
def test_enumerate_vars_real_inp_inferred_kind_order():
    """kind 推断顺序:本设计不暴露 bool(走 str)。"""
    specs = enumerate_vars(EXAMPLES_INP)
    for s in specs:
        if s.kind == "enum":
            continue
        # 不会返回 "bool"
        assert s.kind in ("int", "float", "str")
```

- [ ] **Step 2: 跑测试,确认 RED(无效路径已通过,但真实 .inp 还没实现)**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**Expected:** `test_enumerate_vars_real_inp_*` 失败(返回 3 个枚举轴,没 .inp 变量)

- [ ] **Step 3: 实现 .inp 解析**

追加到 `sweep_var_combo.py` 顶部(已有其他 import 后):

```python
from typing import Any  # noqa: E402

from inp_tool.model import InpFile, infer_type  # noqa: E402
```

追加到 `sweep_var_combo.py`(在 `enumerate_vars` 之前):

```python
def _infer_kind_for_sweep(typed: Any) -> str:
    """推断 sweep 轴的 kind。

    注意:与 ``infer_type`` 的 bool>int>float>str 不同,
    sweep 轴语义上更接近「物理参数」,布尔直接走 str(避免误把
    "t"/"f" 误判成 axis 值)。
    """
    if isinstance(typed, bool):
        return "str"
    if isinstance(typed, int):
        return "int"
    if isinstance(typed, float):
        return "float"
    return "str"


def _parse_inp(path: str) -> List[VarSpec]:
    """解析 .inp,生成所有 (block, keyword, value_idx) 的 VarSpec。"""
    inp = InpFile.parse(path)  # 假设 InpFile 有 parse 类方法(若不存在,见 Step 4)
    out: List[VarSpec] = []
    # 顶层语句
    for stmt in inp.top_stmts:
        for vi, v in enumerate(stmt.values):
            kind = _infer_kind_for_sweep(v.typed)
            raw = str(v.typed) if v.typed is not None else ""
            key = "{}[{}]".format(stmt.keyword, vi)
            label = "{} [{}] = {}".format(key, kind, raw)
            out.append(VarSpec(
                key=key, label=label, kind=kind,
                block="<top>", keyword=stmt.keyword, value_idx=vi,
            ))
    # 块内语句
    for blk in inp.block_list:
        for stmt in blk.statements:
            for vi, v in enumerate(stmt.values):
                kind = _infer_kind_for_sweep(v.typed)
                raw = str(v.typed) if v.typed is not None else ""
                key = "{}.{}[{}]".format(blk.name, stmt.keyword, vi)
                label = "{} [{}] = {}".format(key, kind, raw)
                out.append(VarSpec(
                    key=key, label=label, kind=kind,
                    block=blk.name, keyword=stmt.keyword, value_idx=vi,
                ))
    return out


# 重写 enumerate_vars
def enumerate_vars(template_path: Optional[str]) -> List[VarSpec]:
    """..."""
    enum_specs = _enum_axis_specs()
    if not template_path:
        return enum_specs
    try:
        inp_specs = _parse_inp(template_path)
    except Exception:
        return enum_specs  # 解析失败:静默退化为仅枚举轴
    return enum_specs + inp_specs
```

**注意**: `InpFile.parse(path)` 是**假设**的 API。Step 4 会通过跑测试发现真实 API 并修正。

- [ ] **Step 4: 跑测试,确认是否需要修 API**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_var_combo.py -v
```

**如果 `InpFile.parse` 不存在**:
- 跑 `grep -n "def parse\|def from_\|^def parse_inp" /home/fz/project/cfd--changer/inp_tool/inp_tool/parser.py` 找真实 API
- 替换 `_parse_inp` 中的 `InpFile.parse(path)` 为正确调用,例如:
  ```python
  from inp_tool.parser import parse_inp
  inp = parse_inp(path)
  ```
- 跑测试直到 GREEN

- [ ] **Step 5: 跑全量测试,确认不破后端**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -5
```

**Expected:** 全绿

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_var_combo.py inp_tool/tests/test_gui_sweep_var_combo.py
git commit -m "feat(gui): enumerate_vars() 解析 .inp 部分"
```

---

## Task 4: SweepController.available_vars() + cache

**Files:**
- Modify: `inp_tool/inp_tool_gui/controllers/sweep_controller.py`
- Modify: `inp_tool/tests/test_gui_sweep_controller.py`

- [ ] **Step 1: 写失败的测试(缓存)**

在 `test_gui_sweep_controller.py` 末尾追加(用 monkeypatch 模拟 .inp 解析):

```python
import os
from inp_tool_gui.controllers.sweep_controller import SweepController


def test_available_vars_none_returns_enum_only():
    """无模板:仅枚举轴,3 项。"""
    ctrl = SweepController()
    specs = ctrl.available_vars(None)
    assert len(specs) == 3
    assert {s.key for s in specs} == {"turbulence", "energy", "gas"}


def test_available_vars_caches_per_template_path(monkeypatch):
    """同 template_path 二次调用不打文件(测 cache 命中)。"""
    ctrl = SweepController()
    call_count = {"n": 0}

    def fake_parse(path):
        call_count["n"] += 1
        return []  # 模拟空 InpFile

    # monkeypatch 内部 _parse_inp
    from inp_tool_gui.widgets import sweep_var_combo
    monkeypatch.setattr(sweep_var_combo, "_parse_inp", fake_parse)

    ctrl.available_vars("/tmp/a.inp")
    ctrl.available_vars("/tmp/a.inp")  # 二次调用,期望不递增 call_count
    assert call_count["n"] == 1


def test_available_vars_different_paths_hit_cache_independently(monkeypatch):
    """不同 template_path 各自解析一次,共用 path 二次命中。"""
    ctrl = SweepController()
    call_count = {"n": 0}

    def fake_parse(path):
        call_count["n"] += 1
        return []

    from inp_tool_gui.widgets import sweep_var_combo
    monkeypatch.setattr(sweep_var_combo, "_parse_inp", fake_parse)

    ctrl.available_vars("/tmp/a.inp")
    ctrl.available_vars("/tmp/b.inp")
    assert call_count["n"] == 2
    ctrl.available_vars("/tmp/a.inp")  # 二次
    ctrl.available_vars("/tmp/b.inp")  # 二次
    assert call_count["n"] == 2  # 没新增


def test_available_vars_failed_parse_not_cached(monkeypatch):
    """解析失败不缓存:重试时会再调一次 _parse_inp。"""
    ctrl = SweepController()
    call_count = {"n": 0}

    def fake_parse_fail(path):
        call_count["n"] += 1
        raise IOError("模拟失败")

    from inp_tool_gui.widgets import sweep_var_combo
    monkeypatch.setattr(sweep_var_combo, "_parse_inp", fake_parse_fail)

    ctrl.available_vars("/tmp/bad.inp")
    ctrl.available_vars("/tmp/bad.inp")
    assert call_count["n"] == 2  # 不缓存,重试
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_controller.py -v -k "available_vars"
```

**Expected:** AttributeError(`SweepController` 没 `available_vars`)

- [ ] **Step 3: 实现 available_vars()**

修改 `inp_tool/inp_tool_gui/controllers/sweep_controller.py`:

在文件顶部 import 区追加(已有其他 import 后):

```python
from typing import Dict  # noqa: E402

from inp_tool_gui.widgets.sweep_var_combo import (  # noqa: E402
    VarSpec, enumerate_vars,
)
```

修改 `__init__`,加 cache 字段:

```python
def __init__(self) -> None:
    self._sweep: Optional[CaseSweep] = None
    self._last_report: Optional[SweepReport] = None
    self._var_cache: Dict[Optional[str], List[VarSpec]] = {}
```

在 `class SweepController` 内追加方法(放在 `is_loaded` property 之后):

```python
def available_vars(self, template_path: Optional[str]) -> List[VarSpec]:
    """根据模板路径返回可选 :class:`VarSpec` 列表(枚举轴 + .inp 变量)。

    缓存策略:同一 template_path(str 规范化)只解析一次。
    解析失败时不缓存,下次调用重试。

    Args:
        template_path: .inp 路径;None 或空串 → 仅枚举轴。
    """
    # cache key 规范化(空串 → None,其他 → str)
    key = template_path if (template_path and str(template_path).strip()) else None
    if key in self._var_cache:
        return self._var_cache[key]
    # key 为 None 不会失败,直接 cache
    if key is None:
        result = enumerate_vars(None)
        self._var_cache[None] = result
        return result
    # key 为 path:试探解析,失败不缓存
    try:
        result = enumerate_vars(key)
    except Exception:
        return enumerate_vars(None)  # 退化,不缓存
    self._var_cache[key] = result
    return result
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_controller.py -v -k "available_vars"
```

**Expected:** 4 passed

- [ ] **Step 5: 跑全量,确保不破**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -5
```

**Expected:** 全绿(包含 `test_sweep_controller` 老测试)

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/controllers/sweep_controller.py inp_tool/tests/test_gui_sweep_controller.py
git commit -m "feat(gui): SweepController.available_vars() + 缓存"
```

---

## Task 5: i18n 新 key

**Files:**
- Modify: `inp_tool/inp_tool/i18n_gui.py`

- [ ] **Step 1: 读现有 i18n_gui.py 找格式**

```bash
grep -n "sweep.lbl\|sweep.live" /home/fz/project/cfd--changer/inp_tool/inp_tool/i18n_gui.py | head -20
```

观察:既有 key 用什么结构(zh / en dict?)— 模仿。

- [ ] **Step 2: 加 7 个新 key**

在 `i18n_gui.py` 的 sweep 区(找 `sweep.lbl.template` 等已有 key 附近),追加:

```python
# 顶部 3 个 label(本任务新增)
"sweep.lbl.template": {"zh": "模板路径", "en": "Template path"},
"sweep.lbl.output": {"zh": "输出目录", "en": "Output dir"},
"sweep.lbl.naming": {"zh": "命名模式", "en": "Naming pattern"},
# 错误提示(本任务新增,Task 8-9 使用)
"sweep.live.invalid_int": {"zh": "轴 {key} 第 {idx} 个值不是整数", "en": "Axis {key} value #{idx} is not an integer"},
"sweep.live.invalid_float": {"zh": "轴 {key} 第 {idx} 个值不是浮点数", "en": "Axis {key} value #{idx} is not a float"},
"sweep.live.orphan_axes": {"zh": "有 {n} 个轴未识别,无法运行", "en": "{n} axis(es) not recognized, run disabled"},
"sweep.live.no_template_no_axes": {"zh": "请先填模板路径或加轴", "en": "Please set template path or add axes"},
```

> **格式提示**:如果 `tg()` 函数签名是 `tg(key, **kwargs)`,这里 `{}` 是占位;具体看 `i18n_gui.py` 既有用法(比如 `sweep.live.need_template` 等),模仿它。

- [ ] **Step 3: 跑全量测试,确保 i18n 加载不破**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -5
```

**Expected:** 全绿(若 i18n 加载有 syntax 错误,会立刻被发现)

- [ ] **Step 4: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/i18n_gui.py
git commit -m "feat(gui): Sweep 顶部 3 label + 4 错误 i18n key"
```

---

## Task 6: SweepForm 顶部 3 个 label

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_form.py`
- Modify: `inp_tool/tests/test_gui_sweep_form.py`

- [ ] **Step 1: 读现有 sweep_form.py 行 56-83(顶部 3 行 layout)**

```bash
sed -n '56,83p' /home/fz/project/cfd--changer/inp_tool/inp_tool_gui/widgets/sweep_form.py
```

- [ ] **Step 2: 写失败的测试**

在 `test_gui_sweep_form.py` 末尾追加(假设 offscreen 模式):

```python
def test_sweep_form_has_three_top_labels():
    """顶部 3 行各有 QLabel 显示中文模板路径/输出目录/命名模式。"""
    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
    from inp_tool.i18n_gui import tg

    # 找现有 test_sweep_form 的工厂方法,模仿
    # (offscreen 平台: 必须先有 QApplication)
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    ctrl = SweepController()
    form = SweepForm(ctrl)

    # 收集 form 上所有 QLabel
    from PySide2.QtWidgets import QLabel
    labels = form.findChildren(QLabel)
    label_texts = {lbl.text() for lbl in labels}

    # 期望包含 3 个 i18n 文本
    assert tg("sweep.lbl.template") in label_texts
    assert tg("sweep.lbl.output") in label_texts
    assert tg("sweep.lbl.naming") in label_texts
```

> **注意**: 测试可能要复用现有 `test_gui_sweep_form.py` 里的 QApplication setup 模式;如果文件已用 fixture,加到这个 fixture 下而非独立函数。

- [ ] **Step 3: 跑测试,确认 RED**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "three_top_labels"
```

**Expected:** FAIL(还没 label)

- [ ] **Step 4: 重构 sweep_form.py 顶部 layout**

修改 `sweep_form.py` 行 59-82 区域。原代码是 `QHBoxLayout() + QLineEdit + QPushButton`,无 QLabel。

改为每行: `QLabel` (固定宽度) + `QLineEdit`(stretch=1) + `QPushButton`。

具体代码(替换 `_build_ui` 顶部 3 行 layout):

```python
# 模板路径
tpl_row = QHBoxLayout()
self._lbl_tpl = QLabel(tg("sweep.lbl.template"), self)
self._lbl_tpl.setMinimumWidth(80)
self._edit_tpl = QLineEdit(self)
self._edit_tpl.editingFinished.connect(self._sync_form_to_controller)
self._btn_tpl = QPushButton("浏览...", self)  # 保持原硬编码
self._btn_tpl.clicked.connect(self._pick_template)
tpl_row.addWidget(self._lbl_tpl)
tpl_row.addWidget(self._edit_tpl, 1)
tpl_row.addWidget(self._btn_tpl)
root.addLayout(tpl_row)

# 输出目录
out_row = QHBoxLayout()
self._lbl_out = QLabel(tg("sweep.lbl.output"), self)
self._lbl_out.setMinimumWidth(80)
self._edit_out = QLineEdit(self)
self._edit_out.editingFinished.connect(self._sync_form_to_controller)
self._btn_out = QPushButton("浏览...", self)  # 保持原硬编码
self._btn_out.clicked.connect(self._pick_output)
out_row.addWidget(self._lbl_out)
out_row.addWidget(self._edit_out, 1)
out_row.addWidget(self._btn_out)
root.addLayout(out_row)

# 命名
naming_row = QHBoxLayout()
self._lbl_naming = QLabel(tg("sweep.lbl.naming"), self)
self._lbl_naming.setMinimumWidth(80)
self._edit_naming = QLineEdit(self)
self._edit_naming.editingFinished.connect(self._sync_form_to_controller)
naming_row.addWidget(self._lbl_naming)
naming_row.addWidget(self._edit_naming, 1)
root.addLayout(naming_row)
```

> **说明**: 浏览按钮文本保持硬编码 `"浏览..."`,避免引入新的 i18n key。本任务范围只动 label。

- [ ] **Step 5: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "three_top_labels"
```

**Expected:** PASS

- [ ] **Step 6: 跑全量,确保不破**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -10
```

**Expected:** 全绿(`test_gui_sweep_form` 老的 12 个测试仍过)

- [ ] **Step 7: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_form.py inp_tool/tests/test_gui_sweep_form.py
git commit -m "feat(gui): SweepForm 顶部 3 个 label(模板/输出/命名)"
```

---

## Task 7: SweepForm 轴表 cell widget 化(QComboBox + QLineEdit)

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_form.py`
- Modify: `inp_tool/tests/test_gui_sweep_form.py`

- [ ] **Step 1: 写失败的测试**

在 `test_gui_sweep_form.py` 末尾追加:

```python
def test_sweep_form_axes_table_uses_combobox_cells():
    """轴表第 0 列 cell 是 QComboBox(非 QTableWidgetItem)。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication, QComboBox, QLineEdit, QLabel
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")  # 触发 cell widget 构造
    # 第一行第 0 列应是 QComboBox
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox), "got {}".format(type(cell))
    # 第 1 列:枚举轴应是 QLabel(不可编辑),普通轴应是 QLineEdit
    cell1 = form._axes_table.cellWidget(0, 1)
    assert isinstance(cell1, (QLabel, QLineEdit))


def test_sweep_form_axes_combobox_populated_with_vars():
    """combobox items 来自 controller.available_vars(当前模板)。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication, QComboBox
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController

    ctrl = SweepController()
    form = SweepForm(ctrl)
    form._append_axis_row("turbulence", "sst")
    cell = form._axes_table.cellWidget(0, 0)
    assert isinstance(cell, QComboBox)
    keys = [cell.itemText(i) for i in range(cell.count())]
    # 至少含 3 个枚举轴
    assert "turbulence" in keys
    assert "energy" in keys
    assert "gas" in keys
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "axes_table or combobox_populated"
```

**Expected:** FAIL(原代码用 QTableWidgetItem)

- [ ] **Step 3: 重构 _append_axis_row 接受 VarSpec**

修改 `sweep_form.py` 顶部 import 区:

```python
from typing import Any, Dict, List, Optional

from PySide2.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool_gui.controllers.sweep_controller import SweepController
from inp_tool_gui.widgets.sweep_var_combo import VarSpec  # 新增
```

替换 `_append_axis_row` 方法(在原方法位置),并加新方法 `_make_combo_for_row` / `_make_value_cell_for_kind`:

```python
def _make_combo_for_row(self, spec: Optional[VarSpec]) -> QComboBox:
    """根据当前 controller 模板,生成含所有可选变量的 QComboBox。"""
    template = self._sweep_ctrl.template
    specs = self._sweep_ctrl.available_vars(template)
    combo = QComboBox(self)
    for s in specs:
        combo.addItem(s.label, userData=s.key)
    # 若 spec 给了已选 key,尝试设为 current
    if spec is not None:
        for i in range(combo.count()):
            if combo.itemData(i) == spec.key:
                combo.setCurrentIndex(i)
                break
    return combo


def _make_value_cell_for_kind(self, spec: VarSpec) -> QWidget:
    """按 spec.kind 生成值 cell:enum→QLabel(不可编辑),其他→QLineEdit。"""
    if spec.kind == "enum":
        values = spec.enum_values or ()
        lbl = QLabel(", ".join(values), self)
        lbl.setStyleSheet("color: #555; font-style: italic;")
        return lbl
    return QLineEdit(self)


def _append_axis_row(
    self,
    key: str = "",
    raw_val: Any = "",
) -> None:
    """追加一行:第 0 列 QComboBox(选变量),第 1 列 QLineEdit/QLabel(值)。"""
    r = self._axes_table.rowCount()
    self._axes_table.insertRow(r)

    # 解析已有的 key/raw_val → VarSpec(若可能)
    specs = self._sweep_ctrl.available_vars(self._sweep_ctrl.template)
    spec = None
    for s in specs:
        if s.key == key:
            spec = s
            break
    if spec is None and key:
        # 未知 key:构造一个 dummy VarSpec,combobox 找不到它(失效)
        spec = VarSpec(key=key, label=key + " (未知)", kind="str")

    # 第 0 列:QComboBox
    combo = self._make_combo_for_row(spec)
    self._axes_table.setCellWidget(r, 0, combo)
    combo.currentIndexChanged.connect(self._on_axis_changed)

    # 第 1 列:按 kind
    if spec is not None:
        cell = self._make_value_cell_for_kind(spec)
        if isinstance(cell, QLineEdit):
            text = ", ".join(str(x) for x in raw_val) if isinstance(raw_val, list) else str(raw_val or "")
            cell.setText(text)
            cell.editingFinished.connect(self._sync_form_to_controller)
        self._axes_table.setCellWidget(r, 1, cell)


def _mark_row_orphan(self, r: int) -> None:
    """标记行为失效(红底)。Task 9 加 tooltip 完整化。"""
    for col in (0, 1):
        w = self._axes_table.cellWidget(r, col)
        if w is not None:
            w.setStyleSheet("background-color: #FFD6D6;")


def _mark_row_normal(self, r: int) -> None:
    """清除失效标记。"""
    for col in (0, 1):
        w = self._axes_table.cellWidget(r, col)
        if w is not None:
            w.setStyleSheet("")
```

- [ ] **Step 4: 跑测试,确认 GREEN**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "axes_table or combobox_populated"
```

**Expected:** 2 passed

- [ ] **Step 5: 跑全量,确保不破**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -10
```

**Expected:** 全绿(老测试可能因 `_append_axis_row` 行为变化需要 `_collect_to_dict` 跟进 — Task 8 一起做)

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_form.py inp_tool/tests/test_gui_sweep_form.py
git commit -m "feat(gui): SweepForm 轴表 cell 用 QComboBox/QLineEdit"
```

---

## Task 8: SweepForm 类型校验(失焦时)

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_form.py`
- Modify: `inp_tool/tests/test_gui_sweep_form.py`

- [ ] **Step 1: 写失败的测试**

在 `test_gui_sweep_form.py` 末尾追加:

```python
def test_sweep_form_validates_int_axis_on_edit_finished(monkeypatch):
    """整型轴:输入 'abc' 失焦,cell 红框 + 状态栏报错。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication, QLineEdit
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
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
    # 找刚加的那行(最后一行)的值 cell
    cell = form._axes_table.cellWidget(form._axes_table.rowCount() - 1, 1)
    assert isinstance(cell, QLineEdit)
    cell.setText("abc")
    cell.editingFinished.emit()
    status_text = form._lbl_status.text()
    assert "整数" in status_text or "int" in status_text.lower()


def test_sweep_form_accepts_float_d_notation(monkeypatch):
    """浮点轴接受 '1.0d-3' (FORTRAN 双精度写法)。"""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide2.QtWidgets import QApplication, QLineEdit
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from inp_tool_gui.widgets.sweep_form import SweepForm
    from inp_tool_gui.controllers.sweep_controller import SweepController
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
    # 状态栏不应有「不是浮点数」字样
    text = form._lbl_status.text()
    assert "不是浮点" not in text
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "validates_int or accepts_float_d"
```

**Expected:** FAIL(还没校验逻辑)

- [ ] **Step 3: 实现类型校验 + 重构 _collect_to_dict**

修改 `sweep_form.py`,加 `_validate_value_cell` / `_spec_for_row` / `_on_axis_changed` 方法,并重写 `_collect_to_dict` 和 `_sync_form_to_controller`:

```python
def _validate_value_cell(self, row: int) -> Optional[str]:
    """校验一行的值 cell;返回错误信息或 None(OK)。"""
    spec = self._spec_for_row(row)
    if spec is None:
        return None  # 失效行不校验
    cell = self._axes_table.cellWidget(row, 1)
    if not isinstance(cell, QLineEdit):
        return None  # QLabel(enum)不需要校验
    raw = cell.text().strip()
    if not raw:
        return None  # 空串允许
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if spec.kind == "int":
        for i, p in enumerate(parts, start=1):
            try:
                int(p)
            except ValueError:
                return tg("sweep.live.invalid_int", key=spec.key, idx=i)
    elif spec.kind == "float":
        for i, p in enumerate(parts, start=1):
            try:
                float(p.replace("d", "e").replace("D", "E"))
            except ValueError:
                return tg("sweep.live.invalid_float", key=spec.key, idx=i)
    return None


def _spec_for_row(self, row: int) -> Optional[VarSpec]:
    """取一行的 VarSpec(从 combobox userData)。"""
    combo = self._axes_table.cellWidget(row, 0)
    if not isinstance(combo, QComboBox):
        return None
    key = combo.currentData()
    if not key:
        return None
    for s in self._sweep_ctrl.available_vars(self._sweep_ctrl.template):
        if s.key == key:
            return s
    # 未知 key:返回 dummy
    return VarSpec(key=key, label=key + " (未知)", kind="str")


def _on_axis_changed(self, _idx_or_item=None) -> None:
    """QComboBox.currentIndexChanged 或 QTableWidget.itemChanged 触发。"""
    # 找到发出信号的 combo 所在行
    sender = self.sender()
    row = -1
    for r in range(self._axes_table.rowCount()):
        if self._axes_table.cellWidget(r, 0) is sender:
            row = r
            break
    if row < 0:
        return
    spec = self._spec_for_row(row)
    if spec is None:
        return
    # 重建值 cell(按新 spec 的 kind)
    old_text = ""
    old_cell = self._axes_table.cellWidget(row, 1)
    if isinstance(old_cell, QLineEdit):
        old_text = old_cell.text()
    new_cell = self._make_value_cell_for_kind(spec)
    if isinstance(new_cell, QLineEdit):
        new_cell.setText(old_text)
        new_cell.editingFinished.connect(self._sync_form_to_controller)
    self._axes_table.setCellWidget(row, 1, new_cell)
    self._sync_form_to_controller()


def _collect_to_dict(self) -> Dict[str, Any]:
    """从表单字段收 dict,失败抛 ValueError。"""
    if not self._edit_tpl.text().strip():
        raise ValueError(tg("sweep.live.need_template"))
    if not self._edit_out.text().strip():
        raise ValueError(tg("sweep.live.need_output"))
    sweeps_dict: Dict[str, List[Any]] = {}
    for r in range(self._axes_table.rowCount()):
        spec = self._spec_for_row(r)
        if spec is None:
            continue
        key = spec.key
        cell = self._axes_table.cellWidget(r, 1)
        if isinstance(cell, QLineEdit):
            raw = cell.text().strip()
            try:
                vals = [self._parse_scalar(x) for x in raw.split(",") if x.strip()]
            except ValueError as e:
                raise ValueError(
                    tg("sweep.live.invalid_axis", key=key, val=raw)
                ) from e
            sweeps_dict[key] = vals
        elif isinstance(cell, QLabel):
            # enum:从 spec.enum_values 拿所有
            sweeps_dict[key] = list(spec.enum_values or ())
    return {
        "template": self._edit_tpl.text().strip(),
        "output_dir": self._edit_out.text().strip(),
        "naming": self._edit_naming.text().strip() or "case",
        "sweeps": sweeps_dict,
    }


def _sync_form_to_controller(self) -> None:
    """把表单同步到 controller(失焦触发)。"""
    # 单元级校验(状态栏提示,不阻断)
    for r in range(self._axes_table.rowCount()):
        err = self._validate_value_cell(r)
        if err:
            self._lbl_status.setText(err)
            return
    try:
        d = self._collect_to_dict()
    except ValueError as e:
        if self._sweep_ctrl.is_loaded:
            self._lbl_status.setText(str(e))
        return
    try:
        self._sweep_ctrl.load_from_dict(d)
    except Exception as e:
        self._lbl_status.setText(tg("sweep.live.sync_fail", err=str(e)))
        return
    self._update_status()
```

- [ ] **Step 4: 跑测试**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "validates_int or accepts_float_d"
```

**Expected:** PASS

- [ ] **Step 5: 跑全量**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -10
```

**Expected:** 全绿(老的 12 + 1 顶部 label + 2 cell widget + 2 type validation ≈ 17 个测试全过)

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_form.py inp_tool/tests/test_gui_sweep_form.py
git commit -m "feat(gui): SweepForm 失焦时类型校验(int/float/str)"
```

---

## Task 9: 失效轴警告 + 红底 + 禁用运行

**Files:**
- Modify: `inp_tool/inp_tool_gui/widgets/sweep_form.py`
- Modify: `inp_tool/tests/test_gui_sweep_form.py`

- [ ] **Step 1: 写失败的测试**

在 `test_gui_sweep_form.py` 末尾追加:

```python
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
    # available_vars 只返 1 个有效轴「good」
    def fake_available(template_path=None):
        return [VarSpec(
            key="good", label="good [int] = 1", kind="int",
            block="b", keyword="good", value_idx=0,
        )]
    monkeypatch.setattr(ctrl, "available_vars", fake_available)

    form._append_axis_row("good", "1")
    form._append_axis_row("orphan", "1")
    # 扫描失效
    form._scan_orphan_axes()

    # 运行按钮禁用
    assert not form._btn_run.isEnabled()
    assert not form._btn_run_dry.isEnabled()
    # 状态栏含「未识别」或「失效」
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
    # 状态栏无「未识别」
    assert "未识别" not in form._lbl_status.text()
```

- [ ] **Step 2: 跑测试,确认 RED**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "orphan or no_orphan"
```

**Expected:** FAIL(`_scan_orphan_axes` 未实现)

- [ ] **Step 3: 实现 _scan_orphan_axes + 触发点**

在 `sweep_form.py` 加方法:

```python
def _scan_orphan_axes(self) -> int:
    """扫描所有行,标记失效轴;返回失效数。"""
    valid_keys = {s.key for s in self._sweep_ctrl.available_vars(self._sweep_ctrl.template)}
    orphan_count = 0
    for r in range(self._axes_table.rowCount()):
        spec = self._spec_for_row(r)
        if spec is None:
            continue
        if spec.key in valid_keys:
            self._mark_row_normal(r)
        else:
            self._mark_row_orphan(r)
            orphan_count += 1
    if orphan_count > 0:
        self._lbl_status.setText(tg("sweep.live.orphan_axes", n=orphan_count))
        self._btn_run.setEnabled(False)
        self._btn_run_dry.setEnabled(False)
    else:
        if self._sweep_ctrl.is_loaded:
            self._lbl_status.setText(tg("sweep.live.sync_ok"))
            self._btn_run.setEnabled(True)
            self._btn_run_dry.setEnabled(True)
    return orphan_count
```

补全 `_mark_row_orphan` 的 tooltip:

```python
def _mark_row_orphan(self, r: int) -> None:
    """标记行为失效(红底 + tooltip)。"""
    for col in (0, 1):
        w = self._axes_table.cellWidget(r, col)
        if w is not None:
            w.setStyleSheet("background-color: #FFD6D6;")
            w.setToolTip("此变量不在当前模板中,请删除或重新选模板")
```

让 `_on_axis_changed` 调 `_scan_orphan_axes`(在已有逻辑末尾加一行):

```python
def _on_axis_changed(self, _idx_or_item=None) -> None:
    # ... 已有 cell 重建逻辑 ...
    self._sync_form_to_controller()
    self._scan_orphan_axes()  # 新增
```

让 `_sync_form_to_controller` 末尾也调(模板变更后):

```python
def _sync_form_to_controller(self) -> None:
    # ... 已有逻辑 ...
    self._update_status()
    self._scan_orphan_axes()  # 新增
```

让 `_load_yaml_path` / `_load_json_path` 末尾也调:

```python
def _load_yaml_path(self, path: str) -> None:
    try:
        self._sweep_ctrl.load_from_yaml(path)
    except Exception as exc:
        QMessageBox.critical(self, "加载失败", tg("sweep.load_failed_yaml", err=str(exc)))
        return
    self._sync_from_controller()
    self._scan_orphan_axes()  # 新增
```

- [ ] **Step 4: 跑测试**

```bash
conda run -n cfdchanger pytest tests/test_gui_sweep_form.py -v -k "orphan or no_orphan"
```

**Expected:** 2 passed

- [ ] **Step 5: 跑全量**

```bash
conda run -n cfdchanger pytest tests/ -q 2>&1 | tail -10
```

**Expected:** 全绿(19+ 测试)

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool_gui/widgets/sweep_form.py inp_tool/tests/test_gui_sweep_form.py
git commit -m "feat(gui): 失效轴红底 + 禁用运行 + tooltip"
```

---

## Task 10: 全量回归 + CHANGELOG + 用户手册

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/user-manual/`(找对应章节)
- No code changes

- [ ] **Step 1: 跑全量测试 + 覆盖率**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger pytest tests/ -q --cov=inp_tool --cov-report=term-missing 2>&1 | tail -30
```

**Expected**:
- 全绿
- 新增 / 修改模块覆盖率 ≥ 80%(`sweep_var_combo.py` / `sweep_controller.py` / `sweep_form.py`)

**若覆盖率不足**: 回到对应 Task 加测试,直到 ≥ 80%。

- [ ] **Step 2: 跑 linter / 静态检查**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger ruff check inp_tool_gui/widgets/sweep_var_combo.py inp_tool_gui/widgets/sweep_form.py inp_tool_gui/controllers/sweep_controller.py inp_tool/i18n_gui.py tests/test_gui_sweep_var_combo.py tests/test_gui_sweep_form.py tests/test_gui_sweep_controller.py
```

**Expected:** 0 errors(若有问题,按提示 fix)

- [ ] **Step 3: 更新 CHANGELOG.md**

读 `CHANGELOG.md` 顶部格式(参考 v0.16.0 / v0.16.1 已有的 entry 风格),在「Unreleased」段下加:

```markdown
## [Unreleased]

### Added (GUI Sweep 标签页 UX 重构)
- feat(gui): SweepForm 顶部 3 个 label(模板路径 / 输出目录 / 命名模式)
- feat(gui): SweepForm 轴表 cell 用 QComboBox + QLineEdit
- feat(gui): VarSpec 数据类 + enumerate_vars() 纯函数(sweep_var_combo.py)
- feat(gui): SweepController.available_vars() + 缓存
- feat(gui): 失焦时类型校验(int / float / str / enum)
- feat(gui): 失效轴红底 + 禁用运行 + tooltip 解释
- i18n(gui): 7 个新 key(3 label + 4 错误)
```

- [ ] **Step 4: 更新 docs/user-manual/(找对应章节)**

```bash
ls /home/fz/project/cfd--changer/docs/user-manual/
grep -l "Sweep\|批量" /home/fz/project/cfd--changer/docs/user-manual/*.md
```

找到 Sweep 章节后,加一节「Sweep 标签页新特性」描述本任务的 4 大改进。

如果章节不存在,新建 `XX-sweep-tab-usage.md` 并加到 `README.md` 章节目录。

具体内容:

```markdown
## Sweep 标签页 v0.17 新特性

### 顶部 3 个 label

模板路径 / 输出目录 / 命名模式三个输入框前面新增了文字标签,新手一眼能看明白。

### 轴名可下拉选

之前是自由文本,容易拼错。**现在**:
- 加载 .inp 模板后,Sweep 表的「变量」列变成下拉框,自动列出模板里所有可修改变量
- 同时提供 3 个**枚举轴**(湍流模型 / 能量模型 / 气体模型),值也是下拉
- 没有模板时,只能选 3 个枚举轴

### 值类型校验

整型 / 浮点 / 字符串 / 枚举值,各走各的输入规则:
- 整型:`1, 2, 3`(逗号分隔)
- 浮点:`1.0, 1e6, 1.0d-3`(支持 FORTRAN `d` 写法)
- 字符串:任意文本
- 枚举:自动列合法值(不可输入)

### 失效轴警告

- 加载旧 YAML 含未知轴名 → 该行**变红**,运行按钮禁用
- 模板改了后不存在的轴 → 同样变红
- 鼠标悬停失效行看到提示:「此变量不在当前模板中,请删除或重新选模板」
```

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add CHANGELOG.md docs/user-manual/
git commit -m "docs: CHANGELOG + user-manual Sweep 标签页 v0.17 新特性"
```

---

## Self-Review Checklist(作者自检,已完成)

- [x] **Spec coverage**:
  - §1.2 目标 1(顶部 3 label)→ Task 6
  - §1.2 目标 2(轴名下拉 + 3 枚举)→ Task 2-3 + Task 7
  - §1.2 目标 3(类型校验)→ Task 8
  - §1.2 目标 4(失效轴保护)→ Task 9
  - §1.2 目标 5(空模板兜底)→ Task 4(`available_vars(None)` 返仅枚举)
  - §1.2 目标 6(加载旧 YAML 警告)→ Task 9(`_load_yaml_path` 末尾调 `_scan_orphan_axes`)
  - §4.6 运行按钮禁用规则→ Task 9(`_scan_orphan_axes` + `_update_status` 配合)
  - §5 测试覆盖 → Task 1-10 各自的测试步骤

- [x] **No placeholders**: 每步有完整代码或命令;无 "TODO" / "类似 Task N" / "实现细节"
- [x] **Type consistency**:
  - `VarSpec` 在 sweep_var_combo.py 定义(Task 1),所有后续 Task 一致
  - `available_vars` 在 SweepController(Task 4),widget 通过 `self._sweep_ctrl.available_vars(...)` 调用(Task 7-9)
  - `_scan_orphan_axes` 命名统一(Task 9 引入,后续不再变)

- [x] **Frequent commits**: 每个 Task 结尾有 commit,10 个 commit(Tasks 1-10)
- [x] **TDD**: 所有代码 Task 1-9 遵循「测试先 → RED → 实现 → GREEN → commit」

---

## 验收

- 10 个 Task 全部跑通,所有 commit 在 `feat/sweep-tab-ux-redesign` 分支
- 全量测试全绿
- `sweep_var_combo.py` / `sweep_controller.py` / `sweep_form.py` 覆盖率 ≥ 80%
- CHANGELOG.md + user-manual 更新
- 跑 `git diff main..HEAD --stat` 改动行数符合预期(估算 6 文件 / +600 行 / -100 行)
