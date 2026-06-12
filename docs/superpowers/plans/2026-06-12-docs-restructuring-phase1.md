# docs/ 结构重整 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/technical/`(17 章)和 `docs/user-manual/`(18 章)从"按编号连续扁平"重整为"按职能分子目录 + 子目录内 01-N 连续",35 个文件移动/重命名,3 commit 独立可验。

**Architecture:** 机械式重整 — `git mv` 移动 + 引用同步 + README 重写。无代码逻辑变更,无测试可写(验证靠 grep 残留检查)。每 commit 独立可回滚。

**Tech Stack:** Git, Markdown, grep(无 Python 代码改动)

---

## 工作流约束(执行前必读)

- **必须**在 feature 分支上做(按 `CLAUDE.md` §3.3 + `~/.claude/rules/common/feature-branch-workflow.md`);分支名 `docs/restruct-phase1`
- 每次 `git mv` 前确认当前在 feature 分支
- 每 commit 完成后跑 §6 验证清单再继续
- **不要**改任何章节的正文内容(本次只动归属和文件名;内容修订属其他 PR)

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

预期:无冲突(若有冲突先解决)

- [ ] **Step 3: 建 feature 分支**

```bash
git switch -c docs/restruct-phase1
```

预期:`Switched to a new branch 'docs/restruct-phase1'`

---

## Task 1: Commit 1 — 拆子目录(35 文件移动,不改名)

**Files:**
- Move: `docs/technical/{03..19}-*.md` → `docs/technical/{architecture|sweep|release|ux}/`
- Move: `docs/user-manual/{01..18}-*.md` → `docs/user-manual/{basics|sweep|interactive|reference|advanced}/`
- Modify: `docs/README.md`(改 §子目录速查表的链接)
- Modify: `docs/technical/README.md`(改 §2 章节目录的链接)
- Modify: `docs/user-manual/README.md`(改 §2 章节目录的链接)
- Modify: 35 个章节文件内的相对链接(`../NN-xxx.md` → `../<subdir>/NN-xxx.md`,或在同子目录内保持 `../NN-xxx.md`)

### Step 1: 同步跨引用(预期:有匹配,显示需改位置)

```bash
cd /home/fz/project/cfd--changer
grep -rn -E "\(\.\./[0-9]{2}-[^)]+\.md\)" docs/ 2>&1 | head -50
grep -rn -E "\(docs/(technical|user-manual)/[0-9]{2}-" docs/ CLAUDE.md inp_tool/README.md 2>&1 | head -50
```

预期:输出若干行(显示需要改的相对/绝对链接位置)
**记录这些位置,后续步骤要改。**

### Step 2: 创建 10 个子目录

```bash
cd /home/fz/project/cfd--changer
mkdir -p docs/technical/architecture
mkdir -p docs/technical/sweep
mkdir -p docs/technical/release
mkdir -p docs/technical/ux
mkdir -p docs/technical/intro
mkdir -p docs/user-manual/basics
mkdir -p docs/user-manual/sweep
mkdir -p docs/user-manual/interactive
mkdir -p docs/user-manual/reference
mkdir -p docs/user-manual/advanced
```

预期:无输出,目录创建成功

### Step 3: git mv 35 个章节文件(分 5 批执行)

**Batch 1: technical/architecture/(2 个)**

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/12-architecture-overview.md docs/technical/architecture/
git mv docs/technical/13-core-modules.md docs/technical/architecture/
```

**Batch 2: technical/sweep/(12 个)**

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/03-sweep-overview.md docs/technical/sweep/
git mv docs/technical/04-sweep-architecture.md docs/technical/sweep/
git mv docs/technical/05-sweep-usage.md docs/technical/sweep/
git mv docs/technical/06-sweep-freestream.md docs/technical/sweep/
git mv docs/technical/07-sweep-friendly-uis.md docs/technical/sweep/
git mv docs/technical/08-sweep-testing.md docs/technical/sweep/
git mv docs/technical/09-sweep-risks-roadmap.md docs/technical/sweep/
git mv docs/technical/14-sweep-case-study.md docs/technical/sweep/
git mv docs/technical/16-sweep-flexible.md docs/technical/sweep/
git mv docs/technical/17-sweep-case-dir.md docs/technical/sweep/
git mv docs/technical/18-equation-aware-config.md docs/technical/sweep/
git mv docs/technical/19-equation-sweep-extend.md docs/technical/sweep/
```

**Batch 3: technical/release/(2 个)**

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/10-cli-packaging.md docs/technical/release/
git mv docs/technical/11-ci-cd.md docs/technical/release/
```

**Batch 4: technical/ux/(1 个)**

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/15-ux-friendly-cli.md docs/technical/ux/
```

**Batch 5: user-manual/18 个**

```bash
cd /home/fz/project/cfd--changer
git mv docs/user-manual/01-introduction.md docs/user-manual/basics/
git mv docs/user-manual/02-installation.md docs/user-manual/basics/
git mv docs/user-manual/03-quickstart.md docs/user-manual/basics/
git mv docs/user-manual/04-sweeping.md docs/user-manual/sweep/
git mv docs/user-manual/05-config-files.md docs/user-manual/sweep/
git mv docs/user-manual/06-naming.md docs/user-manual/sweep/
git mv docs/user-manual/07-overrides.md docs/user-manual/sweep/
git mv docs/user-manual/08-multiple-uis.md docs/user-manual/sweep/
git mv docs/user-manual/09-examples.md docs/user-manual/sweep/
git mv docs/user-manual/10-faq.md docs/user-manual/sweep/
git mv docs/user-manual/16-repl-quickstart.md docs/user-manual/interactive/
git mv docs/user-manual/17-repl-tour.md docs/user-manual/interactive/
git mv docs/user-manual/18-wizard-tasks.md docs/user-manual/interactive/
git mv docs/user-manual/12-mcfd-inp-field-reference.md docs/user-manual/reference/
git mv docs/user-manual/13-cli-api-reference.md docs/user-manual/reference/
git mv docs/user-manual/15-glossary.md docs/user-manual/reference/
git mv docs/user-manual/11-packaging.md docs/user-manual/advanced/
git mv docs/user-manual/14-software-tutorial.md docs/user-manual/advanced/
```

预期:35 个 `git mv` 全部成功(每个都有 `Renaming ... to ...` 输出)

### Step 4: 验证 35 个文件已就位

```bash
cd /home/fz/project/cfd--changer
find docs/technical docs/user-manual -name "*.md" -not -name "README.md" | wc -l
```

预期:输出 `35`(所有章节文件)

```bash
find docs/technical docs/user-manual -maxdepth 2 -name "README.md" | wc -l
```

