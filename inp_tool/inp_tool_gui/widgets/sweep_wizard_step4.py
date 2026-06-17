"""SweepWizard Step 4(预览 + 运行)— Task 4.5。

UI 结构::

    +--------------------------------------------------------+
    | case 数预估: 12                                        |
    +--------------------------------------------------------+
    | +----------------------------------------------------+ |
    | | case_id | params          | applied                | |
    | +----------------------------------------------------+ |
    | | 0       | {mach: 0, ...}  | turb_init=yes          | |
    | | 1       | {mach: 1, ...}  |                        | |
    | | ...                                                 | |
    | +----------------------------------------------------+ |
    | (仅展示前 50 case;超过显示 "(略 N)")                    |
    +--------------------------------------------------------+
    | [ Dry run ] [ Run ] [ Force ]   状态: (空)             |
    +--------------------------------------------------------+

数据流(单向,与 SweepWizard 一致):
- 外部 replace → :meth:`refresh_from_store(new_store)` 重建 case 数 label
  与预览表。
- Dry run / Run / Force 按钮 → emit 信号(MainWindow/Phase 7 接):
  - :pyattr:`dry_run_clicked(object)` — 传 ``List[ExpandedCase]``(object 是
    为跨模块稳定;消费者用 ``isinstance(c, ExpandedCase)`` 校验)。
  - :pyattr:`run_clicked()` — Phase 7 实际跑。
  - :pyattr:`force_clicked()` — Phase 7 强制覆盖。

设计决策(Task 4.5 范围):
- 复用 Phase 1 引擎 :func:`inp_tool.sweep.expand_with_conditions`,**不**
  自己展开 case(避免与引擎语义分叉)。
- ``AxisSpec.range`` → 内部用 :func:`_axis_to_value_list` 展开为 list(纯
  Python ``range`` 不支持 float,所以手写含 step=0/反向的容错)。
- 预览表只读,只显示前 50 case(避免在 1280x892 窗口里塞上千行)。
- ``expand_with_conditions`` 抛异常 → 在状态 label 显示错误,表清空。
"""
from typing import Any, Dict, List, Optional, Tuple

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool.sweep import (
    ExpandedCase,
    SweepSpec,
    expand_with_conditions,
)
from inp_tool_gui.models.config_store import AxisSpec, ConfigStore


# --- 常量 ---------------------------------------------------------------

# 预览表最多展示行数(超过显示 "(略 N)")
_PREVIEW_LIMIT = 50

# 表列索引
_COL_CASE_ID = 0
_COL_PARAMS = 1
_COL_APPLIED = 2


# --- 辅助函数 -----------------------------------------------------------


def _axis_to_value_list(spec: AxisSpec) -> List[Any]:
    """把 :class:`AxisSpec` 展成 ``List[Any]``,给 :class:`SweepSpec.values` 用。

    - ``range`` → ``[min, min+step, ..., max]``(含端点;step=0 抛 ValueError)。
    - 其它 (enum_subset / explicit_list / csv_str) → ``list(spec.values)``。
    """
    if spec.kind == "range":
        lo = spec.range_min
        hi = spec.range_max
        step = spec.range_step
        if lo is None or hi is None or step is None:
            return []
        if step == 0:
            raise ValueError("range step must be non-zero")
        if step > 0 and lo > hi:
            raise ValueError("range min must be <= max")
        if step < 0 and lo < hi:
            raise ValueError("range min must be >= max (with negative step)")
        # 计算步数(包含两端点):n = int((hi - lo) / step) + 1
        n = int((hi - lo) / step) + 1
        # 浮点容差:最后一格可能略微越界,提前 break
        out: List[Any] = []
        for i in range(n):
            v = lo + i * step
            if step > 0 and v > hi:
                break
            if step < 0 and v < hi:
                break
            out.append(v)
        return out
    return list(spec.values)


def _format_extras(extras: Tuple[Tuple[str, str], ...]) -> str:
    """``((k1, v1), (k2, v2))`` → ``"k1=v1, k2=v2"``;空 → ``""``。"""
    if not extras:
        return ""
    return ", ".join("{}={}".format(k, v) for k, v in extras)


