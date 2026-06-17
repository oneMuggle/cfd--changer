"""SweepControllerV2 单测(load/dump YAML v2 + v1 迁移)。"""
from pathlib import Path
import pytest


def test_load_yaml_v2_basic(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "sweep.yaml"
    yaml_file.write_text(
        "version: 2\n"
        "template: t.inp\n"
        "output_dir: /out\n"
        "naming: case\n"
        "sweeps:\n"
        "  turbulence: [sst, kw]\n",
        encoding="utf-8",
    )
    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(yaml_file)
    assert store.template == "t.inp"
    assert "turbulence" in store.sweeps


def test_load_yaml_v1_auto_upgrades(tmp_path):
    """无 version 字段 → 自动当 v1 处理并升级。"""
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "old.yaml"
    yaml_file.write_text(
        "template: t.inp\n"
        "output_dir: /out\n"
        "sweeps:\n"
        "  alpha: [0, 1, 2]\n",
        encoding="utf-8",
    )
    ctrl = SweepControllerV2()
    store = ctrl.load_yaml(yaml_file)
    assert store.sweeps["alpha"].kind == "explicit_list"
    assert store.conditions == ()


def test_dump_yaml_v2_roundtrip(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    from inp_tool_gui.models.config_store import ConfigStore, AxisSpec
    ctrl = SweepControllerV2()
    store = ConfigStore(
        template="t.inp", output_dir="/out", naming="case_{x}",
        preset_ref=None,
        sweeps={"mach": AxisSpec(kind="range", range_min=0, range_max=2, range_step=1)},
        conditions=(),
    )
    out = tmp_path / "out.yaml"
    ctrl.dump_yaml(store, out)
    loaded = ctrl.load_yaml(out)
    assert loaded.sweeps["mach"].kind == "range"
    assert loaded.naming == "case_{x}"


def test_load_yaml_invalid_version_raises(tmp_path):
    from inp_tool_gui.controllers.sweep_controller_v2 import SweepControllerV2
    yaml_file = tmp_path / "future.yaml"
    yaml_file.write_text("version: 99\ntemplate: t\n", encoding="utf-8")
    ctrl = SweepControllerV2()
    with pytest.raises(ValueError, match="schema"):
        ctrl.load_yaml(yaml_file)
