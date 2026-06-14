"""运行中监控(v0.14.0 / Phase 4)

读 ``mcfd.info0``(1 行/步, 8 列)拿当前 step / CFL / 残差。
列名从 ``minfo0.mpf1d`` 动态读,不 hardcode。

零运行时依赖(纯 stdlib: dataclasses / datetime / json / re / pathlib / time)。

设计:
- :func:`parse_info0_meta`: 解析 minfo0.mpf1d → ``dict[col_name, index]``
- :class:`Info0Parser`: 包装 minfo0 meta + parse_line + tail_progress
- :class:`CaseProgress` dataclass: 单 case 实时状态聚合
  (case_name / state / step / time / dt / cfl_global / cfl_local /
  rhs_avg / rhs_max / eigenvalue / last_update / log_offset)
- :class:`CaseMonitor`: 包装 cluster.tail + parser,refresh() 拉一次
- :class:`SweepMonitor`: 聚合所有 case + watch loop
- :func:`format_progress_table`: 终端表格
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .cluster import ClusterClient, ClusterConfig


# ===========================================================================
# 解析 mcfd.info0 / minfo0.mpf1d
# ===========================================================================

# minfo0.mpf1d 格式:
#   title
#   <输出文件名,如 "mcfd.info0 output">
#   variables N
#   <列名 1>
#   <列名 2>
#   ...
#   <列名 N>
#   variablesets 0
#
# 列名顺序与 mcfd.info0 文件中每行的列一一对应

_MINFO0_VARIABLES_RE = re.compile(r"^variables\s+(\d+)\s*$", re.MULTILINE)


def parse_info0_meta(text: str) -> Dict[str, int]:
    """解析 minfo0.mpf1d 文本,返回 ``{col_name: index}`` 映射。

    没找到 ``variables N`` 段或 N=0,返回 ``{}``。
    """
    if not text:
        return {}
    m = _MINFO0_VARIABLES_RE.search(text)
    if not m:
        return {}
    n = int(m.group(1))
    if n <= 0:
        return {}
    lines = text.splitlines()
    try:
        idx = next(i for i, ln in enumerate(lines) if _MINFO0_VARIABLES_RE.match(ln))
    except StopIteration:
        return {}
    col_names = [ln.strip() for ln in lines[idx + 1: idx + 1 + n]]
    return {name: i for i, name in enumerate(col_names)}


# 默认 fallback(8 列,来自 reference/full_case/Case/minfo0.mpf1d)
DEFAULT_INFO0_COLUMNS: Dict[str, int] = {
    "step#": 0,
    "time": 1,
    "time_step_size": 2,
    "RHS_average": 3,
    "RHS_maximum": 4,
    "CFL_global": 5,
    "CFL_local": 6,
    "eigenvalue_max": 7,
}


def _to_float(s: str) -> Optional[float]:
    """安全的 float 转换,失败返回 None。"""
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _to_int(s: str) -> Optional[int]:
    """安全的 int 转换(允许 '1.0' 等 float-形式数字)。"""
    f = _to_float(s)
    if f is None:
        return None
    try:
        return int(f)
    except (ValueError, OverflowError):
        return None


# ===========================================================================
# Info0Parser
# ===========================================================================

class Info0Parser:
    """mcfd.info0 解析器(列名从 minfo0.mpf1d 读,失败 fallback 默认 8 列)。"""

    def __init__(
        self,
        meta_path: Optional[str] = None,
        config: Optional[ClusterConfig] = None,
    ):
        self.meta_path = meta_path
        self.config = config
        if meta_path and Path(meta_path).is_file():
            try:
                self.columns = parse_info0_meta(Path(meta_path).read_text())
            except OSError:
                self.columns = {}
        else:
            self.columns = {}
        if not self.columns:
            self.columns = dict(DEFAULT_INFO0_COLUMNS)

    def parse_line(self, line: str) -> Dict[str, Optional[float]]:
        """解析单行(8 列空格分隔),返回 ``{col_name: value}`` 映射。

        行短于列数 → 缺的列填 None。
        空行 / 注释行 → ``{}``。
        """
        line = line.strip()
        if not line or line.startswith("#"):
            return {}
        parts = line.split()
        result: Dict[str, Optional[float]] = {}
        for col_name, col_idx in self.columns.items():
            if col_idx < len(parts):
                result[col_name] = _to_float(parts[col_idx])
            else:
                result[col_name] = None
        return result

    def tail_progress(
        self,
        text: str,
        *,
        case_name: str = "",
        case_dir_local: str = "",
        case_dir_remote: str = "",
        job_id: Optional[str] = None,
        state: str = "Unknown",
    ) -> "CaseProgress":
        """取文本的**最后一行**有效数据,生成 CaseProgress。"""
        last_row: Dict[str, Optional[float]] = {}
        for line in text.splitlines():
            row = self.parse_line(line)
            if row:
                last_row = row
        col_step = self.config.col_step if self.config else 0
        col_time = self.config.col_time if self.config else 1
        col_dt = self.config.col_dt if self.config else 2
        col_rhs_avg = self.config.col_rhs_avg if self.config else 3
        col_rhs_max = self.config.col_rhs_max if self.config else 4
        col_cfl_global = self.config.col_cfl_global if self.config else 5
        col_cfl_local = self.config.col_cfl_local if self.config else 6
        col_eigenvalue = self.config.col_eigenvalue if self.config else 7

        def _by_idx(idx: int) -> Optional[float]:
            for cn, ci in self.columns.items():
                if ci == idx and cn in last_row:
                    return last_row[cn]
            return None

        return CaseProgress(
            case_name=case_name,
            case_dir_local=case_dir_local,
            case_dir_remote=case_dir_remote,
            job_id=job_id,
            state=state,
            current_step=_to_int(str(_by_idx(col_step))) if _by_idx(col_step) is not None else None,
            current_time=_by_idx(col_time),
            current_dt=_by_idx(col_dt),
            current_rhs_avg=_by_idx(col_rhs_avg),
            current_rhs_max=_by_idx(col_rhs_max),
            current_cfl_global=_by_idx(col_cfl_global),
            current_cfl_local=_by_idx(col_cfl_local),
            current_eigenvalue=_by_idx(col_eigenvalue),
            last_update=datetime.now(),
            log_offset=len(text.encode("utf-8")),
            parse_warnings=[],
        )


# ===========================================================================
# CaseProgress dataclass
# ===========================================================================

@dataclass
class CaseProgress:
    """单 case 实时状态聚合(v0.14.0 / Phase 4)。"""
    case_name: str
    case_dir_local: str
    case_dir_remote: str
    job_id: Optional[str] = None
    state: str = "Unknown"
    current_step: Optional[int] = None
    current_time: Optional[float] = None
    current_dt: Optional[float] = None
    current_cfl_global: Optional[float] = None
    current_cfl_local: Optional[float] = None
    current_rhs_avg: Optional[float] = None
    current_rhs_max: Optional[float] = None
    current_eigenvalue: Optional[float] = None
    last_update: datetime = field(default_factory=datetime.now)
    log_offset: int = 0
    parse_warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "case_name": self.case_name,
            "case_dir_local": self.case_dir_local,
            "case_dir_remote": self.case_dir_remote,
            "state": self.state,
            "last_update": self.last_update.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        if self.job_id is not None:
            d["job_id"] = self.job_id
        if self.current_step is not None:
            d["current_step"] = self.current_step
        if self.current_time is not None:
            d["current_time"] = self.current_time
        if self.current_dt is not None:
            d["current_dt"] = self.current_dt
        if self.current_cfl_global is not None:
            d["current_cfl_global"] = self.current_cfl_global
        if self.current_cfl_local is not None:
            d["current_cfl_local"] = self.current_cfl_local
        if self.current_rhs_avg is not None:
            d["current_rhs_avg"] = self.current_rhs_avg
        if self.current_rhs_max is not None:
            d["current_rhs_max"] = self.current_rhs_max
        if self.current_eigenvalue is not None:
            d["current_eigenvalue"] = self.current_eigenvalue
        return d


# ===========================================================================
# CaseMonitor
# ===========================================================================

class CaseMonitor:
    """单 case 监控器。

    走 ``cluster.tail(remote_path)`` 读远端 ``mcfd.info0``(走 SSH),本地解析。
    """

    def __init__(
        self,
        case_name: str,
        cluster: ClusterClient,
        config: ClusterConfig,
        *,
        info_meta_path: Optional[str] = None,
    ):
        self.case_name = case_name
        self.cluster = cluster
        self.config = config
        self.case_dir_local = ""
        self.remote_info0 = f"{config.remote_workdir.rstrip('/')}/{case_name}/{config.info_file}"
        self.parser = Info0Parser(meta_path=info_meta_path, config=config)
        self._history: Dict[str, List[tuple]] = {}
        self._last_step: Optional[int] = None
        self._job_id: Optional[str] = None

    def set_job_id(self, job_id: Optional[str]) -> None:
        """SweepMonitor 用,设 job_id 后 refresh 会拉 qstat state。"""
        self._job_id = job_id

    def refresh(self) -> CaseProgress:
        """读一次远端 mcfd.info0 末行,返回 CaseProgress。"""
        text = self.cluster.tail(self.remote_info0, n=50)
        state = "Unknown"
        if self._job_id:
            try:
                st = self.cluster.status(self._job_id)
                state = st.state
            except Exception:
                pass
        progress = self.parser.tail_progress(
            text,
            case_name=self.case_name,
            case_dir_local=self.case_dir_local,
            case_dir_remote=self.remote_info0,
            job_id=self._job_id,
            state=state,
        )
        # 累加 history(按 step dedup)
        if progress.current_step is not None and progress.current_step != self._last_step:
            for col in [
                "current_cfl_global", "current_cfl_local",
                "current_rhs_avg", "current_rhs_max",
                "current_time", "current_eigenvalue",
            ]:
                v = getattr(progress, col, None)
                if v is not None:
                    self._history.setdefault(col, []).append(
                        (progress.current_step, v)
                    )
            self._last_step = progress.current_step
        return progress

    def history(self, col_attr: str) -> List[tuple]:
        """返回 ``[(step, value), ...]`` 列表(按 step 升序)。"""
        return list(self._history.get(col_attr, []))


# ===========================================================================
# SweepMonitor
# ===========================================================================

class SweepMonitor:
    """聚合所有 case 的 monitor,提供 watch loop。"""

    def __init__(
        self,
        sweep_report_path: Union[str, Path, Dict[str, Any]],
        cluster: ClusterClient,
        *,
        info_meta_path: Optional[str] = None,
    ):
        if isinstance(sweep_report_path, dict):
            self.manifest = sweep_report_path
        else:
            self.manifest = json.loads(Path(sweep_report_path).read_text())
        self.cluster = cluster
        self.config = cluster.config
        self.info_meta_path = info_meta_path
        self._job_id_map: Dict[str, str] = {}
        for sub in self.manifest.get("pbs_submissions", []):
            case_dir = sub.get("case_dir", "")
            job_id = sub.get("job_id", "")
            if case_dir and job_id:
                self._job_id_map[case_dir] = job_id

    def _make_case_monitors(self) -> List[CaseMonitor]:
        monitors: List[CaseMonitor] = []
        for case in self.manifest.get("cases", []):
            case_name = case.get("case_id") or Path(case.get("path", "")).name
            case_dir = case.get("path", "")
            m = CaseMonitor(
                case_name, self.cluster, self.config,
                info_meta_path=self.info_meta_path,
            )
            m.case_dir_local = case_dir
            m.set_job_id(self._job_id_map.get(case_dir))
            monitors.append(m)
        return monitors

    def refresh_all(self) -> List[CaseProgress]:
        progresses: List[CaseProgress] = []
        for m in self._make_case_monitors():
            try:
                p = m.refresh()
                progresses.append(p)
            except Exception as e:
                progresses.append(CaseProgress(
                    case_name=m.case_name,
                    case_dir_local=m.case_dir_local,
                    case_dir_remote=m.remote_info0,
                    state="Error",
                    parse_warnings=[str(e)],
                ))
        return progresses

    def summary_table(self, progresses: Optional[List[CaseProgress]] = None) -> str:
        if progresses is None:
            progresses = self.refresh_all()
        return format_progress_table(progresses)

    def watch(
        self,
        interval: int = 30,
        *,
        once: bool = False,
        callback: Optional[Callable[[List[CaseProgress]], None]] = None,
    ) -> None:
        try:
            while True:
                progresses = self.refresh_all()
                if callback is not None:
                    callback(progresses)
                if once:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


# ===========================================================================
# 终端表格
# ===========================================================================

def format_progress_table(progresses: Sequence[CaseProgress]) -> str:
    """渲染对齐的终端表格。"""
    if not progresses:
        return "(无 case)"
    headers = ["case", "state", "step", "CFL_global", "RHS_avg", "RHS_max", "last_update"]
    rows: List[List[str]] = []
    for p in progresses:
        rows.append([
            p.case_name,
            p.state,
            str(p.current_step) if p.current_step is not None else "-",
            f"{p.current_cfl_global:.3g}" if p.current_cfl_global is not None else "-",
            f"{p.current_rhs_avg:.3g}" if p.current_rhs_avg is not None else "-",
            f"{p.current_rhs_max:.3g}" if p.current_rhs_max is not None else "-",
            p.last_update.strftime("%H:%M:%S"),
        ])
    widths = [max(len(h), max(len(r[i]) for r in rows)) for i, h in enumerate(headers)]
    lines = ["  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append("  ".join("-" * w for w in widths))
    for r in rows:
        lines.append("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)
