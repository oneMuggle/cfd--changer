# 18 - 方程系统感知配置 (Equation-Aware Config)

> **状态:** v0.9.0 阶段 1-4 已实现;v0.9.1 CLI / REPL 集成中
> **代码:** [`inp_tool/inp_tool/equations.py`](../../inp_tool/inp_tool/equations.py)
> **测试:** [`inp_tool/tests/test_equations.py`](../../inp_tool/tests/test_equations.py)(61 个用例)
> **实测样本:** [`reference/inp_example/compare/`](../../reference/inp_example/compare/)(7 个 .inp,覆盖全部方程/湍流组合)

---

## 1. 模块目标

CFD++ 的 `mcfd.inp` 把"方程系统 + 湍流模型 + 物性"耦合在 3 处不同 block 里,且字段语义不直观(全是 X/Y 整数码)。本模块负责:

1. **检测** — 给定 `InpFile`,识别其方程系统(理想/真实/双温)、湍流模型(5 选 1)、物种数。
2. **写入(Preset)** — 给定高层物理参数(I, L, T 等),写出底层字段(k, ω, ν̃, T_vib 等)。
3. **联动校验** — 双温模型必须同时给 T_trans + T_vib,SST 必须 2 方程等。

---

## 2. 控制参数表(实测固化)

> **来源**:`reference/inp_example/compare/` 7 个真实 .inp 文件交叉验证 + 用户 2026-06-11 确认。

### 2.1 唯一权威 block:`eqnset_define`

位于顶层(不在 `physics` 块内),通过 `infsets` 引入:

```
infsets 1
#---------------------------------------------------------
seq.# 1 #vals 31 title eqnset_define
values v1  v2  v3  v4  v5     ← Row 1
values v6  v7  v8  v9  v10    ← Row 2
values v11 v12 v13 v14 v15    ← Row 3
values v16 v17 v18 v19 v20    ← Row 4
values v21 v22 v23 v24 v25    ← Row 5
values v26 v27 v28 v29 v30    ← Row 6
values v31                     ← Row 7
```

31 个值中,**只有 9 个**对方程系统/湍流模型有语义意义。其余 22 个固定(`v1=101`、`v2=v3=1`、`v7-v10=0,1,1,1`、`v11=0`、`v15-v20=0`、`v21=0`、`v26=3`、`v27-v31=0,0,0,0,0`)。

### 2.2 湍流模型 — 4 个位置 (v4 / v5 / v12 / v14)

| Case | v4 | v5 | v12 | v14 | TurbulenceModel 枚举 |
|---|---|---|---|---|---|
| 层流 | **0** | **1** | **5** | **0** | `LAMINAR` |
| Goldberg Rt (1eq) | **1** | **2** | **6** | **1** | `GOLDBERG_RT` |
| SA (1eq) | **1** | **4** | **6** | **1** | `SPALART_ALLMARAS` |
| Realizable k-ε (2eq) | **2** | **2** | **7** | **2** | `REALIZABLE_KEPSILON` |
| SST k-ω (2eq) | **2** | **3** | **7** | **2** | `SST_KW` |

**字段含义**(实测推断):
- `v4` = 湍流方程数(0 / 1 / 2)
- `v5` = 模型 ID(模型族内索引;Goldberg 与 k-ε 都是 2,要靠 v4 区分)
- `v12` = 总求解方程数 = 5 (N-S) + v4
- `v14` = v4 复制(parser 校验位)

**判别表**(`equations.py::_MAP_TURBULENCE`):

```python
_MAP_TURBULENCE: Dict[Tuple[int, int], TurbulenceModel] = {
    (0, 1): TurbulenceModel.LAMINAR,
    (1, 2): TurbulenceModel.GOLDBERG_RT,
    (1, 4): TurbulenceModel.SPALART_ALLMARAS,
    (2, 2): TurbulenceModel.REALIZABLE_KEPSILON,
    (2, 3): TurbulenceModel.SST_KW,
    # (3, *) 留 v0.10+:k-eps-Rt, k-eps-fmu
}
```

### 2.3 气体类型 / 多温 — 5 个位置 (v6 / v22 / v23 / v24 / v25)

