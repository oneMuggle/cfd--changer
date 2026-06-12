"""
v0.10.0+:WizardSweep.step_4b_equation_axes 测试

3 个子问题:Q1 turbulence、Q2 energy、Q3 gas。
合并到 data["sweeps"];若全 skip → 不注入任何 axis key。
仅 Cartesian(mode=1) 走;其他 mode 静默跳过。
"""
from __future__ import annotations
import pytest
from inp_tool.wizard import WizardSweep
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


def _call_step(wiz, data):
    """直接调 step_4b_equation_axes。"""
    return wiz.step_4b_equation_axes(data)


class TestStep4bCartesianGate:
    """非 Cartesian 模式 → 静默跳过,不动 sweeps。"""

    def test_skip_when_not_cartesian(self):
        """mode='2'(explicit) → step_4b 不动 data,直接进 step_4a_detect。"""
        wiz = WizardSweep()
        data = {"mode": "2", "sweeps": {"alpha": [0, 5]}}
        next_step, new_data = _call_step(wiz, data)
        # 跳到 step_4a_detect,data 不变(原 sweeps 保留)
        assert next_step == "step_4a_detect"
        assert new_data.get("sweeps") == {"alpha": [0, 5]}

    def test_csv_mode_skips(self):
        """mode='4' (CSV) → 同样跳过。"""
        wiz = WizardSweep()
        data = {"mode": "4"}
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_4a_detect"
        # 不应注入 sweeps key
        assert "sweeps" not in new_data or new_data.get("sweeps") == {}


class TestStep4bAllSkip:
    """全 3 题选 n → sweeps 不变(等价 v0.10.0 老路径)。"""

    def test_all_n_keeps_sweeps_intact(self, monkeypatch):
        """Q1=n Q2=n Q3=n → 返回 step_4a_detect,data["sweeps"] 不变。"""
        wiz = WizardSweep()
        data = {
            "mode": "1",
            "sweeps": {"alpha": [0, 5], "mach": [0.6, 0.8]},
        }
        # 3 个 n
        responses = iter(["n", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_4a_detect"
        # 原有 sweeps 保留,无新 axis 注入
        assert new_data["sweeps"] == {"alpha": [0, 5], "mach": [0.6, 0.8]}


class TestStep4bSelectTurbulence:
    """Q1 选 SST/SA → sweeps.turbulence 注入。"""

    def test_pick_sst_sa(self, monkeypatch):
        """Q1=Y + 1 2 + Q2=n + Q3=n → sweeps.turbulence=['sst','sa']。"""
        wiz = WizardSweep()
        data = {
            "mode": "1",
            "sweeps": {"alpha": [0, 5]},
        }
        # 顺序:Y, 1 2, n, n
        responses = iter(["y", "1 2", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert next_step == "step_4a_detect"
        assert new_data["sweeps"]["turbulence"] == ["sst", "sa"]
        # 原有 alpha 保留
        assert new_data["sweeps"]["alpha"] == [0, 5]


class TestStep4bSelectEnergy:
    """Q2 选 2T → sweeps.energy 注入。"""

    def test_pick_2t(self, monkeypatch):
        """Q1=n Q2=Y + 2 + Q3=n → sweeps.energy=['2t']。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 5]}}
        responses = iter(["n", "y", "2", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert new_data["sweeps"]["energy"] == ["2t"]


class TestStep4bSelectGas:
    """Q3 选 gas → sweeps.gas 注入。"""

    def test_pick_multi_temp(self, monkeypatch):
        """Q1=n Q2=n Q3=Y + 3 → sweeps.gas=['multi-temp']。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {}}
        responses = iter(["n", "n", "y", "3"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert new_data["sweeps"]["gas"] == ["multi-temp"]


class TestStep4bAllAxes:
    """Q1+Q2+Q3 全选 → 3 个 axis 都注入。"""

    def test_pick_all_three_axes(self, monkeypatch):
        """Y 1 2, Y 2, Y 1 → sweeps 含 turbulence/energy/gas。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {"alpha": [0, 5]}}
        responses = iter([
            "y", "1 2",   # Q1: sst+sa
            "y", "2",     # Q2: 2t
            "y", "3",     # Q3: multi-temp
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        sweeps = new_data["sweeps"]
        assert sweeps["turbulence"] == ["sst", "sa"]
        assert sweeps["energy"] == ["2t"]
        assert sweeps["gas"] == ["multi-temp"]
        # 原有 alpha 保留
        assert sweeps["alpha"] == [0, 5]


class TestStep4bProducesIntendedAxes:
    """step_4b 在 data 里存 intended_axes 供 step_4a_detect 消费。"""

    def test_intended_axes_recorded(self, monkeypatch):
        """Q1 选 sst → data 含 intended_axes.turbulence='sst'(供 detect 消费)。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {}}
        responses = iter(["y", "1", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        # 选中的 axis(用于 detect_equations 警告)
        intended = new_data.get("intended_axes", {})
        assert intended.get("turbulence") == "sst"

    def test_intended_axes_absent_when_all_n(self, monkeypatch):
        """全 n → 不存 intended_axes(没冲突要 warn)。"""
        wiz = WizardSweep()
        data = {"mode": "1", "sweeps": {}}
        responses = iter(["n", "n", "n"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        next_step, new_data = _call_step(wiz, data)
        assert "intended_axes" not in new_data
