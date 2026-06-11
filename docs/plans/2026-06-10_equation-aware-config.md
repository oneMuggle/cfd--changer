# 计划:方程系统感知的 mcfd.inp 配置向导(Equation-Aware Wizard)

> **状态:** 待用户确认(2026-06-11)
> **对应版本:** v0.9.1(预计,补丁级)
> **优先级:** 中-高(用户每次改 mcfd.inp 都要手算 k/ω 和 2T 温度,sweep + 改物性体验断链)
> **前置:** v0.9.0(sweep 整目录 + pbs 可选)已合入 main

---

## 1. 背景

### 1.1 问题

用户在改 `mcfd.inp` 时,需要同时懂 CFD++ 的"方程系统 + 湍流模型 + 物性"三方联动:

| 场景 | 用户必须做的事 | 现状 | 痛点 |
|---|---|---|---|
| **2 温度(2T)非平衡** | 改 `tnoneq_numeqns=1`(1 个非平动温度方程,=振动)后,**同时**改平动温度(`reftem`)+ 振动温度(`vibtem`)两个 IC/BC 字段 | REPL `set` 命令支持,但**没有提示 2T 需要两个温度**;且 完美气体→2T 切换时不会自动设 `tnoneq_numeqns=1` | 用户忘了改振动温度,跑出来 2T 模型无意义 |
| **SST k-ω 湍流** | 用户给湍流强度 `I` 和特征长度 `L`,求解器要 `k` 和 `ω` | 现有 `set` 只支持按字段名改;**没有 I/L → k/ω 的换算** | 手工算 k 和 ω 容易出错(系数、量级) |
| **多组分(质量/摩尔分率)** | 改 `seq.# N values Y_1 ... Y_N`(质量)或 X(摩尔) | REPL `set` 一次只能改一个 values 子行,**不能保证总和=1**;**不能 Y ↔ X 互转** | 用户手算归一化、忘记换算、不同输入单位混用 |

参考用例 `/home/fz/project/cfd--changer/reference/suanli/mcfd.inp` 是一个真实的 CFD++ 算例:

- `physics` 块 493-696 行:含 `tnoneq_numeqns=1`(2T 配置,但当前算例可能未使用 2T 物理)、`ifrnue=1`(粘性)、**`ntrbst=11`(不可靠!实测 6 个算例全 = 11)**、零方程系统(空)
- 顶层 `infsets 1` + `seq.# 1 #vals 31 title eqnset_define` 块:第 1 行 `values 101 1 1 X Y`(**X=方程数(0/1/2/3),Y=湍流模型码(家族内索引)**);第 2 行 `values Z 0 1 1 1`(**Z=气体类型(0=理想/1=真实)**);第 3 行 `values 0 K 5 C 0`(**K 和 C 随湍流家族变**)
- **6 个新参考算例**(`reference/inp_example/compare/`):覆盖 0/1/2-方程 + 4 个湍流模型(Goldberg RT, SA, SST, Realizable k-ε)+ 层流 + 理想/真实气体(已实测)
- 顶层 `infsets 1` + `seq.# 1 #vals 31 title eqnset_define` 块(第 1 行 `values 101 1 1 X Y`:**X=方程数(0/1/2/3)**,**Y=湍流模型码(家族内索引)**;第 2 行 `values Z 0 1 1 1`:**Z=气体类型(0=理想 / 1=真实)**);第 3 行 `values 0 K 5 C 0`:**K 和 C 随湍流家族变**(laminar→5/0, 1-eq→6/1, 2-eq→7/2)
- `guiopts` 块 704-755 行:含 `turbi_lev/len/mutmu`、`aero_ma/alpha/beta/u/v/w/temp/pres`、零湍流比
- 顶层 `infsets 55` + `seq.# 1..55` 复合 Stmt:5 个 species(CO / O2 / C / O / CO2),Mwt 已声明;**质量分率需用户补 seq.# N values 行**

### 1.2 现状缺口分析

| 模块 | 已具备 | 缺什么 |
|---|---|---|
| `parser.py` / `model.py` / `writer.py` | 通用 Block + Stmt 解析,**不识语义** | 不知道 `tnoneq_numeqns=1`(启用 2T)意味着什么、不知道 `turbi_lev`/`turbi_len` 对应物理量 |
| `sweep.py::FreestreamPreset` | 高层来流 preset(alpha/beta/Ma → U/V/W) | **没有**湍流 preset、没有物性 preset、没有 2T 温度联动 preset |
| `wizard.py::WizardModifyFile` | 4 步通用:select file → fields → values → preview | **无检测**;用户必须自己知道要改哪些字段(对新手极不友好) |
| `wizard.py::WizardSweep` | 6 步批量生成,默认开 FreestreamPreset | 同上:无湍流/物性/2T 支持 |
| `repl.py` `set` / `get` / `aero` | `aero` 是 freestream 快捷命令 | **无** `turb` / `species` / `2t` 等价的语义化命令 |

### 1.3 已存在的范式

- **FreestreamPreset**(v0.4 起,见 `docs/technical/06-sweep-freestream.md`)提供了"高层物理量 → 底层字段"映射的范式。
- **WizardModifyFile / WizardSweep**(v0.7.x / v0.8.x)提供了"任务向导"的范式。
- **SweepValidationError**(v0.9.0 起)提供了"预校验"范式。

本计划**复用**这三种范式,新增 3 个 Preset + 1 个预检测步骤 + 1 个新 Wizard。

---

## 2. 目标(Goals)

| # | 目标 | 验收 |
|---|------|------|
| **G1** | **自动检测** mcfd.inp 的方程系统 / 湍流模型 / 物性 species 清单,返回 dataclass 报告 | `detect_equations(inp) → EquationSystemReport`,被 wizard / REPL / sweep 三处共用 |
| **G2** | **2 温度非平衡模型**(tnoneq_numeqns=1,1 个非平动温度方程)支持联动设值:平动温度 + 振动温度,提示用户两者都必须给 | `apply_to_inp(inp, T_trans=300, T_vib=300)` 原子写两个字段;缺一给明确错误 |
| **G3** | **多湍流模型初始化**:支持 4 个湍流模型(SST k-ω / Spalart-Allmaras / Goldberg RT / Realizable k-ε),给湍流强度 `I` + 特征长度 `L` + `Ma` / `T` → 自动算模型对应特征量写入 `turbi_lev` / `turbi_tlev` / `turbi_len` / `turbi_tlen` (具体字段映射按模型不同) | `TurbulencePresetBase.family=2eq-sst, I=0.01, L=0.01, ...` → 写 `turbi_lev=...` round-trip 字段值与手算一致(误差 < 1e-6);每个模型独立公式(见 §5.2) |
| **G4** | **多组分物性**:支持给定 mass fractions `Y_i` 或 mole fractions `X_i`,通过 Mwt 自动换算并写入顶层 `seq.# N values ...`;自动归一化(总和 → 1) | `SpeciesPreset(CO=0.5, O2=0.5, mode="mole").apply(inp)` → 写出正确 mass fractions,总和 1.0 ± 1e-9 |
| **G5** | **Wizard 一体化**:改单个文件的 `WizardModifyFile` 加"检测"步骤(自动报告当前方程系统、推荐字段集);`WizardSweep` 在 step_4_params 后加 1 步"湍流 / 物性 preset"可选启用 | 跑 `wizard modify-file` 改 2T 算例,自动出现"温度 + 振动温度"两个 prompt;不报 TypeError |
| **G6** | **REPL 语义化命令**:新增 `turb I=0.01 L=0.01`(自动算 k/ω) / `species CO=0.5 O2=0.5 mode=mole` / `2t T=300 Tvib=200` 三个快捷命令,等价于 wizard 高频子集 | `inp> turb I=0.01 L=0.01` 改 1 个文件,值符合公式;可 undo |
| **G7** | **Sweep 集成**:三个 Preset 接入 `CaseSweep`,支持 YAML / JSON / CLI flag;与现有 `freestream` preset 一样的 disabled-by-default 行为 | `sweep config.yaml` 加 `turbulence: {enabled: true, I: 0.01}` 后跑 sweep,每个 case 都套用 |
| **G8** | **100% 向后兼容** | 现有 449 + 6 skipped 测试零修改全绿;不开新 preset 时行为与 v0.9.0 完全一致 |
| **G9** | **覆盖率 ≥ 80%** | 新代码测试覆盖(检测 / 公式 / wizard / REPL / sweep 集成),pytest --cov 锁线 |