预期:输出 `2`(`docs/technical/README.md` + `docs/user-manual/README.md`)

### Step 5: 同步跨引用 — docs/README.md

**Files:** `docs/README.md`

读取 `docs/README.md` §子目录速查表与 §常用入口,把指向 `docs/technical/NN-xxx.md` 与 `docs/user-manual/NN-xxx.md` 的链接改为 `docs/technical/<subdir>/NN-xxx.md` 与 `docs/user-manual/<subdir>/NN-xxx.md`。

§子目录速查表两行也要更新:

- `[\`user-manual/\`](user-manual/README.md)` → 保持不变
- `[\`technical/\`](technical/README.md)` → 保持不变

但 §常用入口 内的具体链接要改,例:
- `→ [\`user-manual/03-quickstart.md\`](user-manual/03-quickstart.md)` → `→ [\`user-manual/basics/03-quickstart.md\`](user-manual/basics/03-quickstart.md)`
- `→ [\`technical/12-architecture-overview.md\`](technical/12-architecture-overview.md)` → `→ [\`technical/architecture/12-architecture-overview.md\`](technical/architecture/12-architecture-overview.md)`

⚠️ **本步骤的具体改动因文件而异,请人工(或 subagent)逐处修改并人工复核。**

预期:改完后,§常用入口的所有链接都指向新路径。

### Step 6: 同步跨引用 — docs/technical/README.md

**Files:** `docs/technical/README.md`

读取后,§2 章节目录表里所有 `(\`XX-...\`](XX-...)` 形式的相对链接改为 `(\`XX-...\`](<subdir>/XX-...)`。其他章节文件内引用同样处理。

⚠️ **本步骤的具体改动因文件而异,请逐处修改。**

### Step 7: 同步跨引用 — docs/user-manual/README.md

**Files:** `docs/user-manual/README.md`

同 Step 6,改为新路径。

### Step 8: 同步跨引用 — 35 个章节文件内的相对链接

```bash
cd /home/fz/project/cfd--changer
grep -rln -E "\(\.\./[0-9]{2}-[^)]+\.md\)" docs/technical docs/user-manual
```

预期:列出所有包含旧相对链接的章节文件。对每个文件,逐处把 `../NN-xxx.md` 改为 `../<subdir>/NN-xxx.md`(其中 `<subdir>` 是该章节**所引用的章节**所在的子目录,不是该章节自己所在的子目录)。

例:如果 `docs/technical/sweep/12-equation-sweep-extend.md` 引用 `../18-equation-aware-config.md`,应改为 `../sweep/11-equation-aware-config.md`(注:本步骤仅移动不改名,18 暂时保持原编号,11 是 commit 2 改名后才正确 — 11 是在 commit 2 才生效)。

⚠️ **本步骤可能改动较多;建议先 grep 看数量,再分批处理。**

### Step 9: 同步跨引用 — 外部文件(CLAUDE.md, inp_tool/README.md, 6 个 spec)

```bash
cd /home/fz/project/cfd--changer
grep -rn -E "docs/(technical|user-manual)/[0-9]{2}-" CLAUDE.md inp_tool/ docs/superpowers/specs/ 2>&1
```

预期:若有输出,逐文件修改;若无输出,跳过。

### Step 10: 验证 — 旧路径无残留

```bash
cd /home/fz/project/cfd--changer
ls docs/technical/[0-9][0-9]-*.md 2>&1
ls docs/user-manual/[0-9][0-9]-*.md 2>&1
```

预期:两个 ls 都报 `No such file or directory` 错误(因为所有 NN-xxx.md 都已 git mv 到子目录)

### Step 11: 提交 Commit 1

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:看到 35 个 renamed(百分比 100%)+ 若干 modified(README 改的)

```bash
git add -A
git commit -m "docs(restruct): 拆 technical/ 和 user-manual/ 为子目录(不改文件名)

- technical/ → architecture/ + sweep/ + release/ + ux/ + intro/(占位)
- user-manual/ → basics/ + sweep/ + interactive/ + reference/ + advanced/
- 35 个章节文件 git mv 到对应子目录(原文件名/编号保持不变)
- 同步更新 docs/README + technical/README + user-manual/README
- 同步更新 35 个章节文件内的相对链接
- 同步更新 CLAUDE.md / inp_tool/README.md / 6 个 spec 中的引用(若有)
- 详见 docs/superpowers/specs/2026-06-12-docs-restructuring-design.md"
```

预期:commit 成功,显示 `35 files changed` + 若干 README 改动

---

## Task 2: Commit 2 — 子目录内重设 01-N 编号

**Files:**
- Rename: 30 个章节文件(technical/ 17 + user-manual/ 13,user-manual/basics/ 3 个文件名不变)
- Modify: 所有引用了这 30 个旧文件名的相对链接

### Step 1: 列出所有需要改名的文件

```bash
cd /home/fz/project/cfd--changer
find docs/technical docs/user-manual -name "[0-9][0-9]-*.md" | sort
```

预期:35 行输出。**人工对照 spec §3.3**,如有差异停下来核对。

### Step 2: technical/architecture/ 内改名(2 个)

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/architecture/12-architecture-overview.md docs/technical/architecture/01-architecture-overview.md
git mv docs/technical/architecture/13-core-modules.md docs/technical/architecture/02-core-modules.md
```

### Step 3: technical/sweep/ 内改名(12 个)

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/sweep/03-sweep-overview.md docs/technical/sweep/01-sweep-overview.md
git mv docs/technical/sweep/04-sweep-architecture.md docs/technical/sweep/02-sweep-architecture.md
git mv docs/technical/sweep/05-sweep-usage.md docs/technical/sweep/03-sweep-usage.md
git mv docs/technical/sweep/06-sweep-freestream.md docs/technical/sweep/04-sweep-freestream.md
git mv docs/technical/sweep/07-sweep-friendly-uis.md docs/technical/sweep/05-sweep-friendly-uis.md
git mv docs/technical/sweep/08-sweep-testing.md docs/technical/sweep/06-sweep-testing.md
git mv docs/technical/sweep/09-sweep-risks-roadmap.md docs/technical/sweep/07-sweep-risks-roadmap.md
git mv docs/technical/sweep/14-sweep-case-study.md docs/technical/sweep/08-sweep-case-study.md
git mv docs/technical/sweep/16-sweep-flexible.md docs/technical/sweep/09-sweep-flexible.md
git mv docs/technical/sweep/17-sweep-case-dir.md docs/technical/sweep/10-sweep-case-dir.md
git mv docs/technical/sweep/18-equation-aware-config.md docs/technical/sweep/11-equation-aware-config.md
git mv docs/technical/sweep/19-equation-sweep-extend.md docs/technical/sweep/12-equation-sweep-extend.md
```

