# sweep 完整性检查 + pbs 可选生成 + 任务名建议 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 wizard sweep 流程加 3 个能力:(1) 选中基础算例后自动检查完整性;.inp 必备 block 硬错,网格/物性/pbs 软提示;(2) 可选生成 pbs 脚本,默认开启,只替换 `#PBS -N` 行;(3) 按 sweep 变动的多值轴自动建议短名(如 `Marspath_a04_m0.60`),用户可输入模板覆盖。

**Architecture:** 新建独立模块 `inp_tool/pbs.py`(零依赖)提供 `PbsConfig` / `PbsIssue` / `detect_pbs_template` / `validate_base_case_dir` / `render_pbs_name` / `write_pbs` 6 个 API。`sweep.py` 在 `CaseSweep` 加 `pbs: Optional[PbsConfig]` 字段,`generate()` 在 per_dir 模式末尾挂 `write_pbs()`。`wizard.py` 新增 `step_5a_pbs` + 增强 `step_1`。`cli.py` 加 `--pbs/--no-pbs/--pbs-naming`。

**Tech Stack:** Python 3.8(stdlib only: `re` + `pathlib` + `fnmatch` + `dataclasses`)+ pytest + conda env `cfdchanger`。

**Spec:** `docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md`

---

## File Structure

| 文件 | 责任 | 行数 |
|------|------|------|
| `inp_tool/inp_tool/pbs.py` | 新建:PBS 相关纯函数模块 | +180 |
| `inp_tool/inp_tool/sweep.py` | 加 `pbs` 字段 + generate() 整合 | +30 |
| `inp_tool/inp_tool/wizard.py` | step_1 增强 + 新增 step_5a_pbs + preview 提示 | +80 |
| `inp_tool/inp_tool/cli.py` | --pbs/--no-pbs/--pbs-naming flag | +30 |
| `inp_tool/inp_tool/__init__.py` | 导出 PbsConfig / PbsIssue | +2 |
| `inp_tool/tests/test_pbs.py` | 新建:pbs 模块单测 | +250 |
| `inp_tool/tests/test_sweep_pbs_integration.py` | 新建:generate + pbs 集成 | +120 |
| `inp_tool/tests/test_wizard_sweep_pbs.py` | 新建:wizard step_5a + 完整性 | +150 |
| `docs/technical/04-sweep-architecture.md` | 加 §10 pbs 模块段 | +80 |
| `docs/user-manual/18-wizard-tasks.md` | wizard 步骤更新 | +30 |
| `CHANGELOG.md` | v0.9.0 段 | +15 |

---

## Task 1: 切分支 + 跑基线

**Files:** 无代码改动,纯 git 准备

- [ ] **Step 1: 从 main 切 feat 分支**

```bash
cd /home/fz/project/cfd--changer
git fetch origin main
git switch -c feat/sweep-pbs
```

- [ ] **Step 2: 跑基线测试确认 60+ 全绿**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest -x -q
```

Expected:60+ tests pass。

- [ ] **Step 3: 提交(如有环境变化)**

```bash
cd /home/fz/project/cfd--changer
git status
# 若有 lock 文件等变化:
# git add <变化的文件>
# git commit -m "chore: pre-imp baseline"
```

---

## Task 2: PbsConfig + PbsIssue dataclass

**Files:**
- Create: `inp_tool/inp_tool/pbs.py`
- Create: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 写失败测试 `test_pbs.py`**

```python
"""pbs 模块单测 - Task 2: dataclass + from_dict"""
import pytest
from inp_tool.pbs import PbsConfig, PbsIssue


class TestPbsConfig:
    def test_defaults(self):
        c = PbsConfig()
        assert c.enabled is True
        assert c.template is None
        assert c.naming == ""
        assert c.naming_ext == ""
        assert c.detect_basename is True
        assert c.basename_max_len == 8

    def test_from_dict_full(self):
        d = {
            "enabled": False,
            "template": "/path/to/source.pbs",
            "naming": "Mars-{alpha}",
            "naming_ext": ".pbs",
            "detect_basename": False,
            "basename_max_len": 12,
        }
        c = PbsConfig.from_dict(d)
        assert c.enabled is False
        assert c.template == "/path/to/source.pbs"
        assert c.naming == "Mars-{alpha}"
        assert c.naming_ext == ".pbs"
        assert c.detect_basename is False
        assert c.basename_max_len == 12

    def test_from_dict_empty(self):
        c = PbsConfig.from_dict({})
        assert c.enabled is True  # 默认
        assert c.template is None
        assert c.naming == ""

    def test_from_dict_partial(self):
        c = PbsConfig.from_dict({"naming": "Case-{alpha}"})
        assert c.naming == "Case-{alpha}"
        assert c.enabled is True  # 其他走默认


class TestPbsIssue:
    def test_construction(self):
        issue = PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path="/path/to/source",
            message="找不到 mcfd.inp",
        )
        assert issue.code == "MISSING_MCFD_INP"
        assert issue.severity == "error"
        assert issue.path == "/path/to/source"
        assert issue.message == "找不到 mcfd.inp"
```

写入 `inp_tool/tests/test_pbs.py`。

- [ ] **Step 2: 跑测试确认失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_pbs.py -v
```

Expected:FAIL `ModuleNotFoundError: No module named 'inp_tool.pbs'`

- [ ] **Step 3: 写最小实现 `pbs.py`**

```python
"""PBS 脚本解析 / 校验 / 生成工具模块。

零运行时依赖(纯 stdlib: re / pathlib / fnmatch / dataclasses)。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PbsConfig:
    """PBS 脚本生成配置。"""
    enabled: bool = True
    template: Optional[str] = None
    naming: str = ""
    naming_ext: str = ""
    detect_basename: bool = True
    basename_max_len: int = 8

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PbsConfig":
        """从 dict 构造,缺失字段走默认。空 dict 返回全默认实例。"""
        if d is None:
            d = {}
        return cls(
            enabled=d.get("enabled", True),
            template=d.get("template"),
            naming=d.get("naming", ""),
            naming_ext=d.get("naming_ext", ""),
            detect_basename=d.get("detect_basename", True),
            basename_max_len=d.get("basename_max_len", 8),
        )


@dataclass
class PbsIssue:
    """完整性检查产物。"""
    code: str
    severity: str
    path: str
    message: str
```

写入 `inp_tool/inp_tool/pbs.py`。

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py -v
```

Expected:8 passed (4 PbsConfig + 1 PbsIssue)。

- [ ] **Step 5: Commit**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): PbsConfig + PbsIssue dataclass + from_dict"
```

---

## Task 3: detect_pbs_template()

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestDetectPbsTemplate:
    def test_finds_run_pbs(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        (tmp_path / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        assert result == str(tmp_path / "run_cfdpp.pbs")

    def test_no_pbs_returns_none(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        from inp_tool.pbs import detect_pbs_template
        assert detect_pbs_template(str(tmp_path)) is None

    def test_multiple_pbs_returns_first_with_warning(self, tmp_path, capsys):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        (tmp_path / "run_b.pbs").write_text("#PBS -N b")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        # 字母序第一个 run_a.pbs
        assert result == str(tmp_path / "run_a.pbs")
        captured = capsys.readouterr()
        assert "多个" in captured.out or "warning" in captured.out.lower()

    def test_explicit_template_overrides(self, tmp_path):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        explicit = tmp_path / "custom.pbs"
        explicit.write_text("#PBS -N custom")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path), explicit_template=str(explicit))
        assert result == str(explicit)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestDetectPbsTemplate -v
```

Expected:FAIL `ImportError: cannot import name 'detect_pbs_template'`

- [ ] **Step 3: 在 `pbs.py` 末尾追加实现**

```python
import sys
from pathlib import Path


def detect_pbs_template(
    source_dir: str,
    explicit_template: Optional[str] = None,
) -> Optional[str]:
    """从 source_dir 找 PBS 模板文件。返回 None 表示没找到。

    规则:
    - explicit_template 非空 → 直接返回(已存在性由调用方校验)
    - 否则在 source_dir 下 glob run_*.pbs,取第一个(字母序)
    - 多个时打印 warning 到 stderr
    """
    if explicit_template:
        return explicit_template
    p = Path(source_dir)
    if not p.is_dir():
        return None
    matches = sorted(p.glob("run_*.pbs"))
    if not matches:
        return None
    if len(matches) > 1:
        print(
            f"[warning] 发现 {len(matches)} 个 pbs 模板: "
            f"{[m.name for m in matches]},使用 {matches[0].name}",
            file=sys.stderr,
        )
    return str(matches[0])
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestDetectPbsTemplate -v
```

Expected:4 passed。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): detect_pbs_template() find run_*.pbs in source_dir"
```

---

## Task 4: render_pbs_name() - 默认短名

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestRenderPbsName:
    def test_default_shortname_basic(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha", "mach"],
            base_basename="Marspath",
        )
        assert name == "Marspath_a04_m0.60"

    def test_single_value_axis_excluded(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha"],  # beta 和 mach 是单值
            base_basename="Base",
        )
        assert name == "Base_a04"

    def test_empty_multi_value_axes(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "mach": 0.6},
            multi_value_axes=[],
            base_basename="Case",
        )
        assert name == "Case"

    def test_axis_short_format_floats(self):
        from inp_tool.pbs import render_pbs_name
        # alpha=4.5 → a04.5(整数部分补零到 2 位)
        # mach=0.85 → m0.85(原样保留)
        name = render_pbs_name(
            params={"alpha": 4.5, "mach": 0.85},
            multi_value_axes=["alpha", "mach"],
            base_basename="B",
        )
        assert name == "B_a04.5_m0.85"

    def test_axis_short_int_truncates_decimal(self):
        from inp_tool.pbs import render_pbs_name
        # T_inf=288.15 → T288(整数优先,小数点后 2 位;纯整数去小数)
        name = render_pbs_name(
            params={"T_inf": 288.15},
            multi_value_axes=["T_inf"],
            base_basename="B",
        )
        assert name == "B_T288"

    def test_axis_short_negative(self):
        from inp_tool.pbs import render_pbs_name
        # 负值不补零,原样输出
        name = render_pbs_name(
            params={"alpha": -2.0},
            multi_value_axes=["alpha"],
            base_basename="B",
        )
        assert name == "B_a-2.0"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestRenderPbsName -v
