"""
v0.8.0:sweep 整算例目录生成(source_dir + per-case dir)测试

Phase 1:数据模型扩展(零行为变化)
- CopyStrategy 枚举:copy / hardlink / symlink
- CaseSweep 新字段:source_dir / copy_strategy / exclude
- _resolve_layout():依据 source_dir 返回 "flat" 或 "per_dir"
- from_dict 解析新字段
- 老用法(不传 source_dir)行为零变化
"""
from __future__ import annotations
import os
import shutil
import pytest

from inp_tool.sweep import (
    CaseSweep,
    CopyStrategy,           # 新增
    _resolve_layout,        # 新增
)


# ======================================================================
# CopyStrategy 枚举
# ======================================================================
class TestCopyStrategyEnum:
    def test_three_values_exist(self):
        assert CopyStrategy.COPY.value == "copy"
        assert CopyStrategy.HARDLINK.value == "hardlink"
        assert CopyStrategy.SYMLINK.value == "symlink"

    def test_string_compatible(self):
        # 允许 str 类型用于 argparse / YAML
        assert CopyStrategy("copy") == CopyStrategy.COPY
        assert CopyStrategy("hardlink") == CopyStrategy.HARDLINK
        assert CopyStrategy("symlink") == CopyStrategy.SYMLINK

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            CopyStrategy("invalid")


# ======================================================================
# CaseSweep 新字段默认值
# ======================================================================
class TestCaseSweepNewFieldsDefaults:
    def test_source_dir_defaults_to_none(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        assert cs.source_dir is None  # 老用法:不复制,只写 mcfd.inp

    def test_copy_strategy_defaults_to_hardlink(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        # 默认 hardlink:零空间、跨平台兼容
        assert cs.copy_strategy == CopyStrategy.HARDLINK

    def test_exclude_has_safe_defaults(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        # 默认排除 .bak、mlog/、nodesout.bin(求解器输出)
        assert "*.bak" in cs.exclude
        assert "mlog" in cs.exclude
        assert "nodesout.bin" in cs.exclude

    def test_exclude_is_list(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        assert isinstance(cs.exclude, list)


# ======================================================================
# _resolve_layout:布局判定
# ======================================================================
class TestResolveLayout:
    def test_no_source_dir_returns_flat(self):
        """老用法:source_dir 未设 → flat(每个 case 1 个 mcfd.inp 文件)"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "sweeps": {"alpha": [0]},
        })
        assert _resolve_layout(cs) == "flat"

    def test_source_dir_set_returns_per_dir(self):
        """新用法:source_dir 有值 → per_dir(每个 case 1 个子目录)"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "source_dir": "/some/base",
            "sweeps": {"alpha": [0]},
        })
        assert _resolve_layout(cs) == "per_dir"


# ======================================================================
# from_dict 解析新字段
# ======================================================================
class TestFromDictParsesNewFields:
    def test_source_dir_parsed(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "source_dir": "/path/to/base",
            "sweeps": {"alpha": [0]},
        })
        assert cs.source_dir == "/path/to/base"

    def test_copy_strategy_parsed_string(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "copy_strategy": "copy",
            "sweeps": {"alpha": [0]},
        })
        assert cs.copy_strategy == CopyStrategy.COPY

    def test_copy_strategy_invalid_raises(self):
        with pytest.raises(ValueError):
            CaseSweep.from_dict({
                "template": "t.inp",
                "output_dir": "out",
                "copy_strategy": "rsync",  # 不支持
                "sweeps": {"alpha": [0]},
            })

    def test_exclude_parsed_list(self):
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "exclude": ["*.tmp", "build/"],
            "sweeps": {"alpha": [0]},
        })
        assert cs.exclude == ["*.tmp", "build/"]

    def test_exclude_none_uses_defaults(self):
        """YAML 写 exclude: null 时仍用默认值"""
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "exclude": None,
            "sweeps": {"alpha": [0]},
        })
        # 默认非空
        assert len(cs.exclude) > 0
        assert "*.bak" in cs.exclude


