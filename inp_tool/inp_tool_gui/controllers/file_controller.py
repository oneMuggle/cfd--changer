"""FileController:GUI 文件 I/O 业务逻辑。

包装 :mod:`inp_tool.parser` 与 :mod:`inp_tool.writer`,提供 GUI 友好 API:
- :meth:`open` / :meth:`save` / :attr:`current_path` / :attr:`is_open`
- :meth:`set_value` / :meth:`get_value` — 字段改写 / 读取

**不**依赖 PySide2,纯 Python;widget 层只调此 controller,不直接碰 inp_tool core。

典型用法::

    fc = FileController()
    fc.open("mcfd.inp")
    if fc.set_value("physics", "reftem", 300.0):
        fc.save()  # 写回原路径
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Union

from inp_tool import parser, writer
from inp_tool.model import Block, InpFile


@dataclass
class CaseValidationIssue:
    code: str
    message: str
    severity: str  # "error" | "warning"


@dataclass
class CaseValidation:
    ok: bool
    issues: List["CaseValidationIssue"] = field(default_factory=list)


class CaseValidationError(Exception):
    """算例目录不完整时抛的异常。"""

    def __init__(self, validation: "CaseValidation") -> None:
        self.validation = validation
        msgs = ["[{}] {}".format(i.code, i.message) for i in validation.issues
                if i.severity == "error"]
        super().__init__("算例完整性检查失败:\n" + "\n".join(msgs))


class FileController:
    """GUI 的文件 I/O 控制器。"""

    def __init__(self) -> None:
        self._inp: Optional[InpFile] = None
        self._path: Optional[Path] = None
        self._case_dir: Optional[Path] = None
        self._case_validation: Optional["CaseValidation"] = None

    # --- 状态查询 --------------------------------------------------------

    @property
    def inp(self) -> Optional[InpFile]:
        """当前打开的 :class:`InpFile`;未打开返回 :data:`None`。"""
        return self._inp

    @property
    def current_path(self) -> Optional[Path]:
        """当前文件路径;未打开返回 :data:`None`。"""
        return self._path

    @property
    def is_open(self) -> bool:
        """是否已成功 open 一个文件。"""
        return self._inp is not None

    # --- open / save -----------------------------------------------------

    def open(self, path: Union[str, Path]) -> InpFile:
        """打开 ``path``(.inp 文件),返回 :class:`InpFile`。

        抛 :class:`FileNotFoundError` 或 :class:`ParseError`(取决于 inp_tool parser)。
        """
        path = Path(path)
        self._inp = parser.parse_file(str(path))
        self._path = path
        return self._inp

    def save(self, path: Optional[Union[str, Path]] = None) -> None:
        """写入 :class:`InpFile`。

        - ``path`` 为 None → 写回 ``current_path``
        - ``path`` 非 None → 写入新路径并更新 ``current_path``

        未打开文件时抛 :class:`RuntimeError`;无 ``current_path`` 且无 ``path`` 也抛。
        """
        if self._inp is None:
            raise RuntimeError("没有打开的文件,无法 save")
        if path is None and self._path is None:
            raise RuntimeError("save 需要显式 path 或已 open 的文件")
        out = Path(path) if path is not None else self._path
        assert out is not None  # type-check 提示
        writer.write(self._inp, str(out))
        self._path = out

    # --- 字段读写 -------------------------------------------------------

    def _find_block(
        self, block_name: str, block_idx: int = 0
    ) -> Optional[Block]:
        """找第 ``block_idx`` 个名为 ``block_name`` 的 block;找不到返回 None。"""
        if self._inp is None:
            return None
        matches: List[Block] = [
            b for b in self._inp.block_list if b.name == block_name
        ]
        if not matches or block_idx >= len(matches) or block_idx < 0:
            return None
        return matches[block_idx]

    def get_value(
        self, block_name: str, keyword: str, *, block_idx: int = 0
    ) -> Any:
        """取 block 中某 keyword 的第一个 value 的 typed 值。

        block 或 keyword 不存在时返回 :data:`None`(不抛)。
        """
        block = self._find_block(block_name, block_idx)
        if block is None:
            return None
        stmt = block.get_stmt(keyword)
        if stmt is None:
            return None
        values = stmt.all_values()
        if not values:
            return None
        return values[0].typed

    def set_value(
        self,
        block_name: str,
        keyword: str,
        value: Any,
        *,
        block_idx: int = 0,
    ) -> bool:
        """改或追加某 block 的某 keyword 的值。

        - block 不存在 → 返回 :data:`False`(不做任何修改)
        - block 存在,keyword 存在 → :meth:`Block.set` 修改
        - block 存在,keyword 不存在 → :meth:`Block.append` 追加

        返回 :data:`True` 表示成功修改或追加。
        """
        if self._inp is None:
            raise RuntimeError("没有打开的文件,无法 set_value")
        block = self._find_block(block_name, block_idx)
        if block is None:
            return False
        if not block.set(keyword, value):
            block.append(keyword, value)
        return True

    # --- 文件夹模式(算例目录) -----------------------------------------

    @property
    def current_case_dir(self) -> Optional[Path]:
        """当前打开的算例目录;未打开算例目录时返回 :data:`None`。"""
        return self._case_dir

    @property
    def case_validation(self) -> Optional["CaseValidation"]:
        """最后一次算例目录校验结果;未跑过 :meth:`open_case_dir` 时返回 :data:`None`。"""
        return self._case_validation

    def open_case_dir(self, path: Union[str, Path]) -> InpFile:
        """打开一个完整算例目录(必须是含 mcfd.inp 的目录)。

        - ``path`` 不是目录 → 抛 :class:`CaseValidationError`
        - 缺 ``mcfd.inp`` → 抛 :class:`CaseValidationError`
        - 缺 ``*.pbs`` / 几何文件 → 只在 :attr:`case_validation` 里记 warning,不抛
        - 成功 → 返回 :class:`InpFile`,并设 :attr:`current_case_dir` /
          :attr:`case_validation`
        """
        p = Path(path)
        if not p.is_dir():
            raise CaseValidationError(CaseValidation(
                ok=False, issues=[
                    CaseValidationIssue(
                        "not_a_dir", "{} 不是目录".format(p), "error"),
                ]))
        validation = self._validate_case_dir(p)
        errors = [i for i in validation.issues if i.severity == "error"]
        if errors:
            raise CaseValidationError(validation)
        try:
            self._inp = parser.parse_file(str(p / "mcfd.inp"))
        except Exception as e:
            validation.issues.append(CaseValidationIssue(
                "parse_error", str(e), "error"))
            raise CaseValidationError(validation)
        self._path = p / "mcfd.inp"
        self._case_dir = p
        self._case_validation = validation
        return self._inp

    def _validate_case_dir(self, p: Path) -> "CaseValidation":
        """检查 ``p`` 是不是一个完整算例目录。

        检查项:
        - ``mcfd.inp`` 必须存在(error)
        - 至少一个 ``*.pbs``(warning)
        - 至少一个 ``*.tri`` 或 ``*.plt``(warning)
        """
        issues: List["CaseValidationIssue"] = []
        inp_path = p / "mcfd.inp"
        if not inp_path.is_file():
            issues.append(CaseValidationIssue(
                "missing_inp", "缺少 mcfd.inp", "error"))
        pbs = list(p.glob("*.pbs"))
        if not pbs:
            issues.append(CaseValidationIssue(
                "missing_pbs", "缺少 PBS 脚本", "warning"))
        geom_files = list(p.glob("*.tri")) + list(p.glob("*.plt"))
        if not geom_files:
            issues.append(CaseValidationIssue(
                "missing_geometry", "缺少几何文件", "warning"))
        return CaseValidation(
            ok=not any(i.severity == "error" for i in issues),
            issues=issues,
        )