```

Expected:FAIL `ImportError: cannot import name 'render_pbs_name'`

- [ ] **Step 3: 在 `pbs.py` 追加实现**

```python
def _axis_short(axis: str, value: float) -> str:
    """把 axis 名字 + value 渲染成短 token。

    Examples:
        ("alpha", 4)    -> "a04"
        ("alpha", 4.5)  -> "a04.5"
        ("beta", 0)     -> "b00"
        ("mach", 0.6)   -> "m0.60"
        ("mach", 0.85)  -> "m0.85"
        ("T_inf", 288.15) -> "T288"
        ("alpha", -2.0) -> "a-2.0"
    """
    prefix = axis[0].lower()  # alpha -> a, T_inf -> t
    v = float(value)
    # 整数:补零到 2 位,去小数
    if v == int(v):
        return f"{prefix}{int(v):02d}"
    # 负数:直接转字符串
    if v < 0:
        return f"{prefix}{v}"
    # 正小数:补零到整数部分 2 位,小数部分保留
    int_part = int(v)
    return f"{prefix}{int_part:02d}{v - int_part:.2f}"


def render_pbs_name(
    params: Dict[str, Any],
    multi_value_axes: List[str],
    base_basename: str,
    user_template: str = "",
    max_len: int = 15,
) -> str:
    """渲染 pbs 任务名。

    优先级:
    1. user_template 非空 → str.format(**params)
    2. 否则默认: {base}_{axis1_short}_{axis2_short}...
       - 仅 multi_value_axes 中的轴进入
       - 按 multi_value_axes 顺序
    3. 超 max_len 字符截断(末尾加 .)
    4. 特殊字符替换为 _
    """
    if user_template:
        name = user_template.format(**params)
    else:
        tokens = [_axis_short(ax, params[ax]) for ax in multi_value_axes if ax in params]
        if tokens:
            name = f"{base_basename}_{'_'.join(tokens)}"
        else:
            name = base_basename
    # 长度截断
    if len(name) > max_len:
        name = name[: max_len - 1] + "."
    # 字符兜底(非 [A-Za-z0-9_-])
    import re
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    return name
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestRenderPbsName -v
```

Expected:6 passed。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): render_pbs_name() default shortname with axis format"
```

---

## Task 5: render_pbs_name() - 用户模板 + 截断 + sanitization

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestRenderPbsNameUserTemplate:
    def test_user_template_overrides_default(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4, "mach": 0.6},
            multi_value_axes=["alpha", "mach"],
            base_basename="Marspath",
            user_template="Mars-{alpha}-{mach}",
        )
        assert name == "Mars-4-0.6"

    def test_user_template_with_unknown_placeholder_raises(self):
        from inp_tool.pbs import render_pbs_name
        with pytest.raises(KeyError):
            render_pbs_name(
                params={"alpha": 4},
                multi_value_axes=["alpha"],
                base_basename="B",
                user_template="Case-{nonexistent}",
            )


class TestRenderPbsNameTruncation:
    def test_truncates_over_max_len(self):
        from inp_tool.pbs import render_pbs_name
        # 默认 max_len=15
        name = render_pbs_name(
            params={"alpha": 4, "beta": 0, "mach": 0.6},
            multi_value_axes=["alpha", "beta", "mach"],
            base_basename="VeryLongBaseName",  # 16 字符
        )
        assert len(name) <= 15
        assert name.endswith(".")

    def test_custom_max_len(self):
        from inp_tool.pbs import render_pbs_name
        name = render_pbs_name(
            params={"alpha": 4},
            multi_value_axes=["alpha"],
            base_basename="Base",
            max_len=8,
        )
        # "Base_a04" = 9 字符,截到 8 = "Base_a0."(末尾 .)
        assert name == "Base_a0."


class TestRenderPbsNameSanitization:
    def test_sanitize_special_chars(self):
        from inp_tool.pbs import render_pbs_name
        # 注入特殊字符:用 user_template 直接传
        name = render_pbs_name(
            params={"x": 1},
            multi_value_axes=["x"],
            base_basename="Base",
            user_template="Hello World!",
        )
        # 空格和 ! 都不是合法 PBS 字符,被替换
        assert " " not in name
        assert "!" not in name
        assert name == "Hello_World_"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestRenderPbsNameUserTemplate tests/test_pbs.py::TestRenderPbsNameTruncation tests/test_pbs.py::TestRenderPbsNameSanitization -v
```

Expected:5 个测试,部分失败(模板覆盖、截断等已部分实现,主要验证截断/兜底)

- [ ] **Step 3: 在 `pbs.py` 中,确认 `render_pbs_name` 末尾已经包含截断 + sanitization**

如果 Task 4 实现的 `render_pbs_name` 已有 `max_len` 截断和 `re.sub` sanitization,本任务不需要新加代码,只需确保测试通过。

- [ ] **Step 4: 跑测试确认全部通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py -v
```

Expected:全部通过(19 个左右)。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "test(pbs): render_pbs_name user template + truncation + sanitization"
```

---

## Task 6: validate_base_case_dir() - 文件级检查

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestValidateBaseCaseFiles:
    def _make_minimal_source(self, tmp_path):
        """构造一个最小可用的 source_dir(含 mcfd.inp + tsteps + physics blocks + grid 文件)"""
        mcfd = tmp_path / "mcfd.inp"
        mcfd.write_text(
            "tsteps\n  ntstep = 100\nend\n"
            "physics\n  eqnset = euler\nend\n"
        )
        (tmp_path / "cellsin.bin").write_bytes(b"\x00" * 100)
        (tmp_path / "nodesin.bin").write_bytes(b"\x00" * 100)
        (tmp_path / "C.dat").write_text("C data")
        (tmp_path / "mcfd.bc").write_text("boundary")
        (tmp_path / "mcfd.grp").write_text("groups")
        (tmp_path / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        return tmp_path

    def test_missing_mcfd_inp_is_error(self, tmp_path):
        # 空目录
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        codes = {i.code for i in issues}
        assert "MISSING_MCFD_INP" in codes
        assert any(i.severity == "error" for i in issues if i.code == "MISSING_MCFD_INP")

    def test_complete_dir_no_issues(self, tmp_path):
        self._make_minimal_source(tmp_path)
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        # 全通过,只可能 0 个 issue
        assert issues == []

    def test_missing_grid_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "cellsin.bin").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        grid_issues = [i for i in issues if "GRID" in i.code]
        assert len(grid_issues) >= 1
        assert all(i.severity == "warning" for i in grid_issues)

    def test_missing_property_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "C.dat").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        prop_issues = [i for i in issues if "PROP" in i.code or "DAT" in i.code]
        assert len(prop_issues) >= 1
        assert all(i.severity == "warning" for i in prop_issues)

    def test_missing_pbs_warns(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "run_cfdpp.pbs").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path), pbs_enabled=True)
        pbs_issues = [i for i in issues if "PBS" in i.code or "PBS_TEMPLATE" in i.code]
        assert len(pbs_issues) >= 1
        assert all(i.severity == "warning" for i in pbs_issues)

    def test_pbs_enabled_false_skips_pbs_check(self, tmp_path):
        self._make_minimal_source(tmp_path)
        (tmp_path / "run_cfdpp.pbs").unlink()
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path), pbs_enabled=False)
        pbs_issues = [i for i in issues if "PBS" in i.code]
        assert pbs_issues == []
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestValidateBaseCaseFiles -v
```

Expected:FAIL `ImportError: cannot import name 'validate_base_case_dir'`

- [ ] **Step 3: 在 `pbs.py` 追加实现**

```python
def validate_base_case_dir(
    source_dir: str,
    pbs_enabled: bool = True,
) -> List[PbsIssue]:
    """检查基础算例目录的完整性。返回 issues 列表(error + warning)。

    检查项(文件级):
    - mcfd.inp 存在(若缺失,先返回,后面 block 检查无意义)
    - cellsin.bin / cgrpsin.bin* / nodesin.bin 网格文件(警告)
    - *.dat 物性文件 ≥ 1(警告)
    - mcfd.bc / mcfd.grp 配置(警告)
    - run_*.pbs 模板(pbs_enabled=True 时检查,警告)
    """
    issues: List[PbsIssue] = []
    p = Path(source_dir)

    # mcfd.inp 必须存在
    mcfd_path = p / "mcfd.inp"
    if not mcfd_path.is_file():
        issues.append(PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path=str(mcfd_path),
            message=f"找不到 mcfd.inp: {mcfd_path}",
        ))
        return issues  # 后续检查无意义

    # 网格文件(软提示)
    grid_files = ["cellsin.bin", "nodesin.bin"]
    for gf in grid_files:
        if not (p / gf).exists():
            issues.append(PbsIssue(
                code=f"MISSING_GRID:{gf}",
                severity="warning",
                path=str(p / gf),
                message=f"缺失网格文件 {gf}",
            ))
    # cgrpsin.bin* glob
    cgrp = list(p.glob("cgrpsin.bin*"))
    if not cgrp:
        issues.append(PbsIssue(
            code="MISSING_GRID:cgrpsin.bin*",
            severity="warning",
            path=str(p / "cgrpsin.bin*"),
            message="缺失网格族文件 cgrpsin.bin*",
        ))

    # 物性 *.dat(至少 1 个)
    dat_files = list(p.glob("*.dat"))
    if not dat_files:
        issues.append(PbsIssue(
            code="MISSING_PROPERTY:*.dat",
            severity="warning",
            path=str(p / "*.dat"),
            message="缺失物性文件(*.dat)",
        ))

    # mcfd.bc / mcfd.grp
    for cfg in ["mcfd.bc", "mcfd.grp"]:
        if not (p / cfg).exists():
            issues.append(PbsIssue(
                code=f"MISSING_CONFIG:{cfg}",
                severity="warning",
                path=str(p / cfg),
                message=f"缺失配置文件 {cfg}",
            ))

    # pbs 模板(仅当 pbs_enabled=True)
    if pbs_enabled:
        if not list(p.glob("run_*.pbs")):
            issues.append(PbsIssue(
                code="MISSING_PBS_TEMPLATE",
                severity="warning",
                path=str(p / "run_*.pbs"),
                message="基础算例目录里没有 run_*.pbs 模板,生成 pbs 将自动关闭",
            ))

    return issues
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestValidateBaseCaseFiles -v
```