| Case | v6 | v22 / v23 | v24 | v25 | GasModel 枚举 | 同时 `tnoneq_numeqns` |
|---|---|---|---|---|---|---|
| 理想气体 | **0** | 5 / 5 | 1 | **1** | `PERFECT_GAS` | 0 |
| 真实气体(空气,6 物种) | **1** | **23** / **23** | 1 | **6** | `REAL_GAS` | 0 |
| 双温热非平衡 | **11** | **25** / **25** | **10** | **10** | `MULTI_TEMP` | **1** |

**字段含义**:
- `v6` = 气体类型主开关(0 / 1 / 11)
- `v22` = `v23` = 系统总方程数(含物种 / 温度方程):理想 5 = N-S only;真实 23 = N-S(5) + 物种附加;双温 25 = N-S(5) + 物种 + 温度
- `v24` = 与温度方程数关联(双温 10,其他 1)
- `v25` = 物种数(理想 1,真实空气 6,双温 10)

**判别表**(`equations.py::_MAP_GAS`):

```python
_MAP_GAS: Dict[int, GasModel] = {
    0:  GasModel.PERFECT_GAS,
    1:  GasModel.REAL_GAS,
    11: GasModel.MULTI_TEMP,
}
```

### 2.4 能量模型 — `physics.tnoneq_numeqns`(1 个位置)

| 文件 | `physics.tnoneq_numeqns` | EnergyModel 枚举 |
|---|---|---|
| 理想 / 真实 / 所有理想气体湍流 | **0** | `NONE` |
| 双温模型 | **1** | `TWO_TEMP` |
| 三温(留 v0.10+) | 2 | `THREE_TEMP` |

**一致性约束**:`v6 == 11 ⇔ tnoneq_numeqns == 1`(双温模型两处必须互锁)。`detect_equations()` 不一致时会写 `notes` 警告。

---

## 3. ❌ 不要用这些(常见误区)

| 看起来像开关 | 为什么不能用 |
|---|---|
| `physics.gasnam` | 实测 7 文件**全部** `gasnam Air`,包括真实气体与双温;不能判别气体类型 |
| `physics.ntrbst` | 实测 6 算例**全 = 11**;不能判别湍流家族 |
| `block:iofiles.dfceli 1` | 只在 SA / SST 两个文件出现,Goldberg / k-ε 没有;是 IO 输出标记,非湍流开关 |
| `block:physics.ifwfne` | 理想气体+层流 = 2,其他 = 0;只是近壁面隐式权重,非湍流/气体语义开关 |
| `infsets N`(顶层) | 是 *settings 数*(eqnset 设置块的数量),不是物种数。实测 7 个 compare 文件都是 `infsets 1` |

---

## 4. API 速查

### 4.1 检测

```python
from inp_tool import parse_file
from inp_tool.equations import detect_equations

inp = parse_file("mcfd.inp")
rep = detect_equations(inp)

# 返回 EquationSystemReport
rep.energy        # EnergyModel.NONE / TWO_TEMP / THREE_TEMP / UNKNOWN
rep.turbulence    # TurbulenceModel.{LAMINAR, GOLDBERG_RT, SPALART_ALLMARAS, ...}
rep.gas           # GasModel.PERFECT_GAS / REAL_GAS / MULTI_TEMP / UNKNOWN
rep.gas_code      # 0 / 1 / 11(原始 v6 整数)
rep.ntrbst_family # v4 整数
rep.ntrbst_code   # v5 整数
rep.n_species     # 顶层 infsets 数
rep.notes         # 一致性告警(list[str])

# 中文摘要(给 wizard / REPL 显示)
print(rep.summary_zh())
# → 能量=2T  湍流=k-omega-sst  气体=multi-temp  物种数=55
```

### 4.2 湍流 Preset(写)

```python
from inp_tool.equations import SSTKOmegaPreset, make_turbulence_preset

# 直接用具体 preset
p = SSTKOmegaPreset(I=0.01, L=0.01, U_ref=204.0)
p.apply(inp)
# → 写入 block:guiopts.turbi_lev = k, .turbi_tlev = k/U², .turbi_len = L, .turbi_tlen = ω

# 或通过 detection 结果选 preset
rep = detect_equations(inp)
p = make_turbulence_preset(rep.turbulence, I=0.01, L=0.01, U_ref=204.0)
p.apply(inp)
```

