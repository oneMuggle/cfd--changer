"""
mcfd.inp sweep 批量算例生成器 — Phase 2-3 RED

测试目标:
- CaseSweep.from_dict / from_json: 配置加载与校验
- generate(): 主流程(parse -> deepcopy -> preset -> overrides -> write -> manifest)
- overrides: 两种风格 ({block: {k: v}} 与 {"block.k": v})
- manifest: 写入与回读
- dry_run: 不写盘
- 命名模板 + 输出路径
"""
from __future__ import annotations
import json
import os
import math
import pytest

from inp_tool.sweep import (
    CaseSweep,
    generate,
    FreestreamPreset,
)


# ======================================================================
# CaseSweep.from_dict / from_json
# ======================================================================
class TestCaseSweepFromDict:
    def test_minimal_dict(self):
        s = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        })
        assert s.template == "t.inp"
        assert s.output_dir == "out"
        assert s.sweeps.values == {"alpha": [0, 4]}
        assert s.naming == "case_{alpha}"  # 默认
        assert s.overrides == {}  # 默认
        assert isinstance(s.freestream, FreestreamPreset)  # 默认开启

    def test_full_dict(self):
        s = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "naming": "aoa{alpha:02d}_ma{mach:.2f}",
            "sweeps": {"alpha": [0, 4, 8], "mach": [0.6, 0.8]},
            "overrides": {"tsteps": {"ntstep": 20000}},
            "freestream": {"enabled": False},
            "manifest": {"path": "out/manifest.json"},
        })
        assert s.naming == "aoa{alpha:02d}_ma{mach:.2f}"
        assert s.overrides == {"tsteps": {"ntstep": 20000}}
        assert s.freestream is None  # 显式关闭
        assert s.manifest_path == "out/manifest.json"

    def test_naming_uses_only_multi_value_keys_by_default(self):
        s = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4], "beta": [0], "T_inf": [288.15]},
        })
        # 默认 naming 只包含**多值** sweep 字段(单值轴不进文件名)
        assert "{alpha}" in s.naming
        assert "{beta}" not in s.naming
        assert "{T_inf}" not in s.naming

    def test_naming_missing_multi_value_sweep_key_raises(self):
        # 用户的 naming 缺了某个**多值** sweep 字段占位符
        with pytest.raises(ValueError, match="missing sweep key"):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
                "sweeps": {"alpha": [0, 4, 8], "beta": [0, 4]},  # 都是多值
                "naming": "aoa{alpha}",  # 缺 {beta}
            })

    def test_naming_allows_omitting_single_value_axes(self):
        # beta 是单值(固定为 0),不出现于 naming 也合法
        s = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4, 8], "beta": [0]},
            "naming": "aoa{alpha}",
        })
        assert s.naming == "aoa{alpha}"

    def test_from_json(self, tmp_path):
        cfg = tmp_path / "sweep.json"
        cfg.write_text(json.dumps({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        }))
        s = CaseSweep.from_json(str(cfg))
        assert s.template == "t.inp"
        assert s.sweeps.values == {"alpha": [0, 4]}

    def test_missing_template_raises(self):
        with pytest.raises(KeyError):
            CaseSweep.from_dict({
                "output_dir": "out",
                "sweeps": {"alpha": [0]},
            })


# ======================================================================
# generate() 主流程
# ======================================================================

# 最小可用模板
TEMPLATE_TEXT = """\
guiopts begin
aero_alpha 0.000000e+000
aero_beta 0.000000e+000
aero_ma 0.000000e+000
aero_u 0.000000e+000
aero_v 0.000000e+000
aero_w 0.000000e+000
aero_temp 2.880000e+002
aero_pres 1.013250e+005
guiopts end
physics begin
refvel 0.0
reftem 288.15
refpre 101325.0
refden 1.225
reflen 1.0
refmwt 28.97
physics end
tsteps begin
ntstep 50000
cflbot 0.001
tsteps end
"""


@pytest.fixture
def template_path(tmp_path):
    p = tmp_path / "template.inp"
    p.write_text(TEMPLATE_TEXT)
    return p


@pytest.fixture
def base_sweep_dict(template_path, tmp_path):
    return {
        "template": str(template_path),
        "output_dir": str(tmp_path / "cases"),
        "sweeps": {
            "alpha": [0.0, 4.0],
            "mach": [0.6, 0.8],
            "T_inf": [288.15],
            "p_inf": [101325.0],
        },
    }