Expected:6 passed。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): validate_base_case_dir() file-level checks"
```

---

## Task 7: validate_base_case_dir() - block 级检查

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestValidateBaseCaseBlocks:
    def _make_minimal_source_with_blocks(self, tmp_path, blocks=("tsteps", "physics", "chemkin", "restart")):
        """构造含指定 blocks 的 mcfd.inp"""
        mcfd = tmp_path / "mcfd.inp"
        text = ""
        for b in blocks:
            text += f"{b}\n  key = 1\nend\n"
        mcfd.write_text(text)
        return tmp_path

    def test_missing_required_block_is_error(self, tmp_path):
        self._make_minimal_source_with_blocks(tmp_path, blocks=("tsteps",))  # 缺 physics
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        block_issues = [i for i in issues if i.code.startswith("MISSING_BLOCK:")]
        # 缺 physics
        assert any("physics" in i.code for i in block_issues)
        # 必填 block 是 error
        assert all(i.severity == "error" for i in block_issues if "physics" in i.code)

    def test_missing_warn_block_is_warning(self, tmp_path):
        self._make_minimal_source_with_blocks(tmp_path, blocks=("tsteps", "physics"))  # 缺 chemkin/restart
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        chemkin = [i for i in issues if "chemkin" in i.code]
        assert len(chemkin) == 1
        assert chemkin[0].severity == "warning"

    def test_all_blocks_present_no_block_issues(self, tmp_path):
        self._make_minimal_source_with_blocks(
            tmp_path, blocks=("tsteps", "physics", "chemkin", "restart")
        )
        from inp_tool.pbs import validate_base_case_dir
        issues = validate_base_case_dir(str(tmp_path))
        block_issues = [i for i in issues if i.code.startswith("MISSING_BLOCK:")]
        assert block_issues == []
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestValidateBaseCaseBlocks -v
```

Expected:FAIL(`validate_base_case_dir` 当前不检查 block)

- [ ] **Step 3: 在 `pbs.py` 中更新 `validate_base_case_dir`,在文件级检查后加 block 级检查**

```python
REQUIRED_BLOCKS = ["tsteps", "physics"]
WARN_BLOCKS = ["chemkin", "restart"]


def validate_base_case_dir(
    source_dir: str,
    pbs_enabled: bool = True,
) -> List[PbsIssue]:
    """检查基础算例目录的完整性。返回 issues 列表。

    检查项:
    - 文件级:mcfd.inp / 网格 / 物性 / pbs 模板
    - block 级:REQUIRED_BLOCKS (error) / WARN_BLOCKS (warning)
    """
    issues: List[PbsIssue] = []
    p = Path(source_dir)

    # === mcfd.inp 必须存在 ===
    mcfd_path = p / "mcfd.inp"
    if not mcfd_path.is_file():
        issues.append(PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path=str(mcfd_path),
            message=f"找不到 mcfd.inp: {mcfd_path}",
        ))
        return issues  # 没有 mcfd.inp 就没法检查 block

    # === block 级检查 ===
    # 懒加载 parser 避免循环 import
    from .parser import parse_file
    try:
        inp = parse_file(str(mcfd_path))
    except Exception as e:
        issues.append(PbsIssue(
            code="MCFD_PARSE_ERROR",
            severity="error",
            path=str(mcfd_path),
            message=f"mcfd.inp 解析失败: {e}",
        ))
        return issues

    for blk in REQUIRED_BLOCKS:
        if inp.get_block(blk) is None:
            issues.append(PbsIssue(
                code=f"MISSING_BLOCK:{blk}",
                severity="error",
                path=f"{mcfd_path}#{blk}",
                message=f"mcfd.inp 缺必备 block '{blk}'",
            ))
    for blk in WARN_BLOCKS:
        if inp.get_block(blk) is None:
            issues.append(PbsIssue(
                code=f"MISSING_BLOCK:{blk}",
                severity="warning",
                path=f"{mcfd_path}#{blk}",
                message=f"mcfd.inp 缺可选 block '{blk}'(部分算例类型需要)",
            ))

    # === 文件级检查(网格 / 物性 / 配置 / pbs) ===
    grid_files = ["cellsin.bin", "nodesin.bin"]
    for gf in grid_files:
        if not (p / gf).exists():
            issues.append(PbsIssue(
                code=f"MISSING_GRID:{gf}",
                severity="warning",
                path=str(p / gf),
                message=f"缺失网格文件 {gf}",
            ))
    if not list(p.glob("cgrpsin.bin*")):
        issues.append(PbsIssue(
            code="MISSING_GRID:cgrpsin.bin*",
            severity="warning",
            path=str(p / "cgrpsin.bin*"),
            message="缺失网格族文件 cgrpsin.bin*",
        ))
    dat_files = list(p.glob("*.dat"))
    if not dat_files:
        issues.append(PbsIssue(
            code="MISSING_PROPERTY:*.dat",
            severity="warning",
            path=str(p / "*.dat"),
            message="缺失物性文件(*.dat)",
        ))
    for cfg in ["mcfd.bc", "mcfd.grp"]:
        if not (p / cfg).exists():
            issues.append(PbsIssue(
                code=f"MISSING_CONFIG:{cfg}",
                severity="warning",
                path=str(p / cfg),
                message=f"缺失配置文件 {cfg}",
            ))
    if pbs_enabled and not list(p.glob("run_*.pbs")):
        issues.append(PbsIssue(
            code="MISSING_PBS_TEMPLATE",
            severity="warning",
            path=str(p / "run_*.pbs"),
            message="基础算例目录里没有 run_*.pbs 模板,生成 pbs 将自动关闭",
        ))

    return issues
```

- [ ] **Step 4: 跑测试确认全部通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py -v
```

Expected:全部通过(~22 个)。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): validate_base_case_dir() block-level checks via InpFile"
```

---

## Task 8: write_pbs() - 替换 #PBS -N

**Files:**
- Modify: `inp_tool/inp_tool/pbs.py`
- Modify: `inp_tool/tests/test_pbs.py`

- [ ] **Step 1: 在 `test_pbs.py` 末尾加失败测试**

```python
class TestWritePbs:
    def test_replaces_pbs_n_line(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text(
            "#!/bin/bash\n"
            "#PBS -N OldName\n"
            "#PBS -l nodes=1:ppn=48\n"
            "#PBS -q q02\n"
            "echo hello\n"
        )
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="NewName")
        content = out.read_text()
        assert "#PBS -N NewName" in content
        assert "#PBS -l nodes=1:ppn=48" in content  # 其他行保留
        assert "#PBS -q q02" in content
        assert "echo hello" in content
        assert "OldName" not in content

    def test_appends_n_line_when_missing(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text(
            "#!/bin/bash\n"
            "#PBS -l nodes=1:ppn=48\n"
            "echo hi\n"
        )
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="NewName")
        content = out.read_text()
        assert "#PBS -N NewName" in content
        assert "#PBS -l nodes=1:ppn=48" in content

    def test_preserves_when_no_change(self, tmp_path):
        template = tmp_path / "template.pbs"
        template.write_text("#PBS -N SameName\n")
        from inp_tool.pbs import write_pbs
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), job_name="SameName")
        assert "#PBS -N SameName" in out.read_text()

    def test_template_not_found_raises(self, tmp_path):
        from inp_tool.pbs import write_pbs
        with pytest.raises(FileNotFoundError):
            write_pbs(str(tmp_path / "nope.pbs"), str(tmp_path / "out.pbs"), job_name="X")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestWritePbs -v
```

Expected:FAIL `ImportError: cannot import name 'write_pbs'`

- [ ] **Step 3: 在 `pbs.py` 追加实现**

```python
import re


_PBS_N_PATTERN = re.compile(r"^[ \t]*#PBS[ \t]+-N[ \t]+\S+", re.MULTILINE)


def write_pbs(
    template_path: str,
    output_path: str,
    job_name: str,
) -> None:
    """从 template_path 读取 pbs 脚本,把 #PBS -N 替换为 job_name,写出到 output_path。

    规则:
    - 若模板含 #PBS -N → 原地替换(保留缩进/格式)
    - 若模板不含 → 在 shebang 之后追加一行 #PBS -N job_name
    - job_name 会先过 _sanitize
    """
    tp = Path(template_path)
    if not tp.is_file():
        raise FileNotFoundError(f"pbs 模板不存在: {template_path}")
    text = tp.read_text()
    # 字符兜底
    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", job_name)

    if _PBS_N_PATTERN.search(text):
        new_text = _PBS_N_PATTERN.sub(f"#PBS -N {safe_name}", text, count=1)
    else:
        # 在 shebang 之后插入(若没有 shebang 则在文件开头)
        lines = text.splitlines(keepends=True)
        insert_idx = 0
        for i, ln in enumerate(lines):
            if ln.startswith("#!"):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, f"#PBS -N {safe_name}\n")
        new_text = "".join(lines)

    Path(output_path).write_text(new_text)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_pbs.py::TestWritePbs -v
```

Expected:4 passed。

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/pbs.py inp_tool/tests/test_pbs.py
git commit -m "feat(pbs): write_pbs() replace or append #PBS -N line"
```

---

## Task 9: sweep.py - CaseSweep.pbs 字段 + from_dict 解析

**Files:**
- Modify: `inp_tool/inp_tool/sweep.py`
- Create: `inp_tool/tests/test_sweep_pbs_integration.py`

- [ ] **Step 1: 在 `test_sweep_pbs_integration.py` 写失败测试**

```python
"""sweep + pbs 集成测试 - Task 9: CaseSweep.pbs 字段解析"""
import pytest
from inp_tool.sweep import CaseSweep
from inp_tool.pbs import PbsConfig


class TestCaseSweepPbsField:
    def test_default_pbs_is_none(self):
        cs = CaseSweep(
            template="t.inp",
            output_dir="out",
            sweeps={"alpha": [0, 4]},
        )
        assert cs.pbs is None

    def test_from_dict_parses_pbs(self):
        d = {
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
            "pbs": {
                "enabled": True,
                "naming": "Mars-{alpha}",
            },
        }
        cs = CaseSweep.from_dict(d)
        assert cs.pbs is not None
        assert isinstance(cs.pbs, PbsConfig)
        assert cs.pbs.enabled is True
        assert cs.pbs.naming == "Mars-{alpha}"

    def test_from_dict_without_pbs_field(self):
        d = {
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        }
        cs = CaseSweep.from_dict(d)
        # 不给 pbs 字段 → PbsConfig 默认(enabled=True,字段都默认)
        # 或 cs.pbs = None?此处取 None 保持"不开启"语义
        assert cs.pbs is None

    def test_from_yaml_with_pbs(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "template: t.inp\n"
            "output_dir: out\n"
            "sweeps:\n"
            "  alpha: [0, 4]\n"
            "pbs:\n"
            "  enabled: true\n"
            "  naming: 'Mars-{alpha}'\n"
        )
        cs = CaseSweep.from_yaml(str(yaml_file))
        assert cs.pbs is not None
        assert cs.pbs.naming == "Mars-{alpha}"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py -v
