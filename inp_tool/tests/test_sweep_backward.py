"""
PR #1 重构:零行为变化回归测试

锁死 CaseSweep 老 API 行为(sweeps 字段、from_dict / from_json / from_yaml、
generate())。同时验证新 specs 字段在老用法下也被正确填充(为新流程铺垫)。

如果此文件中任何测试失败,说明重构破坏了向后兼容,必须修复后再继续。
"""
from __future__ import annotations
import json
import os
import pytest

from inp_tool.sweep import (
    CaseSweep,
    CartesianSpec,  # 新增
    ExplicitCase,   # 新增
    expand_cartesian,
    generate,
)


# ======================================================================
# 老 API 字段不变(s.sweeps.values 必须仍可访问)
# ======================================================================
class TestLegacySweepsField:
    def test_old_dict_sweeps_field_preserved(self):
        """老用法:from_dict 传 sweeps 字段,cs.sweeps.values 仍可访问"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert cs.sweeps.values == {"alpha": [0, 4]}

    def test_old_json_sweeps_field_preserved(self, tmp_path):
        cfg = tmp_path / "s.json"
        cfg.write_text(json.dumps({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4], "mach": [0.6, 0.8]},
        }))
        cs = CaseSweep.from_json(str(cfg))
        assert cs.sweeps.values == {"alpha": [0, 4], "mach": [0.6, 0.8]}

    def test_old_yaml_sweeps_field_preserved(self, tmp_path):
        cfg = tmp_path / "s.yaml"
        cfg.write_text(
            "template: t.inp\n"
            "output_dir: out\n"
            "sweeps:\n"
            "  alpha: [0, 4]\n"
            "  mach: [0.6, 0.8]\n"
        )
        cs = CaseSweep.from_yaml(str(cfg))
        assert cs.sweeps.values == {"alpha": [0, 4], "mach": [0.6, 0.8]}


# ======================================================================
# 新 specs 字段在老用法下也应被填充
# ======================================================================
class TestSpecsFieldPopulated:
    def test_old_dict_populates_specs_with_cartesian(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert len(cs.specs) == 1
        assert isinstance(cs.specs[0], CartesianSpec)
        assert cs.specs[0].axes == {"alpha": [0, 4]}

    def test_old_dict_specs_empty_when_no_sweeps_or_cases(self):
        """极端场景:完全不传 sweeps/cases/groups(后续阶段会改成报错,这里只断言 specs 是 list)"""
        # 当前 from_dict 强制要 sweeps;但为防止重构后字段类型变化,这里仅断言 specs 存在
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},  # 占位,绕过强制检查
        })
        assert isinstance(cs.specs, list)


# ======================================================================
# materialize() 等价于 expand_cartesian(sweeps)
# ======================================================================
class TestMaterialize:
    def test_materialize_single_axis(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        flat = cs.materialize()
        assert len(flat) == 2
        assert all(isinstance(c, ExplicitCase) for c in flat)
        assert [c.values for c in flat] == [{"alpha": 0}, {"alpha": 4}]

    def test_materialize_two_axes_cartesian(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4], "mach": [0.6, 0.8]},
        })
        flat = cs.materialize()
        # 与 expand_cartesian 一致
        expected = expand_cartesian(cs.sweeps)
        assert [c.values for c in flat] == expected
        # 4 个 case
        assert len(flat) == 4

    def test_materialize_three_axes(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4, 8], "beta": [0], "mach": [0.6, 0.8]},
        })
        flat = cs.materialize()
        assert len(flat) == 6  # 3 * 1 * 2

    def test_explicit_case_default_group_is_none(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        flat = cs.materialize()
        assert all(c.group is None for c in flat)


# ======================================================================
# 老用法 generate() 行为零变化
# ======================================================================
class TestGenerateUnchanged:
    def test_old_dict_generate_total_unchanged(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 4], "mach": [0.6, 0.8]},
        })
        report = generate(cs)
        assert report.total == 4  # 2*2 笛卡尔

    def test_old_dict_generate_files_written(self, sample_inp, tmp_path):
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0]},
        })
        report = generate(cs)
        for c in report.cases:
            assert os.path.isfile(c.path)

    def test_old_dict_with_overrides_unchanged(self, sample_inp, tmp_path):
        from inp_tool import parse_file
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0]},
            "overrides": {"tsteps": {"ntstep": 20000}},
        })
        report = generate(cs)
        for c in report.cases:
            inp = parse_file(c.path)
            assert inp.get("tsteps", "ntstep") == 20000

    def test_old_yaml_generate_unchanged(self, sample_inp, tmp_path):
        """老 YAML 文件经 from_yaml 走 generate 行为不变"""
        import yaml
        cfg = tmp_path / "sweep.yaml"
        cfg.write_text(yaml.safe_dump({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0, 4], "mach": [0.6, 0.8]},
        }))
        cs = CaseSweep.from_yaml(str(cfg))
        report = generate(cs)
        assert report.total == 4
        # 默认 naming:case_{alpha}_{mach}(两个都是多值轴)
        names = [os.path.basename(c.path) for c in report.cases]
        assert "case_0_0.6.inp" in names
        assert "case_4_0.8.inp" in names

    def test_old_dict_with_manifest_unchanged(self, sample_inp, tmp_path):
        import json
        manifest_path = tmp_path / "out" / "manifest.json"
        cs = CaseSweep.from_dict({
            "template": str(sample_inp),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {"alpha": [0]},
            "manifest": {"path": str(manifest_path)},
        })
        report = generate(cs)
        assert report.total == 1
        with open(manifest_path) as f:
            data = json.load(f)
        assert data["total"] == 1
