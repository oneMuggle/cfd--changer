"""
inp_tool 任务向导(Task Wizards)模块 v0.7.1

提供 3 个任务导向的向导,每个都是完成具体工作的工具:

  - wizard modify-file  — 修改单个 .inp 的来流参数(5 步)
  - wizard sweep        — 批量生成算例(7 步,用 PR #1 的新能力)
  - wizard diff         — 比较两个 .inp 文件(3 步)

无参 `wizard` 显示菜单。

设计:
- WizardBase 抽象基类: 步骤定义 + 公共流程
- WizardSession 状态: 当前步骤 / 数据累积 / 历史(支持 back)
- 通用组件 menu / confirm / input_text(走 i18n)
"""
from __future__ import annotations
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

from . import i18n
from .i18n import t, get_lang
from .repl_state import ReplSession


# ============================================================
# 异常
# ============================================================
class WizardCancel(Exception):
    """用户选择取消(按 Q / Ctrl+C)"""
    pass


# ============================================================
# 通用组件(走 i18n)
# ============================================================
def _print(s: str) -> None:
    """统一 print 到 stdout"""
    print(s)


def input_text(
    question: str,
    default: Optional[str] = None,
    validator: Optional[Callable[[str], Optional[str]]] = None,
) -> str:
    """问一个文本问题,空回车=default。"""
    if default is None or default == "":
        suffix = ": "
    else:
        suffix = f" [{default}]: "
    while True:
        try:
            raw = input(question + suffix)
        except (EOFError, KeyboardInterrupt):
            raise WizardCancel()
        raw = raw.strip()
        if raw == "":
            if default is not None:
                return default
            return raw
        if validator is not None:
            err = validator(raw)
            if err is not None:
                _print(f"  {err}")
                continue
        return raw


def confirm(question: str, default: bool = False) -> bool:
    """y/N 确认。"""
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        try:
            raw = input(question + suffix)
        except (EOFError, KeyboardInterrupt):
            raise WizardCancel()
        raw = raw.strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes", "是", "好"):
            return True
        if raw in ("n", "no", "否", "不"):
            return False
        if get_lang() == "zh":
            _print("  请输入 y 或 n")
        else:
            _print("  Please enter y or n")


def menu(
    prompt: str,
    choices: List[Tuple[str, str, str]],
    default: Optional[str] = None,
) -> str:
    """显示一个数字菜单,返回选中 key。"""
    is_zh = get_lang() == "zh"
    _print(prompt)
    for key, label_zh, label_en in choices:
        label = label_zh if is_zh else label_en
        _print(f"  [{key}] {label}")
    while True:
        try:
            suffix = f" [{default}]: " if default else ": "
            raw = input("> " + suffix)
        except (EOFError, KeyboardInterrupt):
            raise WizardCancel()
        raw = raw.strip()
        if raw == "" and default is not None:
            return default
        for key, _, _ in choices:
            if raw.upper() == key.upper():
                if key.upper() == "Q":
                    raise WizardCancel()
                return key
        if is_zh:
            _print(f"  无效选择: {raw!r},请重试。")
        else:
            _print(f"  Invalid choice: {raw!r}, please retry.")


