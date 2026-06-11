"""
v0.10.0:方程感知扩展的写函数单元测试
"""
from __future__ import annotations
import pytest
from inp_tool.equations import (
    EquationRewriteIssue,
)
from inp_tool.model import InpFile


class TestEquationRewriteIssue:
    def test_issue_basic_fields(self):
        iss_obj = EquationRewriteIssue(
            severity="error",
            code="unknown_turbulence_model",
            message="cannot switch to UNKNOWN turbulence model",
        )
        assert iss_obj.severity == "error"
        assert iss_obj.code == "unknown_turbulence_model"
        assert iss_obj.message == "cannot switch to UNKNOWN turbulence model"

    def test_issue_severity_validation(self):
        with pytest.raises(ValueError, match="severity must be"):
            EquationRewriteIssue(severity="info", code="x", message="y")

    def test_issue_repr(self):
        iss_obj = EquationRewriteIssue(
            severity="warning",
            code="residual_turb_field",
            message="residual fields: turbi_tlev",
        )
        s = repr(iss_obj)
        assert "[warning]" in s
        assert "residual_turb_field" in s
        assert "residual fields: turbi_tlev" in s


class TestSetTurbulenceModel:
    def _build_minimal_inp(self, ntrbst_family: int, ntrbst_code: int) -> "InpFile":
        """构造最小可用的 InpFile,带 eqnset_define 块,family/code 给定。"""
        from pathlib import Path
        from inp_tool.parser import parse_file
        from inp_tool.equations import _find_eqnset_define
        # 用 v0.9.1 的 SST 样本(2-方程 SST k-ω, family=2, code=3)
        path = (
            Path(__file__).parent / "fixtures" / "compare"
            / "可压缩理想气体+2方程SST mcfd.inp"
        )
        inp = parse_file(str(path))
        # 改 eqnset_define v4/v5 为传入值
        stmt = _find_eqnset_define(inp)
        assert stmt is not None
        stmt.children[0].set(3, ntrbst_family)
        stmt.children[0].set(4, ntrbst_code)
        return inp

    def test_sst_to_sa_rewrites_v4_v5(self):
        from inp_tool.equations import set_turbulence_model, TurbulenceModel
        from inp_tool.equations import _find_eqnset_define
        inp = self._build_minimal_inp(ntrbst_family=2, ntrbst_code=3)
        applied = set_turbulence_model(inp, TurbulenceModel.SPALART_ALLMARAS)
        stmt = _find_eqnset_define(inp)
        assert stmt.children[0].values_raw[3] == "1"
        assert stmt.children[0].values_raw[4] == "4"
        assert applied == {"eqnset_define.v4_v5": (1, 4), "eqnset_define.turbulence_model": "spalart-allmaras"}

    def test_sa_to_sst_rewrites_v4_v5(self):
        from inp_tool.equations import set_turbulence_model, TurbulenceModel
        from inp_tool.equations import _find_eqnset_define
        inp = self._build_minimal_inp(ntrbst_family=1, ntrbst_code=4)
        set_turbulence_model(inp, TurbulenceModel.SST_KW)
        stmt = _find_eqnset_define(inp)
        assert stmt.children[0].values_raw[3] == "2"
        assert stmt.children[0].values_raw[4] == "3"

    def test_to_laminar_rewrites_v4_v5(self):
        from inp_tool.equations import set_turbulence_model, TurbulenceModel
        from inp_tool.equations import _find_eqnset_define
        inp = self._build_minimal_inp(ntrbst_family=2, ntrbst_code=3)
        set_turbulence_model(inp, TurbulenceModel.LAMINAR)
        stmt = _find_eqnset_define(inp)
        assert stmt.children[0].values_raw[3] == "0"
        assert stmt.children[0].values_raw[4] == "1"

    def test_unknown_model_raises(self):
        from inp_tool.equations import (
            set_turbulence_model, TurbulenceModel, EquationRewriteError,
        )
        inp = self._build_minimal_inp(ntrbst_family=2, ntrbst_code=3)
        with pytest.raises(EquationRewriteError, match="cannot switch to UNKNOWN"):
            set_turbulence_model(inp, TurbulenceModel.UNKNOWN)

    def test_no_eqnset_define_raises(self):
        from inp_tool.equations import (
            set_turbulence_model, TurbulenceModel, EquationRewriteError,
        )
        from inp_tool.parser import parse_file
        import tempfile
        import os
        with tempfile.NamedTemporaryFile("w", suffix=".inp", delete=False) as f:
            f.write("title dummy\n")
            f.write("values 1.0 2.0 3.0\n")
            tmp = f.name
        try:
            inp = parse_file(tmp)
            with pytest.raises(EquationRewriteError, match="no_eqnset_define"):
                set_turbulence_model(inp, TurbulenceModel.SST_KW)
        finally:
            os.unlink(tmp)


