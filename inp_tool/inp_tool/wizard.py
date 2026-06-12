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
# v0.10.0+:helper 函数
# ============================================================
def _read_template_value(
    template_path: str, block_name: str, key: str, default: float,
) -> float:
    """从 template .inp 读 guiopts.x 或 physics.x,转 float,失败用 default。

    任何异常(missing file / parse error / missing block / unparseable value)
    都静默回退到 default — wizard 不因默认值读取失败而中断流程。
    """
    try:
        from .parser import parse_file
        inp = parse_file(template_path)
        b = inp.get_block(block_name)
        if b is None:
            return default
        v = b.get(key)
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


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


def multi_menu(
    prompt: str,
    choices: List[Tuple[str, str, str]],
) -> List[str]:
    """v0.10.0+ 多选菜单(单行 token 输入)。

    输入约定(任选其一,空格或逗号分隔 token):
      - 数字 key:"1 3" 或 "1,3" → 选 [1, 3]
      - value 串:"sst sa" → 选 [sst, sa](case-insensitive 匹配)
    空输入 / 纯空格 → [] (等于跳过该 axis)。
    任一 token 无效 → 整行重输(不静默丢弃)。

    choices: [(key, "label_zh", "label_en"), ...]
    返回:选中的 key 对应 choice 第 4 元素 value 的列表(保序去重)。
    """
    is_zh = get_lang() == "zh"
    key_to_value: Dict[str, str] = {}
    value_to_key: Dict[str, str] = {}
    for key, _, _, value in _iter_choice4(choices):
        key_to_value[key.upper()] = value
        value_to_key[value.lower()] = key
    _print(prompt)
    for key, label_zh, label_en, _ in _iter_choice4(choices):
        label = label_zh if is_zh else label_en
        _print(f"  [{key}] {label}")
    while True:
        try:
            raw = input("> (空格/逗号分隔,空=跳过): ")
        except (EOFError, KeyboardInterrupt):
            raise WizardCancel()
        # 规范化:替换逗号为空格,再 split
        tokens = raw.replace(",", " ").split()
        if not tokens:
            return []  # 空 → 跳过
        # 检查每个 token 是否有效
        invalid = []
        for tok in tokens:
            t_upper = tok.upper()
            t_lower = tok.lower()
            if t_upper not in key_to_value and t_lower not in value_to_key:
                invalid.append(tok)
        if invalid:
            if is_zh:
                _print(f"  无效 token: {invalid!r},请重试。")
            else:
                _print(f"  Invalid token(s): {invalid!r}, please retry.")
            continue
        # 收集 value(去重保序)
        seen = set()
        result: List[str] = []
        for tok in tokens:
            t_upper = tok.upper()
            t_lower = tok.lower()
            if t_upper in key_to_value:
                value = key_to_value[t_upper]
            else:
                value = key_to_value[value_to_key[t_lower]]
            if value not in seen:
                seen.add(value)
                result.append(value)
        return result


