# 12 — inp_tool 架构总览

**包名:** `inp-tool`  ·  **版本:** v0.4.2  ·  **状态:** 当前主线

---

## 1. 一句话

`inp_tool` 是一个**零依赖的纯 stdlib** Python 包,提供 `mcfd.inp` 的解析、修改、写回、diff、批量生成(sweep)能力,并暴露 CLI / Python API / FastAPI / Web GUI 四种入口。

---

## 2. 包结构

```
inp_tool/                         # 项目根
├── inp_tool/                     # Python 包本体(7 个 .py)
│   ├── __init__.py               # 公共导出(22 个符号) + __version__
│   ├── __main__.py               # `python -m inp_tool` 入口
│   ├── model.py                  # 数据模型(InpFile / Block / Stmt / Value)
│   ├── parser.py                 # 文本 → InpFile
│   ├── writer.py                 # InpFile → 文本
│   ├── diff.py                   # 两个 InpFile → DiffReport
│   ├── sweep.py                  # 批量算例生成(v0.4 增量)
│   ├── cli.py                    # argparse CLI → inp-tool
│   └── api.py                    # FastAPI → inp-tool-api
│
├── tests/                        # 14 个 test_*.py(134 用例)
│   ├── conftest.py               # 公共 fixture
│   ├── test_parser.py            # parser 单测
│   ├── test_writer.py            # writer 单测
│   ├── test_diff.py              # diff 单测
│   ├── test_cli.py               # CLI 端到端
│   ├── test_api.py               # FastAPI TestClient
│   ├── test_completion.py        # shell 补全
│   ├── test_packaging.py         # entry_points / extras / 版本
│   ├── test_sweep*.py            # sweep 7 个测试模块
│   └── ...
│
├── examples/                     # 示例 .inp + demo
│   ├── mcfd_modified.inp         # 真实样本
│   ├── sweep_demo.{json,yaml,py} # sweep 演示配置
│   └── demo.py                   # 端到端 demo
│
├── web/                          # Web GUI 静态资源
│   └── index.html                # 单文件 SPA(由 api.py mount 为 /)
│
├── pyproject.toml                # PEP 621 元数据 + entry_points
├── inp_tool.spec / inp_tool_onedir.spec   # PyInstaller 打包
└── README.md
```

### 2.1 七个 `.py` 文件职责

| 文件 | 行数(约) | 职责 | 关键 API |
|---|---|---|---|
| `__init__.py` | 42 | 公共导出 + `__version__` | 22 个 `__all__` 符号 |
| `__main__.py` | < 10 | `python -m inp_tool` 转发到 `cli.main` | — |
| `model.py` | ~150 | 数据模型 dataclass | `InpFile` / `Block` / `Stmt` / `Value` / `infer_type()` |
| `parser.py` | ~210 | mcfd.inp 文本 → `InpFile` | `parse(text)` / `parse_file(path)` |
| `writer.py` | ~170 | `InpFile` → 文本 | `to_text(inp)` / `write(inp, path)` / `write_bytes(inp)` |
| `diff.py` | ~180 | 两个 InpFile 对比 | `diff(a, b)` → `DiffReport` / `DiffEntry` |
| `sweep.py` | ~430 | 批量算例生成(v0.4) | `CaseSweep` / `generate()` / `FreestreamPreset` |
| `cli.py` | ~480 | argparse CLI 调度 | `main()`(被 `inp-tool` 入口调用) |
| `api.py` | ~330 | FastAPI 暴露 REST + 静态 | `app` / `main()`(被 `inp-tool-api` 入口调用) |

> 备注:`__init__.py` 与 `__main__.py` 加起来仅 ~50 行,本质是薄壳。其余 6 个文件是核心。

---

## 3. 模块依赖图

```
                 ┌──────────┐
                 │ model.py │  ←  数据模型(dataclass)
                 └────┬─────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
   ┌────────┐   ┌────────┐    ┌────────┐
   │parser.py│   │writer.py│   │ diff.py │   ←  v0.2 基础三件套
   └───┬────┘   └────┬────┘    └────┬────┘
       │            │              │
       └────────────┴──────────────┘
                    │
                    ▼
             ┌──────────┐
             │ sweep.py │  ←  v0.4 批量生成
             └────┬─────┘
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
   ┌───────┐ ┌───────┐ ┌─────────┐
   │cli.py │ │api.py │ │web/index│  ←  四个入口
   └───────┘ └───┬───┘ │  .html  │
                │     └─────────┘
                │(mount /)
                ▼
          FastAPI StaticFiles
```

