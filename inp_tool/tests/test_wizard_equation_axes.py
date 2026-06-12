"""
v0.10.0+:Wizard 方程感知步骤集成测试(spec §6.2)

5 组测试覆盖:
1. TestStep4bEquationAxes        — step_4b 3 子问题 + axis 注入
2. TestStep4cOverrides           — step_4c per-case 覆盖
3. TestIncompatibleWarning       — step_4a 显示与 template 不兼容 warning
4. TestStep4bDefaults            — 全 skip / 选 1 axis 的 sweeps 行为
5. TestBackwardCompat            — 既有 wizard 流程(非 Cartesian / 不动 sweeps)
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


# ============================================================
# 共享 template fixture(LAMINAR 模板用于"不兼容"测试)
# ============================================================
@pytest.fixture
def laminar_template(tmp_path):
    p = tmp_path / "laminar.inp"
    p.write_text(textwrap.dedent("""\
        seq.# 1 #vals 31 title eqnset_define
          values 101 1 1 0 1
          values 0 0 0 0 0
          values 1 0
        seq.# 1 #vals 31
        guiopts begin
          aero_ma 0.6
          turbi_lev 1.0
          turbi_len 0.01
        guiopts end
        physics begin
          refvel 204.0
          tnoneq_numeqns 0
        physics end
    """))
    return str(p)


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


# ============================================================
# 1. TestStep4bEquationAxes (4 cases)
# ============================================================
class TestStep4bEquationAxes:
    def test_skip_all_three_axes(self, monkeypatch):
        """Q1/Q2/Q3 全 n → 不注入任何 axis key,sweeps 保持原样。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 5]}}
        monkeypatch.setattr("builtins.input", lambda _: "n")
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert next_step == "step_4a_detect"
        assert new_data["sweeps"] == {"alpha": [0, 5]}

    def test_pick_sst_and_sa(self, monkeypatch):
        """Q1 选 sst + sa → sweeps.turbulence=['sst','sa']。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 5]}}
        responses = iter(["y", "1 2", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert new_data["sweeps"]["turbulence"] == ["sst", "sa"]
        assert new_data["sweeps"]["alpha"] == [0, 5]  # 原有保留

    def test_pick_2t_energy(self, monkeypatch):
        """Q2 选 2T → sweeps.energy=['2t']。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {}}
        responses = iter(["n", "y", "2", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert new_data["sweeps"]["energy"] == ["2t"]

    def test_pick_laminar_with_laminar_template_no_clash(self, monkeypatch):
        """Q1 选 laminar → 即便 template 是 laminar 也不会产生不兼容(本步不查 template)。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {}}
        responses = iter(["y", "5", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4b_equation_axes(data)
        # step_4b 只收 axis,不查 template;intended_axes 含 turbulence='laminar'
        assert new_data["sweeps"]["turbulence"] == ["laminar"]
        assert new_data["intended_axes"]["turbulence"] == "laminar"


# ============================================================
# 2. TestStep4cOverrides (3 cases)
# ============================================================
class TestStep4cOverrides:
    def test_skip_step_4c(self, monkeypatch, laminar_template):
        """Cartesian + sweeps 无 axis → step_4c 跳过,不动 data。"""
        wiz = WizardSweep()
        data = {"mode": "1", "template": laminar_template, "sweeps": {"alpha": [0, 5]}}
        next_step, new_data = wiz.step_4c_equation_overrides(data)
        assert next_step == "step_5_naming"
        assert "turbulence" not in new_data

    def test_sst_override(self, monkeypatch, sst_template):
        """Q0=y + 选 sst + 输 I/L/U → data.turbulence.overrides.sst 含 3 字段。"""
        wiz = WizardSweep()
        data = {"mode": "1", "template": sst_template, "sweeps": {"turbulence": ["sst"]}}
        responses = iter(["y", "1", "0.005", "0.02", "250", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4c_equation_overrides(data)
        assert "turbulence" in new_data
        sst = new_data["turbulence"]["overrides"]["sst"]
        assert sst["I"] == 0.005
        assert sst["L"] == 0.02
        assert sst["U_ref"] == 250.0

    def test_2t_T_vib_override(self, monkeypatch, sst_template):
        """Q0=y + 选 2T + 输 T_trans/T_vib → data.energy_overrides['2T'] 含 2 字段。"""
        wiz = WizardSweep()
        data = {"mode": "1", "template": sst_template, "sweeps": {"energy": ["2t"]}}
        responses = iter(["y", "1", "300", "200"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4c_equation_overrides(data)
        eo = new_data.get("energy_overrides", {})
        assert eo.get("2T", {}).get("T_trans") == 300.0
        assert eo.get("2T", {}).get("T_vib") == 200.0


# ============================================================
# 3. TestIncompatibleWarning (2 cases)
# ============================================================
class TestIncompatibleWarning:
    def test_laminar_template_plus_sst_axis_shows_warning(
        self, laminar_template, capsys,
    ):
        """intended_axes.turbulence='sst' + laminar 模板 → step_4a 显示 ⚠ warning。"""
        wiz = WizardSweep()
        data = {
            "template": laminar_template,
            "intended_axes": {"turbulence": "sst"},
        }
        wiz.step_4a_detect(data)
        out = capsys.readouterr().out
        assert "⚠" in out
        # 警告文本应含 sst/SST 和 laminar
        assert ("SST" in out or "sst" in out) and "laminar" in out.lower()

    def test_sst_plus_2t_both_warn(self, laminar_template, capsys):
        """intended_axes 同时有 sst + 2t → 2 条 warning bullet(sst 撞 laminar,2t 撞 tnoneq=0)。"""
        wiz = WizardSweep()
        data = {
            "template": laminar_template,
            "intended_axes": {"turbulence": "sst", "energy": "2t"},
        }
        wiz.step_4a_detect(data)
        out = capsys.readouterr().out
        # 1 个 ⚠ 段标题 + 2 条 warning(以 "- " 开头)
        assert "⚠" in out
        bullet_count = sum(
            1 for line in out.splitlines() if line.strip().startswith("- ")
        )
        assert bullet_count >= 2


# ============================================================
# 4. TestStep4bDefaults (2 cases)
# ============================================================
class TestStep4bDefaults:
    def test_all_n_preserves_sweeps(self, monkeypatch):
        """全部 Q1/Q2/Q3 选 n → sweeps 不变(等价 v0.10.0 老路径)。"""
        wiz = WizardSweep()
        original_sweeps = {"alpha": [0, 5], "mach": [0.6, 0.8]}
        data = {"mode": "1", "sweeps": dict(original_sweeps)}
        monkeypatch.setattr("builtins.input", lambda _: "n")
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert new_data["sweeps"] == original_sweeps

    def test_select_one_axis_injects_key(self, monkeypatch):
        """只选 1 axis → sweeps 只含该 axis key。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 5]}}
        responses = iter(["n", "n", "y", "3"])  # 只 Q3 选 multi-temp
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = wiz.step_4b_equation_axes(data)
        sweeps = new_data["sweeps"]
        assert "gas" in sweeps and sweeps["gas"] == ["multi-temp"]
        # 没选 turbulence / energy → 不注入对应 key
        assert "turbulence" not in sweeps
        assert "energy" not in sweeps


# ============================================================
# 5. TestBackwardCompat (2 cases)
# ============================================================
class TestBackwardCompat:
    def test_explicit_mode_skips_equation_axes(self):
        """mode='2'(explicit) → step_4b 静默跳到 step_4a_detect,data 不变。"""
        wiz = WizardSweep()
        data = {"mode": "2", "sweeps": [{"alpha": 0}]}
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert next_step == "step_4a_detect"
        # sweeps 是 list(不是 dict)— step_4b 不应改结构
        assert new_data["sweeps"] == [{"alpha": 0}]

    def test_csv_mode_skips_equation_axes(self):
        """mode='4'(CSV) → step_4b 静默跳到 step_4a_detect。"""
        wiz = WizardSweep()
        data = {"mode": "4", "csv": "/tmp/cases.csv"}
        next_step, new_data = wiz.step_4b_equation_axes(data)
        assert next_step == "step_4a_detect"
        assert "csv" in new_data
        # 无新 sweeps key
        assert "sweeps" not in new_data or new_data.get("sweeps") == {}