# ======================================================================
# 向后兼容:老用法 generate() 仍写扁平 .inp
# ======================================================================
class TestBackwardCompatFlat:
    def test_no_source_dir_writes_flat_inp_files(self, tmp_path):
        """source_dir 未设 → 行为与 v0.7.1 完全一致(每个 case = 1 个 .inp 文件)"""
        # 简单模板
        template = tmp_path / "t.inp"
        template.write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "sweeps": {"alpha": [0, 4]},
        })
        from inp_tool.sweep import generate
        report = generate(cs)
        # 输出应是 2 个 .inp 文件(扁平),不是 2 个子目录
        assert report.total == 2
        assert _resolve_layout(cs) == "flat"
        for c in report.cases:
            assert os.path.isfile(c.path)
            assert c.path.endswith(".inp")
            assert os.path.dirname(c.path) == str(out)

    def test_source_dir_set_but_generate_not_yet_implemented(self, tmp_path):
        """Phase 1 阶段:source_dir 设了但 generate() 暂未实现 per_dir 行为
        → 测试会 Phase 2 再启用,这里仅断言 _resolve_layout 返回 per_dir
        """
        cs = CaseSweep.from_dict({
            "template": "t.inp",
            "output_dir": "out",
            "source_dir": "/some/base",
            "sweeps": {"alpha": [0]},
        })
        assert _resolve_layout(cs) == "per_dir"
        # 实际 generate() 行为 Phase 2+ 实现


# ======================================================================
# Phase 2:per_dir 实际行为(目录复制 + mcfd.inp 覆盖)
# ======================================================================


def _make_base_case(base: "Path") -> None:
    """建一个最小基础算例目录(模拟 reference/suanli 的子集)"""
    base.mkdir(parents=True, exist_ok=True)
    # 配置文件
    (base / "mcfd.inp").write_text(
        "guiopts begin\naero_alpha 0.0\nguiopts end\n"
    )
    (base / "mcfd.bc").write_text("bc_data\n")
    (base / "npfopts.inp").write_text("npfopts_data\n")
    # 模拟网格文件
    (base / "cellsin.bin").write_bytes(b"BIN" * 100)
    (base / "nodesin.bin").write_bytes(b"BIN" * 50)
    # 备份(应被排除)
    (base / "mcfd.inp.bak").write_text("old\n")
    (base / "nodesin.bin.bak").write_bytes(b"OLD" * 50)
    # 求解器输出(应被排除)
    (base / "nodesout.bin").write_bytes(b"OUT" * 30)
    # 日志目录(应被排除)
    mlog = base / "mlog"
    mlog.mkdir()
    (mlog / "mcfdgui_c.log").write_text("log\n")
    # 物性文件
    (base / "C.dat").write_text("C\n")
    (base / "O2.dat").write_text("O2\n")


class TestPerDirGenerate:
    def test_per_dir_creates_subdirectory_per_case(self, tmp_path):
        """per_dir 模式:每个 case 一个子目录(无 .inp 扩展名)"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [0, 4]},
        })
        from inp_tool.sweep import generate
        report = generate(cs)
        # 2 个 case → 2 个子目录
        assert report.total == 2
        for c in report.cases:
            assert os.path.isdir(c.path)  # 是目录不是文件
            assert not c.path.endswith(".inp")  # 无扩展名
            assert os.path.dirname(c.path) == str(out)

    def test_per_dir_copies_all_non_excluded_files(self, tmp_path):
        """per_dir 模式:每个子目录包含 source_dir 全部文件(除 exclude)"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [0]},
        })
        from inp_tool.sweep import generate
        report = generate(cs)
        case_dir = Path(report.cases[0].path)
        # 应有的文件
        for f in ["mcfd.inp", "mcfd.bc", "npfopts.inp",
                  "cellsin.bin", "nodesin.bin",
                  "C.dat", "O2.dat"]:
            assert (case_dir / f).is_file(), f"missing {f}"
        # 应排除的(默认规则)
        assert not (case_dir / "mcfd.inp.bak").exists()
        assert not (case_dir / "nodesin.bin.bak").exists()
        assert not (case_dir / "nodesout.bin").exists()
        assert not (case_dir / "mlog").exists()

    def test_per_dir_overwrites_mcfd_inp_with_modified(self, tmp_path):
        """per_dir 模式:复制完后,目标 mcfd.inp 被修改版覆盖"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [4.0]},  # 改 alpha
        })
        from inp_tool.sweep import generate
        from inp_tool import parse_file
        report = generate(cs)
        case_dir = Path(report.cases[0].path)
        # 解析子目录里的 mcfd.inp
        inp = parse_file(str(case_dir / "mcfd.inp"))
        assert inp.get("guiopts", "aero_alpha") == 4.0  # 已修改

    def test_per_dir_custom_exclude(self, tmp_path):
        """per_dir 模式:自定义 exclude 规则生效"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "exclude": ["*.bin", "mlog", "*.bak", "nodesout.bin"],
            "sweeps": {"alpha": [0]},
        })
        from inp_tool.sweep import generate
        report = generate(cs)
        case_dir = Path(report.cases[0].path)
        # 自定义 exclude 包含 *.bin,所以 .bin 网格都不应被打包
        assert not (case_dir / "cellsin.bin").exists()
        assert not (case_dir / "nodesin.bin").exists()
        # 其他文件正常
        assert (case_dir / "mcfd.inp").is_file()
        assert (case_dir / "C.dat").is_file()

    def test_per_dir_target_exists_raises(self, tmp_path):
        """per_dir 模式:目标子目录已存在时,默认报错(避免静默覆盖)"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        out.mkdir()
        # 默认 naming: {alpha: [0]} 单值 → "case";预创建同名目录
        (out / "case").mkdir()  # 占位
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [0]},
        })
        from inp_tool.sweep import generate
        with pytest.raises((FileExistsError, OSError)):
            generate(cs)

    def test_per_dir_dry_run_no_files_written(self, tmp_path):
        """per_dir 模式:dry-run 时不实际创建子目录"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [0, 4]},
        })
        from inp_tool.sweep import generate
        report = generate(cs, dry_run=True)
        # 报告仍生成
        assert report.total == 2
        # 但 output_dir 下不应有 case_0 / case_4 子目录
        assert not out.exists() or list(out.iterdir()) == []

    def test_per_dir_force_overwrites(self, tmp_path):
        """per_dir 模式:force=True 覆盖已存在的目标子目录"""
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        out.mkdir()
        (out / "case").mkdir()  # 预创建
        (out / "case" / "old_file.txt").write_text("stale")
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "sweeps": {"alpha": [0]},
        })
        from inp_tool.sweep import generate
        # force=True 不抛错
        report = generate(cs, force=True)
        # 旧文件被清除,新文件到位
        assert not (out / "case" / "old_file.txt").exists()
        assert (out / "case" / "mcfd.inp").is_file()
        assert (out / "case" / "mcfd.bc").is_file()


