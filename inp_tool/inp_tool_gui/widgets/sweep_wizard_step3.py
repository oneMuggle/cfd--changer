"""SweepWizard Step 3(条件依赖 when/then)— Task 4.4。

UI 结构::

    +--------------------------------------------------------+
    | 条件依赖(条件不满足 → 该 case 跳过对应轴)              |
    +--------------------------------------------------------+
    | +----------------------------------------------------+ |
    | | when:  [mach<1,reynolds>=1e6              ] [删除] | |
    | | 禁用轴: [turbulence                       ]         | |
    | | set_extra: [turb_init=yes                  ]         | |
    | +----------------------------------------------------+ |
    | ...(更多 row,可加可删)                                 |
    +--------------------------------------------------------+
    | [ 添加条件 ]                                            |
    +--------------------------------------------------------+

数据流(单向,与 SweepWizard 一致):
- 用户编辑任意字段 / 点 删除 / 点 添加条件 → 拼新 store → emit
  :pyattr:`store_changed`
- 外部 replace(其他 view 改了)→ :meth:`refresh_from_store(new_store)` 重建
  所有 row

设计简化(Task 4.4 范围):
- 一行 = 一条 :class:`ConditionalRule`,三个 ``QLineEdit`` 字段:
  - ``when``         文本,如 ``mach<1,reynolds>=1e6``
  - ``disable_axes`` 文本,如 ``turbulence,energy``
  - ``set_extra``    文本,如 ``turb_init=yes,scheme=roe``
- ``when`` 字符串解析:用 ``_split_predicates`` 拆 ``key<op>val``(以 ``,`` 分多
  predicate),再用 :func:`inp_tool.sweep.parse_condition` 走引擎真实路径。
  任何解析失败 → 该 row 不 emit(静默丢弃,但 row 仍保留)。
- ``disable_axes`` / ``set_extra`` 都是 tuple 字段,文本 → tuple 的转换在本
  文件的 :func:`_parse_disable_axes` / :func:`_parse_set_extra`。
"""
from typing import Dict, List, Optional, Tuple

from PySide2.QtCore import Qt, Signal
from PySide2.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from inp_tool.i18n_gui import tg
from inp_tool.sweep import (
    ConditionalRule,
    ConditionThen,
    ConditionWhen,
    parse_condition,
)
from inp_tool_gui.models.config_store import ConfigStore


# --- 文本解析辅助 -------------------------------------------------------


# 跟 sweep.py _OP_PATTERN 保持一致;这里前置枚举便于切分字符串。
_VALID_OPS = ("<=", "!=", "==", ">=", "<", ">")


def _split_predicates(when_text: str) -> Dict[str, str]:
    """把 ``"mach<1,reynolds>=1e6"`` 切成 ``{"mach": "<1", "reynolds": ">=1e6"}``。

    失败/空 → 空 dict(调用方据此跳过 emit)。
    """
    text = when_text.strip()
    if not text:
        return {}
    out: Dict[str, str] = {}
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        # 找出最早出现的 op(优先多字符 op: <=, !=, ==, >=, 然后 <, >)
        op_pos = -1
        op = ""
        for cand in _VALID_OPS:
            idx = chunk.find(cand)
            if idx == -1:
                continue
            if op_pos == -1 or idx < op_pos or (idx == op_pos and len(cand) > len(op)):
                op_pos = idx
                op = cand
        if op_pos <= 0 or not op:
            return {}
        key = chunk[:op_pos].strip()
        val = chunk[op_pos + len(op):].strip()
        if not key or not val:
            return {}
        out[key] = op + val
    return out


def _parse_disable_axes(text: str) -> Tuple[str, ...]:
    """``"turbulence, energy"`` → ``("turbulence", "energy")``。

    空字段跳过,允许 ``"a,, b"`` → ``("a", "b")``。
    """
    parts = [p.strip() for p in text.split(",")]
    return tuple(p for p in parts if p)


def _parse_set_extra(text: str) -> Tuple[Tuple[str, str], ...]:
    """``"turb_init=yes, scheme=roe"`` → ``(("turb_init", "yes"), ("scheme", "roe"))``。

    无 ``=`` 的项跳过(容错)。
    """
    out: List[Tuple[str, str]] = []
    for part in text.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        out.append((k, v))
    return tuple(out)


