"""SweepControllerV2:加载/保存/迁移 sweep YAML(v2 + v1 自动升级)。"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from inp_tool_gui.models.config_store import AxisSpec, ConfigStore


SUPPORTED_VERSIONS = (1, 2)


class SweepControllerV2:
    """v2 sweep YAML 控制器:load/dump + v1 自动升级。

    Conditions 序列化在 Phase 4 GUI 集成时再连,目前 round-trip 不写回 conditions。
    """

    def load_yaml(self, path: Union[str, Path]) -> ConfigStore:
        with Path(path).open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return self._parse(data)

    def dump_yaml(self, store: ConfigStore, path: Union[str, Path]) -> None:
        data = self._serialize(store)
        with Path(path).open("w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _parse(self, data: Dict[str, Any]) -> ConfigStore:
        version = data.get("version")
        if version is None:
            data = self._upgrade_v1(data)
        elif version not in SUPPORTED_VERSIONS:
            raise ValueError(
                f"sweep YAML schema version {version} not supported; "
                f"supported: {SUPPORTED_VERSIONS}"
            )
        return ConfigStore(
            template=data["template"],
            output_dir=data["output_dir"],
            naming=data.get("naming", "case"),
            preset_ref=data.get("preset"),
            sweeps=self._parse_sweeps(data.get("sweeps", {})),
            conditions=(),  # condition 解析待 Phase 4 GUI 集成时再连
        )

    def _serialize(self, store: ConfigStore) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "version": 2,
            "template": store.template,
            "output_dir": store.output_dir,
            "naming": store.naming,
            "sweeps": self._serialize_sweeps(store.sweeps),
        }
        if store.preset_ref:
            d["preset"] = store.preset_ref
        # conditions 序列化在 Phase 4 GUI 集成时再连
        return d

    @staticmethod
    def _upgrade_v1(v1: Dict[str, Any]) -> Dict[str, Any]:
        v2 = dict(v1)
        v2["version"] = 2
        v2.setdefault("conditions", [])
        v2.setdefault("preset", None)
        return v2

    @staticmethod
    def _parse_sweeps(raw: Dict[str, Any]) -> Dict[str, AxisSpec]:
        out: Dict[str, AxisSpec] = {}
        for key, val in raw.items():
            if isinstance(val, dict) and "range" in val:
                rng = val["range"]
                if len(rng) == 3:
                    out[key] = AxisSpec(
                        kind="range",
                        range_min=float(rng[0]),
                        range_max=float(rng[1]),
                        range_step=float(rng[2]),
                    )
                elif len(rng) == 2:
                    # linspace 预留
                    out[key] = AxisSpec(
                        kind="linspace",
                        range_min=float(rng[0]),
                        range_max=float(rng[1]),
                    )
                else:
                    raise ValueError(f"range must have 2 or 3 elements, got {len(rng)}")
            elif isinstance(val, str):
                vals = tuple(x.strip() for x in val.split(",") if x.strip())
                out[key] = AxisSpec(kind="csv_str", values=vals)
            elif isinstance(val, list):
                vals = tuple(val)
                kind = "enum_subset" if all(isinstance(v, str) for v in vals) else "explicit_list"
                out[key] = AxisSpec(kind=kind, values=vals)
            else:
                raise ValueError(
                    f"unsupported sweep value type for axis {key!r}: {type(val)}"
                )
        return out

    @staticmethod
    def _serialize_sweeps(sweeps: Dict[str, AxisSpec]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for key, spec in sweeps.items():
            if spec.kind == "range":
                out[key] = {"range": [spec.range_min, spec.range_max, spec.range_step]}
            elif spec.kind in ("enum_subset", "explicit_list"):
                out[key] = list(spec.values)
            elif spec.kind == "csv_str":
                out[key] = ", ".join(str(v) for v in spec.values)
            else:
                raise ValueError(
                    f"unsupported AxisSpec.kind {spec.kind!r} for serialize"
                )
        return out