---

## 3. 非目标(明确不做)

- ❌ **CFD++ GUI 集成**:本计划只覆盖 CLI / wizard / REPL / sweep;GUI 在另一项目 `cfd-gui/`。
- ❌ **多温度(3T / multi-T)**:CFD++ 还有 3T 模型(Mach 7+ 高超声速,T_trans + T_vib + T_elec),本计划只支持 完美气体 + 2T;3T 留 v0.10+(检测器识别但 preset 不实现)。
- ❌ **化学反应动力学参数**(reaction rate 系数、Arrhenius A/n/Ea)改动:超 scope,留 v0.10+。
- ❌ **SST 之外的湍流模型自动算 k/ω**:如 k-ε、SA、RSM 等各有不同公式;**只做 SST k-ω** 这一个最常用,且显式让用户选模式;其他模式留给 v0.10+。
- ❌ **CFD++ 内部守恒量检查**(动量 / 能量 / species 质量守恒):这是求解器职责,本工具只生成 .inp。
- ❌ **多组分物性(C.dat / CO.dat / CO2.dat 等文件)生成**:超 scope,留 v0.10+。
- ❌ **回写 species 物性(sutherland、cp-coef、HF、GF 等)**:v0.10+。
- ❌ **自动推断湍流强度 / 长度**:本工具接受用户给定值,不做"经验公式"(如外流 `I = 0.16 * Re_D^{-1/8}`)— 留给 expert 用户的 overrides。

---

## 4. 涉及文件

| 文件 | 动作 | 估行数 |
|------|------|--------|
| `inp_tool/inp_tool/equations.py`(新) | 检测 + 3 个 Preset(SST k-ω / 2T / Species)+ 公式模块 | +350 |
| `inp_tool/inp_tool/__init__.py` | 导出 `detect_equations`、`TurbulenceKOmegaPreset`、`TwoTemperaturePreset`、`SpeciesPreset`、3 个异常类 | +20 |
| `inp_tool/inp_tool/sweep.py` | `CaseSweep` 新增 `turbulence` / `two_temperature` / `species` 字段(均 Optional),`from_dict` 解析;`generate()` 末尾按顺序应用 preset | +120 / -10 |
| `inp_tool/inp_tool/wizard.py` | `WizardModifyFile` 4 → 5 步(加 `step_2_detect`);`WizardSweep` 6 → 7 步(加 `step_4a_presets`) | +180 |
| `inp_tool/inp_tool/repl.py` | 新增 `do_turb` / `do_species` / `do_2t` 三个语义化命令,委托到 equations 模块 | +150 |
| `inp_tool/inp_tool/cli.py` | `inp-tool info` 加 `--detect` flag(显示方程系统 + 湍流 + species 报告) | +60 |
| `inp_tool/inp_tool/i18n.py` | 加 30+ 新 i18n keys(turb、2t、species 相关提示) | +60 |
| `inp_tool/tests/test_equations.py`(新) | 检测器 / 公式 / 3 个 preset 全套单元测试 | +300 |
| `inp_tool/tests/test_sweep_presets.py`(新) | sweep 集成(3 个 preset + 现有 freestream 共存) | +200 |
| `inp_tool/tests/test_wizard_modify_detect.py`(新) | WizardModifyFile 新增检测步骤的交互测试 | +120 |
| `inp_tool/tests/test_repl_turb_species.py`(新) | REPL `turb` / `species` / `2t` 命令测试 | +180 |
| `inp_tool/tests/test_cli_detect.py`(新) | `inp-tool info --detect` CLI 测试 | +80 |
| `inp_tool/tests/test_backward_equations.py`(新) | **关键**:现有 449 + skipped 6 零修改全绿 | +30 |
| `docs/technical/18-equation-aware-config.md`(新) | 本计划归档版 | +400 |
| `docs/user-manual/15-turbulence-2t-species.md`(新) | 终端用户手册:turb / 2t / species preset 用法 | +250 |
| `docs/technical/13-core-modules.md` | `§7 equations 模块` 新增章节 | +60 |
| `CHANGELOG.md` | v0.9.1 段 | +25 |

净代码 +1450(含测试),文档 +750。**单 PR 略大**,建议拆 2-3 个 PR(数据模型 + 检测 → preset + REPL → wizard + sweep 集成),见 §6。

---

## 5. 技术方案

### 5.1 数据模型

```python
# inp_tool/equations.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class EnergyModel(str, Enum):
    """能量模型(对应 physics.tnoneq_numeqns 字段,**非平动温度方程数**)"""
    NONE       = "none"        # tnoneq_numeqns == 0 → 完美气体(单 T)
    TWO_TEMP   = "2T"          # tnoneq_numeqns == 1 → 2-温度(T_trans + T_vib)
    THREE_TEMP = "3T"          # tnoneq_numeqns == 2 → 3-温度(+ T_elec)— v0.10+ scope
    UNKNOWN    = "unknown"     # 字段缺失或值不在 {0,1,2}


class TurbulenceModel(str, Enum):
    """湍流模型。detection 基于顶层 `seq.# 1 #vals 31 title eqnset_define`
    块第 1 行 `values 101 1 1 X Y` 的 X(方程家族)+ Y(家族内码)。

    家族(由 X 决定):0=无(层流), 1=1-方程, 2=2-方程, 3=3-方程(留 v0.10+)。
    家族内码(由 Y 决定):不同家族含义不同(见下表)。
    """
    LAMINAR          = "laminar"             # 0 家族, 码 1
    GOLDBERG_RT       = "goldberg-rt"         # 1 家族, 码 2
    SPALART_ALLMARAS  = "spalart-allmaras"    # 1 家族, 码 4
    SST_KW            = "k-omega-sst"         # 2 家族, 码 3
    REALIZABLE_KEPSILON = "realizable-k-eps" # 2 家族, 码 2
    UNKNOWN           = "unknown"


class GasModel(str, Enum):
    PERFECT_GAS = "perfect-gas"
    REAL_GAS = "real-gas"
    MIXTURE = "mixture"     # 多 species(顶层 infsets + seq.# N values)
    UNKNOWN = "unknown"


@dataclass
class SpeciesEntry:
    """顶层 seq.# N values Mwt 解析出的 species"""
    name: str               # "CO"
    mwts: List[float]       # [28.01] 通常 1 个
    has_sutherland: bool
    has_cp: bool


