# docs/ 结构重整 Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 Phase 1 之后的 35 章节内容去重(8 个 R 互引)+ 修复 1 个 plan 误归档 + 新增 `docs/INDEX.md` 跨维度导航,2 commit 独立可验。

**Architecture:** 机械式重整 — 16 个 unique 章节顶部加互引段 + 1 文件 git mv(归档)+ 1 新文件(INDEX.md)+ 2 README 微调。无 Python 代码改动,无 pytest。验证靠 grep + Python 跨文件链接检查。

**Tech Stack:** Git, Markdown, grep, Python 链接检查脚本(临时)

---

## 工作流约束(执行前必读)

- **必须**在 feature 分支上做(按 `CLAUDE.md` §3.3 + `feature-branch-workflow.md`);分支名 `docs/restruct-phase2`
- 每次 `git mv` 前确认当前在 feature 分支
- 每 commit 完成后跑 §6 验证清单
- **不要**改任何章节的**正文内容**(本次只加互引段 + 归档 + 新 INDEX)
- **不要**改任何章节的**文件名 / 编号**(Phase 1 已完成)
- **不要**新建任何 README(Phase 1 已完成)

---

## Task 0: 准备工作(分支 + 确认)

**Files:** 无

- [ ] **Step 1: 确认 main 工作区干净**

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:`nothing to commit, working tree clean`

- [ ] **Step 2: 拉最新 main**

```bash
git fetch origin main
git pull --rebase origin main
```

预期:无冲突

- [ ] **Step 3: 建 feature 分支**

```bash
git switch -c docs/restruct-phase2
```

预期:`Switched to a new branch 'docs/restruct-phase2'`

---

## Task 1: Commit 1 — 8 处互引 + ux plan 归档

**Files:**
- Modify: 16 unique 章节文件(顶部加互引段)
- Move: `docs/technical/ux/01-ux-friendly-cli.md` → `docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`
- Modify: `docs/technical/ux/README.md` §1 段
- Modify: `docs/superpowers/specs/README.md` 加 1 条 status 表条目

### Step 1: R1 — sweep 用法 3 处互引

#### 1.1 `docs/user-manual/sweep/01-sweeping.md` 顶部加互引

**Files:** `docs/user-manual/sweep/01-sweeping.md`

Read 整个文件,找到 "## 1. 什么是"扫描"" 这一行(第 4 行),在它**之前**插入:

```markdown
> **视角定位:** 用户视角(扫哪些字段)。完整 API(Python / CLI / FastAPI)见 [technical/sweep/03-sweep-usage](../../technical/sweep/03-sweep-usage.md)。

```

预期:文件第 4 行变成"## 1. ..." 之前有 1 行 blockquote(以 `> ` 开头)。

#### 1.2 `docs/user-manual/sweep/05-multiple-uis.md` 顶部加互引

**Files:** `docs/user-manual/sweep/05-multiple-uis.md`

Read 整个文件,找到 "## 1. 四种入口速览"(第 5 行),在它**之前**插入:

```markdown
> **视角定位:** 用户视角(4 种入口速览)。开发者视角的 YAML / 交互式 / Web GUI 实现细节见 [technical/sweep/05-sweep-friendly-uis](../../technical/sweep/05-sweep-friendly-uis.md)。完整 API 见 [technical/sweep/03-sweep-usage](../../technical/sweep/03-sweep-usage.md)。

```

#### 1.3 `docs/technical/sweep/03-sweep-usage.md` 顶部加互引

**Files:** `docs/technical/sweep/03-sweep-usage.md`

Read 整个文件,找到 "## 1. Python API"(第 7 行),在它**之前**插入:

```markdown
> **视角定位:** 开发者视角(Python / CLI / FastAPI 完整 API)。用户视角的扫哪些字段见 [user-manual/sweep/01-sweeping](../../user-manual/sweep/01-sweeping.md),4 种入口速览见 [user-manual/sweep/05-multiple-uis](../../user-manual/sweep/05-multiple-uis.md)。

```

### Step 2: R2 — wizard/REPL 3 处互引

#### 2.1 `docs/user-manual/interactive/01-repl-quickstart.md` 顶部加互引