# ======================================================================
# Phase 4:manifest 扩展(per_dir 模式)
# ======================================================================
class TestManifestExtension:
    def test_flat_manifest_unchanged(self, tmp_path):
        """flat 模式(老用法):manifest 不含新字段(向后兼容)"""
        import json
        template = tmp_path / "t.inp"
        template.write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        out = tmp_path / "out"
        manifest = out / "manifest.json"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "sweeps": {"alpha": [0]},
            "manifest": {"path": str(manifest)},
        })
        from inp_tool.sweep import generate
        generate(cs)
        data = json.loads(manifest.read_text())
        # 老字段在
        assert "template" in data
        assert "total" in data
        assert "cases" in data
        # 新字段不在(flat 模式不污染)
        assert "layout" not in data
        assert "source_dir" not in data
        assert "copy_strategy" not in data

    def test_per_dir_manifest_has_new_fields(self, tmp_path):
        """per_dir 模式:manifest 含 layout/source_dir/copy_strategy/exclude/files"""
        import json
        base = tmp_path / "base"
        _make_base_case(base)
        template = base / "mcfd.inp"
        out = tmp_path / "out"
        manifest = out / "manifest.json"
        cs = CaseSweep.from_dict({
            "template": str(template),
            "output_dir": str(out),
            "source_dir": str(base),
            "copy_strategy": "hardlink",
            "exclude": ["*.bak", "mlog", "nodesout.bin", "*.log"],
            "sweeps": {"alpha": [0]},
            "manifest": {"path": str(manifest)},
        })
        from inp_tool.sweep import generate
        generate(cs)
        data = json.loads(manifest.read_text())
        # 顶层新字段
        assert data["layout"] == "per_dir"
        assert data["source_dir"] == str(base)
        assert data["copy_strategy"] == "hardlink"
        assert "*.bak" in data["exclude"]
        # 每 case 的 files 字段
        case = data["cases"][0]
        assert "files" in case
        assert "mcfd.inp" in case["files"]  # (虽然被覆写,仍记录复制时清单)
        assert "mcfd.bc" in case["files"]
        assert "cellsin.bin" in case["files"]
        # 排除项不在
        assert "mcfd.inp.bak" not in case["files"]
        assert "nodesout.bin" not in case["files"]


# 放在文件末尾(避免破坏上面的 Path 引用)
from pathlib import Path  # noqa: E402