@dataclass
class EquationSystemReport:
    """detector 的输出,所有 preset 共享"""
    energy: EnergyModel                    # NONE / TWO_TEMP / THREE_TEMP
    turbulence: TurbulenceModel            # LAMINAR / GOLDBERG_RT / SA / SST_KW / REALIZABLE_KEPSILON
    gas: GasModel                          # PERFECT_GAS / REAL_GAS / MIXTURE
    n_species: int = 0                     # 顶层 infsets 解析出的 species 数
    species: List[SpeciesEntry] = field(default_factory=list)
    has_gasnam: bool = False               # physics.gasnam 是否存在
    gasnam: Optional[str] = None           # "Air" / "CO2" / ...
    # 湍流原始索引(从 seq.# 1 第 1 行 values 取,用于追溯)
    ntrbst_family: Optional[int] = None    # X 值(0/1/2/3)
    ntrbst_code: Optional[int] = None      # Y 值(家族内索引)
    notes: List[str] = field(default_factory=list)  # 警告/说明

    def summary_zh(self) -> str:
        """给 wizard / REPL 显示的简短中文摘要"""
        return f"能量={self.energy.value}  湍流={self.turbulence.value}  气体={self.gas.value}  物种数={self.n_species}"

    def recommended_fields(self) -> List[str]:
        """根据检测结果,推荐 wizard step_2 展示的字段集"""
        fields: List[str] = []
        if self.energy == EnergyModel.TWO_TEMP:
            # 2T 模型:必须同时给 T_trans 和 T_vib
            fields += ["tnoneq_numeqns", "reftem (T_trans)", "vibtem (T_vib)"]
        elif self.energy == EnergyModel.NONE:
            # 完美气体:reftem 设了也无非平衡意义,但用户可能想改
            # 不主动推荐(避免噪声)
            pass
        # THREE_TEMP:超 scope,不推荐
        # 湍流模型推荐字段(每个湍流模型所需字段不同;v0.9.1 公式详见 §5.2)
        if self.turbulence in (TurbulenceModel.SST_KW,
                               TurbulenceModel.REALIZABLE_KEPSILON):
            # 2-方程:k + ω(或 k + ε)都要
            fields += ["turbi_lev (k)", "turbi_len (L)",
                       "turbi_tlev (k/U²)", "turbi_tlen"]
        elif self.turbulence in (TurbulenceModel.SPALART_ALLMARAS,
                                 TurbulenceModel.GOLDBERG_RT):
            # 1-方程:SA = ν̃,Golberg = ν̃_RT;只写 turbi_lev (1 个标量)
            fields += ["turbi_lev (ν̃)", "turbi_len (L)"]
        # LAMINAR:无湍流字段
        if self.gas == GasModel.MIXTURE:
            fields += ["species 质量分率 (mass/mole)"]
        return fields


# ============================================================
# 5.1.2 湍流模型码映射表(从 6 个实测文件交叉验证)
# ============================================================
# 家族(由 eqnset_define 第 1 行 values 第 4 位决定):0/1/2/3
# 家族内码(由第 5 位决定):含义随家族变
# 数据来源:reference/inp_example/compare/ 下 6 个 mcfd.inp + cfd-gui 文档
_MAP_TURBULENCE: Dict[Tuple[int, int], TurbulenceModel] = {
    (0, 1): TurbulenceModel.LAMINAR,                  # 层流(实测)
    (1, 2): TurbulenceModel.GOLDBERG_RT,               # 1-方程 Goldberg RT(实测)
    (1, 4): TurbulenceModel.SPALART_ALLMARAS,          # 1-方程 SA(实测)
    (2, 2): TurbulenceModel.REALIZABLE_KEPSILON,       # 2-方程 Realizable k-ε(实测)
    (2, 3): TurbulenceModel.SST_KW,                    # 2-方程 SST k-ω(实测)
    # 3-方程家族(k-eps-Rt, k-eps-fmu)留 v0.10+
}


def _find_top_stmt_by_title(inp: InpFile, title_substr: str) -> Optional[Stmt]:
    """找顶层 stmt 的 `title` 子串(seq.# N #vals K title XXX)。"""
    for s in inp.top_stmts:
        # values_raw[2:] 之后是 title;但我们的 parser 通常 title 在 keyword 后面
        # 这里简化为:seq.# N #vals K title XXX  — title 是 values_raw[2] 之后
        if s.keyword.startswith("seq.#") and title_substr in " ".join(s.values_raw[2:]):
            return s
    return None


def _collect_following_values(start_stmt: Stmt, max_count: int = 7) -> List[Stmt]:
    """从 start_stmt 开始,找后续 values 行直到下一个 seq.# / end-of-block。"""
    # 此处需要 InpFile 上下文的行号;v0.9.1 简化方案:用 start_stmt 的 line 找后续
    out: List[Stmt] = []
    # 实际实现需访问 InpFile 的所有顶层 stmt;此处伪代码
    # return inp.get_following_values(start_stmt, max_count)
    return out


def detect_equations(inp: InpFile) -> EquationSystemReport:
    """
    扫描 InpFile 推断:
    1) 能量模型:physics.tnoneq_numeqns(0/1/2)
    2) 湍流模型:顶层 seq.# 1 第 1 行 values 101 1 1 X Y
       (X=方程家族 0/1/2/3, Y=家族内码;**实测 ntrbst 不可靠**,6 个算例全 = 11)
    3) 气体类型:顶层 seq.# 1 第 2 行 values Z ... (Z=0 理想 / 1 真实)
    4) 物性:理想气体用 physics.gasnam/gasgam/gasmwt;真实气体用顶层 species
    """
    rep = EquationSystemReport(
        energy=EnergyModel.UNKNOWN,
        turbulence=TurbulenceModel.UNKNOWN,
        gas=GasModel.UNKNOWN,
    )

    # 1) 能量模型
    pb = inp.get_block("physics")
    if pb is not None:
        v = pb.get("tnoneq_numeqns")
        if v == 0:
            rep.energy = EnergyModel.NONE
        elif v == 1:
            rep.energy = EnergyModel.TWO_TEMP
        elif v == 2:
            rep.energy = EnergyModel.THREE_TEMP  # v0.10+ scope
        else:
            rep.notes.append(
                f"physics.tnoneq_numeqns={v!r} 非预期值(v0.9.1 仅支持 0/1/2)"
            )
        if pb.get_value("gasnam") is not None:
            rep.has_gasnam = True
            rep.gasnam = str(pb.get("gasnam"))

    # 2) 湍流模型:扫顶层 seq.# 1 #vals 31 title eqnset_define 块
    #    找第 1 行 values 101 1 1 X Y (湍流家族 X + 模型码 Y)
    #    找第 2 行 values Z ...    (气体类型 Z: 0=理想, 1=真实)
    eqnset_define_stmt = _find_top_stmt_by_title(inp, "eqnset_define")
    if eqnset_define_stmt is not None:
        # 解析后续 7 行 values(参考 cfd-gui Engineering Handbook § eqnset_define 块结构)
        values_lines = _collect_following_values(eqnset_define_stmt, max_count=7)
        if len(values_lines) >= 1:
            x_y = values_lines[0].get_values()
            # x_y = [101, 1, 1, X, Y] 至少 5 个
            if len(x_y) >= 5 and x_y[0] == 101:
                eq_count, turb_code = int(x_y[3]), int(x_y[4])
                rep.ntrbst_family = eq_count     # 保留家族索引
                rep.ntrbst_code = turb_code     # 保留家族内码
                rep.turbulence = _MAP_TURBULENCE.get(
                    (eq_count, turb_code), TurbulenceModel.UNKNOWN
                )
        if len(values_lines) >= 2:
            z = values_lines[1].get_values()
            if z and z[0] == 0:
                rep.gas = GasModel.PERFECT_GAS
            elif z and z[0] == 1:
                rep.gas = GasModel.MIXTURE  # 真实气体+多组分

    # 3) 顶层 species 解析(走 top_stmts;仅当 rep.gas == MIXTURE 时)
    infsets_stmt = next((s for s in inp.top_stmts if s.keyword == "infsets"), None)
    if infsets_stmt is not None and infsets_stmt.values:
        n = infsets_stmt.get(0)
        if isinstance(n, int) and n > 0:
            rep.n_species = n
            rep.gas = GasModel.MIXTURE
            for child in _iter_top_seq_children(inp):
                title = " ".join(child.values_raw[2:]) if len(child.values_raw) > 2 else ""
                m = re.match(r"species_(\d+)_Mwt1_(\w+)", title)
                if m:
                    idx, name = int(m.group(1)), m.group(2)
                    mwt = _lookup_mwt(inp, idx)
                    if idx <= len(rep.species):
                        rep.species.append(SpeciesEntry(
                            name=name, mwts=[mwt] if mwt else [],
                            has_sutherland=False, has_cp=False,
                        ))
    else:
        rep.gas = GasModel.PERFECT_GAS if rep.has_gasnam else GasModel.UNKNOWN

    return rep