**Files:** `docs/user-manual/interactive/01-repl-quickstart.md`

Read 整个文件,找到 "## 第 1 步:启动 REPL"(第 5 行),在它**之前**插入:

```markdown
> **速查定位:** 5 个最常用 REPL 命令(快速开始)。REPL 全功能见 [02-repl-tour](02-repl-tour.md),3 个任务向导见 [03-wizard-tasks](03-wizard-tasks.md)。

```

#### 2.2 `docs/user-manual/interactive/02-repl-tour.md` 顶部加互引

**Files:** `docs/user-manual/interactive/02-repl-tour.md`

Read 整个文件,找到第一个 `## ` 段(看具体行号),在它**之前**插入:

```markdown
> **速查定位:** REPL 全功能。5 命令速查见 [01-repl-quickstart](01-repl-quickstart.md),3 个任务向导见 [03-wizard-tasks](03-wizard-tasks.md)。

```

#### 2.3 `docs/user-manual/interactive/03-wizard-tasks.md` 顶部加互引

**Files:** `docs/user-manual/interactive/03-wizard-tasks.md`

Read 整个文件,找到 "## 概述"(第 7 行),在它**之前**插入:

```markdown
> **速查定位:** 3 个 wizard(modify-file / sweep / diff)。REPL 基础见 [02-repl-tour](02-repl-tour.md),5 命令快速开始见 [01-repl-quickstart](01-repl-quickstart.md)。

```

### Step 3: R3 — sweep 配置字段 2 处互引

#### 3.1 `docs/user-manual/sweep/02-config-files.md` 末尾加互引

**Files:** `docs/user-manual/sweep/02-config-files.md`

Read 整个文件,找到文件**最后一行**(可能是某个 `##` 段或代码块结束),在文件**末尾**追加 1 个新段:

```markdown

## 字段全表

本节"## 关联"段:

```markdown
> **字段全表见:** [reference/01-mcfd-inp-field-reference](../reference/01-mcfd-inp-field-reference.md) — 10 块 × 全部字段,sweep 字段映射
```

**注意:** 实际编辑时,**不**用 `## 字段全表` 段标题(因为那个段已经由其他章节讲);只在文件末尾的"## 关联"段(如不存在则新建)加上面这段 blockquote。

简单做法:Read 整个文件 → Edit 找最后 1 个 `## ` 段,在它之前插入上述 blockquote 段。如果无"## 关联"段,则在文件末尾**新加 1 个段**:

```markdown

## 关联

> **字段全表见:** [reference/01-mcfd-inp-field-reference](../reference/01-mcfd-inp-field-reference.md) — 10 块 × 全部字段,sweep 字段映射
```

#### 3.2 `docs/user-manual/reference/01-mcfd-inp-field-reference.md` 顶部加互引

**Files:** `docs/user-manual/reference/01-mcfd-inp-field-reference.md`

Read 整个文件,找到第一个 `## ` 段(具体行号看 Read 输出),在它**之前**插入:

```markdown
> **视角定位:** 字段全表(参考手册)。配置文件(JSON / YAML)写法见 [sweep/02-config-files](../sweep/02-config-files.md)。

```

### Step 4: R4 — sweep 案例 2 处互引(轻量)

#### 4.1 `docs/technical/sweep/08-sweep-case-study.md` 顶部加互引

**Files:** `docs/technical/sweep/08-sweep-case-study.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 案例研究(1D/2D 物理量校验)。完整可跑示例见 [user-manual/sweep/06-examples](../../user-manual/sweep/06-examples.md)。

```

#### 4.2 `docs/user-manual/sweep/06-examples.md` 顶部加互引

**Files:** `docs/user-manual/sweep/06-examples.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 6 个端到端真实场景。物理量校验见 [technical/sweep/08-sweep-case-study](../../technical/sweep/08-sweep-case-study.md)。

```

### Step 5: R5 — 友好入口 2 处互引

#### 5.1 `docs/user-manual/sweep/05-multiple-uis.md`(已 Step 1.2 加 R1 互引)

Read 文件顶部已加的 R1 互引,**Edit 替换**为:

