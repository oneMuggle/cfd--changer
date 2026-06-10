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