```

### 5.2 4 个湍流模型公式(目标 G3)

**重要前提:`physics.ntrbst` 不可靠**(实测 6 个算例全 = 11,湍流模型实际由顶层 `seq.# 1 #vals 31 title eqnset_define` 块控制)。本节为 4 个湍流模型写独立公式 preset。

#### 5.2.1 基类 `TurbulencePresetBase`

```python
import math
from abc import ABC, abstractmethod


@dataclass
class TurbulencePresetBase(ABC):
    """湍流初始化 preset 基类。

    子类必须实现:
    - family: TurbulenceModel(1-方程 / 2-方程)
    - compute(I, L, U_ref) -> Dict[str, float]: 算湍流参数

    共同约束:
    - I ∈ [0, 1]
    - L > 0
    - U_ref > 0
    """
    I: float                         # 湍流强度(0.01 = 1%)
    L: float                         # 特征长度 [m]
    U_ref: float = 1.0               # 参考速度 [m/s](通常 = refvel / aero_u)
    Cmu: float = 0.09                # SST/k-ε 共用默认系数
    # guiopts 字段键(子类可覆盖)
    turbi_lev_key: str = "turbi_lev" # 写"特征量"(k / ν̃)
    turbi_len_key: str = "turbi_len" # 写"长度尺度"
    turbi_tlev_key: str = "turbi_tlev"  # 写"特征量"无量纲比例(可选)
    turbi_tlen_key: str = "turbi_tlen"  # 写"长度"无量纲比例(可选)

    def _validate(self) -> None:
        if not (0 <= self.I <= 1):
            raise ValueError(f"turbulence intensity I ∈ [0,1], got {self.I!r}")
        if self.L <= 0:
            raise ValueError(f"length scale L must be > 0, got {self.L!r}")
        if self.U_ref <= 0:
            raise ValueError(f"reference velocity U_ref must be > 0, got {self.U_ref!r}")

    @abstractmethod
    def family(self) -> TurbulenceModel:
        """返回本 preset 对应的湍流模型。"""
        raise NotImplementedError

    @abstractmethod
    def compute(self) -> Dict[str, float]:
        """算湍流参数。返回字段名 → 浮点值(供 apply 写 guiopts)。"""
        raise NotImplementedError

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        """写入 guiopts 块;返回 applied 字典供 undo / manifest。"""
        self._validate()
        gb = inp.get_block("guiopts")
        if gb is None:
            raise ValueError("template has no `guiopts` block; cannot apply turbulence preset")
        values = self.compute()
        applied: Dict[str, Any] = {}
        for src_key, dst_key in values.items():
            v = dst_key and values[src_key]  # src_key 是 guiopts 字段名,dst_key 在 compute 中已是字段名
            # 简化:apply 只用 src_key 写;compute 返回的 dict key 已经是 guiopts 字段名
            if gb.set(src_key, v):
                applied[f"guiopts.{src_key}"] = v
            else:
                gb.append(src_key, v)
                applied[f"guiopts.{src_key}"] = v
        return applied
```

#### 5.2.2 4 个子类

```python
@dataclass
class SSTKOmegaPreset(TurbulencePresetBase):
    """SST k-ω(Menter 1994)初始化。给 I, L, U_ref 算 k, ω。"""
    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.SST_KW

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2  # 湍动能 [m²/s²]
        omega = math.sqrt(k) / (self.Cmu ** 0.25 * self.L)  # Wilcox 2006 Eq.2.49
        return {
            "turbi_lev": k,                   # 写 k
            "turbi_tlev": k / (0.5 * self.U_ref**2),  # k/U²(无量纲)
            "turbi_len": self.L,
            "turbi_tlen": self.L,
        }


@dataclass
class RealizableKEpsilonPreset(TurbulencePresetBase):
    """Realizable k-ε(Shih et al. 1995)初始化。给 I, L, U_ref 算 k, ε。"""
    Cmu: float = 0.09          # Realizable k-ε 的 Cμ
    C2: float = 1.9             # 模型常数 C2(Shih 1995)
    sigma_eps: float = 1.2       # σ_ε
    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.REALIZABLE_KEPSILON

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2  # 湍动能 [m²/s²]
        l = self.L                              # 湍流长度尺度
        eps = self.Cmu ** (3.0/4.0) * k ** (3.0/2.0) / l  # ε = Cμ^3/4 k^3/2 / l
        return {
            "turbi_lev": k,                   # 写 k
            "turbi_tlev": k / (0.5 * self.U_ref**2),
            "turbi_len": self.L,
            "turbi_tlen": eps,                # ← Realizable k-ε: tlen 存 ε 而非长度
        }


@dataclass
class SpalartAllmarasPreset(TurbulencePresetBase):
    """SA(Spalart-Allmaras 1994)初始化。给 I, L, U_ref 算 ν̃。"""
    Cb1: float = 0.1355         # SA 模型常数
    Cv1: float = 7.1
    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.SPALART_ALLMARAS

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2
        # SA 用 ν̃ 存: ν̃ ~ sqrt(k) * L (简单估计;更精确的公式 v0.9.1 用此近似即可)
        nu_tilde = math.sqrt(k) * self.L / 100.0  # 简化估计;实测尺度需要校准
        return {
            "turbi_lev": nu_tilde,            # ← SA: turbi_lev 存 ν̃ 而非 k
            "turbi_len": self.L,
        }


@dataclass
class GoldbergRTPreset(TurbulencePresetBase):
    """Goldberg Reynolds Transport 1-equation 模型初始化。"""
    @property
    def family(self) -> TurbulenceModel:
        return TurbulenceModel.GOLDBERG_RT

    def compute(self) -> Dict[str, float]:
        self._validate()
        k = 1.5 * (self.U_ref * self.I) ** 2
        nu_tilde = math.sqrt(k) * self.L / 100.0  # 简化;Goldberg 公式 v0.9.1 简化版
        return {
            "turbi_lev": nu_tilde,            # Goldberg 也是 1-方程,字段名同 SA
            "turbi_len": self.L,
        }
```

#### 5.2.3 工厂函数

```python
def make_turbulence_preset(model: TurbulenceModel, I: float, L: float, U_ref: float = 1.0) -> TurbulencePresetBase:
    """从检测到的 TurbulenceModel + 用户给定 I/L/U_ref 选对应 preset。"""
    factory = {
        TurbulenceModel.SST_KW: SSTKOmegaPreset,
        TurbulenceModel.REALIZABLE_KEPSILON: RealizableKEpsilonPreset,
        TurbulenceModel.SPALART_ALLMARAS: SpalartAllmarasPreset,
        TurbulenceModel.GOLDBERG_RT: GoldbergRTPreset,
    }
    if model not in factory:
        raise ValueError(
            f"no preset for {model.value}; v0.9.1 supports only 4 (SST/k-ε/SA/Goldberg)"
        )
    return factory[model](I=I, L=L, U_ref=U_ref)
```

#### 5.2.4 数值验证测试

