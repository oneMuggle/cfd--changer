"""
PR #1 阶段 4:sweeps + cases 混合模式

测试目标:
- sweeps 和 cases 字段同时存在 → CartesianSpec + ExplicitCase 都进入 specs
- materialize() 顺序:先 CartesianSpec(笛卡尔展开)再 ExplicitCase
- generate() 产出 N + M 个 case
- 重复 case 警告(不阻断)
"""
from __future__ import annotations
import os
import pytest

from inp_tool.sweep import (
    CaseSweep, ExplicitCase, CartesianSpec, generate,
)


# ======================================================================
# 混合模式基础
# ======================================================================
class TestMixedModeBasic:
    def test_sweeps_and_cases_both_populated(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 5]},
            "cases": [{"alpha": 10, "beta": 3}],
        })
        # 1 CartesianSpec + 1 ExplicitCase
        assert len(cs.specs) == 2
        assert isinstance(cs.specs[0], CartesianSpec)
        assert isinstance(cs.specs[1], ExplicitCase)

    def test_sweeps_and_cases_and_groups_all_three(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
            "cases": [{"alpha": 1}],
            "groups": [{"name": "g", "common": {}, "cases": [{"alpha": 2}]}],
        })
        # 1 + 1 + 1 = 3
        assert len(cs.specs) == 3

    def test_materialize_cartesian_first_then_explicit(self):
        """materialize 顺序:CartesianSpec 先展开,ExplicitCase 在后"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [10, 20]},
            "cases": [{"alpha": 30}],
        })
        flat = cs.materialize()
        alphas = [c.values["alpha"] for c in flat]
        # 笛卡尔:10, 20 在前;cases:30 在后
        assert alphas == [10, 20, 30]


# ======================================================================
# 混合模式 generate()
# ======================================================================
class TestMixedModeGenerate:
    def test_generate_combined_count(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 5]},  # 2 cases
            "cases": [{"alpha": 10}, {"alpha": 15}],  # 2 cases
        })
        report = generate(cs)
        # 2 + 2 = 4
        assert report.total == 4

    def test_generate_naming_distinct(self, sample_inp, tmp_path):
        """混合模式下,笛卡尔和显式 case 走同一 naming 模板,文件名应不冲突"""
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 5]},
            "cases": [{"alpha": 0}],  # 与笛卡尔 alpha=0 重复
            "naming": "case_a{alpha:02.0f}.inp",
        })
        report = generate(cs)
        # 重复 case 名应被去重(现有 _1, _2 后缀逻辑)
        names = [os.path.basename(c.path) for c in report.cases]
        # 三个: case_a00.inp, case_a00_1.inp(重复), case_a05.inp
        assert "case_a00.inp" in names
        assert "case_a05.inp" in names
        # 不重复时只有 3 个
        assert len(names) == 3


# ======================================================================
# 混合 + groups 联合
# ======================================================================
class TestMixedWithGroups:
    def test_sweeps_cases_groups_total(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 5]},  # 2
            "cases": [{"alpha": 10}],  # 1
            "groups": [{"name": "g", "common": {}, "cases": [{"alpha": 15}, {"alpha": 20}]}],  # 2
        })
        report = generate(cs)
        # 2 + 1 + 2 = 5
        assert report.total == 5
        alphas = sorted(c.params["alpha"] for c in report.cases)
        assert alphas == [0.0, 5.0, 10.0, 15.0, 20.0]


# ======================================================================
# 真实场景:大部分走笛卡尔,几个特例走显式
# ======================================================================
class TestUserMixedScenario:
    """大部分基础算例走 sweeps 笛卡尔,几个特殊算例(用不同侧滑角)走 cases。"""

    def test_sweeps_base_plus_special_cases(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {
                "alpha": [0, 5, 10, 15],  # 4 cases
                "beta": [0],  # 单值
            },
            "cases": [
                # 几个有侧滑角的特例
                {"alpha": 5,  "beta": 3},
                {"alpha": 10, "beta": 5},
            ],
            "naming": "case_a{alpha:02.0f}_b{beta:02.0f}.inp",
        })
        report = generate(cs)
        # 4 + 2 = 6
        assert report.total == 6
        names = sorted(os.path.basename(c.path) for c in report.cases)
        assert names == [
            "case_a00_b00.inp",
            "case_a05_b00.inp",
            "case_a05_b03.inp",
            "case_a10_b00.inp",
            "case_a10_b05.inp",
            "case_a15_b00.inp",
        ]
