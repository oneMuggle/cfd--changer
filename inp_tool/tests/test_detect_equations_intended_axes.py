"""
v0.10.0+:detect_equations(inp, intended_axes=None) 兼容性检查测试

当 wizard 把用户选的 axis(短名,如 'sst' / '2t' / 'multi-temp')传给 detect_equations,
应比对 template 的实际状态,发现不兼容时追加 warning 到 sweeps_equation_warnings
(独立于 notes,供 wizard step_4a_detect 末尾消费)。
"""
from __future__ import annotations
import textwrap
import pytest
from inp_tool.equations import detect_equations
from inp_tool.parser import parse


# ============================================================
# 共享 fixture:最小化 mcfd.inp 文本(可改 guiopts/physics/eqnset_define)
# ============================================================
HEADER = textwrap.dedent("""\
    seq.# 1 #vals 31 title eqnset_define
      values 101 1 1 {v4} {v5}
      values {v6} 0 0 0 0
      values 1 0
    seq.# 1 #vals 31
    guiopts begin
      aero_alpha 0.0
      aero_ma 0.6
      aero_temp 288.15
      turbi_lev 1.0
      turbi_len 0.01
    guiopts end
    physics begin
      refvel 204.0
      reftem 288.15
      tnoneq_numeqns {tnoneq}
    physics end
""")


def _parse_sst_perfect_gas():
    """SST k-ω (v4=2, v5=3) + 完美气体 (v6=0) + tnoneq=0。"""
    text = HEADER.format(v4=2, v5=3, v6=0, tnoneq=0)
    return parse(text)


def _parse_laminar_perfect_gas():
    """LAMINAR (v4=0, v5=1) + 完美气体 (v6=0) + tnoneq=0。"""
    text = HEADER.format(v4=0, v5=1, v6=0, tnoneq=0)
    return parse(text)


def _parse_sst_multitemp():
    """SST k-ω + MULTI_TEMP (v6=11) + tnoneq=1。"""
    text = HEADER.format(v4=2, v5=3, v6=11, tnoneq=1)
    return parse(text)


class TestIntendedAxesNone:
    """不传 intended_axes → 行为与 v0.9.1 完全一致,无 sweeps_equation_warnings。"""

    def test_default_no_axis_check(self):
        """intended_axes 默认 None → sweeps_equation_warnings 始终空。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(inp)
        assert rep.sweeps_equation_warnings == []

    def test_explicit_none(self):
        """显式传 None → 同样不检查。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(inp, intended_axes=None)
        assert rep.sweeps_equation_warnings == []


class TestIntendedAxesLaminarClash:
    """用户选 SST 但 template 是 laminar → warning。"""

    def test_sst_axis_laminar_template_warns(self):
        """intended_axes.turbulence='sst' + template laminar → 1 条 warning。"""
        inp = _parse_laminar_perfect_gas()
        rep = detect_equations(
            inp, intended_axes={"turbulence": "sst"},
        )
        assert len(rep.sweeps_equation_warnings) == 1
        msg = rep.sweeps_equation_warnings[0]
        # 信息含关键提示:SST + laminar + 跳过
        assert "SST" in msg or "sst" in msg
        assert "laminar" in msg.lower()
        assert "skip" in msg.lower() or "跳过" in msg

    def test_laminar_axis_no_warning(self):
        """intended_axes.turbulence='laminar' + template laminar → 无 warning。"""
        inp = _parse_laminar_perfect_gas()
        rep = detect_equations(
            inp, intended_axes={"turbulence": "laminar"},
        )
        assert rep.sweeps_equation_warnings == []

    def test_sa_axis_laminar_template_warns(self):
        """SA + laminar 模板 → 同样 warn(规则对所有非 laminar 湍流一致)。"""
        inp = _parse_laminar_perfect_gas()
        rep = detect_equations(
            inp, intended_axes={"turbulence": "sa"},
        )
        assert len(rep.sweeps_equation_warnings) == 1


