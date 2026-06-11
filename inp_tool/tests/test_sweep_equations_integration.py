"""v0.9.1: sweep + equations preset 集成测试"""
import json
from pathlib import Path

import pytest

from inp_tool.sweep import CaseSweep, generate, TurbulenceInit
from inp_tool.parser import parse_file
from inp_tool.equations import (
    detect_equations, EnergyModel, GasModel, TurbulenceModel,
    SSTKOmegaPreset, TwoTemperaturePreset,
)


COMPARE_DIR = Path(__file__).parent / "fixtures" / "compare"
SST_FILE = COMPARE_DIR / "可压缩理想气体+2方程SST mcfd.inp"
TWOT_FILE = COMPARE_DIR / "双温模型+层流mcfd.inp"
LAMINAR_FILE = COMPARE_DIR / "可压缩理想气体+层流mcfd.inp"


# ============================================================
# CaseSweep.from_dict — turbulence preset 解析
# ============================================================
class TestFromDictTurbulence:
    def test_turbulence_enabled_parses_preset(self, tmp_path):
        """YAML turbulence: {enabled: true, I, L, U_ref} → TurbulenceInit(v0.10.0)"""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {"enabled": True, "I": 0.01, "L": 0.01, "U_ref": 204.0},
        })
        assert cs.turbulence is not None
        # v0.10.0:turbulence 字段是 TurbulenceInit(原 v0.9.1 是 TurbulencePresetBase)
        assert isinstance(cs.turbulence, TurbulenceInit)
        assert cs.turbulence.I == 0.01
        assert cs.turbulence.L == 0.01
        assert cs.turbulence.U_ref == 204.0

    def test_turbulence_disabled_skips(self, tmp_path):
        """enabled: false → preset 为 None"""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {"enabled": False, "I": 0.01, "L": 0.01},
        })
        assert cs.turbulence is None

    def test_turbulence_missing_I_raises(self, tmp_path):
        """v0.9.1 behavior preserved: missing I → KeyError (spec §4.6)."""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        d = {
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {"L": 0.01, "U_ref": 204.0},  # missing I
        }
        with pytest.raises(KeyError, match="I and L are required"):
            CaseSweep.from_dict(d)

    def test_turbulence_missing_L_raises(self, tmp_path):
        """v0.9.1 behavior preserved: missing L → KeyError (spec §4.6)."""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        d = {
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {"I": 0.01, "U_ref": 204.0},  # missing L
        }
        with pytest.raises(KeyError, match="I and L are required"):
            CaseSweep.from_dict(d)

    def test_turbulence_override_missing_I_raises(self, tmp_path):
        """每个 override 也必须自带 I/L(同顶层严格策略)。"""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        d = {
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {
                "I": 0.01, "L": 0.01, "U_ref": 100.0,
                "overrides": {"sst": {"L": 0.02}},  # missing I
            },
        }
        with pytest.raises(KeyError, match="I and L are required"):
            CaseSweep.from_dict(d)

    def test_turbulence_on_laminar_template_accepted_in_v010(self, tmp_path):
        """v0.10.0:层流 template + turbulence 块不再在 from_dict 抛错;
        由 generate() 按 per-case 解析时识别 LAMINAR → _resolve_turb_init 返回 None。
        """
        if not LAMINAR_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(LAMINAR_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "turbulence": {"enabled": True, "I": 0.01, "L": 0.01, "U_ref": 100},
        })
        # TurbulenceInit 容器就绪,实际写入由 generate() 按 model 解析
        assert isinstance(cs.turbulence, TurbulenceInit)
        assert cs.turbulence.I == 0.01

    def test_no_turbulence_block_means_none(self, tmp_path):
        """没有 turbulence: 字段 → 默认 None(向后兼容)"""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(SST_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
        })
        assert cs.turbulence is None


