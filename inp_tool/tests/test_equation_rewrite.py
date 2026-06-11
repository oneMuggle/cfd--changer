"""
v0.10.0:方程感知扩展的写函数单元测试
"""
from __future__ import annotations
import pytest
from inp_tool.equations import (
    EquationRewriteError,
    EquationRewriteIssue,
)


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
        applied = set_energy_model(
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
        with pytest.raises(TwoTemperatureError, match="both T_trans and T_vib"):
            set_energy_model(inp, EnergyModel.TWO_TEMP, T_trans=300.0)
        with pytest.raises(TwoTemperatureError, match="both T_trans and T_vib"):
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
