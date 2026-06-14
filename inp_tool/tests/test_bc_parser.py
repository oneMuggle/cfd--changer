"""``inp_tool.postprocess.bc`` 单元测试。

测试覆盖:
- ``parse_mcfd_bc`` 解析 fixture 文件
- ``#BC`` 文件头注释跳过(非边界名)
- 空白注释 / header 行(``seq# type modi info``)忽略
- ``op_label`` 把 ``[1, 2]`` + ``{1: "Body", 2: "HCW"}`` 拼成 ``"Body+HCW"``
- 未知边界编号回退到数字字符串
- ``FileNotFoundError`` 对不存在的文件

Fixture 来源:``reference/full_case/Case/mcfd.bc``(12 行,5 个边界)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from inp_tool.postprocess.bc import (
    BcNameMap,
    op_label,
    parse_mcfd_bc,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reference"
BC_MINI = FIXTURE_DIR / "bc_mini.bc"


# ============================================================================
# parse_mcfd_bc — fixture 对照
# ============================================================================

class TestParseMcfdBcFixture:
    """对 ``reference/full_case/Case/mcfd.bc`` 截取的 12 行 fixture。"""

    def test_returns_5_boundaries(self):
        result = parse_mcfd_bc(BC_MINI)
        assert len(result) == 5

    def test_id_1_is_body(self):
        result = parse_mcfd_bc(BC_MINI)
        assert result[1] == "Body"

    def test_id_2_is_hcw(self):
        result = parse_mcfd_bc(BC_MINI)
        assert result[2] == "HCW"

    def test_id_3_is_far(self):
        result = parse_mcfd_bc(BC_MINI)
        assert result[3] == "far"

    def test_id_4_is_out(self):
        result = parse_mcfd_bc(BC_MINI)
        assert result[4] == "out"

    def test_id_5_is_sym(self):
        result = parse_mcfd_bc(BC_MINI)
        assert result[5] == "sym"

    def test_full_mapping(self):
        """完整映射(防参数化漂移)。"""
        result = parse_mcfd_bc(BC_MINI)
        assert result == {1: "Body", 2: "HCW", 3: "far", 4: "out", 5: "sym"}


# ============================================================================
# parse_mcfd_bc — 注释 / 头行规则
# ============================================================================

class TestParseMcfdBcCommentRules:
    """``#BC`` 文件头 / ``seq# type modi info`` 头行不能误当边界名。"""

    def test_bc_file_header_not_treated_as_name(self, tmp_path):
        """`#BC file created by ...` 必须被跳过,不能作为下一个数字行的名字。"""
        bc_file = tmp_path / "mcfd.bc"
        bc_file.write_text(
            "#BC file created by Pointwise 2024-05-13 21:37:51\n"
            "seq# type modi info\n"
            "#Body\n"
            "   1    0    0    0\n",
            encoding="utf-8",
        )
        result = parse_mcfd_bc(bc_file)
        # ID 1 应该是 "Body",绝不能是 "BC file ..."
        assert result == {1: "Body"}

    def test_seq_header_row_ignored(self, tmp_path):
        """``seq# type modi info`` 是无 `#` 前缀的 header,应被忽略。"""
        bc_file = tmp_path / "mcfd.bc"
        bc_file.write_text(
            "seq# type modi info\n"
            "#Wall\n"
            "  10    0    0    0\n",
            encoding="utf-8",
        )
        result = parse_mcfd_bc(bc_file)
        assert result == {10: "Wall"}

    def test_blank_lines_skipped(self, tmp_path):
        """空白行 / 多余空行不影响解析。"""
        bc_file = tmp_path / "mcfd.bc"
        bc_file.write_text(
            "#Body\n"
            "\n"
            "   1    0    0    0\n"
            "\n"
            "#HCW\n"
            "\n"
            "   2    0    0    0\n",
            encoding="utf-8",
        )
        result = parse_mcfd_bc(bc_file)
        assert result == {1: "Body", 2: "HCW"}

    def test_consecutive_comments_keep_last(self, tmp_path):
        """连续两个 `#Name`,只有最后一个绑定到数字行。"""
        bc_file = tmp_path / "mcfd.bc"
        bc_file.write_text(
            "#Old\n"
            "#New\n"
            "   7    0    0    0\n",
            encoding="utf-8",
        )
        result = parse_mcfd_bc(bc_file)
        assert result == {7: "New"}

    def test_name_with_spaces_preserved(self, tmp_path):
        """边界名含空格(``# Outer Wall``)应原样保留。"""
        bc_file = tmp_path / "mcfd.bc"
        bc_file.write_text(
            "# Outer Wall\n"
            "   9    0    0    0\n",
            encoding="utf-8",
        )
        result = parse_mcfd_bc(bc_file)
        assert result == {9: "Outer Wall"}


# ============================================================================
# parse_mcfd_bc — 错误边界
# ============================================================================

class TestParseMcfdBcErrors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_mcfd_bc(tmp_path / "does_not_exist.bc")

    def test_empty_file_returns_empty_map(self, tmp_path):
        bc_file = tmp_path / "empty.bc"
        bc_file.write_text("", encoding="utf-8")
        assert parse_mcfd_bc(bc_file) == {}

    def test_no_boundaries_only_comments(self, tmp_path):
        """全是注释 + header,没有数字行 → 空 map。"""
        bc_file = tmp_path / "no_bc.bc"
        bc_file.write_text(
            "#BC file created by ...\n"
            "seq# type modi info\n"
            "#Body\n",  # 没跟数字行
            encoding="utf-8",
        )
        assert parse_mcfd_bc(bc_file) == {}


# ============================================================================
# op_label — 边界编号列表 + 名称映射 → 拼接名称
# ============================================================================

class TestOpLabel:
    """``op_label([1, 2], {1: "Body", 2: "HCW"})`` → ``"Body+HCW"``"""

    def test_single_known_id(self):
        names = {1: "Body"}
        assert op_label([1], names) == "Body"

    def test_two_known_ids_joined_with_plus(self):
        names = {1: "Body", 2: "HCW"}
        assert op_label([1, 2], names) == "Body+HCW"

    def test_three_known_ids(self):
        names = {1: "Body", 2: "HCW", 3: "far"}
        assert op_label([1, 2, 3], names) == "Body+HCW+far"

    def test_unknown_id_falls_back_to_digit(self):
        """未在 map 中的 id,字符串化的数字代替。"""
        names = {1: "Body"}
        assert op_label([1, 99], names) == "Body+99"

    def test_all_unknown_ids(self):
        names: BcNameMap = {}
        assert op_label([7, 8, 9], names) == "7+8+9"

    def test_empty_id_list(self):
        """空 op 列表 → 空字符串。"""
        names = {1: "Body"}
        assert op_label([], names) == ""

    def test_order_preserved(self):
        """顺序保留(不排序)。"""
        names = {1: "Body", 2: "HCW", 3: "far"}
        assert op_label([3, 1, 2], names) == "far+Body+HCW"

    def test_duplicate_id_repeated(self):
        """重复 id 不去重(直接重复名)。"""
        names = {1: "Body"}
        assert op_label([1, 1], names) == "Body+Body"
