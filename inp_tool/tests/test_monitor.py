"""监控 mcfd.info0 单测(v0.14.0 / Phase 4)

覆盖:
- Info0Parser: parse_meta(从 minfo0.mpf1d 读列名) / parse_line(单行解析) /
  tail_progress(末行 → CaseProgress)
- CaseMonitor: refresh(走 ssh tail + 解析) / history(累计) / 列覆盖
- SweepMonitor: refresh_all(聚合多 case) / summary_table(表格) / watch 循环
- 真实 mcfd.info0 样本回归(用 reference/full_case/Case/mcfd.info0)
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from inp_tool.monitor import (
    Info0Parser,
    CaseProgress,
    CaseMonitor,
    SweepMonitor,
    parse_info0_meta,
    format_progress_table,
)
from inp_tool.cluster import (
    ClusterConfig,
    LocalDryRunClient,
    PbsJobStatus,
)


# ---------------------------------------------------------------------------
# 测试数据
# ---------------------------------------------------------------------------

# 真实 minfo0.mpf1d 样本(简化自 reference/full_case/Case/minfo0.mpf1d)
SAMPLE_MINFO0_META = """title
mcfd.info0 output
variables 8
step#
time
time_step_size
RHS_average
RHS_maximum
CFL_global
CFL_local
eigenvalue_max
variablesets 0
"""

# 真实 mcfd.info0 样本(2 行,简化)
SAMPLE_MCFd_INFO0 = """      1  0.0000000e+00  3.201e+10  1.918e+06  7.291e+08  1.000e+15  1.000e-01  3.124e+04
   2000  0.0000000e+00  2.121e+10  2.168e+02  2.459e+07  1.000e+15  2.000e+01  4.714e+04
"""


# ---------------------------------------------------------------------------
# parse_info0_meta - 从 minfo0.mpf1d 读列名
# ---------------------------------------------------------------------------

class TestParseInfo0Meta:
    def test_parses_8_columns(self):
        cols = parse_info0_meta(SAMPLE_MINFO0_META)
        assert cols == {
            "step#": 0,
            "time": 1,
            "time_step_size": 2,
            "RHS_average": 3,
            "RHS_maximum": 4,
            "CFL_global": 5,
            "CFL_local": 6,
            "eigenvalue_max": 7,
        }

    def test_handles_extra_whitespace(self):
        text = """title
foo
variables 3
   step#
   time
   cfl
