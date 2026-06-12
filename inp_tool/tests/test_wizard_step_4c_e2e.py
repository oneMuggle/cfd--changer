"""
C1 回归测试:step_4c 写入 data["turbulence"] / data["energy_overrides"]
必须真的传到 CaseSweep,否则用户在 wizard 输的 I/L/U_ref / 温度被丢弃。
"""
from __future__ import annotations
import textwrap
import pytest
from inp_tool.wizard import WizardSweep
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


@pytest.fixture
def sst_template(tmp_path):
    p = tmp_path / "sst.inp"
    p.write_text(textwrap.dedent("""\
        seq.# 1 #vals 31 title eqnset_define
          values 101 1 1 2 3
          values 0 0 0 0 0
          values 1 0
        seq.# 1 #vals 31
        guiopts begin
          aero_ma 0.6
          turbi_lev 1.5
          turbi_len 0.02
        guiopts end
        physics begin
          refvel 250.0
          tnoneq_numeqns 0
        physics end
    """))
    return str(p)


class TestStep4cPassesToCaseSweep:
    """C1:step_4c 产出必须真传到 CaseSweep,否则 per-case 覆盖是死端。"""

    def test_turbulence_override_passes_to_case_sweep(
        self, monkeypatch, sst_template,
    ):
        """turbulence.overrides.sst = {I, L, U_ref} 须出现在 CaseSweep.turbulence.overrides。"""
        from inp_tool.sweep import CaseSweep
        wiz = WizardSweep()
        data = {
            "mode": "1",
            "template": sst_template,
            "sweeps": {"turbulence": ["sst", "sa"]},
        }
        responses = iter([
            "y",        # Q0
            "1",        # Q1 选 sst
            "0.005",    # I
            "0.02",     # L
            "250",      # U_ref
            "n",        # 不再来
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        _, new_data = wiz.step_4c_equation_overrides(data)
        # 把 wizard 产出喂给 CaseSweep
        cfg = {
            "template": sst_template,
            "output_dir": "/tmp/cs_out_c1",
            "sweeps": new_data.get("sweeps", {}),
        }
        if new_data.get("turbulence"):
            cfg["turbulence"] = new_data["turbulence"]
        if new_data.get("energy_overrides"):
            cfg["energy_overrides"] = new_data["energy_overrides"]
        cs = CaseSweep.from_dict(cfg)
        # 关键断言:turbulence.overrides.sst 真在 CaseSweep 上
        assert cs.turbulence is not None
        assert "sst" in cs.turbulence.overrides
        sst_init = cs.turbulence.overrides["sst"]
        assert sst_init.I == pytest.approx(0.005)
        assert sst_init.L == pytest.approx(0.02)
        assert sst_init.U_ref == pytest.approx(250.0)

    def test_energy_overrides_passes_to_case_sweep(
        self, monkeypatch, sst_template,
    ):
        """energy_overrides['2T'] = {T_trans, T_vib} 须出现在 CaseSweep.energy_overrides。"""
        from inp_tool.sweep import CaseSweep
        wiz = WizardSweep()
        data = {
            "mode": "1",
            "template": sst_template,
            "sweeps": {"energy": ["2t"]},
        }
        responses = iter([
            "y",     # Q0
            "1",     # Q2 选 2T
            "300",   # T_trans
            "200",   # T_vib
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        _, new_data = wiz.step_4c_equation_overrides(data)
        cfg = {
            "template": sst_template,
            "output_dir": "/tmp/cs_out_c1",
            "sweeps": new_data.get("sweeps", {}),
        }
        if new_data.get("turbulence"):
            cfg["turbulence"] = new_data["turbulence"]
        if new_data.get("energy_overrides"):
            cfg["energy_overrides"] = new_data["energy_overrides"]
        cs = CaseSweep.from_dict(cfg)
        # 关键断言:energy_overrides['2T'] 真在 CaseSweep 上
        assert cs.energy_overrides is not None
        assert "2T" in cs.energy_overrides
        two_t = cs.energy_overrides["2T"]
        assert two_t["T_trans"] == pytest.approx(300.0)
        assert two_t["T_vib"] == pytest.approx(200.0)


# ============================================================
# C1 真端到端:step_6_preview 必须把 data["turbulence"] / ["energy_overrides"]
# 喂给 CaseSweep.from_dict,否则用户在 wizard 输的覆盖被静默丢弃。
# ============================================================
class TestStep6PreviewForwardsOverrides:
    """C1 修复端到端验证。"""

    def _patch_generate(self, monkeypatch):
        """patch generate() 捕获传给它的 CaseSweep 实例。

        wizard.py 内部 `from .sweep import CaseSweep, generate, ...`,所以要
        patch 源模块 `inp_tool.sweep.generate`,这样 step_6_preview 内
        import 的引用才能被替换。
        """
        from inp_tool import sweep
        captured = {}

        def fake_generate(cs, force=False):
            captured["cs"] = cs
            captured["force"] = force
            class _Stub:
                total = 0
                cases = []
            return _Stub()
        monkeypatch.setattr(sweep, "generate", fake_generate)
        return captured

    def _base_case(self, tmp_path):
        base = tmp_path / "base"
        base.mkdir()
        (base / "mcfd.inp").write_text(
            "guiopts begin\naero_alpha 0.0\nguiopts end\n"
        )
        (base / "grid.bin").write_bytes(b"G")
        (base / "config.txt").write_text("c")
        return str(base)

    def test_step_6_preview_forwards_turbulence_override(
        self, monkeypatch, tmp_path,
    ):
        """data 含 turbulence.overrides → CaseSweep.turbulence.overrides 真在。"""
        wiz = WizardSweep()
        data = {
            "source_dir": self._base_case(tmp_path),
            "template": str(tmp_path / "base" / "mcfd.inp"),
            "output_dir": str(tmp_path / "cases"),
            "copy_strategy": "hardlink",
            "mode": "1",
            "sweeps": {"turbulence": ["sst", "sa"]},
            "turbulence": {
                "I": 0.01, "L": 0.01, "U_ref": 204.0,
                "overrides": {
                    "sst": {"I": 0.005, "L": 0.02, "U_ref": 250.0},
                },
            },
            "naming": "case_{turbulence}",
            "pbs_enabled": False,
        }
        captured = self._patch_generate(monkeypatch)
        # step_6_preview 内部 2 个 confirm:1) 确认生成? default=True → "y";
        # 2) 强制覆盖? default=False → "n"。我们的 fake_generate 不写盘,无所谓。
        responses = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        wiz.step_6_preview(data)
        cs = captured.get("cs")
        assert cs is not None, "step_6_preview 没调 generate()"
        assert cs.turbulence is not None, "turbulence 被 step_6_preview 丢弃"
        assert "sst" in cs.turbulence.overrides
        sst = cs.turbulence.overrides["sst"]
        assert sst.I == pytest.approx(0.005)
        assert sst.L == pytest.approx(0.02)
        assert sst.U_ref == pytest.approx(250.0)

    def test_step_6_preview_forwards_energy_overrides(
        self, monkeypatch, tmp_path,
    ):
        """data 含 energy_overrides → CaseSweep.energy_overrides 真在。"""
        wiz = WizardSweep()
        data = {
            "source_dir": self._base_case(tmp_path),
            "template": str(tmp_path / "base" / "mcfd.inp"),
            "output_dir": str(tmp_path / "cases"),
            "copy_strategy": "hardlink",
            "mode": "1",
            "sweeps": {"energy": ["2t"]},
            "energy_overrides": {
                "2T": {"T_trans": 300.0, "T_vib": 200.0},
            },
            "naming": "case_{energy}",
            "pbs_enabled": False,
        }
        captured = self._patch_generate(monkeypatch)
        # step_6_preview 内部 2 个 confirm:1) 确认生成? default=True → "y";
        # 2) 强制覆盖? default=False → "n"。我们的 fake_generate 不写盘,无所谓。
        responses = iter(["y", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        wiz.step_6_preview(data)
        cs = captured.get("cs")
        assert cs is not None
        assert cs.energy_overrides is not None, "energy_overrides 被丢弃"
        assert "2T" in cs.energy_overrides
        assert cs.energy_overrides["2T"]["T_trans"] == pytest.approx(300.0)
        assert cs.energy_overrides["2T"]["T_vib"] == pytest.approx(200.0)