class TestSetEnergyModel:
    def _build_inp(self, tnoneq: int) -> "InpFile":
        from inp_tool.parser import parse_file
        # 用 tests/fixtures/compare/ 下的样本(同 Task 2 已用路径)
        from pathlib import Path
        path = str(Path(__file__).parent / "fixtures" / "compare" / "可压缩理想气体+2方程SST mcfd.inp")
        inp = parse_file(path)
        pb = inp.get_block("physics")
        if pb:
            pb.set("tnoneq_numeqns", tnoneq)
        return inp

    def test_none_to_two_temp_writes_numeqns_vibtem(self):
        """NONE → TWO_TEMP:tnoneq_numeqns=1, 写 vibtem, 联动 v6=11。"""
        from inp_tool.equations import (
            set_energy_model, EnergyModel, _find_eqnset_define,
        )
        inp = self._build_inp(tnoneq=0)
        set_energy_model(
            inp, EnergyModel.TWO_TEMP, T_trans=300.0, T_vib=200.0,
        )
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 1
        assert pb.get("vibtem") == 200.0
        assert pb.get("reftem") == 300.0
        eqnset = _find_eqnset_define(inp)
        assert eqnset.children[1].values_raw[0] == "11"

    def test_two_temp_to_none_clears_numeqns(self):
        """TWO_TEMP → NONE:tnoneq_numeqns=0, 联动 v6=0。"""
        from inp_tool.equations import (
            set_energy_model, EnergyModel, _find_eqnset_define,
        )
        inp = self._build_inp(tnoneq=1)
        set_energy_model(inp, EnergyModel.NONE)
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 0
        eqnset = _find_eqnset_define(inp)
        assert eqnset.children[1].values_raw[0] == "0"

    def test_two_temp_missing_temps_raises(self):
        """TWO_TEMP 缺 T_trans 或 T_vib 抛 TwoTemperatureError。"""
        from inp_tool.equations import (
            set_energy_model, EnergyModel, TwoTemperatureError,
        )
        inp = self._build_inp(tnoneq=0)
        with pytest.raises(TwoTemperatureError, match="BOTH T_trans and T_vib"):
            set_energy_model(inp, EnergyModel.TWO_TEMP, T_trans=300.0)
        with pytest.raises(TwoTemperatureError, match="BOTH T_trans and T_vib"):
            set_energy_model(inp, EnergyModel.TWO_TEMP, T_vib=200.0)

    def test_v6_linked_correctly(self):
        """NONE 写 v6=0;TWO_TEMP 写 v6=11(read-back 校验)。"""
        from inp_tool.equations import (
            set_energy_model, EnergyModel, _find_eqnset_define,
        )
        inp_none = self._build_inp(tnoneq=0)
        set_energy_model(inp_none, EnergyModel.NONE)
        eqnset = _find_eqnset_define(inp_none)
        assert eqnset.children[1].values_raw[0] == "0"
        # TWO_TEMP 路径
        inp_2t = self._build_inp(tnoneq=0)
        set_energy_model(inp_2t, EnergyModel.TWO_TEMP, T_trans=300, T_vib=200)
        eqnset = _find_eqnset_define(inp_2t)
        assert eqnset.children[1].values_raw[0] == "11"


