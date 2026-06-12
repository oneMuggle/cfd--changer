# 19. 方程感知扩展（v0.10.0）

> **前置章节:** [18-equation-aware-config.md](18-equation-aware-config.md) — v0.9.1 方程感知(检测 + 初始化)
> **本章目标:** 让 sweep 能 **按 case 切换** 能量/湍流/气体模型,并支持 per-case 初始化参数覆盖。

---

## 19.1 三大新写函数

`inp_tool/equations.py` 新增:

| 函数 | 改写内容 | 典型用途 |
|---|---|---|
| `set_turbulence_model(inp, model)` | `eqnset_define` 第 1 行 v4/v5 + 第 3 行 v12/v14 联动 | SST → SA,SA → k-ε,任意 → LAMINAR |
| `set_energy_model(inp, model, T_trans, T_vib)` | `physics.tnoneq_numeqns` + 联动 `eqnset_define` v6 + `physics.reftem` / `vibtem` | NONE → TWO_TEMP,TWO_TEMP → NONE |
| `set_gas_type(inp, model)` | `eqnset_define` 第 2 行 v6 + v22/v23/v24/v25 联动 + `physics.tnoneq_numeqns` | PERFECT_GAS → REAL_GAS / MULTI_TEMP |

**与 v0.9.1 的区别:**

- v0.9.1 的 `TwoTemperaturePreset` **只**写 `physics.*` 字段,不碰 `eqnset_define` 的 v6/v22/v23(已知限制 §18-6)
- v0.10.0 三个 `set_*_model()` 都联动写 **所有相关位置**,确保 CFD++ 求解器读到一致的方程系统

---

## 19.2 完整 YAML 示例

```yaml
template: cases/base/mcfd.inp
output_dir: sweep_runs
naming: case_{mach}_{turbulence}_{energy}

sweeps:
  mach: [0.6, 0.8]
  turbulence: [sst, sa, laminar]   # 枚举轴(短名 alias 自动识别)
  energy: [none, 2t]               # 枚举轴
  gas: [perfect-gas, real-gas]     # 枚举轴

equation_switches:                 # 布尔开关(默认全 true)
  turbulence: true
  energy: true
  gas: true

turbulence:                         # 顶层默认(老契约)+ per-case 覆盖(新)
  I: 0.01
  L: 0.01
  U_ref: 204
  overrides:
    sst: {I: 0.005, L: 0.02, U_ref: 250}
    sa:  {I: 0.03,  L: 0.005, U_ref: 100}

energy_overrides:
  2t:   {T_trans: 300, T_vib: 200}
  none: {reftem: 288.15}
```

笛卡尔展开:3 mach × 3 turbulence × 2 energy × 2 gas = 36 cases(用户可改 axis 数)。

### 19.2.1 `equation_switches` 行为

| 开关 | 关闭时的行为 |
|---|---|
| `turbulence: false` | 跳过 `set_turbulence_model()`,但仍按 `turbulence.{I,L,U_ref}` 写初始化参数(适用"换算例不改方程"的场景) |
| `energy: false` | 跳过 `set_energy_model()` 与 `energy_overrides`,保留模板的能量模型 |
| `gas: false` | 跳过 `set_gas_type()`,不切气体类型 |

**典型用例:** 对比同一物理参数下不同网格/Mach 时,把湍流/能量/气体全部关掉,只让别的轴(网格密度)生效。

### 19.2.2 `overrides` 与顶层默认的关系

```
对某个 case:
  effective = (turbulence 顶层默认) 覆盖到 (overrides[axis_value])
```

例如 case `{turbulence: sa}`:
- 顶层默认 → `{I: 0.01, L: 0.01, U_ref: 204}`
- overrides[`sa`] → `{I: 0.03, L: 0.005, U_ref: 100}`
- **结果:** `{I: 0.03, L: 0.005, U_ref: 100}`(per-case 完全替换,非合并)

### 19.2.3 `energy_overrides` 按 axis_value 查表

```
对 case {energy: 2t}:
  t_d = energy_overrides["2t"] = {T_trans: 300, T_vib: 200}
  → set_energy_model(inp, EnergyModel.TWO_TEMP, T_trans=300, T_vib=200)
```

未列出的 axis_value → 用函数默认(无 `T_trans`/`T_vib` 时抛 `two_temp_missing_temps`)。

---

## 19.3 错误表

