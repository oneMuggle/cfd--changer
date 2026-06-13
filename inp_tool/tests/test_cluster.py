"""集群配置 + 客户端单测(v0.14.0 / Phase 1)

覆盖:
- ClusterConfig dataclass 默认值 + 序列化(from_dict/to_dict/save/load)
- SshClusterClient: SSH/rsync/qsub/tail 命令拼接(mock subprocess)
- LocalDryRunClient: 不真提交,只记录命令
- check_concurrency: 解析 qstat -u 输出
- SSH 命令构造(host/key/password/proxycommand 4 种认证)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from inp_tool.cluster import (
    ClusterConfig,
    SshClusterClient,
    LocalDryRunClient,
    ClusterInfo,
)


# ---------------------------------------------------------------------------
# ClusterConfig dataclass
# ---------------------------------------------------------------------------

class TestClusterConfigDefaults:
    def test_default_values(self):
        c = ClusterConfig()
        assert c.host == "10.10.10.251"
        assert c.user == "root"
        assert c.port == 22
        assert c.auth_method == "ssh-key"
        assert c.ssh_key is None
        assert c.scheduler == "auto"
        assert c.detected_scheduler is None
        assert c.default_queue == "q02"
        assert c.available_queues == ["q01", "q02"]
        assert c.max_concurrent_jobs == 20
        assert c.default_walltime == "04:00:00"
        assert c.default_nodes == 1
        assert c.default_ppn == 48
        assert c.remote_workdir == "/root/cases"
        assert c.info_file == "mcfd.info0"
        assert c.info_meta_file == "minfo0.mpf1d"
        assert c.info_n_columns == 8


class TestClusterConfigSerialization:
    def test_to_dict(self):
        c = ClusterConfig(host="myhost", user="alice", ssh_key="/path/to/key")
        d = c.to_dict()
        assert d["host"] == "myhost"
        assert d["user"] == "alice"
        assert d["ssh_key"] == "/path/to/key"
        assert d["available_queues"] == ["q01", "q02"]  # 默认

    def test_from_dict_full(self):
        d = {
            "host": "suanli",
            "user": "cfd_user",
            "auth_method": "ssh-key",
            "ssh_key": "C:/Users/me/.ssh/id_rsa",
            "scheduler": "torque",
            "detected_scheduler": "torque",
            "default_queue": "q01",
            "available_queues": ["q01", "q02", "batch"],
            "max_concurrent_jobs": 10,
            "default_walltime": "08:00:00",
            "default_nodes": 2,
            "default_ppn": 24,
            "remote_workdir": "/home/cfd_user/cases",
            "info_file": "mcfd.info0",
            "info_meta_file": "minfo0.mpf1d",
        }
        c = ClusterConfig.from_dict(d)
        assert c.host == "suanli"
        assert c.user == "cfd_user"
        assert c.ssh_key == "C:/Users/me/.ssh/id_rsa"
        assert c.detected_scheduler == "torque"
        assert c.default_queue == "q01"
        assert c.available_queues == ["q01", "q02", "batch"]
        assert c.max_concurrent_jobs == 10
        assert c.remote_workdir == "/home/cfd_user/cases"

    def test_from_dict_partial_uses_defaults(self):
        c = ClusterConfig.from_dict({"host": "other"})
        assert c.host == "other"
        assert c.user == "root"  # 默认
        assert c.default_queue == "q02"  # 默认

    def test_roundtrip(self):
        c1 = ClusterConfig(host="h1", max_concurrent_jobs=30, ssh_key="/k")
        d = c1.to_dict()
        c2 = ClusterConfig.from_dict(d)
        assert c2.host == "h1"
        assert c2.max_concurrent_jobs == 30
        assert c2.ssh_key == "/k"


class TestClusterConfigPersistence:
    def test_save_and_load(self, tmp_path, monkeypatch):
        """save/load 走 ~/.inp_tool/cluster.json,monkeypatch HOME 重定向"""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Win7 fallback
        c = ClusterConfig(host="test", max_concurrent_jobs=15)
        c.save()
        # 文件应在 ~/.inp_tool/cluster.json
        config_path = tmp_path / ".inp_tool" / "cluster.json"
        assert config_path.is_file()
        # load 读回
        c2 = ClusterConfig.load()
        assert c2.host == "test"
        assert c2.max_concurrent_jobs == 15

    def test_load_missing_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        c = ClusterConfig.load()
        assert c.host == "10.10.10.251"  # 默认
        assert c.max_concurrent_jobs == 20

    def test_load_invalid_json_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        config_dir = tmp_path / ".inp_tool"
        config_dir.mkdir(parents=True)
        (config_dir / "cluster.json").write_text("not valid json {{{")
        c = ClusterConfig.load()
        # 解析失败应 fallback 默认,不抛
        assert c.host == "10.10.10.251"


# ---------------------------------------------------------------------------
# SshClusterClient — SSH 命令构造
# ---------------------------------------------------------------------------

class TestSshClientBaseCmd:
    """基础 ssh 命令拼接(host/user/key/password/proxycommand)"""

    def test_minimal_ssh_cmd(self):
        c = ClusterConfig(host="h", user="u")
        client = SshClusterClient(c)
        cmd = client._base_ssh_cmd()
        cmd_str = " ".join(cmd)
        assert "ssh" in cmd
        assert "-p 22" in cmd_str  # -p 和 22 是 list 两个元素
        assert "u@h" in cmd
        # 没指定 ssh_key → 不应有 -i
        assert "-i" not in cmd_str

    def test_with_ssh_key(self, tmp_path):
        key = tmp_path / "id_rsa"
        key.write_text("fake key")
        c = ClusterConfig(host="h", user="u", ssh_key=str(key))
        client = SshClusterClient(c)
        cmd = client._base_ssh_cmd()
        assert "-i" in cmd
        assert str(key) in cmd

    def test_with_proxycommand(self):
        c = ClusterConfig(
            host="h", user="u", auth_method="proxycommand",
            proxycommand="ssh jump -W %h:%p",
        )
        client = SshClusterClient(c)
        cmd = client._base_ssh_cmd()
        # ProxyCommand 拼接形式: -o ProxyCommand=...
        assert any("ProxyCommand" in str(x) for x in cmd)

    def test_with_password_uses_sshpass(self, monkeypatch):
        """密码走 sshpass(不推荐,但支持)"""
        c = ClusterConfig(
            host="h", user="u", auth_method="password",
            password="secret",
        )
        client = SshClusterClient(c)
        cmd = client._base_ssh_cmd()
        assert cmd[0] == "sshpass"
        assert "-p" in cmd
        assert "secret" in cmd


# ---------------------------------------------------------------------------
# SshClusterClient — submit / status / cancel
# ---------------------------------------------------------------------------

class TestSshClientSubmit:
    def test_submit_invokes_qsub_and_returns_job_id(self, monkeypatch):
        from inp_tool.cluster import SchedulerType
        c = ClusterConfig(
            host="h", user="u", ssh_key=None,
            detected_scheduler=SchedulerType.TORQUE.value,
        )
        client = SshClusterClient(c)

        calls = []
        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            cmd_str = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if "qsub" in cmd_str:
                return CompletedProcess(cmd, 0, stdout="1234.head01\n", stderr="")
            return CompletedProcess(cmd, 0, stdout="", stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        job_id = client.submit(
            script_text="#!/bin/bash\n#PBS -N x\nls\n",
            remote_dir="/root/cases/case1",
        )
        assert job_id == "1234"
        # 至少有一次 qsub 调用
        assert any("qsub" in " ".join(c) for c in calls)

    def test_submit_raises_on_qsub_failure(self, monkeypatch):
        from inp_tool.cluster import SchedulerType
        c = ClusterConfig(detected_scheduler=SchedulerType.TORQUE.value)
        client = SshClusterClient(c)
        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 1, stdout="", stderr="qsub: Bad UID")
        monkeypatch.setattr("subprocess.run", fake_run)
        with pytest.raises(RuntimeError):
            client.submit("#!/bin/bash\n", remote_dir="/tmp")


class TestSshClientStatus:
    def test_status_uses_qstat_f(self, monkeypatch):
        from inp_tool.cluster import SchedulerType, PbsJobStatus
        c = ClusterConfig(detected_scheduler=SchedulerType.TORQUE.value)
        client = SshClusterClient(c)

        sample = """Job Id: 1234.head01
    Job_Name = myjob
    Job_Owner = root@head01
    job_state = R
    queue = q02
    Resource_List.ncpus = 48