class TestIntendedAxesEnergyClash:
    """用户选 2T 但 template tnoneq=0 → warning。"""

    def test_2t_axis_perfect_gas_template_warns(self):
        """intended_axes.energy='2t' + template tnoneq=0 → 1 条 warning。"""
        inp = _parse_sst_perfect_gas()  # tnoneq=0
        rep = detect_equations(
            inp, intended_axes={"energy": "2t"},
        )
        assert len(rep.sweeps_equation_warnings) == 1
        msg = rep.sweeps_equation_warnings[0]
        assert "2T" in msg or "2t" in msg.lower()
        assert "tnoneq" in msg or "numeqns" in msg

    def test_2t_axis_multitemp_template_no_warning(self):
        """2T + template 已是 tnoneq=1 → 无 warning(自洽)。"""
        inp = _parse_sst_multitemp()  # tnoneq=1
        rep = detect_equations(
            inp, intended_axes={"energy": "2t"},
        )
        assert rep.sweeps_equation_warnings == []

    def test_none_axis_with_2t_template_warns(self):
        """intended_axes.energy='none' + template tnoneq=1 → warning(反向冲突)。"""
        inp = _parse_sst_multitemp()  # tnoneq=1
        rep = detect_equations(
            inp, intended_axes={"energy": "none"},
        )
        assert len(rep.sweeps_equation_warnings) == 1


class TestIntendedAxesGasClash:
    """用户选 MULTI_TEMP 但 template v6=0 → warning。"""

    def test_multi_temp_axis_perfect_gas_template_warns(self):
        """intended_axes.gas='multi-temp' + v6=0 → 1 条 warning。"""
        inp = _parse_sst_perfect_gas()  # v6=0
        rep = detect_equations(
            inp, intended_axes={"gas": "multi-temp"},
        )
        assert len(rep.sweeps_equation_warnings) == 1
        msg = rep.sweeps_equation_warnings[0]
        assert "multi" in msg.lower()
        assert "v6" in msg

    def test_real_gas_axis_perfect_gas_template_warns(self):
        """intended_axes.gas='real-gas' + v6=0 → warning。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(
            inp, intended_axes={"gas": "real-gas"},
        )
        assert len(rep.sweeps_equation_warnings) == 1

    def test_perfect_gas_axis_no_warning(self):
        """intended_axes.gas='perfect-gas' + v6=0 → 无 warning。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(
            inp, intended_axes={"gas": "perfect-gas"},
        )
        assert rep.sweeps_equation_warnings == []


class TestIntendedAxesMultiAxis:
    """一次传多个 axis,所有冲突都列。"""

    def test_sst_with_laminar_plus_2t_with_perfect_gas(self):
        """SST 撞 laminar + 2T 撞 tnoneq=0 → 2 条 warning。"""
        inp = _parse_laminar_perfect_gas()  # laminar + tnoneq=0
        rep = detect_equations(inp, intended_axes={
            "turbulence": "sst",
            "energy": "2t",
        })
        assert len(rep.sweeps_equation_warnings) == 2

    def test_no_known_axis_key_ignored(self):
        """intended_axes 含未识别的 key(alpha 等)→ 忽略,不影响。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(inp, intended_axes={
            "turbulence": "sst",  # 兼容
            "alpha": [0, 5],      # 非方程轴,忽略
        })
        assert rep.sweeps_equation_warnings == []


class TestIntendedAxesAliasShortName:
    """短名 alias('sst' / 'sa' / 'ke' 等)和规范名都接受(以 _ENUM_ALIASES 为准)。"""

    @pytest.mark.parametrize("alias", ["sst", "k-omega-sst"])
    def test_sst_aliases_accepted(self, alias):
        """'sst' 和 'k-omega-sst' 都被识别为 SST_KW。"""
        inp = _parse_laminar_perfect_gas()
        rep = detect_equations(inp, intended_axes={"turbulence": alias})
        assert len(rep.sweeps_equation_warnings) == 1

    @pytest.mark.parametrize("alias", ["2t", "2T"])
    def test_2t_aliases_accepted(self, alias):
        """'2t' / '2T' 都被识别为 EnergyModel.TWO_TEMP。"""
        inp = _parse_sst_perfect_gas()
        rep = detect_equations(inp, intended_axes={"energy": alias})
        assert len(rep.sweeps_equation_warnings) == 1

    @pytest.mark.parametrize("alias", ["sa", "spalart-allmaras"])
    def test_sa_aliases_accepted(self, alias):
        """'sa' 和 'spalart-allmaras' 都被识别为 SA(用于 laminar 模板时 warn)。"""
        inp = _parse_laminar_perfect_gas()
        rep = detect_equations(inp, intended_axes={"turbulence": alias})
        assert len(rep.sweeps_equation_warnings) == 1