# --- 单行 widget -------------------------------------------------------


class ConditionRow(QGroupBox):
    """Step 3 中一条 (when, then) 的子表单。

    Signals:
        changed(object): 用户改了任意字段 → emit 新 ``ConditionalRule``(已经
            成功解析过;若 ``when`` 仍不可解析,emit ``None`` 表示"不要推 store")。
        remove_requested(int): 用户点了删除按钮,emit 占位索引(父 widget 用
            layout 位置定位,此参数忽略)。
    """

    changed = Signal(object)
    remove_requested = Signal(int)

    def __init__(
        self,
        rule: ConditionalRule,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setTitle("")
        self.setObjectName("wizard_step3_row")
        self._build_ui()
        self._fill_from_rule(rule)

    def _build_ui(self) -> None:
        """三个 field(when / disable_axes / set_extra)+ 删除按钮。"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)

        # --- 第一行: when [QLineEdit] [删除] ---------------------------
        row_when = QHBoxLayout()
        lbl_when = QLabel(tg("wizard.step3.lbl.when"), self)
        lbl_when.setMinimumWidth(70)
        self._edit_when = QLineEdit(self)
        self._edit_when.setPlaceholderText(tg("wizard.step3.lbl.when_hint"))
        self._edit_when.editingFinished.connect(self._on_edit_changed)
        self._btn_del = QPushButton(tg("wizard.step3.btn.del"), self)
        self._btn_del.clicked.connect(self._on_del_clicked)
        row_when.addWidget(lbl_when)
        row_when.addWidget(self._edit_when, 1)
        row_when.addWidget(self._btn_del)
        outer.addLayout(row_when)

        # --- 第二行: 禁用轴 [QLineEdit] -------------------------------
        row_dis = QHBoxLayout()
        lbl_dis = QLabel(tg("wizard.step3.lbl.disable"), self)
        lbl_dis.setMinimumWidth(70)
        self._edit_dis = QLineEdit(self)
        self._edit_dis.setPlaceholderText(tg("wizard.step3.lbl.disable_hint"))
        self._edit_dis.editingFinished.connect(self._on_edit_changed)
        row_dis.addWidget(lbl_dis)
        row_dis.addWidget(self._edit_dis, 1)
        outer.addLayout(row_dis)

        # --- 第三行: set_extra [QLineEdit] ----------------------------
        row_ext = QHBoxLayout()
        lbl_ext = QLabel(tg("wizard.step3.lbl.extra"), self)
        lbl_ext.setMinimumWidth(70)
        self._edit_ext = QLineEdit(self)
        self._edit_ext.setPlaceholderText(tg("wizard.step3.lbl.extra_hint"))
        self._edit_ext.editingFinished.connect(self._on_edit_changed)
        row_ext.addWidget(lbl_ext)
        row_ext.addWidget(self._edit_ext, 1)
        outer.addLayout(row_ext)

    # --- 公开属性 -------------------------------------------------------

    def current_rule(self) -> Optional[ConditionalRule]:
        """把三个 QLineEdit 拼成 ConditionalRule;解析失败 → None。"""
        pred = _split_predicates(self._edit_when.text())
        if not pred:
            return None
        try:
            when = parse_condition(pred)
        except (ValueError, TypeError):
            return None
        then = ConditionThen(
            disable_axes=_parse_disable_axes(self._edit_dis.text()),
            set_extra=_parse_set_extra(self._edit_ext.text()),
        )
        return ConditionalRule(when=when, then=then)

    # --- store -> row 数据流 ------------------------------------------

    def _fill_from_rule(self, rule: ConditionalRule) -> None:
        """从 ConditionalRule 还原三个 QLineEdit 文本(blockSignals 避免递归)。"""
        for w in (self._edit_when, self._edit_dis, self._edit_ext):
            w.blockSignals(True)
        try:
            self._edit_when.setText(
                ", ".join(
                    "{}{}{!r}".format(p.key, p.op, p.value)
                    for p in rule.when.predicates
                )
            )
            self._edit_dis.setText(", ".join(rule.then.disable_axes))
            self._edit_ext.setText(
                ", ".join("{}={}".format(k, v) for k, v in rule.then.set_extra)
            )
        finally:
            for w in (self._edit_when, self._edit_dis, self._edit_ext):
                w.blockSignals(False)

    # --- 内部:UI 事件 ---------------------------------------------------

    def _on_edit_changed(self) -> None:
        rule = self.current_rule()
        self.changed.emit(rule)  # None 也照发(父 widget 决定怎么用)

    def _on_del_clicked(self) -> None:
        # emit 时不带索引,父 widget 用 layout index 定位
        self.remove_requested.emit(-1)


# --- Step 3 主 widget ---------------------------------------------------


class SweepWizardStep3(QWidget):
    """向导 Step 3:条件依赖列表。

    Signals:
        store_changed(object): 当 row 内容变化 / 删除 / 添加 → emit 新
            ``ConfigStore``(conditions 字段已更新); ``object`` 而非
            ``ConfigStore`` 是为了跨模块稳定;消费者用
            ``isinstance(s, ConfigStore)`` 校验。
    """

    store_changed = Signal(object)

    def __init__(
        self,
        store: ConfigStore,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        # 当前条件(顺序与 row 顺序一致);refresh_from_store 时被 store 覆盖。
        self._rules: List[ConditionalRule] = []
        self._rows: List[ConditionRow] = []
        self._build_ui()
        self.refresh_from_store(store)

    # --- UI 构造 -------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # 顶部 label
        title = QLabel(tg("wizard.step3.title"), self)
        title.setWordWrap(True)
        root.addWidget(title)

        # 中部:scrollable area 装 rows
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._rows_host = QWidget(self._scroll)
        self._rows_layout = QVBoxLayout(self._rows_host)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.addStretch(1)  # 永远在底部撑一个 spacer
        self._scroll.setWidget(self._rows_host)
        root.addWidget(self._scroll, 1)

        # 空提示(放在 scroll 内的顶部;只在 row=0 时显示)
        self._empty_lbl = QLabel(tg("wizard.step3.empty"), self._rows_host)
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        # 先插到 layout 顶部,refresh_from_store 时会重新插(避免重复)
        self._rows_layout.insertWidget(0, self._empty_lbl)

        # 底部:添加条件
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self._btn_add = QPushButton(tg("wizard.step3.btn.add"), self)
        self._btn_add.clicked.connect(self._on_add_clicked)
        btn_row.addWidget(self._btn_add)
        root.addLayout(btn_row)

    # --- store 数据流 --------------------------------------------------

    def refresh_from_store(self, store: ConfigStore) -> None:
        """从给定 store 重建 row 列表(外部 replace 后调用)。

        阻断 signals 防误触发。
        """
        self._store = store
        self._rules = list(store.conditions)
        # 清空旧 row(保留底部的 stretch)
        for row in self._rows:
            self._rows_layout.removeWidget(row)
            row.setParent(None)
            row.deleteLater()
        self._rows = []
        # 把空提示插回顶部(scroll 内部)
        self._rows_layout.insertWidget(0, self._empty_lbl)
        # rebuild
        for rule in self._rules:
            self._append_row(rule)
        self._update_empty_label()

    # --- 公开方法:add / remove / row_count -----------------------------

    def add_condition(
        self,
        when_text: str = "",
        disable_axes_text: str = "",
        set_extra_text: str = "",
    ) -> None:
        """加一条新条件(给 row 直接传字段文本)。

        当 ``when_text`` 非空且能解析时 → emit 新 store;
        解析失败 / 全空 → 只加 row,不 emit。
        """
        rule = ConditionalRule(
            when=ConditionWhen(predicates=()),
            then=ConditionThen(),
        )
        row = ConditionRow(rule, self._rows_host)
        # 装信号:row.changed → 同步 _rules + emit;remove_requested → remove_condition
        row.changed.connect(lambda r, _row=row: self._on_row_changed(_row, r))
        row.remove_requested.connect(
            lambda _idx, _row=row: self._on_row_remove_requested(_row)
        )
        # 填文本(测试 / 程序化调用入口)
        self._fill_row_text(row, when_text, disable_axes_text, set_extra_text)
        # 插入 layout(stretch 之前)
        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        idx = self._rows_layout.indexOf(row)
        self._rows.insert(idx, row)
        # 同步 _rules + 可能 emit
        parsed = row.current_rule()
        if parsed is not None:
            # ensure rules list has the new entry
            if idx >= len(self._rules):
                self._rules.append(parsed)
            else:
                self._rules[idx] = parsed
            self._update_empty_label()
            self._commit_store(emit=True)
        else:
            # 解析失败 / 全空 → 只加 row,占位,_rules 暂不同步(下次 on_edit_changed 触发时再加)
            if idx >= len(self._rules):
                self._rules.append(rule)
            self._update_empty_label()

    def remove_condition(self, index: int) -> None:
        """按索引删除一条条件,emit 新 store。"""
        if index < 0 or index >= len(self._rows):
            return
        row = self._rows[index]
        del self._rules[index]
        del self._rows[index]
        self._rows_layout.removeWidget(row)
        row.setParent(None)
        row.deleteLater()
        self._update_empty_label()
        self._commit_store(emit=True)

    def row_count(self) -> int:
        """当前 row 数(测试 / 外部用)。"""
        return len(self._rows)

    # --- 内部:row 管理 -------------------------------------------------

    def _append_row(self, rule: ConditionalRule) -> None:
        """refresh 路径:根据 store.conditions 加 row。"""
        row = ConditionRow(rule, self._rows_host)
        row.changed.connect(lambda r, _row=row: self._on_row_changed(_row, r))
        row.remove_requested.connect(
            lambda _idx, _row=row: self._on_row_remove_requested(_row)
        )
        self._rows_layout.insertWidget(self._rows_layout.count() - 1, row)
        idx = self._rows_layout.indexOf(row)
        self._rows.insert(idx, row)

    def _fill_row_text(
        self,
        row: ConditionRow,
        when_text: str,
        disable_axes_text: str,
        set_extra_text: str,
    ) -> None:
        """测试便捷入口:直接给 row 三个 QLineEdit 填文本(阻断 signals)。"""
        for w in (row._edit_when, row._edit_dis, row._edit_ext):
            w.blockSignals(True)
        try:
            row._edit_when.setText(when_text)
            row._edit_dis.setText(disable_axes_text)
            row._edit_ext.setText(set_extra_text)
        finally:
            for w in (row._edit_when, row._edit_dis, row._edit_ext):
                w.blockSignals(False)

    def _update_empty_label(self) -> None:
        self._empty_lbl.setVisible(len(self._rows) == 0)

    # --- 内部:row 事件 -------------------------------------------------

    def _on_row_changed(
        self, row: ConditionRow, rule: Optional[ConditionalRule],
    ) -> None:
        """row 内字段改动 → 同步 self._rules[index] → emit 新 store。"""
        try:
            idx = self._rows.index(row)
        except ValueError:
            return
        if rule is None:
            # 解析失败 / 空 → 不动 self._rules,也不 emit(用户还在打字)
            return
        if idx >= len(self._rules):
            self._rules.append(rule)
        else:
            self._rules[idx] = rule
        self._commit_store(emit=True)

    def _on_row_remove_requested(self, row: ConditionRow) -> None:
        try:
            idx = self._rows.index(row)
        except ValueError:
            return
        self.remove_condition(idx)

    def _on_add_clicked(self) -> None:
        """点 "添加条件" → 加一条空 row;若 when 暂时空,不 emit store_changed。"""
        self.add_condition()

    # --- 内部:store 提交 ----------------------------------------------

    def _commit_store(self, emit: bool) -> None:
        """用当前 self._rules 拼新 ConfigStore 并(可选)emit。"""
        new_store = self._store.replace(conditions=tuple(self._rules))
        if new_store == self._store:
            return
        self._store = new_store
        if emit:
            self.store_changed.emit(new_store)


__all__ = [
    "ConditionRow",
    "SweepWizardStep3",
    "_split_predicates",
    "_parse_disable_axes",
    "_parse_set_extra",
]