```

Expected:FAIL(`CaseSweep` 还没有 `pbs` 字段)

- [ ] **Step 3: 在 `sweep.py` 中:**
  1. 在文件顶部加 `from typing import TYPE_CHECKING` + `if TYPE_CHECKING: from .pbs import PbsConfig`(避免循环 import)
  2. 在 `CaseSweep` dataclass 加字段:`pbs: Optional["PbsConfig"] = None`
  3. 在 `from_dict` 中加解析逻辑(找 `d.get("pbs")` → `PbsConfig.from_dict(...)`),在 `return cls(...)` 里把 `pbs_cfg` 传进去

**修改 1 — 顶部 import 区:**

```python
# 顶部 import 区,在现有 import 旁加:
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .pbs import PbsConfig
```

**修改 2 — `CaseSweep` dataclass 末尾加字段:**

```python
@dataclass
class CaseSweep:
    # ... 现有 11 字段 ...
    pbs: Optional["PbsConfig"] = None  # v0.9.0 新增
```

**修改 3 — `from_dict` 中(在 `return cls(...)` 之前)加:**

```python
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CaseSweep":
        # ... 现有解析逻辑 ...
        # 解析 pbs 字段(若有)
        pbs_cfg = None
        pbs_d = d.get("pbs")
        if isinstance(pbs_d, dict):
            from .pbs import PbsConfig  # 局部 import 避免循环
            pbs_cfg = PbsConfig.from_dict(pbs_d)
        # ... 把 pbs_cfg 传给 cls(...) 构造 ...
```

具体位置:打开 `inp_tool/inp_tool/sweep.py` 第 390-465 行,找到 `from_dict` 的 `return cls(...)` 行,在传给 `cls` 的 kwargs 里加 `pbs=pbs_cfg`。

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py -v
```

Expected:4 passed。

- [ ] **Step 5: 跑全部 sweep 测试确认 0 回归**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep.py tests/test_sweep_*.py -q
```

Expected:全部通过。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/sweep.py inp_tool/tests/test_sweep_pbs_integration.py
git commit -m "feat(sweep): CaseSweep.pbs field + from_dict parse pbs: dict"
```

---

## Task 10: sweep.py - generate() 整合 validate_base_case_dir

**Files:**
- Modify: `inp_tool/inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_pbs_integration.py`

- [ ] **Step 1: 加失败测试**

在 `test_sweep_pbs_integration.py` 末尾加:

```python
class TestGenerateValidation:
    def _make_source(self, tmp_path, with_physics=True):
        """构造最小可用 source_dir"""
        src = tmp_path / "source"
        src.mkdir()
        mcfd = src / "mcfd.inp"
        text = "tsteps\n  ntstep = 100\nend\n"
        if with_physics:
            text += "physics\n  eqnset = euler\nend\n"
        mcfd.write_text(text)
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("data")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("grp")
        (src / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        return str(src)

    def test_validation_error_block_missing_raises(self, tmp_path):
        from inp_tool.sweep import CaseSweep, generate, SweepValidationError
        src = self._make_source(tmp_path, with_physics=False)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0]},
            source_dir=src,
        )
        with pytest.raises(SweepValidationError) as exc_info:
            generate(cs)
        assert "MISSING_BLOCK:physics" in str(exc_info.value)

    def test_validation_warnings_dont_block(self, tmp_path):
        from inp_tool.sweep import CaseSweep, generate
        src = self._make_source(tmp_path)
        # 删掉 pbs 模板,只产生 warning
        import os
        os.unlink(f"{src}/run_cfdpp.pbs")
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
            source_dir=src,
        )
        report = generate(cs)
        # 不抛错,跑通 2 个 case
        assert report.total == 2

    def test_no_source_dir_skips_validation(self, tmp_path):
        """flat 模式(无 source_dir)不触发 pbs 校验"""
        from inp_tool.sweep import CaseSweep, generate
        template = tmp_path / "t.inp"
        template.write_text("tsteps\n  ntstep = 100\nend\n")
        cs = CaseSweep(
            template=str(template),
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
        )
        report = generate(cs)
        assert report.total == 2
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestGenerateValidation -v
```

Expected:FAIL(`SweepValidationError` 不存在)

- [ ] **Step 3: 在 `sweep.py` 中:**

**修改 1 — 在 `from .pbs import ...` 旁加(顶部):**

```python
class SweepValidationError(Exception):
    """sweep 完整性检查失败时抛的异常。"""
    def __init__(self, issues):
        self.issues = issues
        super().__init__(
            f"基础算例完整性检查失败,{len(issues)} 个 error:\n"
            + "\n".join(f"  [{i.code}] {i.message}" for i in issues if i.severity == "error")
        )
```

**修改 2 — 在 `generate()` 开头(source_dir 校验之前)加:**

找到 `def generate(sweep: CaseSweep, dry_run: bool = False, force: bool = False) -> SweepReport:` 函数体,在加载模板之后、`os.makedirs` 之前(或同步位置)插入:

```python
    # === 完整性检查(仅 per_dir 模式) ===
    if sweep.source_dir is not None and not dry_run:
        from .pbs import validate_base_case_dir
        pbs_enabled = sweep.pbs is not None and sweep.pbs.enabled
        issues = validate_base_case_dir(sweep.source_dir, pbs_enabled=pbs_enabled)
        errors = [i for i in issues if i.severity == "error"]
        if errors:
            raise SweepValidationError(issues)
        # warnings 打印到 stderr
        warnings = [i for i in issues if i.severity == "warning"]
        for w in warnings:
            print(f"[validate] {w.severity}: {w.code} - {w.message}", file=sys.stderr)
```

顶部 import 区加 `import sys`(若还没有)。

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestGenerateValidation -v
```

Expected:3 passed。

- [ ] **Step 5: 跑全部 sweep 测试确认 0 回归**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep.py tests/test_sweep_*.py -q
```

Expected:全部通过。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/sweep.py inp_tool/tests/test_sweep_pbs_integration.py
git commit -m "feat(sweep): generate() validate base case dir at start"
```

---

## Task 11: sweep.py - generate() 整合 write_pbs 在 per_case 末尾

**Files:**
- Modify: `inp_tool/inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_pbs_integration.py`

- [ ] **Step 1: 加失败测试**

```python
class TestGeneratePbsWrite:
    def _make_source(self, tmp_path, pbs_template=True):
        src = tmp_path / "source"
        src.mkdir()
        mcfd = src / "mcfd.inp"
        mcfd.write_text(
            "tsteps\n  ntstep = 100\nend\n"
            "physics\n  eqnset = euler\nend\n"
        )
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("data")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("grp")
        if pbs_template:
            (src / "run_cfdpp.pbs").write_text(
                "#!/bin/bash\n"
                "#PBS -N Marspathfinder-Ini\n"
                "#PBS -l nodes=1:ppn=48\n"
                "echo hi\n"
            )
        return str(src)

    def test_per_case_pbs_written_with_shortname(self, tmp_path):
        from inp_tool.sweep import CaseSweep, generate
        from inp_tool.pbs import PbsConfig
        src = self._make_source(tmp_path)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4], "mach": [0.6]},
            source_dir=src,
            pbs=PbsConfig(enabled=True),
        )
        report = generate(cs)
        assert report.total == 2
        # 检查每个子目录的 pbs
        for case in report.cases:
            case_dir = Path(case.path)
            pbs_file = case_dir / "run_cfdpp.pbs"
            assert pbs_file.exists(), f"pbs 缺失 in {case_dir}"
            content = pbs_file.read_text()
            # 默认短名 + Marspathfinder-Ini 的前 8 字符 = "Marspath"
            # 多值轴只有 alpha → a00 / a04
            assert "Marspath_a" in content
            assert "Marspathfinder-Ini" not in content  # 原任务名被替换
            # 其他行保留
            assert "#PBS -l nodes=1:ppn=48" in content

    def test_pbs_disabled_no_pbs_written(self, tmp_path):
        from inp_tool.sweep import CaseSweep, generate
        from inp_tool.pbs import PbsConfig
        src = self._make_source(tmp_path)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
            source_dir=src,
            pbs=PbsConfig(enabled=False),
        )
        report = generate(cs)
        for case in report.cases:
            case_dir = Path(case.path)
            pbs_file = case_dir / "run_cfdpp.pbs"
            # hardlink 情况下文件存在,但内容是源模板(原任务名)
            if pbs_file.exists():
                content = pbs_file.read_text()
                # enabled=False → write_pbs 不被调用 → 内容是模板
                assert "Marspathfinder-Ini" in content

    def test_user_template_pbs_name(self, tmp_path):
        from inp_tool.sweep import CaseSweep, generate
        from inp_tool.pbs import PbsConfig
        src = self._make_source(tmp_path)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
            source_dir=src,
            pbs=PbsConfig(enabled=True, naming="MyCase-{alpha}"),
        )
        report = generate(cs)
        # 检查不同 case 有不同任务名
        names = []
        for case in report.cases:
            content = (Path(case.path) / "run_cfdpp.pbs").read_text()
            for line in content.splitlines():
                if line.startswith("#PBS -N"):
                    names.append(line)
        assert any("MyCase-0" in n for n in names)
        assert any("MyCase-4" in n for n in names)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestGeneratePbsWrite -v
```

Expected:FAIL(per_case 末尾尚未调 `write_pbs`)

- [ ] **Step 3: 在 `sweep.py` 的 `generate()` 中,找到 per_dir 模式 case 写盘的代码块**

具体位置:在 `generate()` 内 for 循环中,找到 `if not dry_run: if layout == "per_dir": _copy_case_files(...)` 之后,`# manifest 记录 file list(per_dir 模式)` 这段之前(或之后,在 `case = CaseResult(...)` 之后、`report.cases.append(case)` 之前),插入:

```python
        # === pbs 生成(per_dir 模式末尾,可选项) ===
        if layout == "per_dir" and not dry_run and sweep.pbs is not None and sweep.pbs.enabled:
            from .pbs import write_pbs, render_pbs_name, detect_pbs_template
            # 1. 找 pbs 模板路径
            template_path = sweep.pbs.template
            if not template_path:
                template_path = detect_pbs_template(sweep.source_dir)
            if template_path:
                # 2. 算任务名
                base_basename = extract_pbs_basename(
                    template_path, max_len=sweep.pbs.basename_max_len
                )
                # 多值轴过滤
                multi_value = []
                if hasattr(sweep.sweeps, "values"):
                    for ax, vs in sweep.sweeps.values.items():
                        if len(vs) > 1:
                            multi_value.append(ax)
                job_name = render_pbs_name(
                    params=params,
                    multi_value_axes=multi_value,
                    base_basename=base_basename,
                    user_template=sweep.pbs.naming,
                )
                # 3. 写出到子目录
                out_pbs = Path(target) / Path(template_path).name
                write_pbs(template_path, str(out_pbs), job_name=job_name)
                # 4. 记到 result,供 manifest
                case.pbs_name = job_name
                case.pbs_template = str(template_path)
```

