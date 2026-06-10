# cfd++changer

> CFD++ GUI 工具集:HTML/Tcl 帮助文档翻译 (EN→CN) + `mcfd.inp` 求解器输入文件的 Python 解析/修改/diff 库。

---

## 目录结构

| 路径 | 用途 |
|---|---|
| `inp_tool/` | mcfd.inp 解析/修改/diff Python 包 + CLI + Web GUI(详见 [`inp_tool/README.md`](inp_tool/README.md)) |
| `scripts/translate_html.py` | 批量翻译 `html/` → `html_cn/`(LLM 驱动) |
| `scripts/translate_turb.py` | 翻译 `html/turb.html`(字典模式默认, `--llm` 切换 LLM) |
| `scripts/powershell/` | 4 个 PowerShell 工具脚本(`check_missing` / `check_remaining` / `check_sizes` / `fix_bc`) |
| `html/` | 原始英文 CFD++ GUI HTML 帮助(629 个文件) |
| `html_cn/` | 中文翻译输出(627 个文件,与 `html/` 大致一一对应) |
| `gui_src_cn/` | 翻译后的 CFD++ GUI Tcl/Tk 源码 |
| `analysis_v2/` | CFD++ GUI 调用关系分析(当前版:`analyzer11.py` + `gen_report2.py`) |
| `analysis_v2/_archive/` | 31 个 v1–v10 旧版分析器 + 一次性调试脚本(详见 `_archive/README.md`) |
| `docs/` | 项目文档(2026-06-02 整理计划) |
| `scripts/.state/translate_v2_progress.json` | `translate_html.py` 的翻译进度缓存(支持断点续传) |
| `docs/translation/translation_check_report.md` | 翻译覆盖率与缺漏检查报告 |
| `docs/cfd-gui/CFD_GUI_Engineering_Handbook.md` | CFD++ GUI 工程手册(41 KB) |
| `docs/cfd-gui/CFD_GUI_CallGraph_v2.md` | CFD++ GUI 调用关系分析详细版(102 KB) |
| `docs/cfd-gui/CFD_GUI_CallGraph.md` | CFD++ GUI 调用关系分析早期版(14 KB,被 v2 取代) |

---

## 快速开始

### inp_tool — 解析/修改 mcfd.inp

```bash
cd inp_tool
pip install -e .                      # 核心(parser / writer / diff / CLI)
inp-tool --version                    # 检查安装
inp-tool info path/to/file.inp        # 文件概览(块列表、语句数)
inp-tool get file.inp cflbot -b tsteps                  # 取一个值
inp-tool set file.inp tsteps cflbot 0.005 -o new.inp    # 改值写新文件
inp-tool diff a.inp b.inp -u          # unified diff
```

**v0.9.0 整算例目录批量 sweep**(新模块 `inp_tool.pbs` 零依赖):

```bash
# 从 reference/suanli 完整算例出发,扫 alpha+mach,生成 4 个完整子算例
inp-tool sweep config.json --source-dir reference/suanli \
  --pbs-naming 'Mars-{alpha}-{mach}' --force
# → case_aoa0_m0.6/  case_aoa0_m0.8/  case_aoa4_m0.6/  case_aoa4_m0.8/
#   每个子目录含 mcfd.inp (修改后) + 网格/物性/pbs 模板
#   pbs 任务名: #PBS -N Marspath_a00_m0.60 / ... 等 4 个不同
#   manifest.json 含 pbs_enabled + 每 case pbs_name
```

Web GUI(含 FastAPI 后端):
```bash
cd inp_tool
pip install -e .[api]
python run_server.py
# 浏览器打开 http://127.0.0.1:8765
# OpenAPI 文档: http://127.0.0.1:8765/docs
```

详细 API / 数据模型 / 测试说明见 [`inp_tool/README.md`](inp_tool/README.md)。

### 翻译 HTML 帮助文档

```bash
# 批量翻译 html/ → html_cn/(需 LLM 脚本)
python scripts/translate_html.py

# 翻译单文件 turb.html:字典模式(免费/快,使用已嵌入的 17+54 条翻译)
python scripts/translate_turb.py

# 字典模式 + LLM 兜底(分块调用 LLM)
python scripts/translate_turb.py --llm
```