```markdown
> **视角定位:** 用户视角(4 种入口速览)。开发者视角的 YAML / 交互式 / Web GUI 实现细节见 [technical/sweep/05-sweep-friendly-uis](../../technical/sweep/05-sweep-friendly-uis.md)。完整 API 见 [technical/sweep/03-sweep-usage](../../technical/sweep/03-sweep-usage.md)。
```

注:这与 R1 的内容相同,**Edit 替换后内容不变**。目的是确认 R1/R5 互引都已覆盖(5.1 步骤可视为"无操作",因为 Step 1.2 已经做完)。

#### 5.2 `docs/technical/sweep/05-sweep-friendly-uis.md` 顶部加互引

**Files:** `docs/technical/sweep/05-sweep-friendly-uis.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 开发者视角(YAML / 交互式 / Web GUI 实现)。用户视角的 4 种入口速览见 [user-manual/sweep/05-multiple-uis](../../user-manual/sweep/05-multiple-uis.md)。

```

### Step 6: R6 — 整算例目录 2 处互引

#### 6.1 `docs/technical/sweep/10-sweep-case-dir.md` 顶部加互引

**Files:** `docs/technical/sweep/10-sweep-case-dir.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 开发者视角(source_dir / CopyStrategy / per_dir 实现)。用户视角的 source_dir 字段用法见 [user-manual/sweep/02-config-files](../../user-manual/sweep/02-config-files.md) §1 JSON 配置 + §2 YAML 配置(找 source_dir 字段说明)。

```

#### 6.2 `docs/user-manual/sweep/02-config-files.md`(已 Step 3.1 加 R3 互引)

Read 文件末尾已加的 R3 互引,**Edit 追加** 1 行(R6 互引):

在文件末尾的"## 关联"段(R3 加的)底部加:

```markdown
> **字段全表见:** [reference/01-mcfd-inp-field-reference](../reference/01-mcfd-inp-field-reference.md) — 10 块 × 全部字段,sweep 字段映射
> **整算例目录模式(per_dir)见:** [technical/sweep/10](../../technical/sweep/10-sweep-case-dir.md) — source_dir 字段与 CopyStrategy 实现
```

### Step 7: R7 — 方程感知 3 处互引

#### 7.1 `docs/technical/sweep/11-equation-aware-config.md` 顶部加互引

**Files:** `docs/technical/sweep/11-equation-aware-config.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** v0.9.0/0.9.1 方程感知(检测 + 初始化)。v0.10.0 sweep 扩展(per-case 覆盖)见 [12-equation-sweep-extend](12-equation-sweep-extend.md)。

```

#### 7.2 `docs/technical/sweep/12-equation-sweep-extend.md` 顶部加互引

**Files:** `docs/technical/sweep/12-equation-sweep-extend.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** v0.10.0 sweep 扩展(per-case 覆盖 + alias)。v0.9.x 方程感知背景见 [11-equation-aware-config](11-equation-aware-config.md)。

```

#### 7.3 `docs/user-manual/interactive/03-wizard-tasks.md`(已 Step 2.3 加 R2 互引)

Read 文件,找到 wizard sweep 步骤(在 "## `wizard sweep`" 段),在该段内**追加 1 行**:

```markdown
> v0.11.0 wizard sweep 涉及的"step_4b 选 axis + step_4c per-case 覆盖"细节见 [technical/sweep/11](../../technical/sweep/11-equation-aware-config.md) + [technical/sweep/12](../../technical/sweep/12-equation-sweep-extend.md)。
```

### Step 8: R8 — 打包/分发 2 处互引

#### 8.1 `docs/technical/release/01-cli-packaging.md` 顶部加互引

**Files:** `docs/technical/release/01-cli-packaging.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 开发者视角(PyInstaller 配置 + 构建过程)。用户使用 standalone 见 [user-manual/advanced/01-packaging](../../user-manual/advanced/01-packaging.md)。

```

#### 8.2 `docs/user-manual/advanced/01-packaging.md` 顶部加互引

**Files:** `docs/user-manual/advanced/01-packaging.md`

Read 整个文件,找到第一个 `## ` 段,在它**之前**插入:

