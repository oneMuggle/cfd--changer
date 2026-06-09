"""
v0.8.0:复制策略三模式测试(COPY / HARDLINK / SYMLINK)

策略语义:
- COPY:     shutil.copy2(慢,占空间,文件独立)
- HARDLINK: os.link(快,零空间,同 FS,inode 共享)
- SYMLINK:  os.symlink(零空间,跨 FS,Windows 需 dev mode)

失败自动退化:HARDLINK 跨 FS 失败 → COPY;SYMLINK 失败 → HARDLINK → COPY
"""
from __future__ import annotations
import os
import pytest

from inp_tool.sweep import (
    CaseSweep,
    CopyStrategy,
    _copy_one,
    _copy_case_files,
)


# ======================================================================
# _copy_one:基础函数测试
# ======================================================================
class TestCopyOne:
    def test_copy_makes_independent_file(self, tmp_path):
        """COPY:源和目标是独立文件(改目标不影响源)"""
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dst = tmp_path / "dst.txt"
        _copy_one(str(src), str(dst), CopyStrategy.COPY)
        assert dst.read_text() == "hello"
        # 改 dst 不影响 src
        dst.write_text("world")
        assert src.read_text() == "hello"

    def test_hardlink_shares_inode(self, tmp_path):
        """HARDLINK:源和目标共享 inode(改任一方都影响另一方)"""
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dst = tmp_path / "dst.txt"
        _copy_one(str(src), str(dst), CopyStrategy.HARDLINK)
        # 同 inode = 同 st_ino
        assert os.stat(src).st_ino == os.stat(dst).st_ino
        # 改 dst 影响 src
        dst.write_text("world")
        assert src.read_text() == "world"

    def test_symlink_creates_link(self, tmp_path):
        """SYMLINK:目标是符号链接,指向源"""
        from pathlib import Path
        src = tmp_path / "src.txt"
        src.write_text("hello")
        dst = tmp_path / "dst.txt"
        _copy_one(str(src), str(dst), CopyStrategy.SYMLINK)
        assert os.path.islink(dst)
        # Windows 上 os.readlink 返回 extended path 格式 (\\?\C:\...);
        # pathlib.Path 会在 == 比较时规范化路径,跨平台安全
        assert Path(os.readlink(dst)) == src
        # 删源后目标成死链接
        src.unlink()
        assert os.path.islink(dst)
        assert not os.path.exists(dst)


# ======================================================================
# _copy_case_files:目录级别复制
# ======================================================================
def _make_simple_base(base):
    base.mkdir(parents=True, exist_ok=True)
    (base / "mcfd.inp").write_text("aero_alpha 0.0\n")
    (base / "data.bin").write_bytes(b"BIN" * 100)
    (base / "config.txt").write_text("cfg\n")
    return base


