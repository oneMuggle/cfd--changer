"""PBS / cluster CLI 端到端单测(v0.14.0 / Phase 1+2+3)

覆盖:
- inp-tool cluster config --path / --show / --set / --init
- inp-tool cluster probe (mock subprocess)
- inp-tool cluster test (mock subprocess)
- inp-tool pbs submit --dry-run (走 LocalDryRunClient)
- inp-tool pbs status (mock cluster.status)

目的: 提升 cli.py 覆盖率(避免 CI --cov-fail-under=80 红)
"""
from __future__ import annotations

import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from inp_tool.cli import main
from inp_tool.cluster import ClusterConfig, LocalDryRunClient


# ---------------------------------------------------------------------------
# inp-tool cluster config
# ---------------------------------------------------------------------------

class TestClusterConfigCli:
    def test_path_prints_path(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        rc = main(["cluster", "config", "--path"])
        out = capsys.readouterr().out.strip()
        assert "cluster.json" in out
        assert rc == 0

    def test_show_prints_json(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        rc = main(["cluster", "config", "--show"])
        out = capsys.readouterr().out
        # 至少包含一个字段
        assert "host" in out
        assert "max_concurrent_jobs" in out
        assert rc == 0

    def test_set_updates_field(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        rc = main([
            "cluster", "config", "--set", "host=10.10.10.251",
            "--set", "max_concurrent_jobs=15",
        ])
        assert rc == 0
        # 重新 load
        cfg = ClusterConfig.load()
        assert cfg.host == "10.10.10.251"
        assert cfg.max_concurrent_jobs == 15

    def test_set_unknown_field_errors(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["cluster", "config", "--set", "nosuchfield=x"])
        out = capsys.readouterr()
        assert "未知字段" in out.err or "nosuchfield" in out.err
        assert rc == 1

    def test_set_bad_format_errors(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["cluster", "config", "--set", "no_equals_sign"])
        out = capsys.readouterr()
        assert rc == 1

    def test_init_prints_help(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["cluster", "config", "--init"])
        out = capsys.readouterr().out
        assert "--set" in out
        assert rc == 0


# ---------------------------------------------------------------------------
# inp-tool cluster probe / test (mock subprocess)
# ---------------------------------------------------------------------------

class TestClusterProbeCli:
    def test_probe_torque_success(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        # mock ssh: qstat --version 成功
        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if "qstat" in cmd_str:
                return CompletedProcess(cmd, 0, stdout="version: PBSPro_20.0.1\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = main(["cluster", "probe", "--host", "h", "--user", "u"])
        out = capsys.readouterr().out
        assert "torque" in out
        assert rc == 0

    def test_probe_failure_returns_1(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 127, stdout="", stderr="not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = main(["cluster", "probe", "--host", "h", "--user", "u"])
        assert rc == 1


class TestClusterTestCli:
    def test_test_ssh_failure(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        def fake_run(cmd, **kwargs):
            return CompletedProcess(cmd, 127, stdout="", stderr="not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = main(["cluster", "test", "--host", "h", "--user", "u"])
        out = capsys.readouterr()
        assert rc == 1

    def test_test_ssh_success(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        def fake_run(cmd, **kwargs):
            cmd_str = " ".join(cmd) if isinstance(cmd, (list, tuple)) else str(cmd)
            if "qstat" in cmd_str:
                return CompletedProcess(cmd, 0, stdout="PBSPro_20.0.1\n", stderr="")
            return CompletedProcess(cmd, 1, stdout="", stderr="not found")

        monkeypatch.setattr("subprocess.run", fake_run)
        rc = main(["cluster", "test", "--host", "h", "--user", "u"])
        out = capsys.readouterr().out
        assert "torque" in out
        assert rc == 0


# ---------------------------------------------------------------------------
# inp-tool pbs submit
# ---------------------------------------------------------------------------

def _make_minimal_manifest(base_dir: Path, n_cases: int = 2) -> Path:
    """合成 sweep_report.json + 每个 case 目录 + pbs 脚本。"""
    cases = []
    for i in range(n_cases):
        case_id = f"case_{i:03d}"
        case_path = base_dir / case_id
        case_path.mkdir(parents=True, exist_ok=True)
        (case_path / "mcfd.inp").write_text("# minimal\ntitle\ndummy\nend\n")
        pbs_name = f"Mars_a{i:02d}"
        (case_path / f"run_{pbs_name}.pbs").write_text(
            f"#!/bin/bash\n#PBS -N {pbs_name}\nls\n"
        )
        cases.append({
            "case_id": case_id,
            "path": str(case_path),
            "params": {"alpha": i},
            "applied": {},
            "pbs_name": pbs_name,
            "pbs_template": f"run_{pbs_name}.pbs",
        })
    manifest = {
        "template": str(base_dir / "t.inp"),
        "total": n_cases,
        "cases": cases,
        "layout": "per_dir",
        "generated_at": "2026-06-13T10:00:00",
    }
    manifest_path = base_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


class TestPbsSubmitCliDryRun:
    def test_dry_run_uses_local_dry_run(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        manifest = _make_minimal_manifest(tmp_path, n_cases=2)
        rc = main([
            "pbs", "submit", str(manifest),
            "--dry-run",
            "--host", "h", "--user", "u",
        ])
        out = capsys.readouterr().out
        # dry-run 模式 + LocalDryRunClient → 应该跑通
        assert "DRYRUN" in out or "成功" in out
        # 没失败
        assert "失败" not in out or "失败: 0" in out

    def test_dry_run_with_sweep_dir(self, capsys, monkeypatch, tmp_path):
        """传 sweep 目录时,自动找 manifest.json"""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        # 把 manifest 放到 sweep_dir 下
        sweep_dir = tmp_path / "sweep"
        sweep_dir.mkdir()
        manifest_dst = sweep_dir / "manifest.json"
        # 在 sweep_dir/case_000/ 下写脚本
        for i in range(1):
            case_path = sweep_dir / f"case_{i:03d}"
            case_path.mkdir()
            (case_path / "mcfd.inp").write_text("# m\n")
            (case_path / "run_Mars_a00.pbs").write_text("#!/bin/bash\n#PBS -N x\n")
        manifest = {
            "template": str(sweep_dir / "t.inp"),
            "total": 1,
            "cases": [
                {"case_id": "case_000", "path": str(sweep_dir / "case_000"),
                 "params": {}, "applied": {}, "pbs_name": "Mars_a00",
                 "pbs_template": "run_Mars_a00.pbs"},
            ],
            "layout": "per_dir",
        }
        manifest_dst.write_text(json.dumps(manifest))
        rc = main(["pbs", "submit", str(sweep_dir), "--dry-run"])
        out = capsys.readouterr().out
        assert "成功" in out or "DRYRUN" in out

    def test_missing_sweep_report(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["pbs", "submit", str(tmp_path / "nope.json")])
        out = capsys.readouterr()
        assert rc == 1

    def test_sweep_dir_without_manifest(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        rc = main(["pbs", "submit", str(empty_dir), "--from-sweep-dir"])
        out = capsys.readouterr()
        assert rc == 1

    def test_no_sweep_report_arg(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["pbs", "submit"])
        out = capsys.readouterr()
        assert rc == 1


# ---------------------------------------------------------------------------
# inp-tool pbs status
# ---------------------------------------------------------------------------

class TestPbsStatusCli:
    def test_status_table(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        manifest = _make_minimal_manifest(tmp_path, n_cases=2)
        # 加 pbs_submissions 段
        m = json.loads(manifest.read_text())
        m["pbs_submissions"] = [
            {"case_dir": str(tmp_path / f"case_{i:03d}"),
             "case_name": f"case_{i:03d}", "job_id": str(100 + i),
             "pbs_name": f"Mars_a{i:02d}", "submit_time": "2026-06-13T10:00:00",
             "state": "Q", "host": "h", "queue": "q02"}
            for i in range(2)
        ]
        manifest.write_text(json.dumps(m))

        # mock:patch SshClusterClient.status 方法
        from inp_tool.cluster import SshClusterClient, PbsJobStatus
        def fake_status(self, job_id):
            return PbsJobStatus(job_id, "n", "u", "Q", "q02")
        monkeypatch.setattr(SshClusterClient, "status", fake_status)

        rc = main(["pbs", "status", str(manifest)])
        out = capsys.readouterr().out
        assert "case_000" in out
        assert "case_001" in out
        assert "Q=2" in out or "Q = 2" in out

    def test_status_json(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        manifest = _make_minimal_manifest(tmp_path, n_cases=1)
        m = json.loads(manifest.read_text())
        m["pbs_submissions"] = [
            {"case_dir": str(tmp_path / "case_000"),
             "case_name": "case_000", "job_id": "100",
             "pbs_name": "Mars_a00", "submit_time": "2026-06-13T10:00:00",
             "state": "Q", "host": "h", "queue": "q02"}
        ]
        manifest.write_text(json.dumps(m))

        from inp_tool.cluster import SshClusterClient, PbsJobStatus
        def fake_status(self, job_id):
            return PbsJobStatus(job_id, "n", "u", "Q", "q02")
        monkeypatch.setattr(SshClusterClient, "status", fake_status)

        rc = main(["pbs", "status", str(manifest), "--json"])
        out = capsys.readouterr().out
        # JSON 输出
        d = json.loads(out)
        assert d["total"] == 1
        assert d["summary"] == {"Q": 1}

    def test_status_filter(self, capsys, monkeypatch, tmp_path):
        """--filter R,C 只看运行+完成的 case。

        本测试不调 main() 触发真实 SSH(默认 host 10.10.10.251 网络不可达会卡 90s),
        只测 ``--filter`` 参数解析 + query_sweep_status filter 行为。
        CLI 集成测试在 test_pbs_status.py 中已覆盖。
        """
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        manifest = _make_minimal_manifest(tmp_path, n_cases=3)
        m = json.loads(manifest.read_text())
        m["pbs_submissions"] = [
            {"case_dir": str(tmp_path / f"case_{i:03d}"),
             "case_name": f"case_{i:03d}", "job_id": str(100 + i),
             "pbs_name": f"Mars_a{i:02d}", "submit_time": "2026-06-13T10:00:00",
             "state": "Q", "host": "h", "queue": "q02"}
            for i in range(3)
        ]
        manifest.write_text(json.dumps(m))

        from inp_tool.batch import query_sweep_status, summarize_states
        from inp_tool.cluster import ClusterConfig, LocalDryRunClient
        client = LocalDryRunClient(ClusterConfig())
        all_entries = query_sweep_status(manifest, client, filter_states=None)
        r_filtered = query_sweep_status(manifest, client, filter_states=["R", "C"])
        # LocalDryRunClient.status 全返 "Q",filter [R, C] 后空
        assert len(r_filtered) == 0
        assert len(all_entries) == 3
        assert summarize_states(all_entries) == {"Q": 3}

    def test_status_no_pbs_submissions(self, capsys, monkeypatch, tmp_path):
        """没 pbs_submissions 段 → (无 case)"""
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        manifest = _make_minimal_manifest(tmp_path, n_cases=2)
        # 不加 pbs_submissions 段
        rc = main(["pbs", "status", str(manifest)])
        out = capsys.readouterr().out
        assert "无 case" in out or "0 case" in out

    def test_status_missing_manifest(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["pbs", "status", str(tmp_path / "nope.json")])
        assert rc == 1

    def test_status_no_arg(self, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        rc = main(["pbs", "status"])
        assert rc == 1
