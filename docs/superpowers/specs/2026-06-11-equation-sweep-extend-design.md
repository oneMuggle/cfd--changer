# 批量算例切模型（方程/湍流/气体）— 设计文档

**日期**: 2026-06-11
**作者**: brainstorming with user
**Status:** ✅ 已批准,实施中
**目标版本**: inp-tool v0.10.0
**前置**: v0.9.1（方程感知 — commit 3160d8d；`detect_equations` / `TurbulencePresetBase` / `TwoTemperaturePreset` / `SpeciesPreset` 已就位）

---

## 1. 背景与目标

v0.9.1 实现了"方程感知"——能 **detect** 一个 .inp 文件的能量/湍流/气体类型,并对 **单一 case** 应用初始化 preset(湍流 I/L/U、2T 联动温度)。但 sweep **批量** 场景下用户的需求超出 v0.9.1 范围:

| 痛点 | 影响 |
|------|------|
| 想对比 SST vs SA vs k-ε,只能跑三次 sweep,改三次 template | 工作量 ×3,且易复制出错 |
| 想对比完美气体 vs 真实气体 vs 双温 | 同样要改 template 重跑 |
| 不同 case 想要不同的湍流强度 I、特征长度 L(同一模型不同工况)| v0.9.1 顶层 `turbulence: {I, L}` 是**单值**,不能 per-case 覆盖 |

实测样本(`reference/inp_example/compare/`)已经覆盖 7 种组合,见 `docs/technical/18-equation-aware-config.md` 末尾的真值表。

**v0.10.0 目标**:让 sweep 能 **按 case 切换** 控制方程、湍流模型、气体类型;初始化参数 (I/L/U_ref, T_trans/T_vib) 顶层默认 + per-case 覆盖。

---

## 2. 非目标(YAGNI)

- ❌ **多组分编辑**(infsets 改数、species 加减、Mwt 改写、mass/mole fracs 写回)— v0.10+ 留 v0.11 单独 spec;`SpeciesPreset` 在 v0.10.0 仍 v0.9.1 占位
- ❌ **3-温度能量模型**(tnoneq_numeqns=2)— 已知 v0.10+ scope,本版不解析、不写
- ❌ **3-方程湍流家族**(X=3, k-eps-Rt / k-eps-fmu)— 留 v0.10+ scope
- ❌ **`physics.ntrbst` 改写**— 实测 6 文件全 = 11,不可靠;只改 `eqnset_define` v4/v5
- ❌ **多 template 库管理**(每模型一份 template)— 用户给单 template,框架改写
- ❌ **跨 case 的方程间一致性自动校验**(如"切到 NONE 能量后自动清 vibtem"可选,本版只 warning,不开 auto-clean)— 见 §3.1

---

## 3. 涉及文件

| 文件 | 动作 | 估行数 |
|------|------|--------|
| `inp_tool/inp_tool/equations.py` | 新增:`set_turbulence_model` / `set_energy_model` / `set_gas_type` / `EquationRewriteError` / `EquationRewriteIssue`;`TurbulencePresetBase` 加 `clear_incompatible_fields: bool` 字段 | +200 / -5 |
| `inp_tool/inp_tool/sweep.py` | `SweepSpec` 加枚举轴识别(按 key 名 `turbulence` / `energy` / `gas`);`CaseSweep` 加 `equation_switches` / `turbulence.overrides` / `energy_overrides` 字段;`from_dict` 解析;`generate()` 末尾循环改写顺序 | +120 / -30 |
| `inp_tool/inp_tool/cli.py` | `sweep` 子命令加 `--strict-equations` flag;REPL 暴露 `do_set_turbulence` / `do_set_energy` / `do_set_gas`(可选) | +60 / -5 |
| `inp_tool/inp_tool/__init__.py` | 导出新异常 + 新写函数 | +5 / -0 |
| `inp_tool/inp_tool/repl.py` | (可选) 3 个新命令 `set-turb` / `set-energy` / `set-gas`,按 detect 到的 model 改写 | +60 / -0 |
| `inp_tool/tests/test_equation_rewrite.py` | 新建:7 组测试(详见 §6.3) | +400 |
| `inp_tool/tests/test_sweep_equation_axes.py` | 新建:笛卡尔 + CSV + groups 3 模式覆盖 | +200 |
| `docs/technical/19-equation-sweep-extend.md` | 新建:3 个新写函数 API、YAML schema、笛卡尔示例、错误表 | +350 |
| `docs/technical/README.md` | 目录加 `19-...` 章节 | +3 / -0 |
| `docs/technical/18-equation-aware-config.md` | 末尾加 "v0.10.0 扩展" 一节,链向 19 章 | +20 / -0 |
| `CHANGELOG.md` | 新增 `[Unreleased]` 段(feat: set_*_model + sweep axes) | +15 / -0 |

