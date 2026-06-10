"""pbs 模块单测 - Task 2: dataclass + from_dict"""
import pytest
from inp_tool.pbs import PbsConfig, PbsIssue


class TestPbsConfig:
    def test_defaults(self):
        c = PbsConfig()
        assert c.enabled is True
        assert c.template is None
        assert c.naming == ""
        assert c.naming_ext == ""
        assert c.detect_basename is True
        assert c.basename_max_len == 8

    def test_from_dict_full(self):
        d = {
            "enabled": False,
            "template": "/path/to/source.pbs",
            "naming": "Mars-{alpha}",
            "naming_ext": ".pbs",
            "detect_basename": False,
            "basename_max_len": 12,
        }
        c = PbsConfig.from_dict(d)
        assert c.enabled is False
        assert c.template == "/path/to/source.pbs"
        assert c.naming == "Mars-{alpha}"
        assert c.naming_ext == ".pbs"
        assert c.detect_basename is False
        assert c.basename_max_len == 12

    def test_from_dict_empty(self):
        c = PbsConfig.from_dict({})
        assert c.enabled is True  # 默认
        assert c.template is None
        assert c.naming == ""

    def test_from_dict_partial(self):
        c = PbsConfig.from_dict({"naming": "Case-{alpha}"})
        assert c.naming == "Case-{alpha}"
        assert c.enabled is True  # 其他走默认


class TestPbsIssue:
    def test_construction(self):
        issue = PbsIssue(
            code="MISSING_MCFD_INP",
            severity="error",
            path="/path/to/source",
            message="找不到 mcfd.inp",
        )
        assert issue.code == "MISSING_MCFD_INP"
        assert issue.severity == "error"
        assert issue.path == "/path/to/source"
        assert issue.message == "找不到 mcfd.inp"


class TestDetectPbsTemplate:
    def test_finds_run_pbs(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        (tmp_path / "run_cfdpp.pbs").write_text("#!/bin/bash\n#PBS -N test\n")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        assert result == str(tmp_path / "run_cfdpp.pbs")

    def test_no_pbs_returns_none(self, tmp_path):
        (tmp_path / "mcfd.inp").write_text("placeholder")
        from inp_tool.pbs import detect_pbs_template
        assert detect_pbs_template(str(tmp_path)) is None

    def test_multiple_pbs_returns_first_with_warning(self, tmp_path, capsys):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        (tmp_path / "run_b.pbs").write_text("#PBS -N b")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path))
        # 字母序第一个 run_a.pbs
        assert result == str(tmp_path / "run_a.pbs")
        captured = capsys.readouterr()
        # warning 输出到 stderr(spec §6 + 计划 Task 3)
        assert "多个" in captured.err or "warning" in captured.err.lower()

    def test_explicit_template_overrides(self, tmp_path):
        (tmp_path / "run_a.pbs").write_text("#PBS -N a")
        explicit = tmp_path / "custom.pbs"
        explicit.write_text("#PBS -N custom")
        from inp_tool.pbs import detect_pbs_template
        result = detect_pbs_template(str(tmp_path), explicit_template=str(explicit))
        assert result == str(explicit)