```markdown
> **视角定位:** 用户使用 standalone 版本。打包构建过程见 [technical/release/01-cli-packaging](../../technical/release/01-cli-packaging.md)。

```

### Step 9: 误归档修复 — git mv + STATUS 头

**Files:**
- Move: `docs/technical/ux/01-ux-friendly-cli.md` → `docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`
- Modify: `docs/technical/ux/README.md`
- Modify: `docs/superpowers/specs/README.md`
- Modify: `docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`(归档后)

#### 9.1 git mv 归档

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/ux/01-ux-friendly-cli.md docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md
```

预期:`Renaming ... to ...`

#### 9.2 在归档后文件加 STATUS 头

**Files:** `docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`

Read 整个文件(应当是 plan 内容:背景/目标/涉及文件/实施步骤),找到第一行非空行(`# 计划:i18n + Wizard 任务向导(PR #2)`)前一行(或文件最顶),**插入 1 行 STATUS**:

实际上 spec 模板 STATUS 行在标题**之后**,所以:

Read 文件 → 找到第 1 行 `# 计划:...` → **Edit** 把这一行替换为:

```markdown
# 2026-06-09 i18n + Wizard 任务向导(原 PR #2 计划,已实施)

**Status:** ✅ 已实施(PR #2 后的 v0.7.1+,实际已合入 main)
**Date:** 2026-06-09
**归档时间:** 2026-06-12(从 `docs/technical/ux/01-ux-friendly-cli.md` 移入本 specs 目录)

---

## 计划:i18n + Wizard 任务向导(PR #2)
```

(保留原文件标题"## 计划:..."作为 `## 2 级标题`,新加的"# 2026-06-09 ..."作为 `## 1 级标题` + STATUS + Date + 归档时间元数据 + 分隔线 + 原文"## 计划"段)

**操作方式:**
- Edit 工具:old_string = "# 计划:i18n + Wizard 任务向导(PR #2)"(文件原第 1 行),new_string = 上面整段(包括原"## 计划"升为 `## 2 级`)

#### 9.3 改 `docs/technical/ux/README.md` §1 段

**Files:** `docs/technical/ux/README.md`

Read 整个文件,找到 "## 章节" 段(应当存在,Phase 1 写的模板),在它**之前**替换或新增 1 段(让"暂无章节"的原因讲明是因 plan 已归档):

如果 `## 章节` 段后面是空表格,把整段替换为:

```markdown
## 章节

| # | 标题 | 内容简介 |
|---|---|---|
| (暂无) | — | — |

> **注:** 本目录 Phase 1 误归档了 v0.7.1 计划 `01-ux-friendly-cli.md`。Phase 2 修复:移到 [`../superpowers/specs/2026-06-09-ux-friendly-cli-design.md`](../superpowers/specs/2026-06-09-ux-friendly-cli-design.md)。
>
> UX 章节尚未单独成文;UX 设计的实操内容见 [`../../user-manual/interactive/`](../../user-manual/interactive/)(REPL + wizard)。
```

#### 9.4 改 `docs/superpowers/specs/README.md` 加 status 条目

**Files:** `docs/superpowers/specs/README.md`

Read 整个文件,找到 "## 当前 spec 列表" 表格,在表格**末尾**加 1 行:

