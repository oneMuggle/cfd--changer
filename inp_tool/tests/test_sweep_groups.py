"""
PR #1 阶段 3:`groups:` 分组继承模式

测试目标:
- groups: [{name, common, cases}] 解析
- common 字段注入到每个 case(per-case 字段覆盖 common)
- {group} 占位符在 naming 中展开
- 无名 group 兜底
- 嵌套组合(多 group 拼接)
"""
from __future__ import annotations
import os
import pytest

from inp_tool.sweep import (
    CaseSweep, ExplicitCase, CartesianSpec, generate,
)


# ======================================================================
# groups 模式基础
# ======================================================================
class TestGroupsModeBasic:
    def test_groups_populates_specs(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [
                {
                    "name": "flow1",
                    "common": {"T": 288.15, "p": 101325, "mach": 0.6},
                    "cases": [
                        {"alpha": 10, "beta": 5},
                        {"alpha": 10, "beta": 8},
                    ],
                },
            ],
        })
        # 2 cases from group
        assert len(cs.specs) == 2
        assert all(isinstance(s, ExplicitCase) for s in cs.specs)

    def test_groups_common_inherited(self):
        """common 字段应注入到每个 case"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [{
                "name": "flow1",
                "common": {"T": 288.15, "p": 101325},
                "cases": [
                    {"alpha": 10, "beta": 5},
                ],
            }],
        })
        flat = cs.materialize()
        assert flat[0].values == {
            "alpha": 10, "beta": 5, "T": 288.15, "p": 101325,
        }

    def test_groups_case_overrides_common(self):
        """per-case 字段覆盖 common 同名字段"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [{
                "name": "flow1",
                "common": {"T": 288.15, "mach": 0.6},
                "cases": [
                    {"alpha": 10, "mach": 0.8},  # mach 覆盖
                ],
            }],
        })
        flat = cs.materialize()
        assert flat[0].values["mach"] == 0.8  # 来自 case
        assert flat[0].values["T"] == 288.15  # 来自 common

    def test_groups_group_name_carried(self):
        """ExplicitCase.group 字段记录 group 名"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [
                {"name": "flow1", "common": {}, "cases": [{"alpha": 1}]},
                {"name": "flow2", "common": {}, "cases": [{"alpha": 2}]},
            ],
        })
        flat = cs.materialize()
        assert flat[0].group == "flow1"
        assert flat[1].group == "flow2"

    def test_groups_unnamed_group(self):
        """无名 group:group 字段为 None"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [
                {"common": {"T": 300}, "cases": [{"alpha": 0}]},
            ],
        })
        flat = cs.materialize()
        assert flat[0].group is None
        assert flat[0].values["T"] == 300.0

    def test_groups_multiple_groups_merged(self):
        """多个 group 的 cases 应拼接(按顺序)"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "groups": [
                {
                    "name": "low",
                    "common": {"mach": 0.3},
                    "cases": [{"alpha": 2}, {"alpha": 4}],
                },
                {
                    "name": "high",
                    "common": {"mach": 0.85},
                    "cases": [{"alpha": 10}, {"alpha": 15}, {"alpha": 20}],
                },
            ],
        })
        flat = cs.materialize()
        # 2 + 3 = 5
        assert len(flat) == 5
        alphas = [c.values["alpha"] for c in flat]
        assert alphas == [2, 4, 10, 15, 20]
        # 前 2 个是 low,后 3 个是 high
        assert flat[0].group == "low"
        assert flat[3].group == "high"


# ======================================================================
# {group} 命名占位符
# ======================================================================
class TestGroupPlaceholder:
    def test_group_placeholder_in_naming(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "groups": [
                {
                    "name": "flow1",
                    "common": {"mach": 0.6},
                    "cases": [{"alpha": 10}],
                },
            ],
            "naming": "{group}_a{alpha:02.0f}.inp",
        })
        report = generate(cs)
        assert report.cases[0].path.endswith("flow1_a10.inp")

    def test_group_placeholder_multi_groups(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "groups": [
                {"name": "low",  "common": {"mach": 0.3}, "cases": [{"alpha": 2}]},
                {"name": "high", "common": {"mach": 0.85}, "cases": [{"alpha": 10}]},
            ],
            "naming": "{group}_a{alpha:02.0f}.inp",
        })
        report = generate(cs)
        names = sorted(os.path.basename(c.path) for c in report.cases)
        assert names == ["high_a10.inp", "low_a02.inp"]


# ======================================================================
# groups 模式 generate()
# ======================================================================
class TestGroupsModeGenerate:
    def test_generate_total_count(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "groups": [
                {
                    "name": "flow1",
                    "common": {"T": 288.15, "p": 101325, "mach": 0.6},
                    "cases": [
                        {"alpha": 10, "beta": 5},
                        {"alpha": 10, "beta": 8},
                        {"alpha": 20, "beta": 10},
                        {"alpha": 20, "beta": 15},
                    ],
                },
            ],
        })
        report = generate(cs)
        assert report.total == 4

    def test_generate_with_overrides(self, sample_inp, tmp_path):
        from inp_tool import parse_file
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "groups": [
                {
                    "name": "flow1",
                    "common": {"T": 288.15, "p": 101325, "mach": 0.6},
                    "cases": [{"alpha": 5}, {"alpha": 10}],
                },
            ],
            "overrides": {"tsteps": {"ntstep": 20000}},
        })
        report = generate(cs)
        for c in report.cases:
            inp = parse_file(c.path)
            assert inp.get("tsteps", "ntstep") == 20000


# ======================================================================
# 错误处理
# ======================================================================
class TestGroupsModeErrors:
    def test_empty_groups_list_raises(self):
        with pytest.raises((KeyError, ValueError)):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
                "groups": [],
            })

    def test_group_with_empty_cases_raises(self):
        with pytest.raises((KeyError, ValueError)):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
                "groups": [
                    {"name": "g1", "common": {}, "cases": []},
                ],
            })


# ======================================================================
# 用户真实场景:多流场分组
# ======================================================================
class TestUserMultiFlowScenario:
    """用户原话:"流场 1 的 T/p 对应 10°/20° 攻角,各攻角下又有不同侧滑角"。

    这里扩到多流场对比:flow_1_sealevel / flow_2_high_alt / flow_3_cruise。
    """

    def test_three_flows(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "groups": [
                {
                    "name": "flow_1_sealevel",
                    "common": {"T": 288.15, "p": 101325, "mach": 0.6},
                    "cases": [
                        {"alpha": 10, "beta": 5},
                        {"alpha": 10, "beta": 8},
                        {"alpha": 20, "beta": 10},
                        {"alpha": 20, "beta": 15},
                    ],
                },
                {
                    "name": "flow_2_high_alt",
                    "common": {"T": 250.0, "p": 35000, "mach": 0.85},
                    "cases": [
                        {"alpha": 5, "beta": 0},
                        {"alpha": 15, "beta": 0},
                        {"alpha": 25, "beta": 0},
                    ],
                },
                {
                    "name": "flow_3_cruise",
                    "common": {"T": 273.0, "p": 75000, "mach": 0.78},
                    "cases": [
                        {"alpha": 2, "beta": -3},
                        {"alpha": 2, "beta": 0},
                        {"alpha": 2, "beta": 3},
                    ],
                },
            ],
            "naming": "{group}_a{alpha:02.0f}_b{beta:+03.0f}.inp",
        })
        report = generate(cs)
        # 4 + 3 + 3 = 10
        assert report.total == 10
        names = sorted(os.path.basename(c.path) for c in report.cases)
        # 至少检查 3 个有代表性的
        assert "flow_1_sealevel_a10_b+05.inp" in names
        assert "flow_2_high_alt_a15_b+00.inp" in names
        assert "flow_3_cruise_a02_b-03.inp" in names
