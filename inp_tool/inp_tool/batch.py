"""批量提交 sweep_report.json 中所有 case 到 PBS 集群(v0.14.0 / Phase 2)

零运行时依赖(纯 stdlib: dataclasses / json / pathlib / datetime / time)。

工作流:
1. 读 sweep_report.json(manifest)
2. 对每 case(per_dir + pbs=True 模式):
   a. 检查 skip-existing
   b. 检查并发限流(暂停等待,Q3)
   c. rsync 推整个 case_dir 到 <remote_workdir>/<case_name>/
   d. ssh + qsub 拿 job_id
   e. 收集 PbsSubmission
3. patch manifest,加 ``pbs_submissions`` 段(保留其他字段 + 已存在的旧 entries)
4. 返回 PbsBatchResult
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .cluster import ClusterClient


# ===========================================================================
# 数据类
# ===========================================================================

@dataclass
class PbsSubmission:
    """单 case 提交记录(v0.14.0 / Phase 2)。"""
    case_dir: str             # 本地路径
    case_name: str            # basename
    job_id: str
    pbs_name: str
    host: str
    queue: str
    state: str = "Q"          # 提交时默认 Q
    submit_time: str = field(default_factory=lambda: _iso_now())
    pbs_template: Optional[str] = None
    script_remote: Optional[str] = None   # 远端 pbs 脚本路径

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "case_dir": self.case_dir,
            "case_name": self.case_name,
            "job_id": self.job_id,
            "pbs_name": self.pbs_name,
            "submit_time": self.submit_time,
            "state": self.state,
            "host": self.host,
            "queue": self.queue,
        }
        if self.pbs_template is not None:
            d["pbs_template"] = self.pbs_template
        if self.script_remote is not None:
            d["script_remote"] = self.script_remote
        return d


@dataclass
class PbsBatchResult:
    """批量提交结果。"""
    submissions: List[PbsSubmission] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)    # (case_dir, error_msg)
    skipped: List[str] = field(default_factory=list)                # case_dir 列表(为什么跳)
    dry_run: bool = False
    elapsed_seconds: float = 0.0

    @property
    def total(self) -> int:
        return len(self.submissions) + len(self.failed) + len(self.skipped)


# ===========================================================================
# Helpers
# ===========================================================================

def _iso_now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ===========================================================================
# submit_sweep - 主流程
# ===========================================================================

def submit_sweep(
    sweep_report_path: Any,
    cluster: ClusterClient,
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    skip_existing: bool = True,
    pbs_overrides: Optional[Dict[str, str]] = None,
    respect_concurrency: bool = True,
    wait_timeout_seconds: int = 300,
    wait_poll_interval: int = 10,
) -> PbsBatchResult:
    """批量提交 sweep_report.json 中所有 case 到 PBS 集群。

    Args:
        sweep_report_path: manifest JSON 路径(Path 或 str)
        cluster: ClusterClient 实例(SshClusterClient / LocalDryRunClient)
        dry_run: True 时不真提交,只记录命令(走 LocalDryRunClient 默认行为)
        limit: 只提交前 N 个
        skip_existing: True 时,manifest 中已存在的 case 跳过
        pbs_overrides: 覆盖 pbs 脚本参数(如 ``{"-q": "q01"}``)
        respect_concurrency: True 时,超过 max_concurrent_jobs 暂停等待
        wait_timeout_seconds: 并发限流等待超时(默认 5 分钟)
        wait_poll_interval: 检查并发的间隔秒

    Returns:
        PbsBatchResult 含 submissions / failed / skipped / elapsed_seconds
    """
    start = time.time()
    report_path = Path(sweep_report_path)
    if not report_path.is_file():
        raise FileNotFoundError(f"sweep_report.json 不存在: {report_path}")
    manifest: Dict[str, Any] = json.loads(report_path.read_text())
    cases: List[Dict[str, Any]] = list(manifest.get("cases", []))

    # 已有 pbs_submissions(用于 skip_existing)
    existing_submissions: List[Dict[str, Any]] = list(manifest.get("pbs_submissions", []))
    submitted_case_dirs: set = {
        s.get("case_dir") for s in existing_submissions
    }

    result = PbsBatchResult(dry_run=dry_run)

    # 取 limit
    if limit is not None and limit > 0:
        skipped_by_limit = cases[limit:]
        cases = cases[:limit]
        for c in skipped_by_limit:
            case_dir = c.get("path", "")
            result.skipped.append(f"{case_dir} (beyond limit={limit})")

    cfg = cluster.config
    user = cfg.user
    max_concurrent = cfg.max_concurrent_jobs
    remote_root = cfg.remote_workdir.rstrip("/")

    timed_out_due_to_concurrency: set = set()

    for idx, case in enumerate(cases):
        case_dir = case.get("path", "")
        case_name = case.get("case_id") or Path(case_dir).name
        pbs_name = case.get("pbs_name")
        pbs_template = case.get("pbs_template")

        # 1. skip-existing
        if skip_existing and case_dir in submitted_case_dirs:
            result.skipped.append(f"{case_dir} (already in pbs_submissions)")
            continue

        # 2. flat 模式 / pbs disabled → 跳过
        if not pbs_name:
            result.skipped.append(f"{case_dir} (no pbs_name; flat layout or pbs disabled)")
            continue

        # 3. 并发限流(暂停等待,Q3)
        if respect_concurrency and not dry_run:
            waited = 0.0
            timed_out = False
            while True:
                current = cluster.check_concurrency(user)
                if current < max_concurrent:
                    break
                if waited >= wait_timeout_seconds:
                    result.failed.append((
                        case_dir,
                        f"concurrency limit timeout: {current} ≥ {max_concurrent} for {wait_timeout_seconds}s"
                    ))
                    timed_out = True
                    break
                time.sleep(wait_poll_interval)
                waited += wait_poll_interval
            if timed_out:
                continue

        # 4. 真提交
        try:
            remote_case_dir = f"{remote_root}/{case_name}"
            script_text = _load_script_text(case_dir, pbs_template, pbs_name)
            job_id = cluster.submit(
                script_text=script_text,
                remote_dir=remote_case_dir,
                pbs_overrides=pbs_overrides,
            )
            submission = PbsSubmission(
                case_dir=case_dir,
                case_name=case_name,
                job_id=job_id,
                pbs_name=pbs_name,
                host=cfg.host,
                queue=cfg.default_queue,
                pbs_template=pbs_template,
                script_remote=f"{remote_case_dir}/run_{pbs_name}.pbs",
            )
            result.submissions.append(submission)
        except Exception as e:
            result.failed.append((case_dir, str(e)))

    # 5. patch manifest
    _patch_manifest(report_path, manifest, result)

    result.elapsed_seconds = time.time() - start
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_script_text(case_dir: str, pbs_template: Optional[str], pbs_name: str) -> str:
    """读 case_dir 下的 pbs 脚本文本。

    优先 pbs_template(manifest 里写明的文件名),否则用 ``run_<pbs_name>.pbs``。
    """
    case_path = Path(case_dir)
    candidates: List[Path] = []
    if pbs_template:
        # pbs_template 形如 "run_{pbs_name}.pbs" → 在 case_dir 下找
        candidates.append(case_path / pbs_template)
    # fallback:标准命名
    candidates.append(case_path / f"run_{pbs_name}.pbs")
    for c in candidates:
        if c.is_file():
            return c.read_text()
    raise FileNotFoundError(
        f"case {case_dir} 找不到 pbs 脚本(试过: {[str(c) for c in candidates]})"
    )


def _patch_manifest(
    report_path: Path,
    manifest: Dict[str, Any],
    result: PbsBatchResult,
) -> None:
    """把 result.submissions 追加到 manifest['pbs_submissions'],写回文件。

    保留:
    - 原有 pbs_submissions(老的 job_id 记录)
    - 原有其他字段(template / cases / layout / generated_at / 等)
    """
    existing: List[Dict[str, Any]] = list(manifest.get("pbs_submissions", []))
    # 过滤掉本次重提的同名 case(避免重复)
    new_submission_dirs = {s.case_dir for s in result.submissions}
    kept = [s for s in existing if s.get("case_dir") not in new_submission_dirs]
    # 追加本次新的
    kept.extend(s.to_dict() for s in result.submissions)
    manifest["pbs_submissions"] = kept
    report_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )


# ===========================================================================
# v0.14.0 / Phase 3:状态查询
# ===========================================================================

@dataclass
class SweepStatusEntry:
    """单 case 状态条目(本地 manifest 字段 + 实时 qstat 字段的并集)。"""
    case_name: str
    job_id: str
    pbs_name: str
    case_dir: str
    state: str                       # Q|R|E|H|C|Unknown
    queue: str
    submit_time: str = ""            # 来自 manifest
    ncpus: Optional[int] = None
    walltime_req: Optional[str] = None
    walltime_used: Optional[str] = None
    start_time: Optional[str] = None
    exec_host: Optional[str] = None
    exit_status: Optional[int] = None
    live: bool = True                # True = 来自 qstat;False = qstat 失败(默认 Unknown)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "case_name": self.case_name,
            "job_id": self.job_id,
            "pbs_name": self.pbs_name,
            "case_dir": self.case_dir,
            "state": self.state,
            "queue": self.queue,
            "submit_time": self.submit_time,
            "live": self.live,
        }
        if self.ncpus is not None:
            d["ncpus"] = self.ncpus
        if self.walltime_req is not None:
            d["walltime_req"] = self.walltime_req
        if self.walltime_used is not None:
            d["walltime_used"] = self.walltime_used
        if self.start_time is not None:
            d["start_time"] = self.start_time
        if self.exec_host is not None:
            d["exec_host"] = self.exec_host
        if self.exit_status is not None:
            d["exit_status"] = self.exit_status
        return d


def query_sweep_status(
    sweep_report_path: Any,
    cluster: ClusterClient,
    *,
    filter_states: Optional[Sequence[str]] = None,
) -> List[SweepStatusEntry]:
    """读 sweep_report.json, 对每个 pbs_submission 调 cluster.status() 聚合。

    Args:
        sweep_report_path: manifest JSON 路径
        cluster: ClusterClient 实例(通常 SshClusterClient)
        filter_states: 逗号分隔的 state 过滤(如 ``["R", "Q"]`` 只返回运行 + 排队)

    Returns:
        list[SweepStatusEntry],按 manifest 原顺序

    错误处理:
    - manifest 缺失 → raise FileNotFoundError
    - cluster.status() 单个失败 → 该 entry 标 state="Unknown" / live=False,不抛
    """
    report_path = Path(sweep_report_path)
    if not report_path.is_file():
        raise FileNotFoundError(f"sweep_report.json 不存在: {report_path}")
    manifest: Dict[str, Any] = json.loads(report_path.read_text())
    submissions: List[Dict[str, Any]] = list(manifest.get("pbs_submissions", []))

    filter_set: Optional[set] = set(filter_states) if filter_states else None
    results: List[SweepStatusEntry] = []

    for sub in submissions:
        job_id = sub.get("job_id", "")
        # 1. 调 cluster.status 单个 job
        try:
            live_status = cluster.status(job_id)
        except Exception:
            # qstat 失败:用 manifest 字段填,state="Unknown"
            results.append(SweepStatusEntry(
                case_name=sub.get("case_name", ""),
                job_id=job_id,
                pbs_name=sub.get("pbs_name", ""),
                case_dir=sub.get("case_dir", ""),
                state="Unknown",
                queue=sub.get("queue", ""),
                submit_time=sub.get("submit_time", ""),
                live=False,
            ))
            continue

        entry = SweepStatusEntry(
            case_name=sub.get("case_name", ""),
            job_id=job_id,
            pbs_name=live_status.name or sub.get("pbs_name", ""),
            case_dir=sub.get("case_dir", ""),
            state=live_status.state,
            queue=live_status.queue or sub.get("queue", ""),
            submit_time=sub.get("submit_time", ""),
            ncpus=live_status.ncpus,
            walltime_req=live_status.walltime_req,
            walltime_used=live_status.walltime_used,
            start_time=live_status.start_time,
            exec_host=live_status.exec_host,
            exit_status=live_status.exit_status,
            live=True,
        )
        # 2. 过滤
        if filter_set is not None and entry.state not in filter_set:
            continue
        results.append(entry)

    return results


# ===========================================================================
# v0.14.0 / Phase 3:状态汇总(给 CLI 用)
# ===========================================================================

def summarize_states(entries: Sequence[SweepStatusEntry]) -> Dict[str, int]:
    """统计 state 分布,给 CLI 显示"3 Q / 5 R / 2 C"。"""
    summary: Dict[str, int] = {}
    for e in entries:
        summary[e.state] = summary.get(e.state, 0) + 1
    return summary


def format_status_table(entries: Sequence[SweepStatusEntry]) -> str:
    """渲染对齐的终端表格(给 ``pbs status`` 用)。"""
    if not entries:
        return "(无 case)"
    headers = ["case", "job_id", "state", "queue", "ncpu", "walltime_used", "exec_host"]
    rows: List[List[str]] = []
    for e in entries:
        rows.append([
            e.case_name,
            e.job_id,
            e.state,
            e.queue,
            str(e.ncpus) if e.ncpus is not None else "-",
            e.walltime_used or "-",
            e.exec_host or "-",
        ])
    # 计算每列宽度
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    # 头
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    # 行
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)
