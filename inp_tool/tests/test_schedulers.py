"""调度器适配器单测(v0.14.0 / Phase 1)

覆盖:
- Torque qsub/qstat 输出解析
- Slurm sbatch/squeue 输出解析
- SchedulerAdapter 协议基本接口
- 调度器自动探测(probe)
"""
from __future__ import annotations

import pytest

from inp_tool.cluster import (
    SchedulerType,
    TorqueAdapter,
    SlurmAdapter,
    probe_scheduler,
    PbsJobStatus,
)


# ---------------------------------------------------------------------------
# TorqueAdapter.parse_submit_stdout
# ---------------------------------------------------------------------------

class TestTorqueParseSubmitStdout:
    """qsub 输出格式: '<job_id>.<server>' (e.g. '1234.head01')"""

    def test_extracts_job_id_from_dot_separated(self):
        out = "1234.head01"
        assert TorqueAdapter.parse_submit_stdout(out) == "1234"

    def test_extracts_job_id_with_long_server_name(self):
        out = "99999.suanli-mgmt"
        assert TorqueAdapter.parse_submit_stdout(out) == "99999"

    def test_empty_stdout_raises(self):
        with pytest.raises(ValueError, match="qsub"):
            TorqueAdapter.parse_submit_stdout("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="qsub"):
            TorqueAdapter.parse_submit_stdout("   \n  ")

    def test_no_dot_raises(self):
        with pytest.raises(ValueError, match="qsub"):
            TorqueAdapter.parse_submit_stdout("1234")


# ---------------------------------------------------------------------------
# SlurmAdapter.parse_submit_stdout
# ---------------------------------------------------------------------------

class TestSlurmParseSubmitStdout:
    """sbatch 输出格式: 'Submitted batch job <job_id>'"""

    def test_extracts_job_id(self):
        out = "Submitted batch job 1234"
        assert SlurmAdapter.parse_submit_stdout(out) == "1234"

    def test_with_trailing_whitespace(self):
        out = "Submitted batch job 9999\n"
        assert SlurmAdapter.parse_submit_stdout(out) == "9999"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="sbatch"):
            SlurmAdapter.parse_submit_stdout("")

    def test_no_match_raises(self):
        with pytest.raises(ValueError, match="sbatch"):
            SlurmAdapter.parse_submit_stdout("ERROR: invalid partition")


# ---------------------------------------------------------------------------
# TorqueAdapter.parse_qstat_f
# ---------------------------------------------------------------------------

