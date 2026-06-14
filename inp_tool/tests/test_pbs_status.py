"""PBS 状态查询单测(v0.14.0 / Phase 3)

覆盖:
- SweepStatusEntry dataclass(to_dict)
- query_sweep_status() 主流程(mock cluster)
- filter_states 过滤(R / Q / C / E 等)
- 无 pbs_submissions 段 → 空结果
- 多 case 状态聚合
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from inp_tool.batch import (
    PbsSubmission,
    SweepStatusEntry,
    query_sweep_status,
)
from inp_tool.cluster import (
    ClusterConfig,
    LocalDryRunClient,
    PbsJobStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_manifest_with_submissions(
    base_dir: Path,
    submissions: list = None,
) -> dict:
    """合成一个含 pbs_submissions 段的 manifest。"""
    if submissions is None:
        submissions = [
            {
                "case_dir": str(base_dir / "case_000"),
                "case_name": "case_000",
                "job_id": "100",
                "pbs_name": "Mars_a00",
                "submit_time": "2026-06-13T10:00:00",
                "state": "Q",
                "host": "10.10.10.251",
                "queue": "q02",
            },
            {
                "case_dir": str(base_dir / "case_001"),
                "case_name": "case_001",
                "job_id": "101",
                "pbs_name": "Mars_a01",
                "submit_time": "2026-06-13T10:00:01",
                "state": "R",
                "host": "10.10.10.251",
                "queue": "q02",
            },
        ]
    return {
        "template": str(base_dir / "template.inp"),
        "total": len(submissions),
        "cases": [
            {"case_id": s["case_name"], "path": s["case_dir"]}
            for s in submissions
        ],
        "layout": "per_dir",
        "generated_at": "2026-06-13T10:00:00",
        "pbs_submissions": submissions,
    }


# ---------------------------------------------------------------------------
# SweepStatusEntry dataclass
# ---------------------------------------------------------------------------

class TestSweepStatusEntry:
    def test_required_fields(self):
        e = SweepStatusEntry(
            case_name="case_000",
            job_id="100",
            pbs_name="Mars_a00",
            case_dir="/local/c0",
            state="R",
            queue="q02",
        )
        assert e.case_name == "case_000"
        assert e.state == "R"
        assert e.ncpus is None  # 可选

    def test_to_dict_includes_all(self):
        e = SweepStatusEntry(
            case_name="c1", job_id="1", pbs_name="p1",
            case_dir="/d", state="R", queue="q02",
            ncpus=48, walltime_req="04:00:00", walltime_used="01:00:00",
            start_time="2026-06-13T10:01:00", exec_host="node1/0*48",
        )
        d = e.to_dict()
        assert d["case_name"] == "c1"
        assert d["ncpus"] == 48
        assert d["exec_host"] == "node1/0*48"


# ---------------------------------------------------------------------------
# query_sweep_status - 主流程
# ---------------------------------------------------------------------------

class TestQuerySweepStatusHappyPath:
    def test_empty_manifest_returns_empty(self, tmp_path):
        manifest = {"template": str(tmp_path / "t"), "total": 0, "cases": []}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = query_sweep_status(manifest_path, client)
        assert result == []

    def test_manifest_without_pbs_submissions_returns_empty(self, tmp_path):
        """manifest 没有 pbs_submissions 段(还没提交)→ 空 list"""
        manifest = {
            "template": str(tmp_path / "t"),
            "total": 2,
            "cases": [
                {"case_id": "c0", "path": str(tmp_path / "c0")},
                {"case_id": "c1", "path": str(tmp_path / "c1")},
            ],
        }
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = query_sweep_status(manifest_path, client)
        assert result == []

    def test_returns_status_for_each_submission(self, tmp_path, monkeypatch):
        """mock cluster.status() 返回不同状态"""
        manifest = _make_manifest_with_submissions(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # mock cluster.status 按 job_id 返回不同状态
        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                if job_id == "100":
                    return PbsJobStatus(
                        job_id="100", name="Mars_a00", user="root",
                        state="Q", queue="q02", ncpus=48,
                        walltime_req="04:00:00",
                    )
                if job_id == "101":
                    return PbsJobStatus(
                        job_id="101", name="Mars_a01", user="root",
                        state="R", queue="q02", ncpus=48,
                        walltime_req="04:00:00", walltime_used="01:00:00",
                        exec_host="node1/0*48",
                    )
                return PbsJobStatus(job_id=job_id, name="", user="", state="Unknown", queue="")
            # 其余方法不需要
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(ClusterConfig())
        result = query_sweep_status(manifest_path, client)
        assert len(result) == 2
        # 排序应保留 manifest 顺序
        assert result[0].case_name == "case_000"
        assert result[0].state == "Q"
        assert result[0].ncpus == 48
        assert result[1].case_name == "case_001"
        assert result[1].state == "R"
        assert result[1].exec_host == "node1/0*48"


# ---------------------------------------------------------------------------
# query_sweep_status - filter_states
# ---------------------------------------------------------------------------

class TestQuerySweepStatusFilter:
    def test_filter_by_running(self, tmp_path):
        manifest = _make_manifest_with_submissions(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                if job_id == "100":
                    return PbsJobStatus("100", "n", "u", "Q", "q02")
                return PbsJobStatus("101", "n", "u", "R", "q02")
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(ClusterConfig())
        # 只看 running
        result = query_sweep_status(manifest_path, client, filter_states=["R"])
        assert len(result) == 1
        assert result[0].state == "R"
        assert result[0].case_name == "case_001"

    def test_filter_multiple_states(self, tmp_path):
        manifest = _make_manifest_with_submissions(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                return PbsJobStatus(job_id, "n", "u", "Q", "q02")
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(ClusterConfig())
        # 多个状态
        result = query_sweep_status(
            manifest_path, client, filter_states=["Q", "R"],
        )
        # 2 个 case 都是 Q → 都返回
        assert len(result) == 2

    def test_filter_no_match_returns_empty(self, tmp_path):
        manifest = _make_manifest_with_submissions(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        from inp_tool.cluster import ClusterClient
        class MockClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                return PbsJobStatus(job_id, "n", "u", "Q", "q02")
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = MockClient(ClusterConfig())
        # 过滤 C(完成)→ 没 case 符合
        result = query_sweep_status(
            manifest_path, client, filter_states=["C"],
        )
        assert result == []


# ---------------------------------------------------------------------------
# query_sweep_status - 错误处理
# ---------------------------------------------------------------------------

class TestQuerySweepStatusErrors:
    def test_missing_manifest_raises(self, tmp_path):
        client = LocalDryRunClient(ClusterConfig())
        with pytest.raises(FileNotFoundError):
            query_sweep_status(tmp_path / "nope.json", client)

    def test_status_failure_collected_as_unknown(self, tmp_path):
        """cluster.status() 抛异常时,该 case 进 entries 但 state='Unknown'"""
        manifest = _make_manifest_with_submissions(tmp_path)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        from inp_tool.cluster import ClusterClient
        class FlakyClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
            def status(self, job_id):
                if job_id == "100":
                    raise RuntimeError("qstat failed")
                return PbsJobStatus(job_id, "n", "u", "R", "q02")
            def probe(self): pass
            def submit(self, **kw): return "x"
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = FlakyClient(ClusterConfig())
        result = query_sweep_status(manifest_path, client)
        # 2 个 case:1 失败(state="Unknown"),1 成功(state="R")
        assert len(result) == 2
        # 第 1 个进 Unknown
        failed_entry = next(e for e in result if e.job_id == "100")
        assert failed_entry.state == "Unknown"
        # 第 2 个正常
        ok_entry = next(e for e in result if e.job_id == "101")
        assert ok_entry.state == "R"
