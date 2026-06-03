# cfd++changer 项目整理计划

**项目**：`cfd++changer`（CFD++ GUI 翻译 + `inp_tool` 子包）
**范围**：根目录结构整理（不动 CFD++ 业务代码本身）
**前置**：git status 已记录全部现状

---

## Step 1 — 归档 `analysis_v2/` 中的废弃实验脚本

**意图**：`analysis_v2/` 累积了 `analyzer1.py`–`analyzer11.py` 编号迭代脚本 + 一堆 `test_*.py` 调试脚本 + `gen_report.py`/`gen_report2.py`。识别最终版（按 import 关系 + mtime 判断，大概率是 `analyzer11.py` + `gen_report2.py`），其余移到 `analysis_v2/_archive/` 并附 README 说明取舍。

**不在范围**：重写 analyzer 逻辑、合并 `analyzer11.py` 与 `gen_report2.py`、删除 CFD_GUI_CallGraph*.md 分析文档。

---

## Step 2 — 合并根目录重复的 `translate_*.py`

**意图**：根目录有 `translate_html.py` / `translate_html_v2.py` 与 `translate_turb.py` / `translate_turb_llm.py` 两组 v1/v2 重复。合并到 `scripts/translate_html.py`、`scripts/translate_turb.py`，LLM 模式以 `--llm` flag 暴露。`*.ps1` 工具脚本一并归入 `scripts/powershell/`。

**不在范围**：新增翻译功能、切换 LLM 提供商、改 HTML 翻译结果目录结构。

---

## Step 3 — 补全 `inp_tool/` 工程化

**意图**：`inp_tool/` 已有完整 `cli/parser/writer/model/api/diff` 结构，但缺 `pyproject.toml`、根 README、`python -m inp_tool` 入口测试。补齐：标准 `pyproject.toml`（setuptools，`inp-tool` console_script 指向 `cli.main`）、`inp_tool/README.md`、用 pytest 覆盖 `parser` / `writer` / `diff` / `api`、保留 `examples/demo.py`。

**不在范围**：发布到 PyPI、新增 parser 功能、改 CLI 参数语义。

---

## Step 4 — 写项目根目录 README.md

**意图**：在仓库根写 `README.md`，让陌生访客 5 分钟内能：1) 知道项目是干嘛的（CFD++ GUI 翻译 + `inp_tool`），2) 看到顶层目录地图（`inp_tool/`、`scripts/`、`html/`、`html_cn/`、`gui_src_cn/`、`analysis_v2/`），3) 跑起来（`python -m inp_tool --help` 与 `scripts/translate_*.py` 入口），4) 找到深入文档（链接 `CFD_GUI_Engineering_Handbook.md`）。

**不在范围**：改写既有的 `CFD_GUI_CallGraph*.md` / `Engineering_Handbook.md`、翻译其他章节到中文。
