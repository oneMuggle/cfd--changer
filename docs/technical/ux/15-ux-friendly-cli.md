# 计划:i18n + Wizard 任务向导(PR #2)

> **状态:** 进行中(2026-06-09)
> **对应版本:** v0.7.1
> **优先级:** 中-高
> **前置:** PR #1 (sweep 灵活化)已 merge → main
> **计划完工时:** 把本文件 + `2026-06-09_sweep-flexible.md` 一起归档到 `docs/technical/`,删空 `docs/plans/`

---

## 1. 背景

PR #1 解决了"灵活生成算例"问题(sweep 灵活化),但**用户体验**仍是英文+CLI 风格:

- REPL 提示、错误、help 全英文
- 单条命令的 help 只有一行
- 错误信息只说"哪里错",不说"怎么办"
- 没有任务向导(用户需要自己摸索命令组合)

PR #2 解决这些:**中文化 + 增强 help + 错误引导 + 任务向导**。

---

## 2. 目标

| # | 目标 | 验收 |
|---|------|------|
| G1 | REPL/CLI 提示中英可切换,默认中文 | `inp-tool --lang en` 切英文 |
| G2 | 单命令 help 4 段(用途/语法/示例/下一步) | `help set` 输出 ≥ 4 段 |
| G3 | 错误带下一步建议 | 错误后含"请试用 X"提示 |
| G4 | 3 个任务向导:`wizard` / `wizard modify-file` / `wizard sweep` / `wizard diff` | `wizard` 菜单可见,3 子向导走通 |
| G5 | 启动打印"快速开始"面板(5 命令) | REPL intro 后立即显示 |
| G6 | 向后兼容:老 CLI 不变,英文用户不被强切 | `--lang en` 完整回退 |
| G7 | 覆盖率 ≥ 80% | pytest + cov |
| G8 | 零新运行时依赖(纯 stdlib) | 纯 dict i18n |

---

## 3. 涉及文件