# ============================================================
# CaseSweep.from_dict — two_temperature preset 解析
# ============================================================
class TestFromDictTwoTemperature:
    def test_2t_enabled_parses(self, tmp_path):
        if not TWOT_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(TWOT_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "two_temperature": {"T_trans": 300.0, "T_vib": 200.0},
        })
        assert cs.two_temperature is not None
        assert isinstance(cs.two_temperature, TwoTemperaturePreset)
        assert cs.two_temperature.T_trans == 300.0
        assert cs.two_temperature.T_vib == 200.0

    def test_2t_disabled(self, tmp_path):
        if not TWOT_FILE.exists():
            pytest.skip("compare sample 缺失")
        cs = CaseSweep.from_dict({
            "template": str(TWOT_FILE),
            "output_dir": str(tmp_path),
            "sweeps": {"alpha": [0]},
            "two_temperature": {"enabled": False, "T_trans": 300.0, "T_vib": 200.0},
        })
        assert cs.two_temperature is None

    def test_2t_missing_Tvib_raises(self, tmp_path):
        if not TWOT_FILE.exists():
            pytest.skip("compare sample 缺失")
        with pytest.raises(KeyError, match="T_trans.*T_vib"):
            CaseSweep.from_dict({
                "template": str(TWOT_FILE),
                "output_dir": str(tmp_path),
                "sweeps": {"alpha": [0]},
                "two_temperature": {"T_trans": 300.0},
            })


# ============================================================
# generate() 应用 preset
# ============================================================
class TestGenerateApplyTurbulence:
    def test_generate_writes_turbi_fields(self, tmp_path):
        """sweep + turbulence preset → 每个生成的 case 都有 guiopts.turbi_lev"""
        if not SST_FILE.exists():
            pytest.skip("compare sample 缺失")
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(SST_FILE),
            "output_dir": str(out),
            "sweeps": {"alpha": [0, 4]},
            "turbulence": {"I": 0.01, "L": 0.01, "U_ref": 204.0},
            "freestream": {"enabled": False},   # 隔离测试,只验证 turbulence
        })
        report = generate(cs)
        assert report.total == 2
        # 读其中一个 case,验证 guiopts.turbi_lev 写了 k = 1.5*(204*0.01)^2 ≈ 6.24
        cases = sorted(out.glob("*.inp"))
        assert len(cases) == 2
        inp = parse_file(str(cases[0]))
        gb = inp.get_block("guiopts")
        assert gb is not None
        k = gb.get("turbi_lev")
        assert k is not None and abs(k - 6.2424) < 1e-3


class TestGenerateApplyTwoTemperature:
    def test_generate_writes_2t_fields(self, tmp_path):
        """sweep + 2t preset → 每个 case 写 tnoneq_numeqns=1 + reftem + vibtem"""
        if not TWOT_FILE.exists():
            pytest.skip("compare sample 缺失")
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(TWOT_FILE),
            "output_dir": str(out),
            "sweeps": {"alpha": [0]},
            "two_temperature": {"T_trans": 350.0, "T_vib": 250.0},
            "freestream": {"enabled": False},
        })
        report = generate(cs)
        assert report.total == 1
        case = next(out.glob("*.inp"))
        inp = parse_file(str(case))
        pb = inp.get_block("physics")
        assert pb is not None
        assert pb.get("tnoneq_numeqns") == 1
        assert pb.get("reftem") == 350.0
        assert pb.get("vibtem") == 250.0


# ============================================================
# WizardModifyFile.step_1a_detect — 烟测
# ============================================================
def test_wizard_modify_file_has_detect_step():
    """WizardModifyFile.steps 包含 step_1a_detect"""
    from inp_tool.wizard import WizardModifyFile
    assert "step_1a_detect" in WizardModifyFile.steps


def test_wizard_sweep_has_detect_step():
    """WizardSweep.steps 包含 step_4a_detect"""
    from inp_tool.wizard import WizardSweep
    assert "step_4a_detect" in WizardSweep.steps


def test_wizard_modify_step_1a_detect_prints_report(capsys):
    """step_1a_detect 调用时打印 detect 报告 + 推荐字段"""
    if not TWOT_FILE.exists():
        pytest.skip("compare sample 缺失")
    from inp_tool.wizard import WizardModifyFile
    w = WizardModifyFile()
    result = w.step_1a_detect({"file": str(TWOT_FILE)})
    captured = capsys.readouterr()
    out = captured.out
    assert "方程系统检测" in out or "Detection" in out
    assert "2T" in out
    assert "multi-temp" in out
    # 推荐字段段(双温 → tnoneq_numeqns + reftem + vibtem)
    assert "推荐" in out or "Recommended" in out
    # 流转到 step_2
    assert result == ("step_2_select_fields", {})


def test_wizard_sweep_step_4a_detect_prints_report(capsys):
    if not SST_FILE.exists():
        pytest.skip("compare sample 缺失")
    from inp_tool.wizard import WizardSweep
    w = WizardSweep()
    result = w.step_4a_detect({"template": str(SST_FILE)})
    captured = capsys.readouterr()
    out = captured.out
    assert "k-omega-sst" in out
    assert result == ("step_5_naming", {})
