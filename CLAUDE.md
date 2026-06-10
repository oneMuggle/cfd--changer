# CLAUDE.md — cfd--changer 项目约束

> 本文件是给 Claude Code 在本项目中工作的硬性约束。优先级高于 `~/.claude/rules/*` 中的全局规则。
> 适用范围:整个 `/home/fz/project/cfd--changer` 仓库。

---

## 1. Python 环境(强约束)

**禁止使用 base 环境。** 任何 Python / pip / pytest / mypy 操作必须通过 conda 激活 `cfdchanger` 环境。

### 1.1 命名与位置

| 项 | 值 |
|---|---|
| Conda 环境名 | `cfdchanger` |
| Python 版本 | **3.8**(LTS 兼容 Win7) |
| 创建命令 | `conda create -n cfdchanger python=3.8 -y` |
| 激活命令 | `conda activate cfdchanger` |

### 1.2 调用方式

**正确做法**(`conda run` 避免污染 shell 状态):
```bash
conda run -n cfdchanger python -m pytest
conda run -n cfdchanger pip install -e .[api,dev]
conda run -n cfdchanger python -m inp_tool.cli info mcfd.inp
```

**禁止做法**:
```bash
python -m pytest           # 走 base 环境,污染全局
pip install ...            # 装到 base,污染全局
conda activate cfdchanger  # 改变 shell 状态,harness 不友好
```

### 1.3 验证环境正确性

每次进入新会话或长任务开始前,执行:
```bash
conda run -n cfdchanger python -c "import sys; assert sys.version_info[:2] == (3, 8); print('OK', sys.version)"
```

若不是 3.8.x,**立刻停止**并向用户报告,不要尝试在 base 环境跑。

### 1.4 平台兼容性约束

| 项 | 约束 |
|---|---|
| 目标平台 | **Windows 7 / Windows 10 / Linux** 三平台同代码可运行 |
| Python | **≥ 3.8, ≤ 3.12**(3.8 是 Win7 兼容下限) |
| `inp_tool` 核心 | **零运行时依赖**(纯 stdlib) |
| `inp_tool` `[api]` | `fastapi`/`uvicorn`/`pydantic` + `eval_type_backport` (3.8 兼容) |
| `inp_tool` `[dev]` | `pytest`/`pytest-cov`/`httpx` |
| 禁止使用 | PEP 604 `X \| Y` 联合语法(Pydantic 在 3.8 评估失败,即使有 `from __future__ import annotations`);Pydantic field 注解中直接用 `list[dict]` 等 PEP 585 内建下标 |

### 1.5 代码规范对 3.8 的影响

允许的(经 `from __future__ import annotations` 转字符串后,3.8 也能 import):
- `list[X]`, `dict[K, V]`, `tuple[X, ...]`, `set[X]`(PEP 585)
- `X | Y`(PEP 604)用于**非 Pydantic 字段**的标注

不允许的(Pydantic 字段实际求值):
- Pydantic `BaseModel` 字段中用 `list[dict]` 等 PEP 585 内建下标

**首选写法** —— Pydantic 字段一律 `typing.List[typing.Dict]` 等老式构造,即便高版本也用 `Optional[X]` 而非 `X | None`:
```python
from typing import List, Dict, Optional
class Foo(BaseModel):
    items: List[Dict[str, int]]
    name: Optional[str] = None
```

非 Pydantic 标注可保持 `list[X]` 风格(因为 `from __future__ import annotations` 不会求值)。

---

## 2. 项目结构(速查)

```
cfd--changer/
├── inp_tool/             # mcfd.inp 解析/修改/diff + sweep 批量生成
│   ├── inp_tool/         # 包本体
│   ├── tests/            # 55+ pytest
│   ├── examples/         # 样例 .inp + demo.py
│   └── pyproject.toml    # requires-python = ">=3.8"
├── scripts/              # 翻译/批处理脚本(Windows 路径硬编码)
├── analysis_v2/          # CFD++ GUI 调用关系分析
├── docs/
│   ├── README.md         # 顶层文档索引
│   ├── plans/            # 进行中的通用计划(完成后删除)
│   ├── user-manual/      # 终端用户手册(总览+分章)
│   ├── technical/        # 开发者技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph(老项目静态)
│   └── superpowers/      # brainstorming/PRP 工作流产物
│       ├── specs/        # 设计文档(保留, 含 STATUS 头)
│       └── plans/        # 工作流生成的 implementation plan(完成后删除)
└── README.md
```

---

## 3. 工作流约束

### 3.1 计划先行

新功能模块 / 跨模块集成 / 架构级变更 → **必须**先在 `docs/plans/<YYYY-MM-DD>_<name>.md` 写计划,含:
- 背景与目标
- 涉及文件
- 技术方案
- 实施步骤(checkbox 化)
- 风险评估

完成后归档至 `docs/technical/`,**删除** `docs/plans/` 中的原文件(不保留历史)。

> 特殊地,使用 brainstorming/PRP 工作流(superpowers skill)时, plan 可放在 `docs/superpowers/plans/`(完成后同样删除); 对应设计文档保留在 `docs/superpowers/specs/` 并更新 `**Status:**` 行。

### 3.2 TDD

非 trivial 功能 → 写测试 → 看 RED → 实现 → 看 GREEN → 重构。覆盖率 ≥ 80%。

### 3.3 Git

- 默认分支 `main`,所有新工作在新分支(用 `git switch -c <branch>`)
- 提交信息用 conventional commits(`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`)
- 推送前 `git status` 自检:不留 `.bak`/`.log`/`__pycache__`

### 3.4 进度报告

所有进度汇报、总结、状态更新**必须用中文**(代码、命令、技术术语、API 名保留原文)。

---

## 4. 禁止事项

- ❌ 在 `base` 环境安装任何包(`pip install` 不带 `conda run -n cfdchanger`)
- ❌ 把 `bash.exe.stackdump`、`*.bak`、`__pycache__` 提交进 git
- ❌ 修改 `parser/writer/model/diff` 的对外 API(向后兼容)
- ❌ 引入 PyYAML 等重依赖到 inp_tool 核心(可走 `[yaml]` extras)
- ❌ 在 Linux 路径下硬编码 `E:\...` / `C:\...` Windows 路径(在 `scripts/` 下除外,那里是已存在的 Windows 工具)
- ❌ 修改本文件不与用户确认(本约束是用户显式要求的)
