"""集群配置 + 调度器适配 + SSH 客户端(v0.14.0 / Phase 1)

零运行时依赖(纯 stdlib: dataclasses / enum / json / subprocess / pathlib / re)。

设计要点:
- ``SchedulerType`` + ``TorqueAdapter``/``SlurmAdapter``: 双调度器适配,
  解析各调度器特定命令的输出(``qsub``/``qstat -f`` vs ``sbatch``/``squeue``)
- ``ClusterConfig``: 全量配置 dataclass,支持 ``to_dict``/``from_dict``/``save``/``load``
  持久化到 ``~/.inp_tool/cluster.json``
- ``SshClusterClient``: 真实 SSH 客户端,subprocess 调 ssh/rsync/qsub/qstat
- ``LocalDryRunClient``: 干跑模式,不真提交,只记录命令(单元测试 + ``--dry-run``)
- ``probe_scheduler()``: 远端自动探测 qstat vs sinfo,识别调度器类型
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


# ===========================================================================
# 调度器类型 + 适配器
# ===========================================================================

class SchedulerType(str, Enum):
    """支持的 PBS 调度器类型。"""
    TORQUE = "torque"      # 开源 PBS(Torque) - 10.10.10.251 默认
    SLURM = "slurm"        # Slurm - 备
    PBSPRO = "pbspro"      # PBS Pro - 留接口


@dataclass
class PbsJobStatus:
    """PBS 作业状态(双调度器统一)。"""
    job_id: str
    name: str
    user: str
    state: str                       # Q|R|E|H|C|... (Torque) / R|PD|CG|... (Slurm)
    queue: str
    ncpus: Optional[int] = None
    walltime_req: Optional[str] = None    # HH:MM:SS
    walltime_used: Optional[str] = None
    submit_time: Optional[str] = None
    start_time: Optional[str] = None
    exec_host: Optional[str] = None
    exit_status: Optional[int] = None
    raw: Dict[str, str] = field(default_factory=dict)


@dataclass
class ClusterInfo:
    """集群探测结果。"""
    host: str
    scheduler: SchedulerType
    user: str
    queues: List[str] = field(default_factory=list)
    pbs_version: str = ""
    latency_ms: int = 0


# ---------------------------------------------------------------------------
# TorqueAdapter
# ---------------------------------------------------------------------------

class TorqueAdapter:
    """Torque 调度器命令构造 + 输出解析。"""

    submit_cmd = "qsub"
    cancel_cmd = "qdel"
    list_cmd = "qstat"
    status_cmd = "qstat -f {job_id}"
    list_user_cmd = "qstat -u {user}"

    @staticmethod
    def parse_submit_stdout(stdout: str) -> str:
        """qsub 输出: '<job_id>.<server>' → 抽 job_id。"""
        s = stdout.strip()
        if not s:
            raise ValueError("qsub returned empty stdout (submit failed?)")
        first = s.splitlines()[0].strip()
        if "." not in first:
            raise ValueError(f"qsub output unexpected (no '.' separator): {first!r}")
        job_id = first.split(".", 1)[0]
        if not job_id.isdigit():
            raise ValueError(f"qsub output job_id is not numeric: {job_id!r}")
        return job_id

    @staticmethod
    def parse_qstat_f(text: str) -> List[PbsJobStatus]:
        """解析 ``qstat -f <job_id>`` 输出。

        格式示例::

            Job Id: 1234.head01
                Job_Name = myjob
                Job_Owner = root@head01
                job_state = R
                queue = q02
                Resource_List.ncpus = 48
                Resource_List.walltime = 04:00:00
                resources_used.walltime = 01:23:45
                submit_time = Fri Jun 13 10:00:00 2026
                start_time = Fri Jun 13 10:01:00 2026
                exec_host = node1/0*48
                exit_status = 0
        """
        if not text or "Job Id:" not in text:
            return []
        chunks = re.split(r"(?m)^Job Id:\s*", text)
        results: List[PbsJobStatus] = []
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            first_line = chunk.splitlines()[0].strip()
            job_id_full = first_line.split()[0] if first_line else ""
            if "." in job_id_full:
                job_id = job_id_full.split(".", 1)[0]
            else:
                job_id = job_id_full
            if not job_id:
                continue
            attrs: Dict[str, str] = {}
            for line in chunk.splitlines()[1:]:
                m = re.match(r"\s*([A-Za-z0-9_.]+)\s*=\s*(.*)", line)
                if m:
                    key, val = m.group(1), m.group(2).strip()
                    attrs[key] = val
            name = attrs.get("Job_Name", "")
            owner = attrs.get("Job_Owner", "")
            user = owner.split("@")[0] if "@" in owner else owner
            state = attrs.get("job_state", "Unknown")
            queue = attrs.get("queue", "")
            ncpus_s = attrs.get("Resource_List.ncpus", "")
            ncpus = int(ncpus_s) if ncpus_s.isdigit() else None
            walltime_req = attrs.get("Resource_List.walltime")
            walltime_used = attrs.get("resources_used.walltime")
            submit_time = attrs.get("submit_time")
            start_time = attrs.get("start_time")
            exec_host = attrs.get("exec_host")
            exit_s = attrs.get("exit_status", "")
            exit_status = int(exit_s) if exit_s.lstrip("-").isdigit() else None
            results.append(PbsJobStatus(
                job_id=job_id,
                name=name,
                user=user,
                state=state,
                queue=queue,
                ncpus=ncpus,
                walltime_req=walltime_req,
                walltime_used=walltime_used,
                submit_time=submit_time,
                start_time=start_time,
                exec_host=exec_host,
                exit_status=exit_status,
                raw=attrs,
            ))
        return results

    @staticmethod
    def parse_qstat_user(text: str, user: str) -> int:
        """从 ``qstat -u <user>`` 输出计数 user 的 job 数。

        输出格式(简化)::

            Job id           Name             User            Time Use S Queue
            ---------------- ---------------- ---------------- -------- - ----
            1234.head01      myjob            root            01:23:45 R q02
        """
        if not text:
            return 0
        count = 0
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("Job id") or line.startswith("---"):
                continue
            parts = line.split()
            if len(parts) >= 3 and parts[2] == user:
                count += 1
        return count


# ---------------------------------------------------------------------------
# SlurmAdapter
# ---------------------------------------------------------------------------

class SlurmAdapter:
    """Slurm 调度器命令构造 + 输出解析。"""

    submit_cmd = "sbatch"
    cancel_cmd = "scancel"
    list_cmd = "squeue"
    status_cmd = "squeue -j {job_id}"
    list_user_cmd = "squeue -u {user}"

    @staticmethod
    def parse_submit_stdout(stdout: str) -> str:
        """sbatch 输出: 'Submitted batch job <job_id>' → 抽 job_id。"""
        s = stdout.strip()
        if not s:
            raise ValueError("sbatch returned empty stdout (submit failed?)")
        m = re.search(r"Submitted batch job\s+(\d+)", s)
        if not m:
            raise ValueError(f"sbatch output unexpected: {s!r}")
        return m.group(1)

    @staticmethod
    def parse_squeue(text: str) -> List[PbsJobStatus]:
        """解析 ``squeue`` 默认输出::

            JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
            1234      q02     myjob    root  R       1:23     1  node1
            5678      q01   second    root PD       0:00     1  (Resources)
        """
        if not text:
            return []
        results: List[PbsJobStatus] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("JOBID") or line.startswith("---"):
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            job_id = parts[0]
            queue = parts[1]
            name = parts[2]
            user = parts[3]
            state = parts[4]
            results.append(PbsJobStatus(
                job_id=job_id,
                name=name,
                user=user,
                state=state,
                queue=queue,
                ncpus=None,
                walltime_used=parts[5] if len(parts) > 5 else None,
                raw={"raw_line": line},
            ))
        return results


# ---------------------------------------------------------------------------
# probe_scheduler - 远端自动探测
# ---------------------------------------------------------------------------

def probe_scheduler(
    ssh_target: str,
    *,
    ssh_key: Optional[str] = None,
    timeout: int = 10,
) -> SchedulerType:
    """ssh 远端探测调度器类型:先试 qstat,失败再试 sinfo。"""
    ssh_cmd: List[str] = ["ssh"]
    if ssh_key:
        ssh_cmd += ["-i", ssh_key]
    ssh_cmd += [
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        ssh_target,
    ]

    # 试 qstat
    try:
        r = subprocess.run(
            ssh_cmd + ["qstat", "--version"],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode == 0:
            return SchedulerType.TORQUE
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # 试 sinfo
    try:
        r = subprocess.run(
            ssh_cmd + ["sinfo", "--version"],
            capture_output=True, text=True, timeout=timeout,
        )
        if r.returncode == 0:
            return SchedulerType.SLURM
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    raise RuntimeError(
        f"无法识别 {ssh_target} 上的调度器(scheduler): "
        f"qstat / sinfo 都失败"
    )


# ===========================================================================
# ClusterConfig — 集群配置 dataclass + 持久化
# ===========================================================================

@dataclass
class ClusterConfig:
    """集群配置全量 dataclass。

    默认值反映 10.10.10.251 集群(v0.14.0)。可全部覆盖。
    """

    # —— 连接 ——
    host: str = "10.10.10.251"
    user: str = "root"
    port: int = 22
    auth_method: str = "ssh-key"            # ssh-key | password | proxycommand
    ssh_key: Optional[str] = None
    ssh_key_passphrase: Optional[str] = None
    password: Optional[str] = None
    proxycommand: Optional[str] = None

    # —— 调度器 ——
    scheduler: str = "auto"                 # auto-detect on probe
    detected_scheduler: Optional[str] = None

    # —— 队列与限流 ——
    available_queues: List[str] = field(default_factory=lambda: ["q01", "q02"])
    default_queue: str = "q02"
    max_concurrent_jobs: int = 20

    # —— 资源默认值 ——
    default_walltime: str = "04:00:00"
    default_nodes: int = 1
    default_ppn: int = 48

    # —— 路径 ——
    remote_workdir: str = "/root/cases"

    # —— 监控文件格式 ——
    info_file: str = "mcfd.info0"
    info_meta_file: str = "minfo0.mpf1d"
    info_n_columns: int = 8

    # —— 列映射(从 minfo0.mpf1d 动态读,失败 fallback)——
    col_step: int = 0
    col_time: int = 1
    col_dt: int = 2
    col_rhs_avg: int = 3
    col_rhs_max: int = 4
    col_cfl_global: int = 5
    col_cfl_local: int = 6
    col_eigenvalue: int = 7

    # ----- 序列化 -----

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClusterConfig":
        valid_keys = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})

    # ----- 持久化 -----

    @staticmethod
    def _config_path() -> Path:
        home = Path(os.path.expanduser("~"))
        if os.name == "nt":
            home = Path(os.environ.get("USERPROFILE", str(home)))
        return home / ".inp_tool" / "cluster.json"

    def save(self) -> Path:
        """写到 ~/.inp_tool/cluster.json,目录不存在自动创建。"""
        p = self._config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        return p

    @classmethod
    def load(cls) -> "ClusterConfig":
        """从 ~/.inp_tool/cluster.json 读,失败 fallback 默认。"""
        p = cls._config_path()
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text())
            if not isinstance(data, dict):
                return cls()
            return cls.from_dict(data)
        except (json.JSONDecodeError, OSError, TypeError):
            return cls()


# ===========================================================================
# ClusterClient — 客户端基类
# ===========================================================================

class ClusterClient:
    """集群客户端基类。

    具体实现: :class:`SshClusterClient` / :class:`LocalDryRunClient`。
    """
    config: ClusterConfig

    def __init__(self, config: ClusterConfig):
        self.config = config

    def probe(self) -> ClusterInfo:
        raise NotImplementedError

    def submit(self, script_text: str, *, remote_dir: str,
               pbs_overrides: Optional[Dict[str, str]] = None) -> str:
        raise NotImplementedError

    def status(self, job_id: str) -> PbsJobStatus:
        raise NotImplementedError

    def status_many(self, job_ids: Sequence[str]) -> List[PbsJobStatus]:
        raise NotImplementedError

    def cancel(self, job_id: str, *, force: bool = False) -> bool:
        raise NotImplementedError

    def list_user_jobs(self, user: str) -> List[PbsJobStatus]:
        raise NotImplementedError

    def tail(self, remote_path: str, n: int = 50) -> str:
        raise NotImplementedError

    def rsync_to(self, local_dir: str, remote_dir: str,
                 *, exclude: Sequence[str] = ()) -> None:
        raise NotImplementedError

    def rsync_from(self, remote_path: str, local_path: str) -> None:
        raise NotImplementedError

    def check_concurrency(self, user: str) -> int:
        raise NotImplementedError


# ===========================================================================
# SshClusterClient — 真实 SSH 客户端
# ===========================================================================

class SshClusterClient(ClusterClient):
    """通过 SSH 调远端 qsub/qstat/rsync/tail。"""

    def _base_ssh_cmd(self) -> List[str]:
        """构造 ssh 基础命令(认证 + 端口 + 目标)。"""
        c = self.config
        cmd: List[str] = []
        if c.auth_method == "password" and c.password:
            cmd += ["sshpass", "-p", c.password, "ssh"]
        else:
            cmd += ["ssh"]
        if c.ssh_key:
            cmd += ["-i", c.ssh_key]
        if c.proxycommand and c.auth_method == "proxycommand":
            cmd += ["-o", f"ProxyCommand={c.proxycommand}"]
        cmd += [
            "-p", str(c.port),
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            f"{c.user}@{c.host}",
        ]
        return cmd

    def _ssh(self, remote_cmd: str, *, timeout: int = 30) -> str:
        cmd = self._base_ssh_cmd() + [remote_cmd]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout

    def _adapter(self):
        s = self.config.detected_scheduler or self.config.scheduler
        if s == SchedulerType.SLURM.value or s == "slurm":
            return SlurmAdapter
        return TorqueAdapter

    # ----- ClusterClient API -----

    def probe(self) -> ClusterInfo:
        s = probe_scheduler(
            f"{self.config.user}@{self.config.host}",
            ssh_key=self.config.ssh_key,
        )
        self.config.detected_scheduler = s.value
        return ClusterInfo(
            host=self.config.host,
            scheduler=s,
            user=self.config.user,
            queues=list(self.config.available_queues),
        )

    def submit(self, script_text: str, *, remote_dir: str,
               pbs_overrides: Optional[Dict[str, str]] = None) -> str:
        # 1. ssh + qsub
        script_name = "run.pbs"  # 默认;Phase 2 可配置
        cmd = self._adapter().submit_cmd
        remote_qsub = f"cd {shlex.quote(remote_dir)} && {cmd} {shlex.quote(script_name)}"
        full = self._base_ssh_cmd() + [remote_qsub]
        r = subprocess.run(full, capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise RuntimeError(
                f"{cmd} failed: rc={r.returncode} stderr={r.stderr.strip()!r}"
            )
        return self._adapter().parse_submit_stdout(r.stdout)

    def status(self, job_id: str) -> PbsJobStatus:
        cmd = self._adapter().status_cmd.format(job_id=shlex.quote(job_id))
        out = self._ssh(cmd)
        if not out.strip():
            return PbsJobStatus(
                job_id=job_id, name="", user=self.config.user,
                state="Unknown", queue="",
            )
        if self._adapter() is TorqueAdapter:
            statuses = TorqueAdapter.parse_qstat_f(out)
        else:
            statuses = SlurmAdapter.parse_squeue(out)
        if not statuses:
            return PbsJobStatus(
                job_id=job_id, name="", user=self.config.user,
                state="Unknown", queue="",
            )
        return statuses[0]

    def status_many(self, job_ids: Sequence[str]) -> List[PbsJobStatus]:
        return [self.status(jid) for jid in job_ids]

    def cancel(self, job_id: str, *, force: bool = False) -> bool:
        if force and self._adapter() is TorqueAdapter:
            remote_cmd = f"qdel -W 15 {shlex.quote(job_id)}"
        else:
            remote_cmd = f"{self._adapter().cancel_cmd} {shlex.quote(job_id)}"
        full = self._base_ssh_cmd() + [remote_cmd]
        r = subprocess.run(full, capture_output=True, text=True, timeout=30)
        return r.returncode == 0

    def list_user_jobs(self, user: str) -> List[PbsJobStatus]:
        if self._adapter() is TorqueAdapter:
            cmd = self._adapter().list_user_cmd.format(user=shlex.quote(user))
            out = self._ssh(cmd)
            return TorqueAdapter.parse_qstat_f(out)
        cmd = self._adapter().list_user_cmd.format(user=shlex.quote(user))
        out = self._ssh(cmd)
        return SlurmAdapter.parse_squeue(out)

    def tail(self, remote_path: str, n: int = 50) -> str:
        remote_cmd = f"tail -n {n} {shlex.quote(remote_path)}"
        full = self._base_ssh_cmd() + [remote_cmd]
        r = subprocess.run(full, capture_output=True, text=True, timeout=30)
        return r.stdout

    def rsync_to(self, local_dir: str, remote_dir: str, *,
                 exclude: Sequence[str] = ()) -> None:
        excludes: List[str] = []
        for e in exclude:
            excludes += ["--exclude", e]
        cmd = [
            "rsync", "-avz",
            *excludes,
            "-e", " ".join(shlex.quote(x) for x in self._base_ssh_cmd()),
            f"{local_dir}/",
            f"{self.config.user}@{self.config.host}:{remote_dir}/",
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(
                f"rsync_to failed: rc={r.returncode} stderr={r.stderr.strip()!r}"
            )

    def rsync_from(self, remote_path: str, local_path: str) -> None:
        cmd = [
            "rsync", "-avz",
            "-e", " ".join(shlex.quote(x) for x in self._base_ssh_cmd()),
            f"{self.config.user}@{self.config.host}:{remote_path}",
            local_path,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            raise RuntimeError(
                f"rsync_from failed: rc={r.returncode} stderr={r.stderr.strip()!r}"
            )

    def check_concurrency(self, user: str) -> int:
        if self._adapter() is TorqueAdapter:
            cmd = self._adapter().list_user_cmd.format(user=shlex.quote(user))
            out = self._ssh(cmd)
            return TorqueAdapter.parse_qstat_user(out, user)
        cmd = self._adapter().list_user_cmd.format(user=shlex.quote(user))
        out = self._ssh(cmd)
        statuses = SlurmAdapter.parse_squeue(out)
        return sum(1 for s in statuses if s.user == user)


# ===========================================================================
# LocalDryRunClient — 干跑模式,不真提交
# ===========================================================================

class LocalDryRunClient(ClusterClient):
    """不真提交,只记录命令(单元测试 + CLI --dry-run 用)。"""

    def __init__(self, config: ClusterConfig):
        super().__init__(config)
        self.commands: List[List[str]] = []    # 记录所有"应该执行"的命令

    def _record(self, cmd: Sequence[str]) -> None:
        self.commands.append(list(cmd))

    def _adapter(self):
        s = self.config.detected_scheduler or self.config.scheduler
        if s == SchedulerType.SLURM.value or s == "slurm":
            return SlurmAdapter
        return TorqueAdapter

    def probe(self) -> ClusterInfo:
        self.config.detected_scheduler = SchedulerType.TORQUE.value
        return ClusterInfo(
            host=self.config.host,
            scheduler=SchedulerType.TORQUE,
            user=self.config.user,
            queues=list(self.config.available_queues),
        )

    def submit(self, script_text: str, *, remote_dir: str,
               pbs_overrides: Optional[Dict[str, str]] = None) -> str:
        cmd = self._adapter().submit_cmd
        self._record([cmd, remote_dir, script_text[:30] + "..."])
        return f"DRYRUN-{len(self.commands):04d}"

    def status(self, job_id: str) -> PbsJobStatus:
        self._record(["status", job_id])
        return PbsJobStatus(
            job_id=job_id, name="dryrun", user=self.config.user,
            state="Q", queue=self.config.default_queue,
        )

    def status_many(self, job_ids: Sequence[str]) -> List[PbsJobStatus]:
        return [self.status(jid) for jid in job_ids]

    def cancel(self, job_id: str, *, force: bool = False) -> bool:
        self._record(["cancel", job_id, str(force)])
        return True

    def list_user_jobs(self, user: str) -> List[PbsJobStatus]:
        self._record(["list_user_jobs", user])
        return []

    def tail(self, remote_path: str, n: int = 50) -> str:
        self._record(["tail", remote_path, str(n)])
        return f"DRYRUN tail of {remote_path}\n"

    def rsync_to(self, local_dir: str, remote_dir: str, *,
                 exclude: Sequence[str] = ()) -> None:
        self._record(["rsync_to", local_dir, remote_dir, *exclude])

    def rsync_from(self, remote_path: str, local_path: str) -> None:
        self._record(["rsync_from", remote_path, local_path])

    def check_concurrency(self, user: str) -> int:
        self._record(["check_concurrency", user])
        return 0
