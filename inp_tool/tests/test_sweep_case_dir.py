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