| 预设 | 输入 (I, L, U_ref) | turbi_lev | turbi_tlen(若用) |
|---|---|---|---|
| SSTKOmega | (0.01, 0.01, 204) | k=6.241 | — |
| RealizableKEpsilon | (0.01, 0.01, 204) | k=6.241 | ε=0.09^0.75 × 6.241^1.5 / 0.01 = 3.82e3 |
| SpalartAllmaras | (0.01, 0.01, 204) | ν̃=0.499 | — |
| GoldbergRT | (0.01, 0.01, 204) | ν̃=0.499 | — |
| SSTKOmega | (0.05, 0.005, 100) | k=37.5 | — |

### 5.3 质量 ↔ 摩尔分率换算(目标 G4)

```python
@dataclass
class SpeciesPreset:
    """
    多组分物性 preset。
    给定 {species_name: fraction},mode ∈ {"mass","mole"},自动:
    1) 读 EquationSystemReport 拿每个 species 的 Mwt
    2) mass ↔ mole 互转
    3) 归一化(总和 → 1.0)
    4) 写入顶层 infsets 之后的 seq.# N values Y_1 ... Y_N
    """
    fractions: Dict[str, float]    # {"CO": 0.5, "O2": 0.5}
    mode: str = "mass"             # "mass" or "mole"
    tol: float = 1e-9

    def convert(self, rep: EquationSystemReport) -> Dict[str, float]:
        """归一化 + mass↔mole 换算。返回 {name: mass_fraction}"""
        if not rep.species:
            raise SpeciesNotFoundError("no species found in InpFile; cannot apply")
        mwts = {s.name: s.mwts[0] for s in rep.species if s.mwts}
        unknown = set(self.fractions) - set(mwts)
        if unknown:
            raise SpeciesNotFoundError(
                f"species {sorted(unknown)!r} not declared in InpFile; "
                f"known: {sorted(mwts)!r}"
            )
        total = sum(self.fractions.values())
        if total <= 0:
            raise ValueError(f"fractions sum to {total}, must be > 0")
        norm = {k: v / total for k, v in self.fractions.items()}
        if self.mode == "mass":
            mass = norm
            # mass → mole: X_i = (Y_i / M_i) / Σ(Y_j / M_j)
            denom = sum(mass[n] / mwts[n] for n in mass)
            return mass
        elif self.mode == "mole":
            mole = norm
            # mole → mass: Y_i = X_i * M_i / Σ(X_j * M_j)
            denom = sum(mole[n] * mwts[n] for n in mole)
            mass = {n: mole[n] * mwts[n] / denom for n in mole}
            return mass
        else:
            raise ValueError(f"mode must be 'mass' or 'mole', got {self.mode!r}")

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        rep = detect_equations(inp)
        if rep.gas != GasModel.MIXTURE:
            raise GasModelError(
                f"inp is not a multi-species mixture (gas={rep.gas.value}); "
                f"SpeciesPreset requires infsets + seq.# N values structure"
            )
        mass = self.convert(rep)
        applied: Dict[str, Any] = {}
        n = rep.n_species
        existing = _find_mass_fractions_stmt(inp, n)
        if existing is not None:
            new_vals = [str(mass[s.name]) for s in rep.species[:n]]
            existing.values = [Value(raw=v) for v in new_vals]
            applied["top_stmts"] = new_vals
        else:
            from .model import Stmt, Value
            line_no = (inp.top_stmts[-1].line + 1) if inp.top_stmts else 1
            seq_stmt = Stmt(keyword=f"seq.# {n+1}", values=[Value(raw=str(n+1))], line=line_no)
            values_stmt = Stmt(keyword="values", values=[Value(raw=str(mass[s.name])) for s in rep.species[:n]], line=line_no + 1)
            inp.top_stmts.append(seq_stmt)
            inp.top_stmts.append(values_stmt)
            applied["top_stmts"] = "appended"
        return applied
```

**公式单元测试:**

| 输入 (mode=mole) | 期望 mass |
|---|---|
| CO=0.5, O2=0.5 (Mwt:28.01,32) | CO: 0.5×28/(0.5×28+0.5×32)=14/30=0.4667; O2: 16/30=0.5333 |
| CO=1.0, O2=0, C=0, O=0 | CO: 1.0(全 CO) |

### 5.4 2 温度非平衡(目标 G2)

**`tnoneq_numeqns` 字段语义(用户 2026-06-11 确认):**

| 值 | 物理含义 | 非平动温度方程数 | 总温度变量 |
|---|---|---|---|
| `0` | 完美气体(无非平衡) | 0 | T(单 T) |
| `1` | **2-温度非平衡**(T_trans + T_vib) | 1(振动) | **T_trans + T_vib** |
| `2` | 3-温度非平衡(T_trans + T_vib + T_elec) | 2(振动+电子) | 3 个(超 v0.9.1 scope) |

**字段名约定(从 CFD++ 习惯推断,未官方确认):**

| 字段 | 含义 | 备注 |
|---|---|---|
| `physics.tnoneq_numeqns` | **非平衡温度方程数**(非总温度数) | **`=1` 启用 2T 模型**(非 `=2`!) |
| `physics.reftem` | 平动温度(T_trans) | 1T/2T 都用 |
| `physics.vibtem` | 振动温度(T_vib) | 仅 2T;v0.9.1 拟写,字段名为约定(若用户用 `T_vib` / `vib_temp` 留 v0.10 适配) |

**关键认识:** `tnoneq_numeqns` 字面意思 = "thermal non-equilibrium **number of equations**",即"非平动温度的能量方程数"。`=1` 表示 1 个额外的能量方程(振动),所以总温度数 = 1(平动)+ 1(振动)= 2。

**典型 2T 算例 physics 块尾段:**

```ini
physics begin
  ...
  tnoneq_numeqns 1      # ← 关键:1 = 启用 2T 模型(1 个非平动温度方程)
  ...
  reftem 288.15          # ← T_trans (平动温度)
  vibtem 288.15          # ← T_vib (振动温度,v0.9.1 写入)
  ...
physics end
```

```python
@dataclass
class TwoTemperaturePreset:
    """
    2 温度(2T)非平衡能量模型联动 preset。
    强约束:T_trans(平动温度)和 T_vib(振动温度)必须**同时**给。
    """
    T_trans: Optional[float] = None       # 平动温度 [K]
    T_vib: Optional[float] = None         # 振动温度 [K]
    set_numeqns: bool = True              # 是否自动设 tnoneq_numeqns=1(启用 2T)

    def apply(self, inp: InpFile) -> Dict[str, Any]:
        rep = detect_equations(inp)
        if self.T_trans is None or self.T_vib is None:
            raise TwoTemperatureError(
                "2T model requires BOTH T_trans and T_vib. "
                f"got T_trans={self.T_trans!r}, T_vib={self.T_vib!r}"
            )
        if self.T_trans <= 0 or self.T_vib <= 0:
            raise ValueError(
                f"temperatures must be > 0 K (got T_trans={self.T_trans}, T_vib={self.T_vib})"
            )
        pb = inp.get_block("physics")
        if pb is None:
            raise ValueError("template has no `physics` block; cannot apply 2T preset")
        applied: Dict[str, Any] = {}
        if self.set_numeqns:
            # 启用 2T 模型:tnoneq_numeqns = 1(1 个非平动温度方程,即振动)
            if pb.set("tnoneq_numeqns", 1):
                applied["physics.tnoneq_numeqns"] = 1
            else:
                pb.append("tnoneq_numeqns", 1)
                applied["physics.tnoneq_numeqns"] = 1
        # 平动温度 / 振动温度字段名:CFD++ 习惯 reftem (平动), v0.9.1 新加 vibtem
        if pb.set("reftem", self.T_trans):
            applied["physics.reftem"] = self.T_trans
        else:
            pb.append("reftem", self.T_trans)
            applied["physics.reftem"] = self.T_trans
        if pb.set("vibtem", self.T_vib):
            applied["physics.vibtem"] = self.T_vib
        else:
            pb.append("vibtem", self.T_vib)
            applied["physics.vibtem"] = self.T_vib
        return applied
```

