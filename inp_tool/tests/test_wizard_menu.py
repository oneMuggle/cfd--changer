"""
PR #2 阶段 3-6:wizard 菜单测试

无参 `wizard` 入口:显示菜单 → 选向导 → run。
"""
from __future__ import annotations
import pytest

from inp_tool.wizard import run_menu
from inp_tool import i18n


@pytest.fixture(autouse=True)
def _force_zh():
    i18n.set_lang("zh")
    yield
    i18n.set_lang("zh")


class TestRunMenu:
    def test_menu_picks_modify_file(self, monkeypatch, tmp_path, capsys):
        inp = tmp_path / "t.inp"
        inp.write_text("x")
        responses = iter([
            "1",
            str(inp),
            "1",
            "0.8",
            "y",
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        run_menu()
        out = capsys.readouterr().out
        assert "向导" in out or "修改" in out

    def test_menu_picks_sweep(self, monkeypatch, tmp_path, capsys):
        """v0.8.2:菜单选 sweep → 6 步(source_dir 必填)。"""
        base = tmp_path / "base"
        base.mkdir()
        (base / "mcfd.inp").write_text(
            "guiopts begin\n"
            "aero_alpha 0.0\n"
            "aero_beta 0.0\n"
            "aero_ma 0.0\n"
            "guiopts end\n"
        )
        out_dir = str(tmp_path / "cases")
        responses = iter([
            "2",                  # menu pick sweep
            str(base),            # 1. source_dir
            "1",                  # 2. hardlink
            out_dir,              # 3. output
            "n",                  # 4. manifest? no
            "1",                  # 5. mode cartesian
            "{alpha: [0]}",       # 6. sweeps
            "case_{alpha}",       # 7. naming
            "y",                  # 8. confirm
            "n",                  # 9. 不覆盖
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        run_menu()
        out = capsys.readouterr().out
        assert "生成" in out

    def test_menu_picks_diff(self, monkeypatch, tmp_path, capsys):
        a = tmp_path / "a.inp"
        a.write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        b = tmp_path / "b.inp"
        b.write_text("guiopts begin\naero_alpha 5.0\nguiopts end\n")
        responses = iter(["3", str(a), str(b), "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        run_menu()
        out = capsys.readouterr().out
        assert "差异" in out

    def test_menu_quit(self, monkeypatch, capsys):
        monkeypatch.setattr("builtins.input", lambda _: "q")
        run_menu()
        out = capsys.readouterr().out
        assert "退出" in out or "wizard" in out.lower()


class TestModuleExports:
    def test_run_modify_file(self, monkeypatch, tmp_path):
        inp = tmp_path / "t.inp"
        inp.write_text("x")
        responses = iter([str(inp), "1", "0.8", "y"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        from inp_tool.wizard import run_modify_file
        run_modify_file()

    def test_run_sweep(self, monkeypatch, tmp_path):
        """v0.8.2:run_sweep 6 步(source_dir 必填)。"""
        base = tmp_path / "base"
        base.mkdir()
        (base / "mcfd.inp").write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        out_dir = str(tmp_path / "cases")
        responses = iter([
            str(base),            # 1. source_dir
            "1",                  # 2. hardlink
            out_dir,              # 3. output dir
            "n",                  # 4. manifest? no
            "1",                  # 5. mode menu=cartesian
            "{alpha: [0]}",       # 6. sweeps
            "case_{alpha}",       # 7. naming
            "y",                  # 8. confirm continue
            "n",                  # 9. 不覆盖
        ])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        from inp_tool.wizard import run_sweep
        run_sweep()

    def test_run_diff(self, monkeypatch, tmp_path):
        a = tmp_path / "a.inp"
        a.write_text("guiopts begin\naero_alpha 0.0\nguiopts end\n")
        b = tmp_path / "b.inp"
        b.write_text("guiopts begin\naero_alpha 5.0\nguiopts end\n")
        responses = iter([str(a), str(b), "1"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        from inp_tool.wizard import run_diff
        run_diff()