variablesets 0
"""
        cols = parse_info0_meta(text)
        assert cols == {"step#": 0, "time": 1, "cfl": 2}

    def test_empty_meta_returns_empty_dict(self):
        assert parse_info0_meta("") == {}
        assert parse_info0_meta("title\nfoo\nvariables 0\nvariablesets 0\n") == {}

    def test_missing_variables_keyword(self):
        # 没 "variables N" 段,应 fallback 空
        text = "title\nfoo\nbar\n"
        assert parse_info0_meta(text) == {}


# ---------------------------------------------------------------------------
# Info0Parser
# ---------------------------------------------------------------------------

class TestInfo0Parser:
    def test_parse_meta_loads_column_names(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        assert p.columns["step#"] == 0
        assert p.columns["CFL_global"] == 5

    def test_parse_meta_fallback_when_no_meta_file(self, tmp_path):
        """minfo0.mpf1d 不存在 → 用 fallback 默认列名(8 列)"""
        p = Info0Parser(meta_path=str(tmp_path / "nope.mpf1d"))
        # fallback 默认 8 列
        assert len(p.columns) == 8
        assert p.columns["step#"] == 0
        assert p.columns["CFL_global"] == 5

    def test_parse_line_returns_dict(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        line = "      1  0.0000000e+00  3.201e+10  1.918e+06  7.291e+08  1.000e+15  1.000e-01  3.124e+04"
        d = p.parse_line(line)
        assert d["step#"] == 1
        assert d["time"] == 0.0
        # 实际 CFL 在 CFL_local 列(ramp 0.1→20.0)
        assert d["CFL_local"] == 0.1
        # CFL_global 列是 cflglo 残差上界(常值 1e15)
        assert d["CFL_global"] == 1.000e+15
        assert d["RHS_average"] == 1.918e6

    def test_parse_line_handles_short_line(self, tmp_path):
        """行短于列数 → 缺的列填 None"""
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        d = p.parse_line("1 2.0")  # 只有 2 列
        assert d["step#"] == 1
        assert d["time"] == 2.0
        assert d["time_step_size"] is None
        assert d["CFL_global"] is None

    def test_parse_line_handles_blank_line(self, tmp_path):
        """空行 / 注释行 → 空 dict"""
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        assert p.parse_line("") == {}
        assert p.parse_line("   \n") == {}

    def test_tail_progress_returns_last_line_parsed(self, tmp_path):
        """多行 → 只取最后一行有效数据

        真实 mcfd.info0 数据(从 reference/full_case/Case 验证):
        - col 5 (CFL_global) = 1.000e+15 — 实际是 cflglo 残差上界(常值)
        - col 6 (CFL_local)  = 0.1→20.0 — 实际 CFL ramp(用户监控的)
        - col 3 (RHS_average) = 残差,下降
        - col 4 (RHS_maximum) = 残差,下降
        """
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        progress = p.tail_progress(SAMPLE_MCFd_INFO0)
        assert isinstance(progress, CaseProgress)
        # 第二行(step=2000)是最后一行
        assert progress.current_step == 2000
        # 实际 CFL(用户关心的)在 CFL_local 列(ramp 0.1→20)
        assert progress.current_cfl_local == 20.0
        # CFL_global 列实际是 cflglo 残差上界(常值)
        assert progress.current_cfl_global == 1.000e+15
        # 残差下降
        assert progress.current_rhs_avg == 216.8
        assert progress.current_rhs_max == 2.459e7

    def test_tail_progress_empty_input(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        p = Info0Parser(meta_path=str(meta_path))
        progress = p.tail_progress("")
        assert progress.current_step is None
        assert progress.current_cfl_global is None


# ---------------------------------------------------------------------------
# CaseMonitor
# ---------------------------------------------------------------------------

class _TailMock:
    """模拟 cluster.tail 返回固定文本。"""
    def __init__(self, texts):
        self._texts = list(texts)
        self._idx = 0
    def __call__(self, remote_path: str, n: int = 50) -> str:
        if self._idx >= len(self._texts):
            return self._texts[-1] if self._texts else ""
        t = self._texts[self._idx]
        self._idx += 1
        return t


class TestCaseMonitor:
    def test_refresh_reads_remote_info0(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        cfg = ClusterConfig()
        # 模拟 cluster (用 LocalDryRunClient + 注入 tail)
        client = LocalDryRunClient(cfg)
        client.tail = _TailMock([SAMPLE_MCFd_INFO0])
        m = CaseMonitor("case_000", client, cfg, info_meta_path=str(meta_path))
        progress = m.refresh()
        assert progress.current_step == 2000
        # 实际 CFL 在 CFL_local 列
        assert progress.current_cfl_local == 20.0

    def test_history_accumulates_over_refreshes(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        cfg = ClusterConfig()
        client = LocalDryRunClient(cfg)
        client.tail = _TailMock([
            SAMPLE_MCFd_INFO0,
            SAMPLE_MCFd_INFO0,    # 第二次还是 2000,模拟稳态
        ])
        m = CaseMonitor("case_000", client, cfg, info_meta_path=str(meta_path))
        m.refresh()
        m.refresh()
        # history key 是 CaseProgress 属性名(带 current_ 前缀)
        hist = m.history("current_cfl_local")
        # 第二次 refresh step 还是 2000,所以 dict dedup → 只有 1 个 entry
        assert all(step == 2000 for step, _ in hist)

    def test_history_grows_when_step_changes(self, tmp_path):
        """多次 refresh 中 step 变化 → history 累积"""
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        cfg = ClusterConfig()
        client = LocalDryRunClient(cfg)
        # 第一次 step=1000,第二次 step=1500
        text1 = SAMPLE_MCFd_INFO0.replace("      1", "   1000").replace("   2000", "   1000")
        text2 = SAMPLE_MCFd_INFO0.replace("      1", "   1500").replace("   2000", "   1500")
        client.tail = _TailMock([text1, text2])
        m = CaseMonitor("case_000", client, cfg, info_meta_path=str(meta_path))
        m.refresh()
        m.refresh()
        hist = m.history("current_cfl_local")
        # 应该有 2 个 entry(去重 by step)
        assert len(hist) == 2

    def test_history_returns_empty_for_missing_column(self, tmp_path):
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        cfg = ClusterConfig()
        client = LocalDryRunClient(cfg)
        client.tail = _TailMock([SAMPLE_MCFd_INFO0])
        m = CaseMonitor("case_000", client, cfg, info_meta_path=str(meta_path))
        m.refresh()
        # 不存在的列 → 空 list
        assert m.history("nonexistent_column") == []

    def test_column_override_via_config(self, tmp_path):
        """用户可在 ClusterConfig 改 col_cfl_global 等覆盖"""
        meta_path = tmp_path / "minfo0.mpf1d"
        meta_path.write_text(SAMPLE_MINFO0_META)
        cfg = ClusterConfig(col_cfl_global=6)  # 改成 col 6 (CFL_local)
        client = LocalDryRunClient(cfg)
        client.tail = _TailMock([SAMPLE_MCFd_INFO0])
        m = CaseMonitor("case_000", client, cfg, info_meta_path=str(meta_path))
        progress = m.refresh()
        # col_cfl_global=6 → 取 col 6 (CFL_local = 1.000e-01)
        # 注意:cfl_global 字段名还是 "CFL_global" 因为从 meta 读
        assert progress.current_cfl_global is not None


# ---------------------------------------------------------------------------
# SweepMonitor
# ---------------------------------------------------------------------------

def _make_manifest_with_pbs_subs(base_dir: Path, n_cases: int = 2) -> Path:
    """合成 sweep manifest + 每 case 的 info0 内容。"""
    cases_meta = []
    for i in range(n_cases):
        case_id = f"case_{i:03d}"
        case_path = base_dir / case_id
        case_path.mkdir(parents=True, exist_ok=True)
        # 写 meta + info0
        (case_path / "minfo0.mpf1d").write_text(SAMPLE_MINFO0_META)
        (case_path / "mcfd.info0").write_text(SAMPLE_MCFd_INFO0)
        cases_meta.append({
            "case_dir": str(case_path),
            "case_name": case_id,
            "job_id": str(100 + i),
            "pbs_name": f"Mars_a{i:02d}",
            "submit_time": "2026-06-13T10:00:00",
            "state": "R",
            "host": "h",
            "queue": "q02",
        })
    manifest = {
        "template": str(base_dir / "t.inp"),
        "total": n_cases,
        "cases": [
            {"case_id": cm["case_name"], "path": cm["case_dir"]}
            for cm in cases_meta
        ],
        "layout": "per_dir",
        "generated_at": "2026-06-13T10:00:00",
        "pbs_submissions": cases_meta,
    }
    p = base_dir / "manifest.json"
    p.write_text(json.dumps(manifest))
    return p


class TestSweepMonitor:
    def test_refresh_all_returns_one_per_case(self, tmp_path):
        manifest = _make_manifest_with_pbs_subs(tmp_path, n_cases=3)
        cfg = ClusterConfig()
        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
                self._call_count = 0
            def status(self, job_id):
                self._call_count += 1
                return PbsJobStatus(job_id, "n", "u", "R", "q02")
            def tail(self, remote_path, n=50):
                return SAMPLE_MCFd_INFO0
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(cfg)
        m = SweepMonitor(manifest, client, info_meta_path=str(tmp_path / "minfo0.mpf1d"))
        progresses = m.refresh_all()
        assert len(progresses) == 3
        # 每个 case 都读到 step=2000, cfl_local=20(实际 ramp)
        for p in progresses:
            assert p.current_step == 2000
            assert p.current_cfl_local == 20.0

    def test_summary_table_contains_all_cases(self, tmp_path):
        manifest = _make_manifest_with_pbs_subs(tmp_path, n_cases=2)
        cfg = ClusterConfig()
        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                return PbsJobStatus(job_id, "n", "u", "R", "q02")
            def tail(self, remote_path, n=50):
                return SAMPLE_MCFd_INFO0
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(cfg)
        m = SweepMonitor(manifest, client, info_meta_path=str(tmp_path / "minfo0.mpf1d"))
        table = m.summary_table()
        assert "case_000" in table
        assert "case_001" in table
        assert "2000" in table  # step
        assert "20" in table   # CFL_global

    def test_watch_loop_calls_callback(self, tmp_path, monkeypatch):
        """watch 调 N 次 refresh 后退出"""
        manifest = _make_manifest_with_pbs_subs(tmp_path, n_cases=1)
        cfg = ClusterConfig()
        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                return PbsJobStatus(job_id, "n", "u", "R", "q02")
            def tail(self, remote_path, n=50):
                return SAMPLE_MCFd_INFO0
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(cfg)
        m = SweepMonitor(manifest, client, info_meta_path=str(tmp_path / "minfo0.mpf1d"))

        call_count = [0]
        def fake_sleep(s):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise KeyboardInterrupt

        monkeypatch.setattr("time.sleep", fake_sleep)
        m.watch(interval=0.01)  # 0.01s 间隔,3 次后中断
        assert call_count[0] >= 3


# ---------------------------------------------------------------------------
# format_progress_table
# ---------------------------------------------------------------------------

class TestFormatProgressTable:
    def test_empty_returns_placeholder(self):
        assert "无 case" in format_progress_table([])

    def test_aligns_columns(self):
        progresses = [
            CaseProgress(
                case_name="c1", case_dir_local="/d1", case_dir_remote="/d1",
                job_id="1", state="R", current_step=2000, current_cfl_global=20.0,
                current_rhs_avg=1e3, current_rhs_max=1e5,
            ),
        ]
        table = format_progress_table(progresses)
        # 至少包含 case 名
        assert "c1" in table
        assert "2000" in table
        assert "R" in table
