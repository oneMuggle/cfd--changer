"""
v0.10.0+:wizard._read_template_value helper 测试

从 template .inp 读 guiopts.x 或 physics.x,转 float,失败用 default。
供 step_4c_equation_overrides 取 I/L/U_ref 默认值。
"""
from __future__ import annotations
import textwrap
import pytest
from inp_tool.wizard import _read_template_value


@pytest.fixture
def template_path(tmp_path):
    p = tmp_path / "mcfd.inp"
    p.write_text(textwrap.dedent("""\
        guiopts begin
          turbi_lev 2.5
          turbi_len 0.03
        guiopts end
        physics begin
          refvel 250.0
          reftem 300.0
        physics end
    """))
    return str(p)


class TestReadTemplateValueHappy:
    def test_guiopts_field(self, template_path):
        """guiopts.turbi_lev=2.5 → 2.5 (float)。"""
        v = _read_template_value(template_path, "guiopts", "turbi_lev", 0.01)
        assert v == pytest.approx(2.5)

    def test_physics_field(self, template_path):
        """physics.refvel=250.0 → 250.0。"""
        v = _read_template_value(template_path, "physics", "refvel", 100.0)
        assert v == pytest.approx(250.0)

    def test_int_value_coerced_to_float(self, template_path):
        """physics.reftem=300 (int) → 300.0 (float)。"""
        v = _read_template_value(template_path, "physics", "reftem", 288.15)
        assert v == 300.0
        assert isinstance(v, float)


class TestReadTemplateValueFallbacks:
    def test_missing_block_returns_default(self, tmp_path):
        """template 缺 block → default。"""
        p = tmp_path / "empty.inp"
        p.write_text("guiopts begin\nguiopts end\n")
        v = _read_template_value(str(p), "physics", "refvel", 204.0)
        assert v == 204.0

    def test_missing_key_returns_default(self, tmp_path):
        """block 存在但缺 key → default。"""
        p = tmp_path / "partial.inp"
        p.write_text("guiopts begin\nturbi_lev 1.0\nguiopts end\n")
        v = _read_template_value(str(p), "guiopts", "turbi_tlev", 0.01)
        assert v == 0.01

    def test_missing_file_returns_default(self, tmp_path):
        """template 文件不存在 → default(不抛异常)。"""
        v = _read_template_value(
            str(tmp_path / "nonexistent.inp"), "guiopts", "turbi_lev", 0.5,
        )
        assert v == 0.5

    def test_unparseable_value_returns_default(self, tmp_path):
        """value 不是数字(字符串等)→ default(不抛)。"""
        p = tmp_path / "bad.inp"
        p.write_text(textwrap.dedent("""\
            guiopts begin
              turbi_lev not-a-number
            guiopts end
        """))
        v = _read_template_value(str(p), "guiopts", "turbi_lev", 0.99)
        assert v == 0.99

    def test_corrupt_file_returns_default(self, tmp_path):
        """完全无法解析的 garbage → default。"""
        p = tmp_path / "garbage.inp"
        p.write_text("\x00\x01\x02 binary garbage")
        v = _read_template_value(str(p), "guiopts", "turbi_lev", 0.5)
        assert v == 0.5