> **注意**:这两个脚本的 `SRC` / `DST` / `LOG` 与 LLM 脚本路径都是**硬编码的 Windows 绝对路径**(如 `E:\ProgrammingData\python\cfd++changer\html`、`C:\Users\muggle\.mavis\.builtin-skills\llm-call\scripts\llm_call.py`)。要迁移到其他机器需修改脚本顶部的常量。

### CFD++ GUI 调用关系分析

```bash
cd analysis_v2
python analyzer11.py      # 扫 GUI 源码,生成 analysis_v11.json
python gen_report2.py     # 读 JSON 生成报告
```

`analyzer11.py` / `gen_report2.py` 是当前在用版本;v1–v10 旧版本与一次性测试脚本归档在 `analysis_v2/_archive/`(31 个文件,按需 `mv` 回上层即可复活)。

---

## 深入文档

- [`inp_tool/README.md`](inp_tool/README.md) — inp_tool 完整文档(install / Python API / CLI / 数据模型 / 测试)
- [`docs/cfd-gui/CFD_GUI_Engineering_Handbook.md`](docs/cfd-gui/CFD_GUI_Engineering_Handbook.md) — CFD++ GUI 工程手册
- [`docs/cfd-gui/CFD_GUI_CallGraph_v2.md`](docs/cfd-gui/CFD_GUI_CallGraph_v2.md) — GUI 调用关系详细分析
- [`docs/translation/translation_check_report.md`](docs/translation/translation_check_report.md) — 翻译覆盖率与缺漏
- [`docs/technical/`](docs/technical/) — 开发者技术手册(架构 / 核心模块 / sweep / REPL / 打包 / CI)
- [`docs/user-manual/`](docs/user-manual/) — 终端用户手册(快速开始 / 配置 / wizard / FAQ)

---

## 环境

- **Python** ≥ 3.10
- **inp_tool 核心** 无外部依赖(stdlib only)
- **`[api]` extras** 需要 `fastapi` / `uvicorn` / `pydantic`
- **`[dev]` extras** 需要 `pytest` / `pytest-cov` / `httpx`(FastAPI TestClient)
- **翻译脚本的 LLM 调用** 依赖 `C:\Users\muggle\.mavis\.builtin-skills\llm-call\scripts\llm_call.py`
- **外部 INP_DIR**(可选,用于 inp_tool 54 样本真实回归):`E:\softwareData\edge\download\inp`;目录不存在时 `pytest -m external` 自动 skip

---

## 项目状态

- 首次提交:`55f4f79` (2026-05-14)
- 2026-06-02 整理:Step 1 归档 31 个废弃脚本到 `analysis_v2/_archive/`;Step 2 合并根目录 4 个 `translate_*.py` 到 `scripts/`(含 LLM flag 统一);Step 3 给 `inp_tool/` 加 `pyproject.toml` / `__main__.py` / 5 个 pytest 模块 / 80% 覆盖率;Step 4 写本 README。
- 2026-06-10 文档结构整理:删除已完成的 `docs/cleanup-plan.md` 与 `docs/superpowers/plans/2026-06-08-inp-tool-repl.md`;`user-manual/` REPL/wizard 章节重新编号为 16-/17-/18-。
- 2026-06-10 **inp_tool v0.9.0**(PR #14,tag `v0.9.0`,[Release](https://github.com/oneMuggle/cfd--changer/releases/tag/v0.9.0)):
  - **新模块** `inp_tool.pbs`(~250 行,零运行时依赖):`PbsConfig` / `PbsIssue` / `detect_pbs_template` / `validate_base_case_dir` / `render_pbs_name` / `write_pbs` / `extract_pbs_basename`
  - **sweep 集成**:`CaseSweep.pbs` 字段 + `generate()` 完整性检查 + per_case 写 pbs + manifest `pbs_enabled` / `pbs_name`
  - **CLI**:`inp-tool sweep --pbs/--no-pbs` + `--pbs-naming` 模板
  - **Wizard**:6 步 → 7 步,新增 `step 5a pbs` 询问 + 建议名展示
  - **测试**:33 pbs 单测 + 12 集成 = 45 新测;**449 passed, 0 回归**;pbs.py 85% 覆盖
  - **CI**:3 平台(Ubuntu / macOS / Windows)× Python 3.8-3.12 矩阵全过
  - **smoke**:`reference/suanli` 544MB 真实算例 2-case sweep 端到端通过