支持 4 个湍流模型:`SSTKOmegaPreset` / `RealizableKEpsilonPreset` / `SpalartAllmarasPreset` / `GoldbergRTPreset`。每个有独立公式(见 `equations.py` `compute()` 实现 + 测试 `test_equations.py::TestSSTKOmega` 等)。

### 4.3 双温联动 Preset

```python
from inp_tool.equations import TwoTemperaturePreset, TwoTemperatureError

# 必须同时给 T_trans + T_vib;缺一抛 TwoTemperatureError
p = TwoTemperaturePreset(T_trans=300.0, T_vib=200.0)
p.apply(inp)
# → 写 physics.tnoneq_numeqns=1, physics.reftem=300, physics.vibtem=200

# 缺一会抛
TwoTemperaturePreset(T_trans=300.0).apply(inp)
# → TwoTemperatureError: 2T model requires BOTH T_trans and T_vib
```

> ⚠️ v0.9.1 的 `TwoTemperaturePreset` 只改 `physics.*` 字段,**不会自动**改顶层 `eqnset_define` 的 `v6=11`(实测需配套)。如果只改 `tnoneq_numeqns` 而 `v6` 不变,CFD++ 求解器可能不按双温走 — 留 v0.10 完整修复。

### 4.4 多组分 Preset

```python
from inp_tool.equations import SpeciesPreset

# mole 模式自动转 mass(用每个 species 的 Mwt)
p = SpeciesPreset(fractions={"CO": 0.5, "O2": 0.5}, mode="mole")
mass = p.convert(rep)  # → {"CO": 0.467, "O2": 0.533}(以 Mwt=28.01 / 32.00 估算)

# apply 当前 v0.9.1 仅做换算,不写文件(写顶层 infsets 留 v0.10)
```

---

## 5. 测试覆盖(61 个用例)

| 测试类 | 覆盖 |
|---|---|
| `TestDetectEnergy` | 4 个 tnoneq_numeqns 取值 |
| `TestDetectTurbulence` | 5 个湍流模型 + 未知/3-方程告警 |
| `TestDetectGas` | 7 个 v6 取值 + gasnam 退化场景 + infsets 不再判 MIXTURE |
| `TestSuanliDetection` | suanli 端到端(双温 + SST_KW + multi_temp) |
| `TestCompareFolderDetection` | `compare/` 7 个真实文件全覆盖 |
| `TestSSTKOmega` / `TestRealizableKEpsilon` / `TestSpalartAllmaras` / `TestGoldbergRT` | 4 个 preset 公式 |
| `TestTwoTemperaturePreset` | 联动写 + 缺一抛错 |
| `TestSpeciesPreset` | mass/mole 互转 + 归一化 + species 不存在抛错 |

---

## 6. 已知限制 (v0.9.1)

- ❌ 3-方程湍流家族(`(3, *)`)未实现 — 仅写 `notes` 告警留 v0.10+ scope。
- ❌ 3 温度(`tnoneq_numeqns=2`)未实现 — 检测器识别为 `THREE_TEMP` 但无 preset。
- ❌ 顶层 species 显式枚举(`species_*.Mwt1_*` 解析)未实现 — `SpeciesEntry` 数据类已声明但 `detect_equations` 还不填。
- ❌ `eqnset_define` 写入功能未实现 — 当前 preset 只改 `physics.*` 和 `guiopts.*`,**不改** v6/v22/v23/v24/v25。要切换气体类型需手改文件或 v0.10 实现。
- ❌ wizard 集成未完成 — `WizardModifyFile.step_2_detect` / `WizardSweep.step_4a_presets` 留 v0.9.1 后续 PR。

---

## 7. 相关文档

- 完整设计文档(implementation plan):`docs/plans/2026-06-10_equation-aware-config.md`(实施中,完成后会被并入本章并删除)
- 核心模块设计:[13-core-modules](13-core-modules.md)
- Sweep 集成路径:[09-sweep-risks-roadmap](09-sweep-risks-roadmap.md) §2 v0.9.x roadmap

## v0.10.0 扩展

本章 v0.9.1 描述的是"detect + 单一 case 初始化"。v0.10.0 扩展为"sweep 按 case 切模型"。

详见 [19-equation-sweep-extend.md](19-equation-sweep-extend.md)。