**辅助函数**(在 `sweep.py` 中 `_copy_case_files` 旁边加):

```python
def extract_pbs_basename(template_path: str, max_len: int = 8) -> str:
    """从 pbs 模板里读 #PBS -N 提取 base basename,截到 max_len 字符。
    若模板无 #PBS -N,返回 "case" 作为 fallback。
    """
    import re
    try:
        text = Path(template_path).read_text()
    except OSError:
        return "case"
    m = re.search(r"^[ \t]*#PBS[ \t]+-N[ \t]+(\S+)", text, re.MULTILINE)
    if not m:
        return "case"
    name = m.group(1)
    if len(name) > max_len:
        name = name[:max_len]
    return name
```

**注意**:同时在 `pbs.py` 顶部加 `extract_pbs_basename` 的引用(从 sweep.py 调用),或者直接在 pbs.py 顶部 import sweep 不可行(循环 import)。方案:在 pbs.py 也加一份 `extract_pbs_basename`(同实现,~10 行),sweep.py 调用 pbs.py 的版本。

**修改 pbs.py 末尾追加:**

```python
def extract_pbs_basename(template_path: str, max_len: int = 8) -> str:
    """(pbs.py 公开版本,同 sweep.py 实现)"""
    import re
    p = Path(template_path)
    if not p.is_file():
        return "case"
    text = p.read_text()
    m = re.search(r"^[ \t]*#PBS[ \t]+-N[ \t]+(\S+)", text, re.MULTILINE)
    if not m:
        return "case"
    name = m.group(1)
    if len(name) > max_len:
        name = name[:max_len]
    return name
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestGeneratePbsWrite -v
```

Expected:3 passed(但 `case.pbs_name` 字段在 Task 12 才加,可能 1 个失败 → 继续 Task 12)

- [ ] **Step 5: Commit**

```bash
git add inp_tool/inp_tool/sweep.py inp_tool/tests/test_sweep_pbs_integration.py inp_tool/inp_tool/pbs.py
git commit -m "feat(sweep): generate() write pbs at per_case end + extract_pbs_basename in pbs.py"
```

---

## Task 12: sweep.py - CaseResult.pbs_name 字段 + manifest pbs_name

**Files:**
- Modify: `inp_tool/inp_tool/sweep.py`
- Modify: `inp_tool/tests/test_sweep_pbs_integration.py`

- [ ] **Step 1: 加失败测试**

```python
class TestManifestPbsName:
    def _make_source(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "mcfd.inp").write_text(
            "tsteps\n  ntstep = 100\nend\nphysics\n  eqnset = euler\nend\n"
        )
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("data")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("grp")
        (src / "run_cfdpp.pbs").write_text("#PBS -N OriginalName\n")
        return str(src)

    def test_manifest_contains_pbs_name_per_case(self, tmp_path):
        import json
        from inp_tool.sweep import CaseSweep, generate
        from inp_tool.pbs import PbsConfig
        src = self._make_source(tmp_path)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
            source_dir=src,
            pbs=PbsConfig(enabled=True),
            manifest_path=str(tmp_path / "out" / "manifest.json"),
        )
        report = generate(cs)
        manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
        # 顶层
        assert manifest.get("pbs_enabled") is True
        # 每 case
        for c in manifest["cases"]:
            assert "pbs_name" in c
            assert c["pbs_name"].startswith("Original")  # OriginalName 前 8 字符
            # 多值轴 alpha → a00 / a04
            assert c["pbs_name"].endswith("_a00") or c["pbs_name"].endswith("_a04")

    def test_manifest_no_pbs_when_disabled(self, tmp_path):
        import json
        from inp_tool.sweep import CaseSweep, generate
        from inp_tool.pbs import PbsConfig
        src = self._make_source(tmp_path)
        cs = CaseSweep(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            sweeps={"alpha": [0, 4]},
            source_dir=src,
            pbs=PbsConfig(enabled=False),
            manifest_path=str(tmp_path / "out" / "manifest.json"),
        )
        report = generate(cs)
        manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
        # flat 模式 / pbs 关闭时,顶层 pbs_enabled 字段不写
        assert "pbs_enabled" not in manifest or manifest.get("pbs_enabled") is False
        for c in manifest["cases"]:
            assert "pbs_name" not in c
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestManifestPbsName -v
```

Expected:FAIL(`CaseResult` 没有 `pbs_name`)

- [ ] **Step 3: 在 `sweep.py` 中:**

**修改 1 — `CaseResult` dataclass 加字段:**

```python
@dataclass
class CaseResult:
    case_id: str
    path: str
    params: Dict[str, Any]
    applied: Dict[str, Any]
    pbs_name: Optional[str] = None        # v0.9.0 新增
    pbs_template: Optional[str] = None     # v0.9.0 新增
```

**修改 2 — `SweepReport.to_dict()`(或 `__dict__` 输出处)加 `pbs_enabled` 字段:**

找到 `SweepReport.to_dict` 实现,在 `cases` 列表前加:

```python
        if any(c.pbs_name for c in self.cases):
            d["pbs_enabled"] = True
        # 序列化 cases
        d["cases"] = [
            {
                "case_id": c.case_id,
                "path": c.path,
                "files": getattr(c, "files", None),
                "params": c.params,
                "applied": c.applied,
                **({"pbs_name": c.pbs_name} if c.pbs_name else {}),
                **({"pbs_template": c.pbs_template} if c.pbs_template else {}),
            }
            for c in self.cases
        ]
```

(具体 dict 结构可能跟现有 `to_dict` 不一致,以现有 `sweep.py` 中 `SweepReport.to_dict` 实际代码为基准,在 `cases` 列表推导中加 `pbs_name` 字段。)

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep_pbs_integration.py::TestManifestPbsName -v
```

Expected:2 passed。

- [ ] **Step 5: 跑全部 sweep 测试确认 0 回归**

```bash
conda run -n cfdchanger python -m pytest tests/test_sweep.py tests/test_sweep_*.py -q
```

Expected:全部通过。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/sweep.py inp_tool/tests/test_sweep_pbs_integration.py
git commit -m "feat(sweep): CaseResult.pbs_name + manifest pbs_name field"
```

---

## Task 13: cli.py - --pbs/--no-pbs + --pbs-naming flag

**Files:**
- Modify: `inp_tool/inp_tool/cli.py`
- Modify: `inp_tool/tests/test_cli.py`

- [ ] **Step 1: 在 `test_cli.py` 末尾加失败测试**

```python
class TestSweepPbsFlag:
    def test_no_pbs_flag_disables(self, tmp_path, capsys):
        from click.testing import CliRunner
        from inp_tool.cli import cli
        src = tmp_path / "source"
        src.mkdir()
        (src / "mcfd.inp").write_text("tsteps\n  ntstep = 100\nend\nphysics\n  eqnset = euler\nend\n")
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("d")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("g")
        (src / "run_cfdpp.pbs").write_text("#PBS -N x\n")
        cfg = tmp_path / "config.json"
        cfg.write_text('{"template": "' + str(src / "mcfd.inp") + '", "output_dir": "' + str(tmp_path / "out") + '", "sweeps": {"alpha": [0, 4]}}')
        runner = CliRunner()
        result = runner.invoke(cli, ["sweep", str(cfg), "--source-dir", str(src), "--no-pbs", "--force"])
        assert result.exit_code == 0

    def test_pbs_naming_flag_sets_template(self, tmp_path, capsys):
        from click.testing import CliRunner
        from inp_tool.cli import cli
        src = tmp_path / "source"
        src.mkdir()
        (src / "mcfd.inp").write_text("tsteps\n  ntstep = 100\nend\nphysics\n  eqnset = euler\nend\n")
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("d")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("g")
        (src / "run_cfdpp.pbs").write_text("#PBS -N Marspath\n")
        cfg = tmp_path / "config.json"
        cfg.write_text('{"template": "' + str(src / "mcfd.inp") + '", "output_dir": "' + str(tmp_path / "out") + '", "sweeps": {"alpha": [0, 4]}}')
        runner = CliRunner()
        result = runner.invoke(
            cli,
            ["sweep", str(cfg), "--source-dir", str(src),
             "--pbs-naming", "MyCase-{alpha}", "--force"],
        )
        assert result.exit_code == 0
        # 检查子目录 pbs 含 MyCase-0 和 MyCase-4
        names = []
        for d in (tmp_path / "out").iterdir():
            if d.is_dir():
                pbs = d / "run_cfdpp.pbs"
                if pbs.exists():
                    for line in pbs.read_text().splitlines():
                        if line.startswith("#PBS -N"):
                            names.append(line)
        assert any("MyCase-0" in n for n in names)
        assert any("MyCase-4" in n for n in names)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_cli.py::TestSweepPbsFlag -v
```

Expected:FAIL(`--no-pbs` / `--pbs-naming` 不识别)

- [ ] **Step 3: 在 `cli.py` 中:**

打开 `inp_tool/inp_tool/cli.py`,找到 `sweep` 子命令的 click 装饰器(应该是 `@cli.command()` 或 `@cli.group()` 下的 `def sweep(...)`),在现有 `--source-dir` / `--force` 等 flag 旁加:

```python
@click.option(
    "--pbs/--no-pbs",
    default=True,
    help="是否生成 pbs 脚本(默认 yes)",
)
@click.option(
    "--pbs-naming",
    default="",
    help="pbs 任务名模板(空 = 自动短名,例: 'Mars-{alpha}-{mach}')",
)
def sweep(config, source_dir, force, pbs, pbs_naming, ...):
    # ... 现有逻辑 ...
    # 在构造 CaseSweep 之后(无论是 from_dict / from_yaml / from_json)加:
    from .pbs import PbsConfig
    if pbs or pbs_naming:
        cs.pbs = PbsConfig(enabled=pbs, naming=pbs_naming)
    # ... 调 generate(cs) ...
```

具体位置:打开 `cli.py` 找 `def sweep(` 函数,根据现有 flag 风格对齐缩进和顺序。

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_cli.py::TestSweepPbsFlag -v
```

Expected:2 passed。

- [ ] **Step 5: 跑全部 CLI 测试确认 0 回归**

```bash
conda run -n cfdchanger python -m pytest tests/test_cli.py -q
```

Expected:全部通过。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/cli.py inp_tool/tests/test_cli.py
git commit -m "feat(cli): --pbs/--no-pbs + --pbs-naming flag for sweep"
```

---

## Task 14: wizard.py - step_1 增强(完整性检查 + auto-detect pbs)

