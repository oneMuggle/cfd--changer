"""``PostprocessController`` — GUI 层后处理业务逻辑(PySide2-free)。

包装 :mod:`inp_tool.postprocess` 子包,提供 GUI 友好 API:
- :meth:`set_geometry` / :meth:`set_op_ibd`
- :meth:`extract` / :meth:`convergence` / :meth:`report` / :meth:`plot` /
  :meth:`run_all` 5 个方法对应 cli_post 5 个子命令

**不**依赖 PySide2,纯 Python;widget 层只调此 controller。

参考范式:``inp_tool_gui/controllers/sweep_controller.py``
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from inp_tool.postprocess.convergence import (
    DEFAULT_CV_THRESHOLD,
    DEFAULT_MIN_WINDOW,
    DEFAULT_WINDOW_FRACTION,
    ConvergenceWindow,
    compute_convergence,
    format_convergence_report,
)
from inp_tool.postprocess.forces import (
    ForceReport,
    ReferenceGeometry,
    summarize_forces,
)
from inp_tool.postprocess.info1 import read_info1


class PostprocessController:
    """后处理控制器。

    使用范式::

        c = PostprocessController()
        c.set_geometry(sref=1.0, lref=1.0)
        c.set_op_ibd([1, 2])
        report = c.extract([Path("case_01"), Path("case_02")])
        # ... 或一站式
        result = c.run_all([Path("case_01")], out_dir=Path("out"))
    """

    def __init__(self) -> None:
        self._sref: float = 1.0
        self._lref: float = 1.0
        self._xref: float = 0.0
        self._yref: float = 0.0
        self._zref: float = 0.0
        self._op_ibd: List[int] = []
        self._xcg: float = 0.0

    # ---- 几何 ----

    @property
    def sref(self) -> float:
        return self._sref

    @property
    def lref(self) -> float:
        return self._lref

    @property
    def xref(self) -> float:
        return self._xref

    @property
    def yref(self) -> float:
        return self._yref

    @property
    def zref(self) -> float:
        return self._zref

    @property
    def xcg(self) -> float:
        return self._xcg

    def set_geometry(
        self,
        sref: Optional[float] = None,
        lref: Optional[float] = None,
        xref: Optional[float] = None,
        yref: Optional[float] = None,
        zref: Optional[float] = None,
        xcg: Optional[float] = None,
    ) -> None:
        """部分更新参考几何(只设非 None 字段)。"""
        if sref is not None:
            self._sref = float(sref)
        if lref is not None:
            self._lref = float(lref)
        if xref is not None:
            self._xref = float(xref)
        if yref is not None:
            self._yref = float(yref)
        if zref is not None:
            self._zref = float(zref)
        if xcg is not None:
            self._xcg = float(xcg)

    def _build_ref_geom(self) -> ReferenceGeometry:
        return ReferenceGeometry(
            Sref=self._sref, Lref=self._lref,
            Xref=self._xref, Yref=self._yref, Zref=self._zref,
        )

    # ---- op_ibd ----

    @property
    def op_ibd(self) -> List[int]:
        return list(self._op_ibd)

    def set_op_ibd(self, value: Union[str, Sequence[int]]) -> None:
        """设积分边界 op 列表。

        - ``"1,2,3"`` 字符串(逗号分隔)
        - ``[1, 2, 3]`` 整数 list
        - 空串 / 空 list → ``ValueError``
        """
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("op_ibd cannot be empty")
            parts = [p.strip() for p in stripped.split(",") if p.strip()]
            try:
                self._op_ibd = [int(p) for p in parts]
            except ValueError as e:
                raise ValueError(
                    f"op_ibd must be comma-separated integers, got: {value!r}"
                ) from e
        else:
            ids = list(value)
            if not ids:
                raise ValueError("op_ibd cannot be empty")
            self._op_ibd = [int(x) for x in ids]

    # ---- extract ----

    def extract(self, case_dirs: Sequence[Union[str, Path]]) -> ForceReport:
        """提取气动力 + 系数,返回 :class:`ForceReport`。"""
        return summarize_forces(
            [Path(c) for c in case_dirs],
            op_ibd=self._op_ibd,
            ref_geom=self._build_ref_geom(),
            xcg=self._xcg,
        )

    # ---- convergence ----

    def convergence(
        self,
        case_dirs: Sequence[Union[str, Path]],
        threshold: float = DEFAULT_CV_THRESHOLD,
        fraction: float = DEFAULT_WINDOW_FRACTION,
        min_window: int = DEFAULT_MIN_WINDOW,
    ) -> List[Tuple[str, Optional[ConvergenceWindow]]]:
        """对每个 case 算 CV 收敛性,返回 ``[(case_name, window or None), ...]``。"""
        results: List[Tuple[str, Optional[ConvergenceWindow]]] = []
        for cd in case_dirs:
            d = Path(cd)
            info1 = d / "mcfd.info1"
            if not info1.is_file():
                results.append((d.name, None))
                continue
            steps = read_info1(info1, self._op_ibd)
            window = compute_convergence(
                steps,
                threshold=threshold,
                fraction=fraction,
                min_window=min_window,
            )
            results.append((d.name, window))
        return results

    def format_convergence_report(
        self,
        results: Sequence[Tuple[str, Optional[ConvergenceWindow]]],
        threshold: float = DEFAULT_CV_THRESHOLD,
        fraction: float = DEFAULT_WINDOW_FRACTION,
    ) -> str:
        """委托给底层 :func:`format_convergence_report`。"""
        return format_convergence_report(results, threshold, fraction)

    # ---- report ([post]) ----

    def report(
        self,
        case_dirs: Sequence[Union[str, Path]],
        out_path: Union[str, Path],
    ) -> Path:
        """生成 Excel 报告。需 [post] extras;缺包抛 ``ImportError``。"""
        from inp_tool.postprocess.report import write_excel
        force_report = self.extract(case_dirs)
        return write_excel(force_report, Path(out_path))

    # ---- plot ([post]) ----

    def plot(
        self,
        case_dirs: Sequence[Union[str, Path]],
        out_path: Union[str, Path],
        threshold: float = DEFAULT_CV_THRESHOLD,
        fraction: float = DEFAULT_WINDOW_FRACTION,
        min_window: int = DEFAULT_MIN_WINDOW,
    ) -> Path:
        """生成收敛曲线 png。需 [post] extras;缺包抛 ``ImportError``。"""
        from inp_tool.postprocess.plot import save_convergence_plot
        plot_data = []
        for cd in case_dirs:
            d = Path(cd)
            info1 = d / "mcfd.info1"
            if not info1.is_file():
                plot_data.append((d.name, None, None))
                continue
            steps = read_info1(info1, self._op_ibd)
            window = compute_convergence(
                steps,
                threshold=threshold,
                fraction=fraction,
                min_window=min_window,
            )
            plot_data.append((d.name, window, steps))
        return save_convergence_plot(plot_data, Path(out_path))

    # ---- run_all ----

    def run_all(
        self,
        case_dirs: Sequence[Union[str, Path]],
        out_dir: Union[str, Path],
        threshold: float = DEFAULT_CV_THRESHOLD,
        fraction: float = DEFAULT_WINDOW_FRACTION,
        min_window: int = DEFAULT_MIN_WINDOW,
    ) -> Dict[str, Any]:
        """一站式:extract + convergence + (report+plot 若 [post] 装了)。

        返回字典::

            {
                'report': ForceReport,
                'convergence': [(case_name, window or None), ...],
                'txt': Path,                  # convergence_report.txt
                'xlsx': Optional[Path],       # ForceReport.xlsx(若 openpyxl 装了)
                'png': Optional[Path],        # convergence_plot.png(若 matplotlib 装了)
            }
        """
        out_dir_p = Path(out_dir)
        out_dir_p.mkdir(parents=True, exist_ok=True)

        # 1. extract
        report = self.extract(case_dirs)

        # 2. convergence
        conv_results = self.convergence(
            case_dirs,
            threshold=threshold,
            fraction=fraction,
            min_window=min_window,
        )
        conv_text = self.format_convergence_report(
            conv_results, threshold=threshold, fraction=fraction,
        )
        txt_path = out_dir_p / "convergence_report.txt"
        txt_path.write_text(conv_text, encoding="utf-8")

        # 3. xlsx(可选)
        xlsx_path: Optional[Path] = None
        try:
            from inp_tool.postprocess.report import write_excel
            xlsx_path = write_excel(report, out_dir_p / "ForceReport.xlsx")
        except ImportError:
            pass

        # 4. png(可选)
        png_path: Optional[Path] = None
        try:
            from inp_tool.postprocess.plot import save_convergence_plot
            plot_data = []
            for cd, (case_name, window) in zip(case_dirs, conv_results):
                d = Path(cd)
                info1 = d / "mcfd.info1"
                if info1.is_file():
                    steps = read_info1(info1, self._op_ibd)
                else:
                    steps = None
                plot_data.append((case_name, window, steps))
            png_path = save_convergence_plot(
                plot_data, out_dir_p / "convergence_plot.png",
            )
        except ImportError:
            pass

        return {
            "report": report,
            "convergence": conv_results,
            "txt": txt_path,
            "xlsx": xlsx_path,
            "png": png_path,
        }