# ============================================================
# Wizard 框架
# ============================================================
class WizardBase:
    """所有任务向导的基类。"""
    title: str = ""
    description: str = ""

    def __init__(self, session: Optional[ReplSession] = None):
        self.session = session
        self.data: Dict[str, Any] = {}
        self.history: List[str] = []
        self._cancelled = False

    def run(self) -> None:
        """主循环:依次走每个步骤,最后 execute。"""
        if not self.steps:
            raise NotImplementedError(f"{self.__class__.__name__}: empty steps")
        self._print_header()
        for step_name in self.steps:
            self._print_step_header(step_name)
            method = getattr(self, step_name, None)
            if method is None:
                raise NotImplementedError(
                    f"{self.__class__.__name__}: missing method {step_name}"
                )
            try:
                result = method(self.data)
            except WizardCancel:
                self._print_cancelled()
                return
            if result is None:
                self._print_cancelled()
                return
            next_name, new_data = result
            if next_name == "__done__":
                # 跳到 execute(不再走 step)
                self.data.update(new_data)
                break
            self.data.update(new_data)
            self.history.append(step_name)
        self._print_execute_header()
        try:
            self.execute(self.data)
        except WizardCancel:
            self._print_cancelled()
            return
        self._print_done()

    def _print_header(self) -> None:
        sep = "═" * 60
        _print(f"\n{sep}")
        _print(f"  {self.title}")
        _print(sep)
        if self.description:
            _print(self.description)
            _print("")

    def _print_step_header(self, step_name: str) -> None:
        total = len(self.steps)
        import re
        m = re.match(r"step_(\d+)_(.+)", step_name)
        if m:
            step_num, step_desc = m.group(1), m.group(2).replace("_", " ")
            if get_lang() == "zh":
                _print(f"\n──── 步骤 {step_num}/{total}: {step_desc} ────")
            else:
                _print(f"\n──── Step {step_num}/{total}: {step_desc} ────")
        else:
            _print(f"\n──── {step_name} ────")

    def _print_cancelled(self) -> None:
        if get_lang() == "zh":
            _print("\n✗ 已取消。")
        else:
            _print("\n✗ Cancelled.")

    def _print_execute_header(self) -> None:
        if get_lang() == "zh":
            _print("\n──── 执行 ────")
        else:
            _print("\n──── Executing ────")

    def _print_done(self) -> None:
        if get_lang() == "zh":
            _print("\n✓ 向导完成。")
        else:
            _print("\n✓ Wizard done.")

    def execute(self, data: Dict[str, Any]) -> None:
        raise NotImplementedError


# ============================================================
# 3 个具体向导
# ============================================================

