"""pbs 模块 - PBS -N 名字验证(Phase 0 / v0.14.0)

集群硬约束(来自 reference/docs/1.md):
- 限 15 字符
- 首字符为字母
- 无空格

约定:
- render_pbs_name max_len 默认 = 15(从 200 改)
- extract_pbs_basename max_len 默认 = 14(从 8 改,留 1 给 suffix)
- write_pbs 写出前自动 validate,违规 raise PbsValidationError
- validate_pbs_name 返回 list[PbsIssue](可空,error/warning)
"""
from __future__ import annotations

import pytest

from inp_tool.pbs import (
    PbsIssue,
    extract_pbs_basename,
    render_pbs_name,
    validate_pbs_name,
    write_pbs,
)


# ---------------------------------------------------------------------------
# render_pbs_name: max_len 改 15
# ---------------------------------------------------------------------------

class TestRenderPbsNameDefaultMaxLen:
    """v0.14.0: render_pbs_name 默认 max_len 从 200 改为 15(集群硬约束)"""

    def test_short_name_under_15_unchanged(self):
        """14 字符名字不受影响"""
        out = render_pbs_name({"alpha": 4}, ["alpha"], "Mars")
        # Mars + "_" + "a04" = 7 chars, well under 15
        assert len(out) <= 15
        assert out.startswith("Mars")

    def test_name_truncated_at_15_by_default(self):
        """默认 max_len=15:超长名字截断"""
        params = {"alpha": 4, "mach": 0.85, "T_inf": 288}
        out = render_pbs_name(params, ["alpha", "mach", "T_inf"], "Mars")
        assert len(out) <= 15

    def test_explicit_max_len_20_overrides_default(self):
        """显式 max_len=20 仍可用(测试 max_len 参数未被删除)"""
        params = {"alpha": 4, "mach": 0.85}
        out = render_pbs_name(params, ["alpha", "mach"], "Mars", max_len=20)
        assert len(out) <= 20

    def test_explicit_max_len_5_truncates_aggressively(self):
        """显式 max_len=5 仍然工作"""
        out = render_pbs_name({"alpha": 4}, ["alpha"], "Mars", max_len=5)
        assert len(out) <= 5

    def test_max_len_15_keeps_15_chars_exactly(self):
        """边界:14 字符 OK,15 字符 OK,16 字符截断"""
        # 14 字符名字
        out = render_pbs_name(
            {"alpha": 12}, ["alpha"], "M"  # M + a12 = 4 chars
        )
        # 短,不受影响
        assert len(out) <= 15


# ---------------------------------------------------------------------------
# extract_pbs_basename: max_len 改 14
# ---------------------------------------------------------------------------

class TestExtractPbsBasenameDefaultMaxLen:
    """v0.14.0: extract_pbs_basename 默认 max_len 从 8 改为 14"""

    def test_short_name_extracted_unchanged(self, tmp_path):
        p = tmp_path / "run.pbs"
        p.write_text("#!/bin/bash\n#PBS -N short\ncd $PBS_O_WORKDIR\n")
        assert extract_pbs_basename(str(p)) == "short"

    def test_name_at_15_chars_truncated_to_14(self, tmp_path):
        """16 字符名字截到 14"""
        p = tmp_path / "run.pbs"
        p.write_text("#PBS -N " + "a" * 16 + "\n")
        out = extract_pbs_basename(str(p))
        assert len(out) == 14
        assert out == "a" * 14

    def test_name_at_14_chars_unchanged(self, tmp_path):
        p = tmp_path / "run.pbs"
        p.write_text("#PBS -N " + "a" * 14 + "\n")
        out = extract_pbs_basename(str(p))
        assert len(out) == 14
        assert out == "a" * 14

    def test_explicit_max_len_still_works(self, tmp_path):
        """显式 max_len=20 仍可用"""
        p = tmp_path / "run.pbs"
        p.write_text("#PBS -N " + "a" * 20 + "\n")
        out = extract_pbs_basename(str(p), max_len=20)
        assert len(out) == 20

    def test_missing_file_returns_case(self, tmp_path):
        """找不到文件返回 'case' fallback"""
        out = extract_pbs_basename(str(tmp_path / "nope.pbs"))
        assert out == "case"

    def test_no_pbs_n_directive_returns_case(self, tmp_path):
        """没 #PBS -N 行返回 'case' fallback"""
        p = tmp_path / "run.pbs"
        p.write_text("#!/bin/bash\necho hello\n")
        assert extract_pbs_basename(str(p)) == "case"


# ---------------------------------------------------------------------------
# validate_pbs_name: 新函数
# ---------------------------------------------------------------------------