class TestCopyCaseFiles:
    def test_copy_strategy_creates_real_files(self, tmp_path):
        """COPY:目标目录里有真实文件(非链接)"""
        base = _make_simple_base(tmp_path / "base")
        dst = tmp_path / "case"
        copied = _copy_case_files(str(base), str(dst), [], CopyStrategy.COPY)
        # 全部文件都复制了
        assert (dst / "mcfd.inp").is_file()
        assert (dst / "data.bin").is_file()
        assert (dst / "config.txt").is_file()
        # data.bin 不是 symlink,不是 hardlink
        st = os.stat(dst / "data.bin")
        assert not os.path.islink(dst / "data.bin")

    def test_hardlink_strategy_shares_inode(self, tmp_path):
        """HARDLINK:目标 data.bin 与源共享 inode"""
        base = _make_simple_base(tmp_path / "base")
        dst = tmp_path / "case"
        _copy_case_files(str(base), str(dst), [], CopyStrategy.HARDLINK)
        # 硬链接的 st_ino 应相同
        assert os.stat(base / "data.bin").st_ino == os.stat(dst / "data.bin").st_ino
        # 但不是 symlink
        assert not os.path.islink(dst / "data.bin")

    def test_symlink_strategy_creates_symlinks(self, tmp_path):
        """SYMLINK:目标文件都是 symlink(指回源)"""
        base = _make_simple_base(tmp_path / "base")
        dst = tmp_path / "case"
        _copy_case_files(str(base), str(dst), [], CopyStrategy.SYMLINK)
        # 全部都是 symlink
        for f in ["mcfd.inp", "data.bin", "config.txt"]:
            assert os.path.islink(dst / f), f"{f} should be symlink"
            # 链接目标应是源文件绝对路径
            target = os.readlink(dst / f)
            assert os.path.basename(target) == f

    def test_returns_copied_file_list(self, tmp_path):
        """返回的 copied 列表含全部相对路径(供 manifest 用)"""
        base = _make_simple_base(tmp_path / "base")
        dst = tmp_path / "case"
        copied = _copy_case_files(str(base), str(dst), [], CopyStrategy.COPY)
        assert set(copied) == {"mcfd.inp", "data.bin", "config.txt"}

    def test_exclude_applied(self, tmp_path):
        """排除规则生效:默认排除 *.bak"""
        base = tmp_path / "base"
        base.mkdir()
        (base / "keep.txt").write_text("k\n")
        (base / "x.bak").write_text("b\n")
        dst = tmp_path / "case"
        copied = _copy_case_files(str(base), str(dst), ["*.bak"], CopyStrategy.COPY)
        assert (dst / "keep.txt").is_file()
        assert not (dst / "x.bak").exists()
        assert "keep.txt" in copied
        assert "x.bak" not in copied

    def test_source_dir_not_found_raises(self, tmp_path):
        """src 不存在时抛 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            _copy_case_files(
                str(tmp_path / "nonexistent"),
                str(tmp_path / "case"),
                [],
                CopyStrategy.COPY,
            )

    def test_target_exists_raises(self, tmp_path):
        """dst 已存在时抛 FileExistsError(避免静默覆盖)"""
        base = _make_simple_base(tmp_path / "base")
        dst = tmp_path / "case"
        dst.mkdir()  # 预创建
        with pytest.raises(FileExistsError):
            _copy_case_files(str(base), str(dst), [], CopyStrategy.COPY)


# ======================================================================
# 端到端:CaseSweep → generate() 走指定策略
# ======================================================================
class TestGenerateWithStrategy:
    @pytest.fixture
    def base(self, tmp_path):
        b = tmp_path / "base"
        b.mkdir()
        (b / "mcfd.inp").write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        (b / "grid.bin").write_bytes(b"GRID")
        return b

    def _sweep(self, base, out, strategy):
        return CaseSweep.from_dict({
            "template": str(base / "mcfd.inp"),
            "output_dir": str(out),
            "source_dir": str(base),
            "copy_strategy": strategy.value,
            "sweeps": {"alpha": [0]},
        })

    def test_generate_with_copy_strategy(self, base, tmp_path):
        out = tmp_path / "out"
        from inp_tool.sweep import generate
        cs = self._sweep(base, out, CopyStrategy.COPY)
        generate(cs)
        # grid.bin 是真实文件,不是链接
        assert (out / "case" / "grid.bin").is_file()
        assert not os.path.islink(out / "case" / "grid.bin")

    def test_generate_with_hardlink_strategy(self, base, tmp_path):
        out = tmp_path / "out"
        from inp_tool.sweep import generate
        cs = self._sweep(base, out, CopyStrategy.HARDLINK)
        generate(cs)
        # grid.bin 是硬链接(同 inode)
        src_st = os.stat(base / "grid.bin")
        dst_st = os.stat(out / "case" / "grid.bin")
        assert src_st.st_ino == dst_st.st_ino
        assert not os.path.islink(out / "case" / "grid.bin")

    def test_generate_with_symlink_strategy(self, base, tmp_path):
        out = tmp_path / "out"
        from inp_tool.sweep import generate
        cs = self._sweep(base, out, CopyStrategy.SYMLINK)
        generate(cs)
        # grid.bin 是符号链接
        assert os.path.islink(out / "case" / "grid.bin")