class WizardModifyFile(WizardBase):
    """修改单个 .inp 文件的来流参数。5 步。"""
    title_zh = "向导:修改单个 .inp 文件"
    title_en = "Wizard: Modify a single .inp file"
    description_zh = (
        "用途:打开一个 .inp,改它的来流参数(Ma/α/β/T/p),保存到磁盘。"
    )
    description_en = (
        "Purpose: Open a .inp, edit its freestream (Ma/α/β/T/p), save to disk."
    )

    @property
    def title(self) -> str:
        return self.title_zh if get_lang() == "zh" else self.title_en

    @property
    def description(self) -> str:
        return self.description_zh if get_lang() == "zh" else self.description_en

    steps = [
        "step_1_select_file",
        "step_1a_detect",      # v0.9.1:加载后立即展示方程系统检测报告
        "step_2_select_fields",
        "step_3_enter_values",
        "step_4_preview",
        "step_5_output",
    ]

    def step_1_select_file(self, data: dict):
        from pathlib import Path
        _print("加载一个 .inp 文件,作为修改目标。")
        if self.session and self.session.current:
            cur_path = str(self.session.files[self.session.current].path)
            _print(f"  当前已加载: {cur_path}")
            ans = confirm(f"  使用当前已加载文件?", default=True)
            if ans:
                return ("step_1a_detect", {"file": cur_path})
        while True:
            path_str = input_text("文件路径(可拖入)")
            if not path_str:
                raise WizardCancel()
            p = Path(path_str)
            if not p.is_file():
                _print(f"  文件不存在: {p}")
                continue
            return ("step_1a_detect", {"file": str(p)})

    def step_1a_detect(self, data: dict):
        """v0.9.1:解析 .inp 并展示方程系统/湍流模型/气体类型检测报告。

        纯展示步骤,无用户输入。让用户在选字段前了解当前文件配置 — 例如
        看到 "2T + multi-temp" 就知道改 reftem 时还要配 vibtem。
        """
        from .parser import parse_file
        from .equations import detect_equations
        is_zh = get_lang() == "zh"
        file_path = data.get("file")
        if not file_path:
            return ("step_2_select_fields", {})
        try:
            inp = parse_file(file_path)
            rep = detect_equations(inp)
        except Exception as e:
            if is_zh:
                _print(f"  ⚠ 检测失败(跳过):{e}")
            else:
                _print(f"  ⚠ Detection failed (skipping): {e}")
            return ("step_2_select_fields", {})
        if is_zh:
            _print(f"  方程系统检测:")
            _print(f"    能量模型 : {rep.energy.value}"
                   f"  (physics.tnoneq_numeqns)")
            _print(f"    湍流模型 : {rep.turbulence.value}"
                   f"  (eqnset_define v4={rep.ntrbst_family}, v5={rep.ntrbst_code})")
            _print(f"    气体类型 : {rep.gas.value}"
                   f"  (eqnset_define v6={rep.gas_code})")
            _print(f"    物种数   : {rep.n_species}")
        else:
            _print(f"  Detection:")
            _print(f"    Energy  : {rep.energy.value}")
            _print(f"    Turb    : {rep.turbulence.value}")
            _print(f"    Gas     : {rep.gas.value} (v6={rep.gas_code})")
            _print(f"    Species : {rep.n_species}")
        if rep.notes:
            if is_zh:
                _print(f"  ⚠ 告警:")
            else:
                _print(f"  ⚠ Warnings:")
            for n in rep.notes:
                _print(f"    - {n}")
        # 推荐字段(让用户对 step_2 有预期)
        recs = rep.recommended_fields()
        if recs:
            if is_zh:
                _print(f"  推荐改这些字段(根据当前方程系统):")
            else:
                _print(f"  Recommended fields (per current equation system):")
            for f in recs:
                _print(f"    • {f}")
        return ("step_2_select_fields", {})

    def step_2_select_fields(self, data: dict):
        is_zh = get_lang() == "zh"
        if is_zh:
            _print("  可选项:1 2 3 4 5 all done Q")
            _print("  (1=Ma 2=alpha 3=beta 4=T 5=p)")
        else:
            _print("  Options: 1 2 3 4 5 all done Q")
            _print("  (1=Ma 2=alpha 3=beta 4=T 5=p)")
        chosen: List[str] = []
        while True:
            try:
                raw = input_text("  字段")
            except WizardCancel:
                return None
            raw = raw.strip()
            if raw == "" or raw.lower() == "done":
                break
            if raw.lower() == "all":
                chosen = ["Ma", "alpha", "beta", "T", "p"]
                break
            tokens = raw.split()
            for tok in tokens:
                if tok == "1":
                    chosen.append("Ma")
                elif tok == "2":
                    chosen.append("alpha")
                elif tok == "3":
                    chosen.append("beta")
                elif tok == "4":
                    chosen.append("T")
                elif tok == "5":
                    chosen.append("p")
                elif tok.lower() == "q":
                    return None
            if chosen:
                break
            if is_zh:
                _print("  请至少选一个字段")
            else:
                _print("  Please pick at least one field")
        if not chosen:
            return None
        return ("step_3_enter_values", {"fields": chosen})

    def step_3_enter_values(self, data: dict):
        values = {}
        for field_name in data["fields"]:
            v = input_text(f"  {field_name} 新值", default="")
            if not v:
                continue
            try:
                values[field_name] = float(v)
            except ValueError:
                if get_lang() == "zh":
                    _print(f"  '{v}' 不是有效数字,跳过 {field_name}")
                else:
                    _print(f"  '{v}' not a number, skip {field_name}")
        if not values:
            if get_lang() == "zh":
                _print("  没有有效输入,取消。")
            else:
                _print("  No valid input, cancelled.")
            return None
        return ("step_4_preview", {"values": values})

    def step_4_preview(self, data: dict):
        is_zh = get_lang() == "zh"
        if is_zh:
            _print("  预览变更:")
        else:
            _print("  Preview changes:")
        for k, v in data["values"].items():
            _print(f"    {k} → {v}")
        if confirm("  确认继续?", default=True):
            return ("step_5_output", {})
        return None

    def step_5_output(self, data: dict):
        from pathlib import Path
        src = Path(data["file"])
        suffix = "_modified"
        dst = src.parent / f"{src.stem}{suffix}{src.suffix}"
        if get_lang() == "zh":
            _print(f"  输出: {dst}")
        else:
            _print(f"  Output: {dst}")
        return ("__done__", {"output": str(dst)})

    def execute(self, data: dict) -> None:
        is_zh = get_lang() == "zh"
        if is_zh:
            _print(f"  → 加载 {data['file']}")
            _print(f"  → 应用 {len(data['values'])} 个字段修改")
            _print(f"  → 写入 {data.get('output', data['file'])}")
            _print("  (modify-file 真实写入实现见后续 PR。本次为占位骨架。)")
        else:
            _print(f"  → load {data['file']}")
            _print(f"  → apply {len(data['values'])} field changes")
            _print(f"  → write {data.get('output', data['file'])}")