def _format_params(values: Dict[str, Any]) -> str:
    """``{a: 1, b: 'x'}`` → ``"a=1, b='x'"``(str 加引号便于视觉区分)。"""
    parts: List[str] = []
    for k in sorted(values.keys()):
        v = values[k]
        if isinstance(v, str):
            parts.append("{}='{}'".format(k, v))
        else:
            parts.append("{}={}".format(k, v))
    return ", ".join(parts)


# --- 主 widget ----------------------------------------------------------


class SweepWizardStep4(QWidget):
    """向导 Step 4:case 数预估 + 预览表 + Dry/Run/Force 按钮。

    Signals:
        dry_run_clicked(object): 用户点 Dry run,emit 当前
            ``List[ExpandedCase]``(已成功展开);object 是为跨模块稳定。
        run_clicked(): 用户点 Run(无参数;实际执行由 Phase 7 接管)。
        force_clicked(): 用户点 Force(强制覆盖)。
    """

    dry_run_clicked = Signal(object)
    run_clicked = Signal()
    force_clicked = Signal()

    def __init__(
        self,
        store: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        # 上一次成功展开的 cases(给 Dry run / preview 用;出错时清空)
        self._expanded: List[ExpandedCase] = []
        # 上次错误信息(用于状态 label)
        self._last_error: Optional[str] = None
        self._build_ui()
        self.refresh_from_store(store)

    # --- 公开属性(测试 / 外部用)------------------------------------

    def case_count_text(self) -> str:
        """返回当前 case 数 label 的完整文本(测试断言用)。"""
        return self._case_count_label.text()

    def preview_row_count(self) -> int:
        """返回预览表当前行数(测试断言用)。"""
        return self._table.rowCount()

    def status_text(self) -> str:
        """返回状态 label 文本(测试断言用)。"""
        return self._status_label.text()

    def last_error(self) -> Optional[str]:
        """返回最近一次展开的错误信息(测试 / 调试用)。"""
        return self._last_error

    def current_cases(self) -> List[ExpandedCase]:
        """返回最近一次成功展开的 cases(供外部连接 Run 按钮时使用)。"""
        return list(self._expanded)

    # --- UI 构造 ------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 顶部:case 数预估
        self._case_count_label = QLabel(self)
        self._case_count_label.setObjectName("wizard_step4_case_count")
        root.addWidget(self._case_count_label)

        # 中部:预览表
        self._table = QTableWidget(self)
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels([
            tg("sweep.col.case_id"),
            tg("sweep.col.params"),
            tg("sweep.col.applied"),
        ])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(_COL_CASE_ID, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(_COL_PARAMS, QHeaderView.Stretch)
        header.setSectionResizeMode(_COL_APPLIED, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self._table, 1)

        # 底部:按钮 + 状态
        btn_row = QHBoxLayout()
        self._btn_dry = QPushButton(tg("sweep.btn.run_dry"), self)
        self._btn_dry.setObjectName("wizard_step4_btn_dry")
        self._btn_dry.clicked.connect(self.on_dry_run_clicked)
        self._btn_run = QPushButton(tg("sweep.btn.run"), self)
        self._btn_run.setObjectName("wizard_step4_btn_run")
        self._btn_run.clicked.connect(self.on_run_clicked)
        self._btn_force = QPushButton(tg("sweep.btn.force"), self)
        self._btn_force.setObjectName("wizard_step4_btn_force")
        self._btn_force.clicked.connect(self.on_force_clicked)
        btn_row.addWidget(self._btn_dry)
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_force)
        btn_row.addStretch(1)
        self._status_label = QLabel("", self)
        self._status_label.setObjectName("wizard_step4_status")
        btn_row.addWidget(self._status_label, 1)
        root.addLayout(btn_row)

    # --- store -> view 数据流 ----------------------------------------

    def refresh_from_store(self, store: ConfigStore) -> None:
        """从给定 store 重建 case 数 label 和预览表(外部 replace 后调用)。

        失败容错:任何展开错误(范围 step=0、轴空)→ 清空表 + 状态 label
        显示错误信息,但不抛异常(用户正在编辑,允许中间态)。
        """
        self._store = store
        # 先更新 case 数 label(尝试展开一次拿 case count)
        n_cases = 0
        try:
            n_cases = len(
                expand_with_conditions(
                    self._build_engine_spec(), self._store.conditions,
                )
            )
        except (ValueError, TypeError, ZeroDivisionError):
            n_cases = 0
        self._case_count_label.setText(
            "{} {}".format(tg("sweep.lbl.case_count"), n_cases)
        )
        # 重建预览表(也负责更新 self._expanded / 状态 label)
        self._rebuild_preview()

    # --- 内部:重新计算 + 重画表 -------------------------------------

    def _rebuild_preview(self) -> None:
        """重画预览表(也用于 Dry run 按钮)。"""
        self._table.blockSignals(True)
        try:
            self._table.setRowCount(0)
            try:
                self._expanded = expand_with_conditions(
                    self._build_engine_spec(), self._store.conditions,
                )
            except (ValueError, TypeError, ZeroDivisionError) as exc:
                self._expanded = []
                self._last_error = str(exc)
                self._status_label.setText(str(exc))
                return
            self._last_error = None
            # 展开成功 → 状态 label 清空(但不重置 case count label)
            self._status_label.setText("")
            self._render_preview_table(self._expanded)
        finally:
            self._table.blockSignals(False)

    def _build_engine_spec(self) -> SweepSpec:
        """把 store.sweeps 拼成 :class:`SweepSpec`(供引擎展开)。

        注:这里**不**捕获展开错误(让上层的 try/except 看到原始异常)。
        """
        values: Dict[str, List[Any]] = {}
        for key, axis in self._store.sweeps.items():
            values[key] = _axis_to_value_list(axis)
        return SweepSpec(values=values)

    def _render_preview_table(self, cases: List[ExpandedCase]) -> None:
        """把前 N 个 case 渲到预览表;超过 N 时附加一行 ``"(略 M)"``。"""
        n_total = len(cases)
        shown = cases[:_PREVIEW_LIMIT]
        extra_row = 1 if n_total > _PREVIEW_LIMIT else 0
        self._table.setRowCount(len(shown) + extra_row)
        for row_idx, case in enumerate(shown):
            self._set_row(
                row_idx,
                str(row_idx),
                _format_params(case.values),
                _format_extras(case.extras),
            )
        if n_total > _PREVIEW_LIMIT:
            # 末行用 "(略 N)" 占位
            omitted = n_total - _PREVIEW_LIMIT
            placeholder = "{} {}".format(tg("sweep.lbl.short"), omitted)
            self._set_row(len(shown), "", placeholder, "")

    def _set_row(self, row: int, case_id: str, params: str, applied: str) -> None:
        """(内部辅助)在表指定 row 设置三列文本(全只读)。"""
        for col, text in (
            (_COL_CASE_ID, case_id),
            (_COL_PARAMS, params),
            (_COL_APPLIED, applied),
        ):
            item = QTableWidgetItem(text)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(row, col, item)

    # --- 按钮 handler -------------------------------------------------

    def on_dry_run_clicked(self) -> None:
        """Dry run:重建预览 + emit dry_run_clicked(expanded_cases)。"""
        self._rebuild_preview()
        # 即使展开失败也 emit(传空 list)——消费者可据此判断
        self.dry_run_clicked.emit(list(self._expanded))

    def on_run_clicked(self) -> None:
        """Run(Phase 7 接管):emit run_clicked()。"""
        # 顺手 refresh,确保 emit 之前的 preview 是最新的
        self._rebuild_preview()
        self.run_clicked.emit()

    def on_force_clicked(self) -> None:
        """Force(强制覆盖):emit force_clicked()。"""
        self._rebuild_preview()
        self.force_clicked.emit()


__all__ = ["SweepWizardStep4"]
