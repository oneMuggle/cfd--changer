"""
mcfd.inp sweep YAML 配置 — Phase A RED

测试目标:
- CaseSweep.from_yaml(path) 加载 YAML 配置文件
- 缺 pyyaml 时给清晰 ImportError 提示
- YAML 内容与 from_dict 等价
- 错误格式(空文件、坏 YAML)报清晰错误
"""
from __future__ import annotations
import json
import pytest
import yaml

from inp_tool.sweep import CaseSweep


YAML_SAMPLE = """
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
sweeps:
  alpha: [0.0, 4.0, 8.0]
  beta:  [0.0]
  mach:  [0.60, 0.80]
  T_inf: [288.15]
  p_inf: [101325.0]
naming: "case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}.inp"
manifest:
  path: examples/sweep_cases/manifest.json
freestream:
  enabled: true
  gamma: 1.4
  R: 287.05
"""


@pytest.fixture
def yaml_file(tmp_path):
    p = tmp_path / "sweep.yaml"
    p.write_text(YAML_SAMPLE)
    return p


class TestFromYaml:
    def test_loads_yaml(self, yaml_file):
        cs = CaseSweep.from_yaml(str(yaml_file))
        assert cs.template == "examples/mcfd_v2_modified.inp"
        assert cs.output_dir == "examples/sweep_cases"
        assert cs.sweeps.values["alpha"] == [0.0, 4.0, 8.0]
        assert cs.sweeps.values["beta"] == [0.0]
        assert cs.sweeps.values["mach"] == [0.60, 0.80]
        assert cs.freestream is not None
        assert cs.freestream.gamma == 1.4
        assert cs.freestream.R == 287.05

    def test_yaml_equivalent_to_json(self, yaml_file, tmp_path):
        json_path = tmp_path / "sweep.json"
        json_data = yaml.safe_load(YAML_SAMPLE)
        json_path.write_text(json.dumps(json_data))

        cs_y = CaseSweep.from_yaml(str(yaml_file))
        cs_j = CaseSweep.from_json(str(json_path))
        assert cs_y.template == cs_j.template
        assert cs_y.output_dir == cs_j.output_dir
        assert cs_y.sweeps.values == cs_j.sweeps.values
        assert cs_y.naming == cs_j.naming
        assert cs_y.manifest_path == cs_j.manifest_path

    def test_yaml_unicode_strings_preserved(self, tmp_path):
        p = tmp_path / "cn.yaml"
        p.write_text("""
template: 模板.inp
output_dir: 算例
sweeps:
  alpha: [0]
naming: "案例_{alpha}"
""", encoding="utf-8")
        cs = CaseSweep.from_yaml(str(p))
        assert cs.template == "模板.inp"
        assert cs.output_dir == "算例"
        assert cs.naming == "案例_{alpha}"

    def test_yaml_missing_template_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("output_dir: out\nsweeps:\n  alpha: [0]\n")
        with pytest.raises(KeyError, match="template"):
            CaseSweep.from_yaml(str(p))

    def test_yaml_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        with pytest.raises(KeyError, match="template"):
            CaseSweep.from_yaml(str(p))

    def test_yaml_invalid_syntax_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("template: foo\n  output_dir: bar\n  sweeps: [unclosed")
        with pytest.raises(yaml.YAMLError):
            CaseSweep.from_yaml(str(p))

    def test_yaml_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            CaseSweep.from_yaml(str(tmp_path / "nonexistent.yaml"))

    def test_yaml_freestream_disabled(self, tmp_path):
        p = tmp_path / "no_fs.yaml"
        p.write_text("""
template: t.inp
output_dir: out
sweeps:
  alpha: [0]
freestream:
  enabled: false
""")
        cs = CaseSweep.from_yaml(str(p))
        assert cs.freestream is None