**注意:** "vibtem" 字段名是**约定** —— v0.9.1 引入。若用户 inp 已用其他字段名(如 `vib_temp`),`detect_equations` 扩展时可识别并支持(留给 v0.10+)。

### 5.5 Wizard / REPL / Sweep 集成

#### 5.5.1 WizardModifyFile 加检测步骤

```python
# inp_tool/wizard.py — WizardModifyFile 5 步
steps = [
    "step_1_select_file",
    "step_2_detect",             # 新增
    "step_2_select_fields",      # 字段选择(原 step_2)
    "step_3_enter_values",       # (原 step_3)
    "step_4_preview",
    "step_5_output",
]

def step_2_detect(self, data: dict):
    from .equations import detect_equations
    from .parser import parse_file
    inp = parse_file(data["file"])
    rep = detect_equations(inp)
    is_zh = get_lang() == "zh"
    _print("  ── 自动检测 ──")
    _print(f"  {rep.summary_zh()}")
    for note in rep.notes:
        _print(f"  ⚠ {note}")
    recommended = rep.recommended_fields()
    if recommended:
        _print(f"  推荐字段: {recommended}")
    return ("step_2_select_fields", {"_detect_report": rep})
```

#### 5.5.2 WizardSweep 加 preset 步骤

```python
# inp_tool/wizard.py — WizardSweep 7 步
steps = [
    "step_1_source_dir",
    "step_2_output",
    "step_3_mode",
    "step_4_params",
    "step_4a_presets",         # 新增:turb / 2T / species 可选启用
    "step_5_naming",
    "step_5a_pbs",
    "step_6_preview",
]

def step_4a_presets(self, data: dict):
    is_zh = get_lang() == "zh"
    if is_zh:
        choices = [
            ("1", "湍流 SST k-ω (I, L → k, ω)", "Turbulence"),
            ("2", "2 温度非平衡 (T_trans, T_vib)", "Two-Temperature"),
            ("3", "多组分物性 (mass/mole)", "Species"),
            ("0", "不启用额外 preset", "(none)"),
        ]
    else:
        choices = [
            ("1", "Turbulence SST k-ω (I, L → k, ω)", "Turbulence"),
            ("2", "Two-Temperature (T_trans, T_vib)", "Two-Temperature"),
            ("3", "Multi-species (mass/mole)", "Species"),
            ("0", "no extra preset", "(none)"),
        ]
    key = menu("  选择额外 preset:", choices, default="0")
    if key == "0":
        return ("step_5_naming", {})
    return ("step_5_naming", {"presets_enabled": [key]})
```

#### 5.5.3 REPL 新增 3 个命令

```python
# inp_tool/repl.py
def do_turb(self, arg):
    """turb I=0.01 L=0.01 [-b BLOCK] — SST k-ω 反算 + 写 guiopts"""
    from .equations import TurbulenceKOmegaPreset
    params = {}
    for tok in arg.split():
        if '=' not in tok:
            self._err(f"turb: expected KEY=VALUE, got {tok!r}")
            return
        k, _, v = tok.partition('=')
        try:
            params[k.strip()] = float(v)
        except ValueError:
            self._err(f"turb: {k} must be a number, got {v!r}")
            return
    if 'I' not in params or 'L' not in params:
        self._err("turb: requires I=<intensity> L=<length>")
        return
    U_ref = params.get('U_ref', None)
    if U_ref is None:
        from .parser import parse_file
        inp = parse_file(str(self.session.files[self.session.current].path))
        refvel = inp.get('physics', 'refvel')
        aero_u = inp.get('guiopts', 'aero_u')
        U_ref = refvel or aero_u or 1.0
    preset = TurbulenceKOmegaPreset(I=params['I'], L=params['L'], U_ref=U_ref)
    # apply + undo 注册
    ...

def do_species(self, arg):
    """species CO=0.5 O2=0.5 [mode=mole|mass] — 多组分物性 preset"""
    from .equations import SpeciesPreset
    ...

def do_2t(self, arg):
    """2t T=<trans> Tvib=<vib> — 2 温度非平衡 preset"""
    from .equations import TwoTemperaturePreset
    ...
```

#### 5.5.4 Sweep 集成(目标 G7)

```python
# inp_tool/sweep.py — CaseSweep 新增 3 个字段
@dataclass
class CaseSweep:
    # ... 现有字段 ...
    turbulence: Optional[Any] = None       # 实际类型:Optional["TurbulenceKOmegaPreset"]
    two_temperature: Optional[Any] = None  # 实际类型:Optional["TwoTemperaturePreset"]
    species: Optional[Any] = None          # 实际类型:Optional["SpeciesPreset"]
```

```python
# sweep.py::generate() 末尾,在 freestream 之后调用
applied: Dict[str, Any] = {}
if sweep.freestream is not None:
    applied.update(sweep.freestream.apply(inp, params))
if sweep.turbulence is not None:
    applied.update(sweep.turbulence.apply(inp))
if sweep.two_temperature is not None:
    applied.update(sweep.two_temperature.apply(inp))
if sweep.species is not None:
    applied.update(sweep.species.apply(inp))
_apply_overrides(inp, sweep.overrides)
```

**Sweep YAML 示例:**

```yaml
template: reference/suanli/mcfd.inp
output_dir: sweep_cases
sweeps:
  alpha: [0, 5, 10]
  mach: [0.6, 0.8]
freestream: {enabled: true}
turbulence:    # v0.9.1 新
  enabled: true
  I: 0.01
  L: 0.01
species:       # v0.9.1 新
  enabled: true
  mode: mole
  fractions: {CO: 0.5, O2: 0.5}
naming: "case_a{alpha}_m{mach}"
```

### 5.6 数据流总图

```
mcfd.inp ──parser──▶ InpFile ──┬──▶ detect_equations() → EquationSystemReport
                                │       │
                                │       ├─▶ WizardModifyFile.step_2_detect(报告给用户)
                                │       │
                                │       └─▶ TurbulenceKOmegaPreset.compute()  ← I, L
                                │           TwoTemperaturePreset.apply()    ← T, Tvib
                                │           SpeciesPreset.convert()         ← mass/mole
                                │               │
                                │               ▼
                                │           InpFile  (修改后)
                                │               │
                                │               ├─▶ write_preserve() → .inp 文件
                                │               │
                                │               └─▶ undo / manifest 记录
                                │
                                └─▶ CaseSweep.generate() 在 freestream 后顺序应用 3 个 preset
```

---

## 6. 实施阶段(8 阶段)

> **建议拆 PR:**
> - **PR A**(阶段 1+2):数据模型 + 检测器 + 公式 + 单元测试
> - **PR B**(阶段 3+4):3 个 Preset + REPL 命令 + 简单 wizard 检测步骤
> - **PR C**(阶段 5+6):wizard 完整集成 + sweep YAML/JSON 集成 + CLI `--detect`
> - **PR D**(阶段 7+8):文档 + 真实算例 smoke + 归档

### 阶段 0 — 开工前
- [ ] 0.1 写本计划(本文件)
- [ ] 0.2 分支:`git switch -c feat/equation-aware-config`
- [ ] 0.3 基线:`pytest` 全绿(449 passed, 6 skipped)
- [ ] 0.4 在 `docs/plans/2026-06-10_equation-aware-config.md` 落盘

