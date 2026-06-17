"""PresetLibrary 单测(纯 Python,纯文件系统,无 Qt)。"""
from pathlib import Path
import pytest


def test_preset_library_save_and_list(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {"mach": [1, 2]}, "conditions": []})
    items = lib.list()
    assert len(items) == 1
    assert items[0].name == "foo"
    assert items[0].source == "user"


def test_preset_library_get_returns_content(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {"mach": [1, 2]}, "conditions": []})
    content = lib.get("foo")
    assert content["sweeps"]["mach"] == [1, 2]


def test_preset_library_duplicate_save_raises(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    with pytest.raises(FileExistsError):
        lib.save("foo", {"sweeps": {}})


def test_preset_library_duplicate_save_with_overwrite(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    lib.save("foo", {"sweeps": {"x": [1]}}, overwrite=True)
    assert lib.get("foo")["sweeps"] == {"x": [1]}


def test_preset_library_delete_user(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("foo", {"sweeps": {}})
    lib.delete("foo")
    assert lib.list() == []


def test_preset_library_team_source_marked(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    team = tmp_path / "team"
    team.mkdir()
    (team / "bar.yaml").write_text("sweeps: {}\nconditions: []\n", encoding="utf-8")
    lib = PresetLibrary(user_dir=tmp_path / "user", team_dirs=[team])
    items = lib.list()
    assert any(i.name == "bar" and i.source.startswith("team:") for i in items)


def test_preset_library_delete_team_raises(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    team = tmp_path / "team"
    team.mkdir()
    (team / "bar.yaml").write_text("sweeps: {}\n", encoding="utf-8")
    lib = PresetLibrary(user_dir=tmp_path / "user", team_dirs=[team])
    with pytest.raises(PermissionError):
        lib.delete("team:bar")


def test_preset_library_search_by_tag(tmp_path):
    from inp_tool_gui.preset_library import PresetLibrary
    lib = PresetLibrary(user_dir=tmp_path, team_dirs=[])
    lib.save("a", {"sweeps": {}, "tags": ["baseline", "low-speed"]})
    lib.save("b", {"sweeps": {}, "tags": ["transonic"]})
    results = lib.search("low")
    assert [r.name for r in results] == ["a"]
