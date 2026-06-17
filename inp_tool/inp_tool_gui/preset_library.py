"""Preset 库:用户级 + 团队级,纯文件系统,无 Qt 依赖。"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pkgutil
import yaml

# 打包在 inp_tool_gui.resources.default_presets 下的种子文件目录(package 内 data path)。
# 在用户首次启动 GUI 时由 seed_default_presets() 拷到 ~/.config/cfd--changer/presets/。
_DEFAULT_PRESETS_PKG = "inp_tool_gui.resources.default_presets"


@dataclass(frozen=True)
class PresetMeta:
    name: str
    source: str        # "user" 或 "team:<dir_name>"
    tags: Tuple[str, ...] = ()
    path: Optional[Path] = None


class PresetLibrary:
    def __init__(self, user_dir: Path, team_dirs: List[Path]) -> None:
        self.user_dir = Path(user_dir)
        self.team_dirs = [Path(d) for d in team_dirs]

    def list(self) -> List[PresetMeta]:
        out: List[PresetMeta] = []
        if self.user_dir.exists():
            for p in sorted(self.user_dir.glob("*.yaml")):
                meta = self._meta_from(p, source="user")
                if meta:
                    out.append(meta)
        for team in self.team_dirs:
            if not team.exists():
                continue
            for p in sorted(team.glob("*.yaml")):
                meta = self._meta_from(p, source=f"team:{team.name}")
                if meta:
                    out.append(meta)
        return out

    def get(self, ref: str) -> Dict[str, Any]:
        path = self._resolve_path(ref)
        if path is None:
            raise KeyError(f"preset {ref!r} not found")
        with path.open(encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save(self, name: str, content: Dict[str, Any], *, overwrite: bool = False) -> Path:
        self.user_dir.mkdir(parents=True, exist_ok=True)
        path = self.user_dir / f"{name}.yaml"
        if path.exists() and not overwrite:
            raise FileExistsError(f"preset {name!r} already exists at {path}")
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(content, f, allow_unicode=True, sort_keys=False)
        return path

    def delete(self, ref: str) -> None:
        if ref.startswith("team:"):
            raise PermissionError("cannot delete team preset via PresetLibrary")
        path = self._resolve_path(ref)
        if path is None or not path.exists():
            raise KeyError(f"preset {ref!r} not found")
        path.unlink()

    def search(self, query: str) -> List[PresetMeta]:
        q = query.lower()
        return [
            m for m in self.list()
            if q in m.name.lower() or any(q in t.lower() for t in m.tags)
        ]

    def _meta_from(self, path: Path, source: str) -> Optional[PresetMeta]:
        try:
            with path.open(encoding="utf-8") as f:
                content = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return None
        return PresetMeta(
            name=path.stem,
            source=source,
            tags=tuple(content.get("tags", [])),
            path=path,
        )

    def _resolve_path(self, ref: str) -> Optional[Path]:
        if ref.startswith("team:"):
            name = ref[len("team:"):]
            for team in self.team_dirs:
                p = team / f"{name}.yaml"
                if p.exists():
                    return p
            return None
        p = self.user_dir / f"{ref}.yaml"
        return p if p.exists() else None


# 模块内置的种子 preset 文件名清单(必须在 inp_tool_gui.resources.default_presets 下存在)。
# 增加新默认 preset 时同步更新这里,否则不会自动拷到用户目录。
_BUILTIN_PRESETS: Tuple[str, ...] = ("low-speed.yaml", "transonic.yaml", "high-speed.yaml")


def seed_default_presets(user_preset_dir: Path) -> List[Path]:
    """把包内置的 3 个默认 preset 拷到用户目录(不覆盖已有文件)。

    用途:GUI 启动时若 ``~/.config/cfd--changer/presets/`` 不存在或为空,
    调用本函数把 ``inp_tool_gui.resources.default_presets`` 下的种子 yaml
    拷过去作为初始内容。已有同名文件保留,绝不覆盖(避免破坏用户修改)。

    Args:
        user_preset_dir: 用户 preset 目录(尚不存在也可,会自动创建)。

    Returns:
        本次实际新写入的文件路径列表(已存在的不会出现在结果里)。

    Notes:
        - 使用 ``pkgutil.get_data`` 而不是 ``importlib.resources.files``,
          因为 ``files()`` 是 3.9+ API,而本项目要求 Python 3.8 兼容。
        - ``pkgutil.get_data`` 在 zipapp/PyInstaller 冻结包下也工作良好。
    """
    target_dir = Path(user_preset_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    copied: List[Path] = []
    for name in _BUILTIN_PRESETS:
        target = target_dir / name
        if target.exists():
            # 用户已有同名文件,保留不动(避免覆盖用户自定义)。
            continue
        data = pkgutil.get_data(_DEFAULT_PRESETS_PKG, name)
        if data is None:
            # 包内种子缺失:跳过(不抛错,保持 GUI 启动容错)。
            continue
        target.write_bytes(data)
        copied.append(target)
    return copied
