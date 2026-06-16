"""SweepController:GUI 批量算例生成的业务逻辑(阶段 5)。

包装 :mod:`inp_tool.sweep` 的 :class:`CaseSweep` + :func:`generate`,
提供 GUI 友好 API:
- :meth:`load_from_dict` / :meth:`load_from_json` / :meth:`load_from_yaml`
- :meth:`preview` (Dry run,只展开不写盘)
- :meth:`run` (实际生成,可选 dry_run)
- :attr:`is_loaded` / :attr:`template` / :attr:`case_count` / :attr:`last_report`

**不**依赖 PySide2,纯 Python;widget 层只调此 controller。
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from inp_tool.sweep import (
    CaseSweep,
    ExplicitCase,
    SweepReport,
    generate as sweep_generate,
)

from inp_tool_gui.widgets import sweep_var_combo  # noqa: E402
from inp_tool_gui.widgets.sweep_var_combo import VarSpec  # noqa: E402


class SweepController:
    """GUI 的 sweep 控制器,包装 :class:`CaseSweep`。"""

    def __init__(self) -> None:
        self._sweep: Optional[CaseSweep] = None
        self._last_report: Optional[SweepReport] = None
        self._var_cache: Dict[Optional[str], List[VarSpec]] = {}

    # --- 状态查询 --------------------------------------------------------

    @property
    def is_loaded(self) -> bool:
        """是否已成功 load 一个 sweep 配置。"""
        return self._sweep is not None

    def available_vars(self, template_path: Optional[str]) -> List[VarSpec]:
        """根据模板路径返回可选 :class:`VarSpec` 列表(枚举轴 + .inp 变量)。

        缓存策略:同一 template_path(str 规范化)只解析一次。
        解析失败时不缓存,下次调用重试。

        Args:
            template_path: .inp 路径;None 或空串 → 仅枚举轴。
        """
        # cache key 规范化(空串 → None,其他 → str)
        key = template_path if (template_path and str(template_path).strip()) else None
        if key in self._var_cache:
            return self._var_cache[key]
        # key 为 None:仅枚举轴,直接 cache
        if key is None:
            result = sweep_var_combo._enum_axis_specs()
            self._var_cache[None] = result
            return result
        # key 为 path:直接调 sweep_var_combo._parse_inp(走模块属性查找,
        # 以便被 monkeypatch.setattr 替换)。这样可以捕获异常并区分
        # "解析失败"与"成功解析出空文件"。
        enum_specs = sweep_var_combo._enum_axis_specs()
        try:
            inp_specs = sweep_var_combo._parse_inp(key)
        except Exception:
            # 解析失败:退化为仅枚举轴,但不缓存(下次重试)
            return enum_specs
        result = enum_specs + inp_specs
        self._var_cache[key] = result
        return result

    @property
    def template(self) -> Optional[str]:
        """模板 .inp 路径;未 load 返 None。"""
        if self._sweep is None:
            return None
        tpl = getattr(self._sweep, "template", None)
        return str(tpl) if tpl is not None else None

    @property
    def case_count(self) -> int:
        """笛卡尔积 case 数(展开后);未 load 返 0。"""
        if self._sweep is None:
            return 0
        return len(self._sweep.materialize())

    @property
    def last_report(self) -> Optional[SweepReport]:
        """最近一次 :meth:`run` 的 SweepReport;未 run 返 None。"""
        return self._last_report

    # --- load ------------------------------------------------------------

    def load_from_dict(self, cfg: Dict[str, Any]) -> CaseSweep:
        """用 dict 配置构造 sweep,替换前一次状态。"""
        self._sweep = CaseSweep.from_dict(cfg)
        self._last_report = None
        return self._sweep

    def load_from_json(self, path: Union[str, Path]) -> CaseSweep:
        """从 JSON 文件 load sweep。"""
        self._sweep = CaseSweep.from_json(str(path))
        self._last_report = None
        return self._sweep

    def load_from_yaml(self, path: Union[str, Path]) -> CaseSweep:
        """从 YAML 文件 load sweep。"""
        self._sweep = CaseSweep.from_yaml(str(path))
        self._last_report = None
        return self._sweep

    # --- preview / run ---------------------------------------------------

    def preview(self) -> List[ExplicitCase]:
        """Dry run:只摊开 specs,不写盘。返 :class:`ExplicitCase` 列表。

        未 load 抛 :class:`RuntimeError`。
        """
        if self._sweep is None:
            raise RuntimeError("未 load sweep 配置,无法 preview")
        return self._sweep.materialize()

    def run(
        self, *, dry_run: bool = False, force: bool = False
    ) -> SweepReport:
        """实际生成 sweep,返 :class:`SweepReport`。

        - ``dry_run=True``:不写盘,只产出报告
        - ``force=True``:覆盖已存在的 case 子目录

        未 load 抛 :class:`RuntimeError`。
        """
        if self._sweep is None:
            raise RuntimeError("未 load sweep 配置,无法 run")
        self._last_report = sweep_generate(
            self._sweep, dry_run=dry_run, force=force
        )
        return self._last_report

    def report_dict(self) -> Optional[Dict[str, Any]]:
        """最近 report 的 :meth:`SweepReport.to_dict` 形式;供 GUI 表格展示。

        未 run 返 :data:`None`。
        """
        if self._last_report is None:
            return None
        return self._last_report.to_dict()

    # --- 实时编辑(实时表单用)----------------------------------------

    def update_field(self, key, value):
        """实时修改某个字段并重新构造内部 CaseSweep。

        支持的 key:
            - "template" / "output_dir" / "naming" / "naming_ext"
            - "source_dir" / "copy_strategy" / "exclude"
            - "sweeps.<axis>"    单个 axis 值
            - "sweeps_dict"      整个 sweeps dict 替换

        Raises:
            KeyError: 未知 key
            RuntimeError: 未 load 配置
        """
        if self._sweep is None:
            raise RuntimeError("未 load sweep 配置,无法 update_field")

        d = _sweep_to_dict(self._sweep)

        if "." in key:
            head, _, tail = key.partition(".")
            if head == "sweeps":
                d.setdefault("sweeps", {})[tail] = value
            else:
                raise KeyError("不支持的复合字段 {!r}".format(key))
        else:
            if key in ("template", "output_dir", "naming", "naming_ext",
                       "source_dir", "copy_strategy", "exclude"):
                d[key] = value
            elif key == "sweeps_dict":
                d["sweeps"] = dict(value)
            else:
                raise KeyError("未知字段 {!r}".format(key))

        self._sweep = CaseSweep.from_dict(d)
        self._last_report = None


def _sweep_to_dict(cs):
    """把 CaseSweep 实例转回 dict,供 update_field 改写后重建。

    注意:CaseSweep 里的 ``sweeps`` 是 ``SweepSpec`` dataclass,``asdict`` 会
    序列化成 ``{"values": {...}}``;这里要展平回 ``{axis: [...]}`` 形式,
    才能被 :meth:`CaseSweep.from_dict` 正确解析。
    """
    if hasattr(cs, "to_dict") and callable(cs.to_dict):
        return cs.to_dict()
    from dataclasses import asdict
    d = asdict(cs)
    if "copy_strategy" in d and hasattr(d["copy_strategy"], "value"):
        d["copy_strategy"] = d["copy_strategy"].value
    # 展平 SweepSpec → 平铺 dict (供 from_dict 识别)
    sw = d.get("sweeps")
    if isinstance(sw, dict) and "values" in sw and isinstance(sw["values"], dict):
        d["sweeps"] = sw["values"]
    return d