class WizardSweep(WizardBase):
    """v0.8.2 起:批量生成算例。6 步,整目录模式为默认,扁平模式已移除。

    步骤顺序:
      1. source_dir   (基础算例目录,必填,自动取其下 mcfd.inp 作为 template)
      2. output       (输出目录 + manifest)
      3. mode         (笛卡尔 / cases / groups / CSV)
      4. params       (填参,根据 mode)
      5. naming       (命名模板)
      6. preview      (预览 + 覆盖确认 + 执行)
    """
    title_zh = "向导:批量生成算例(整目录)"
    title_en = "Wizard: Batch-generate cases (whole-dir)"

    @property
    def title(self) -> str:
        return self.title_zh if get_lang() == "zh" else self.title_en

    @property
    def description(self) -> str:
        is_zh = get_lang() == "zh"
        if is_zh:
            return "适用:从 1 个完整基础算例目录出发,扫一组参数,生成 N 个完整算例子目录。"
        return "Use: From 1 complete base case dir, sweep parameters, generate N full subdirs."

    steps = [
        "step_1_source_dir",
        "step_2_output",
        "step_3_mode",
        "step_4_params",
        "step_4a_detect",      # v0.9.1:展示 template 的方程系统检测报告
        "step_5_naming",
        "step_5a_pbs",
        "step_6_preview",
    ]

    def step_1_source_dir(self, data: dict):
        """v0.8.2 起:source_dir 必填。模板路径自动取 source_dir/mcfd.inp。"""
        from pathlib import Path
        is_zh = get_lang() == "zh"
        if is_zh:
            prompt = "  基础算例目录(必填,完整算例根目录,例:/home/.../reference/suanli)"
            hint = "  (扁平模式 v0.8.2 起已从 wizard 移除,基础算例必须是含 mcfd.inp 的完整目录)"
        else:
            prompt = "  Base case directory (required, full case root, e.g. /path/to/reference/suanli)"
            hint = "  (flat mode removed from wizard v0.8.2; base case must be a complete dir containing mcfd.inp)"
        _print(hint)
        while True:
            source_dir = input_text(prompt, default="")
            if not source_dir:
                if is_zh:
                    _print("  错误: 基础算例目录为必填项(扁平模式已从 wizard 中移除)")
                else:
                    _print("  Error: base case directory is required (flat mode removed from wizard)")
                continue
            p = Path(source_dir)
            if not p.is_dir():
                _print(f"  目录不存在: {p}")
                continue
            template_path = p / "mcfd.inp"
            if not template_path.is_file():
                _print(f"  目录下找不到 mcfd.inp: {template_path}")
                continue
            if is_zh:
                choices = [
                    ("1", "hardlink  零空间,跨 FS 退化(推荐)", "hardlink"),
                    ("2", "copy      慢,占空间", "copy"),
                    ("3", "symlink   零空间,跨 FS,Windows 需 dev mode", "symlink"),
                ]
                sp_prompt = "  复制策略:"
            else:
                choices = [
                    ("1", "hardlink  zero space, falls back on cross-FS (recommended)", "hardlink"),
                    ("2", "copy      slow, uses disk space", "copy"),
                    ("3", "symlink   zero space, cross-FS, needs dev mode on Windows", "symlink"),
                ]
                sp_prompt = "  Copy strategy:"
            try:
                key = menu(sp_prompt, choices, default="1")
            except WizardCancel:
                return None
            key_to_strategy = {"1": "hardlink", "2": "copy", "3": "symlink"}
            return ("step_2_output", {
                **data,
                "source_dir": str(p),
                "template": str(template_path),
                "copy_strategy": key_to_strategy.get(key, "hardlink"),
            })

    def step_2_output(self, data: dict):
        is_zh = get_lang() == "zh"
        default = "./sweep_cases"
        prompt = "  输出目录" if is_zh else "  Output directory"
        out_dir = input_text(prompt, default=default)
        if is_zh:
            manifest = confirm("  生成 manifest.json?", default=True)
        else:
            manifest = confirm("  Generate manifest.json?", default=True)
        manifest_path = None
        if manifest:
            from pathlib import Path
            mp = input_text("  manifest 路径", default=str(Path(out_dir) / "manifest.json"))
            manifest_path = mp
        return ("step_3_mode", {"output_dir": out_dir, "manifest_path": manifest_path})

    def step_3_mode(self, data: dict):
        is_zh = get_lang() == "zh"
        if is_zh:
            choices = [
                ("1", "笛卡尔积 sweeps: {axis: [v1, v2]}", "Cartesian"),
                ("2", "显式列表 cases: [{...}, ...]", "Explicit list"),
                ("3", "分组继承 groups: [{name, common, cases}, ...]", "Groups"),
                ("4", "CSV 文件 cases.csv", "CSV file"),
                ("Q", "取消", "(quit)"),
            ]
            prompt = "选择 sweep 模式:"
        else:
            choices = [
                ("1", "Cartesian: sweeps: {axis: [v1, v2]}", "Cartesian"),
                ("2", "Explicit list: cases: [{...}, ...]", "Explicit list"),
                ("3", "Groups: groups: [{name, common, cases}, ...]", "Groups"),
                ("4", "CSV file cases.csv", "CSV file"),
                ("Q", "(quit)", "(quit)"),
            ]
            prompt = "Pick sweep mode:"
        key = menu(prompt, choices, default="1")
        return ("step_4_params", {"mode": key})

    def step_4_params(self, data: dict):
        is_zh = get_lang() == "zh"
        mode = data["mode"]
        if mode == "1":
            _print("  笛卡尔:用 sweeps: 语法。")
            _print("  示例:{alpha: [0, 5, 10], mach: [0.6, 0.8]}")
            raw = input_text("  sweeps(YAML / JSON)")
            if not raw:
                return None
            import yaml
            try:
                sweeps = yaml.safe_load(raw)
                if not isinstance(sweeps, dict):
                    raise ValueError("expected a dict")
            except Exception as e:
                _print(f"  解析失败: {e}")
                return None
            return ("step_5_naming", {"sweeps": sweeps})
        elif mode == "2":
            _print("  显式列表:每行一个 case,如 {alpha: 10, beta: 5}")
            raw = input_text("  cases(YAML 列表)")
            if not raw:
                return None
            import yaml
            try:
                cases = yaml.safe_load(raw)
                if not isinstance(cases, list):
                    raise ValueError("expected a list")
            except Exception as e:
                _print(f"  解析失败: {e}")
                return None
            return ("step_5_naming", {"cases": cases})
        elif mode == "3":
            _print("  分组继承:每组共享 common 字段,组内 cases 是列表")
            raw = input_text("  groups(YAML 列表)")
            if not raw:
                return None
            import yaml
            try:
                groups = yaml.safe_load(raw)
                if not isinstance(groups, list):
                    raise ValueError("expected a list")
            except Exception as e:
                _print(f"  解析失败: {e}")
                return None
            return ("step_5_naming", {"groups": groups})
        elif mode == "4":
            csv_path = input_text("  CSV 文件路径")
            if not csv_path:
                return None
            from pathlib import Path
            if not Path(csv_path).is_file():
                _print(f"  文件不存在: {csv_path}")
                return None
            return ("step_5_naming", {"csv": csv_path})
        return None

    def step_5_naming(self, data: dict):
        is_zh = get_lang() == "zh"
        default = "case_{alpha}"
        prompt = ("  命名模板(可用 {alpha} {beta} {mach} {T} {p} {group})"
                  if is_zh else
                  "  Naming template (placeholders: {alpha} {beta} {mach} {T} {p} {group})")
        naming = input_text(prompt, default=default)
        return ("step_5a_pbs", {"naming": naming})

    def step_4a_detect(self, data: dict):
        """v0.9.1:展示 template 的方程系统检测报告,让用户在 naming/pbs 前
        清楚 template 是层流/湍流/双温,以及推荐应改的字段。

        纯展示步骤,无交互。检测失败不阻断。
        """
        from .parser import parse_file
        from .equations import detect_equations
        is_zh = get_lang() == "zh"
        template = data.get("template")
        if not template:
            return ("step_5_naming", {})
        try:
            inp = parse_file(template)
            rep = detect_equations(inp)
        except Exception as e:
            if is_zh:
                _print(f"  ⚠ 检测失败(跳过):{e}")
            else:
                _print(f"  ⚠ Detection failed (skipping): {e}")
            return ("step_5_naming", {})
        if is_zh:
            _print(f"  Template 方程系统检测:")
            _print(f"    能量模型 : {rep.energy.value}")
            _print(f"    湍流模型 : {rep.turbulence.value}"
                   f"  (v4={rep.ntrbst_family}, v5={rep.ntrbst_code})")
            _print(f"    气体类型 : {rep.gas.value}  (v6={rep.gas_code})")
            _print(f"    物种数   : {rep.n_species}")
        else:
            _print(f"  Template equation system:")
            _print(f"    Energy  : {rep.energy.value}")
            _print(f"    Turb    : {rep.turbulence.value}")
            _print(f"    Gas     : {rep.gas.value} (v6={rep.gas_code})")
            _print(f"    Species : {rep.n_species}")
        if rep.notes:
            if is_zh:
                _print(f"  ⚠ 告警:")
            else:
                _print(f"  ⚠ Warnings:")
            for n in rep.notes:
                _print(f"    - {n}")
        if is_zh:
            _print(f"  提示:本 wizard 不写湍流/2T preset(由 sweep YAML 字段"
                   f" turbulence/two_temperature 或 REPL `turb`/`2t` 命令处理)。")
        else:
            _print(f"  Note: this wizard does not write turbulence/2T preset"
                   f" (use sweep YAML or REPL `turb`/`2t` commands).")
        return ("step_5_naming", {})

    def step_5a_pbs(self, data: dict):
        """v0.9.0 新增:询问 pbs 生成 + 任务名模板。"""
        from .pbs import extract_pbs_basename, render_pbs_name
        is_zh = get_lang() == "zh"
        pbs_enabled = confirm(
            "  是否生成 pbs 脚本?" if is_zh else "  Generate pbs script?",
            default=True,
        )
        pbs_naming = ""
        if pbs_enabled:
            detected = data.get("detected_pbs")
            base_basename = "case"
            if detected:
                base_basename = extract_pbs_basename(detected, max_len=8)
            multi_value: List[str] = []
            sweeps = data.get("sweeps") or {}
            for ax, vs in sweeps.items():
                if isinstance(vs, list) and len(vs) > 1:
                    multi_value.append(ax)
            first_params = {ax: vs[0] for ax, vs in sweeps.items() if isinstance(vs, list) and vs}
            suggested = render_pbs_name(
                params=first_params,
                multi_value_axes=multi_value,
                base_basename=base_basename,
            )
            if is_zh:
                _print(f"  pbs 任务名建议(可改): {suggested}")
            else:
                _print(f"  Suggested pbs job name: {suggested}")
            pbs_naming = input_text(
                "  任务名模板(空=接受建议,例 Mars-{alpha})" if is_zh else
                "  Naming template (empty=accept, e.g. Mars-{alpha})",
                default="",
            )
        return ("step_6_preview", {
            **data,
            "pbs_enabled": pbs_enabled,
            "pbs_naming": pbs_naming,
        })

    def step_6_preview(self, data: dict):
        """v0.8.2 起:预览 + 覆盖确认 + 执行合一(原 step_7 + step_8)。"""
        is_zh = get_lang() == "zh"
        if is_zh:
            _print("  预览(简化):")
            _print(f"    源目录: {data['source_dir']} (策略: {data.get('copy_strategy', 'hardlink')})")
            _print(f"    模板: {data['template']}")
            _print(f"    模式: {data['mode']}")
            _print(f"    输出: {data['output_dir']}")
            if data.get("naming"):
                _print(f"    命名: {data['naming']}")
        else:
            _print("  Preview (simplified):")
            _print(f"    Source: {data['source_dir']} (strategy: {data.get('copy_strategy', 'hardlink')})")
            _print(f"    Template: {data['template']}")
            _print(f"    Mode: {data['mode']}")
            _print(f"    Output: {data['output_dir']}")
            if data.get("naming"):
                _print(f"    Naming: {data['naming']}")
        if not confirm("  确认生成?", default=True):
            return None
        if is_zh:
            force = confirm("  目标子目录已存在时覆盖?", default=False)
        else:
            force = confirm("  Overwrite existing case subdirectories?", default=False)
        from .sweep import CaseSweep, generate, CopyStrategy
        cfg: Dict[str, Any] = {
            "template": data["template"],
            "output_dir": data["output_dir"],
        }
        mode = data.get("mode", "1")
        if mode == "4":
            cs = CaseSweep.from_csv(
                data["csv"],
                template=data["template"],
                output_dir=data["output_dir"],
                naming=data.get("naming"),
                manifest_path=data.get("manifest_path"),
            )
        else:
            if mode == "1":
                cfg["sweeps"] = data.get("sweeps", {})
            elif mode == "2":
                cfg["cases"] = data.get("cases", [])
            elif mode == "3":
                cfg["groups"] = data.get("groups", [])
            if data.get("naming"):
                cfg["naming"] = data["naming"]
            if data.get("manifest_path"):
                cfg["manifest"] = {"path": data["manifest_path"]}
            cs = CaseSweep.from_dict(cfg)
        # v0.8.2:source_dir 必填,直接注入 per_dir 模式
        cs.source_dir = data["source_dir"]
        cs.copy_strategy = CopyStrategy(data.get("copy_strategy", "hardlink"))
        # v0.9.0:pbs 注入(若 step_5a_pbs 设了)
        if data.get("pbs_enabled", False):
            from .pbs import PbsConfig
            cs.pbs = PbsConfig(
                enabled=True,
                naming=data.get("pbs_naming", ""),
            )
        report = generate(cs, force=force)
        _print(f"  生成 {report.total} 个算例 (整目录) → {data['output_dir']}")
        if data.get("manifest_path"):
            _print(f"  manifest → {data['manifest_path']}")

    def execute(self, data: dict) -> None:
        pass  # step_6_preview 完成