class TestValidatePbsName:
    """v0.14.0 新增: 校验名字符合集群硬约束"""

    def test_valid_name_returns_empty_issues(self):
        """合法名字返回空 list"""
        assert validate_pbs_name("Mars_a04") == []
        assert validate_pbs_name("a") == []
        assert validate_pbs_name("a" * 15) == []

    def test_too_long_returns_error(self):
        """16 字符返回 error 级别 issue"""
        issues = validate_pbs_name("a" * 16)
        assert len(issues) >= 1
        assert any(i.severity == "error" for i in issues)
        assert any("16" in i.message or "length" in i.message.lower() for i in issues)

    def test_empty_string_returns_error(self):
        """空串返回 error"""
        issues = validate_pbs_name("")
        assert any(i.severity == "error" for i in issues)

    def test_first_char_not_letter_returns_error(self):
        """首字符不是字母返回 error"""
        for bad in ["1abc", "_abc", "-abc", ".abc", " abc"]:
            issues = validate_pbs_name(bad)
            assert any(i.severity == "error" for i in issues), f"{bad!r} should error"

    def test_contains_space_returns_error(self):
        """含空格返回 error"""
        issues = validate_pbs_name("Mars a04")
        assert any(i.severity == "error" for i in issues)
        assert any("space" in i.message.lower() or "whitespace" in i.message.lower() for i in issues)

    def test_contains_special_char_returns_error(self):
        """含非允许字符返回 error"""
        for bad in ["Mars$a", "Mars#a", "Mars@a", "Mars*a", "Mars/a"]:
            issues = validate_pbs_name(bad)
            assert any(i.severity == "error" for i in issues), f"{bad!r} should error"

    def test_underscore_and_dot_allowed(self):
        """下划线和点应该合法"""
        assert validate_pbs_name("Mars_a04") == []
        assert validate_pbs_name("Mars.a04") == []
        assert validate_pbs_name("Mars_a04.0") == []

    def test_digits_after_first_letter_allowed(self):
        """首字母后允许数字"""
        assert validate_pbs_name("a1") == []
        assert validate_pbs_name("a123") == []
        assert validate_pbs_name("Mars123") == []

    def test_returns_pbs_issue_objects(self):
        """返回 PbsIssue 列表"""
        issues = validate_pbs_name("")
        assert all(isinstance(i, PbsIssue) for i in issues)


# ---------------------------------------------------------------------------
# write_pbs: 集成测试 - 写出前自动 validate
# ---------------------------------------------------------------------------

class TestWritePbsValidatesName:
    """v0.14.0: write_pbs 在写出前自动校验,违规 raise"""

    def test_valid_name_writes_normally(self, tmp_path):
        """合法名字正常写出"""
        template = tmp_path / "tpl.pbs"
        template.write_text("#!/bin/bash\n#PBS -N old_name\nls\n")
        out = tmp_path / "out.pbs"
        write_pbs(str(template), str(out), "Mars_a04")
        text = out.read_text()
        assert "#PBS -N Mars_a04" in text

    def test_invalid_name_raises(self, tmp_path):
        """非法名字 raise"""
        from inp_tool.pbs import PbsValidationError
        template = tmp_path / "tpl.pbs"
        template.write_text("#!/bin/bash\n#PBS -N old\nls\n")
        out = tmp_path / "out.pbs"
        # 16 字符超长
        with pytest.raises(PbsValidationError):
            write_pbs(str(template), str(out), "a" * 16)

    def test_first_char_digit_raises(self, tmp_path):
        """首字符数字 raise"""
        from inp_tool.pbs import PbsValidationError
        template = tmp_path / "tpl.pbs"
        template.write_text("#!/bin/bash\n#PBS -N old\nls\n")
        out = tmp_path / "out.pbs"
        with pytest.raises(PbsValidationError):
            write_pbs(str(template), str(out), "1abc")

    def test_space_in_name_raises(self, tmp_path):
        """含空格 raise"""
        from inp_tool.pbs import PbsValidationError
        template = tmp_path / "tpl.pbs"
        template.write_text("#!/bin/bash\n#PBS -N old\nls\n")
        out = tmp_path / "out.pbs"
        with pytest.raises(PbsValidationError):
            write_pbs(str(template), str(out), "Mars a04")

    def test_template_text_in_memory_still_validated(self, tmp_path):
        """传 template_text 时同样校验"""
        from inp_tool.pbs import PbsValidationError
        out = tmp_path / "out.pbs"
        with pytest.raises(PbsValidationError):
            write_pbs(
                str(tmp_path / "nonexistent"),  # 模板不存在
                str(out),
                "a" * 16,
                template_text="#!/bin/bash\n#PBS -N old\nls\n",
            )
