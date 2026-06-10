"""sweep + pbs 集成测试 - Task 9-12"""
import json
import os
from pathlib import Path

import pytest

from inp_tool.pbs import PbsConfig
from inp_tool.sweep import CaseSweep


def _cs_from(**kwargs):
    """通过 from_dict 构造 CaseSweep(specs 自动从 sweeps 字段生成)。"""
    d = {
        "template": kwargs.get("template", "t.inp"),
        "output_dir": kwargs.get("output_dir", "out"),
        "sweeps": kwargs.get("sweeps_dict", {"alpha": [0, 4]}),
    }
    if "naming" in kwargs:
        d["naming"] = kwargs["naming"]
    if "source_dir" in kwargs:
        d["source_dir"] = kwargs["source_dir"]
    if "pbs_dict" in kwargs:
        d["pbs"] = kwargs["pbs_dict"]
    if "manifest_path" in kwargs:
        d["manifest"] = {"path": kwargs["manifest_path"]}
    return CaseSweep.from_dict(d)


class TestCaseSweepPbsField:
    def test_default_pbs_is_none(self):
        cs = _cs_from()
        assert cs.pbs is None

    def test_from_dict_parses_pbs(self):
        d = {
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
            "pbs": {"enabled": True, "naming": "Mars-{alpha}"},
        }
        cs = CaseSweep.from_dict(d)
        assert cs.pbs is not None
        assert isinstance(cs.pbs, PbsConfig)
        assert cs.pbs.enabled is True
        assert cs.pbs.naming == "Mars-{alpha}"

    def test_from_dict_without_pbs_field(self):
        d = {
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0, 4]},
        }
        cs = CaseSweep.from_dict(d)
        assert cs.pbs is None

    def test_from_yaml_with_pbs(self, tmp_path):
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            "template: t.inp\n"
            "output_dir: out\n"
            "sweeps:\n"
            "  alpha: [0, 4]\n"
            "pbs:\n"
            "  enabled: true\n"
            "  naming: 'Mars-{alpha}'\n"
        )
        cs = CaseSweep.from_yaml(str(yaml_file))
        assert cs.pbs is not None
        assert cs.pbs.naming == "Mars-{alpha}"


def _make_source(tmp_path, with_physics=True, with_pbs=True):
    src = tmp_path / "source"
    src.mkdir()
    mcfd = src / "mcfd.inp"
    text = "tsteps begin\n  ntstep = 100\ntsteps end\n"
    if with_physics:
        text += "physics begin\n  eqnset = euler\nphysics end\n"
    mcfd.write_text(text)
    (src / "cellsin.bin").write_bytes(b"\x00" * 50)
    (src / "nodesin.bin").write_bytes(b"\x00" * 50)
    (src / "cgrpsin.bin.1").write_bytes(b"\x00" * 50)
    (src / "C.dat").write_text("data")
    (src / "mcfd.bc").write_text("bc")
    (src / "mcfd.grp").write_text("grp")
    if with_pbs:
        (src / "run_cfdpp.pbs").write_text(
            "#!/bin/bash\n"
            "#PBS -N Marspathfinder-Ini\n"
            "#PBS -l nodes=1:ppn=48\n"
            "echo hi\n"
        )
    return str(src)


class TestGenerateValidation:
    def test_validation_warns_on_missing_block(self, tmp_path):
        from inp_tool.sweep import generate
        src = _make_source(tmp_path, with_physics=False)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            sweeps_dict={"alpha": [0]},
            naming="case_{alpha}",
        )
        # v0.9.0:缺失 block 降为 warning(向后兼容),generate 不抛
        report = generate(cs)
        assert report.total == 1

    def test_validation_warnings_dont_block(self, tmp_path):
        from inp_tool.sweep import generate
        src = _make_source(tmp_path, with_pbs=False)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            naming="case_{alpha}",
        )
        report = generate(cs)
        assert report.total == 2

    def test_no_source_dir_skips_validation(self, tmp_path):
        from inp_tool.sweep import generate
        template = tmp_path / "t.inp"
        template.write_text("tsteps begin\n  ntstep = 100\ntsteps end\n")
        cs = _cs_from(
            template=str(template),
            output_dir=str(tmp_path / "out"),
            naming="case_{alpha}",
        )
        report = generate(cs)
        assert report.total == 2