**总估**:+1430 / -40。

---

## 4. 设计

### 4.1 SweepSpec 枚举轴识别(增量,向后兼容)

**SweepSpec.values 当前类型**:`Union[int, float, str, List[Union[int, float, str]]]`

**新规则**:按 **key 名** 自动识别为某枚举类型,字符串值查表映射:

| key 名 | 允许 string 值 | 映射到 |
|---|---|---|
| `turbulence` | `laminar` / `goldberg-rt` / `sa` / `sst` / `k-eps` | `TurbulenceModel` |
| `energy` | `none` / `2t` | `EnergyModel` |
| `gas` | `perfect-gas` / `real-gas` / `multi-temp` | `GasModel` |

其他 key(`alpha` / `beta` / `mach` / `T_inf` / `p_inf` / `re` 等)行为不变;若用户把 `sst` 写在 `alpha` 轴上,抛 `ValueError("unknown axis value 'sst' for key 'alpha'")`。

识别函数:

```python
_ENUM_AXES: Dict[str, type] = {
    "turbulence": TurbulenceModel,
    "energy": EnergyModel,
    "gas": GasModel,
}

def _normalize_axis_value(key: str, v: Any) -> List[Any]:
    if key in _ENUM_AXES and isinstance(v, str):
        enum_cls = _ENUM_AXES[key]
        try:
            return [enum_cls(v)]  # 短名/长名都支持 — 枚举 str 继承
        except ValueError:
            raise ValueError(
                f"unknown axis value {v!r} for key {key!r}; "
                f"expected one of {[e.value for e in enum_cls]}"
            ) from None
    return _normalize_axis(v)  # 老逻辑
```

**为什么 str 继承 Enum 够用**:`class TurbulenceModel(str, Enum)` (v0.9.1 已写)→ `TurbulenceModel("sst")` 等价 `TurbulenceModel.SST_KW`。

### 4.2 三个新写函数(`equations.py` 新增)

签名:

