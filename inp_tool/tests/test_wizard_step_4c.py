"""
v0.10.0+:WizardSweep.step_4c_equation_overrides 测试

per-case 覆盖 I/L/U_ref(turbulence)或温度(energy)。
触发条件:Cartesian + step_4b 选了至少 1 axis。
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
def template_path(tmp_path):
    """模板含 guiopts/physics 字段,供 _read_template_value 取默认值。"""
    p = tmp_path / "mcfd.inp"
    p.write_text(textwrap.dedent("""\
        guiopts begin
          aero_alpha 0.0
          turbi_lev 1.5
          turbi_len 0.02
        guiopts end
        physics begin
          refvel 250.0
          reftem 300.0
        physics end
    """))
    return str(p)


def _call_step(wiz, data):
    return wiz.step_4c_equation_overrides(data)


class TestStep4cGate:
    """非 Cartesian 或无 axis → 静默跳到 step_5_naming。"""

    def test_skip_when_not_cartesian(self, template_path):
        """mode='2' → 跳到 step_5_naming,不动 data。"""
        wiz = WizardSweep()
        data = {"mode": "2", "template": template_path, "sweeps": {"turbulence": ["sst"]}}
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_5_naming"
        assert "turbulence" not in new_data

    def test_skip_when_no_axis_selected(self, template_path):
        """mode='1' 但 sweeps 无方程 axis → 跳到 step_5_naming。"""
        wiz = WizardSweep()
        data = {"mode": "1", "template": template_path, "sweeps": {"alpha": [0, 5]}}
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_5_naming"
        assert "turbulence" not in new_data


class TestStep4cQ0No:
    """Q0 选 n → 跳到 step_5_naming,无 overrides。"""

    def test_q0_n_skips(self, monkeypatch, template_path):
        """Q0=n → next=step_5_naming,data 无 turbulence。"""
        wiz = WizardSweep()
        data = {
            "mode": "1", "template": template_path,
            "sweeps": {"turbulence": ["sst"]},
        }
        monkeypatch.setattr("builtins.input", lambda _: "n")
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_5_naming"
        assert "turbulence" not in new_data


class TestStep4cTurbulenceOverride:
    """Q0=y + Q1 选 sst + 输 I/L/U → data.turbulence.overrides.sst。"""

    def test_sst_override_with_template_defaults(self, monkeypatch, template_path):
        """Q0=y + Q1 选 sst + 输 I/L/U_ref → turbulence.overrides.sst = {...}。"""
        wiz = WizardSweep()
        data = {
            "mode": "1", "template": template_path,
            "sweeps": {"turbulence": ["sst", "sa"]},
        }
        # 顺序:y, 1 (sst), 0.005, 0.02, 250, n (Q3 不再来)
        responses = iter([
            "y",     # Q0
            "1",     # Q1 选 sst
            "0.005", # I
            "0.02",  # L
            "250",   # U_ref
            "n",     # Q3 不再选
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_5_naming"
        assert "turbulence" in new_data
        ov = new_data["turbulence"]
        # 顶层默认
        assert ov["I"] == 0.005  # 用户覆盖
        assert ov["L"] == 0.02
        assert ov["U_ref"] == 250.0
        # sst override
        assert ov["overrides"]["sst"]["I"] == 0.005
        assert ov["overrides"]["sst"]["L"] == 0.02
        assert ov["overrides"]["sst"]["U_ref"] == 250.0

    def test_default_values_from_template(self, monkeypatch, tmp_path):
        """空输入 → 走 template 读到的默认(此处 _read_template_value 解析失败用 fallback)。"""
        p = tmp_path / "tmpl.inp"
        p.write_text(textwrap.dedent("""\
            guiopts begin
              turbi_lev 5.0
            guiopts end
            physics begin
              refvel 123.0
            physics end
        """))
        wiz = WizardSweep()
        data = {
            "mode": "1", "template": str(p),
            "sweeps": {"turbulence": ["sst"]},
        }
        # 用户全空 → 默认
        responses = iter([
            "y",    # Q0
            "1",    # Q1 选 sst
            "",     # I (空 → 默认)
            "",     # L
            "",     # U_ref
            "n",    # Q3 不再来
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        ov = new_data["turbulence"]["overrides"]["sst"]
        # 模板里 turbi_lev=5.0 是 2-方程字段,_read_template_value(turbi_tlev)
        # 在模板里没有 → 用 fallback 0.01
        # L 模板里没有 → fallback 0.01
        # U_ref 模板 refvel=123.0
        assert ov["I"] == 0.01  # fallback(模板无 turbi_tlev)
        assert ov["L"] == 0.01  # fallback
        assert ov["U_ref"] == 123.0  # 模板 refvel


class TestStep4cEnergyOverride:
    """Q0=y + 选了 energy 走 2T → overrides.2T。"""

    def test_2t_override(self, monkeypatch, template_path):
        """选了 energy axis + 选 2T + 输 T_trans/T_vib → overrides['2T']。"""
        wiz = WizardSweep()
        data = {
            "mode": "1", "template": template_path,
            "sweeps": {"energy": ["2t"]},
        }
        # 顺序:y (Q0), 1 (Q2 选 2T — 1=2t), 300, 200 (T_trans, T_vib)
        responses = iter([
            "y",     # Q0
            "1",     # Q2 选 2T(energy_choices: 1=2t, 2=none, 3=skip)
            "300",   # T_trans
            "200",   # T_vib
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        # energy overrides
        eo = new_data.get("energy_overrides", {})
        assert eo.get("2T", {}).get("T_trans") == 300.0
        assert eo.get("2T", {}).get("T_vib") == 200.0


class TestStep4cMultipleOverrides:
    """Q3 选 y → 循环覆盖多个 model。"""

    def test_override_two_turbulence_models(self, monkeypatch, template_path):
        """Q3=y → Q1 选 sa 再覆盖一次。"""
        wiz = WizardSweep()
        data = {
            "mode": "1", "template": template_path,
            "sweeps": {"turbulence": ["sst", "sa"]},
        }
        # Q0=y, Q1=1 sst, I/L/U, Q3=y 再来,Q1=2 sa, I/L/U, Q3=n 结束
        responses = iter([
            "y",   # Q0
            "1",   # Q1 sst
            "0.01", "0.01", "204",  # SST 默认
            "y",   # Q3 再来
            "2",   # Q1 sa
            "0.03", "0.005", "100",  # SA
            "n",   # 结束
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        ov = new_data["turbulence"]["overrides"]
        assert "sst" in ov and "sa" in ov
        assert ov["sa"]["I"] == 0.03
        assert ov["sa"]["L"] == 0.005
        assert ov["sa"]["U_ref"] == 100.0