- **下层无环**: `model` 是叶子,`parser/writer/diff` 只依赖 `model`,`sweep` 依赖前三者,`cli/api` 是最外层。
- **核心零依赖**: 灰色框(parser / writer / model / diff / sweep)只 import stdlib。

---

## 4. 三条数据流

### 4.1 parse → modify → write(主流程)

```
.mcfd.inp 文件
   │  parse_file(path)
   ▼
InpFile 对象(model.py)
   │  in-memory 任意修改
   │  (inp.get_block(...).set_value(...))
   ▼
InpFile 对象(已修改)
   │  write(inp, out_path)
   ▼
新的 .inp 文件
```

**典型场景:** 把模板里 `mach` 从 0.6 改成 0.8,改完写回,验证 round-trip。

### 4.2 diff(对比)

```
.mcfd.inp (A)  ──┐
                 ├──> diff(a, b) ──> DiffReport
.mcfd.inp (B)  ──┘
```

- 输出 `DiffEntry` 列表,每个 entry 标 `add` / `remove` / `modify` / `same` + location + keyword
- 既可 CLI(`inp-tool diff a.inp b.inp`)也可 Python API(`from inp_tool import diff`)
- 也可走 FastAPI:`POST /api/diff` 同时接 `a` 和 `b` 两个文件

### 4.3 sweep(批量生成,v0.4)

```
template.inp ───┐
                │  parse_file → InpFile
                ▼
            InpFile(tpl)
                │
   SweepSpec / FreestreamPreset
                │  CaseSweep.run() / generate()
                │  for each params in expand_cartesian(spec):
                │     copy.deepcopy(InpFile)
                │     apply preset + overrides
                │     write to output_dir/name.format(**params)
                ▼
  N 个 .inp 文件  +  manifest.json
```

**关键设计:** 每个 case 独立 `copy.deepcopy` 模板,保证不污染源,允许并行/中断/重跑。

详见 [02-sweep-architecture.md](../sweep/02-sweep-architecture.md)。

---

## 5. 入口点

| 入口 | 触发方式 | 对应源码 | 文档 |
|---|---|---|---|
| **Python API** | `from inp_tool import parse, write, diff, generate, ...` | `inp_tool/__init__.py` | [03-sweep-usage.md §1](../sweep/03-sweep-usage.md) |
| **CLI** | `inp-tool <subcmd> ...`(安装后)/ `python -m inp_tool` | `inp_tool/cli.py:main` | [03-sweep-usage.md §2](../sweep/03-sweep-usage.md) |
| **FastAPI** | `inp-tool-api` / `python -m inp_tool.api` | `inp_tool/api.py:main` | [03-sweep-usage.md §3](../sweep/03-sweep-usage.md) |
| **Web GUI** | `inp-tool-api` 启动后访问 `/` | `inp_tool/web/index.html` | [05-sweep-friendly-uis.md §3](../sweep/05-sweep-friendly-uis.md) |

### 5.1 console_script 声明(pyproject.toml)

```toml
[project.scripts]
inp-tool = "inp_tool.cli:main"
inp-tool-api = "inp_tool.api:main"
```

`pip install -e .` 后,两个命令自动出现在 PATH。

### 5.2 Python 公共导出(`__init__.py`)

```python
from .model import InpFile, Block, Stmt, Value, infer_type
from .parser import parse, parse_file
from .writer import to_text, write, write_bytes
from .diff import diff, DiffReport, DiffEntry
from .sweep import (SweepSpec, expand_cartesian, FreestreamPreset,
                    render_case_name, CaseResult, SweepReport,
                    CaseSweep, generate)
__version__ = '0.4.0'
```

22 个公开符号,涵盖 read / write / diff / sweep 全部能力。

### 5.3 Web GUI 静态文件挂载