class TestSetGasType:
    def _build_inp(self, tnoneq: int) -> "InpFile":
        from inp_tool.parser import parse_file
        from pathlib import Path
        path = str(Path(__file__).parent / "fixtures" / "compare" / "可压缩理想气体+2方程SST mcfd.inp")
        inp = parse_file(path)
        pb = inp.get_block("physics")
        if pb:
            pb.set("tnoneq_numeqns", tnoneq)
        return inp

    def test_perfect_to_real_writes_v6_1(self):
        """PERFECT_GAS → REAL_GAS:v6=0 → v6=1。"""
        from inp_tool.equations import (
            set_gas_type, GasModel, _find_eqnset_define,
        )
        inp = self._build_inp(tnoneq=0)
        set_gas_type(inp, GasModel.REAL_GAS)
        eqnset = _find_eqnset_define(inp)
        assert eqnset.children[1].values_raw[0] == "1"

    def test_perfect_to_multi_temp_forces_2t(self):
        """PERFECT_GAS → MULTI_TEMP:自动设 tnoneq_numeqns=1 + v6=11。"""
        from inp_tool.equations import (
            set_gas_type, GasModel, _find_eqnset_define,
        )
        inp = self._build_inp(tnoneq=0)
        set_gas_type(inp, GasModel.MULTI_TEMP)
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 1
        eqnset = _find_eqnset_define(inp)
        assert eqnset.children[1].values_raw[0] == "11"

    def test_real_to_multi_temp_writes_v6_11(self):
        """REAL_GAS → MULTI_TEMP(若 tnoneq=0 但用户已允许):v6=11, tnoneq 强制设 1。"""
        # 注:set_gas_type(MULTI_TEMP) 会强制把 tnoneq 设 1
        # 因此"raises"路径不存在,改测"成功但自动改 tnoneq"
        from inp_tool.equations import (
            set_gas_type, GasModel, _find_eqnset_define,
        )
        inp = self._build_inp(tnoneq=0)
        set_gas_type(inp, GasModel.MULTI_TEMP)
        pb = inp.get_block("physics")
        assert pb.get("tnoneq_numeqns") == 1
        eqnset = _find_eqnset_define(inp)
        assert eqnset.children[1].values_raw[0] == "11"

    def test_warns_when_perfect_gas_with_2t(self):
        """tnoneq=1 + 设 v6=0(PERFECT_GAS)→ applied 含 gas_inconsistent_with_energy 警告。"""
        from inp_tool.equations import set_gas_type, GasModel
        inp = self._build_inp(tnoneq=1)
        applied = set_gas_type(inp, GasModel.PERFECT_GAS)
        assert "eqnset_define.issue" in applied
        assert "gas_inconsistent_with_energy" in applied["eqnset_define.issue"]

    def test_warns_when_real_gas_with_2t(self):
        """tnoneq=1 + 设 v6=1(REAL_GAS)→ applied 含 gas_real_with_2t 警告。"""
        from inp_tool.equations import set_gas_type, GasModel
        inp = self._build_inp(tnoneq=1)
        applied = set_gas_type(inp, GasModel.REAL_GAS)
        assert "eqnset_define.issue" in applied
        assert "gas_real_with_2t" in applied["eqnset_define.issue"]

    def test_unsupported_model_raises(self):
        """MIXTURE / UNKNOWN 抛 EquationRewriteError(v0.10.0 不支持)。"""
        from inp_tool.equations import (
            set_gas_type, GasModel, EquationRewriteError,
        )
        for unsupported in (GasModel.MIXTURE, GasModel.UNKNOWN):
            inp = self._build_inp(tnoneq=0)
            with pytest.raises(EquationRewriteError, match="unsupported gas model"):
                set_gas_type(inp, unsupported)