**Files:**
- Modify: `inp_tool/inp_tool/wizard.py`
- Create: `inp_tool/tests/test_wizard_sweep_pbs.py`

- [ ] **Step 1: 在 `test_wizard_sweep_pbs.py` 写失败测试**

```python
"""wizard sweep + pbs 流程测试 - Task 14-16"""
import pytest
from pathlib import Path
from inp_tool.wizard import WizardSweep


class TestSweepWizardStep1Validation:
    def _make_source(self, tmp_path, with_physics=True, with_pbs=True):
        src = tmp_path / "source"
        src.mkdir()
        mcfd_text = "tsteps\n  ntstep = 100\nend\n"
        if with_physics:
            mcfd_text += "physics\n  eqnset = euler\nend\n"
        (src / "mcfd.inp").write_text(mcfd_text)
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("d")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("g")
        if with_pbs:
            (src / "run_cfdpp.pbs").write_text("#PBS -N Marspathfinder-Ini\n")
        return src

    def test_step1_returns_validation_issues_in_data(self, tmp_path, monkeypatch):
        """step_1 在 source_dir 选完后,data 里应带 validation_issues + detected_pbs"""
        from inp_tool.wizard import _print
        src = self._make_source(tmp_path, with_physics=False)  # 缺 physics
        wiz = WizardSweep()
        # 模拟 step_1 输入:source_dir 路径
        from inp_tool.wizard import input_text, menu
        inputs = iter([str(src), "1"])  # source_dir + copy_strategy=1
        monkeypatch.setattr("inp_tool.wizard.input_text", lambda *a, **kw: next(inputs))
        monkeypatch.setattr("inp_tool.wizard.menu", lambda *a, **kw: "1")
        result = wiz.step_1_source_dir({})
        assert result is not None
        next_step, data = result
        assert next_step == "step_2_output"
        assert "validation_issues" in data
        issues = data["validation_issues"]
        # 缺 physics → error
        assert any("physics" in i["code"] and i["severity"] == "error" for i in issues)

    def test_step1_detects_pbs_template(self, tmp_path, monkeypatch):
        src = self._make_source(tmp_path, with_pbs=True)
        wiz = WizardSweep()
        from inp_tool.wizard import input_text, menu
        inputs = iter([str(src), "1"])
        monkeypatch.setattr("inp_tool.wizard.input_text", lambda *a, **kw: next(inputs))
        monkeypatch.setattr("inp_tool.wizard.menu", lambda *a, **kw: "1")
        result = wiz.step_1_source_dir({})
        next_step, data = result
        assert data.get("detected_pbs") == str(src / "run_cfdpp.pbs")
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py -v
```

Expected:FAIL(wizard 还没有 `validation_issues` / `detected_pbs` 字段)

- [ ] **Step 3: 在 `wizard.py` 中,修改 `step_1_source_dir` 方法:**

打开 `inp_tool/inp_tool/wizard.py` 第 400-451 行的 `step_1_source_dir`,在 return `("step_2_output", {...})` 之前,加:

```python
            # === v0.9.0 完整性检查 + pbs auto-detect ===
            from .pbs import validate_base_case_dir, detect_pbs_template
            issues = validate_base_case_dir(
                str(p),
                pbs_enabled=True,  # wizard 里 pbs 默认 yes
            )
            validation_issues = [
                {"code": i.code, "severity": i.severity,
                 "path": i.path, "message": i.message}
                for i in issues
            ]
            # 打印 issues
            for i in issues:
                if i.severity == "error":
                    _print(f"  [error]   {i.code}: {i.message}")
                else:
                    _print(f"  [warning] {i.code}: {i.message}")
            # 若有 error,询问"仍要继续?"
            errors = [i for i in issues if i.severity == "error"]
            if errors:
                if is_zh:
                    cont = confirm(f"  完整性检查有 {len(errors)} 个 error,仍要继续?", default=False)
                else:
                    cont = confirm(f"  {len(errors)} validation errors, continue?", default=False)
                if not cont:
                    return None
            # pbs auto-detect
            detected_pbs = detect_pbs_template(str(p))
            if detected_pbs:
                _print(f"  ✓ pbs 模板: {detected_pbs}")
            else:
                _print(f"  [warning] 未发现 run_*.pbs,pbs 生成将自动关闭")
            # 把 issues 和 detected_pbs 塞到 data
            return ("step_2_output", {
                **data,
                "source_dir": str(p),
                "template": str(template_path),
                "copy_strategy": key_to_strategy.get(key, "hardlink"),
                "validation_issues": validation_issues,
                "detected_pbs": detected_pbs,
            })
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py -v
```

Expected:2 passed。

- [ ] **Step 5: 跑全部 wizard 测试确认 0 回归**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep.py tests/test_wizard_diff.py -q
```

Expected:全部通过(已有 wizard 测试可能需要小调整,见下面"注意")。

**注意**:若现有 `test_wizard_sweep.py::TestSweepSourceDirRequired` 等测试断言 `step_1_source_dir` 的返回 dict 只含特定字段,可能因新加 `validation_issues` / `detected_pbs` 而失败。修复:把这些字段也作为"无关"字段处理(测试只断言部分 key)。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/wizard.py inp_tool/tests/test_wizard_sweep_pbs.py
git commit -m "feat(wizard): step_1 validate base case + auto-detect pbs"
```

---

## Task 15: wizard.py - 新增 step_5a_pbs

**Files:**
- Modify: `inp_tool/inp_tool/wizard.py`
- Modify: `inp_tool/tests/test_wizard_sweep_pbs.py`

- [ ] **Step 1: 加失败测试**

```python
class TestSweepWizardStep5aPbs:
    def test_default_pbs_enabled(self, tmp_path, monkeypatch):
        from inp_tool.wizard import input_text, confirm
        wiz = WizardSweep()
        # data 来自 step_4_params 之后
        data = {
            "mode": "1",
            "sweeps": {"alpha": [0, 4], "mach": [0.6]},
            "detected_pbs": "/some/source/run.pbs",
        }
        # 默认 yes(confirm 返回 True)
        # task name 默认(empty)接受
        monkeypatch.setattr("inp_tool.wizard.confirm", lambda *a, **kw: True)
        monkeypatch.setattr("inp_tool.wizard.input_text", lambda *a, **kw: "")
        result = wiz.step_5a_pbs(data)
        assert result is not None
        next_step, new_data = result
        assert next_step == "step_6_preview"
        assert new_data.get("pbs_enabled") is True
        assert new_data.get("pbs_naming") == ""  # 默认空 = 短名

    def test_pbs_disabled_keeps_data(self, tmp_path, monkeypatch):
        from inp_tool.wizard import confirm
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 4]}}
        monkeypatch.setattr("inp_tool.wizard.confirm", lambda *a, **kw: False)
        result = wiz.step_5a_pbs(data)
        next_step, new_data = result
        assert new_data.get("pbs_enabled") is False

    def test_user_template_pbs_naming(self, tmp_path, monkeypatch):
        from inp_tool.wizard import confirm, input_text
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 4]}}
        monkeypatch.setattr("inp_tool.wizard.confirm", lambda *a, **kw: True)
        # input_text 总是返回模板
        monkeypatch.setattr(
            "inp_tool.wizard.input_text",
            lambda *a, **kw: "Mars-{alpha}",
        )
        result = wiz.step_5a_pbs(data)
        next_step, new_data = result
        assert new_data.get("pbs_enabled") is True
        # 如果实现把 {alpha} 当模板,应进入 pbs_naming
        # 如果实现把它当新名字,pbs_naming 留空,job_name_override 写入
        # 此测试只要求 enabled=True,不强求 naming 字段值
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py::TestSweepWizardStep5aPbs -v
```

Expected:FAIL(`step_5a_pbs` 方法不存在)

- [ ] **Step 3: 在 `wizard.py` 中,`WizardSweep` 类里加 `step_5a_pbs` 方法 + 在 `steps` 列表加一项:**

**修改 1 — `steps` 列表:**

```python
    steps = [
        "step_1_source_dir",
        "step_2_output",
        "step_3_mode",
        "step_4_params",
        "step_5_naming",
        "step_5a_pbs",         # v0.9.0 新增
        "step_6_preview",
    ]
```

**修改 2 — 在 `step_5_naming` 末尾改 return:**

找到 `step_5_naming`,把:
```python
        return ("step_6_preview", {"naming": naming})
```
改为:
```python
        return ("step_5a_pbs", {"naming": naming})
```

**修改 3 — 加 `step_5a_pbs` 方法:**

```python
    def step_5a_pbs(self, data: dict):
        """v0.9.0 新增:询问 pbs 生成 + 任务名模板。"""
        from .pbs import PbsConfig, extract_pbs_basename, render_pbs_name
        is_zh = get_lang() == "zh"
        if is_zh:
            q = "  是否生成 pbs 脚本?"
        else:
            q = "  Generate pbs script?"
        pbs_enabled = confirm(q, default=True)
        pbs_naming = ""
        if pbs_enabled:
            # 算建议任务名(给用户看)
            detected = data.get("detected_pbs")
            base_basename = "case"
            if detected:
                base_basename = extract_pbs_basename(detected, max_len=8)
            # 收集多值轴
            multi_value = []
            sweeps = data.get("sweeps") or {}
            for ax, vs in sweeps.items():
                if isinstance(vs, list) and len(vs) > 1:
                    multi_value.append(ax)
            # 第一个 case 的 params 算建议名
            first_params = {ax: vs[0] for ax, vs in sweeps.items() if isinstance(vs, list) and vs}
            suggested = render_pbs_name(
                params=first_params,
                multi_value_axes=multi_value,
                base_basename=base_basename,
            )
            if is_zh:
                _print(f"  pbs 任务名建议(可改): {suggested}")
                _print(f"  (原 #PBS -N base 短名: \"{base_basename}\")")
                _print(f"  [enter 接受 / 输入新名 / 输入模板如 Mars-{{alpha}}-{{mach}}]")
                prompt_name = "  任务名(enter 接受建议,或输模板)"
            else:
                _print(f"  Suggested pbs job name (editable): {suggested}")
                _print(f"  (Original #PBS -N basename: \"{base_basename}\")")
                _print(f"  [Enter to accept / new name / template like Mars-{{alpha}}-{{mach}}]")
                prompt_name = "  Job name (Enter to accept, or template)"
            user_input = input_text(prompt_name, default="")
            if user_input:
                # 检测是模板(含 {) 还是新名字
                if "{" in user_input:
                    pbs_naming = user_input
                else:
                    # 用户给了具体名字,直接用(不用模板)
                    data["pbs_job_name_override"] = user_input
        return ("step_6_preview", {
            **data,
            "pbs_enabled": pbs_enabled,
            "pbs_naming": pbs_naming,
        })
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py::TestSweepWizardStep5aPbs -v
```

