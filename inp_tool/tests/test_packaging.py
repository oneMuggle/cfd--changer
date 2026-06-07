"""
inp_tool 打包测试 — 验证 spec / 脚本 / extras 正确性

测试策略:
- 静态检查: spec / build.sh / build.bat / pyproject.toml [build] extras 存在
- 动态构建(可跳过): 实际跑 PyInstaller 生成 binary 并 smoke test
"""
from __future__ import annotations
import os
import sys
from pathlib import Path

import pytest

# 项目根
INP_TOOL_ROOT = Path(__file__).resolve().parent.parent


# ==================================================================
# 静态检查(spec / scripts / extras)
# ==================================================================
class TestPackagingFiles:
    def test_spec_file_exists(self):
        spec = INP_TOOL_ROOT / "inp_tool.spec"
        assert spec.is_file(), f"missing {spec}"

    def test_spec_has_onefile_config(self):
        spec_text = (INP_TOOL_ROOT / "inp_tool.spec").read_text()
        # 单文件模式 = 只用 EXE(),不用 COLLECT() 包裹(onedir 模式才会)
        assert "EXE(" in spec_text
        assert "COLLECT(" not in spec_text, "spec 用 COLLECT 则是 onedir 模式(多文件)"
        assert "console=True" in spec_text

    def test_spec_datas_include_examples(self):
        spec_text = (INP_TOOL_ROOT / "inp_tool.spec").read_text()
        assert "examples" in spec_text
        assert "web" in spec_text

    def test_spec_includes_required_hiddenimports(self):
        spec_text = (INP_TOOL_ROOT / "inp_tool.spec").read_text()
        for mod in ("inp_tool.sweep", "inp_tool.api", "inp_tool.cli"):
            assert mod in spec_text, f"spec missing hiddenimport: {mod}"

    def test_build_sh_exists_and_executable(self):
        sh = INP_TOOL_ROOT.parent / "scripts" / "build.sh"
        assert sh.is_file()
        # v0.4.2: 不再检查 st_mode 的 execute bit — Windows NTFS 不支持 Unix mode,
        # git checkout 时 build.sh 在 Windows runner 上 mode 是 0o100666(无 execute)。
        # 改为检查 shebang 头(跨平台一致,反映"意图可执行")
        head = sh.read_text(encoding="utf-8", errors="replace").splitlines()[:3]
        assert any(line.startswith("#!") and "sh" in line for line in head), (
            f"build.sh 缺少 shebang 头: {head!r}"
        )

    def test_build_bat_exists(self):
        bat = INP_TOOL_ROOT.parent / "scripts" / "build.bat"
        assert bat.is_file()

    def test_pyproject_has_build_extra(self):
        toml_text = (INP_TOOL_ROOT / "pyproject.toml").read_text()
        assert "[project.optional-dependencies]" in toml_text
        assert "build = [" in toml_text
        assert "pyinstaller==6.16.0" in toml_text


# ==================================================================
# 动态构建(默认跳过,需要环境变量 ENABLE_BUILD_TEST=1)
# ==================================================================
@pytest.mark.skipif(
    "1" != os.environ.get("ENABLE_BUILD_TEST", "0"),
    reason="set ENABLE_BUILD_TEST=1 to run full build (slow)",
)
class TestFullBuild:
    def test_built_binary_runs(self, tmp_path):
        """跑 PyInstaller 生成 binary,验证能跑 --version"""
        import subprocess
        subprocess.run(
            ["pyinstaller", "--clean", "--noconfirm", "inp_tool.spec"],
            cwd=str(INP_TOOL_ROOT), check=True, capture_output=True,
        )
        if sys.platform.startswith("win"):
            binary = INP_TOOL_ROOT / "dist" / "inp-tool.exe"
        else:
            binary = INP_TOOL_ROOT / "dist" / "inp-tool"
        assert binary.is_file(), f"binary not found: {binary}"

        r = subprocess.run([str(binary), "--version"], capture_output=True, text=True, timeout=30)
        assert r.returncode == 0
        assert "0.4" in r.stdout

    def test_built_binary_sweep_works(self, tmp_path):
        """跑 binary 做一次端到端 sweep,验证几何分解正确"""
        import subprocess
        import json

        binary = (
            INP_TOOL_ROOT / "dist" / ("inp-tool.exe" if sys.platform.startswith("win") else "inp-tool")
        )
        tpl = INP_TOOL_ROOT / "examples" / "mcfd_v2_modified.inp"
        cfg = tmp_path / "sweep.json"
        cfg.write_text(json.dumps({
            "template": str(tpl),
            "output_dir": str(tmp_path / "out"),
            "sweeps": {
                "alpha": [8.0],
                "mach":  [0.6],
                "T_inf": [288.15],
                "p_inf": [101325.0],
            },
            "naming": "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
        }))

        r = subprocess.run(
            [str(binary), "sweep", str(cfg)],
            capture_output=True, text=True, timeout=60,
        )
        assert r.returncode == 0, f"stderr: {r.stderr}"

        case_file = tmp_path / "out" / "case_aoa08_ma0.60.inp"
        assert case_file.is_file()
