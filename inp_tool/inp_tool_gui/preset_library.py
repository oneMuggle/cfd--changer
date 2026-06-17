"""Preset 库:用户级 + 团队级,纯文件系统,无 Qt 依赖。"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml


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
