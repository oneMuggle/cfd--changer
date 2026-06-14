"""``inp_tool.postprocess.info1`` 单元测试。

测试覆盖:
- ``read_info1`` 解析 fixture 的 step / dimensional / total/inv/vis 三流
- ``op_ibd`` 单边界 / 多边界(多 op 累加)过滤
- ``nondimensional`` 行被跳过(只取 dimensional)
- 步骤过渡(``nt 1 → nt 2``)
- EOF flush — 最后一个 step 的累积值不能丢(reference 已知 bug 我们修了)
- ``find_total_force_file`` 排除 ``_inviscid`` / ``_viscous`` 后缀文件
- ``is_viscous`` 任一分量非零 → True
- ``FileNotFoundError`` 对不存在的文件
- 损坏 / 空 / 无 nt 文件容错

Fixture 来源:``reference/full_case/Case/mcfd.info1``(151 行,2 个 nt step:
  - step 1 完整(5 个 selector × nondim+dim)
  - step 2 partial(只 selector 1 完整))
"""
from __future__ import annotations

from pathlib import Path

import pytest

from inp_tool.postprocess.info1 import (
    Info1Step,
    find_total_force_file,
    is_viscous,
    read_info1,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "reference"
INFO1_MINI = FIXTURE_DIR / "info1_mini.txt"


# ============================================================================
# Fixture 中已知的关键数值(从 reference/full_case/Case/mcfd.info1 截取)
# ============================================================================

# nbc=1, step 1, dimensional (lines 25-35 in original mcfd.info1)
S1_NBC1_FX_TOTAL = 5.6728762e+06
S1_NBC1_FY_TOTAL = 9.8257097e+06
S1_NBC1_FZ_TOTAL = -2.0087836e+07
S1_NBC1_MX_TOTAL = 3.2809557e+08
S1_NBC1_MY_TOTAL = 1.2634166e+09
S1_NBC1_MZ_TOTAL = 7.0734602e+08

# nbc=2, step 1, dimensional (lines 48-58)
S1_NBC2_FX_TOTAL = -3.0630251e-03
S1_NBC2_FY_TOTAL = -5.2729701e-03
S1_NBC2_FZ_TOTAL = 1.2093873e+06
S1_NBC2_MX_TOTAL = -1.3299811e+07
S1_NBC2_MY_TOTAL = -9.0509576e+07
S1_NBC2_MZ_TOTAL = -3.8779901e-01

# nbc=1, step 2, dimensional (lines 141-151)
S2_NBC1_FX_TOTAL = 5.4915687e+06
S2_NBC1_FY_TOTAL = 9.5116761e+06
S2_NBC1_FZ_TOTAL = -1.9459764e+07
S2_NBC1_MX_TOTAL = 3.1770083e+08
S2_NBC1_MY_TOTAL = 1.2242058e+09
S2_NBC1_MZ_TOTAL = 6.8474011e+08


# ============================================================================
# read_info1 — fixture 对照(单边界 op_ibd=[1])
# ============================================================================

class TestReadInfo1OpIbd1:
    """``op_ibd=[1]`` 应返回 2 个 step,与 fixture nbc=1 dimensional 一致。"""

    def test_returns_two_steps(self):
        """fixture 有 2 个 ``nt`` 标记(nt 1, nt 2)→ 2 个 step。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        assert len(steps) == 2

    def test_step_numbers_are_1_and_2(self):
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        assert steps[0].step == 1
        assert steps[1].step == 2

    def test_times_are_zero(self):
        """fixture 中 nt 行 time = 0.0e+00。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        assert steps[0].time == pytest.approx(0.0, abs=1e-12)
        assert steps[1].time == pytest.approx(0.0, abs=1e-12)

    def test_step_1_total_force_matches_nbc1(self):
        """step 1 总力 = nbc=1 dimensional (因 op_ibd=[1])。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        total = steps[0].total
        assert total[0] == pytest.approx(S1_NBC1_FX_TOTAL, rel=1e-6)
        assert total[1] == pytest.approx(S1_NBC1_FY_TOTAL, rel=1e-6)
        assert total[2] == pytest.approx(S1_NBC1_FZ_TOTAL, rel=1e-6)
        assert total[3] == pytest.approx(S1_NBC1_MX_TOTAL, rel=1e-6)
        assert total[4] == pytest.approx(S1_NBC1_MY_TOTAL, rel=1e-6)
        assert total[5] == pytest.approx(S1_NBC1_MZ_TOTAL, rel=1e-6)

    def test_step_2_total_force_matches_nbc1(self):
        """step 2 nbc=1 dimensional(EOF flush bug 修复后此 step 的值不能丢)。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        total = steps[1].total
        assert total[0] == pytest.approx(S2_NBC1_FX_TOTAL, rel=1e-6)
        assert total[1] == pytest.approx(S2_NBC1_FY_TOTAL, rel=1e-6)
        assert total[2] == pytest.approx(S2_NBC1_FZ_TOTAL, rel=1e-6)
        assert total[3] == pytest.approx(S2_NBC1_MX_TOTAL, rel=1e-6)
        assert total[4] == pytest.approx(S2_NBC1_MY_TOTAL, rel=1e-6)
        assert total[5] == pytest.approx(S2_NBC1_MZ_TOTAL, rel=1e-6)

    def test_inv_equals_total_when_viscous_zero(self):
        """在 fixture 中 viscous 全为 0,inviscid == total。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        for i in range(6):
            assert steps[0].inv[i] == pytest.approx(steps[0].total[i], rel=1e-9)

    def test_vis_all_zero(self):
        """fixture 中 viscous 全为 0。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        for s in steps:
            for v in s.vis:
                assert v == 0.0


# ============================================================================
# read_info1 — op_ibd=[2](selector 2 单独)
# ============================================================================

class TestReadInfo1OpIbd2:
    """``op_ibd=[2]`` step 1 有数据,step 2 为零(fixture cut before step 2 nbc=2)。"""

    def test_step_1_matches_nbc2(self):
        steps = read_info1(INFO1_MINI, op_ibd=[2])
        total = steps[0].total
        assert total[0] == pytest.approx(S1_NBC2_FX_TOTAL, rel=1e-6)
        assert total[1] == pytest.approx(S1_NBC2_FY_TOTAL, rel=1e-6)
        assert total[2] == pytest.approx(S1_NBC2_FZ_TOTAL, rel=1e-6)
        assert total[3] == pytest.approx(S1_NBC2_MX_TOTAL, rel=1e-6)
        assert total[4] == pytest.approx(S1_NBC2_MY_TOTAL, rel=1e-6)
        assert total[5] == pytest.approx(S1_NBC2_MZ_TOTAL, rel=1e-6)

    def test_step_2_all_zero(self):
        """fixture 中 step 2 不含 nbc=2,所以 op_ibd=[2] 在 step 2 为全零。"""
        steps = read_info1(INFO1_MINI, op_ibd=[2])
        for v in steps[1].total:
            assert v == 0.0


# ============================================================================
# read_info1 — op_ibd=[1, 2](多边界合并)
# ============================================================================

class TestReadInfo1MultiOp:
    """``op_ibd=[1, 2]`` 应该把 nbc=1 + nbc=2 dim 累加成一个 op。"""

    def test_step_1_sum_of_nbc1_and_nbc2(self):
        steps = read_info1(INFO1_MINI, op_ibd=[1, 2])
        total = steps[0].total
        assert total[0] == pytest.approx(S1_NBC1_FX_TOTAL + S1_NBC2_FX_TOTAL, rel=1e-6)
        assert total[1] == pytest.approx(S1_NBC1_FY_TOTAL + S1_NBC2_FY_TOTAL, rel=1e-6)
        assert total[2] == pytest.approx(S1_NBC1_FZ_TOTAL + S1_NBC2_FZ_TOTAL, rel=1e-6)
        assert total[3] == pytest.approx(S1_NBC1_MX_TOTAL + S1_NBC2_MX_TOTAL, rel=1e-6)
        assert total[4] == pytest.approx(S1_NBC1_MY_TOTAL + S1_NBC2_MY_TOTAL, rel=1e-6)
        assert total[5] == pytest.approx(S1_NBC1_MZ_TOTAL + S1_NBC2_MZ_TOTAL, rel=1e-6)

    def test_step_2_only_nbc1_in_fixture(self):
        """fixture step 2 缺 nbc=2,所以 op_ibd=[1,2] 在 step 2 只有 nbc=1 贡献。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1, 2])
        total = steps[1].total
        assert total[0] == pytest.approx(S2_NBC1_FX_TOTAL, rel=1e-6)


# ============================================================================
# read_info1 — nondimensional 必须被跳过
# ============================================================================

class TestReadInfo1SkipsNondimensional:
    """``nondimensional`` 段必须被跳过,不能与 dimensional 段值相加。"""

    def test_op_ibd_1_does_not_double_count(self):
        """nondim 与 dim 在 fixture 中数值相同;若误加,Fx 会变 2 倍。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        # 期望 == dim 单倍,不能 == 2 倍
        assert steps[0].total[0] == pytest.approx(S1_NBC1_FX_TOTAL, rel=1e-6)
        assert steps[0].total[0] != pytest.approx(S1_NBC1_FX_TOTAL * 2, rel=0.1)


# ============================================================================
# read_info1 — op_ibd 不在 fixture 中的边界
# ============================================================================

class TestReadInfo1OpIbdMissing:
    """``op_ibd=[99]`` 没匹配:仍返回所有 step 但 force 全为零。"""

    def test_returns_two_steps_with_zero_force(self):
        steps = read_info1(INFO1_MINI, op_ibd=[99])
        assert len(steps) == 2
        for s in steps:
            assert all(v == 0.0 for v in s.total)


# ============================================================================
# read_info1 — 错误边界
# ============================================================================

class TestReadInfo1Errors:
    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_info1(tmp_path / "missing.info1", op_ibd=[1])

    def test_empty_file_returns_empty(self, tmp_path):
        f = tmp_path / "empty.info1"
        f.write_text("", encoding="utf-8")
        assert read_info1(f, op_ibd=[1]) == []

    def test_no_nt_marker_returns_empty(self, tmp_path):
        """全是 header 行没有 ``nt`` 标记 → 空列表(无 step)。"""
        f = tmp_path / "no_nt.info1"
        f.write_text(
            "At the beginning of this run:\n"
            "reflen: reference length      =  1.0000000e+00\n",
            encoding="utf-8",
        )
        assert read_info1(f, op_ibd=[1]) == []

    def test_malformed_nt_line_skipped(self, tmp_path):
        """``nt`` 行字段不全(< 6 列)→ 跳过不 crash。"""
        f = tmp_path / "bad_nt.info1"
        f.write_text(
            "nt 1\n"  # 缺 tau / time 字段
            "nt 2 tau 0.0 time 0.0\n"
            "nbc =    1,          total       inviscid        viscous, dimensional\n"
            "energy flux  0.0e+00  0.0e+00  0.0e+00\n"
            "mass   flux  0.0e+00  0.0e+00  0.0e+00\n"
            "x force      1.0e+00  1.0e+00  0.0e+00\n"
            "y force      2.0e+00  2.0e+00  0.0e+00\n"
            "z force      3.0e+00  3.0e+00  0.0e+00\n"
            "x moment     4.0e+00  4.0e+00  0.0e+00\n"
            "y moment     5.0e+00  5.0e+00  0.0e+00\n"
            "z moment     6.0e+00  6.0e+00  0.0e+00\n"
            "areas        0.0e+00  0.0e+00  0.0e+00  0.0e+00\n"
            "areamoments  0.0e+00  0.0e+00  0.0e+00\n",
            encoding="utf-8",
        )
        steps = read_info1(f, op_ibd=[1])
        # 第一个不合法的 nt 应被跳过,只保留 nt 2 的有效 step
        assert len(steps) == 1
        assert steps[0].step == 2
        assert steps[0].total[0] == pytest.approx(1.0, rel=1e-9)


# ============================================================================
# is_viscous
# ============================================================================

class TestIsViscous:
    """任一 viscous 分量非零 → True。"""

    def test_all_zero_returns_false(self):
        steps = [Info1Step(
            step=1, time=0.0,
            total=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            inv=(1.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            vis=(0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        )]
        assert is_viscous(steps) is False

    def test_fixture_is_inviscid(self):
        """fixture 的 viscous 全 0,is_viscous 应返回 False。"""
        steps = read_info1(INFO1_MINI, op_ibd=[1])
        assert is_viscous(steps) is False

    def test_any_nonzero_viscous_returns_true(self):
        steps = [
            Info1Step(step=1, time=0.0,
                      total=(0,)*6, inv=(0,)*6, vis=(0,)*6),
            Info1Step(step=2, time=0.0,
                      total=(0,)*6, inv=(0,)*6,
                      vis=(0, 0, 0, 0.1, 0, 0)),  # Mx 非零
        ]
        assert is_viscous(steps) is True

    def test_empty_list_returns_false(self):
        assert is_viscous([]) is False


# ============================================================================
# find_total_force_file
# ============================================================================

class TestFindTotalForceFile:
    """找 ``minfo1_e1*`` 但排除 ``_inviscid`` / ``_viscous`` 后缀。"""

    def test_finds_minfo1_e1(self, tmp_path):
        target = tmp_path / "minfo1_e1"
        target.write_text("data\n", encoding="utf-8")
        assert find_total_force_file(tmp_path) == target

    def test_excludes_inviscid_suffix(self, tmp_path):
        (tmp_path / "minfo1_e1_inviscid").write_text("inv\n", encoding="utf-8")
        target = tmp_path / "minfo1_e1"
        target.write_text("total\n", encoding="utf-8")
        assert find_total_force_file(tmp_path) == target

    def test_excludes_viscous_suffix(self, tmp_path):
        (tmp_path / "minfo1_e1_viscous").write_text("vis\n", encoding="utf-8")
        target = tmp_path / "minfo1_e1"
        target.write_text("total\n", encoding="utf-8")
        assert find_total_force_file(tmp_path) == target

    def test_returns_none_when_only_inviscid_present(self, tmp_path):
        """只有 _inviscid / _viscous,没有总力文件 → None。"""
        (tmp_path / "minfo1_e1_inviscid").write_text("inv\n", encoding="utf-8")
        (tmp_path / "minfo1_e1_viscous").write_text("vis\n", encoding="utf-8")
        assert find_total_force_file(tmp_path) is None

    def test_returns_none_when_no_files(self, tmp_path):
        assert find_total_force_file(tmp_path) is None

    def test_finds_op_name_suffix(self, tmp_path):
        """``minfo1_e1_Body`` (op 名后缀)应该被识别为总力文件。

        force_extract_core 会生成 ``minfo1_e1_<op_name>``,
        find_total_force_file 是为单 case 简单场景准备的,只要不带
        ``_inviscid`` / ``_viscous`` 后缀就算总力文件。
        """
        target = tmp_path / "minfo1_e1_Body"
        target.write_text("data\n", encoding="utf-8")
        assert find_total_force_file(tmp_path) == target


# ============================================================================
# Info1Step dataclass
# ============================================================================

class TestInfo1Step:
    def test_field_access(self):
        s = Info1Step(
            step=5, time=1.23e-3,
            total=(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            inv=(0.9, 1.9, 2.9, 3.9, 4.9, 5.9),
            vis=(0.1, 0.1, 0.1, 0.1, 0.1, 0.1),
        )
        assert s.step == 5
        assert s.time == pytest.approx(1.23e-3)
        assert s.total[2] == pytest.approx(3.0)
        assert s.vis[0] == pytest.approx(0.1)
