"""
PR #1 阶段 2:`cases:` 显式列表模式

测试目标:
- from_dict 传 cases 字段 → specs 走 ExplicitCase
- materialize() 透传 cases(不展开)
- generate() 产出 N 个 case(N = len(cases))
- 错误场景:同时缺 sweeps/cases/groups → 清晰 KeyError
"""
from __future__ import annotations
import os
import pytest

from inp_tool.sweep import (
    CaseSweep, ExplicitCase, CartesianSpec, generate,
)


# ======================================================================
# cases 模式基础
# ======================================================================
class TestCasesModeBasic:
    def test_cases_populates_specs_with_explicit(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "cases": [
                {"alpha": 10, "beta": 5, "mach": 0.6},
                {"alpha": 10, "beta": 8, "mach": 0.6},
                {"alpha": 20, "beta": 10, "mach": 0.6},
                {"alpha": 20, "beta": 15, "mach": 0.6},
            ],
        })
        assert len(cs.specs) == 4
        assert all(isinstance(s, ExplicitCase) for s in cs.specs)
        # 没有 CartesianSpec
        assert not any(isinstance(s, CartesianSpec) for s in cs.specs)

    def test_cases_group_is_none_by_default(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "cases": [{"alpha": 0}],
        })
        assert cs.specs[0].group is None

    def test_cases_materialize_returns_same_count(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "cases": [
                {"alpha": 10, "beta": 5},
                {"alpha": 10, "beta": 8},
                {"alpha": 20, "beta": 10},
                {"alpha": 20, "beta": 15},
            ],
        })
        flat = cs.materialize()
        assert len(flat) == 4
        # 用户给定的 4 个 case,顺序保留
        assert flat[0].values == {"alpha": 10, "beta": 5}
        assert flat[1].values == {"alpha": 10, "beta": 8}
        assert flat[2].values == {"alpha": 20, "beta": 10}
        assert flat[3].values == {"alpha": 20, "beta": 15}

    def test_cases_legacy_sweeps_field_is_empty(self):
        """cases 模式下,cs.sweeps.values 应为空 dict(老 API 兼容)"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "cases": [{"alpha": 0}],
        })
        assert cs.sweeps.values == {}


# ======================================================================
# cases 模式 generate()
# ======================================================================
class TestCasesModeGenerate:
    def test_generate_produces_n_cases(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "cases": [
                {"alpha": 10, "beta": 5, "mach": 0.6},
                {"alpha": 10, "beta": 8, "mach": 0.6},
                {"alpha": 20, "beta": 10, "mach": 0.6},
                {"alpha": 20, "beta": 15, "mach": 0.6},
            ],
        })
        report = generate(cs)
        assert report.total == 4

    def test_generate_files_written(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "cases": [
                {"alpha": 0}, {"alpha": 5}, {"alpha": 10},
            ],
        })
        report = generate(cs)
        for c in report.cases:
            assert os.path.isfile(c.path)

    def test_generate_writes_correct_alpha_per_case(self, sample_inp, tmp_path):
        from inp_tool import parse_file
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "cases": [
                {"alpha": 7},
                {"alpha": 13},
            ],
            "naming": "case_a{alpha:02.0f}.inp",
        })
        report = generate(cs)
        assert report.cases[0].path.endswith("case_a07.inp")
        assert report.cases[1].path.endswith("case_a13.inp")
        # 验证写盘的内容
        inp = parse_file(report.cases[0].path)
        assert inp.get("guiopts", "aero_alpha") == 7.0
        inp = parse_file(report.cases[1].path)
        assert inp.get("guiopts", "aero_alpha") == 13.0

    def test_generate_freestream_applied(self, sample_inp, tmp_path):
        from inp_tool import parse_file
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "cases": [{"alpha": 5, "mach": 0.8, "T_inf": 300.0}],
            "freestream": {"enabled": True},
        })
        report = generate(cs)
        inp = parse_file(report.cases[0].path)
        assert inp.get("guiopts", "aero_alpha") == 5.0
        assert inp.get("guiopts", "aero_ma") == 0.8


# ======================================================================
# 错误处理
# ======================================================================
class TestCasesModeErrors:
    def test_no_sweeps_no_cases_no_groups_raises(self):
        """必须 sweeps/cases/groups 至少一个"""
        with pytest.raises(KeyError, match="sweeps.*cases.*groups|at least one"):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
            })

    def test_empty_cases_list_treated_as_no_spec(self):
        """cases: [] 视为未提供 → 报错"""
        with pytest.raises((KeyError, ValueError)):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
                "cases": [],
            })


# ======================================================================
# 真实场景:用户原话举例
# ======================================================================
class TestUserScenario:
    """用户在对话中给的真实例子:
    流场 1 的 T/p 对应 10°/20° 攻角,各攻角下又有不同侧滑角。
    """

    def test_user_scenario_4_cases(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "cases": [
                {"alpha": 10, "beta": 5,  "T": 288.15, "p": 101325},
                {"alpha": 10, "beta": 8,  "T": 288.15, "p": 101325},
                {"alpha": 20, "beta": 10, "T": 288.15, "p": 101325},
                {"alpha": 20, "beta": 15, "T": 288.15, "p": 101325},
            ],
            "naming": "case_a{alpha:02.0f}_b{beta:02.0f}.inp",
        })
        report = generate(cs)
        assert report.total == 4
        names = sorted(os.path.basename(c.path) for c in report.cases)
        assert names == [
            "case_a10_b05.inp",
            "case_a10_b08.inp",
            "case_a20_b10.inp",
            "case_a20_b15.inp",
        ]
