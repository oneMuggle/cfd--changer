"""DiffController:GUI 对比业务逻辑(Phase 5)。

包装 :mod:`inp_tool.diff` 的 :func:`diff` + :class:`DiffReport`,
提供 GUI 友好 API:
- :meth:`load_pair` 加载两个文件,parse + diff
- :attr:`last_report` 最近一次 diff 结果
- :meth:`unified_text` 转 unified diff 字符串(供 QTextBrowser 渲染)
- :meth:`change_count` 变更条数

**不**依赖 PySide2;widget 层只调此 controller。

注:不能 ``import inp_tool.diff as diff_mod`` — 因为 ``inp_tool/__init__.py``
里有 ``from .diff import diff``,把 ``inp_tool.diff`` 名覆盖成了函数。
改为直接 ``from inp_tool.diff import DiffReport, diff as diff_fn`` 避开。
"""
from pathlib import Path
from typing import Optional, Union

from inp_tool import parser
from inp_tool.diff import DiffReport, diff as diff_fn


class DiffController:
    """GUI 的 diff 控制器。"""

    def __init__(self) -> None:
        self._a_path: Optional[Path] = None
        self._b_path: Optional[Path] = None
        self._a_inp = None
        self._b_inp = None
        self._report: Optional[DiffReport] = None

    # --- 状态查询 --------------------------------------------------------

    @property
    def a_path(self) -> Optional[Path]:
        return self._a_path

    @property
    def b_path(self) -> Optional[Path]:
        return self._b_path

    @property
    def last_report(self) -> Optional[DiffReport]:
        return self._report

    @property
    def has_pair(self) -> bool:
        return self._a_inp is not None and self._b_inp is not None

    @property
    def change_count(self) -> int:
        if self._report is None:
            return 0
        return len(self._report.changes)

    # --- 加载 + diff -----------------------------------------------------

    def load_pair(self, a: Union[str, Path], b: Union[str, Path]) -> DiffReport:
        """加载两个文件并 diff。

        任一文件 parse 失败抛 :class:`ParseError`(从 parser)。
        """
        self._a_path = Path(a)
        self._b_path = Path(b)
        self._a_inp = parser.parse_file(str(self._a_path))
        self._b_inp = parser.parse_file(str(self._b_path))
        self._report = diff_fn(self._a_inp, self._b_inp)
        return self._report

    def unified_text(self) -> str:
        """最近报告的 unified diff 字符串。

        未 load_pair 返 ``"(未加载)"``;无变更返 DiffReport.__str__()(即 ``(no changes)``)。
        """
        if self._report is None:
            return "(未加载)"
        return self._report.unified(
            a_path=str(self._a_path) if self._a_path else "a.inp",
            b_path=str(self._b_path) if self._b_path else "b.inp",
        )