class TestGeneratePbsWrite:
    def test_per_case_pbs_written_with_shortname(self, tmp_path):
        from inp_tool.sweep import generate
        src = _make_source(tmp_path, with_pbs=True)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            sweeps_dict={"alpha": [0, 4], "mach": [0.6]},
            pbs_dict={"enabled": True},
            naming="case_{alpha}",
        )
        report = generate(cs)
        assert report.total == 2
        for case in report.cases:
            case_dir = Path(case.path)
            pbs_file = case_dir / "run_cfdpp.pbs"
            assert pbs_file.exists(), f"pbs 缺失 in {case_dir}"
            content = pbs_file.read_text()
            assert "Marspath_a" in content
            assert "Marspathfinder-Ini" not in content
            assert "#PBS -l nodes=1:ppn=48" in content

    def test_pbs_disabled_no_pbs_written(self, tmp_path):
        from inp_tool.sweep import generate
        src = _make_source(tmp_path, with_pbs=True)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            pbs_dict={"enabled": False},
            naming="case_{alpha}",
        )
        report = generate(cs)
        for case in report.cases:
            case_dir = Path(case.path)
            pbs_file = case_dir / "run_cfdpp.pbs"
            if pbs_file.exists():
                content = pbs_file.read_text()
                # enabled=False → write_pbs 不调用 → 内容是源 hardlink
                assert "Marspathfinder-Ini" in content

    def test_user_template_pbs_name(self, tmp_path):
        from inp_tool.sweep import generate
        src = _make_source(tmp_path, with_pbs=True)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            pbs_dict={"enabled": True, "naming": "MyCase-{alpha}"},
            naming="case_{alpha}",
        )
        report = generate(cs)
        names = []
        for case in report.cases:
            content = (Path(case.path) / "run_cfdpp.pbs").read_text()
            for line in content.splitlines():
                if line.startswith("#PBS -N"):
                    names.append(line)
        assert any("MyCase-0" in n for n in names)
        assert any("MyCase-4" in n for n in names)


class TestManifestPbsName:
    def _make_source_simple(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "mcfd.inp").write_text(
            "tsteps begin\n  ntstep = 100\ntsteps end\n"
            "physics begin\n  eqnset = euler\nphysics end\n"
        )
        (src / "cellsin.bin").write_bytes(b"\x00" * 50)
        (src / "nodesin.bin").write_bytes(b"\x00" * 50)
        (src / "cgrpsin.bin.1").write_bytes(b"\x00" * 50)
        (src / "C.dat").write_text("data")
        (src / "mcfd.bc").write_text("bc")
        (src / "mcfd.grp").write_text("grp")
        (src / "run_cfdpp.pbs").write_text("#PBS -N OriginalName\n")
        return str(src)

    def test_manifest_contains_pbs_name_per_case(self, tmp_path):
        from inp_tool.sweep import generate
        src = self._make_source_simple(tmp_path)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            pbs_dict={"enabled": True},
            manifest_path=str(tmp_path / "out" / "manifest.json"),
            naming="case_{alpha}",
        )
        report = generate(cs)
        manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
        assert manifest.get("pbs_enabled") is True
        for c in manifest["cases"]:
            assert "pbs_name" in c
            assert c["pbs_name"].startswith("Original")
            assert c["pbs_name"].endswith("_a00") or c["pbs_name"].endswith("_a04")

    def test_manifest_no_pbs_when_disabled(self, tmp_path):
        from inp_tool.sweep import generate
        src = self._make_source_simple(tmp_path)
        cs = _cs_from(
            template=f"{src}/mcfd.inp",
            output_dir=str(tmp_path / "out"),
            source_dir=src,
            pbs_dict={"enabled": False},
            manifest_path=str(tmp_path / "out" / "manifest.json"),
            naming="case_{alpha}",
        )
        report = generate(cs)
        manifest = json.loads((tmp_path / "out" / "manifest.json").read_text())
        # pbs 关闭时,顶层 pbs_enabled 字段不写
        assert "pbs_enabled" not in manifest
        for c in manifest["cases"]:
            assert "pbs_name" not in c