### Step 4: technical/release/ 内改名(2 个)

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/release/10-cli-packaging.md docs/technical/release/01-cli-packaging.md
git mv docs/technical/release/11-ci-cd.md docs/technical/release/02-ci-cd.md
```

### Step 5: technical/ux/ 内改名(1 个)

```bash
cd /home/fz/project/cfd--changer
git mv docs/technical/ux/15-ux-friendly-cli.md docs/technical/ux/01-ux-friendly-cli.md
```

### Step 6: user-manual/ 子目录内改名(13 个,basics/ 不动)

```bash
cd /home/fz/project/cfd--changer
git mv docs/user-manual/sweep/04-sweeping.md docs/user-manual/sweep/01-sweeping.md
git mv docs/user-manual/sweep/05-config-files.md docs/user-manual/sweep/02-config-files.md
git mv docs/user-manual/sweep/06-naming.md docs/user-manual/sweep/03-naming.md
git mv docs/user-manual/sweep/07-overrides.md docs/user-manual/sweep/04-overrides.md
git mv docs/user-manual/sweep/08-multiple-uis.md docs/user-manual/sweep/05-multiple-uis.md
git mv docs/user-manual/sweep/09-examples.md docs/user-manual/sweep/06-examples.md
git mv docs/user-manual/sweep/10-faq.md docs/user-manual/sweep/07-faq.md
git mv docs/user-manual/interactive/16-repl-quickstart.md docs/user-manual/interactive/01-repl-quickstart.md
git mv docs/user-manual/interactive/17-repl-tour.md docs/user-manual/interactive/02-repl-tour.md
git mv docs/user-manual/interactive/18-wizard-tasks.md docs/user-manual/interactive/03-wizard-tasks.md
git mv docs/user-manual/reference/12-mcfd-inp-field-reference.md docs/user-manual/reference/01-mcfd-inp-field-reference.md
git mv docs/user-manual/reference/13-cli-api-reference.md docs/user-manual/reference/02-cli-api-reference.md
git mv docs/user-manual/reference/15-glossary.md docs/user-manual/reference/03-glossary.md
git mv docs/user-manual/advanced/11-packaging.md docs/user-manual/advanced/01-packaging.md
git mv docs/user-manual/advanced/14-software-tutorial.md docs/user-manual/advanced/02-software-tutorial.md
```

⚠️ **注意:** `user-manual/basics/01-introduction.md`、`02-installation.md`、`03-quickstart.md` **文件名不变**(已是 01-03)。

### Step 7: 同步所有相对链接(从原编号到新编号)

```bash
cd /home/fz/project/cfd--changer
grep -rln -E "\(\.\./(0[3-9]|1[0-9])-[^)]+\.md\)" docs/ 2>&1
```

预期:列出所有文件。对每个文件,逐处把 `../<旧编号>-<slug>.md` 改为 `../<新编号>-<slug>.md`。

⚠️ **对应关系表(从 spec §3):**

| 旧编号 → 新编号 | 文件 |
|---|---|
| 03→01 | technical/sweep/03-sweep-overview.md |
| 04→02 | technical/sweep/04-sweep-architecture.md, user-manual/sweep/04-sweeping.md |
| 05→03 | technical/sweep/05-sweep-usage.md, user-manual/sweep/05-config-files.md |
| 06→04 | technical/sweep/06-sweep-freestream.md, user-manual/sweep/06-naming.md |
| 07→05 | technical/sweep/07-sweep-friendly-uis.md, user-manual/sweep/07-overrides.md |
| 08→06 | technical/sweep/08-sweep-testing.md, user-manual/sweep/08-multiple-uis.md |
| 09→07 | technical/sweep/09-sweep-risks-roadmap.md, user-manual/sweep/09-examples.md |
| 10→01 | technical/release/10-cli-packaging.md, user-manual/sweep/10-faq.md(注意:在不同子目录) |
| 11→02 | technical/release/11-ci-cd.md, user-manual/advanced/11-packaging.md(在不同子目录) |
| 12→01 | technical/architecture/12-architecture-overview.md, user-manual/reference/12-mcfd-inp-field-reference.md(在不同子目录) |
| 13→02 | technical/architecture/13-core-modules.md, user-manual/reference/13-cli-api-reference.md(在不同子目录) |
| 14→08 | technical/sweep/14-sweep-case-study.md, user-manual/advanced/14-software-tutorial.md(在不同子目录) |
| 15→01 | technical/ux/15-ux-friendly-cli.md, user-manual/reference/15-glossary.md(在不同子目录) |
| 16→09 | technical/sweep/16-sweep-flexible.md, user-manual/interactive/16-repl-quickstart.md(在不同子目录) |
| 17→10 | technical/sweep/17-sweep-case-dir.md, user-manual/interactive/17-repl-tour.md(在不同子目录) |
| 18→11 | technical/sweep/18-equation-aware-config.md, user-manual/interactive/18-wizard-tasks.md(在不同子目录) |
| 19→12 | technical/sweep/19-equation-sweep-extend.md |

**注:** 编号 10-18 在 technical/ 和 user-manual/ 都有同名编号但不同主题,所以**替换时要基于完整文件名**(如 `10-cli-packaging.md` 改 `01-cli-packaging.md`,但 `10-faq.md` 改 `07-faq.md`),不能裸编号。

### Step 8: 验证 — 编号 01-N 连续

```bash
cd /home/fz/project/cfd--changer
for d in docs/technical/architecture docs/technical/sweep docs/technical/release docs/technical/ux docs/user-manual/basics docs/user-manual/sweep docs/user-manual/interactive docs/user-manual/reference docs/user-manual/advanced; do
  echo "=== $d ==="
  ls $d/*.md 2>/dev/null | sort
done
```

预期:每个子目录内编号 01-N 连续(可能 N 视子目录而定)
**核对 spec §3.3 表格。**

### Step 9: 验证 — 旧编号无残留

```bash
cd /home/fz/project/cfd--changer
find docs/technical -name "0[3-9]-*.md" -o -name "1[0-9]-*.md" | sort
find docs/user-manual -name "0[4-9]-*.md" -o -name "1[0-9]-*.md" | sort
```

预期:**无输出**(所有旧编号 03-19 都已改为 01-N 连续)
**注意:** `user-manual/basics/01-03` 是 commit 1 时文件名就已是 01-03,本步不动。

### Step 10: 提交 Commit 2

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:30 个 renamed(原编号 → 新编号)+ 若干 modified(链接)

```bash
git add -A
git commit -m "docs(restruct): 子目录内重设 01-N 编号

- technical/architecture/: 12,13 → 01,02
- technical/sweep/: 03-09,14,16-19 → 01-12
- technical/release/: 10,11 → 01,02
- technical/ux/: 15 → 01
- user-manual/sweep/: 04-10 → 01-07
- user-manual/interactive/: 16-18 → 01-03
- user-manual/reference/: 12,13,15 → 01-03
- user-manual/advanced/: 11,14 → 01-02
- user-manual/basics/ 01-03 文件名不变
- 同步更新所有相对链接"
```

预期:commit 成功,显示 30 files changed

---

## Task 3: Commit 3 — 重写 README + 新建子目录 README

**Files:**
- Rewrite: `docs/README.md`, `docs/technical/README.md`, `docs/user-manual/README.md`
- Create: 10 个子目录 README(`docs/technical/{architecture,sweep,release,ux,intro}/README.md` + `docs/user-manual/{basics,sweep,interactive,reference,advanced}/README.md`)

### Step 1: 写 `docs/technical/architecture/README.md`

**File:** `docs/technical/architecture/README.md`

```markdown
# Architecture(架构与核心模块)

> inp_tool 整体架构与 parser/writer/model/diff 四大核心模块设计。

## 章节

| # | 标题 | 内容简介 |
|---|---|---|
| [01-architecture-overview](01-architecture-overview.md) | **inp_tool 架构总览** | 包结构 / 模块依赖 / 数据流 / 入口点 / 外部依赖(10 分钟必读)|
| [02-core-modules](02-core-modules.md) | 核心模块设计 | parser / writer / model / diff 4 模块详细设计 |

## 速读路径

- **5 分钟入门** → [01-architecture-overview](01-architecture-overview.md)
- **想看具体模块** → [02-core-modules](02-core-modules.md) 选模块读

## 关联目录

- 上级: [`../README.md`](../README.md) — 技术手册总览
- 相关: [`../sweep/`](../sweep/) — sweep 模块(本目录的"主用例")
```

### Step 2: 写 `docs/technical/sweep/README.md`

**File:** `docs/technical/sweep/README.md`

```markdown
# Sweep(批量算例生成模块)

> sweep 是 inp_tool 的**核心模块**,负责按笛卡尔积 / 列表 / 整目录复制 / 方程感知等多种模式批量生成 mcfd.inp 算例。

## 章节

| # | 标题 | 内容简介 | 状态 |
|---|---|---|---|
| [**01-sweep-overview**](01-sweep-overview.md) | **sweep 总览** | 背景 / 目标 / 三入口 / 关键能力 / 风险速览 | 当前主线 |
| [02-sweep-architecture](02-sweep-architecture.md) | sweep 架构 & 数据模型 | 流程图 / 5 个 dataclass / `generate()` 主流程 | 当前主线 |
| [03-sweep-usage](03-sweep-usage.md) | sweep 三入口详细用法 | Python API / CLI / FastAPI 完整示例 | 当前主线 |
| [04-sweep-freestream](04-sweep-freestream.md) | FreestreamPreset 几何分解 | 公式 / 默认参数 / 方向假设 | 当前主线 |
| [05-sweep-friendly-uis](05-sweep-friendly-uis.md) | v0.4.2 友好入口 | YAML / 交互式 CLI / Web GUI | 当前主线 |
| [06-sweep-testing](06-sweep-testing.md) | sweep 测试与质量门 | 测试结构 / 覆盖率 / 端到端清单 | 当前主线 |
| [07-sweep-risks-roadmap](07-sweep-risks-roadmap.md) | sweep 风险登记 & roadmap | 8 项风险 + 后续工作 | 当前主线 |
| [08-sweep-case-study](08-sweep-case-study.md) | sweep 案例研究 | 1D/2D sweep + 物理量校验 + 已知坑 | 当前主线 |
| [09-sweep-flexible](09-sweep-flexible.md) | sweep 灵活化 (v0.7.0) | cases/groups/CSV/分组继承(已归档,供回顾) | 已归档 |
| [**10-sweep-case-dir**](10-sweep-case-dir.md) | **sweep 整算例目录 (v0.8.0)** | source_dir / CopyStrategy / per_dir 模式 | **当前主线** |
| [**11-equation-aware-config**](11-equation-aware-config.md) | **方程感知配置 (v0.9.0/0.9.1)** | 9 eqnset 位置 + 5 湍流 + 3 气体 + 4 preset | **当前主线** |
| [12-equation-sweep-extend](12-equation-sweep-extend.md) | 方程感知扩展 (v0.10.0) | sweep 按 case 切方程/湍流/气体(枚举轴 + per-case 覆盖 + alias) | 当前主线 |

## 速读路径

- **5 分钟了解 sweep** → [01-sweep-overview](01-sweep-overview.md)
- **要写配置跑批量** → [03-sweep-usage](03-sweep-usage.md)
- **要改 sweep 代码** → [02-sweep-architecture](02-sweep-architecture.md) + 源码 `inp_tool/inp_tool/sweep.py`
- **遇坑查风险** → [07-sweep-risks-roadmap](07-sweep-risks-roadmap.md)

## 关联目录

- 上级: [`../README.md`](../README.md) — 技术手册总览
- 同级: [`../architecture/`](../architecture/) — 底层架构(本目录依赖)
- 上游用户: [`../../user-manual/sweep/`](../../user-manual/sweep/) — 用户视角的 sweep 用法
```

### Step 3: 写 `docs/technical/release/README.md`

**File:** `docs/technical/release/README.md`

```markdown
# Release(打包与发布)

> inp_tool 的 CLI 打包、跨平台发布、CI/CD 配置。

## 章节

| # | 标题 | 内容简介 |
|---|---|---|
| [01-cli-packaging](01-cli-packaging.md) | CLI 打包与发布 | PyInstaller onedir / standalone / cross-platform |
| [02-ci-cd](02-ci-cd.md) | CI/CD 配置 | GitHub Actions matrix + environment.yml |

## 关联目录

- 上级: [`../README.md`](../README.md) — 技术手册总览
- 关联: [`../../user-manual/advanced/`](../../user-manual/advanced/) — 用户视角的打包说明
```

### Step 4: 写 `docs/technical/ux/README.md`

**File:** `docs/technical/ux/README.md`

```markdown
# UX(用户体验设计)

> inp_tool 的 UX 友好 CLI 设计 — REPL 启动面板 / i18n / wizard 任务流 / 交互细节。

## 章节

| # | 标题 | 内容简介 |
|---|---|---|
| [01-ux-friendly-cli](01-ux-friendly-cli.md) | UX 友好 CLI 设计 | REPL 启动面板 / i18n / wizard 任务流 / 交互细节 |

## 关联目录

- 上级: [`../README.md`](../README.md) — 技术手册总览
- 关联: [`../../user-manual/interactive/`](../../user-manual/interactive/) — 用户视角的 REPL/wizard
```

### Step 5: 写 `docs/technical/intro/README.md`(占位)

**File:** `docs/technical/intro/README.md`

```markdown
# Intro(项目级概念,占位)

> 本目录当前**为空** — 留作未来放置项目级概念性章节(版本策略、兼容性矩阵、术语统一说明等)。
>
> 暂无章节。如需新增,从此目录的 `01-xxx.md` 开始编号。

## 关联

- 上级: [`../README.md`](../README.md) — 技术手册总览
```

### Step 6: 写 `docs/user-manual/basics/README.md`

**File:** `docs/user-manual/basics/README.md`

```markdown
# Basics(入门)

> 如果你是第一次接触 `inp_tool`,从本章开始。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-introduction](01-introduction.md) | 介绍:这是给谁用的 | `inp_tool` 是什么 / 解决什么 / 不解决什么 | 3 分钟 |
| [02-installation](02-installation.md) | 安装 | 系统要求 / conda 环境 / 离线安装 / 验证 | 5 分钟 |
| [03-quickstart](03-quickstart.md) | 快速开始 | 5 分钟跑通第一个批量生成,三种姿势 | 5 分钟 |

## 速读路径

新用户:01 → 02 → 03(约 13 分钟)

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
- 下一步: [`../sweep/01-sweeping.md`](../sweep/01-sweeping.md) — 扫描参数
```

### Step 7: 写 `docs/user-manual/sweep/README.md`

**File:** `docs/user-manual/sweep/README.md`

```markdown
# Sweep(扫描参数)

> sweep 是本工具的**主要用途**;本章把 sweep 从入门讲到精通,含 FAQ。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-sweeping](01-sweeping.md) | 扫描参数 | 可扫哪些字段 / 笛卡尔积 / 来流参数 / 几何分解 | 15 分钟 |
| [02-config-files](02-config-files.md) | 配置文件 | JSON vs YAML vs CLI 怎么选 / 字段详解 | 15 分钟 |
| [03-naming](03-naming.md) | 命名规则 | `str.format` 模板 / 格式说明符 / 校验规则 | 10 分钟 |
| [04-overrides](04-overrides.md) | 字段覆盖 | 改 alpha/ma 之外的字段(时间步、输出频率等) | 15 分钟 |
| [05-multiple-uis](05-multiple-uis.md) | 多入口使用 | CLI / Python / Web GUI / 交互式 / Shell 补全 | 15 分钟 |
| [06-examples](06-examples.md) | 完整示例 | 6 个端到端真实场景 | 20 分钟 |
| [07-faq](07-faq.md) | 常见问题 | 安装/运行/几何分解/路径/性能/调试 | 边用边查 |

## 速读路径

- **30 分钟会用** → 01 + 02
- **完整掌握** → 01-07(约 1.5 小时)

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
- 上游: [`../basics/`](../basics/) — 入门
- 开发者视角: [`../../technical/sweep/`](../../technical/sweep/) — sweep 内部实现
```

### Step 8: 写 `docs/user-manual/interactive/README.md`

**File:** `docs/user-manual/interactive/README.md`

```markdown
# Interactive(交互式工具)

> REPL 与 wizard 是给不爱记命令的工程师用的交互式工具。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-repl-quickstart](01-repl-quickstart.md) | REPL 快速开始 | 5 个最常用 REPL 命令 + 直接命令行模式 | 5 分钟 |
| [02-repl-tour](02-repl-tour.md) | REPL 全功能指南 | 全部命令分组 + 会话变量 + Tab 补全 + 历史 + i18n | 20 分钟 |
| [03-wizard-tasks](03-wizard-tasks.md) | 任务向导 | `wizard modify-file` / `wizard sweep` / `wizard diff` 步骤详解 | 15 分钟 |

## 速读路径

- **5 分钟** → [01-repl-quickstart](01-repl-quickstart.md)
- **要写 wizard** → [03-wizard-tasks](03-wizard-tasks.md)

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
- 开发者视角: [`../../technical/ux/`](../../technical/ux/) — UX 设计
```

### Step 9: 写 `docs/user-manual/reference/README.md`

**File:** `docs/user-manual/reference/README.md`

```markdown
# Reference(参考手册)

> 速查类内容 — 字段、API、术语。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-mcfd-inp-field-reference](01-mcfd-inp-field-reference.md) | mcfd.inp 完整字段参考 | 10 块 × 全部字段,sweep 字段映射 | 30 分钟 |
| [02-cli-api-reference](02-cli-api-reference.md) | CLI / FastAPI / Python 速查 | 7 子命令 + 12 端点 + 24 符号 | 10 分钟 |
| [03-glossary](03-glossary.md) | 术语表 | A-Z 80+ 词条 | 边用边查 |

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
```

### Step 10: 写 `docs/user-manual/advanced/README.md`

**File:** `docs/user-manual/advanced/README.md`

```markdown
# Advanced(进阶)

> 高级用法与教程。

## 章节

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-packaging](01-packaging.md) | 打包与分发 | PyInstaller onedir / standalone CLI / cross-platform | 10 分钟 |
| [02-software-tutorial](02-software-tutorial.md) | 端到端教程 | 5 个真实工作流(alpha-Mach / Web GUI / CI / 单文件 / SLURM) | 30 分钟 |

## 关联

- 上级: [`../README.md`](../README.md) — 用户手册总览
- 开发者视角: [`../../technical/release/`](../../technical/release/) — 打包/CI 内部实现
```

### Step 11: 重写 `docs/README.md`

**File:** `docs/README.md`

```markdown
# cfd--changer 文档总览

本目录是 `cfd--changer` 项目的全部文档归档。下面是各子目录的用途速查与常用入口。

## 子目录速查

| 目录 | 受众 | 内容 | 结构 |
|---|---|---|---|
| [`user-manual/`](user-manual/README.md) | 终端用户(CFD 工程师) | sweep / wizard / REPL / CLI 怎么用 | 5 子目录,18 章 |
| [`technical/`](technical/README.md) | 开发者 | 架构、API、模块设计、测试、打包、CI/CD | 5 子目录,17 章 |
| [`cfd-gui/`](cfd-gui/) | CFD++ GUI 调研者 | 老项目 CFD++ GUI 工程手册 + call graph(静态) | 2 文件(只读) |
| [`plans/`](plans/README.md) | 协作 | 进行中的通用 implementation plan | 完成即删 |
| [`superpowers/specs/`](superpowers/specs/README.md) | 设计追溯 | brainstorming 产生的设计文档(含 STATUS) | 保留 |
| [`superpowers/plans/`](superpowers/plans/README.md) | 协作 | 工作流自动生成的 implementation plan | 完成即删 |

## 常用入口

### 新用户

→ [`user-manual/basics/01-introduction`](user-manual/basics/01-introduction.md) — `inp_tool` 是什么
→ [`user-manual/basics/03-quickstart`](user-manual/basics/03-quickstart.md) — 5 分钟跑通第一个批量生成
→ [`user-manual/interactive/01-repl-quickstart`](user-manual/interactive/01-repl-quickstart.md) — REPL 5 个最常用命令

### 包安装与命令速查

→ [`../inp_tool/README.md`](../inp_tool/README.md) — `inp_tool` 包自述(安装 + Python/CLI/Web API 速查)

### 想理解架构 / 改代码

→ [`technical/architecture/01-architecture-overview`](technical/architecture/01-architecture-overview.md) — 10 分钟过架构
→ [`technical/README.md`](technical/README.md) — 5 子目录索引 + 选读指南
→ [`../CLAUDE.md`](../CLAUDE.md) — 项目硬约束(conda / Win7 / Py3.8)

### 想跟进进行中的设计

→ [`superpowers/specs/README.md`](superpowers/specs/README.md) — spec 列表 + STATUS

## 维护规则

- **过期文档立即删除**,不保留历史(git log 是唯一历史)
- **新增功能模块** → user-manual + technical 同步加章节(从下一个可用编号继续)
- **进行中的 plan** → `plans/` 或 `superpowers/plans/`,完成后删
- **brainstorming 产生的设计** → `superpowers/specs/`,完成后更新 Status 行
- **章节按"主题组 → 子目录"组织** — 不再"按编号"索引;子目录内编号 01-N 连续

详见各子目录 `README.md`。
```

### Step 12: 重写 `docs/technical/README.md`

**File:** `docs/technical/README.md`

```markdown
# cfd--changer 技术手册(总览)

> **审计:** 2026-06-12 · 章节与 v0.11.0 同步 · Phase 1 重整后 · 子目录按职能划分
> 本目录是项目各功能模块的**架构/API/实现细节**文档,面向开发者(读代码、改代码、写扩展)。

---

## 1. 文档组织

- **总览(本文件)** — 索引 + 选读指南
- **子目录** — 按职能划分,每个子目录有自己的 README
- **命名:** `XX-topic-name.md`,`XX` 是子目录内两位数编号(01-N 连续)
- **cfd-gui 调研材料**([`../cfd-gui/`](../cfd-gui/))独立成目录,不在本目录收录

## 2. 子目录索引

| 子目录 | 主题 | 章节数 | 起点章节 |
|---|---|---|---|
| [`architecture/`](architecture/README.md) | inp_tool 架构与核心模块 | 2 | [01-architecture-overview](architecture/01-architecture-overview.md) |
| [`sweep/`](sweep/README.md) | sweep 批量算例生成(本手册主线) | 12 | [01-sweep-overview](sweep/01-sweep-overview.md) |
| [`release/`](release/README.md) | CLI 打包与 CI/CD | 2 | [01-cli-packaging](release/01-cli-packaging.md) |
| [`ux/`](ux/README.md) | UX 友好 CLI 设计 | 1 | [01-ux-friendly-cli](ux/01-ux-friendly-cli.md) |
| [`intro/`](intro/README.md) | 项目级概念(占位) | 0 | — |

## 3. 选读指南

### 3.0 我想理解整体架构(无论改什么模块都建议先看)

→ [`architecture/01-architecture-overview`](architecture/01-architecture-overview.md) (10 分钟, 必读)
→ [`architecture/02-core-modules`](architecture/02-core-modules.md) 按需看具体模块

### 3.1 我是新用户,想用 sweep

→ [`sweep/01-sweep-overview`](sweep/01-sweep-overview.md) (5 分钟)
→ [`sweep/03-sweep-usage`](sweep/03-sweep-usage.md) 选你要的入口
→ [`../user-manual/sweep/`](../user-manual/sweep/) 用户视角的 sweep 用法
→ [`../../inp_tool/README.md`](../../inp_tool/README.md) 安装与快速开始

### 3.2 我想理解 sweep 内部怎么工作

→ [`sweep/01-sweep-overview`](sweep/01-sweep-overview.md) 整体流程
→ [`sweep/02-sweep-architecture`](sweep/02-sweep-architecture.md) 数据模型 + `generate()` 主流程
→ [`sweep/04-sweep-freestream`](sweep/04-sweep-freestream.md) 公式细节
→ 源码 [`../../inp_tool/inp_tool/sweep.py`](../../inp_tool/inp_tool/sweep.py)

### 3.3 我想贡献代码

→ [`sweep/07-sweep-risks-roadmap` §4](sweep/07-sweep-risks-roadmap.md) 贡献指南
→ [`sweep/06-sweep-testing`](sweep/06-sweep-testing.md) 测试结构 + 端到端验证清单
→ [`../../CLAUDE.md`](../../CLAUDE.md) 硬性约束(conda / Win7 / Py3.8)

### 3.4 我遇到了问题

→ [`sweep/07-sweep-risks-roadmap` §5](sweep/07-sweep-risks-roadmap.md) 已知"非 bug"
→ [`sweep/04-sweep-freestream` §4 方向假设](sweep/04-sweep-freestream.md) — 最常见的"值不对"问题
→ GitHub Issues(如有)

### 3.5 我要规划新功能

→ [`sweep/07-sweep-risks-roadmap` §2](sweep/07-sweep-risks-roadmap.md) 已有 roadmap
→ 新功能应先写 `../plans/YYYY-MM-DD_<name>.md`,完成后**直接删除**(git log 是历史;设计意图保留在 [`../superpowers/specs/`](../superpowers/specs/))

---

## 4. 文档维护规则

- **不在此保留历史版本** — 过期内容直接删除或覆盖
- **新功能模块** — 选主题所属子目录,编号接子目录内下一个可用号
- **大章节拆分** — 单一文件超 200 行时按主题拆成多个
- **代码改动** — 同步更新相关章节(架构、API、测试);如改 API,更新 [`sweep/03-sweep-usage`](sweep/03-sweep-usage.md) 和示例
- **进行中的设计文档** — 通用 plan 放 [`../plans/`](../plans/);PRP/brainstorming 工作流的 plan 放 [`../superpowers/plans/`](../superpowers/plans/);完成后均直接删除
- **设计意图保留** — brainstorming 产生的设计文档保留在 [`../superpowers/specs/`](../superpowers/specs/)(含 STATUS 头)

---

## 5. 模块间关系

```
inp_tool/                          ←  核心包
├── parser.py / writer.py / model.py / diff.py   ←  解析/序列化/对比(v0.3)
├── sweep.py                       ←  批量算例生成(v0.4,本手册主文档)
├── cli.py / api.py / web/         ←  三入口(CLI / FastAPI / Web GUI)
└── __init__.py                    ←  公共导出
```

对应文档:
- 核心架构 → [`architecture/`](architecture/README.md)
- sweep 模块 → [`sweep/`](sweep/README.md)(本手册主线)
- 打包/CI → [`release/`](release/README.md)
- UX → [`ux/`](ux/README.md)

---

## 6. 快速跳转

- **代码入口:** [`../../inp_tool/inp_tool/sweep.py`](../../inp_tool/inp_tool/sweep.py) / [`parser.py`](../../inp_tool/inp_tool/parser.py) / [`writer.py`](../../inp_tool/inp_tool/writer.py) / [`diff.py`](../../inp_tool/inp_tool/diff.py) / [`model.py`](../../inp_tool/inp_tool/model.py)
- **架构总览:** [`architecture/01-architecture-overview`](architecture/01-architecture-overview.md)
- **核心模块:** [`architecture/02-core-modules`](architecture/02-core-modules.md)
- **示例配置:** [`../../inp_tool/examples/`](../../inp_tool/examples/)
- **测试:** [`../../inp_tool/tests/`](../../inp_tool/tests/)
- **项目约束:** [`../../CLAUDE.md`](../../CLAUDE.md)
```

### Step 13: 重写 `docs/user-manual/README.md`

**File:** `docs/user-manual/README.md`

```markdown
# cfd--changer 用户手册(总览)

> 本目录是 `inp_tool` 的**用户操作手册**,面向**最终用户** — 用 sweep 工具做 CFD 参数扫描的工程师。
>
> 关注:**怎么用** / **怎么用好**,不涉及内部架构、源码、测试。
>
> 想了解**为什么这样设计**、**怎么实现的**,看 [`../technical/`](../technical/)。

---

## 1. 5 分钟上手路径

| 你的时间 | 读什么 |
|---|---|
| 5 分钟 | [`basics/03-快速开始`](basics/03-quickstart.md) — 跑通第一个批量生成 |
| 30 分钟 | [`sweep/01-扫描参数`](sweep/01-sweeping.md) + [`sweep/02-配置文件`](sweep/02-config-files.md) |
| 1 小时 | 完整读 basics/ + sweep/ ,熟悉所有概念 |
| 1 周 | 加上 interactive/ + reference/ + advanced/ ,处理所有边界情况 |

## 2. 子目录索引

| 子目录 | 主题 | 章节数 | 起点章节 |
|---|---|---|---|
| [`basics/`](basics/README.md) | 入门(介绍 / 安装 / 快速开始) | 3 | [01-introduction](basics/01-introduction.md) |
| [`sweep/`](sweep/README.md) | sweep 入门到精通(含 FAQ) | 7 | [01-sweeping](sweep/01-sweeping.md) |
| [`interactive/`](interactive/README.md) | REPL + Wizard | 3 | [01-repl-quickstart](interactive/01-repl-quickstart.md) |
| [`reference/`](reference/README.md) | 字段参考 + CLI/API 速查 + 术语表 | 3 | [01-mcfd-inp-field-reference](reference/01-mcfd-inp-field-reference.md) |
| [`advanced/`](advanced/README.md) | 打包 + 端到端教程 | 2 | [01-packaging](advanced/01-packaging.md) |

## 3. 选读指南

### 3.1 我是工程师,想扫一组参数

→ [`basics/03-快速开始`](basics/03-quickstart.md) 跑通第一个
→ [`sweep/01-扫描参数`](sweep/01-sweeping.md) 看能扫什么字段
→ [`sweep/02-配置文件`](sweep/02-config-files.md) 写 JSON / YAML
→ [`sweep/06-例`](sweep/06-examples.md) 直接抄模板

### 3.2 我想改 alpha/ma 之外的字段

→ [`sweep/04-字段覆盖`](sweep/04-overrides.md)
→ 看 `inp-tool parse tpl.inp -b tsteps -f` 拿模板字段名

### 3.3 我想集成到自己代码(Python)

→ [`sweep/05-多入口 §4`](sweep/05-multiple-uis.md) Python API
→ [`sweep/06-例 4 / 例 5`](sweep/06-examples.md) 端到端模板

### 3.4 老板/同事不爱用命令行

→ [`sweep/05-多入口 §5`](sweep/05-multiple-uis.md) Web GUI
→ 启动 `python run_server.py`,浏览器开 `http://127.0.0.1:8765/`

### 3.5 出错了

→ [`sweep/07-FAQ`](sweep/07-faq.md) 90% 的问题都有
→ 实在不行提 issue: <https://github.com/oneMuggle/cfd--changer/issues>

### 3.6 我想查某个 .inp 字段是什么意思

→ [`reference/01-mcfd-inp-field-reference`](reference/01-mcfd-inp-field-reference.md) 完整字段表(10 块 × 全部字段)
→ §4 节专列 sweep 关注的字段(对应 sweep 轴)

### 3.7 我想用交互式 REPL / wizard(不爱记命令)

→ [`interactive/01-repl-quickstart`](interactive/01-repl-quickstart.md) 5 个最常用 REPL 命令
→ [`interactive/02-repl-tour`](interactive/02-repl-tour.md) REPL 全功能
→ [`interactive/03-wizard-tasks`](interactive/03-wizard-tasks.md) 3 个任务向导(modify-file / sweep / diff)

## 4. 与其他文档的关系

| 文档 | 视角 | 适合 |
|---|---|---|
| **[本目录 `docs/user-manual/`](.)** | 终端用户(我) | 想用好工具 |
| [`docs/technical/`](../technical/) | 开发者(看代码/扩展) | 想改工具 / 加功能 / 排查内部 bug |
| [`inp_tool/README.md`](../../inp_tool/README.md) | inp_tool 包自述 | 安装 + Python/CLI/Web API 速查 |
| [`CLAUDE.md`](../../CLAUDE.md) | 项目级硬约束(conda/Py3.8/Win7) | 任何修改前必读 |
| `inp_tool/examples/` | 样例 .inp + 配置 | 直接拿 sample 改 |

## 5. 文档维护规则

- **不保留历史版本** — 过期内容直接覆盖
- **新功能加章节** — 选主题所属子目录,编号接子目录内下一个可用号
- **示例代码必须能跑** — 用户复制粘贴就跑不通会很挫败
- **截图 / 录屏** — 当前无(待加);如有 v0.4 之后的 GUI 更新,加 `screenshots/` 子目录
- **英文版** — 当前仅中文;如有需求,起 `docs/user-manual-en/`

## 6. 快速跳转

- **安装:** [`basics/02-安装`](basics/02-installation.md)
- **5 分钟上手:** [`basics/03-快速开始`](basics/03-quickstart.md) 或 [`interactive/01-REPL-快速开始`](interactive/01-repl-quickstart.md)
- **用 REPL / wizard:** [`interactive/02-repl-tour`](interactive/02-repl-tour.md) + [`interactive/03-wizard-tasks`](interactive/03-wizard-tasks.md)
- **看示例:** [`sweep/06-完整示例`](sweep/06-examples.md)
- **查 .inp 字段:** [`reference/01-mcfd-inp-field-reference`](reference/01-mcfd-inp-field-reference.md)
- **用 CLI / API:** [`reference/02-cli-api-reference`](reference/02-cli-api-reference.md)
- **遇到问题:** [`sweep/07-FAQ`](sweep/07-faq.md)
- **想理解内部:** [`../technical/`](../technical/)
```

### Step 14: 验证 — 10 个 README 存在

```bash
cd /home/fz/project/cfd--changer
ls docs/technical/architecture/README.md docs/technical/sweep/README.md docs/technical/release/README.md docs/technical/ux/README.md docs/technical/intro/README.md
ls docs/user-manual/basics/README.md docs/user-manual/sweep/README.md docs/user-manual/interactive/README.md docs/user-manual/reference/README.md docs/user-manual/advanced/README.md
```

预期:每个 `ls` 各 5 行,**所有 10 个 README 都存在**

### Step 15: 验证 — 顶层 README 链接可点(目视 + grep)

```bash
cd /home/fz/project/cfd--changer
grep -oE "\([a-zA-Z0-9_/.~-]*\.md\)" docs/README.md | tr -d '()' | sort -u | while read p; do
  if [[ "$p" =~ ^\.\. ]] || [[ "$p" =~ ^http ]]; then continue; fi
  if [ ! -f "docs/$p" ] && [ ! -f "docs/${p#./}" ]; then
    echo "BROKEN: docs/$p"
  fi
done
echo "验证完成"
```

预期:**无 `BROKEN:` 开头行**(所有引用的相对路径都存在)

### Step 16: 验证 — 各子目录 README 链接

```bash
cd /home/fz/project/cfd--changer
for f in docs/technical/sweep/README.md docs/user-manual/sweep/README.md docs/technical/architecture/README.md docs/user-manual/interactive/README.md docs/technical/release/README.md; do
  echo "=== $f ==="
  grep -oE "\]\([^)]+\.md\)" "$f" | head -10
done
```

预期:每个 README 输出 5-10 行相对链接,所有路径在新结构下应存在

### Step 17: 提交 Commit 3

```bash
cd /home/fz/project/cfd--changer
git status
```

预期:3 个 modified(docs/README, technical/README, user-manual/README) + 10 个 untracked(新建的子目录 README)

```bash
git add -A
git commit -m "docs(restruct): 重写各 README + 新建子目录 README(按主题组索引)

- docs/README.md: 按子目录重写速查表与常用入口
- docs/technical/README.md: 按 5 子目录(architecture/sweep/release/ux/intro)索引
- docs/user-manual/README.md: 按 5 子目录(basics/sweep/interactive/reference/advanced)索引
- 新建 10 个子目录 README,各含章节表 + 速读路径 + 关联目录
- 编号规则:子目录内 01-N 连续,跨子目录不再比大小"
```

预期:commit 成功,显示 3 modified + 10 new files

---

## Task 4: 推分支 + 开 PR

- [ ] **Step 1: 确认在 feature 分支上**

```bash
cd /home/fz/project/cfd--changer
git branch --show-current
```

预期:`docs/restruct-phase1`

- [ ] **Step 2: 推分支到 origin**

```bash
git push -u origin docs/restruct-phase1
```

预期:`branch 'docs/restruct-phase1' set up to track 'origin/docs/restruct-phase1'`

- [ ] **Step 3: 开 PR**

```bash
gh pr create --title "docs(restruct): 拆 technical/ 和 user-manual/ 为子目录(Phase 1)" --body "
## 背景

参见 docs/superpowers/specs/2026-06-12-docs-restructuring-design.md

## 改动

3 commit:

1. \`docs(restruct): 拆 technical/ 和 user-manual/ 为子目录(不改文件名)\` — 35 文件 git mv
2. \`docs(restruct): 子目录内重设 01-N 编号\` — 30 文件重命名
3. \`docs(restruct): 重写各 README + 新建子目录 README\` — 3 README 重写 + 10 子目录 README 新建

## 验证

每个 commit 后已跑 grep 验证清单(spec §7)。所有旧路径无残留,新路径链接完整。

## 测试计划

- [ ] 人工 spot check 5 个章节末尾"相关章节"链接
- [ ] 人工检查 docs/README 顶层导航
- [ ] 人工检查 CLAUDE.md / inp_tool/README.md 中 docs 引用
- [ ] review 整体结构合理性

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

预期:PR URL 输出

- [ ] **Step 4: 监控 CI**

```bash
gh pr checks <PR_NUMBER> --watch
```

预期:所有 check 通过(若失败,STOP 并报告用户)

- [ ] **Step 5: 更新 spec 状态(实施完成后)**

修改 `docs/superpowers/specs/2026-06-12-docs-restructuring-design.md` 第 1 行:

```diff
-**Status:** 待实施
+**Status:** ✅ 已完成 (PR #<NUMBER>, commit <SHA>)
```

提交并合并回 main。

---

## 附录 A:验证清单(汇总,spec §7)

每个 commit 后必跑:

- [ ] `git grep -E "docs/(technical|user-manual)/[0-9]{2}-"` 无匹配(原路径全部清除)
- [ ] `git grep -E "\(\.\./[0-9]{2}-[^)]+\.md\)"` 无失效引用
- [ ] 每个子目录 README 至少 3 个文件链接
- [ ] `docs/README.md` 顶层导航可点
- [ ] `CLAUDE.md` / `inp_tool/README.md` 中 docs 引用正确
- [ ] 6 个 spec 中无失效 docs 引用
- [ ] 至少 1 个章节末尾"相关章节"链接正确(spot check 5 个)
- [ ] `git diff --stat` 在 commit 1 仅显示文件移动 + 链接修改,无意外内容修改

---

## 附录 B:回滚方案(若某 commit 出问题)

```bash
# 回滚 commit 3(HEAD)
git reset --hard HEAD~1

# 回滚 commit 2(再前一个)
git reset --hard HEAD~1

# 回滚 commit 1(回到 main)
git switch main
git branch -D docs/restruct-phase1
```

回滚后,**plan 文件本身**留在 `docs/superpowers/plans/`(不删,因为 Phase 2 复用),spec 状态改回"待实施"。