| 触发条件 | 严重度 | code |
|---|---|---|
| `set_turbulence_model(inp, UNKNOWN)` | error | `unknown_turbulence_model` |
| `set_energy_model(inp, TWO_TEMP)` 缺 T_trans/T_vib | error | `two_temp_missing_temps` |
| `set_gas_type(inp, MULTI_TEMP)` 但 tnoneq_numeqns≠1 | error | `gas_multi_temp_requires_2t` |
| 切到 SA/Goldberg 残留 turbi_tlev/turbi_tlen | warning | `residual_turb_field` |
| 切到 LAMINAR 残留 turbi_* | warning | `residual_turb_field` |
| 切到 NONE 能量残留 vibtem | warning | `residual_vibtem` |
| YAML `sweeps.turbulence: [unknown_xxx]` | error | `unknown axis value 'unknown_xxx' for key 'turbulence'; expected one of [...]` |
| YAML `energy_overrides` 值为非 dict | error | `CaseSweep config: energy_overrides['2t'] must be a dict` |

> **错误 vs 警告:** 错误终止 sweep;警告只 `print(..., file=stderr)`,仍写文件(让用户自己决定是否清理)。

---

## 19.4 兼容性

| 项 | v0.9.1 行为 | v0.10.0 行为 |
|---|---|---|
| `turbulence: {I, L, U_ref}` 单值形式 | 合法,所有 case 共享 | 仍合法(等价于 `overrides: {}` 的全共享) |
| `sweeps` 无 `turbulence/energy/gas` 轴 | 合法 | 仍合法(等价于 axis 长度=1) |
| 无 `equation_switches` 字段 | N/A | 默认为 `{turbulence: true, energy: true, gas: true}` |
| 无 `energy_overrides` 字段 | N/A | 默认为 `{}` |
| `--strict-equations` flag | N/A | 默认 False(不破现有 sweep);True 时 1 个 warning 立即 fail |
| 老 REPL 命令(`turb` / `2t` / `detect`) | 正常 | 不变 |
| CLI 单 case 修改命令 | 正常 | 不变;新增 `set-equation` 类(可选) |

**保证:** 任何 v0.9.1 写过的 YAML 配置文件,在 v0.10.0 直接跑结果**字节级一致**(因为默认行为不变)。

---

## 19.5 枚举短名 alias

为方便 YAML/CLI 用户,以下短名 alias 自动识别(都映射到 enum 规范值):

| 轴 | 短名 alias | 映射到 enum.value |
|---|---|---|
| `turbulence` | `sst`, `sa`, `ke`, `keps`, `goldberg`, `laminar` | `k-omega-sst`, `spalart-allmaras`, `realizable-k-eps`, `realizable-k-eps`, `goldberg_rt`, `laminar` |
| `energy` | `2t`, `3t`, `none` | `2T`, `3T`, `none` |
| `gas` | `perfect`, `real`, `multi`, `mixture` | `perfect-gas`, `real-gas`, `multi-temp`, `mixture` |

**实现位置:** `inp_tool/sweep.py::_ENUM_ALIASES: Dict[type, Dict[str, str]]`

**查表顺序:**

1. 先按 enum.value 精确匹配(`"k-omega-sst"`)
2. 再按 alias 反查(`"sst"`)
3. 都失败 → `ValueError("unknown axis value '<v>' for key '<key>'; expected one of [...]")`

---

## 19.6 示例:CFD++ GUI 等价操作对照

| GUI 操作 | CLI/YAML 等价 |
|---|---|
| 在 Equation Set 页面下拉选湍流 | `sweeps.turbulence: [sst, sa]` |
| 改"气体类型"为 Real Gas | `sweeps.gas: [real-gas]` |
| 启用 2-温度 + 设 T_vib | `sweeps.energy: [2t]` + `energy_overrides.2t.T_vib: 200` |
| 不切湍流,只改初始化 | `equation_switches.turbulence: false` + 顶层 `turbulence: {I, L, U_ref}` |
| LAMINAR 算例配湍流 init | `_resolve_turb_init(laminar) → None`,自动跳过 preset |
| GUI "Reftem" 输入框(单值) | `energy_overrides.none.reftem: 288.15` |
| GUI "Vibtem" 输入框(单值,2T 模型) | `energy_overrides.2t.T_vib: 200` |

**LAMINAR 自动跳过:** LAMINAR 算例不写 `turbi_lev` / `turbi_tlev` / `turbi_len` / `turbi_tlen` 任何字段(求解器本身不用),即使配了也忽略。

---

## 19.7 v0.10.0+ Wizard 集成(方程感知步骤)

v0.10.0+ `WizardSweep` 在 `step_4` 与 `step_4a_detect` 之间插 2 个新步骤,
让用户**向导式**地构造 `sweeps: {turbulence/energy/gas: [...]}` 块,无需手写 YAML。

### 步骤顺序(新 10 步)

