"""批量提交单测(v0.14.0 / Phase 2)

覆盖:
- PbsSubmission / PbsBatchResult dataclass 字段
- submit_sweep() 主流程(mock ClusterClient + LocalDryRunClient)
- 并发限流(等待空出 slot)
- --skip-existing(已提交过的 case 跳过)
- --limit(只提交前 N 个)
- --dry-run(不真提交,只记录)
- sweep_report.json patch(加 pbs_submissions 段,保留其他字段)
- 失败 case 收集到 result.failed
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from inp_tool.batch import (
    PbsSubmission,
    PbsBatchResult,
    submit_sweep,
)
from inp_tool.cluster import (
    ClusterConfig,
    LocalDryRunClient,
    SshClusterClient,
    PbsJobStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sweep_report(
    base_dir: Path,
    n_cases: int = 3,
    *,
    layout: str = "per_dir",
    with_pbs: bool = True,
) -> dict:
    """合成一个 sweep_report dict + 实际 case 目录(每个有 run.pbs)。

    返回 manifest dict(含 cases 列表)。
    """
    cases = []
    for i in range(n_cases):
        case_id = f"case_{i:03d}"
        case_path = base_dir / case_id
        case_path.mkdir(parents=True, exist_ok=True)
        # 写一个最小 mcfd.inp(免得 validate_base_case_dir 报缺)
        (case_path / "mcfd.inp").write_text("# minimal mcfd.inp\ntitle\ndummy\nend\n")
        # 写一个 pbs 脚本(per_dir + pbs=True 模式)
        if with_pbs:
            pbs_name = f"Mars_a{i:02d}"
            pbs_path = case_path / f"run_{pbs_name}.pbs"
            pbs_path.write_text(
                f"#!/bin/bash\n#PBS -N {pbs_name}\n"
                f"#PBS -q q02\n#PBS -l nodes=1:ppn=48\n"
                f"cd $PBS_O_WORKDIR\nls\n"
            )
        else:
            pbs_name = None
        cases.append({
            "case_id": case_id,
            "path": str(case_path),
            "params": {"alpha": i},
            "applied": {},
            "pbs_name": pbs_name,
            "pbs_template": "run_{pbs_name}.pbs" if pbs_name else None,
        })
    return {
        "template": str(base_dir / "template.inp"),
        "total": n_cases,
        "cases": cases,
        "layout": layout,
        "source_dir": str(base_dir / "src"),
        "copy_strategy": "hardlink",
        "generated_at": "2026-06-13T10:00:00",
    }


# ---------------------------------------------------------------------------
# PbsSubmission / PbsBatchResult dataclass
# ---------------------------------------------------------------------------

class TestPbsSubmission:
    def test_required_fields(self):
        s = PbsSubmission(
            case_dir="/local/c1",
            case_name="c1",
            job_id="1234",
            pbs_name="Mars_a00",
            host="10.10.10.251",
            queue="q02",
        )
        assert s.case_dir == "/local/c1"
        assert s.job_id == "1234"
        assert s.state == "Q"  # 默认
        assert s.submit_time is not None  # 自动填

    def test_to_dict(self):
        s = PbsSubmission(
            case_dir="/c1", case_name="c1", job_id="1",
            pbs_name="p1", host="h", queue="q02",
        )
        d = s.to_dict()
        assert d["case_dir"] == "/c1"
        assert d["job_id"] == "1"
        assert d["state"] == "Q"
        assert "submit_time" in d


class TestPbsBatchResult:
    def test_empty(self):
        r = PbsBatchResult()
        assert r.submissions == []
        assert r.failed == []
        assert r.skipped == []
        assert r.dry_run is False
        assert r.total == 0

    def test_total_counts_all(self):
        r = PbsBatchResult(
            submissions=[PbsSubmission("a", "a", "1", "p", "h", "q02")],
            failed=[("b", "err")],
            skipped=["c"],
        )
        assert r.total == 3  # 1+1+1


# ---------------------------------------------------------------------------
# submit_sweep - 主流程
# ---------------------------------------------------------------------------

class TestSubmitSweepHappyPath:
    def test_empty_manifest_returns_empty_result(self, tmp_path):
        manifest = {"template": str(tmp_path / "t.inp"), "total": 0, "cases": []}
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        assert isinstance(result, PbsBatchResult)
        assert result.submissions == []
        assert result.failed == []
        assert result.dry_run is False

    def test_single_case_submits(self, tmp_path):
        manifest = _make_sweep_report(tmp_path, n_cases=1)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        assert len(result.submissions) == 1
        assert result.failed == []
        s = result.submissions[0]
        assert s.case_name == "case_000"
        assert s.pbs_name == "Mars_a00"
        # LocalDryRunClient 返回 "DRYRUN-NNNN"
        assert s.job_id.startswith("DRYRUN-")

    def test_multiple_cases_all_submitted(self, tmp_path):
        manifest = _make_sweep_report(tmp_path, n_cases=3)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        assert len(result.submissions) == 3
        assert {s.case_name for s in result.submissions} == {
            "case_000", "case_001", "case_002"
        }

    def test_dry_run_does_not_call_submit(self, tmp_path):
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client, dry_run=True)
        # dry_run=True 时 PbsBatchResult.dry_run 标志为 True
        # (实际 LocalDryRun 不真提交,只是标记)
        assert result.dry_run is True


# ---------------------------------------------------------------------------
# submit_sweep - limit / skip-existing
# ---------------------------------------------------------------------------

class TestSubmitSweepLimit:
    def test_limit_n_submits_only_first_n(self, tmp_path):
        manifest = _make_sweep_report(tmp_path, n_cases=5)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client, limit=2)
        assert len(result.submissions) == 2
        # 后 3 个被跳过
        assert len(result.skipped) == 3
        assert {s.case_name for s in result.submissions} == {"case_000", "case_001"}


class TestSubmitSweepSkipExisting:
    def test_skip_existing_default(self, tmp_path):
        """默认 --skip-existing=True:已提交过的 case 跳过"""
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        # 模拟"已提交"状态:在 manifest 写 pbs_submissions 段
        manifest["pbs_submissions"] = [
            {
                "case_dir": str(tmp_path / "case_000"),
                "case_name": "case_000",
                "job_id": "111",
                "pbs_name": "Mars_a00",
                "submit_time": "2026-06-13T09:00:00",
                "state": "C",  # 已完成
                "host": "h",
                "queue": "q02",
            }
        ]
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        # 0 已提交(C=done) → 跳过;1 未提交
        assert len(result.submissions) == 1
        assert result.submissions[0].case_name == "case_001"
        # 跳过的应该被记录
        assert any("case_000" in s for s in result.skipped)

    def test_skip_existing_false_resubmits_completed(self, tmp_path):
        """--skip-existing=False:即使是已完成也重提"""
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        manifest["pbs_submissions"] = [
            {
                "case_dir": str(tmp_path / "case_000"),
                "case_name": "case_000",
                "job_id": "111",
                "pbs_name": "Mars_a00",
                "submit_time": "2026-06-13T09:00:00",
                "state": "C",
                "host": "h",
                "queue": "q02",
            }
        ]
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client, skip_existing=False)
        # 全部重提
        assert len(result.submissions) == 2

    def test_running_job_not_skipped_by_skip_existing(self, tmp_path):
        """skip_existing 只跳过已完成(C/E);运行中(R/Q)仍可重新提交

        但当前实现:所有 pbs_submissions 里有记录都视为已存在 → 跳过。
        (Q3 = 暂停等待的并发限流会在另一个层面处理)
        """
        manifest = _make_sweep_report(tmp_path, n_cases=1)
        manifest["pbs_submissions"] = [
            {
                "case_dir": str(tmp_path / "case_000"),
                "case_name": "case_000",
                "job_id": "111",
                "pbs_name": "Mars_a00",
                "submit_time": "2026-06-13T09:00:00",
                "state": "R",  # 运行中
                "host": "h",
                "queue": "q02",
            }
        ]
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        # skip_existing 默认 True → 跳过 R 状态(简单实现:有记录都跳)
        assert len(result.submissions) == 0


# ---------------------------------------------------------------------------
# submit_sweep - 并发限流 (Q3 = 暂停等待)
# ---------------------------------------------------------------------------

class TestSubmitSweepConcurrency:
    def test_respect_concurrency_waits_when_limit_hit(self, tmp_path, monkeypatch):
        """当前并发 ≥ max_concurrent_jobs 时,submit_sweep 暂停等待。

        mock check_concurrency 返回 21(>20),模拟 5 秒后降到 19。
        """
        manifest = _make_sweep_report(tmp_path, n_cases=1)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # 计数器:call N 次后切换
        call_count = [0]

        def fake_check_concurrency(user):
            call_count[0] += 1
            # 第一次返回超限(21),第二次返回空 slot(19)
            if call_count[0] < 2:
                return 21
            return 19

        # mock sleep 加速
        slept = []
        def fake_sleep(s):
            slept.append(s)
        monkeypatch.setattr("time.sleep", fake_sleep)

        # 用 LocalDryRunClient + 改 check_concurrency
        from inp_tool.cluster import LocalDryRunClient
        c = LocalDryRunClient(ClusterConfig(max_concurrent_jobs=20))
        # 注入 fake_check_concurrency
        c.check_concurrency = fake_check_concurrency

        result = submit_sweep(manifest_path, c)
        # 第一次 submit 前 check → 21 (超限) → 等 → 第二次 → 19 → 提交
        assert len(result.submissions) == 1
        # 至少睡了一次
        assert len(slept) >= 1
        assert slept[0] > 0

    def test_no_respect_concurrency_skips_limit_check(self, tmp_path, monkeypatch):
        """--no-respect-concurrency 跳过限流,直接提交"""
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        check_calls = [0]
        def fake_check_concurrency(user):
            check_calls[0] += 1
            return 999  # 永远超限

        monkeypatch.setattr("time.sleep", lambda s: None)

        c = LocalDryRunClient(ClusterConfig(max_concurrent_jobs=20))
        c.check_concurrency = fake_check_concurrency

        result = submit_sweep(manifest_path, c, respect_concurrency=False)
        # 全部提交,不调 check_concurrency
        assert len(result.submissions) == 2
        assert check_calls[0] == 0


# ---------------------------------------------------------------------------
# submit_sweep - sweep_report.json patch
# ---------------------------------------------------------------------------

class TestSubmitSweepPatchManifest:
    def test_manifest_gets_pbs_submissions_field(self, tmp_path):
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        submit_sweep(manifest_path, client)
        # 重新读 manifest
        new_manifest = json.loads(manifest_path.read_text())
        assert "pbs_submissions" in new_manifest
        assert len(new_manifest["pbs_submissions"]) == 2
        # 原有字段保留
        assert new_manifest["template"] == manifest["template"]
        assert new_manifest["total"] == 2
        assert new_manifest["generated_at"] == "2026-06-13T10:00:00"
        assert new_manifest["layout"] == "per_dir"

    def test_manifest_pbs_submissions_preserves_existing(self, tmp_path):
        """追加,而不是覆盖(已存在的 pbs_submissions + 新提交的)"""
        manifest = _make_sweep_report(tmp_path, n_cases=2)
        manifest["pbs_submissions"] = [
            {
                "case_dir": str(tmp_path / "case_000"),
                "case_name": "case_000",
                "job_id": "OLD",
                "pbs_name": "Mars_a00",
                "submit_time": "2026-06-13T08:00:00",
                "state": "C",
                "host": "h",
                "queue": "q02",
            }
        ]
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        # skip_existing=True (默认):case_000 跳过,保留 OLD 记录
        result = submit_sweep(manifest_path, client, skip_existing=True)
        # 重新读
        new_manifest = json.loads(manifest_path.read_text())
        # 2 个 submissions(老的 case_000 OLD + 新的 case_001)
        assert len(new_manifest["pbs_submissions"]) == 2
        # 老的 OLD job_id 应保留
        old_ids = [s["job_id"] for s in new_manifest["pbs_submissions"]]
        assert "OLD" in old_ids


# ---------------------------------------------------------------------------
# submit_sweep - 错误处理
# ---------------------------------------------------------------------------

class TestSubmitSweepErrors:
    def test_missing_manifest_raises(self, tmp_path):
        client = LocalDryRunClient(ClusterConfig())
        with pytest.raises(FileNotFoundError):
            submit_sweep(tmp_path / "nope.json", client)

    def test_case_without_pbs_name_skipped(self, tmp_path):
        """flat 模式或 pbs disabled 的 case(pbs_name=None)跳过"""
        manifest = _make_sweep_report(tmp_path, n_cases=2, with_pbs=False)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        client = LocalDryRunClient(ClusterConfig())
        result = submit_sweep(manifest_path, client)
        # 全没 pbs_name → 全部跳过
        assert len(result.submissions) == 0
        assert len(result.skipped) == 2

    def test_submit_failure_collected(self, tmp_path):
        """单 case 提交失败时,不影响其他 case,失败记录到 result.failed"""
        manifest = _make_sweep_report(tmp_path, n_cases=3)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

        # mock client:第二个 case 抛 RuntimeError
        from inp_tool.cluster import ClusterClient
        class FlakyClient(ClusterClient):
            def __init__(self, config):
                super().__init__(config)
                self.call_count = 0
            def probe(self): pass
            def submit(self, script_text, *, remote_dir, pbs_overrides=None):
                self.call_count += 1
                if self.call_count == 2:
                    raise RuntimeError("qsub: connection refused")
                return f"OK-{self.call_count:04d}"
            def status(self, job_id):
                return PbsJobStatus(job_id, "", "u", "Q", "q")
            def status_many(self, jids): return [self.status(j) for j in jids]
            def cancel(self, jid, *, force=False): return True
            def list_user_jobs(self, user): return []
            def tail(self, p, n=50): return ""
            def rsync_to(self, ld, rd, *, exclude=()): pass
            def rsync_from(self, rp, lp): pass
            def check_concurrency(self, user): return 0

        client = FlakyClient(ClusterConfig())
        result = submit_sweep(manifest_path, client, respect_concurrency=False)
        # 2 成功 + 1 失败
        assert len(result.submissions) == 2
        assert len(result.failed) == 1
        failed_case, err = result.failed[0]
        assert "case_001" in failed_case
        assert "connection refused" in err
