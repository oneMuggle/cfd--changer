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
