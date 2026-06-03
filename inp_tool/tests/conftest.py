"""Pytest fixtures and path setup for inp_tool tests.

- 把 inp_tool/ 包根加到 sys.path,让测试可以 `import inp_tool`
- 提供 examples_dir / sample_inp / external_inp_dir 三个 session-scope fixture
"""
import sys
from pathlib import Path

import pytest

# tests/ 的父目录就是包根
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

EXAMPLES_DIR = _PKG_ROOT / "examples"
# 外部 54 样本真实回归测试用;目录不存在时使用此 fixture 的测试自动 skip
EXTERNAL_INP_DIR = Path(r"E:\softwareData\edge\download\inp")


@pytest.fixture(scope="session")
def examples_dir() -> Path:
    """inp_tool/examples/ 目录路径。"""
    return EXAMPLES_DIR


@pytest.fixture(scope="session")
def sample_inp(examples_dir: Path) -> Path:
    """examples/ 下的示例 .inp(优先 mcfd_v2_modified.inp)。"""
    for name in ("mcfd_v2_modified.inp", "mcfd_modified.inp"):
        p = examples_dir / name
        if p.exists():
            return p
    inps = sorted(examples_dir.glob("*.inp"))
    if not inps:
        pytest.skip(f"no .inp sample found in {examples_dir}")
    return inps[0]


@pytest.fixture(scope="session")
def external_inp_dir() -> Path:
    """外部 54 样本真实回归目录。
    若不存在,使用此 fixture 的测试自动 skip(不报错)。
    """
    if not EXTERNAL_INP_DIR.is_dir():
        pytest.skip(f"external INP_DIR not found: {EXTERNAL_INP_DIR}")
    return EXTERNAL_INP_DIR