| 文件 | 动作 | 估行 |
|------|------|------|
| `inp_tool/inp_tool/i18n.py` (新) | 字典 + `t()` + `set_lang()` + `INP_TOOL_LANG` env | +200 |
| `inp_tool/inp_tool/repl.py` | `intro` / `prompt` / `help` / 错误中文化;`do_wizard` 入口 | +260 |
| `inp_tool/inp_tool/wizard.py` (新) | `WizardBase` + `WizardSession` + 3 个向导 | +580 |
| `inp_tool/inp_tool/cli.py` | `--lang` 顶层 flag + argparse 中文化 | +90 |
| `inp_tool/inp_tool/__init__.py` | 暴露 `i18n.t` | +5 |
| `inp_tool/tests/test_i18n.py` (新) | 字典齐整 / 占位符 / lang 切换 | +80 |
| `inp_tool/tests/test_repl_zh.py` (新) | 中文模式提示/错误/help | +60 |
| `inp_tool/tests/test_repl_help.py` (新) | 单命令 help ≥ 4 段 | +50 |
| `inp_tool/tests/test_wizard_modify_file.py` (新) | modify-file 5 步走通 | +80 |
| `inp_tool/tests/test_wizard_sweep.py` (新) | sweep 7 步走通(含 PR #1 新模式) | +100 |
| `inp_tool/tests/test_wizard_diff.py` (新) | diff 3 步走通 | +50 |
| `inp_tool/tests/test_wizard_menu.py` (新) | `wizard` 菜单 + 退出 | +40 |
| `docs/user-manual/README.md` (新) | 总览 + 章节目录 | +40 |
| `docs/user-manual/interactive/16-repl-quickstart.md` (新) | 5 命令快速上手 | +120 |
| `docs/user-manual/interactive/17-repl-tour.md` (新) | REPL 全功能指南 | +150 |
| `docs/user-manual/interactive/18-wizard-tasks.md` (新) | 3 个 wizard 详细用法 | +200 |
| `docs/technical/architecture/13-core-modules.md` | 加 i18n + wizard 模块说明 | +30 |
| `docs/technical/sweep/05-sweep-usage.md` | 加 wizard sweep 一节 | +40 |
| `CHANGELOG.md` | 加 v0.7.1 段 | +15 |
| **本计划文档** | 归档用 | +260 |
| **总计** | | **+2450 行** |

净代码 +1900(扣测试/文档/计划)。

---

## 4. 实施阶段

### 阶段 0 — 开工前

- [x] 0.1 写本计划
- [x] 0.2 分支:`git switch -c feat/ux-friendly-cli`
- [x] 0.3 基线:跑现有 301 测试确认绿(PR #1 已在 main)

### 阶段 1 — i18n 基础设施(TDD)

- [ ] 1.1 RED:`test_i18n.py` — 字典齐整 + `t()` 占位符 + lang 切换
- [ ] 1.2 GREEN:`i18n.py`:`MESSAGES` 字典 + `t(key, **kw)` + `set_lang(zh|en)`
- [ ] 1.3 GREEN:环境变量 `INP_TOOL_LANG` 兜底
- [ ] 1.4 准备 ~80 条中文字符串(REPL / help / errors / wizard)

### 阶段 2 — REPL 中文化

- [ ] 2.1 RED:`test_repl_zh.py` — zh 模式提示/错误/help 含中文
- [ ] 2.2 GREEN:`repl.py` `intro` / `prompt` / `_err` 走 `t()`
- [ ] 2.3 GREEN:启动后打印"快速开始"面板
- [ ] 2.4 GREEN:`do_help` 重写:分组 + 单命令 4 段

### 阶段 3 — Wizard 基础设施

- [ ] 3.1 `WizardBase` 抽象基类(步骤定义 + 公共流程)
- [ ] 3.2 `WizardSession` 状态机(当前步骤 / 历史 / 取消)
- [ ] 3.3 通用 `menu(prompt, choices, default)` 组件
- [ ] 3.4 通用 `confirm(question, default)` 组件(已有 `_confirm` 复用)
- [ ] 3.5 `wizard` 菜单入口 + `do_wizard` 分发

### 阶段 4 — `wizard modify-file`(最高优先级)

- [ ] 4.1 5 步:选文件 → 选字段 → 输值 → 预览 → 选输出
- [ ] 4.2 测试:每步选择/输入/确认覆盖
- [ ] 4.3 集成 REPL: `wizard modify-file` 调用 + 完成后 dirty 状态

### 阶段 5 — `wizard sweep`(用 PR #1 能力)

- [ ] 5.1 7 步:模板 → 模式 → 填参 → 命名 → 输出 → 预览 → 执行
- [ ] 5.2 步骤 2 模式选项:1=笛卡尔, 2=cases, 3=groups, 4=CSV
- [ ] 5.3 模式 4(CSV)走 from_csv,模板在步骤 1 收集
- [ ] 5.4 测试:每个模式走通

### 阶段 6 — `wizard diff`

- [ ] 6.1 3 步:基准 → 对比 → 输出格式 → 结果
- [ ] 6.2 测试

### 阶段 7 — CLI 层面

- [ ] 7.1 RED:测试 `inp-tool --lang en` 输出英文
- [ ] 7.2 GREEN:`cli.py` 顶层 `--lang` flag + `set_lang()`
- [ ] 7.3 GREEN:`inp-tool --help` 中文化
- [ ] 7.4 GREEN:subparser description/epilog 中文化

### 阶段 8 — 文档

- [ ] 8.1 `docs/user-manual/README.md`(总览 + 章节目录)
- [ ] 8.2 `docs/user-manual/interactive/16-repl-quickstart.md`(5 命令快速上手)
- [ ] 8.3 `docs/user-manual/interactive/17-repl-tour.md`(REPL 全功能)
- [ ] 8.4 `docs/user-manual/interactive/18-wizard-tasks.md`(3 个 wizard 详细)
- [ ] 8.5 `docs/technical/architecture/13-core-modules.md` 加 i18n + wizard
- [ ] 8.6 `docs/technical/sweep/05-sweep-usage.md` 加 wizard sweep 一节
- [ ] 8.7 `CHANGELOG.md` 加 v0.7.1 段

### 阶段 9 — 归档 + 收尾

- [ ] 9.1 把 `2026-06-09_sweep-flexible.md` + `2026-06-09_ux-friendly-cli.md` 移到 `docs/technical/`
- [ ] 9.2 删空 `docs/plans/`
- [ ] 9.3 跑全量测试 + 覆盖率 ≥ 80%
- [ ] 9.4 smoke:`inp-tool shell` zh/en 都试
- [ ] 9.5 commit(走 conventional commits,可能 1 个大 commit 或拆 2 个)
- [ ] 9.6 push + 开 PR
- [ ] 9.7 监控 CI,merge 后清理分支
- [ ] 9.8 打 v0.7.1 tag + push tag(可选,等用户确认)

---

## 5. 数据模型(i18n 关键)

```python
# inp_tool/i18n.py
from typing import Any
import os

_CURRENT_LANG = os.environ.get("INP_TOOL_LANG", "zh")

MESSAGES: dict[str, dict[str, str]] = {
    "zh": {
        "repl.intro": "inp-tool {ver} 交互式外壳",
        "repl.welcome": "欢迎使用 inp-tool!输入 `tutorial` 走完 5 步快速上手,`wizard` 走任务向导。",
        "repl.quickstart.title": "快速开始(5 个最常用命令):",
        "repl.prompt": "inp> ",
        "error.no_file_current": "尚未加载文件。请先用 `load <路径>` 加载 .inp 文件",
        ...
    },
    "en": {
        "repl.intro": "inp-tool {ver} interactive shell",
        "repl.welcome": "Welcome! Type `tutorial` for 5-step onboarding, `wizard` for task wizards.",
        ...
    },
}


def t(key: str, **kwargs: Any) -> str:
    """取当前语言的字符串,支持 {name} 占位符"""
    msg = MESSAGES[_CURRENT_LANG].get(key)
    if msg is None:
        raise KeyError(f"i18n: missing key {key!r} in {_CURRENT_LANG}")
    if kwargs:
        msg = msg.format(**kwargs)
    return msg


def set_lang(lang: str) -> None:
    """切换语言:zh / en"""
    global _CURRENT_LANG
    if lang not in MESSAGES:
        raise ValueError(f"i18n: unsupported language {lang!r}")
    _CURRENT_LANG = lang
```

---

## 6. Wizard 抽象(关键)

```python
# inp_tool/wizard.py
from typing import Callable, Optional


class WizardBase:
    """所有任务向导的基类。每个 step 是一个方法,返回 (next_step_id, data)。

    步骤:
    - 接收 step_id 和上一步累积的 data
    - 走自己的一次性交互(input / menu / confirm)
    - 返回 (None, data) 完成,或 (next_id, data) 进入下一步
    - 抛 WizardCancel 取消
    """
    title: str = ""  # 向导名(给菜单显示)
    steps: list[str] = []  # step 方法名列表

    def run(self, start_data: Optional[dict] = None) -> None:
        data = start_data or {}
        step_id = self.steps[0]
        for step_name in self.steps:
            method = getattr(self, step_name)
            print(f"\n──── {step_name} ────")  # i18n 化
            result = method(data)
            if result is None:
                print("cancelled")
                return
            next_id, new_data = result
            data.update(new_data)
        # 全部完成 → 执行 final action
        self.execute(data)

    def execute(self, data: dict) -> None:
        raise NotImplementedError


class WizardCancel(Exception):
    pass


# 具体向导 modify-file / sweep / diff 实现继承 WizardBase
```

---

## 7. 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| HIGH | REPL 中文化破坏现有 test_repl.py | 阶段 2 先写 zh 测试,跑全量确认无回归 |
| HIGH | 字典不一致 / 缺 key 运行时崩 | `t()` 缺 key 抛 KeyError,测试覆盖 |
| MEDIUM | Wizard 状态机有 bug | 阶段 3 写 WizardBase 测试 + 多次 mock input |
| MEDIUM | CLI --lang 与现有 subparser flag 冲突 | 顶层加,subparser 内不再加 |
| LOW | 中文字符在某些终端乱码 | 沿用现有 UTF-8 输出策略 + 测试覆盖 |
| LOW | 用户手册质量参差 | 阶段 8 一次性写,简洁实用 |

---

## 8. 兼容性

- **API:** 新增 `i18n.t` / `i18n.set_lang` 公开符号
- **CLI:** `--lang` flag,默认 zh(老用户用 `--lang en` 切回)
- **REPL:** 中文模式下 prompt 仍 `inp> `(命令名短,无需中文化)
- **测试:** 现有 301 全绿 + ~50 新测试 = 351

---

## 9. 不在本次范围

- ❌ Web GUI 中文化
- ❌ 日 / 韩语等第三语种(架构上支持,本次不写)
- ❌ `tutorial`(教学)— 可选保留,本次不动
- ❌ `wizard convert` / `wizard backup`(v1.1 路线图)
- ❌ 修改 `parser/writer/model/diff` API

---

## 10. 验收

- [ ] 现有 301 测试全绿(零行为变化)
- [ ] ~50 新测试全绿
- [ ] 覆盖率 ≥ 80%
- [ ] `inp-tool shell` zh 模式跑通(中英切换)
- [ ] 3 个 wizard 全部走通
- [ ] `docs/user-manual/` 4 个文件
- [ ] CHANGELOG v0.7.1 段
- [ ] PR merge 到 main
- [ ] PR #1 + PR #2 plans 归档到 docs/technical/,删空 plans/

---

## 11. 实施顺序图

```
阶段 0 ─ 计划归档 + 分支
   ↓
阶段 1 ─ i18n(独立,可单独测)
   ↓
阶段 2 ─ REPL 用 i18n(中文提示)
   ↓
阶段 3 ─ Wizard 基础(独立)
   ↓
阶段 4 ─ wizard modify-file
   ↓
阶段 5 ─ wizard sweep(用 PR #1 能力)
   ↓
阶段 6 ─ wizard diff
   ↓
阶段 7 ─ CLI --lang(用 i18n)
   ↓
阶段 8 ─ 文档
   ↓
阶段 9 ─ 归档 + 收尾 + PR
```

---

## 12. 关键设计点(最终版)

- **Q1:** 3 个向导(已确定)
- **Q2:** 默认 zh(已确定)
- **Q3:** 纯 dict i18n(已确定)
- **Q4:** `--lang` + `INP_TOOL_LANG` env(已确定)
- **Q5:** help 4 段(已确定)
- **Q6:** 错误带建议(已确定)
- **Q7:** tutorial 保留(已确定,本次不动)
- **Q8:** 归档时机 = PR #2 完工时(本计划落地)