```python
def set_turbulence_model(
    inp: InpFile, model: TurbulenceModel,
) -> Dict[str, Any]:
    """改写顶层 `seq.# 1 #vals 31 title eqnset_define` 块第 1 行
    `values 101 1 1 v4 v5` 的 v4/v5 到 model 对应的 (X, Y)。
    返回 {applied_key: value};若写不动则 raise EquationRewriteError。

    校验:
    - model != UNKNOWN,否则 error
    - template 必须有 eqnset_define 块,否则 error
    - LAMINAR 写入 (0, 1);SST → (2, 3);SA → (1, 4);k-ε → (2, 2);Goldberg → (1, 2)
    - 写完 read-back 校验(在 inp.top_stmts 中可被 _find_eqnset_define 重新找到且 v4/v5 一致)
    """

def set_energy_model(
    inp: InpFile, model: EnergyModel,
    *, T_trans: Optional[float] = None,
    T_vib: Optional[float] = None,
    set_numeqns: bool = True,
) -> Dict[str, Any]:
    """改写 physics.tnoneq_numeqns + 联动 eqnset_define v6。

    NONE:
      - 设 physics.tnoneq_numeqns = 0
      - 联动 eqnset_define v6 → 0
      - 不动 reftem / vibtem(若已存在则 add note: 'energy=NONE but vibtem present')

    TWO_TEMP:
      - 强校验 T_trans/T_vib 都给(同 v0.9.1 TwoTemperaturePreset)
      - 设 physics.tnoneq_numeqns = 1(若 set_numeqns=True)
      - 写 physics.reftem = T_trans、physics.vibtem = T_vib
      - 联动 eqnset_define v6 → 11
    """

def set_gas_type(
    inp: InpFile, model: GasModel,
) -> Dict[str, Any]:
    """改写顶层 `seq.# 1 #vals 31 title eqnset_define` 块第 2 行
    `values v6 ...` 的 v6 到 model 对应码。

    一致性校验:
    - v6=11 → 必须 tnoneq_numeqns=1(否则 error)
    - 现有 tnoneq_numeqns=1 但 v6=0 → warning
    - v6=1(真实气体)+ tnoneq_numeqns>0 → warning(物性冲突)
    """
```

**共享异常**:

```python
class EquationRewriteError(ValueError):
    """set_*_model 写不进去或一致性破坏时抛。"""

@dataclass
class EquationRewriteIssue:
    """写完后追加到 inp.notes 列表;generate 末尾聚合。"""
    severity: str  # "error" | "warning"
    code: str      # "unknown_model" / "inconsistent_v6" / "residual_field" / ...
    message: str
    # 复用 v0.9.0 PbsIssue 字段结构(severity/code/message)
```

### 4.3 `generate()` 末尾循环改写顺序

```python
for case_spec in flat:
    inp = deepcopy(template_inp)
    params = case_spec.values

    # === ① 切方程(先于 preset) ===
    if sweep.equation_switches.turbulence and "turbulence" in params:
        applied.update(set_turbulence_model(inp, params["turbulence"]))
    if sweep.equation_switches.energy and "energy" in params:
        applied.update(set_energy_model(
            inp, params["energy"],
            T_trans=..., T_vib=...,  # per-case 覆盖或顶层默认
        ))
    if sweep.equation_switches.gas and "gas" in params:
        applied.update(set_gas_type(inp, params["gas"]))

    # === ② 现有 freestream(基于 alpha/beta/mach) ===
    if sweep.freestream is not None:
        applied.update(sweep.freestream.apply(inp, params))

    # === ③ 现有 turbulence preset(改"按 case 模型"动态选) ===
    if "turbulence" in params:
        # per-case 覆盖 I/L/U_ref;sweeps.turbulence.overrides 优先,顶层默认兜底
        init = _resolve_turb_init(params["turbulence"], sweep)
        if params["turbulence"] != TurbulenceModel.LAMINAR:
            applied.update(make_turbulence_preset(
                params["turbulence"], I=init.I, L=init.L, U_ref=init.U_ref
            ).apply(inp))
    elif sweep.turbulence_default is not None:
        # 老契约:没 sweeps.turbulence 轴,但顶层有 turbulence: {I,L,U_ref}
        applied.update(sweep.turbulence_default.apply(inp))

    # === ④ 现有 two_temperature preset(改"按 case 能量"动态选) ===
    # 同上对称:有 energy 轴时按 case 决定 NONE(不写)还是 TWO_TEMP(写)
    # 老契约:无 energy 轴但顶层有 two_temperature: {T_trans, T_vib} → 沿用 v0.9.1

    # === ⑤ 现有 overrides ===
    _apply_overrides(inp, sweep.overrides)
```

**关键不变量**:preset 应用**永远在**切模型**之后**;切模型后 case 已是新方程系统,preset 据此选 SSTKOmegaPreset 还是 SpalartAllmarasPreset。

### 4.4 残会 guiopts 字段处理

`TurbulencePresetBase` 加字段:

```python
@dataclass
class TurbulencePresetBase(ABC):
    clear_incompatible_fields: bool = True   # v0.10.0 新增

    def _clear_incompatible(self, gb: Block, new_model: TurbulenceModel) -> List[str]:
        """根据 new_model 决定清掉哪些 turbi_* 字段。
        返回被清字段名(供 notes 记录)。

        SST / Realizable k-ε(2-方程):保留 turbi_lev, turbi_len, turbi_tlev, turbi_tlen
        SA / Goldberg RT(1-方程):保留 turbi_lev, turbi_len;清 turbi_tlev, turbi_tlen
        LAMINAR:清全部 turbi_*
        """
```

CLI `--strict-equations` flag 开启时:残留字段 → `EquationRewriteError(error, "residual_field")` → `SweepValidationError`。

### 4.5 opt-out 机制

```yaml
# 顶层三个开关,默认全 true(切)
equation_switches:
  turbulence: true   # 改 false → 只做初始化,不动 eqnset_define
  energy: true
  gas: true
```

CLI 等价:`inp-tool sweep --no-switch-turbulence`。

### 4.6 Per-case I/L/U 覆盖

```yaml
turbulence:           # 顶层默认(v0.9.1 老契约)
  I: 0.01
  L: 0.01
  U_ref: 204
  overrides:           # v0.10.0 新增:per-case 覆盖
    sst: {I: 0.005, L: 0.02, U_ref: 250}
    sa:  {I: 0.03,  L: 0.005, U_ref: 100}
```

`_resolve_turb_init(model, sweep)` 查表顺序:
1. `sweep.turbulence.overrides[model.value]`
2. `sweep.turbulence` 顶层默认(I/L/U_ref)
3. 若都没有 → 抛 `KeyError("I and L are required")`(同 v0.9.1 行为)

类似 `energy_overrides`:`{none: {reftem: 288.15}, 2t: {T_trans: 300, T_vib: 200}}`。

### 4.7 完整 YAML 示例

```yaml
template: cases/base/mcfd.inp
output_dir: sweep_runs
naming: case_{mach}_{turbulence}

sweeps:
  mach: [0.6, 0.8]
  turbulence: [sst, sa]            # 新:枚举轴
  energy: [none, 2t]              # 新:枚举轴
  gas: [perfect-gas, real-gas]    # 新:枚举轴

equation_switches:                # 新:opt-out 开关
  turbulence: true
  energy: true
  gas: true

turbulence:                        # 老契约 + 新 overrides
  I: 0.01
  L: 0.01
  U_ref: 204
  overrides:
    sst: {I: 0.005, L: 0.02, U_ref: 250}
    sa:  {I: 0.03,  L: 0.005, U_ref: 100}

energy_overrides:                  # 新:per-case 温度覆盖
  none: {reftem: 288.15}
  2t:   {T_trans: 300, T_vib: 200}

source_dir: cases/base
copy_strategy: hardlink
```

笛卡尔展开:2 × 2 × 2 × 2 = **16 cases**。每个 case 跑前先 detect + 改写 + 写 preset。

---

## 5. 验证矩阵

| 触发条件 | 严重度 | code | message |
|---|---|---|---|
| `set_turbulence_model(inp, UNKNOWN)` | error | `unknown_turbulence_model` | `cannot switch to UNKNOWN turbulence model` |
| `set_turbulence_model` 找不到 eqnset_define 块 | error | `no_eqnset_define` | `template has no seq.# 1 ... eqnset_define block; cannot switch` |
| `set_energy_model(inp, TWO_TEMP)` 但 T_trans/T_vib 缺一 | error | `two_temp_missing_temps` | `TwoTemperatureError: both T_trans and T_vib required` |
| `set_gas_type(inp, MULTI_TEMP)` 但 tnoneq_numeqns≠1 | error | `gas_multi_temp_requires_2t` | `gas=multi-temp requires energy=2T (tnoneq_numeqns=1)` |
| 现有 tnoneq_numeqns=1 但 set_gas_type → PERFECT_GAS | warning | `gas_inconsistent_with_energy` | `tnoneq_numeqns=1 but gas=perfect-gas (v6=0); may be inconsistent` |
| 切到 SA/Goldberg 后 guiopts 残留 turbi_tlev/turbi_tlen | warning(strict→error) | `residual_turb_field` | `residual fields may confuse solver: turbi_tlev, turbi_tlen` |
| 切到 LAMINAR 后 guiopts 残留 turbi_* 全部 | warning(strict→error) | `residual_turb_field` | `LAMINAR + residual turbi_*` |
| 切到 NONE 能量后 vibtem 残留 | warning | `residual_vibtem` | `energy=NONE but vibtem=... present` |
| `sweeps.turbulence=[laminar]` + 顶层 `turbulence.I` | warning | `laminar_with_init` | `LAMINAR case cannot use I/L/U; preset will skip` |

校验时机:每次 `set_*_model()` 末尾追加 `EquationRewriteIssue` 到 `inp.notes` 列表;`generate()` 末尾聚合 → warning 打 stderr,error 累计到 `SweepValidationError`(v0.9.0 已有的异常)。

---

## 6. 测试

### 6.1 覆盖率目标:≥ 80%

### 6.2 单元测试(`tests/test_equation_rewrite.py`,新建)

| 类 | 用例数 | 关键场景 |
|---|---|---|
| `TestSetTurbulenceModel` | 5 | SST→SA 改 v4=1,v5=4;SA→SST 改 v4=2,v5=3;→LAMINAR 改 v4=0,v5=1;UNKNOWN 抛 error;无 eqnset_define 抛 error |
| `TestSetEnergyModel` | 4 | NONE→TWO_TEMP 联动 tnoneq_numeqns=1 + 写 vibtem;TWO_TEMP→NONE 清 numeqns=0;T_trans/T_vib 缺一抛 TwoTemperatureError;联动 v6=0/11 |
| `TestSetGasType` | 3 | 0→1;0→11 强制 tnoneq_numeqns=1;1→11 抛 error |
| `TestEquationRewriteIssue` | 3 | severity/code/message 字段;复用 PbsIssue 结构 |
| `TestResidualFieldsStrict` | 2 | 默认保留不报错;`--strict-equations` 抛 SweepValidationError |
| `TestClearIncompatibleFields` | 3 | SST→SA 清 tlev/tlen;LAMINAR 清全部;SST→SST 保留 |
| `TestBackwardCompat` | 4 | 跑 v0.9.1 的 9 个 detect_equations 测试 + 4 个 preset 测试,全 pass |

### 6.3 集成测试(`tests/test_sweep_equation_axes.py`,新建)

| 用例 | 场景 |
|---|---|
| `test_cartesian_with_turbulence_axis` | `sweeps.turbulence=[sst, sa]` × `mach=[0.6, 0.8]` → 4 cases,每个 case 的 `eqnset_define` v4/v5 正确 |
| `test_csv_with_turbulence_column` | CSV 含 `turbulence` 列 → 4 cases 同上 |
| `test_groups_with_turbulence_key` | `groups[].common.turbulence` 命中 |
| `test_per_case_turb_init_override` | `turbulence.overrides.sst.I=0.005` 只影响 sst case |
| `test_strict_mode_raises` | SST→SA + 残留字段 + `--strict-equations` → 抛 `SweepValidationError` |
| `test_unknown_axis_value` | `sweeps.turbulence=[sst, foo]` → `ValueError("unknown axis value 'foo'")` |
| `test_opt_out_no_touch` | `equation_switches.turbulence=false` → eqnset_define v4/v5 不变,只写 guiopts |

### 6.4 手工 e2e(developer)

```bash
# 1) 跑全量
conda run -n cfdchanger pytest inp_tool/tests/ -v --tb=short

# 2) 跑 sweep 实际生成
conda run -n cfdchanger python -m inp_tool.cli sweep \
    reference/inp_example/compare/可压缩理想气体+2方程SST\ mcfd.inp \
    --dry-run --verbose

# 3) 跑新轴 (sweep 笛卡尔=2×2×2=8 cases)
cat > /tmp/eq_sweep.yaml <<'EOF'
template: reference/inp_example/compare/可压缩理想气体+2方程SST mcfd.inp
output_dir: /tmp/eq_sweep_out
sweeps:
  mach: [0.6, 0.8]
  turbulence: [sst, sa]
  gas: [perfect-gas, real-gas]
naming: case_{mach}_{turbulence}_{gas}
EOF
conda run -n cfdchanger python -m inp_tool.cli sweep --config /tmp/eq_sweep.yaml --dry-run
```

---

## 7. 文档更新

| 文件 | 改动 |
|---|---|
| `docs/technical/19-equation-sweep-extend.md` | 全文:3 个新写函数 API、YAML schema、笛卡尔示例、错误表 |
| `docs/technical/README.md` | 目录加 `19-...` 章节 |
| `docs/technical/18-equation-aware-config.md` | 末尾加 "v0.10.0 扩展" 一节,链向 19 章 |
| `CHANGELOG.md` | 新增 `[Unreleased]` 段 |
| 本 spec 文件 | 实施完毕后更新 Status 行 |

---

## 8. 风险与缓解

| 风险 | 缓解 |
|---|---|
| parser 对 `eqnset_define` 的 children 解析可能漏行(v0.9.1 已知 31 个 values 中只读前 5 个) | `set_*_model` 写完必须 read-back 校验(单元测试覆盖) |
| `make_turbulence_preset` 当前依赖 detect;切模型后调用顺序要重排 | §4.3 第 ③ 步明确"先切后 preset" |
| 用户已 hardcode `ntrbst=11` 在 physics 块(实测 6 文件全 11) | 文档明示 `physics.ntrbst` 不可靠(v0.9.1 已记);v0.10.0 切湍流时不写 ntrbst(只改 eqnset_define) |
| 三平台兼容(Win7/Win10/Linux)— `set_*_model` 全部 stdlib | 已确认(跟 v0.9.1 一致) |
| 笛卡尔组合爆炸:5 湍流 × 2 能量 × 3 气体 × N 工况 = 30N cases | 文档明示"N 大时考虑分批 sweep,或用 cases 模式显式列" |
| `--strict-equations` 误开启导致大 sweep 全 fail | 默认 False;CLI help 写明;文档单列"什么时候开" |

---

## 9. 实施步骤(草案,供 writing-plans 拆任务)

1. 在 `equations.py` 新增 `set_turbulence_model` / `set_energy_model` / `set_gas_type` 三个纯函数 + `EquationRewriteError` + `EquationRewriteIssue`
2. 写 `tests/test_equation_rewrite.py` 单元测试,RED→GREEN
3. 扩 `SweepSpec` 接受枚举字符串(按 key 名识别)
4. 改 `CaseSweep` 加 `equation_switches` / `turbulence.overrides` / `energy_overrides`;`from_dict` 解析
5. 改 `generate()` 末尾循环:先切模型 → 选 preset → 应用
5. CLI 加 `--strict-equations` / `--no-switch-turbulence` / `--no-switch-energy` / `--no-switch-gas` flag
6. (可选) REPL 加 `set-turb` / `set-energy` / `set-gas` 命令
7. 写 `19-equation-sweep-extend.md`
8. 跑 `test_equation_rewrite.py` + 跑全量 `tests/` → 全 pass
9. 跑 `conda run -n cfdchanger ruff check . && mypy inp_tool/`
10. 提 PR(feature 分支),CI 绿后 merge
11. merge 后 bump `__version__` 0.9.1 → 0.10.0,打 tag

---

## 10. 决策追溯(本 spec 关键设计取舍)

| 决策 | 选 | 不选 | 理由 |
|---|---|---|---|
| SweepSpec 表达方式 | **枚举轴直接做 sweeps key** | 专用 `equation_axes` 字段 / 只能 cases 模式 | 与现有 SweepSpec 完全对称,CSV/cases/groups 都能复用 |
| template 策略 | **单 template 重写 eqnset_define** | 多 template 库 / 显式 `--no-override` | 用户工作流最简,只维护一份 |
| 残会字段 | **默认保留,strict 才报错** | 默认清 / 默认报错 | 不破坏老契约,strict 模式给挑剔用户 |
| 初始化参数源 | **顶层默认 + per-case 覆盖** | 每 case 必显式 / 不提供 I/L/U | 90% 场景只需顶层默认,10% 场景可覆盖 |
| 覆盖语法 | **`turbulence.overrides: {sst: {...}}`** | 在 sweeps 嵌套 / 用 cases 模式 | YAML 顶层显式声明,跟 v0.9.1 老契约同字段 |
| 多组分 scope | **v0.11+** | 本 spec 一起做 | 多组分涉及 species 块原子写 + 字典轴,RISK 高 |