`api.py` 启动时把 `inp_tool/web/index.html` mount 到根路径:

```python
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
```

无需构建步骤,纯 HTML + JS 直接 fetch `/api/*`。

---

## 6. 外部依赖

`inp_tool` 严格分层,核心**零运行时依赖**;可选能力走 extras。

| Extras | 依赖 | 用于 | 何时必须装 |
|---|---|---|---|
| (无) | — | 核心(parser / writer / model / diff / sweep) | 始终 |
| `[api]` | `fastapi>=0.100` | Web 后端 | 装 `inp-tool-api` 或用 FastAPI 时 |
| `[api]` | `uvicorn[standard]>=0.23` | ASGI 服务器 | 同上 |
| `[api]` | `pydantic>=2.0` | 请求/响应模型 | 同上 |
| `[api]` | `eval_type_backport>=0.2.0` (Py<3.9) | 3.8 兼容 PEP 604 注解 | 仅 Python 3.8 |
| `[yaml]` | `pyyaml>=6.0` | YAML sweep 配置 | `inp-tool sweep foo.yaml` |
| `[dev]` | `pytest>=7.0` / `pytest-cov>=4.0` / `httpx>=0.24` | 测试 | `pytest` / `tox` |
| `[build]` | `pyinstaller==5.13.2` | 单文件 / onedir 可执行 | 打包分发 |

### 6.1 为什么核心零依赖

- **可移植性**: 用户的 Win7 + Py3.8 现场,`pip install inp-tool` 不引入 transitive deps,不会因 numpy / pydantic 版本冲突装不上。
- **可嵌入性**: 其他脚本(批处理 / 翻译工具 / 单元测试)可以直接 `from inp_tool import parse_file` 而不背一坨。
- **可分阶段升级**: 用户先用 stdlib 跑通核心,再按需加 `[api]` / `[yaml]`。

### 6.2 安装矩阵(典型)

```bash
# 最小:核心
pip install inp-tool

# 加 CLI + API
pip install inp-tool[api]

# 加 YAML sweep
pip install inp-tool[api,yaml]

# 开发
pip install -e .[api,yaml,dev]

# 打包单文件 exe
pip install .[build] && pyinstaller inp_tool_onedir.spec
```

---

## 7. 版本演进与目录对应

| 版本 | 新增 | 章节文档 |
|---|---|---|
| v0.2 | parser / writer / model / diff + CLI | 本章 §2-§4 |
| v0.3 | Python 包工程化(pyproject / pytest / FastAPI) | [02-ci-cd.md](../release/02-ci-cd.md) |
| v0.4.2 | sweep 批量生成 + 三入口 | [03-09 sweep 全章节](../sweep/01-sweep-overview.md) |
| v0.4.x | onedir 打包 + preserve_format(后续小版本) | [01-cli-packaging.md §4](../release/01-cli-packaging.md) |

---

## 8. 子文档索引

| 文件 | 主题 |
|---|---|
| [01-sweep-overview](../sweep/01-sweep-overview.md) | sweep 总览(背景/三入口/风险) |
| [02-sweep-architecture](../sweep/02-sweep-architecture.md) | sweep 数据模型 + 主流程 |
| [03-sweep-usage](../sweep/03-sweep-usage.md) | 三入口详细用法 |
| [01-cli-packaging](../release/01-cli-packaging.md) | CLI 设计与 PyInstaller 打包 |
| [02-ci-cd](../release/02-ci-cd.md) | CI/CD matrix + environment.yml |
| [02-core-modules](02-core-modules.md) | parser / writer / model / diff 4 模块详细 |

---

## 9. 设计原则速记

| 原则 | 体现 |
|---|---|
| **零核心依赖** | 核心无 pip install |
| **下层无环** | model 叶子,parser/writer/diff 单向依赖 |
| **不破坏 round-trip** | 解析-写回差异最小化,行尾注释保留 |
| **可独立使用** | 任何子模块(单文件)可单独 import |
| **多入口同源** | CLI / API / Web 共用同一份核心逻辑 |
| **3.8 兼容** | 所有代码在 Python 3.8-3.12 可运行 |
| **3 平台同代码** | Win7 / Win10 / Linux 一份代码 |