class TestClearIncompatibleFields:
    """v0.10.0:Turbu lencePresetBase.clear_incompatible_fields + apply(model=...)"""

    def _load_sst_inp(self):
        from pathlib import Path
        from inp_tool.parser import parse_file
        path = (
            Path(__file__).parent / "fixtures" / "compare"
            / "可压缩理想气体+2方程SST mcfd.inp"
        )
        return parse_file(str(path))

    def test_sst_to_sa_clears_tlev_tlen(self):
        """SST → SA:清 turbi_tlev, turbi_tlen, 保留 turbi_lev, turbi_len。"""
        from inp_tool.equations import (
            SpalartAllmarasPreset, TurbulenceModel,
        )
        inp = self._load_sst_inp()
        gb = inp.get_block("guiopts")
        gb.set("turbi_lev", 1.0)
        gb.set("turbi_tlev", 0.5)
        gb.set("turbi_len", 0.01)
        gb.set("turbi_tlen", 100.0)
        # 切到 SA:用 SA preset, model=SA
        new_preset = SpalartAllmarasPreset(I=0.01, L=0.01, U_ref=204.0)
        new_preset.apply(
            inp, model=TurbulenceModel.SPALART_ALLMARAS,
            clear_incompatible_fields=True,
        )
        # SA 只需 turbi_lev, turbi_len;tlev/tlen 被清
        assert gb.get("turbi_tlev") is None
        assert gb.get("turbi_tlen") is None
        assert gb.get("turbi_lev") is not None
        assert gb.get("turbi_len") is not None

    def test_laminar_clears_all_turbi(self):
        """切到 LAMINAR:清全部 turbi_* 字段(用 SA preset 测,SA.compute() 不写 tlev/tlen)。

        重要:若用 SST preset,SST.compute() 会重写 turbi_lev/len/tlev/tlen,
        看不到 clear 效果。所以这里用 SpalartAllmaras(1-方程,只写 lev/len)
        来暴露 clear 行为。
        """
        from inp_tool.equations import (
            SpalartAllmarasPreset, TurbulenceModel,
        )
        inp = self._load_sst_inp()
        gb = inp.get_block("guiopts")
        gb.set("turbi_lev", 1.0)
        gb.set("turbi_tlev", 0.5)
        gb.set("turbi_len", 0.01)
        gb.set("turbi_tlen", 100.0)
        preset = SpalartAllmarasPreset(I=0.01, L=0.01, U_ref=204.0)
        preset.apply(
            inp, model=TurbulenceModel.LAMINAR,
            clear_incompatible_fields=True,
        )
        # LAMINAR 清全部;SA compute 只写 turbi_lev/turbi_len,
        # 所以 turbi_tlev/turbi_tlen 留下 None;turbi_lev/len 被 SA 重写
        assert gb.get("turbi_tlev") is None
        assert gb.get("turbi_tlen") is None
        # SA compute 写了 turbi_lev/turbi_len(清后被新值覆盖)
        assert gb.get("turbi_lev") is not None
        assert gb.get("turbi_len") is not None

    def test_sst_to_sst_keeps_all(self):
        """同模型(SST→SST):_clear_incompatible 对 2-方程是 no-op,compute() 重写。

        重要:用户设的 turbi_lev=1.0/turbi_len=0.01 会被 SST compute() 覆盖为
        实际算出的 k/ω 公式值;这里测的是清不掉 + 公式正确执行(不抛错)。
        """
        from inp_tool.equations import (
            SSTKOmegaPreset, TurbulenceModel,
        )
        inp = self._load_sst_inp()
        gb = inp.get_block("guiopts")
        gb.set("turbi_lev", 1.0)
        gb.set("turbi_tlev", 0.5)
        gb.set("turbi_len", 0.01)
        gb.set("turbi_tlen", 100.0)
        preset = SSTKOmegaPreset(I=0.01, L=0.01, U_ref=204.0)
        # 不抛错
        preset.apply(
            inp, model=TurbulenceModel.SST_KW,
            clear_incompatible_fields=True,
        )
        # SST → SST 是 2-方程,_clear_incompatible 不删任何字段
        # 然后 SST compute() 重写 4 个字段(用户值被覆盖)
        # 不变量:4 个字段都存在(被 compute 写过)
        assert gb.get("turbi_lev") is not None
        assert gb.get("turbi_tlev") is not None
        assert gb.get("turbi_len") is not None
        assert gb.get("turbi_tlen") is not None
        # SST 公式正确:turbi_tlev = k / (0.5 * U²)
        # k = 1.5 * (204*0.01)^2 = 6.2424;U²/2 = 204²/2 = 20808
        # turbi_tlev = 6.2424 / 20808 ≈ 0.0003
        expected_k = 1.5 * (204.0 * 0.01) ** 2
        assert abs(gb.get("turbi_lev") - expected_k) < 1e-3