class WizardDiff(WizardBase):
    """比较两个 .inp 文件。3 步。"""
    title_zh = "向导:比较两个 .inp 文件"
    title_en = "Wizard: Compare two .inp files"
    description_zh = "用途:看两个 .inp 文件的字段差异(基准 vs 派生)。"
    description_en = "Purpose: See field differences between two .inp files (baseline vs derived)."

    @property
    def title(self) -> str:
        return self.title_zh if get_lang() == "zh" else self.title_en

    @property
    def description(self) -> str:
        return self.description_zh if get_lang() == "zh" else self.description_en

    steps = [
        "step_1_baseline",
        "step_2_other",
        "step_3_format",
    ]

    def step_1_baseline(self, data: dict):
        path = input_text("基准 .inp 路径")
        if not path:
            return None
        from pathlib import Path
        if not Path(path).is_file():
            _print(f"  文件不存在: {path}")
            return None
        return ("step_2_other", {"baseline": path})

    def step_2_other(self, data: dict):
        path = input_text("对比 .inp 路径")
        if not path:
            return None
        from pathlib import Path
        if not Path(path).is_file():
            _print(f"  文件不存在: {path}")
            return None
        return ("step_3_format", {"other": path})

    def step_3_format(self, data: dict):
        is_zh = get_lang() == "zh"
        if is_zh:
            choices = [
                ("1", "side-by-side(逐字段并排)", "side-by-side"),
                ("2", "unified diff", "unified diff"),
                ("3", "仅显示有差异的字段", "only changed"),
                ("Q", "取消", "(quit)"),
            ]
            prompt = "选择输出格式:"
        else:
            choices = [
                ("1", "side-by-side (field-by-field)", "side-by-side"),
                ("2", "unified diff", "unified diff"),
                ("3", "only changed fields", "only changed"),
                ("Q", "(quit)", "(quit)"),
            ]
            prompt = "Pick output format:"
        key = menu(prompt, choices, default="1")
        return ("__done__", {"format": key})

    def execute(self, data: dict) -> None:
        from .parser import parse_file
        from .diff import diff as diff_fn
        a = parse_file(data["baseline"])
        b = parse_file(data["other"])
        r = diff_fn(a, b)
        is_zh = get_lang() == "zh"
        _print(f"=== {data['baseline']} → {data['other']} ===")
        if is_zh:
            _print(f"差异条数: {len(r)}")
        else:
            _print(f"Change count: {len(r)}")
        for e in r.changes:
            _print(f"  {e}")