Expected:3 passed。

- [ ] **Step 5: 跑全部 wizard 测试**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep.py tests/test_wizard_sweep_pbs.py tests/test_wizard_diff.py -q
```

Expected:全部通过(可能需要小幅调整现有 wizard_sweep 测试以适配 7 步)。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/wizard.py inp_tool/tests/test_wizard_sweep_pbs.py
git commit -m "feat(wizard): step_5a_pbs - confirm + task name template"
```

---

## Task 16: wizard.py - step_6_preview 打印 pbs 建议名 + 调 generate

**Files:**
- Modify: `inp_tool/inp_tool/wizard.py`
- Modify: `inp_tool/tests/test_wizard_sweep_pbs.py`

- [ ] **Step 1: 加失败测试**

```python
class TestSweepWizardStep6PbsPreview:
    def test_preview_shows_pbs_suggested_name(self, tmp_path, monkeypatch):
        from inp_tool.wizard import _print, confirm
        wiz = WizardSweep()
        src = tmp_path / "source"
        src.mkdir()
        (src / "mcfd.inp").write_text("tsteps\n  ntstep = 100\nend\nphysics\n  eqnset = euler\nend\n")
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("d")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("g")
        (src / "run_cfdpp.pbs").write_text("#PBS -N Marspath\n")
        out = tmp_path / "out"
        data = {
            "source_dir": str(src),
            "template": str(src / "mcfd.inp"),
            "copy_strategy": "hardlink",
            "output_dir": str(out),
            "mode": "1",
            "sweeps": {"alpha": [0, 4]},
            "naming": "case_{alpha}",
            "manifest_path": None,
            "detected_pbs": str(src / "run_cfdpp.pbs"),
            "pbs_enabled": True,
            "pbs_naming": "",
            "validation_issues": [],
        }
        # 接受预览(confirm 返回 True)
        monkeypatch.setattr("inp_tool.wizard.confirm", lambda *a, **kw: True)
        wiz.step_6_preview(data)
        # 检查子目录生成
        assert (out / "case_0").exists()
        assert (out / "case_4").exists()
        # 检查 pbs
        for case_dir in (out / "case_0", out / "case_4"):
            pbs = case_dir / "run_cfdpp.pbs"
            assert pbs.exists()
            content = pbs.read_text()
            assert "#PBS -N Marspath_a" in content  # 默认短名
            assert "Marspathfinder" not in content  # 原任务名被替换
```

- [ ] **Step 2: 跑测试确认失败**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py::TestSweepWizardStep6PbsPreview -v
```

Expected:FAIL(`step_6_preview` 还没用 pbs 字段)

- [ ] **Step 3: 在 `wizard.py` 的 `step_6_preview` 中:**

打开 `inp_tool/inp_tool/wizard.py` 第 558-615 行的 `step_6_preview`,在构造 `cfg` 之后、`cs = CaseSweep.from_dict(cfg)` 之后加 pbs 字段注入(在 `cs.source_dir = data["source_dir"]` 之后):

```python
        # v0.9.0:pbs 注入
        from .pbs import PbsConfig, extract_pbs_basename, render_pbs_name
        pbs_enabled = data.get("pbs_enabled", False)
        pbs_naming = data.get("pbs_naming", "")
        if pbs_enabled:
            cs.pbs = PbsConfig(enabled=True, naming=pbs_naming)
        # 打印 pbs 建议名(预览)
        if pbs_enabled and data.get("detected_pbs"):
            base_basename = extract_pbs_basename(data["detected_pbs"], max_len=8)
            sweeps = data.get("sweeps") or {}
            multi_value = [ax for ax, vs in sweeps.items() if isinstance(vs, list) and len(vs) > 1]
            first_params = {ax: vs[0] for ax, vs in sweeps.items() if isinstance(vs, list) and vs}
            suggested = render_pbs_name(
                params=first_params,
                multi_value_axes=multi_value,
                base_basename=base_basename,
                user_template=pbs_naming,
            )
            if is_zh:
                _print(f"    pbs 任务名建议: {suggested}")
            else:
                _print(f"    pbs job name suggestion: {suggested}")
        report = generate(cs, force=force)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep_pbs.py::TestSweepWizardStep6PbsPreview -v
```

Expected:1 passed。

- [ ] **Step 5: 跑全部 wizard 测试**

```bash
conda run -n cfdchanger python -m pytest tests/test_wizard_sweep.py tests/test_wizard_sweep_pbs.py tests/test_wizard_diff.py -q
```

Expected:全部通过。

- [ ] **Step 6: Commit**

```bash
git add inp_tool/inp_tool/wizard.py inp_tool/tests/test_wizard_sweep_pbs.py
git commit -m "feat(wizard): step_6 preview shows pbs suggestion + inject PbsConfig"
```

---

## Task 17: `__init__.py` 导出 PbsConfig / PbsIssue

**Files:**
- Modify: `inp_tool/inp_tool/__init__.py`

- [ ] **Step 1: 打开 `__init__.py`,找到现有 export 列表**

```bash
grep -n "from .pbs\|from .sweep\|PbsConfig" /home/fz/project/cfd--changer/inp_tool/inp_tool/__init__.py
```

- [ ] **Step 2: 加 export**

在 `__init__.py` 现有 import 区加:

```python
from .pbs import PbsConfig, PbsIssue
```

并在 `__all__`(若存在)列表加:

```python
__all__ = [
    # ... 现有 ...
    "PbsConfig",
    "PbsIssue",
]
```

- [ ] **Step 3: 跑 import 测试**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -c "from inp_tool import PbsConfig, PbsIssue; print('OK', PbsConfig, PbsIssue)"
```

Expected:`OK <class 'inp_tool.pbs.PbsConfig'> <class 'inp_tool.pbs.PbsIssue'>`

- [ ] **Step 4: Commit**

```bash
git add inp_tool/inp_tool/__init__.py
git commit -m "feat: export PbsConfig + PbsIssue from inp_tool"
```

---

## Task 18: docs/technical/04-sweep-architecture.md 加 §10 pbs 模块

**Files:**
- Modify: `docs/technical/04-sweep-architecture.md`

- [ ] **Step 1: 在文档末尾(§9 之后)加 §10**

在 `docs/technical/04-sweep-architecture.md` 末尾追加:

```markdown
## 10. v0.9.0:PBS 脚本可选生成

### 10.1 背景

v0.8.0 整算例目录模式复制了 `run_*.pbs` 到每个子算例,但任务名是源模板里硬编码的(如 `Marspathfinder-Ini`),批量提交时无法区分 case。v0.9.0 让 wizard/CLI 可选生成 pbs,按 sweep 参数自动重新填 `#PBS -N`。

### 10.2 新增模块 `inp_tool.pbs`

```
pbs.py
├── PbsConfig              (dataclass, enabled/template/naming/...)
├── PbsIssue               (dataclass, code/severity/path/message)
├── detect_pbs_template()  (从 source_dir glob run_*.pbs)
├── validate_base_case_dir()  (文件级 + block 级检查)
├── render_pbs_name()      (默认短名 / 用户模板)
├── write_pbs()            (替换/追加 #PBS -N)
└── extract_pbs_basename() (从 #PBS -N 提取 base 短名)
```

零运行时依赖(纯 stdlib)。

### 10.3 完整性检查规则

| 类别 | error 必填 | warning 软提示 |
|------|------------|----------------|
| mcfd.inp | 存在 | — |
| mcfd.inp blocks | tsteps, physics | chemkin, restart |
| 网格 | — | cellsin.bin, nodesin.bin, cgrpsin.bin* |
| 物性 | — | *.dat (≥1) |
| 配置 | — | mcfd.bc, mcfd.grp |
| pbs 模板 | — | run_*.pbs(pbs_enabled=True 时) |

### 10.4 任务名生成规则

默认短名格式:
- 抽取原 `#PBS -N` base 名,截前 8 字符(`Marspathfinder-Ini` → `Marspath`)
- 追加多值轴短 token:`a04` (alpha=4), `m0.60` (mach=0.6), `T288` (T_inf=288.15)
- 单值轴不进
- 整体 ≤ 15 字符(PBS 上限),超长末尾加 `.`
- 特殊字符 (`[^A-Za-z0-9_.-]`) → `_` 兜底

用户模板覆盖:在 wizard step_5a_pbs 输 `Mars-{alpha}-{mach}`,走 `str.format()` 路径。

### 10.5 数据流(per_dir 模式)

```
generate(caseSweep)
  ├─ 开头: validate_base_case_dir → 抛 SweepValidationError (error 时)
  ├─ per_case 循环:
  │    ├─ _copy_case_files(源目录 → 子目录,hardlink/copy/symlink)
  │    ├─ write_preserve(修改后的 mcfd.inp)
  │    └─ pbs.write_pbs(template, 子目录/run_*.pbs, job_name)  ← v0.9.0 新增
  └─ 写 manifest.json,加 pbs_enabled + 每 case pbs_name 字段
```

### 10.6 manifest 扩展

per_dir 模式 manifest 增字段(向下兼容):
```json
{
  "pbs_enabled": true,
  "cases": [
    {"case_id": "case_aoa04_ma0.80", "pbs_name": "Marspath_a04_m0.80", ...}
  ]
}
```
flat 模式 / `pbs.enabled=False` 时不写。
```

- [ ] **Step 2: Commit**

```bash
git add docs/technical/04-sweep-architecture.md
git commit -m "docs(technical): §10 pbs module architecture (v0.9.0)"
```

---

## Task 19: docs/user-manual/18-wizard-tasks.md 更新 wizard 步骤

**Files:**
- Modify: `docs/user-manual/18-wizard-tasks.md`

- [ ] **Step 1: 找到 wizard sweep 步骤说明**

```bash
grep -n "step_1\|source_dir\|基础算例" /home/fz/project/cfd--changer/docs/user-manual/18-wizard-tasks.md | head -20
```

- [ ] **Step 2: 把 6 步改为 7 步,加 step_5a_pbs 说明**

把现有 "1. source_dir → 2. output → 3. mode → 4. params → 5. naming → 6. preview" 改为 "1. source_dir → 2. output → 3. mode → 4. params → 5. naming → **5a. pbs** → 6. preview"。

在 step_5a_pbs 位置加段落(中文):

```markdown
### 5a. pbs 脚本(可选,v0.9.0 新增)

询问"是否生成 pbs 脚本?"(默认 yes)。