### 阶段 1 — 数据模型 + 检测器(零行为变化)
- [ ] 1.1 新建 `inp_tool/inp_tool/equations.py`
- [ ] 1.2 RED:`test_equations.py::test_detect_2T_suanli` — 扫 suanli → energy=TWO_TEMP(因 `tnoneq_numeqns=1` 启用 2T),turbulence=NONE(ntrbst 不在 suanli 范围)
- [ ] 1.3 GREEN:`detect_equations()` 骨架
- [ ] 1.4 RED:检测 SST k-ω(`seq.# 1` 第 1 行 `values 101 1 1 2 3` → 家族=2, 码=3)
- [ ] 1.5 GREEN:补充 `_MAP_TURBULENCE = {(0,1):LAMINAR, (1,2):GOLDBERG_RT, (1,4):SA, (2,3):SST_KW, (2,2):REALIZABLE_KEPSILON}` 映射表
- [ ] 1.6 RED:检测多组分(`seq.# 1` 第 2 行 `values 1 ...` → gas=REAL_GAS)
- [ ] 1.7 GREEN:`_find_top_stmt_by_title()` + `_collect_following_values()` 工具函数
- [ ] 1.6 RED:检测多组分(infsets=55, 5 species)
- [ ] 1.7 GREEN:`_iter_top_seq_children()` 解析 species_N_Mwt1_NAME
- [ ] 1.8 RED:`EquationSystemReport.recommended_fields()` 返回字段集
- [ ] 1.9 GREEN:字段推荐逻辑(2T → T+Tvib, SST → k+ω, MIXTURE → mass fracs)
- [ ] 1.10 `__init__.py` 导出 6 个 public symbol

### 阶段 2 — SST k-ω preset + 公式
- [ ] 2.1 RED:`test_equations.py::test_sst_komega_formula` — SSTKOmegaPreset(I=0.01, L=0.01, U=204) → k=6.241
- [ ] 2.2 GREEN:`SSTKOmegaPreset.compute()`
- [ ] 2.3 RED:`test_realizable_kepsilon_formula` — RealizableKEpsilonPreset → ε=0.09^0.75 · k^1.5 / L
- [ ] 2.4 GREEN:`RealizableKEpsilonPreset.compute()`
- [ ] 2.5 RED:`test_sa_formula` — SpalartAllmarasPreset(I=0.01, L=0.01) → ν̃ (近似公式)
- [ ] 2.6 GREEN:`SpalartAllmarasPreset.compute()`
- [ ] 2.7 RED:`test_goldberg_formula` — GoldbergRTPreset → ν̃ (近似公式)
- [ ] 2.8 GREEN:`GoldbergRTPreset.compute()`
- [ ] 2.9 RED:`test_apply_sst` — SSTKOmegaPreset.apply(inp) → `guiopts.turbi_lev` 写入
- [ ] 2.10 GREEN:`TurbulencePresetBase.apply()` 公共实现
- [ ] 2.11 RED:边界 — I=0 → k=0; L=0 → 报错;I>1 → 报错
- [ ] 2.12 GREEN:`if self.I < 0 or self.I > 1: raise ValueError`
- [ ] 2.13 RED:`turbi_lev` 缺失时 append(不 set)
- [ ] 2.14 GREEN:`gb.set` False → `gb.append`
- [ ] 2.15 RED:`test_factory_dispatch` — `make_turbulence_preset(SST_KW, ...)` 返回 `SSTKOmegaPreset`
- [ ] 2.16 GREEN:`make_turbulence_preset()` 工厂
- [ ] 2.17 RED:从 6 个 compare/ 算例读 `seq.# 1` 反推 TurbulenceModel
- [ ] 2.18 GREEN:`_MAP_TURBULENCE` 映射 + 测试 6 个算例 → 期望 4 个湍流模型(SA/Goldberg/SST/k-ε)+ 2 个层流(理想/真实)

### 阶段 3 — 2T preset + Species preset
- [ ] 3.1 RED:`test_two_temp_missing_Tvib_raises`
- [ ] 3.2 GREEN:`TwoTemperaturePreset.apply()` 强校验
- [ ] 3.3 RED:`test_two_temp_writes_both` — 验证 reftem + vibtem 都写
- [ ] 3.4 GREEN:`apply()` 写 2 个字段
- [ ] 3.5 RED:`test_species mass_to_mole` — CO=0.5, O2=0.5 (mole) → mass 0.467, 0.533
- [ ] 3.6 GREEN:`SpeciesPreset.convert()`
- [ ] 3.7 RED:`test_species_unknown_species_raises`
- [ ] 3.8 GREEN:unknown species 检测
- [ ] 3.9 RED:`test_species_apply_updates_existing` — 找到现有 mass fracs 行并 update
- [ ] 3.10 GREEN:`_find_mass_fractions_stmt()` 工具
- [ ] 3.11 RED:`test_species_apply_appends_when_missing`
- [ ] 3.12 GREEN:append 新 seq.# + values 行
- [ ] 3.13 RED:归一化 — 输入 sum=0.6, 自动 sum→1
- [ ] 3.14 GREEN:`total = sum(...)`,`norm = .../ total`

### 阶段 4 — REPL 3 个语义化命令
- [ ] 4.1 RED:`test_repl_turb.py::test_do_turb_basic`
- [ ] 4.2 GREEN:`do_turb` 骨架(解析 KEY=VALUE)
- [ ] 4.3 RED:`test_do_turb_undo` — undo 还原
- [ ] 4.4 GREEN:`session.undo.push(UndoEntry(...))`
- [ ] 4.5 RED:`test_do_species_mole`
- [ ] 4.6 GREEN:`do_species`
- [ ] 4.7 RED:`test_do_2t_missing_Tvib_errors`
- [ ] 4.8 GREEN:`do_2t`
- [ ] 4.9 RED:`test_do_turb_undo_push` — 必须支持 undo
- [ ] 4.10 GREEN:确认 undo 注册路径

### 阶段 5 — WizardModifyFile / WizardSweep 集成
- [ ] 5.1 RED:`test_wizard_modify_detect.py::test_detect_step_runs`
- [ ] 5.2 GREEN:`WizardModifyFile.step_2_detect`
- [ ] 5.3 RED:`test_recommended_fields_appear_in_select_fields` — 2T 算例的 wizard 必须显示 T+Tvib
- [ ] 5.4 GREEN:`step_2_select_fields` 接受 `_detect_report` 自动加入 recommended
- [ ] 5.5 RED:`test_wizard_sweep_presets_step` — `wizard sweep` 加 presets 步骤
- [ ] 5.6 GREEN:`WizardSweep.step_4a_presets`
- [ ] 5.7 RED:CLI `inp-tool info mcfd.inp --detect` 输出报告
- [ ] 5.8 GREEN:`cmd_info` 加 `--detect` flag

### 阶段 6 — Sweep 集成
- [ ] 6.1 RED:`test_sweep_presets.py::test_turbulence_in_sweep` — sweep 跑 4 cases,每个 turbi_lev 都被覆盖
- [ ] 6.2 GREEN:`CaseSweep.turbulence` 字段 + `from_dict` 解析
- [ ] 6.3 RED:`test_sweep_two_temp` — sweep 2T preset
- [ ] 6.4 GREEN:`CaseSweep.two_temperature`
- [ ] 6.5 RED:`test_sweep_species` — sweep species preset
- [ ] 6.6 GREEN:`CaseSweep.species`
- [ ] 6.7 RED:`test_sweep_all_presets_together` — freestream + turbulence + 2t + species 共存
- [ ] 6.8 GREEN:`generate()` 末尾顺序应用 4 个 preset
- [ ] 6.9 RED:`test_sweep_backward` — 不给新字段时行为不变
- [ ] 6.10 GREEN:确认 `turbulence=None` 时不调 `apply()`