| Spec | 简介 | Status |
|---|---|---|
| (已有 6 行) | | |
| [2026-06-09 ux-friendly-cli](2026-06-09-ux-friendly-cli-design.md) | v0.7.1 i18n + Wizard 任务向导(原 PR #2 计划,Phase 2 从 `technical/ux/01-ux-friendly-cli.md` 归档) | ✅ 已实施(PR #2 后的 v0.7.1+,Phase 2 归档) |

**操作:** Read 整个文件 → 找到 `| [2026-06-11 wizard-equation-axes]` 那一行(Phase 1 后的最新行)→ **Edit** 在它**之后**追加 1 行新条目。

### Step 10: 验证(commit 1 范围)

#### 10.1 互引段全到位(grep)

```bash
cd /home/fz/project/cfd--changer
# 检查 16 unique 文件都已加互引段(顶部 blockquote 以 "> **视角定位" 或 "> **速查定位" 开头)
for f in \
  docs/user-manual/sweep/01-sweeping.md \
  docs/user-manual/sweep/05-multiple-uis.md \
  docs/technical/sweep/03-sweep-usage.md \
  docs/user-manual/interactive/01-repl-quickstart.md \
  docs/user-manual/interactive/02-repl-tour.md \
  docs/user-manual/interactive/03-wizard-tasks.md \
  docs/user-manual/sweep/02-config-files.md \
  docs/user-manual/reference/01-mcfd-inp-field-reference.md \
  docs/technical/sweep/08-sweep-case-study.md \
  docs/user-manual/sweep/06-examples.md \
  docs/technical/sweep/05-sweep-friendly-uis.md \
  docs/technical/sweep/10-sweep-case-dir.md \
  docs/technical/sweep/11-equation-aware-config.md \
  docs/technical/sweep/12-equation-sweep-extend.md \
  docs/technical/release/01-cli-packaging.md \
  docs/user-manual/advanced/01-packaging.md; do
  if ! head -10 "$f" | grep -qE "^> \*\*(视角定位|速查定位)"; then
    echo "MISSING: $f"
  fi
done
echo "互引段检查完成"
```

预期:无 `MISSING:` 行

#### 10.2 归档后旧路径无残留

```bash
cd /home/fz/project/cfd--changer
ls docs/technical/ux/01-ux-friendly-cli.md 2>&1
ls docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md
```

预期:第一个 ls 报 No such file;第二个存在

#### 10.3 跨文件链接检查(用 Python 脚本)

```bash
cd /home/fz/project/cfd--changer
python3 -c "
import os, re, glob

broken = []
for mdfile in glob.glob('docs/**/*.md', recursive=True):
    if 'docs/superpowers/specs/' in mdfile or 'docs/superpowers/plans/' in mdfile:
        continue
    base = os.path.dirname(mdfile)
    with open(mdfile) as f:
        content = f.read()
    for m in re.finditer(r'\[([^\]]*)\]\(([^)]+\.md)\)', content):
        link = m.group(2)
        if link.startswith('http') or link.startswith('//') or link.startswith('/'):
            continue
        if link.startswith('../'):
            parts = link.split('/')
            depth = 0
            while parts and parts[0] == '..':
                depth += 1
                parts = parts[1:]
            base_parts = base.split('/')
            resolved = '/'.join(base_parts[:-depth] + parts) if depth > 0 else '/'.join(parts)
        else:
            resolved = base + '/' + link
        full = os.path.normpath(resolved)
        if not os.path.exists(full):
            broken.append((mdfile, link, full))

print(f'TOTAL BROKEN: {len(broken)}')
for f, l, _ in broken[:5]:
    print(f'  {f} → {l}')
"
```

预期:`TOTAL BROKEN: 0`(0 broken 链接)

#### 10.4 提交 Commit 1

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:16 modified(章节文件)+ 1 renamed(归档)+ 1 modified(ux/README)+ 1 modified(specs/README)+ 1 modified(归档后文件 STATUS 头)

```bash
git add -A
git commit -m "docs(cleanup): Phase 2 去重 — 8 处互引 + ux plan 归档

8 个重复候选按"中度互引"原则处理(19 处编辑,16 个 unique 文件):
- R1 sweep 用法(3 处):user 01/05 ↔ technical 03
- R2 wizard/REPL(3 处):user interactive 01/02/03 互引
- R3 sweep 配置字段(2 处):user 02-config-files ↔ reference 01
- R4 sweep 案例(2 处):technical 08 ↔ user 06-examples
- R5 友好入口(1 处新):technical 05 ↔ user 05(已在 R1 互引)
- R6 整算例目录(2 处):technical 10 ↔ user 02-config-files 末尾
- R7 方程感知(3 处):technical 11/12 互引 + user interactive 03-wizard 步骤加链接
- R8 打包/分发(2 处):technical release 01 ↔ user advanced 01

误归档修复:
- docs/technical/ux/01-ux-friendly-cli.md (实际是 v0.7.1 plan)
  → docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md(加 STATUS: ✅ 已实施)
- docs/technical/ux/README.md §1 段注明"UX 章节尚未单独成文"
- docs/superpowers/specs/README.md status 表加新条目

详见 docs/superpowers/specs/2026-06-12-docs-restruct-phase2-design.md"
```

预期:commit 成功

---

## Task 2: Commit 2 — `docs/INDEX.md` 跨维度导航

**Files:**
- Create: `docs/INDEX.md`
- Modify: `docs/README.md` §常用入口

### Step 1: 创建 `docs/INDEX.md`

**Files:** `docs/INDEX.md`

Write 整个文件,内容(从 spec §3.3):

```markdown
# docs/ 跨维度导航(Phase 2 新增)

> 不知道从哪读起?按下面三种方式之一跳。
>
> 已有 docs/README + 子目录 README 是"按目录"组织;本 INDEX 是"按主题/受众/任务"组织。

---

## 1. 按主题(我要解决 X 问题)

| 任务 | 主章节 | 补充 |
|---|---|---|
| 扫一组参数 | [user-manual/sweep/01-sweeping](../user-manual/sweep/01-sweeping.md) | [tech sweep-usage](../technical/sweep/03-sweep-usage.md) 完整 API |
| 改 alpha/ma 之外的字段 | [user-manual/sweep/04-overrides](../user-manual/sweep/04-overrides.md) | — |
| 用 JSON/YAML 配置 sweep | [user-manual/sweep/02-config-files](../user-manual/sweep/02-config-files.md) | [reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) 字段全表 |
| 改命名规则 | [user-manual/sweep/03-naming](../user-manual/sweep/03-naming.md) | — |
| 用 wizard 任务向导 | [user-manual/interactive/03-wizard-tasks](../user-manual/interactive/03-wizard-tasks.md) | [01 quickstart](../user-manual/interactive/01-repl-quickstart.md) + [02 tour](../user-manual/interactive/02-repl-tour.md) |
| 查某个 .inp 字段 | [user-manual/reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) | — |
| 用打包版本(standalone) | [user-manual/advanced/01-packaging](../user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) 打包过程 |
| 端到端教程 | [user-manual/advanced/02-software-tutorial](../user-manual/advanced/02-software-tutorial.md) | — |

## 2. 按受众(我是 Y 类用户)

| 受众 | 起点 | 关键章节 |
|---|---|---|
| **新用户(CFD 工程师)** | [user-manual/README](../user-manual/README.md) | [basics/01-03](../user-manual/basics/) + [sweep/01-07](../user-manual/sweep/) |
| **偶尔用 / 不爱记命令** | [user-manual/interactive/README](../user-manual/interactive/README.md) | [01 quickstart](../user-manual/interactive/01-repl-quickstart.md) + [03 wizard](../user-manual/interactive/03-wizard-tasks.md) |
| **数据科学 / 集成到自己代码** | [user-manual/sweep/05-multiple-uis §Python API](../user-manual/sweep/05-multiple-uis.md) | [tech sweep/03-sweep-usage §1 Python API](../technical/sweep/03-sweep-usage.md) |
| **运维/分发** | [user-manual/advanced/01-packaging](../user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) |
| **开发者(读代码/扩展)** | [technical/README](../technical/README.md) | [architecture/01](../technical/architecture/01-architecture-overview.md) → [sweep/02](../technical/sweep/02-sweep-architecture.md) |
| **贡献者** | [technical/sweep/07-risks-roadmap §4 贡献指南](../technical/sweep/07-sweep-risks-roadmap.md) | [tech sweep/06-testing](../technical/sweep/06-sweep-testing.md) 测试结构 |

## 3. 按任务(我要做 Y 任务)

| 任务 | 关键章节 |
|---|---|
| 跑通第一个 sweep | [basics/03-quickstart](../user-manual/basics/03-quickstart.md) |
| 扫 alpha-mach | [sweep/01-sweeping](../user-manual/sweep/01-sweeping.md) + [06-examples 例 1](../user-manual/sweep/06-examples.md) |
| 整算例目录复制 | [tech sweep/10-case-dir](../technical/sweep/10-sweep-case-dir.md) |
| 方程感知(per-case 切) | [tech sweep/11-equation-aware](../technical/sweep/11-equation-aware-config.md) + [12-equation-extend](../technical/sweep/12-equation-sweep-extend.md) |
| 查 .inp 字段 | [reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) |
| 改 REPL 启动面板 | [tech specs/2026-06-09-ux-friendly-cli (plan, 已实施 v0.7.1)](../superpowers/specs/2026-06-09-ux-friendly-cli-design.md) |
| 写 wizard | [interactive/03-wizard-tasks](../user-manual/interactive/03-wizard-tasks.md) |
| 查 sweep 出错原因 | [sweep/07-faq](../user-manual/sweep/07-faq.md) |
| 打包 standalone | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) + [user advanced/01](../user-manual/advanced/01-packaging.md) |
| 跑 CI / 修 CI | [tech release/02-ci-cd](../technical/release/02-ci-cd.md) |
| 提 issue | GitHub issues |

---

## 4. 维护

- INDEX.md 由人在 Phase 2 后手工维护(不自动生成)
- 新增章节时,在 §1/§2/§3 适当位置加一行
- 章节归档时,从 INDEX 移除
```

### Step 2: 改 `docs/README.md` §常用入口

**Files:** `docs/README.md`

Read 整个文件,找到 "### 想跟进进行中的设计" 段(在文件**末尾**附近),在它**之前**插入新段:

```markdown

### 不知道从哪读起?

→ [INDEX.md](INDEX.md) — 跨维度导航(按主题 / 按受众 / 按任务 三种方式)

```

### Step 3: 验证

#### 3.1 INDEX.md 链接全可点

```bash
cd /home/fz/project/cfd--changer
python3 -c "
import os, re
mdfile = 'docs/INDEX.md'
base = os.path.dirname(mdfile)
with open(mdfile) as f:
    content = f.read()
broken = []
for m in re.finditer(r'\[([^\]]*)\]\(([^)]+\.md)\)', content):
    link = m.group(2)
    if link.startswith('http') or link.startswith('//') or link.startswith('/'):
        continue
    if link.startswith('../'):
        parts = link.split('/')
        depth = 0
        while parts and parts[0] == '..':
            depth += 1
            parts = parts[1:]
        base_parts = base.split('/')
        resolved = '/'.join(base_parts[:-depth] + parts) if depth > 0 else '/'.join(parts)
    else:
        resolved = base + '/' + link
    full = os.path.normpath(resolved)
    if not os.path.exists(full):
        broken.append((m.group(1), link, full))

print(f'INDEX.md broken: {len(broken)}')
for label, link, _ in broken:
    print(f'  [{label}]({link})')
"
```

预期:`INDEX.md broken: 0`

#### 3.2 docs/README.md 包含 INDEX 链接

```bash
cd /home/fz/project/cfd--changer
grep "INDEX.md" docs/README.md
```

预期:有 1 行匹配

#### 3.3 提交 Commit 2

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:1 new file(INDEX.md) + 1 modified(docs/README.md)

```bash
git add -A
git commit -m "docs(cleanup): Phase 2 加 docs/INDEX.md 跨维度导航

- docs/INDEX.md(新):3 维度导航
  - §1 按主题(扫参数/改字段/配置 sweep/用 wizard/查字段/打包/教程)
  - §2 按受众(新用户/偶尔用/数据科学/运维/开发者/贡献者)
  - §3 按任务(扫 alpha-mach/整算例目录/方程感知/查字段/写 wizard/打包/CI)
- docs/README.md §常用入口 加 '→ [INDEX.md] — 跨维度导航' 链接
- 手工维护(不自动生成),新增章节时人工加行

详见 docs/superpowers/specs/2026-06-12-docs-restruct-phase2-design.md"
```

预期:commit 成功

---

## Task 3: 推分支 + 开 PR

- [ ] **Step 1: 确认在 feature 分支**

```bash
cd /home/fz/project/cfd--changer
git branch --show-current
```

预期:`docs/restruct-phase2`

- [ ] **Step 2: 推分支**

```bash
git push -u origin docs/restruct-phase2
```

预期:`branch 'docs/restruct-phase2' set up to track 'origin/docs/restruct-phase2'`

- [ ] **Step 3: 开 PR**

```bash
gh pr create --title "docs(cleanup): Phase 2 — 内容去重 + 跨维度导航(8 互引 + 1 归档 + INDEX.md)" --body "## 背景

参见 docs/superpowers/specs/2026-06-12-docs-restruct-phase2-design.md

## 改动(2 commit)

1. \`docs(cleanup): Phase 2 去重 — 8 处互引 + ux plan 归档\` — 19 处互引(16 个 unique 文件) + 1 文件归档
2. \`docs(cleanup): Phase 2 加 docs/INDEX.md 跨维度导航\` — 新建 INDEX.md + docs/README 加链接

## 8 个重复候选处理

| R | 主题 | 处理 |
|---|---|---|
| R1 | sweep 用法 | 3 处互引(user 01/05 ↔ technical 03)|
| R2 | wizard/REPL | 3 处互引(interactive 01/02/03)|
| R3 | sweep 配置字段 | 2 处互引(02-config-files ↔ 01-mcfd-inp-field-ref)|
| R4 | sweep 案例 | 2 处互引(08-case-study ↔ 06-examples)|
| R5 | 友好入口 | 1 处互引(05-friendly-uis ↔ 05-multiple-uis)|
| R6 | 整算例目录 | 2 处互引(10-case-dir ↔ 02-config-files)|
| R7 | 方程感知 | 3 处互引(11/12 + interactive 03-wizard)|
| R8 | 打包/分发 | 2 处互引(release/01 ↔ advanced/01)|

## 误归档修复

- docs/technical/ux/01-ux-friendly-cli.md (实际是 v0.7.1 plan)
  → docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md(STATUS: ✅ 已实施)
- docs/technical/ux/README.md 注明"UX 章节尚未单独成文"

## INDEX.md 三维度

- §1 按主题(8 行)
- §2 按受众(6 行)
- §3 按任务(11 行)

## 验证

- [x] Python 跨文件链接检查:0 broken
- [x] 16 unique 章节文件互引段全到位
- [x] 旧路径 `docs/technical/ux/01-ux-friendly-cli.md` 无残留
- [x] 新 spec STATUS 头已加
- [x] INDEX.md 链接全可点

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

预期:PR URL 输出

- [ ] **Step 4: 监控 CI**

```bash
gh pr checks <PR_NUMBER> --watch
```

预期:3 平台 pass

- [ ] **Step 5: PR merge 后 cleanup**

PR merge 后:
```bash
git switch main
git pull --rebase origin main
git push origin --delete docs/restruct-phase2
git branch -D docs/restruct-phase2
```

删除本 plan:`docs/superpowers/plans/2026-06-12-docs-restruct-phase2.md`(plan 完成后即删)

更新 spec STATUS:`docs/superpowers/specs/2026-06-12-docs-restruct-phase2-design.md` 第 1 行改 `**Status:** ✅ 已完成 (PR #N, commits ...)`。

---

## 附录 A:验证清单(汇总,spec §5)

- [ ] Python 跨文件链接检查:0 broken
- [ ] 旧路径残留:0
- [ ] `git grep "docs/technical/ux/01-ux-friendly-cli.md"` 无引用(归档后)
- [ ] `git grep "docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md"` 引用 ≥ 1(INDEX + 新 spec README)
- [ ] `docs/superpowers/specs/README.md` status 表新增条目
- [ ] 8 个重复点互引 19 处编辑(commit 1 范围,16 个 unique 文件)全到位
- [ ] `docs/INDEX.md` §1/§2/§3 三维度表格存在,链接全可点
- [ ] `docs/README.md` §常用入口 包含 INDEX 链接
- [ ] 章节正文**未改**
- [ ] 3 平台 CI pass

---

## 附录 B:回滚方案

```bash
# 回滚 commit 2(HEAD)
git reset --hard HEAD~1

# 回滚 commit 1
git reset --hard HEAD~1

# 全回滚回到 main
git switch main
git branch -D docs/restruct-phase2
```