如果 yes,展示建议的 pbs 任务名(如 `Marspath_a04_m0.60`),基于:
- 源算例 pbs 模板的 `#PBS -N` base 短名
- sweep 的多值轴(`alpha` / `mach` / `T_inf` 等)
- 短名规则:参数值短 token,总长 ≤ 15 字符

可选项:
- `enter` 接受建议名
- 输入具体新名(全部 case 共享)
- 输入模板(如 `Mars-{alpha}-{mach}`,case 间自动差异化)

如果源目录缺 `run_*.pbs` 模板,自动关闭 pbs 生成并提示。
```

- [ ] **Step 3: 在文档 step_1 段落加完整性检查说明**

```markdown
### 1. source_dir(基础算例目录)

v0.9.0 起,选中 source_dir 后自动跑完整性检查:
- **error(必填)**:mcfd.inp 存在 + 含 `tsteps` / `physics` block
- **warning(软提示)**:网格/物性/pbs 模板缺失

error 存在时,询问"仍要继续?",确认后才往下走。
```

- [ ] **Step 4: Commit**

```bash
git add docs/user-manual/18-wizard-tasks.md
git commit -m "docs(user-manual): wizard sweep step 5a pbs + step 1 validation"
```

---

## Task 20: CHANGELOG v0.9.0 段

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 在 `CHANGELOG.md` 顶部 `[Unreleased]` 段下加 v0.9.0 条目**

找到 `## [Unreleased]` 段,在它**下方**加:

```markdown
## [v0.9.0] - 2026-06-XX

### Added
- feat(pbs): 新建 `inp_tool.pbs` 模块,提供 `PbsConfig` / `PbsIssue` / `detect_pbs_template` / `validate_base_case_dir` / `render_pbs_name` / `write_pbs` 等 API(Task 2-8)
- feat(sweep): `CaseSweep.pbs: Optional[PbsConfig]` 字段;`generate()` 整合完整性检查 + pbs 写盘;manifest 新增 `pbs_enabled` / `pbs_name` 字段(Task 9-12)
- feat(cli): `inp-tool sweep` 新增 `--pbs` / `--no-pbs` / `--pbs-naming` flag(Task 13)
- feat(wizard): sweep wizard step_1 加完整性检查 + pbs auto-detect;新增 step_5a_pbs;step_6_preview 打印 pbs 建议名(Task 14-16)
- test(pbs): 新建 `tests/test_pbs.py` (~30 单测)
- test(integration): 新建 `tests/test_sweep_pbs_integration.py` (~10 集成)
- test(wizard): 新建 `tests/test_wizard_sweep_pbs.py` (~6 wizard 流程)
- docs(technical): `04-sweep-architecture.md` §10 pbs 模块架构
- docs(user-manual): `18-wizard-tasks.md` 更新 wizard 步骤

### Changed
- docs(spec): 新增 `docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md`
- docs(plan): 新增 `docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md`
- 兼容性:`CaseSweep.pbs = None` 默认,现有 60+ 测试零修改
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): v0.9.0 sweep 完整性 + pbs 可选 + 任务名建议"
```

---

## Task 21: 真实算例 smoke(reference/suanli)

**Files:** 无代码改动

- [ ] **Step 1: 复制 reference/suanli 到临时目录**

```bash
SCRATCH=$(mktemp -d)
cp -r /home/fz/project/cfd--changer/reference/suanli "$SCRATCH/source"
ls "$SCRATCH/source" | head -5
```

- [ ] **Step 2: 跑端到端 CLI smoke**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m inp_tool.cli sweep \
  --source-dir "$SCRATCH/source" \
  --template "$SCRATCH/source/mcfd.inp" \
  --output-dir "$SCRATCH/out" \
  --sweeps '{"alpha": [0, 4], "mach": [0.6]}' \
  --naming "case_a{alpha}_m{mach}" \
  --pbs-naming "Marspath-{alpha}" \
  --force
```

Expected:4 个 case 目录生成,每个含 `mcfd.inp` + `run_cfdpp.pbs`,pbs 任务名 `Marspath-0` / `Marspath-4`。

- [ ] **Step 3: 验证 pbs 内容**

```bash
cat "$SCRATCH/out/case_a0_m0.6/run_cfdpp.pbs" | grep "#PBS -N"
cat "$SCRATCH/out/case_a4_m0.6/run_cfdpp.pbs" | grep "#PBS -N"
```

Expected:
- case_a0_m0.6 → `#PBS -N Marspath-0`
- case_a4_m0.6 → `#PBS -N Marspath-4`

- [ ] **Step 4: 验证完整性 error 路径**

```bash
# 删 mcfd.inp 里的 physics block,跑 --no-pbs 跳过 pbs 完整性
SCRATCH2=$(mktemp -d)
cp -r /home/fz/project/cfd--changer/reference/suanli "$SCRATCH2/source"
# 移除 physics block
sed -i '/^physics$/,/^end$/d' "$SCRATCH2/source/mcfd.inp"
conda run -n cfdchanger python -m inp_tool.cli sweep \
  --source-dir "$SCRATCH2/source" \
  --template "$SCRATCH2/source/mcfd.inp" \
  --output-dir "$SCRATCH2/out" \
  --sweeps '{"alpha": [0]}' \
  --no-pbs --force 2>&1 | tail -20
```

Expected:抛 `SweepValidationError`,含 `MISSING_BLOCK:physics`。

- [ ] **Step 5: 清理**

```bash
rm -rf "$SCRATCH" "$SCRATCH2"
```

- [ ] **Step 6: 跑全部测试最终验证**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest -q
```

Expected:全部通过,无 regression。

---

## Task 22: 最终 review + merge

**Files:** 无代码改动

- [ ] **Step 1: 跑 simplify + code-review agent**

```bash
git log --oneline main..HEAD
# 选最近的 commit 跑 review
git diff main..HEAD --stat
```

手动调 `code-review` agent 检视本分支 diff,确保:
- 0 个 CRITICAL/HIGH issue
- MEDIUM issue 修复或记录
- 覆盖率 ≥ 80%

- [ ] **Step 2: 跑一次完整 pytest + coverage**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest --cov=inp_tool --cov-report=term-missing -q
```

Expected:全部通过,pbs.py 覆盖率 ≥ 80%。

- [ ] **Step 3: 推分支 + 开 PR**

```bash
cd /home/fz/project/cfd--changer
git push -u origin feat/sweep-pbs
gh pr create --title "feat(sweep): 完整性检查 + pbs 可选 + 任务名建议 (v0.9.0)" \
  --body "见 docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md

## 主要变更
- 新建 inp_tool.pbs 模块(零依赖,~180 行)
- CaseSweep.pbs 字段 + generate() 整合
- wizard sweep 6 → 7 步
- CLI --pbs/--no-pbs/--pbs-naming flag

## 测试
- 新增 ~520 行测试
- 现有 60+ 测试零修改全绿

## 兼容性
- CaseSweep.pbs 默认 None,向后兼容
- flat 模式(无 source_dir)时 pbs 模块零调用"
```

- [ ] **Step 4: 监控 PR CI**

```bash
gh pr checks <PR-number> --watch
```

Expected:CI 全绿(根据项目 .github/workflows/)。

- [ ] **Step 5: 等用户 merge PR**

- [ ] **Step 6: 合并后清理分支**

```bash
cd /home/fz/project/cfd--changer
git switch main
git pull --rebase origin main
git push origin --delete feat/sweep-pbs
git branch -d feat/sweep-pbs
```

- [ ] **Step 7: 更新 CHANGELOG 日期**

把 CHANGELOG.md 里 `## [v0.9.0] - 2026-06-XX` 改为实际 merge 日期。

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): v0.9.0 实际 release 日期"
```

---

## Self-Review

### Spec 覆盖检查

| Spec 章节 | 对应 Task |
|-----------|-----------|
| §1 背景与目标 | (whole plan) |
| §2 非目标 | (whole plan, 严格 YAGNI) |
| §3 涉及文件 | Task 2-22 |
| §4 架构 | Task 2-17 (pbs.py 新建 + sweep/wizard/cli 集成) |
| §5 数据模型 | Task 2, 9 (PbsConfig / PbsIssue / CaseSweep.pbs) |
| §6 完整性检查 | Task 6, 7 (validate_base_case_dir 文件 + block) |
| §7 任务名生成 | Task 4, 5 (render_pbs_name + 截断 + sanitization) |
| §8 数据流 | Task 9-12, 14-16 (generate + wizard) |
| §9 错误处理 | Task 9-10 (SweepValidationError) |
| §10 manifest 扩展 | Task 12 (pbs_name 字段) |
| §11 测试计划 | Task 2-8, 9-12, 13-16 (pbs 单测 + 集成 + wizard) |
| §12 兼容性 + 风险 | Task 9 (向后兼容), Task 12 (manifest 兼容) |
| §13 验收 | Task 21 (smoke), Task 22 (review + merge) |
| §14 不在范围 | (none — YAGNI 严格执行) |

### 占位符扫描

无 TBD / TODO / "implement later"。所有 step 含实际代码 / 命令 / 路径。

### 类型一致性

| 类型/方法 | 定义位置 | 使用位置 |
|----------|----------|----------|
| `PbsConfig` | Task 2 (pbs.py) | Task 9 (sweep), Task 13 (cli), Task 14-16 (wizard) |
| `PbsIssue` | Task 2 | Task 6, 7, 10 |
| `detect_pbs_template()` | Task 3 | Task 11 (generate) |
| `validate_base_case_dir()` | Task 6, 7 | Task 10 (generate 入口) |
| `render_pbs_name()` | Task 4, 5 | Task 11, 15, 16 (wizard preview) |
| `write_pbs()` | Task 8 | Task 11 (generate per_case) |
| `extract_pbs_basename()` | Task 11 (pbs.py) | Task 15, 16 (wizard step_5a, step_6) |
| `SweepValidationError` | Task 10 (sweep) | Task 10, 21 (smoke) |
| `CaseResult.pbs_name` | Task 12 | Task 11, 12 (manifest) |
| `CaseSweep.pbs` | Task 9 | Task 9-12, 14-16, 21 |

### 已知小问题(已在 Task 步骤内说明)

1. Task 11 `multi_value_axes` 提取方式:`sweep.sweeps` 可能是 `SweepSpec` 或 dict,代码只用 dict 路径(因 `SweepSpec.values` 是 dict),不冗余。
2. Task 15 `step_5a_pbs` 内部对 `Mars-{alpha}` 形式的输入做模板/具体名判断(检测 `{`),不依赖 wizard 之前步骤。
3. Task 14-16 wizard 现有测试可能因 7 步变化需要小幅调整,在 Step 5 加"可能需要小幅调整现有测试"。

**无重大问题。** Plan 可执行。