# ============================================================
# 菜单入口(无参 `wizard`)
# ============================================================
def run_menu(session: Optional[ReplSession] = None) -> None:
    """无参 wizard 入口。"""
    is_zh = get_lang() == "zh"
    if is_zh:
        choices = [
            ("1", "modify-file  修改单个 .inp 的来流参数", "modify-file"),
            ("2", "sweep        批量生成算例(交互式)", "sweep"),
            ("3", "diff         比较两个 .inp 文件的差异", "diff"),
            ("Q", "退出", "(quit)"),
        ]
        prompt = "═══ inp-tool 向导菜单 ═══\n请选择向导(输入编号):"
    else:
        choices = [
            ("1", "modify-file  edit single .inp freestream", "modify-file"),
            ("2", "sweep        batch-generate cases", "sweep"),
            ("3", "diff         compare two .inp files", "diff"),
            ("Q", "(quit)", "(quit)"),
        ]
        prompt = "═══ inp-tool wizard menu ═══\nPick a wizard (number):"
    try:
        key = menu(prompt, choices, default="1")
    except WizardCancel:
        if is_zh:
            _print("\n✗ 已退出向导。")
        else:
            _print("\n✗ Exited wizard menu.")
        return
    if key == "1":
        WizardModifyFile(session).run()
    elif key == "2":
        WizardSweep(session).run()
    elif key == "3":
        WizardDiff(session).run()


def run_modify_file(session: Optional[ReplSession] = None) -> None:
    WizardModifyFile(session).run()


def run_sweep(session: Optional[ReplSession] = None) -> None:
    WizardSweep(session).run()


def run_diff(session: Optional[ReplSession] = None) -> None:
    WizardDiff(session).run()
