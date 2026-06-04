"""audit_docs.py — 审计 docs/ 下的 markdown 文件

检查项:
  1. 内部相对链接(.md 文件)是否指向真实存在的文件
  2. 文中 v0.X.Y 版本号引用是否与 inp_tool/__init__.py 一致

输出: 每章节的 pass/fail 表格 + 总计
退出码: 0 = 全过, 1 = 有问题
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIRS = [
    REPO_ROOT / "docs" / "user-manual",
    REPO_ROOT / "docs" / "technical",
]
INP_VERSION_FILE = REPO_ROOT / "inp_tool" / "inp_tool" / "__init__.py"
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
VERSION_RE = re.compile(r"\bv0\.\d+\.\d+\b")

# 表格列宽(可按需调整)
COL_FILE_WIDTH = 42
COL_NUM_WIDTH = 13


def find_markdown_files():
    for d in DOCS_DIRS:
        if d.exists():
            yield from sorted(d.glob("*.md"))


def _read_text(path: Path) -> str:
    """读取文件,容错处理。失败返回空串(并把失败当作 issue 上报)。"""
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        print(f"[WARN] 读取失败 {path}: {e}", file=sys.stderr)
        return ""


def check_internal_links(md_path: Path) -> list:
    """返回 broken_list - [link_target, ...]"""
    text = _read_text(md_path)
    broken = []
    for m in LINK_RE.finditer(text):
        link = m.group(2).split("#")[0]  # 去锚点
        if not link or link.startswith("http") or link.startswith("mailto:"):
            continue
        if not link.endswith(".md"):
            continue
        target = (md_path.parent / link).resolve()
        if not target.exists():
            broken.append(link)
    return broken


def check_version_references(md_path: Path, actual_version: str) -> list:
    """返回 mismatched_list - 与 actual_version 不一致的版本号引用。

    actual_version 由 main() 读一次 __init__.py 后传入,避免每文件重复磁盘读。
    """
    if not actual_version:
        return []
    text = _read_text(md_path)
    refs = set(VERSION_RE.findall(text))
    return sorted(r for r in refs if r != actual_version)


def _resolve_inp_version() -> str:
    """读 __init__.py 一次,返回形如 'v0.4.0' 的字符串;失败返回空串。"""
    if not INP_VERSION_FILE.exists():
        return ""
    text = _read_text(INP_VERSION_FILE)
    m = re.search(r"__version__\s*=\s*['\"]v?([0-9.]+)['\"]", text)
    return f"v{m.group(1)}" if m else ""


def audit_one(md_path: Path, actual_version: str) -> dict:
    broken = check_internal_links(md_path)
    mismatched = check_version_references(md_path, actual_version)
    return {
        "file": md_path.name,
        "broken": broken,
        "mismatched": mismatched,
    }


def main():
    files = list(find_markdown_files())
    actual_version = _resolve_inp_version()
    print(f"=== 审计 {len(files)} 个 markdown 文件 (实际版本: {actual_version or 'unknown'}) ===\n")
    rows = [audit_one(f, actual_version) for f in files]
    header = f"{'file':<{COL_FILE_WIDTH}} {'broken_links':>{COL_NUM_WIDTH}} {'ver_mismatch':>{COL_NUM_WIDTH}}"
    sep = "-" * (COL_FILE_WIDTH + 2 * COL_NUM_WIDTH + 2)
    print(header)
    print(sep)
    for r in rows:
        bl = len(r["broken"])
        vm = len(r["mismatched"])
        marker = "X" if (bl or vm) else "ok"
        print(f"{r['file']:<{COL_FILE_WIDTH}} {bl:>{COL_NUM_WIDTH}} {vm:>{COL_NUM_WIDTH}} {marker}")
    total_broken = sum(len(r["broken"]) for r in rows)
    total_ver = sum(len(r["mismatched"]) for r in rows)
    print(sep)
    print(f"{'TOTAL':<{COL_FILE_WIDTH}} {total_broken:>{COL_NUM_WIDTH}} {total_ver:>{COL_NUM_WIDTH}}")
    if total_broken:
        print("\n--- 失效链接详情 ---")
        for r in rows:
            for link in r["broken"]:
                print(f"  {r['file']}: -> {link}")
    if total_ver:
        print("\n--- 版本号不一致详情 ---")
        for r in rows:
            for v in r["mismatched"]:
                print(f"  {r['file']}: {v}")
    return 0 if (total_broken == 0 and total_ver == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
