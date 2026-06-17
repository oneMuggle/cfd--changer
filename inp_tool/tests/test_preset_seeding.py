"""seed_default_presets 单测 + 默认 preset 内容 smoke test。

覆盖:
- 首次启动:用户目录为空 → 复制全部 3 个内置 preset。
- 二次启动:用户已有部分 preset → 保留用户文件,只补缺失的。
- 种子 yaml 内容 smoke:每个文件能 pkgutil.get_data 出来,基本字段齐全。
"""
from pathlib import Path
import pkgutil

import yaml


# ---- 行为测试 ------------------------------------------------------------

def test_seed_default_presets_copies_three(tmp_path):
    """空用户目录 → 复制 3 个内置 preset。"""
    from inp_tool_gui.preset_library import seed_default_presets
    copied = seed_default_presets(tmp_path / "presets")
    assert len(copied) == 3
    assert (tmp_path / "presets" / "low-speed.yaml").exists()
    assert (tmp_path / "presets" / "transonic.yaml").exists()
    assert (tmp_path / "presets" / "high-speed.yaml").exists()


def test_seed_default_presets_skips_existing(tmp_path):
    """已存在的 preset 不覆盖,且不计入 copied。"""
    from inp_tool_gui.preset_library import seed_default_presets
    target = tmp_path / "presets"
    target.mkdir(parents=True)
    (target / "low-speed.yaml").write_text("user: modified\n", encoding="utf-8")

    copied = seed_default_presets(target)

    # 用户自定义的低速文件应保留(未被覆盖)
    assert (target / "low-speed.yaml").read_text(encoding="utf-8") == "user: modified\n"
    # 只复制缺失的(transonic + high-speed)
    assert len(copied) == 2
    assert (target / "transonic.yaml").exists()
    assert (target / "high-speed.yaml").exists()


def test_seed_default_presets_creates_missing_dir(tmp_path):
    """user_preset_dir 不存在时应自动创建(parents=True)。"""
    from inp_tool_gui.preset_library import seed_default_presets
    deep = tmp_path / "a" / "b" / "c" / "presets"
    assert not deep.exists()
    seed_default_presets(deep)
    assert deep.is_dir()
    assert (deep / "low-speed.yaml").exists()


def test_seed_default_presets_idempotent(tmp_path):
    """连续调用两次,第二次应返回空(copied=0),不重复写。"""
    from inp_tool_gui.preset_library import seed_default_presets
    target = tmp_path / "presets"
    first = seed_default_presets(target)
    second = seed_default_presets(target)
    assert len(first) == 3
    assert second == []
    # 文件总数仍为 3(没有被复制 6 份)
    assert len(list(target.glob("*.yaml"))) == 3


def test_seeded_files_round_trip_via_yaml(tmp_path):
    """复制出来的 yaml 必须能被 yaml.safe_load 解析,且 version=2。"""
    from inp_tool_gui.preset_library import seed_default_presets
    target = tmp_path / "presets"
    seed_default_presets(target)
    for name in ("low-speed", "transonic", "high-speed"):
        with (target / f"{name}.yaml").open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert data["version"] == 2
        assert data["name"].endswith(name) or name in data["name"]
        assert isinstance(data["sweeps"], dict)
        assert isinstance(data["conditions"], list)


# ---- 内容 smoke test -----------------------------------------------------

def test_low_speed_yaml_content():
    """low-speed.yaml 应能被 pkgutil 从包内资源读出,且含 low-speed/mach 关键字。"""
    data = pkgutil.get_data("inp_tool_gui.resources", "default_presets/low-speed.yaml")
    assert data is not None, "low-speed.yaml missing from package resources"
    text = data.decode("utf-8")
    assert "low-speed" in text
    assert "mach" in text


def test_transonic_yaml_content():
    """transonic.yaml 内容 smoke。"""
    text = pkgutil.get_data("inp_tool_gui.resources", "default_presets/transonic.yaml").decode("utf-8")
    assert "transonic" in text
    # 跨音速应至少包含一个 condition
    assert "conditions" in text
    assert "when" in text


def test_high_speed_yaml_content():
    """high-speed.yaml 内容 smoke。"""
    text = pkgutil.get_data("inp_tool_gui.resources", "default_presets/high-speed.yaml").decode("utf-8")
    assert "high-speed" in text
    assert "mach" in text


def test_transonic_has_two_conditions():
    """transonic.yaml 必须有 2 个 condition(亚/超音速各一个)。"""
    data = pkgutil.get_data("inp_tool_gui.resources", "default_presets/transonic.yaml")
    parsed = yaml.safe_load(data)
    conds = parsed["conditions"]
    assert len(conds) == 2
    # 至少有一个 when 涉及 mach
    assert all("mach" in c["when"] for c in conds)
