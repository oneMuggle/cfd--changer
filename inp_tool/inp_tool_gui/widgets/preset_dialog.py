"""PresetDialog:3 类 Preset 通用应用对话框(v0.13 升级版)。

v0.13:用真实 preset 类替换 v0.12 hardcoded ``_PRESETS`` dict:
- ``turb`` → :func:`inp_tool.equations.make_turbulence_preset` (SSTKOmegaPreset)
- ``2t`` → :class:`inp_tool.equations.TwoTemperaturePreset`
- ``species`` → :class:`inp_tool.equations.SpeciesPreset`

构造只保存 preset 实例 + 元数据,不立即触发改写。
:meth:`accept(inp)` 注入 InpFile → 调 preset.apply(inp) → 捕 EquationRewriteError /
TwoTemperatureError → 错误标签(不弹模态,避免阻塞自动化测试)。

API:
    dlg = PresetDialog("turb")
    dlg.set_inp(file_ctrl.inp)
    if dlg.exec_() == QDialog.Accepted:
        ...  # preset 已写入 inp
"""
from typing import Any, List, Optional, Tuple

from PySide2.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)

from inp_tool.equations import (
    EquationRewriteError,
    SpeciesPreset,
    TwoTemperatureError,
    TwoTemperaturePreset,
    TurbulenceModel,
    make_turbulence_preset,
)

from inp_tool_gui.controllers.edit_controller import EditController  # noqa: F401  # 保留向后兼容


def _make_preset(name: str):
    """按名字构造对应 preset 实例。

    SST 默认参数:I=0.01 / L=0.01 / U_ref=204(典型高超声速);
    2T 默认:T_trans=300 / T_vib=300;
    Species 默认:fractions=N2/O2 空气。
    """
    if name == "turb":
        return make_turbulence_preset(
            TurbulenceModel.SST_KW,
            I=0.01,
            L=0.01,
            U_ref=204.0,
        )
    if name == "2t":
        return TwoTemperaturePreset(T_trans=300.0, T_vib=300.0)
    if name == "species":
        return SpeciesPreset(fractions={"N2": 0.79, "O2": 0.21})
    raise ValueError(f"未知 preset: {name}")


# Preset 名字 → 描述(给 QTextEdit 显示),真实 ops 在 accept(inp) 后由
# preset.apply 返回的 Dict 推导。
_PRESET_DESCRIPTIONS: dict = {
    "turb": (
        "SST k-ω 湍流预设:\n"
        "  • 用 make_turbulence_preset(SST_KW, I=0.01, L=0.01, U_ref=204)\n"
        "  • 调用 apply(inp) 自动写:\n"
        "      - physics.reynolds = 1.5·I·L·U_ref² / ν ≈ 0.036 U_ref\n"
        "      - physics.turbi_lev = 1.5·(I·U_ref)²\n"
        "      - physics.turbi_len = L\n"
        "      - eqnset_define v4=2, v5=3 (SST 家族内码)\n"
        "  • 自动清不兼容字段(clear_incompatible_fields=True)"
    ),
    "2t": (
        "双温度(2T)预设:\n"
        "  • 用 TwoTemperaturePreset(T_trans=300, T_vib=300)\n"
        "  • 调用 apply(inp) 自动写:\n"
        "      - physics.tnoneq_numeqns = 1 (启用非平衡能量方程)\n"
        "      - physics.reftem = 300 (平动温度)\n"
        "      - physics.vibtem = 300 (振动温度)\n"
        "      - eqnset_define v6 = 11 (MULTI_TEMP 标记)"
    ),
    "species": (
        "多组分预设:\n"
        "  • 用 SpeciesPreset(fractions={'N2': 0.79, 'O2': 0.21})\n"
        "  • 调用 apply(inp) 自动写:\n"
        "      - chemistry block + species 质量分率行\n"
        "      - 触发 infsets 与顶层 eqnset_define 适配"
    ),
}


class PresetDialog(QDialog):
    """通用 Preset 应用对话框(v0.13:真实 preset API)。"""

    def __init__(
        self,
        preset_name: str,
        edit_ctrl: Optional[EditController] = None,
        parent: Optional[QDialog] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"应用 Preset: {preset_name}")
        self.setModal(True)

        if preset_name not in _PRESET_DESCRIPTIONS:
            raise ValueError(f"未知 preset: {preset_name}")
        self._preset_name = preset_name
        self._preset = _make_preset(preset_name)
        # edit_ctrl 在 v0.12 由 accept() 写值循环用;v0.13 改走 preset.apply,
        # edit_ctrl 保留仅供向后兼容(签名不变),内部不再用
        self._edit_ctrl = edit_ctrl
        self._applied = False
        self._inp = None  # set_inp() 注入

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"即将应用 {preset_name} preset:", self))
        self._ops_view = QTextEdit(self)
        self._ops_view.setReadOnly(True)
        self._ops_view.setPlainText(_PRESET_DESCRIPTIONS[preset_name])
        layout.addWidget(self._ops_view)

        self._error_lbl = QLabel("", self)
        self._error_lbl.setStyleSheet("color: #c00;")
        self._error_lbl.setVisible(False)
        layout.addWidget(self._error_lbl)

        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # --- 公开 API -------------------------------------------------------

    def set_inp(self, inp) -> None:
        """注入 InpFile(accept 前调)。"""
        self._inp = inp

    @property
    def applied(self) -> bool:
        """是否成功 accept 并执行 preset.apply。"""
        return self._applied

    @property
    def preset_name(self) -> str:
        return self._preset_name

    # --- 槽 --------------------------------------------------------------

    def accept(self) -> None:
        """应用 preset.apply(inp),捕获异常 → 错误标签(保持 dialog 打开)。"""
        if self._inp is None:
            self._error_lbl.setText("⚠ 未设置 InpFile(请先调 set_inp)")
            self._error_lbl.setVisible(True)
            return
        try:
            self._preset.apply(self._inp)
        except EquationRewriteError as exc:
            self._error_lbl.setText(f"⚠ 改写失败:{exc}")
            self._error_lbl.setVisible(True)
            return
        except TwoTemperatureError as exc:
            self._error_lbl.setText(f"⚠ 双温错误:{exc}")
            self._error_lbl.setVisible(True)
            return
        except Exception as exc:  # noqa: BLE001 兜底
            self._error_lbl.setText(f"⚠ 未知错误:{exc}")
            self._error_lbl.setVisible(True)
            return
        self._applied = True
        super().accept()