class TestGenerate:
    def test_total_case_count_is_cartesian(self, base_sweep_dict):
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        assert report.total == 4  # 2 alpha * 2 mach

    def test_each_case_written_to_disk(self, base_sweep_dict):
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        for r in report:
            assert os.path.isfile(r.path)

    def test_round_trip_preserves_alpha_in_generated_inp(self, base_sweep_dict):
        from inp_tool import parse_file
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        # 至少检查一个 case: alpha=4 的某个文件应含 aero_alpha=4
        r0 = report.cases[0]
        inp = parse_file(r0.path)
        # 解析回去的 aero_alpha 应该是 sweep 里的 alpha
        assert inp.get("guiopts", "aero_alpha") in [0.0, 4.0]
        assert inp.get("guiopts", "aero_ma") in [0.6, 0.8]

    def test_overrides_dict_style(self, base_sweep_dict):
        from inp_tool import parse_file
        base_sweep_dict["overrides"] = {"tsteps": {"ntstep": 20000}}
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        for r in report:
            inp = parse_file(r.path)
            assert inp.get("tsteps", "ntstep") == 20000

    def test_overrides_dotted_style(self, base_sweep_dict):
        from inp_tool import parse_file
        base_sweep_dict["overrides"] = {
            "tsteps.ntstep": 20000,
            "tsteps.cflbot": 0.005,
        }
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        for r in report:
            inp = parse_file(r.path)
            assert inp.get("tsteps", "ntstep") == 20000
            assert inp.get("tsteps", "cflbot") == 0.005

    def test_overrides_warn_on_missing_block(self, base_sweep_dict, capsys):
        base_sweep_dict["overrides"] = {"nonexistent_block": {"foo": 1}}
        s = CaseSweep.from_dict(base_sweep_dict)
        generate(s)
        captured = capsys.readouterr()
        assert "nonexistent_block" in captured.err or "warn" in captured.err.lower()

    def test_freestream_disabled_keeps_original_uv(self, base_sweep_dict):
        from inp_tool import parse_file
        base_sweep_dict["freestream"] = {"enabled": False}
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        # 关闭 preset 后,aero_u/v/w 应保留模板原值 0.0
        for r in report:
            inp = parse_file(r.path)
            # alpha/ma 仍被 overrides 直接写入(因为 from_dict 默认会写)
            # 实际: 关闭 preset 时,alpha/beta/ma 也不会被改
            # 检查 aero_u 保持 0
            assert inp.get("guiopts", "aero_u") == 0.0

    def test_dry_run_does_not_write_files(self, base_sweep_dict, tmp_path):
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s, dry_run=True)
        # 报告仍生成,但 output_dir 下不应有 .inp 文件
        out = tmp_path / "cases"
        inps = list(out.glob("*.inp")) if out.exists() else []
        assert inps == []
        assert report.total == 4  # 报告完整

    def test_manifest_written_when_path_set(self, base_sweep_dict):
        import json
        base_sweep_dict["manifest"] = {"path": str(
            (base_sweep_dict["output_dir"]) + "/manifest.json"
        )}
        s = CaseSweep.from_dict(base_sweep_dict)
        generate(s)
        with open(s.manifest_path) as f:
            data = json.load(f)
        assert data["total"] == 4
        assert len(data["cases"]) == 4
        assert "template" in data
        for c in data["cases"]:
            assert "case_id" in c
            assert "params" in c
            assert "applied" in c
            assert "path" in c

    def test_manifest_applied_contains_aero_fields(self, base_sweep_dict, tmp_path):
        import json
        manifest_path = tmp_path / "cases" / "manifest.json"
        base_sweep_dict["manifest"] = {"path": str(manifest_path)}
        s = CaseSweep.from_dict(base_sweep_dict)
        generate(s)
        with open(manifest_path) as f:
            data = json.load(f)
        # 任一 case 的 applied 字典应含 guiopts.aero_alpha
        first = data["cases"][0]
        assert "guiopts.aero_alpha" in first["applied"]
        assert "guiopts.aero_u" in first["applied"]

    def test_naming_format_with_alpha_and_mach(self, base_sweep_dict, tmp_path):
        base_sweep_dict["naming"] = "aoa{alpha:02.0f}_ma{mach:.2f}.inp"
        s = CaseSweep.from_dict(base_sweep_dict)
        report = generate(s)
        names = [os.path.basename(r.path) for r in report]
        # 至少应包含 aoa00_ma0.60.inp 与 aoa04_ma0.80.inp
        assert any("aoa00" in n for n in names)
        assert any("ma0.60" in n for n in names)
        # 文件名不重复
        assert len(names) == len(set(names))