```
step_1_source_dir
step_2_output
step_3_mode                # 选 "1"(Cartesian)才进 4b
step_4_params              # 现有 — alpha/mach 等 sweeps
step_4b_equation_axes      # 新(Cartesian only)— 选 3 个 axis
step_4a_detect             # 现有 — 消费 sweeps_equation_warnings
step_4c_equation_overrides # 新(4b 选了 axis 才出现)— per-case I/L/U 或温度
step_5_naming
step_5a_pbs
step_6_preview
```

### `step_4b_equation_axes` 三个子问题

每个"Y/n + 多选菜单"模式,合并到 `data["sweeps"]`:

- Q1 turbulence: `sst` / `sa` / `keps` / `goldberg` / `laminar`(可多选)
- Q2 energy: `none` / `2t`(可多选)
- Q3 gas: `perfect-gas` / `real-gas` / `multi-temp`(可多选)

Cartesian gate:非 Cartesian 模式静默跳到 `step_4a_detect`,不动 `sweeps`。
全 skip → 不注入 axis key(等价 v0.10.0 老路径)。
至少选 1 axis → 同时存 `data["intended_axes"]` 供 `step_4a_detect` 末尾消费。

### `step_4a_detect` 消费 sweeps_equation_warnings

`detect_equations(inp, intended_axes=None)` 在 v0.10.0+ 接受 `intended_axes` 参数,
比对用户选的 axis 与 template 的 `eqnset_define` v4/v5/v6,发现冲突追加
`rep.sweeps_equation_warnings` 列表(独立于 `notes`,不污染方程检测自身告警):

| 用户选 | template 状态 | 警告 |
|---|---|---|
| `turbulence: sst` | LAMINAR | "SST 选但 template 是 laminar — preset 会被跳过" |
| `energy: 2t` | `tnoneq_numeqns=0` | "2T 选但 template tnoneq=0 — set_energy_model 会强制设 1" |
| `gas: multi-temp` | v6=0 | "multi-temp 选但 template v6=0 — set_gas_type 会写 v6=11" |

`step_4a_detect` 末尾新增 `⚠ 你选的 axis 与 template 不兼容:` 段,把 warnings 展示给用户。

### `step_4c_equation_overrides` per-case 覆盖

触发条件:Cartesian + step_4b 选了至少 1 axis。
- Q0: 要给某些 case 设单独的 I/L/U 或温度?Y/n
- Q1(选了 turbulence):选湍流 model + 输 I/L/U_ref → 循环
- Q2(选了 energy):选能量 model + 输 T_trans/T_vib 或 reftem

输出:
- `data["turbulence"] = {I, L, U_ref, overrides: {<key>: {I, L, U_ref}}}`
- `data["energy_overrides"] = {"2T": {T_trans, T_vib}, "none": {reftem}}`

下游 `step_6_preview` 喂给 `CaseSweep.from_dict`,与 YAML 手写完全等效。

### 设计文档

详细 spec 见 `docs/superpowers/specs/2026-06-11-wizard-equation-axes-design.md`
(Status: ✅ 已批准 → v0.10.0 后续 PR)。

---

## 19.8 实现位置(代码索引)

| 概念 | 文件 | 关键符号 |
|---|---|---|
| 三大 set 函数 | `inp_tool/equations.py` | `set_turbulence_model`, `set_energy_model`, `set_gas_type` |
| 短名 alias 表 | `inp_tool/sweep.py` | `_ENUM_ALIASES: Dict[type, Dict[str, str]]` |
| 开关 dataclass | `inp_tool/sweep.py` | `EquationSwitches` (字段: `turbulence`, `energy`, `gas`) |
| 解析入口 | `inp_tool/sweep.py::CaseSweep.from_dict` | 行 ~717-755 |
| 主流程联动 | `inp_tool/sweep.py::generate()` | 行 ~1237-1250(3 个 `if equation_switches.X`) |
| 单元测试 | `inp_tool/tests/test_equations_setters.py` | 3 个 set_* 全覆盖 + alias 反向 |
| Sweep 集成测试 | `inp_tool/tests/test_sweep_equation.py` | 36 case 笛卡尔展开 + 字节级对比 |

---

## 19.8 相关文档

- 设计文档(implementation plan,实施中,完成后并入并删除):`docs/plans/2026-06-11_equation-sweep-extend.md`
- 前置章节:[18-equation-aware-config.md](18-equation-aware-config.md)
- Sweep 整体架构:[04-sweep-architecture](04-sweep-architecture.md)
- Sweep YAML schema:[05-sweep-usage](05-sweep-usage.md)
- 核心模块设计:[13-core-modules](../architecture/13-core-modules.md)