# 真实 qstat -f <job_id> 输出样例(简化)
SAMPLE_QSTAT_F = """Job Id: 1234.head01
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


class TestTorqueParseQstatF:
    def test_parses_running_job(self):
        statuses = TorqueAdapter.parse_qstat_f(SAMPLE_QSTAT_F)
        assert len(statuses) == 1
        s = statuses[0]
        assert s.job_id == "1234"
        assert s.name == "myjob"
        assert s.user == "root"
        assert s.state == "R"
        assert s.queue == "q02"
        assert s.ncpus == 48
        assert s.walltime_req == "04:00:00"
        assert s.walltime_used == "01:23:45"
        assert s.exec_host == "node1/0*48"
        assert s.exit_status == 0

    def test_empty_input_returns_empty_list(self):
        assert TorqueAdapter.parse_qstat_f("") == []

    def test_garbage_input_returns_empty_list(self):
        """乱码输入不抛,返回空 list (而不是 raise)"""
        assert TorqueAdapter.parse_qstat_f("not a job listing\n") == []

    def test_multiple_jobs(self):
        text = SAMPLE_QSTAT_F + "\n" + SAMPLE_QSTAT_F.replace("1234", "5678").replace("myjob", "second")
        statuses = TorqueAdapter.parse_qstat_f(text)
        assert len(statuses) == 2
        assert {s.job_id for s in statuses} == {"1234", "5678"}


# ---------------------------------------------------------------------------
# SlurmAdapter.parse_squeue
# ---------------------------------------------------------------------------

SAMPLE_SQUEUE = """JOBID PARTITION     NAME     USER ST       TIME  NODES NODELIST(REASON)
1234      q02     myjob    root  R       1:23     1  node1
5678      q01   second    root PD       0:00     1  (Resources)
"""


class TestSlurmParseSqueue:
    def test_parses_running_job(self):
        statuses = SlurmAdapter.parse_squeue(SAMPLE_SQUEUE)
        assert len(statuses) == 2
        s = statuses[0]
        assert s.job_id == "1234"
        assert s.name == "myjob"
        assert s.user == "root"
        assert s.state == "R"
        assert s.queue == "q02"

    def test_parses_pending_job(self):
        statuses = SlurmAdapter.parse_squeue(SAMPLE_SQUEUE)
        pending = [s for s in statuses if s.job_id == "5678"][0]
        assert pending.state == "PD"
        assert pending.queue == "q01"

    def test_empty_returns_empty_list(self):
        assert SlurmAdapter.parse_squeue("") == []
        assert SlurmAdapter.parse_squeue("JOBID PARTITION NAME USER ST TIME NODES NODELIST(REASON)\n") == []


# ---------------------------------------------------------------------------
# SchedulerType / probe_scheduler
# ---------------------------------------------------------------------------

class TestSchedulerType:
    def test_string_values(self):
        assert SchedulerType.TORQUE.value == "torque"
        assert SchedulerType.SLURM.value == "slurm"
        assert SchedulerType.PBSPRO.value == "pbspro"

    def test_from_string(self):
        assert SchedulerType("torque") is SchedulerType.TORQUE
        assert SchedulerType("slurm") is SchedulerType.SLURM


class TestProbeScheduler:
    """probe_scheduler 应探测远端是什么调度器(monkeypatch subprocess)"""

    def test_torque_when_qstat_version_works(self, monkeypatch):
        from subprocess import CompletedProcess
        def fake_run(cmd, **kwargs):
            # qstat --version 成功
            if "qstat" in cmd:
                return CompletedProcess(cmd, 0, stdout="version: PBSPro_20.0.1\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        assert probe_scheduler("user@host", ssh_key=None) == SchedulerType.TORQUE

    def test_slurm_when_qstat_fails_sinfo_works(self, monkeypatch):
        from subprocess import CompletedProcess
        def fake_run(cmd, **kwargs):
            if "qstat" in cmd:
                return CompletedProcess(cmd, 1, stdout="", stderr="command not found")
            if "sinfo" in cmd:
                return CompletedProcess(cmd, 0, stdout="PARTITION AVAIL  TIMELIMIT  NODES  STATE NODELIST\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        assert probe_scheduler("user@host", ssh_key=None) == SchedulerType.SLURM

    def test_unknown_raises_when_both_fail(self, monkeypatch):
        from subprocess import CompletedProcess
        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 127, stdout="", stderr="command not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        with pytest.raises(RuntimeError, match="scheduler"):
            probe_scheduler("user@host", ssh_key=None)


# ---------------------------------------------------------------------------
# PbsJobStatus dataclass
# ---------------------------------------------------------------------------

class TestPbsJobStatus:
    def test_required_fields(self):
        s = PbsJobStatus(
            job_id="1234",
            name="myjob",
            user="root",
            state="R",
            queue="q02",
        )
        assert s.job_id == "1234"
        assert s.name == "myjob"
        assert s.ncpus is None  # 可选
        assert s.exit_status is None  # 可选

    def test_all_fields(self):
        s = PbsJobStatus(
            job_id="1234",
            name="myjob",
            user="root",
            state="R",
            queue="q02",
            ncpus=48,
            walltime_req="04:00:00",
            walltime_used="01:00:00",
            submit_time="2026-06-13 10:00:00",
            start_time="2026-06-13 10:01:00",
            exec_host="node1/0*48",
            exit_status=0,
            raw={"some": "field"},
        )
        assert s.ncpus == 48
        assert s.exec_host == "node1/0*48"
        assert s.raw == {"some": "field"}
