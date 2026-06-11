"""
v0.9.0:方程系统感知的 mcfd.inp 配置 — equations 模块测试

测试目标:
- detect_equations(inp) 读 tnoneq_numeqns / seq.# 1 / gasnam 推断:
  - 能量模型(NONE / TWO_TEMP / THREE_TEMP)
  - 湍流模型(LAMINAR / GOLDBERG_RT / SA / SST_KW / REALIZABLE_KEPSILON)
  - 气体类型(PERFECT_GAS / MIXTURE)
- TurbulencePresetBase 4 子类公式正确性
- SpeciesPreset mass↔mole 互转
- TwoTemperaturePreset 强校验 + 联动写 3 字段
"""
from __future__ import annotations
import math
import pytest
from pathlib import Path

from inp_tool.equations import (
    detect_equations,
    EnergyModel,
    TurbulenceModel,
    GasModel,
    SSTKOmegaPreset,
    RealizableKEpsilonPreset,
    SpalartAllmarasPreset,
    GoldbergRTPreset,
    make_turbulence_preset,
    TwoTemperaturePreset,
    TwoTemperatureError,
    SpeciesPreset,
    SpeciesNotFoundError,
    GasModelError,
)
from inp_tool.parser import parse, parse_file
from inp_tool.sweep import CaseSweep


# ======================================================================
# 工具函数
# ======================================================================


def _make_inp(physics_lines, top_stmts_lines=None):
    """构造一个最小 InpFile 用于测试:只有 physics 块 + 可选顶层语句。"""
    text = "physics begin\n"
    for line in physics_lines:
        text += f"  {line}\n"
    text += "physics end\n"
    if top_stmts_lines:
        for line in top_stmts_lines:
            text += line + "\n"
    return parse(text, path="<test>")


# ======================================================================
# 阶段 1:detect_equations 单元测试
# ======================================================================


class TestDetectEnergy:
    """tnoneq_numeqns 字段 → EnergyModel 映射"""

    def test_tnoneq_0_means_perfect_gas(self):
        inp = _make_inp(["tnoneq_numeqns 0"])
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.NONE

    def test_tnoneq_1_means_2T_model(self):
        """用户 2026-06-11 确认:tnoneq_numeqns=1 → 2-温度(1 个非平动温度方程)"""
        inp = _make_inp(["tnoneq_numeqns 1"])
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.TWO_TEMP

    def test_tnoneq_2_means_3T_model(self):
        """tnoneq_numeqns=2 → 3-温度(2 个非平动温度方程),v0.10+ scope"""
        inp = _make_inp(["tnoneq_numeqns 2"])
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.THREE_TEMP

    def test_missing_tnoneq_is_unknown(self):
        inp = _make_inp(["ifrnue 1"])
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.UNKNOWN

    def test_unexpected_tnoneq_logs_note(self):
        inp = _make_inp(["tnoneq_numeqns 99"])
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.UNKNOWN
        assert any("99" in n for n in rep.notes)


