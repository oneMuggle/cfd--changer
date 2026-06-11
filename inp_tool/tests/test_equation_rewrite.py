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