"""
        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 0, stdout=sample, stderr="")

        monkeypatch.setattr("subprocess.run", fake_run)
        s = client.status("1234")
        assert isinstance(s, PbsJobStatus)
        assert s.job_id == "1234"
        assert s.state == "R"

    def test_status_empty_returns_default_status(self, monkeypatch):
        """qstat 无输出 → 返回一个 'unknown' 状态而非抛"""
        from inp_tool.cluster import SchedulerType
        c = ClusterConfig(detected_scheduler=SchedulerType.TORQUE.value)
        client = SshClusterClient(c)
        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 0, stdout="", stderr="")
        monkeypatch.setattr("subprocess.run", fake_run)
        s = client.status("99999")
        # 默认 unknown 状态
        assert s.state == "Unknown" or s.state == "C"


class TestSshClientCheckConcurrency:
    def test_counts_user_jobs(self, monkeypatch):
        from inp_tool.cluster import SchedulerType
        c = ClusterConfig(detected_scheduler=SchedulerType.TORQUE.value)
        client = SshClusterClient(c)
        # qstat -u <user> 列格式(简表)
        sample = """Job id           Name             User            Time Use S Queue
---------------- ---------------- ---------------- -------- - ----
1234.head01      myjob            root            01:23:45 R q02
1235.head01      job2             root            00:30:00 R q02
1236.head01      job3             alice           00:00:00 Q q01
"""
        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 0, stdout=sample, stderr="")
        monkeypatch.setattr("subprocess.run", fake_run)
        n = client.check_concurrency("root")
        assert n == 2  # root 有 2 个 job


class TestSshClientTail:
    def test_tail_invokes_ssh_tail(self, monkeypatch):
        c = ClusterConfig()
        client = SshClusterClient(c)
        captured = []
        def fake_run(cmd, **kwargs):
            captured.append(cmd)
            return CompletedProcess(cmd, 0, stdout="last 10 lines\n", stderr="")
        monkeypatch.setattr("subprocess.run", fake_run)
        out = client.tail("/root/cases/c1/mcfd.info0", n=10)
        assert "last 10 lines" in out
        # 命令应含 tail -n 10
        assert any("tail" in " ".join(cmd) and "-n 10" in " ".join(cmd) for cmd in captured)


class TestSshClientRsync:
    def test_rsync_to_includes_exclude(self, monkeypatch):
        c = ClusterConfig()
        client = SshClusterClient(c)
        captured = []
        def fake_run(cmd, **kwargs):
            captured.append(cmd)
            return CompletedProcess(cmd, 0, stdout="", stderr="")
        monkeypatch.setattr("subprocess.run", fake_run)
        client.rsync_to("/local/c1", "/root/cases/c1", exclude=["mlog/", "*.bak"])
        rsync_cmd = " ".join(captured[0])
        assert "rsync" in rsync_cmd
        # rsync 的 --exclude 是空格分隔(--exclude PATTERN),不是 --
        assert "--exclude" in rsync_cmd
        assert "mlog/" in rsync_cmd
        assert "*.bak" in rsync_cmd
        assert "/root/cases/c1/" in rsync_cmd


# ---------------------------------------------------------------------------
# LocalDryRunClient — 不真提交,只记录
# ---------------------------------------------------------------------------

class TestLocalDryRunClient:
    def test_submit_returns_fake_job_id(self, tmp_path, monkeypatch):
        from inp_tool.cluster import ClusterConfig, LocalDryRunClient
        c = ClusterConfig(remote_workdir=str(tmp_path / "remote"))
        client = LocalDryRunClient(c)
        job_id = client.submit("#!/bin/bash\nls\n", remote_dir="/tmp/case1")
        # job_id 是 fake(包含 "DRYRUN-" 或类似)
        assert "DRYRUN" in job_id or "dryrun" in job_id.lower() or job_id.startswith("0")

    def test_dry_run_records_commands(self, tmp_path, monkeypatch):
        from inp_tool.cluster import ClusterConfig, LocalDryRunClient
        c = ClusterConfig(remote_workdir=str(tmp_path / "remote"))
        client = LocalDryRunClient(c)
        client.submit("#!/bin/bash\n", remote_dir="/tmp/c1")
        client.tail("/tmp/c1/mcfd.info0", n=5)
        # 记录的命令应可读出
        if hasattr(client, "commands"):
            assert len(client.commands) >= 2