### 阶段 7 — 真实算例 smoke + i18n
- [ ] 7.1 RED:`test_sweep_presets.py::test_suanli_real_case` — 跑 `reference/suanli` 4-case sweep,断言 turbi_lev / species 全 4 个 case 都被覆盖
- [ ] 7.2 GREEN:端到端 smoke
- [ ] 7.3 i18n 加 30+ keys(turb、2t、species 提示信息)
- [ ] 7.4 覆盖率 ≥ 80%

### 阶段 8 — 文档与收尾
- [ ] 8.1 `docs/technical/13-core-modules.md` 加 §7 equations 模块
- [ ] 8.2 `docs/user-manual/15-turbulence-2t-species.md` 新建
- [ ] 8.3 `CHANGELOG.md` v0.9.1 段
- [ ] 8.4 `simplify` + `code-review` agent
- [ ] 8.5 commit + push + PR
- [ ] 8.6 监控 CI + merge + 清理分支
- [ ] 8.7 归档本计划 → `docs/technical/18-equation-aware-config.md`,**删除** `docs/plans/` 版
- [ ] 8.8 tag `v0.9.1`(`chore: bump version`)

---

## 7. 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| **HIGH** | **2T 字段名约定风险**:CFD++ 各版本可能用 `vibtem` / `T_vib` / `vib_temp` 等不同字段名;写错字段名不报错但求解器忽略 | v0.9.1 只在用户显式选 2T preset 时写;`detect_equations` 不假设字段存在;文档明确说"v0.9.1 假设 CFD++ 字段名 `vibtem`";若用户的 inp 无此字段,`apply()` append(无副作用) |
| **HIGH** | **湍流模型字段映射假设风险**:`turbi_lev ↔ k(2-方程)` / `ν̃(1-方程)`、`turbi_tlev ↔ k/U²` / `ε(Realizable k-ε)` 是 CFD++ 习惯,但**没看到官方 spec**;不同版本/不同湍流模型可能不同 | 阶段 2 配数值断言(每个公式独立 test) + 字段映射做成 dataclass 字段,用户可覆盖;`docs/technical/18-` 显式标"约定,需用户确认 CFD++ 版本" |
| **MEDIUM** | **多组分物性 inpset 结构复杂**:顶层 `infsets` 后续 seq.# 顺序不一定对(`species_1_Mwt1_CO` 紧跟 `species_1_Sutherland6`...);mass fracs 行可能插入位置不对会破坏 CFD++ 解析 | v0.9.1 只做 append(不重排);`_find_mass_fractions_stmt()` 用 title 关键字匹配;`test_suanli_real_case` 必须包含 round-trip 读出 mass fracs 正确性 |
| **MEDIUM** | **detect_equations 对"未知"情形可能漏报**:如 `ntrbst=99` 在 CFD++ 是某种新模型,detector 返回 `UNKNOWN` 不会告知用户 | `EquationSystemReport.notes` 字段收集"未识别模型"警告;wizard step_2_detect 显示警告 |
| **MEDIUM** | **REPL undo 路径有 bug 风险**:`do_turb` 写 4 个字段,undo 一次只能回滚一组;若用户连续改两次,可能错乱 | 仿照 `do_aero` 用 `UndoEntry` 一次 push;测试覆盖 `test_do_turb_undo_push` |
| **LOW** | **公式精度**:k=1.5×(U·I)² 在 I=0.001 极小值时仍为正,但浮点下溢风险 | 用 `>= 0` 校验,极小时用 `max(0, k)` |
| **LOW** | **i18n 漏 key** | i18n 加默认值兜底(已有 `t()` 行为);新增 30+ keys 走中英对照 |
| **LOW** | **PR 太大** | 拆 4 个 PR(A 数据模型 / B Preset+REPL / C wizard+sweep / D 文档+归档) |

---

## 8. 兼容性

- **API:** `CaseSweep` 新增 3 个字段(均 Optional,默认 None)→ 现有 YAML/JSON config 零修改
- **CLI:** `inp-tool info mcfd.inp`(无 `--detect`)与 v0.9.0 完全一致
- **REPL:** `do_turb` / `do_species` / `do_2t` 是**新增**命令,不改变现有 `set` / `get` / `aero` 行为
- **Wizard:** `WizardModifyFile` 4 → 5 步(插入 step_2_detect 自动步骤,用户键入 1 字符即可)→ 向后兼容
- **Wizard:** `WizardSweep` 6 → 7 步(插入 step_4a_presets,默认选 "0"(不启用),空回车跳过)
- **测试:** 现有 449 + 6 skipped 零修改,新增 50+ 测试
- **覆盖率:** ≥ 80%

---

## 9. 验收

- [ ] 现有 449 + 6 skipped 测试零修改全绿
- [ ] 新增 50+ 测试全绿(含 6 个 compare/ 算例的 `_MAP_TURBULENCE` 反向测试)
- [ ] 覆盖率 ≥ 80%
- [ ] **`reference/inp_example/compare/` 6 个 mcfd.inp** 经 `detect_equations()` 处理后,每文件:
  - 湍流模型:LAMINAR / GOLDBERG_RT / SA / SST_KW / REALIZABLE_KEPSILON(各 1-2 个匹配)
  - 气体类型:PERFECT_GAS / MIXTURE (REAL_GAS) 各 1 个
  - 公式 round-trip:`SSTKOmegaPreset.apply` 后 `turbi_lev` 值与手算 k 误差 < 1e-6
- [ ] `reference/suanli` 跑 4-case sweep(含 turbulence + species preset),每个子目录 `mcfd.inp` round-trip 后:
  - `turbi_lev` 值与手算 k 误差 < 1e-6
  - 顶层 mass fracs 行总和 1.0 ± 1e-9
- [ ] `inp-tool info mcfd.inp --detect` 输出:能量 / 湍流家族+码 / 气体 / species 数
- [ ] `inp> turb I=0.01 L=0.01` 改 1 个文件,值符合 SST 公式 + 支持 undo
- [ ] `wizard modify-file` 改 2T 算例,自动出现"温度 + 振动温度"两个 prompt(不报 TypeError)
- [ ] `wizard sweep` 加湍流/2T/species preset 步骤
- [ ] CHANGELOG v0.9.1 段
- [ ] PR merge 到 main + 打 tag

---

## 10. 不在本次范围(Out of Scope → v0.10+)

- ❌ **3 温度(3T)非平衡模型** —— tnoneq_numeqns=2 留 v0.10
- ❌ **化学反应动力学参数**(reaction rate 系数) —— 留给 v0.10
- ❌ **3-方程湍流模型**(k-eps-Rt, k-eps-fmu 等家族码 3 系列) —— 留给 v0.10
- ❌ **LES / DES / DDES / IDDES** —— 留给 v0.10
- ❌ **多组分物性文件生成**(C.dat / CO.dat 等 .dat 文件) —— 留给 v0.10
- ❌ **species 物性(sutherland、cp-coef、HF、GF)回写** —— 留给 v0.10
- ❌ **CFD++ GUI 集成** —— 另一项目 cfd-gui
- ❌ **自动推断湍流强度 / 长度**(如外流经验公式) —— 留给 expert user overrides
- ❌ **不同 CFD++ 版本的 2T 字段名兼容**(vibtem / T_vib / vib_temp) —— 只支持约定的 vibtem,其他留 v0.10
- ❌ **不同 CFD++ 版本的湍流模型码映射** —— v0.9.1 用 compare/ 实测 4 码,其他码(如 Goldberg 1/3/5)留 v0.10