def _iter_choice4(choices: List[Tuple[str, str, str]]):
    """把 3-tuple choices 当作 4-tuple(value 复用 key 当 fallback)迭代。

    允许调用方传 [(key, "zh", "en")] 或 [(key, "zh", "en", "value")];
    缺 value 时用 key 作 value(给某些复用场景使用)。
    """
    for c in choices:
        if len(c) == 4:
            yield c
        else:
            key, zh, en = c[0], c[1], c[2]
            yield (key, zh, en, key)


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
        "step_3_mode",                 # 用户选 "1"(Cartesian)才进 4b
        "step_4_params",
        "step_4b_equation_axes",       # v0.10.0+:Cartesian 选 turbulence/energy/gas 轴
        "step_4a_detect",              # v0.9.1 + v0.10.0+:消费 sweeps_equation_warnings
        "step_4c_equation_overrides",  # v0.10.0+:per-case I/L/U 或温度(4b 选了 axis 才出现)
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
            return ("step_4b_equation_axes", {"sweeps": sweeps})
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
            return ("step_4b_equation_axes", {"cases": cases})
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
            return ("step_4b_equation_axes", {"groups": groups})
        elif mode == "4":
            csv_path = input_text("  CSV 文件路径")
            if not csv_path:
                return None
            from pathlib import Path
            if not Path(csv_path).is_file():
                _print(f"  文件不存在: {csv_path}")
                return None
            return ("step_4b_equation_axes", {"csv": csv_path})
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

        v0.10.0+:把 data["intended_axes"] 传给 detect_equations,末尾消费
        rep.sweeps_equation_warnings 显示给用户。

        纯展示步骤,无交互。检测失败不阻断。
        """
        from .parser import parse_file
        from .equations import detect_equations
        is_zh = get_lang() == "zh"
        template = data.get("template")
        if not template:
            return ("step_4c_equation_overrides", {})
        try:
            inp = parse_file(template)
            intended = data.get("intended_axes")
            rep = detect_equations(inp, intended_axes=intended)
        except Exception as e:
            if is_zh:
                _print(f"  ⚠ 检测失败(跳过):{e}")
            else:
                _print(f"  ⚠ Detection failed (skipping): {e}")
            return ("step_4c_equation_overrides", {})
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
                _print(f"  ⚠ 告警(方程检测自身):")
            else:
                _print(f"  ⚠ Warnings (equation detection):")
            for n in rep.notes:
                _print(f"    - {n}")
        # v0.10.0+:消费 sweeps_equation_warnings
        if rep.sweeps_equation_warnings:
            if is_zh:
                _print(f"  ⚠ 你选的 axis 与 template 不兼容:")
            else:
                _print(f"  ⚠ Selected axis incompatible with template:")
            for w in rep.sweeps_equation_warnings:
                _print(f"    - {w}")
        if is_zh:
            _print(f"  提示:本 wizard 不写湍流/2T preset(由 sweep YAML 字段"
                   f" turbulence/two_temperature 或 REPL `turb`/`2t` 命令处理)。")
        else:
            _print(f"  Note: this wizard does not write turbulence/2T preset"
                   f" (use sweep YAML or REPL `turb`/`2t` commands).")
        return ("step_4c_equation_overrides", {})

    def step_4b_equation_axes(self, data: dict):
        """v0.10.0+:引导用户按 turbulence/energy/gas 3 个轴 sweep。

        仅 Cartesian(mode="1")走;其他 mode 静默跳到 step_4a_detect。
        全 skip → 不注入 sweeps;任一轴选 → 合并到 data["sweeps"](保留 step_4_params
        已填的 alpha/mach 等)。同时记 intended_axes,供 step_4a_detect 末尾检测
        与 template 是否不兼容并显示 warning。
        """
        is_zh = get_lang() == "zh"
        # Cartesian gate
        if data.get("mode") != "1":
            return ("step_4a_detect", data)
        # 默认 sweeps(保留 step_4_params 注入的)
        sweeps: Dict[str, Any] = dict(data.get("sweeps") or {})
        intended: Dict[str, str] = {}

        # Q1: turbulence
        if is_zh:
            q1 = "  要按湍流模型扫吗?"
        else:
            q1 = "  Sweep by turbulence?"
        if confirm(q1, default=False):
            choices = [
                ("1", "sst (k-omega-sst)", "sst (k-omega-sst)", "sst"),
                ("2", "sa (spalart-allmaras)", "sa (spalart-allmaras)", "sa"),
                ("3", "k-eps (realizable)", "k-eps (realizable)", "keps"),
                ("4", "goldberg", "goldberg", "goldberg"),
                ("5", "laminar", "laminar", "laminar"),
            ]
            picked = multi_menu("  选湍流模型(空格/逗号分隔多选):", choices)
            if picked:
                sweeps["turbulence"] = picked
                intended["turbulence"] = picked[0]

        # Q2: energy
        if is_zh:
            q2 = "  要按能量模型扫吗?"
        else:
            q2 = "  Sweep by energy model?"
        if confirm(q2, default=False):
            choices = [
                ("1", "none (完美气体)", "none (perfect gas)", "none"),
                ("2", "2t (双温)", "2t (two-temp)", "2t"),
            ]
            picked = multi_menu("  选能量模型:", choices)
            if picked:
                sweeps["energy"] = picked
                intended["energy"] = picked[0]

        # Q3: gas
        if is_zh:
            q3 = "  要按气体类型扫吗?"
        else:
            q3 = "  Sweep by gas type?"
        if confirm(q3, default=False):
            choices = [
                ("1", "perfect-gas", "perfect-gas", "perfect-gas"),
                ("2", "real-gas", "real-gas", "real-gas"),
                ("3", "multi-temp", "multi-temp", "multi-temp"),
            ]
            picked = multi_menu("  选气体类型:", choices)
            if picked:
                sweeps["gas"] = picked
                intended["gas"] = picked[0]

        new_data = dict(data)
        new_data["sweeps"] = sweeps
        if intended:
            new_data["intended_axes"] = intended
        return ("step_4a_detect", new_data)

    def step_4c_equation_overrides(self, data: dict):
        """v0.10.0+:per-case 覆盖 I/L/U_ref(turbulence)或温度(energy)。

        触发条件:Cartesian + step_4b 选了至少 1 个 equation axis。
        Q0: 是否要 per-case 覆盖?Y/n
          Y → 进入子循环:
            - 若 sweeps 含 turbulence: 选湍流 model + 输 I/L/U_ref → 再来?
            - 若 sweeps 含 energy: 选能量 model + 输 T_trans/T_vib 或 reftem
        Q3: 再来一个湍流覆盖?Y/n(只对 turbulence 循环;YAGNI 不对 energy 循环)

        字段:
        - data["turbulence"] = {I, L, U_ref, overrides: {<key>: {I, L, U_ref}}}
        - data["energy_overrides"] = {"2T": {T_trans, T_vib}, "none": {reftem}}
        """
        is_zh = get_lang() == "zh"
        # Gate
        if data.get("mode") != "1":
            return ("step_5_naming", data)
        sweeps = data.get("sweeps") or {}
        has_turb = bool(sweeps.get("turbulence"))
        has_energy = bool(sweeps.get("energy"))
        if not (has_turb or has_energy):
            return ("step_5_naming", data)

        # Q0
        if is_zh:
            q0 = "  要给某些 case 设单独的 I/L/U 或温度吗?"
        else:
            q0 = "  Override I/L/U or T for some cases?"
        if not confirm(q0, default=False):
            return ("step_5_naming", data)

        template = data.get("template")
        new_data = dict(data)
        turb_out: Dict[str, Any] = {}   # {key: {I, L, U_ref}}
        energy_out: Dict[str, Any] = {}  # {"2T": {T_trans, T_vib}, "none": {reftem}}

        # Turbulence loop
        if has_turb:
            tur_choices = [
                ("1", "sst (k-omega-sst)", "sst (k-omega-sst)"),
                ("2", "sa (spalart-allmaras)", "sa (spalart-allmaras)"),
                ("3", "k-eps (realizable)", "k-eps (realizable)"),
                ("4", "goldberg", "goldberg"),
            ]
            tur_value = {"1": "sst", "2": "sa", "3": "keps", "4": "goldberg", "5": "__skip__"}
            skip_zh = "(跳过湍流覆盖)"
            skip_en = "(skip turbulence override)"
            if is_zh:
                choices = tur_choices + [("5", skip_zh, skip_zh)]
            else:
                choices = tur_choices + [("5", skip_en, skip_en)]
            while True:
                key = menu("  覆盖哪个湍流模型?", choices, default="5")
                picked = tur_value[key]
                if picked == "__skip__":
                    break
                # 输 I/L/U_ref
                default_I = _read_template_value(
                    template or "", "guiopts", "turbi_tlev", 0.01,
                )
                default_L = _read_template_value(
                    template or "", "guiopts", "turbi_len", 0.01,
                )
                default_U = _read_template_value(
                    template or "", "physics", "refvel", 204.0,
                )
                I_str = input_text(
                    f"    {picked} 湍流强度 I (默认 {default_I})",
                    default=str(default_I),
                )
                L_str = input_text(
                    f"    {picked} 特征长度 L (默认 {default_L})",
                    default=str(default_L),
                )
                U_str = input_text(
                    f"    {picked} 参考速度 U_ref (默认 {default_U})",
                    default=str(default_U),
                )
                try:
                    turb_out[picked] = {
                        "I": float(I_str),
                        "L": float(L_str),
                        "U_ref": float(U_str),
                    }
                except ValueError:
                    if is_zh:
                        _print(f"  ⚠ 输入非法,跳过 {picked} 覆盖")
                    else:
                        _print(f"  ⚠ Invalid input, skip {picked} override")
                # Q3: 再来?
                if not confirm(
                    "  再选一个湍流覆盖?" if is_zh else
                    "  Another turbulence override?", default=False,
                ):
                    break

        # Energy (一次,YAGNI 不循环)
        if has_energy:
            energy_choices = [
                ("1", "2t (双温)", "2t (two-temp)"),
                ("2", "none (完美气体)", "none (perfect gas)"),
            ]
            energy_value = {"1": "2t", "2": "none", "3": "__skip__"}
            skip_zh = "(跳过能量覆盖)"
            skip_en = "(skip energy override)"
            if is_zh:
                energy_choices.append(("3", skip_zh, skip_zh))
            else:
                energy_choices.append(("3", skip_en, skip_en))
            key = menu("  覆盖哪个能量模型?", energy_choices, default="3")
            picked = energy_value[key]
            if picked != "__skip__":
                if picked == "2t":
                    default_T = _read_template_value(
                        template or "", "physics", "reftem", 300.0,
                    )
                    T_trans = input_text(
                        f"    2T 平动温度 T_trans (默认 {default_T})",
                        default=str(default_T),
                    )
                    T_vib = input_text(
                        "    2T 振动温度 T_vib (默认 300.0)",
                        default="300.0",
                    )
                    try:
                        energy_out["2T"] = {
                            "T_trans": float(T_trans),
                            "T_vib": float(T_vib),
                        }
                    except ValueError:
                        if is_zh:
                            _print("  ⚠ 输入非法,跳过 2T 覆盖")
                        else:
                            _print("  ⚠ Invalid input, skip 2T override")
                elif picked == "none":
                    default_T = _read_template_value(
                        template or "", "physics", "reftem", 300.0,
                    )
                    reftem = input_text(
                        f"    none 平衡温度 reftem (默认 {default_T})",
                        default=str(default_T),
                    )
                    try:
                        energy_out["none"] = {"reftem": float(reftem)}
                    except ValueError:
                        if is_zh:
                            _print("  ⚠ 输入非法,跳过 none 覆盖")
                        else:
                            _print("  ⚠ Invalid input, skip none override")

        # 合并到 data
        if turb_out:
            # 顶层默认取第一个(或用 template 默认 — 这里用第一个 override 复制上去)
            first = next(iter(turb_out.values()))
            new_data["turbulence"] = {
                "I": first["I"],
                "L": first["L"],
                "U_ref": first["U_ref"],
                "overrides": turb_out,
            }
        if energy_out:
            new_data["energy_overrides"] = energy_out

        return ("step_5_naming", new_data)

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
            # v0.10.0+:step_4c 产出必须接入(C1)— 否则用户在 wizard 输的
            # I/L/U_ref / 温度覆盖被静默丢弃
            if data.get("turbulence"):
                cfg["turbulence"] = data["turbulence"]
            if data.get("energy_overrides"):
                cfg["energy_overrides"] = data["energy_overrides"]
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