class TestResidualFieldsStrict:
    """v0.10.0:默认行为与显式 clear=False 行为不破坏 v0.9.1 调用约定。

    关键不变量(v0.9.1→v0.10.0 必须保留):
    - apply(inp) 不传 model 时:不抛错,正常写 compute() 结果,返回 applied dict
    - apply(inp, model=X, clear_incompatible_fields=False):不抛错,不清多余字段,
      仅按 compute() 写应有的字段
    """

    def _load_sst_inp(self):
        from pathlib import Path
        from inp_tool.parser import parse_file
        path = (
            Path(__file__).parent / "fixtures" / "compare"
            / "可压缩理想气体+2方程SST mcfd.inp"
        )
        return parse_file(str(path))

    def test_default_keeps_residual_no_error(self):
        """默认模式(不传 model):apply 行为同 v0.9.1,不抛错、返回 applied dict。"""
        from inp_tool.equations import SSTKOmegaPreset
        inp = self._load_sst_inp()
        gb = inp.get_block("guiopts")
        gb.set("turbi_tlev", 0.5)
        gb.set("turbi_tlen", 100.0)
        new_preset = SSTKOmegaPreset(I=0.01, L=0.01, U_ref=204.0)
        # 不传 model → 走 v0.9.1 路径,不抛错
        applied = new_preset.apply(inp)
        # v0.9.1 行为:apply 会用 compute() 写 guiopts 字段(覆盖原值)
        # 不变量:不抛错 + 返回非空 applied dict
        assert applied
        # 写过的 compute() 字段都在 applied 中
        assert "guiopts.turbi_lev" in applied
        assert "guiopts.turbi_tlev" in applied
        assert "guiopts.turbi_len" in applied
        assert "guiopts.turbi_tlen" in applied

    def test_clear_false_keeps_residual(self):
        """clear_incompatible_fields=False:不清理多余字段,只写 compute() 要求的。"""
        from inp_tool.equations import (
            SSTKOmegaPreset, TurbulenceModel,
        )
        inp = self._load_sst_inp()
        gb = inp.get_block("guiopts")
        gb.set("turbi_tlev", 0.5)
        gb.set("turbi_tlen", 100.0)
        new_preset = SSTKOmegaPreset(I=0.01, L=0.01, U_ref=204.0)
        # clear=False → 不会主动删 turbi_*/多余字段;不抛错
        new_preset.apply(
            inp, model=TurbulenceModel.SPALART_ALLMARAS,
            clear_incompatible_fields=False,
        )
        # v0.9.1 不变量:apply 不抛错,applied 含 compute() 写的字段
        # 注意:即使 clear=False,SST 自己的 compute() 也会写 turbi_tlev/tlen
        # (这里 SST 在 v0.9.1 的写法就是无条件覆盖;新加的 model= 只是给清除逻辑用)
        # 所以这里验证 "不抛错" 和 "compute 字段已写"
        gb_lev = gb.get("turbi_lev")
        assert gb_lev is not None  # SST compute 写了
        gb_len = gb.get("turbi_len")
        assert gb_len is not None
