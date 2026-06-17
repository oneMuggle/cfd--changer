"""
mcfd.inp sweep CLI — `migrate-sweep-v1` 子命令测试

迁移路径:
- v1 sweep YAML(无 version 字段)→ v2(自动加 version: 2 + conditions: [])
- 已是 v2 的文件再迁移 → 保持原样
- 迁移后用 SweepControllerV2 重新加载应得到 ConfigStore
"""
from __future__ import annotations
import subprocess
import sys


def _run_cli(*args, cwd=None):
    """通过 python -m inp_tool.cli 调用,返回 (returncode, stdout, stderr)"""
    proc = subprocess.run(
        [sys.executable, "-m", "inp_tool.cli", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd is not None else None,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_migrate_sweep_v1_help_shows_subcommand(tmp_path):
    """`inp-tool --help` 应包含 migrate-sweep-v1。"""
    rc, out, err = _run_cli("--help", cwd=tmp_path)
    assert rc == 0, (out, err)
    assert "migrate-sweep-v1" in out


def test_migrate_sweep_v1_writes_version_2(tmp_path):
    """迁移后输出文件应包含 version: 2。"""
    src = tmp_path / "old.yaml"
    src.write_text(
        "template: t\noutput_dir: /o\nsweeps:\n  a: [1,2]\n",
        encoding="utf-8",
    )
    dst = tmp_path / "new.yaml"
    rc, out, err = _run_cli("migrate-sweep-v1", str(src), str(dst), cwd=tmp_path)
    assert rc == 0, (out, err)
    text = dst.read_text(encoding="utf-8")
    assert "version: 2" in text


def test_migrate_sweep_v1_preserves_template_and_sweeps(tmp_path):
    """迁移后 template 和 sweeps 内容应保留。"""
    src = tmp_path / "old.yaml"
    src.write_text(
        "template: my.inp\noutput_dir: /out\nnaming: case\nsweeps:\n"
        "  mach: [0.5, 1.0, 1.5]\n",
        encoding="utf-8",
    )
    dst = tmp_path / "new.yaml"
    rc, out, err = _run_cli("migrate-sweep-v1", str(src), str(dst), cwd=tmp_path)
    assert rc == 0, (out, err)
    text = dst.read_text(encoding="utf-8")
    assert "my.inp" in text
    assert "mach" in text
    assert "0.5" in text


def test_migrate_sweep_v1_already_v2_no_op(tmp_path):
    """已是 v2 的文件再迁移 → 内容保留(无破坏)。"""
    src = tmp_path / "v2.yaml"
    src.write_text(
        "version: 2\ntemplate: t\noutput_dir: /o\nnaming: case\nsweeps: {}\n",
        encoding="utf-8",
    )
    dst = tmp_path / "out.yaml"
    rc, out, err = _run_cli("migrate-sweep-v1", str(src), str(dst), cwd=tmp_path)
    assert rc == 0, (out, err)
    text = dst.read_text(encoding="utf-8")
    assert "version: 2" in text
    assert "template: t" in text


def test_migrate_sweep_v1_roundtrip(tmp_path):
    """迁移后用 SweepControllerV2 重新加载应得到 ConfigStore,sweeps 解析正确。"""
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2

    src = tmp_path / "old.yaml"
    src.write_text(
        "template: t\noutput_dir: /o\nsweeps:\n  mach: [1, 2, 3]\n",
        encoding="utf-8",
    )
    dst = tmp_path / "new.yaml"
    rc, out, err = _run_cli("migrate-sweep-v1", str(src), str(dst), cwd=tmp_path)
    assert rc == 0, (out, err)

    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(dst)
    assert store.sweeps["mach"].kind in ("enum_subset", "explicit_list")
    assert 1 in store.sweeps["mach"].values


def test_migrate_sweep_v1_missing_src_errors(tmp_path):
    """源文件不存在应返回非零退出码。"""
    dst = tmp_path / "out.yaml"
    rc, out, err = _run_cli(
        "migrate-sweep-v1",
        str(tmp_path / "nope.yaml"),
        str(dst),
        cwd=tmp_path,
    )
    assert rc != 0