class TestDetectTurbulence:
    """seq.# 1 第 1 行 values 101 1 1 X Y → TurbulenceModel"""

    def test_laminar_eqset_0_1(self):
        """0 家族, 码 1 = 层流(实测 compare/ 2 个层流算例)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 0 0 1 1 1",
            "values 0 5 5 0 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.LAMINAR
        assert rep.ntrbst_family == 0
        assert rep.ntrbst_code == 1

    def test_goldberg_rt_eqset_1_2(self):
        """1 家族, 码 2 = Goldberg RT(实测)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 1 2",
            "values 0 0 1 1 1",
            "values 0 6 5 1 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.GOLDBERG_RT

    def test_sa_eqset_1_4(self):
        """1 家族, 码 4 = SA(实测)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 1 4",
            "values 0 0 1 1 1",
            "values 0 6 5 1 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.SPALART_ALLMARAS

    def test_sst_kw_eqset_2_3(self):
        """2 家族, 码 3 = SST k-ω(实测)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 2 3",
            "values 0 0 1 1 1",
            "values 0 7 5 2 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.SST_KW

    def test_realizable_k_eps_eqset_2_2(self):
        """2 家族, 码 2 = Realizable k-ε(实测)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 2 2",
            "values 0 0 1 1 1",
            "values 0 7 5 2 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.REALIZABLE_KEPSILON

    def test_eqset_3_is_unknown(self):
        """3-方程家族(k-eps-Rt 等)留 v0.10+ scope → UNKNOWN"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 3 1",
            "values 0 0 1 1 1",
            "values 0 8 5 3 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.UNKNOWN
        assert any("3-方程" in n or "3 家族" in n for n in rep.notes)

    def test_unknown_eqset_1_99_logs_note(self):
        """1 家族, 码 99 = 未知湍流(新模型)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 1 99",
            "values 0 0 1 1 1",
            "values 0 6 5 1 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.UNKNOWN
        assert any("99" in n for n in rep.notes)


class TestDetectGas:
    """气体类型检测:v0.9.1 改用 eqnset_define 第 2 行 v6(实测发现 gasnam 全 = Air,不可用于判别)"""

    def test_gasnam_air_is_perfect_gas(self):
        """gasnam + eqnset_define v6=0 → PERFECT_GAS (v0.9.1 用 v6 判别)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 0 0 1 1 1",     # v6 = 0 → 理想气体
            "values 0 5 5 0 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp(["gasnam Air", "gasgam 1.4", "gasmwt 28.95"], top)
        rep = detect_equations(inp)
        assert rep.gas == GasModel.PERFECT_GAS
        assert rep.gas_code == 0
        assert rep.gasnam == "Air"      # 字段仍保留为参考

    def test_gasnam_without_eqnset_define_is_unknown(self):
        """v0.9.1:gasnam 不再判别 gas;无 eqnset_define → UNKNOWN"""
        inp = _make_inp(["gasnam Air", "gasgam 1.4"])
        rep = detect_equations(inp)
        assert rep.gas == GasModel.UNKNOWN          # gasnam 单独不再决定 gas
        assert rep.has_gasnam is True
        assert rep.gasnam == "Air"
        assert rep.gas_code is None

    def test_no_gasnam_unknown(self):
        inp = _make_inp(["ifrnue 1"])
        rep = detect_equations(inp)
        assert rep.gas == GasModel.UNKNOWN

    def test_infsets_55_fills_n_species_only(self):
        """v0.9.1:infsets 只是 settings 数,不再 → MIXTURE;只填 n_species 字段"""
        top = [
            "infsets 55",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 0 0 1 1 1",     # v6 = 0 → 理想气体
            "values 0 5 5 0 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.gas == GasModel.PERFECT_GAS      # v6=0 主判
        assert rep.gas_code == 0
        assert rep.n_species == 55                  # infsets 入 n_species

    def test_v6_1_is_real_gas(self):
        """v6=1 → REAL_GAS(可压缩真实气体)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 1 0 1 1 1",     # v6 = 1 → 真实气体
            "values 0 5 5 0 0",
            "values 0 0 0 0 0",
            "values 0 23 23 1 6",   # 实测真实气体的 v22/v23/v25
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.gas == GasModel.REAL_GAS
        assert rep.gas_code == 1

    def test_v6_11_is_multi_temp(self):
        """v6=11 + tnoneq_numeqns=1 → MULTI_TEMP(双温热非平衡)"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 11 0 1 1 1",    # v6 = 11 → 双温
            "values 0 6 5 0 0",
            "values 0 0 0 0 0",
            "values 0 25 25 10 10", # 实测双温的 v22/v23/v24/v25
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp(["tnoneq_numeqns 1"], top)
        rep = detect_equations(inp)
        assert rep.gas == GasModel.MULTI_TEMP
        assert rep.gas_code == 11
        assert rep.energy == EnergyModel.TWO_TEMP   # 一致性
        assert rep.notes == []                        # 无不一致告警

    def test_v6_unknown_logs_note(self):
        """v6 不在 {0,1,11} → UNKNOWN + note"""
        top = [
            "infsets 1",
            "seq.# 1 #vals 31 title eqnset_define",
            "values 101 1 1 0 1",
            "values 99 0 1 1 1",
            "values 0 5 5 0 0",
            "values 0 0 0 0 0",
            "values 0 5 5 1 1",
            "values 3 0 0 0 0",
            "values 0",
        ]
        inp = _make_inp([], top)
        rep = detect_equations(inp)
        assert rep.gas == GasModel.UNKNOWN
        assert rep.gas_code == 99
        assert any("99" in n for n in rep.notes)


class TestSuanliDetection:
    """完整 suanli 算例的 detect_equations 端到端测试"""

    SUANLI = Path("/home/fz/project/cfd--changer/reference/suanli/mcfd.inp")

    def test_suanli_tnoneq_1_means_2T(self):
        if not self.SUANLI.exists():
            pytest.skip("suanli not present")
        inp = parse_file(str(self.SUANLI))
        rep = detect_equations(inp)
        assert rep.energy == EnergyModel.TWO_TEMP

    def test_suanli_seq1_sst_kw(self):
        if not self.SUANLI.exists():
            pytest.skip("suanli not present")
        inp = parse_file(str(self.SUANLI))
        rep = detect_equations(inp)
        assert rep.turbulence == TurbulenceModel.SST_KW
        assert rep.ntrbst_family == 2
        assert rep.ntrbst_code == 3

    def test_suanli_gas_multi_temp_with_v6_eq_11(self):
        """v0.9.1:suanli 是 v6=11(双温热非平衡)+ tnoneq_numeqns=1。

        实测发现:gasnam=Air 不能作为 PERFECT_GAS 判别依据 — 双温/真实气体
        文件也都标 gasnam=Air,需用 eqnset_define v6 主判。
        """
        if not self.SUANLI.exists():
            pytest.skip("suanli not present")
        inp = parse_file(str(self.SUANLI))
        rep = detect_equations(inp)
        assert rep.gas == GasModel.MULTI_TEMP
        assert rep.gas_code == 11
        assert rep.gasnam == "Air"      # 字段仍保留,但不影响判别


class TestCompareFolderDetection:
    """6 个 compare/ 算例端到端测试(实测 → 期望映射)"""

    COMPARE = Path("/home/fz/project/cfd--changer/reference/inp_example/compare")

    def test_layered_ideal_gas(self):
        """理想气体 + 层流 → LAMINAR + PERFECT_GAS"""
        f = self.COMPARE / "可压缩理想气体+层流mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.LAMINAR
        assert rep.gas == GasModel.PERFECT_GAS

    def test_layered_real_gas(self):
        """真实气体 + 层流 → REAL_GAS + LAMINAR(v0.9.1 用 eqnset_define v6=1 判别)"""
        f = self.COMPARE / "可压缩真实气体+层流mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.LAMINAR
        assert rep.gas == GasModel.REAL_GAS
        assert rep.gas_code == 1

    def test_two_temperature_layered(self):
        """双温模型 + 层流 → MULTI_TEMP + 2T + LAMINAR(v0.9.1 用 v6=11 + tnoneq_numeqns=1)"""
        f = self.COMPARE / "双温模型+层流mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.LAMINAR
        assert rep.gas == GasModel.MULTI_TEMP
        assert rep.gas_code == 11
        assert rep.energy == EnergyModel.TWO_TEMP

    def test_goldberg_rt_1eq(self):
        f = self.COMPARE / "可压缩理想气体+1方程goldberg RTmcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.GOLDBERG_RT

    def test_sa_1eq(self):
        f = self.COMPARE / "可压缩理想气体+1方程SA mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.SPALART_ALLMARAS

    def test_sst_2eq(self):
        f = self.COMPARE / "可压缩理想气体+2方程SST mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.SST_KW

    def test_realizable_k_eps_2eq(self):
        f = self.COMPARE / "可压缩理想气体+2re方程alizable k-eps mcfd.inp"
        if not f.exists():
            pytest.skip("compare file not present")
        rep = detect_equations(parse_file(str(f)))
        assert rep.turbulence == TurbulenceModel.REALIZABLE_KEPSILON


# ======================================================================
# 阶段 2:TurbulencePresetBase + 4 子类公式测试
# ======================================================================


class TestSSTKOmega:
    def test_formula_basic(self):
        """SST k-ω: k = 1.5·(U·I)², ω = √k / (Cμ^0.25·L)"""
        p = SSTKOmegaPreset(I=0.01, L=0.01, U_ref=204.0)
        result = p.compute()
        k_expected = 1.5 * (204.0 * 0.01) ** 2
        omega_expected = math.sqrt(k_expected) / (0.09 ** 0.25 * 0.01)
        assert math.isclose(result["turbi_lev"], k_expected, rel_tol=1e-6)
        assert math.isclose(result["turbi_tlen"], omega_expected, rel_tol=1e-6)

    def test_family_is_SST_KW(self):
        assert SSTKOmegaPreset(I=0.01, L=0.01).family == TurbulenceModel.SST_KW

    def test_validation_I_out_of_range(self):
        with pytest.raises(ValueError, match="turbulence intensity"):
            SSTKOmegaPreset(I=1.5, L=0.01).compute()
        with pytest.raises(ValueError, match="turbulence intensity"):
            SSTKOmegaPreset(I=-0.1, L=0.01).compute()

    def test_validation_L_must_be_positive(self):
        with pytest.raises(ValueError, match="length scale"):
            SSTKOmegaPreset(I=0.01, L=0).compute()

    def test_apply_writes_guiopts(self):
        p = SSTKOmegaPreset(I=0.01, L=0.01)
        # 构造带 guiopts 块的 inp
        text = (
            "guiopts begin\n"
            "turbi_lev 1\n"
            "turbi_len 1\n"
            "guiopts end\n"
        )
        inp = parse(text, path="<test>")
        p.apply(inp)
        gb = inp.get_block("guiopts")
        # U_ref 默认 1.0 → k = 1.5 * (1.0 * 0.01)^2 = 0.00015
        k_default = 1.5 * (1.0 * 0.01) ** 2
        assert math.isclose(gb.get("turbi_lev"), k_default, rel_tol=1e-6)


class TestRealizableKEpsilon:
    def test_formula_basic(self):
        """Realizable k-ε: ε = Cμ^0.75 · k^1.5 / L"""
        p = RealizableKEpsilonPreset(I=0.01, L=0.01, U_ref=204.0)
        result = p.compute()
        k = 1.5 * (204.0 * 0.01) ** 2
        eps_expected = (0.09 ** 0.75) * (k ** 1.5) / 0.01
        assert math.isclose(result["turbi_lev"], k, rel_tol=1e-6)
        assert math.isclose(result["turbi_tlen"], eps_expected, rel_tol=1e-6)

    def test_family(self):
        assert RealizableKEpsilonPreset(I=0.01, L=0.01).family == TurbulenceModel.REALIZABLE_KEPSILON


class TestSpalartAllmaras:
    def test_formula_basic(self):
        """SA: ν̃ ≈ √k · L / 100(v0.9.1 简化估计)"""
        p = SpalartAllmarasPreset(I=0.01, L=0.01, U_ref=204.0)
        result = p.compute()
        k = 1.5 * (204.0 * 0.01) ** 2
        nu_tilde_expected = math.sqrt(k) * 0.01 / 100.0
        assert math.isclose(result["turbi_lev"], nu_tilde_expected, rel_tol=1e-6)

    def test_family(self):
        assert SpalartAllmarasPreset(I=0.01, L=0.01).family == TurbulenceModel.SPALART_ALLMARAS


class TestGoldbergRT:
    def test_formula_basic(self):
        """Goldberg: ν̃ ≈ √k · L / 100(v0.9.1 简化)"""
        p = GoldbergRTPreset(I=0.01, L=0.01, U_ref=204.0)
        result = p.compute()
        k = 1.5 * (204.0 * 0.01) ** 2
        nu_tilde_expected = math.sqrt(k) * 0.01 / 100.0
        assert math.isclose(result["turbi_lev"], nu_tilde_expected, rel_tol=1e-6)

    def test_family(self):
        assert GoldbergRTPreset(I=0.01, L=0.01).family == TurbulenceModel.GOLDBERG_RT


class TestFactoryDispatch:
    """make_turbulence_preset 按 family 自动选对应子类"""

    def test_sst_kw_returns_SSTKOmegaPreset(self):
        p = make_turbulence_preset(TurbulenceModel.SST_KW, I=0.01, L=0.01)
        assert isinstance(p, SSTKOmegaPreset)
        assert p.family == TurbulenceModel.SST_KW

    def test_sa_returns_SA(self):
        p = make_turbulence_preset(TurbulenceModel.SPALART_ALLMARAS, I=0.01, L=0.01)
        assert isinstance(p, SpalartAllmarasPreset)

    def test_goldberg_returns_Goldberg(self):
        p = make_turbulence_preset(TurbulenceModel.GOLDBERG_RT, I=0.01, L=0.01)
        assert isinstance(p, GoldbergRTPreset)

    def test_k_eps_returns_RealizableKEpsilon(self):
        p = make_turbulence_preset(TurbulenceModel.REALIZABLE_KEPSILON, I=0.01, L=0.01)
        assert isinstance(p, RealizableKEpsilonPreset)

    def test_laminar_unsupported_raises(self):
        with pytest.raises(ValueError, match="laminar"):
            make_turbulence_preset(TurbulenceModel.LAMINAR, I=0.01, L=0.01)

    def test_unknown_unsupported_raises(self):
        with pytest.raises(ValueError):
            make_turbulence_preset(TurbulenceModel.UNKNOWN, I=0.01, L=0.01)


# ======================================================================
# 阶段 3:SpeciesPreset mass↔mole
# ======================================================================


def _make_fake_report(species_names, mwts):
    """构造一个 EquationSystemReport 用于 convert 测试"""
    from inp_tool.equations import (
        EquationSystemReport, EnergyModel, SpeciesEntry,
    )
    return EquationSystemReport(
        energy=EnergyModel.NONE,
        turbulence=TurbulenceModel.LAMINAR,
        gas=GasModel.MIXTURE,
        n_species=len(species_names),
        species=[SpeciesEntry(name=n, mwts=[m], has_sutherland=False, has_cp=False)
                 for n, m in zip(species_names, mwts)],
    )


class TestSpeciesPreset:
    """SpeciesPreset.convert:mass↔mole 互转 + 归一化"""

    def test_mole_to_mass_50_50(self):
        """CO=0.5, O2=0.5 (mole, Mwt 28.01/32) → mass: CO=14/30, O2=16/30"""
        p = SpeciesPreset(fractions={"CO": 0.5, "O2": 0.5}, mode="mole")
        rep = _make_fake_report(["CO", "O2"], [28.01, 32.0])
        result = p.convert(rep)
        # mole → mass: Y_CO = 0.5 * 28.01 / (0.5*28.01 + 0.5*32) = 14.005 / 30.005
        # Y_O2 = 0.5 * 32 / 30.005 = 16 / 30.005
        # 总和 = 1.0
        assert math.isclose(result["CO"], 14.005 / 30.005, rel_tol=1e-6)
        assert math.isclose(result["O2"], 16.0 / 30.005, rel_tol=1e-6)
        assert math.isclose(sum(result.values()), 1.0, rel_tol=1e-9)

    def test_mass_to_mole(self):
        """mass mode 直接归一化,不做转换(v0.9.1 简化)"""
        p = SpeciesPreset(fractions={"CO": 0.3, "O2": 0.6}, mode="mass")
        rep = _make_fake_report(["CO", "O2"], [28.01, 32.0])
        result = p.convert(rep)
        # 归一化:sum=0.9 → CO=1/3, O2=2/3
        assert math.isclose(result["CO"], 1.0 / 3, rel_tol=1e-9)
        assert math.isclose(result["O2"], 2.0 / 3, rel_tol=1e-9)
        assert math.isclose(sum(result.values()), 1.0, rel_tol=1e-9)

    def test_normalization_sum_to_1(self):
        """输入 sum 不等于 1,自动归一化"""
        p = SpeciesPreset(fractions={"CO": 0.6, "O2": 0.6}, mode="mass")
        rep = _make_fake_report(["CO", "O2"], [28.01, 32.0])
        result = p.convert(rep)
        assert math.isclose(sum(result.values()), 1.0, rel_tol=1e-9)
        # mass mode 归一化:0.6+0.6=1.2 → CO=0.5, O2=0.5
        assert math.isclose(result["CO"], 0.5, rel_tol=1e-9)
        assert math.isclose(result["O2"], 0.5, rel_tol=1e-9)

    def test_unknown_species_raises(self):
        p = SpeciesPreset(fractions={"UNKNOWN": 0.5}, mode="mole")
        rep = _make_fake_report(["CO", "O2"], [28.01, 32.0])
        with pytest.raises(SpeciesNotFoundError):
            p.convert(rep)

    def test_empty_fractions_raises(self):
        p = SpeciesPreset(fractions={}, mode="mole")
        rep = _make_fake_report(["CO", "O2"], [28.01, 32.0])
        with pytest.raises((ValueError, SpeciesNotFoundError)):
            p.convert(rep)

    def test_apply_on_non_mixture_raises(self):
        """非 MIXTURE inp 用 SpeciesPreset → GasModelError"""
        from inp_tool.equations import EquationSystemReport
        inp = _make_inp(["gasnam Air"])  # PERFECT_GAS
        p = SpeciesPreset(fractions={"CO": 0.5}, mode="mole")
        with pytest.raises(GasModelError):
            p.apply(inp)


# ======================================================================
# 阶段 4:TwoTemperaturePreset
# ======================================================================


class TestTwoTemperature:
    def test_missing_Tvib_raises(self):
        p = TwoTemperaturePreset(T_trans=300.0, T_vib=None)
        with pytest.raises(TwoTemperatureError, match="BOTH T_trans and T_vib"):
            p.apply(_make_inp([], []))

    def test_missing_T_trans_raises(self):
        p = TwoTemperaturePreset(T_trans=None, T_vib=300.0)
        with pytest.raises(TwoTemperatureError, match="BOTH T_trans and T_vib"):
            p.apply(_make_inp([], []))

    def test_negative_T_trans_raises(self):
        p = TwoTemperaturePreset(T_trans=-10.0, T_vib=300.0)
        with pytest.raises(ValueError, match="temperatures must be > 0"):
            p.apply(_make_inp([], []))

    def test_writes_tnoneq_numeqns_1(self):
        """启用 2T 模型:tnoneq_numeqns = 1(用户 2026-06-11 确认)"""
        p = TwoTemperaturePreset(T_trans=288.0, T_vib=300.0)
        inp = _make_inp([], [])
        p.apply(inp)
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 1
        assert pb.get("reftem") == 288.0
        assert pb.get("vibtem") == 300.0

    def test_appends_if_tnoneq_missing(self):
        """physics 块没 tnoneq_numeqns 字段 → append"""
        inp = _make_inp(["ifrnue 1"], [])
        p = TwoTemperaturePreset(T_trans=288.0, T_vib=300.0)
        p.apply(inp)
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 1


# ======================================================================
# 阶段 5:CaseSweep 集成(从 0.8.0 既有 sweep.py 集成新 preset)
# ======================================================================


class TestCaseSweepIntegration:
    """CaseSweep 新增字段:turbulence / two_temperature / species preset 集成"""

    def test_case_sweep_has_turbulence_field(self):
        """CaseSweep 新增 turbulence 字段(默认 None,不破坏老用法)"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert hasattr(cs, "turbulence"), "CaseSweep must have 'turbulence' field"
        assert cs.turbulence is None

    def test_case_sweep_has_two_temperature_field(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert hasattr(cs, "two_temperature")
        assert cs.two_temperature is None

    def test_case_sweep_has_species_field(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert hasattr(cs, "species")
        assert cs.species is None

    def test_old_sweep_still_works_no_new_presets(self):
        """老用法(不指定新 preset)行为与 v0.9.0 完全一致"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert cs.turbulence is None
        assert cs.two_temperature is None
        assert cs.species is None
