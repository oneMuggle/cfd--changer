# Wizard 方程感知步骤（v0.10.0 后续 PR）— 设计文档

**日期**: 2026-06-11
**作者**: brainstorming with user
**Status:** ✅ 已批准,待写 plan
**目标版本**: inp-tool v0.10.0 后续 PR(或 v0.10.1 视情况)
**前置**:
- v0.10.0 方程感知扩展(PR #17,merge 后)— 提供 `set_*_model` 写函数、SweepSpec 枚举轴、`TurbulenceInit` overrides
- v0.9.1 WizardSweep 7 步 + `step_4a_detect`

---

## 1. 背景与目标

v0.10.0 让 sweep 能按 case 切方程/湍流/气体。但 **wizard 仍是 YAML 文本黑盒** — 用户必须手写 `sweeps: {turbulence: [sst, sa]}` 才能用 v0.10.0 能力,wizard 内部不引导。

**本 spec 目标**:在 `WizardSweep` 加 2 个新步骤,让用户**向导式**地选湍流/能量/气体维度构造 `sweeps:` 块,可选 per-case 覆盖 I/L/U 或温度。

| 现状痛点 | 影响 |
|---|---|
| 想做 SST vs SA 对比 sweep,wizard 只让用户手写 YAML | 易拼错 `ssttt` 触发 `ValueError`,无友好提示 |
| 不熟悉 `_ENUM_ALIASES`(`sst` 短名)的用户写规范名 `k-omega-sst` | 长难记,易错 |
| 想给某个 case 设不同 I/L/U | 必须手写 `turbulence.overrides` 嵌套结构 |
| LAMINAR template 想对比 SA | wizard 不告诉用户"sst 会被自动跳过",默默生成不写 turbi_ 的 case |

**目标**:wizard 加 `step_4b` 选 axis + `step_4c` per-case override,体验对齐"菜单下拉 + 友好提示"。

---

## 2. 非目标(YAGNI)

- ❌ CSV / groups / explicit 模式的 equation axes 交互(只 Cartesian 走)
- ❌ 多组分 / SpeciesPreset 编辑(wizard 不动)
- ❌ step_4a_detect 改造(已 v0.9.1 完整,仅追加 warning 显示)
- ❌ wizard 默认 commit / 快速路径(用户要显式走 wizard)
- ❌ 3-温度 / 3-方程湍流家族(v0.10+ scope)
- ❌ equation_switches 在 wizard 内暴露(默认全 True,CLI flag 走 `--no-switch-*`)
- ❌ 完整 i18n 改造(只中英双语言,沿用 wizard 既有风格)

---

## 3. 涉及文件

| 文件 | 动作 | 估行数 |
|---|---|---|
| `inp_tool/inp_tool/wizard.py` | 加 `multi_menu` / `_read_template_value` helper + 2 个新 step 方法 + steps 列表插入 | +200 / -10 |
| `inp_tool/inp_tool/equations.py` | `EquationSystemReport` 加 `sweeps_equation_warnings: List[str]` 字段 + `detect_equations` 接受可选 `intended_axes` 参数 | +20 / -2 |
| `inp_tool/tests/test_wizard_equation_axes.py` | 新建 5 组测试 | +200 |
| `docs/technical/19-equation-sweep-extend.md` | 末尾加一节"v0.10.0+ Wizard 集成" | +30 / -0 |
| `CHANGELOG.md` | 追加 [Unreleased] 子节 | +5 / -0 |

**总估**:+455 / -12。

---

## 4. 设计

### 4.1 步骤位置

`WizardSweep.steps` 改为:

```python
steps = [
    "step_1_source_dir",
    "step_2_output",
    "step_3_mode",              # 用户选 "1" (Cartesian) 才进 4b
    "step_4_params",           # 现有 — 用户填 alpha/mach 等 sweeps
    "step_4b_equation_axes",    # 新(Cartesian only)— 选 turbulence/energy/gas 轴
    "step_4a_detect",           # 现有 — 展示 template + 消费 warnings
    "step_4c_equation_overrides",  # 新(4b 选了 axis 才出现)— per-case I/L/U 或温度
    "step_5_naming",
    "step_5a_pbs",
    "step_6_preview",
]
```

> 顺序说明:`step_4b` 在 `step_4a_detect` **之前** — 用户先选 axes,再看到 detect 报告里 template 是 laminar / 2T / perfect-gas,可即时知道"我选的 sst + template 是 laminar 会被 warn"。

### 4.2 step_4b 子流程

3 个连续子问题,每个"Y/n + 多选菜单"模式。

```
Q1:要不要按湍流扫? [Y/n]
  Y → 多选菜单:
    1. sst (k-omega-sst)
    2. sa  (spalart-allmaras)
    3. k-eps (realizable-k-eps)
    4. goldberg (goldberg_rt)
    5. laminar
  选 1 3 → sst + k-eps
  n → 跳过 turbulence 轴

Q2:要不要按能量扫? [Y/n]
  Y → 多选菜单:
    1. none (完美气体)
    2. 2t (双温)
  n → 跳过

Q3:要不要按气体扫? [Y/n]
  Y → 多选菜单:
    1. perfect-gas
    2. real-gas
    3. multi-temp (双温)
  n → 跳过
```

**选完后,合并到 `data["sweeps"]`**:

```python
# 例:Q1 选 sst, Q2 选 none, Q3 跳过
data["sweeps"] = {
    **data.get("sweeps", {}),  # step_4_params 已填的 alpha/mach 等
    "turbulence": ["sst"],
    "energy": ["none"],
    # gas 未选 → 不注入
}
```

### 4.3 step_4c 子流程(可选)

**触发条件**(全部满足才出现):
- `step_3_mode == "1"`(Cartesian)
- `step_4b` 至少选了 1 个 axis

否则跳过,直接进 `step_5_naming`。

```
Q0:要不要给某些 case 设单独的 I/L/U 或温度? [Y/n]
  n → 跳过
  Y → 进入 Q1

Q1:覆盖哪个湍流模型? (仅当 step_4b 选了 turbulence 轴)
  菜单(单选):
    1. sst
    2. sa
    3. k-eps
    4. (跳过湍流覆盖)
  选 1 → I/L/U prompt(默认值从 template 读)
  选 4 → 跳到 Q2

Q2:覆盖能量模型? (仅当 step_4b 选了 energy 轴)
  菜单:1. 2t  2. none  3. (跳过能量覆盖)
  选 1 → T_trans, T_vib prompt
  选 2 → reftem prompt
  选 3 → 不覆盖能量

Q3:是否再选一个湍流覆盖? [Y/n]
  Y → 回到 Q1(循环)
  n → 结束 step_4c
```

**字段 prompt 细节**:

```python
# Q1 选了 sst 后:
default_I = _read_template_value(template, "guiopts", "turbi_tlev", 0.01)
default_L = _read_template_value(template, "guiopts", "turbi_len", 0.01)
default_U_ref = _read_template_value(template, "physics", "refvel", 204.0)

I = float(input(f"  sst 湍流强度 I (默认 {default_I}): ") or default_I)
L = float(input("  sst 特征长度 L: ") or default_L)
U_ref = float(input("  sst 参考速度 U_ref: ") or default_U_ref)
```

**选完后,合并到 `data["turbulence"]`**:

```python
data["turbulence"] = {
    "I": 0.01, "L": 0.01, "U_ref": 204.0,   # 顶层默认(从模板读)
    "overrides": {
        "sst": {"I": 0.005, "L": 0.02, "U_ref": 250.0}
    }
}
```

### 4.4 多选菜单 helper

新增 `multi_menu(prompt, choices) -> List[str]`:

```python
def multi_menu(prompt: str, choices: List[Tuple[str, str, str]]) -> List[str]:
    """多选菜单。choices: [(key, "label", "value"), ...]
    
    交互:输入"1 3"或"1,3"或"sst sa" → 返回对应 value 列表
    输入空 → 空列表(等于跳过)
    """
    # 实际:沿用 wizard 既有 menu 单选 + 循环,允许重选直到 done
    # 或:单行多 token 输入(更紧凑)
```

**实现选择**:单行 token 输入(例:`1 3 5`)而非 click-style 上下导航(避免新依赖)。

### 4.5 `_read_template_value` helper

```python
def _read_template_value(template_path: str, block_name: str, key: str, default: float) -> float:
    """从 template .inp 读 guiopts.x 或 physics.x,转 float,失败用 default。"""
    try:
        inp = parse_file(template_path)
        b = inp.get_block(block_name)
        if b is None:
            return default
        v = b.get(key)
        if v is None:
            return default
        return float(v)
    except Exception:
        return default
```

### 4.6 EquationSystemReport.sweeps_equation_warnings

`equations.py` 新增字段:

```python
@dataclass
class EquationSystemReport:
    # ... 现有字段
    sweeps_equation_warnings: List[str] = field(default_factory=list)
    # 用法:detect_equations 接受可选 intended_axes 参数
    # 当 intended_axes 含与 template 不兼容的 enum 时,append warning
```

`detect_equations(inp, intended_axes: Optional[Dict[str, str]] = None)`:
- 若 `intended_axes` 给出用户选的 axis 值(如 `{"turbulence": "sst", "energy": "2t"}`)
- 对每个 axis 检查与 template 检测结果是否冲突:
  - 用户选 SST,但 template 是 laminar → `sweeps_equation_warnings.append("SST 选但 template 是 laminar — preset 会跳过")`
  - 用户选 2T,但 template tnoneq=0 → `sweeps_equation_warnings.append("2T 选但 template tnoneq_numeqns=0 — set_energy_model 会强制设 1")`
  - 用户选 MULTI_TEMP,但 template v6=0 → `sweeps_equation_warnings.append("MULTI_TEMP 选但 template v6=0 — set_gas_type 会写 v6=11 联动 tnoneq=1")`

`step_4a_detect` 末尾消费 `sweeps_equation_warnings` 列表显示给用户:

```python
if rep.sweeps_equation_warnings:
    _print("  ⚠ 你选的 axis 与 template 不兼容:")
    for w in rep.sweeps_equation_warnings:
        _print(f"    - {w}")
```

### 4.7 错误处理

| 触发 | 严重度 | 行为 |
|---|---|---|
| 选了 `sst` 但 template 是 laminar | warning | `sweeps_equation_warnings` 追加 |
| 选了 `2t` 但 `physics` 块没 vibtem | auto-fix | v0.10.0 `set_energy_model` 自动 `pb.append("vibtem", T_vib)` |
| 选了 `real-gas` 但 template 是 perfect-gas | warning | `sweeps_equation_warnings` 追加(`set_gas_type` 会写 v6=1) |
| 选了 0 个 axis(全 n) | 静默 | `data["sweeps"]` 不变(等价 v0.10.0 老路径) |
| 覆盖字段值解析失败 | error | 重新 prompt 该字段,Y/n 兜底 |
| 同一 model 重复覆盖 | overwrite | 后一次覆盖前一次 |
| `multi_menu` 输入空 | 静默 | 等于跳过该 axis |
| step_4c 触发条件不满足 | 跳过 | 静默进 step_5_naming |

### 4.8 与 v0.10.0 YAML 格式的对应

wizard 产出的 `data["sweeps"]` + `data["turbulence"]` / `data["energy_overrides"]` 直接喂给 `CaseSweep.from_dict()` — **零转换**。所有 spec §4.5-4.7 校验仍在 `from_dict` + `generate()` 路径生效。

### 4.9 兼容性

- v0.10.0 PR #17 已合 main;本 spec 是后续 PR
- 既有 step 顺序不变,只在 `step_4` 与 `step_4a` 之间插
- 老 wizard 用户(走 CSV/groups/explicit)路径完全不变(`step_4b/4c` 不出现)
- 不动 `equation_switches` 默认值(全 True,沿用 v0.10.0)

---

## 5. 验证矩阵

| 触发 | 严重度 | 行为 |
|---|---|---|
| step_4b 选 sst + template 是 laminar | warning | detect 报告加 1 条 |
| step_4b 选 2t + template tnoneq=0 | warning | detect 报告加 1 条 |
| step_4b 选 0 个 axis | 静默 | step_4c 不出现,等价 v0.10.0 老路径 |
| step_4c 触发条件不满足 | 静默 | 跳过 |
| step_4c 同 model 二次覆盖 | overwrite | 后一次的覆盖覆盖前一次 |
| 字段 prompt 输入非数字 | error | 重新 prompt |
| 多选菜单输入空 | 静默 | 等于跳过该 axis |
| CSV/groups/explicit mode | N/A | step_4b/4c 不出现 |

---

## 6. 测试

### 6.1 覆盖率目标:≥ 80%

### 6.2 单元测试(`tests/test_wizard_equation_axes.py`,新建)

| 类 | 用例 | 关键场景 |
|---|---|---|
| `TestStep4bEquationAxes` | 4 | 跳过全 3 axis;选 sst+sa;选 2t;选了 laminar 时 warning |
| `TestStep4cOverrides` | 3 | 跳过 step_4c;给 sst 设 override;给 2t 设 T_vib |
| `TestIncompatibleWarning` | 2 | laminar + sst → note 出现;sst + 2t 同时 → 2 个 note |
| `TestStep4bDefaults` | 2 | 全部 Q1/Q2/Q3 选 n → sweeps 不变;选 1 axis → sweeps 含该 axis |
| `TestBackwardCompat` | 2 | v0.10.0 老 wizard 流程不动;非 Cartesian mode 不进 4b/4c |

### 6.3 手工 e2e(developer)

```bash
conda run -n cfdchanger pytest inp_tool/tests/ -v
# 进 REPL 走 wizard
echo "load reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp
modify
4
1
cases
1
{\"alpha\":[0,5]}
sweeps case1
1 2
n
2
n
n
case1
预览
run
q" | conda run -n cfdchanger python -m inp_tool.cli shell
```

---

## 7. 文档更新

| 文件 | 改动 |
|---|---|
| `docs/technical/19-equation-sweep-extend.md` | 末尾加"v0.10.0+ Wizard 集成"节,链向本 spec |
| `CHANGELOG.md` | [Unreleased] 追加 5 行 |

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 现有 `input_text` / `menu` 不支持多选 | 写新 `multi_menu` helper(单行 token,无新依赖) |
| `_read_template_value` 工具不存在 | 写简单 helper:`inp.get_block(name).get(key)` + 类型 cast + 默认 |
| `data["sweeps"]` 已含 `alpha` / `mach`,4b 注入新 key 不能覆盖 | 用 `**data.get("sweeps", {})` + 新 keys 覆盖 |
| `equation_switches` 全 True 默认时,用户没选 axis 仍切 | step_4b 不选 → 不注入 sweeps key → `params` 不含 → `isinstance(..., TurbulenceModel)` 守卫 |
| step_4a_detect 的 `rep.notes` 没"用户选不兼容"的钩子 | 加 `sweeps_equation_warnings` 字段到 `EquationSystemReport`,detect 末尾追加 |
| LAMINAR template + 选 SST 时 wizard 默默不写 turbi_ | 已在 §4.6 warning 路径覆盖 |
| step_4b 默认值读 template 时报错 | 静默用 default,不影响 wizard 流程 |

---

## 9. 实施步骤(草案,供 writing-plans 拆任务)

1. `wizard.py` 加 `multi_menu` helper
2. `wizard.py` 加 `_read_template_value(path, block, key, default)` helper
3. `equations.py` `EquationSystemReport` 加 `sweeps_equation_warnings` 字段
4. `equations.py` `detect_equations` 接受可选 `intended_axes` 参数
5. `WizardSweep.steps` 插入 `step_4b` + `step_4c`
6. 实现 `step_4b_equation_axes`(3 子问题)
7. 实现 `step_4c_equation_overrides`(可选触发 + 字段 prompt)
8. `step_4a_detect` 末尾消费 warnings
9. 写 5 组测试(`test_wizard_equation_axes.py`)
10. 跑全量 + e2e
11. 提 PR(基于 v0.10.0 main)

---

## 10. 决策追溯(本 spec 关键设计取舍)

| 决策 | 选 | 不选 | 理由 |
|---|---|---|---|
| step_4b 交互模型 | **3 个独立问题** | 1 个合并 / 菜单+跳选 | 发现性高,每轴独立 |
| step_4c 触发 | **仅 step_4b 选了 axis 才出现** | 总出现 / 合入 4b | 不快跳简单用户 |
| 不兼容 axis | **允许 + warn + 跳过** | 警告后问 Y/n / 静默错败 | 与 v0.10.0 generate 行为对齐 |
| step_4c 默认值 | **读 template 现存值,缺则默认** | 全默认 0.01 | 让用户有"起点"可微调 |
| step_4b 位置 | **step_4a 之前** | step_4a 之后 | 用户先选再看到 detect 报告 |
| 多选菜单实现 | **单行 token 输入** | click-style 上下导航 | 无新依赖,简单 |
| LAMINAR + SST 行为 | **自动跳过 preset(同 v0.10.0)** | 报错 | 与 _resolve_turb_init=None 一致 |
| 覆盖 key 用 enum.value | **sst → k-omega-sst** | 短名 | wizard 内部转换,user 友好 |
