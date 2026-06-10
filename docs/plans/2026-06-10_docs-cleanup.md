# docs/ 目录整理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 清理 `docs/` 目录:删除过期/已发布/已被取代的文档,补全索引 README,修复失效链接,同步 `CLAUDE.md §2` 文档结构。净变化约 -3000 行。

**Architecture:** 纯 docs 改动,零代码改动。按 7 个 Phase 顺序执行,每个 Phase 一个 commit。完成后 PR → CI → merge → 清理 plan + 分支。

**Tech Stack:** git + bash(grep / ls / rm) + Markdown 编辑。Smoke check 使用 `conda run -n cfdchanger pytest -q`。

**Spec:** [`docs/superpowers/specs/2026-06-10-docs-cleanup-design.md`](../superpowers/specs/2026-06-10-docs-cleanup-design.md)

**Branch:** `docs/cleanup-2026-06-10` (已创建)

---

## File Structure

### 删除 (3 文件 + 1 目录)

| 路径 | 类型 | 行数 |
|---|---|---|
| `docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md` | 已发布 plan | -2669 |
| `docs/cfd-gui/CFD_GUI_CallGraph.md` | v1, 已被 v2 取代 | -396 |
| `docs/translation/translation_check_report.md` | 过期一次性报告 | -102 |
| `docs/translation/` | 空目录 | — |

### 新建 (5 README + 1 已在前序步骤新建的 spec)

| 路径 | 行数 | 用途 |
|---|---|---|
| `docs/README.md` | ~45 | 顶层文档索引 |
| `docs/plans/README.md` | ~20 | 通用 plan 目录占位说明 |
| `docs/superpowers/README.md` | ~25 | brainstorming/PRP 工作流说明 |
| `docs/superpowers/specs/README.md` | ~25 | spec 列表 + STATUS |
| `docs/superpowers/plans/README.md` | ~15 | superpowers plan 目录占位 |

### 修改 (5 文件)

| 路径 | 改动 |
|---|---|
| `docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md` | 表格行 6 替换 `**状态**` → `**Status**` 待实施 |
| `docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md` | 行 5 替换 `**状态**:` → `**Status:**` ✅ 已实现 v0.7.1 |
| `docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md` | 行 5 替换 `**状态**:` → `**Status:**` ✅ 已实现 v0.9.0 |
| `docs/technical/README.md` | 行 78 §3.5 + 行 88 §4 更新引用 |
| `CLAUDE.md` | §2 项目结构同步 + §3.1 追加 superpowers 说明 |

---

## Phase A: 删除过期文档 (3 文件 + 1 目录)

**Files:**
- Delete: `docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md`
- Delete: `docs/cfd-gui/CFD_GUI_CallGraph.md`
- Delete: `docs/translation/translation_check_report.md`
- Delete: `docs/translation/` (空目录)

### Task A1: 验证 v0.9.0 plan 已发布 + 删除

- [ ] **Step A1.1: 验证对应 commit 已合并**

```bash
cd /home/fz/project/cfd--changer
git log --oneline main | grep -E "4e45428|v0.9.0" | head -3
```

Expected: 看到 `4e45428 feat(sweep): 完整性检查 + pbs 可选 + 任务名建议 (v0.9.0) (#14)`

- [ ] **Step A1.2: 检查文件无被引用**

```bash
grep -r "sweep-completeness-pbs-naming\.md" docs/ inp_tool/ *.md CHANGELOG.md 2>/dev/null
```

Expected: 仅可能出现在 spec 自身或本 plan 内,**不应出现在 README 或其他 doc**

- [ ] **Step A1.3: 删除**

```bash
rm docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md
```

- [ ] **Step A1.4: 验证已删除**

```bash
ls docs/superpowers/plans/ 2>&1
```

Expected: 空目录或仅含其他 plan(本 plan 此时已在 `docs/plans/`,不会出现这里)

### Task A2: 验证 CallGraph v1 无引用 + 删除

- [ ] **Step A2.1: 全仓扫描 CallGraph.md (排除 _v2.md)**

```bash
grep -rE "CFD_GUI_CallGraph\.md([^_]|$)" docs/ inp_tool/ *.md 2>/dev/null
```

Expected: 空结果。如有,**STOP 并报告** — 不能直接删

- [ ] **Step A2.2: 删除**

```bash
rm docs/cfd-gui/CFD_GUI_CallGraph.md
```

- [ ] **Step A2.3: 验证 cfd-gui 目录仅剩 2 文件**

```bash
ls docs/cfd-gui/
```

Expected:
```
CFD_GUI_CallGraph_v2.md
CFD_GUI_Engineering_Handbook.md
```

### Task A3: 删除过期翻译报告 + 空目录

- [ ] **Step A3.1: 检查 translation 报告无引用**

```bash
grep -r "translation_check_report\|docs/translation" docs/ inp_tool/ *.md 2>/dev/null
```

Expected: 仅出现在本 plan / spec(项目说明里也可能引用,但应不在 README 中)

- [ ] **Step A3.2: 删除文件**

```bash
rm docs/translation/translation_check_report.md
```

- [ ] **Step A3.3: 删除空目录**

```bash
rmdir docs/translation/
```

- [ ] **Step A3.4: 验证 docs 顶层不再有 translation**

```bash
ls docs/ | grep -v translation && echo "OK: no translation/"
```

Expected: 看到剩余子目录列表,末尾 "OK: no translation/"

### Task A4: 提交 Phase A

- [ ] **Step A4.1: 查看待提交差异**

```bash
git status
git diff --stat
```

Expected: 3 个 deletion,共减约 3167 行

- [ ] **Step A4.2: 提交**

```bash
git add -A
git commit -m "docs: 删除过期/已发布/已被取代的文档

- docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md
  (对应 v0.9.0 commit 4e45428 已合并发布, 按规则删 plan)
- docs/cfd-gui/CFD_GUI_CallGraph.md (v1, 已被 v2 取代, 无引用)
- docs/translation/translation_check_report.md + 空目录
  (2026-05-23 一次性检查报告, 翻译已 100% 完成)"
```

---

## Phase B: 更新 3 份 spec 的 STATUS 行

**Files:**
- Modify: `docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md:6`
- Modify: `docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md:5`
- Modify: `docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md:5`

### Task B1: cfdplusplus-toolkit-phase1 spec (表格格式)

- [ ] **Step B1.1: 确认原 state**

```bash
sed -n '5,7p' docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md
```

Expected:
```
| **Spec 作者** | brainstorming session, 2026-06-02 |
| **状态** | 设计稿，待人工 review |
| **目标读者** | 后续 writing-plans 阶段（实现工程师） |
```

- [ ] **Step B1.2: 替换 line 6**

用 Edit 工具:
```
old_string: "| **状态** | 设计稿，待人工 review |"
new_string: "| **Status** | 待实施 (resid_tool 后处理工具,未启动) |"
```

- [ ] **Step B1.3: 验证替换成功**

```bash
sed -n '6p' docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md
```

Expected: `| **Status** | 待实施 (resid_tool 后处理工具,未启动) |`

### Task B2: inp-tool-repl spec

- [ ] **Step B2.1: 确认原 state**

```bash
sed -n '3,7p' docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md
```

Expected:
```
**日期**: 2026-06-08
**作者**: brainstorming with user
**状态**: 已批准,待实现
**目标版本**: inp-tool v0.5.0
```

- [ ] **Step B2.2: 替换 line 5**

用 Edit 工具:
```
old_string: "**状态**: 已批准,待实现"
new_string: "**Status:** ✅ 已实现 v0.7.1 (commit 40dbdbf)"
```

- [ ] **Step B2.3: 验证**

```bash
sed -n '5p' docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md
```

Expected: `**Status:** ✅ 已实现 v0.7.1 (commit 40dbdbf)`

### Task B3: sweep-completeness-pbs-naming spec

- [ ] **Step B3.1: 确认原 state**

```bash
sed -n '3,7p' docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md
```

Expected:
```
**日期**: 2026-06-10
**作者**: brainstorming with user
**状态**: 已批准,待实现
**目标版本**: inp-tool v0.9.0
**前置**: v0.8.2(wizard sweep 整目录模式必填)
```

- [ ] **Step B3.2: 替换 line 5**

用 Edit 工具:
```
old_string: "**状态**: 已批准,待实现"
new_string: "**Status:** ✅ 已实现 v0.9.0 (commit 4e45428)"
```

- [ ] **Step B3.3: 验证**

```bash
sed -n '5p' docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md
```

Expected: `**Status:** ✅ 已实现 v0.9.0 (commit 4e45428)`

### Task B4: 提交 Phase B

- [ ] **Step B4.1: 检查差异**

```bash
git diff docs/superpowers/specs/
```

Expected: 3 文件,每个 1 行修改

- [ ] **Step B4.2: 提交**

```bash
git add docs/superpowers/specs/
git commit -m "docs(spec): 3 份 spec 加 STATUS 行 (统一英文 key)

- cfdplusplus-toolkit-phase1: 待实施
- inp-tool-repl: ✅ 已实现 v0.7.1
- sweep-completeness-pbs-naming: ✅ 已实现 v0.9.0"
```

---

## Phase C: 新建 5 份索引 README

**Files:**
- Create: `docs/plans/README.md`
- Create: `docs/superpowers/README.md`
- Create: `docs/superpowers/specs/README.md`
- Create: `docs/superpowers/plans/README.md`
- Create: `docs/README.md`

### Task C1: 创建 docs/plans/README.md

- [ ] **Step C1.1: 确认目录已存在**

```bash
ls docs/plans/
```

Expected: `2026-06-10_docs-cleanup.md`(本 plan; 目录在写本 plan 时已隐式创建)

- [ ] **Step C1.2: 用 Write 工具创建 docs/plans/README.md**

文件内容:

````markdown
# docs/plans/ — 通用 implementation plan

本目录存放**进行中**的通用 implementation plan(手写、协作产生、非 brainstorming/PRP 工作流自动产物)。

## 命名约定

`YYYY-MM-DD_<feature-name>.md` (如 `2026-06-10_docs-cleanup.md`)

## 生命周期

1. **新功能开发前** — 写 plan 到本目录
2. **开发过程中** — 用 `- [ ]` / `- [x]` 标记进度
3. **完成后立即删除** — git log 是唯一历史,plan 不归档
4. **设计意图保留** — brainstorming 阶段产生的设计文档保留在 [`../superpowers/specs/`](../superpowers/specs/)(含 STATUS 头)

## 与 superpowers/plans/ 的区别

| 目录 | 来源 | 适用 |
|---|---|---|
| **本目录** `docs/plans/` | 手写 / 协作 / 非工作流 | 通用 plan |
| [`../superpowers/plans/`](../superpowers/plans/) | brainstorming + writing-plans skill | PRP 工作流自动产物 |

两者**生命周期一致**(完成即删),区别仅在 plan 来源。
````

- [ ] **Step C1.3: 验证文件创建**

```bash
ls docs/plans/
head -3 docs/plans/README.md
```

Expected: README.md 已创建,首行 `# docs/plans/ — 通用 implementation plan`

### Task C2: 创建 docs/superpowers/README.md

- [ ] **Step C2.1: 用 Write 工具创建,内容**

````markdown
# docs/superpowers/ — brainstorming/PRP 工作流产物

本目录归档 [`superpowers`](https://github.com/anthropics/claude-code) 插件的 brainstorming + writing-plans + executing-plans 工作流产物。

## 子目录

| 路径 | 用途 | 生命周期 |
|---|---|---|
| [`specs/`](specs/) | 设计文档(brainstorming 产物) | **保留**,含 `**Status:**` 头追踪实现状态 |
| [`plans/`](plans/) | implementation plan(writing-plans 产物) | 完成后**立即删除**(同 [`../plans/`](../plans/)) |

## 与 docs/plans/ 的关系

- `docs/plans/` — 通用 plan(手写、协作产生)
- `docs/superpowers/plans/` — 工作流自动生成的 plan

两者**生命周期一致**(完成即删),区别仅在 plan 来源。

## 工作流入口

```
brainstorming skill → 设计稿 → spec (docs/superpowers/specs/)
                                ↓
                       writing-plans skill → plan (docs/superpowers/plans/)
                                            ↓
                       executing-plans skill → 实施 + commit
                                            ↓
                                    完成 → 删 plan
                                          (spec 加 STATUS 保留)
```
````

- [ ] **Step C2.2: 验证**

```bash
head -3 docs/superpowers/README.md
```

Expected: 首行 `# docs/superpowers/ — brainstorming/PRP 工作流产物`

### Task C3: 创建 docs/superpowers/specs/README.md

- [ ] **Step C3.1: 用 Write 工具创建,内容**

````markdown
# docs/superpowers/specs/ — 设计文档

本目录保留 brainstorming 阶段产生的设计文档。每份 spec 在第 1 行标题下方含 `**Status:**` 行追踪实现状态。

## 当前 spec 列表

| Spec | 简介 | Status |
|---|---|---|
| [2026-06-02 cfdplusplus-toolkit-phase1](2026-06-02-cfdplusplus-toolkit-phase1-design.md) | resid_tool 后处理工具(Phase 1) | 待实施 |
| [2026-06-08 inp-tool-repl](2026-06-08-inp-tool-repl-design.md) | inp-tool 交互式 REPL | ✅ 已实现 v0.7.1 (commit 40dbdbf) |
| [2026-06-10 sweep-completeness-pbs-naming](2026-06-10-sweep-completeness-pbs-naming-design.md) | sweep 完整性 + PBS 可选 + 任务名建议 | ✅ 已实现 v0.9.0 (commit 4e45428) |
| [2026-06-10 docs-cleanup](2026-06-10-docs-cleanup-design.md) | docs/ 目录整理 | ✅ 已批准,实施中(本次) |

## Status 取值规范

| 取值 | 含义 |
|---|---|
| `待实施` | 已设计,但未启动开发 |
| `✅ 已实现 vX.Y.Z (commit <sha>)` | 已合并发布,可在 git log 追溯 |
| `✅ 已批准,实施中` | 当前正在写 plan / 实施 |
| `🔄 已部分实现 (vX.Y.Z 完成 §N)` | 多 Phase 设计,已完成部分 |
| `❌ 已废弃 (替代方案: <link>)` | 不再实施,有更优方案 |

## 维护规则

- spec **不删除**,作为决策追溯
- 实现完成后,**立即更新 Status 行**(由 commit 触发)
- 大修改(架构变化、Phase 推进)→ 新建 spec,旧 spec 标 `❌ 已废弃 (替代: <new spec>)`
````

- [ ] **Step C3.2: 验证**

```bash
head -3 docs/superpowers/specs/README.md
```

Expected: 首行 `# docs/superpowers/specs/ — 设计文档`

### Task C4: 创建 docs/superpowers/plans/README.md

- [ ] **Step C4.1: 用 Write 工具创建,内容**

````markdown
# docs/superpowers/plans/ — 工作流 implementation plan

本目录存放 brainstorming/PRP 工作流(`writing-plans` skill)自动生成的 plan。

## 当前状态

(目录为空 — 上一个 plan `sweep-completeness-pbs-naming` 对应 v0.9.0 已发布,按规则删除)

## 命名约定

`YYYY-MM-DD-<feature-name>.md`(由 `writing-plans` skill 自动生成)

## 生命周期

1. brainstorming → spec(放 [`../specs/`](../specs/))
2. writing-plans → plan(放本目录)
3. executing-plans / subagent-driven-development → 实施 + commit
4. 完成后 → **立即删除 plan + 更新 spec STATUS 行**

## 与 ../plans/ 的区别

| 目录 | 来源 |
|---|---|
| [`../plans/`](../plans/) | 通用 plan(手写、协作) |
| **本目录** | brainstorming/PRP 工作流自动生成 |

两者**生命周期一致**(完成即删)。
````

- [ ] **Step C4.2: 验证**

```bash
head -3 docs/superpowers/plans/README.md
```

Expected: 首行 `# docs/superpowers/plans/ — 工作流 implementation plan`

### Task C5: 创建顶层 docs/README.md

- [ ] **Step C5.1: 用 Write 工具创建,内容**

````markdown
# cfd--changer 文档总览

本目录是 `cfd--changer` 项目的全部文档归档。下面是各子目录的用途速查与常用入口。

## 子目录速查

| 目录 | 受众 | 内容 | 状态 |
|---|---|---|---|
| [`user-manual/`](user-manual/README.md) | 终端用户(CFD 工程师) | sweep / wizard / REPL / CLI 怎么用 | 18 章 |
| [`technical/`](technical/README.md) | 开发者 | 架构、API、模块设计、测试、打包、CI/CD | 16 章 |
| [`cfd-gui/`](cfd-gui/) | CFD++ GUI 调研者 | 老项目 CFD++ GUI 工程手册 + call graph(静态) | 2 文件 |
| [`plans/`](plans/README.md) | 协作 | 进行中的通用 implementation plan | 完成即删 |
| [`superpowers/specs/`](superpowers/specs/README.md) | 设计追溯 | brainstorming 产生的设计文档(含 STATUS) | 保留 |
| [`superpowers/plans/`](superpowers/plans/README.md) | 协作 | 工作流自动生成的 implementation plan | 完成即删 |

## 常用入口

### 新用户

→ [`user-manual/03-quickstart.md`](user-manual/03-quickstart.md) — 5 分钟跑通第一个批量生成
→ [`user-manual/16-repl-quickstart.md`](user-manual/16-repl-quickstart.md) — REPL 5 个最常用命令

### 包安装与命令速查

→ [`../inp_tool/README.md`](../inp_tool/README.md) — `inp_tool` 包自述(安装 + Python/CLI/Web API 速查)

### 想理解架构 / 改代码

→ [`technical/12-architecture-overview.md`](technical/12-architecture-overview.md) — 10 分钟过架构
→ [`technical/README.md`](technical/README.md) — 16 章索引 + 选读指南
→ [`../CLAUDE.md`](../CLAUDE.md) — 项目硬约束(conda / Win7 / Py3.8)

### 想跟进进行中的设计

→ [`superpowers/specs/README.md`](superpowers/specs/README.md) — spec 列表 + STATUS

## 维护规则

- **过期文档立即删除**,不保留历史(git log 是唯一历史)
- **新增功能模块** → user-manual + technical 同步加章节(从下一个可用编号继续)
- **进行中的 plan** → `plans/` 或 `superpowers/plans/`,完成后删
- **brainstorming 产生的设计** → `superpowers/specs/`,完成后更新 Status 行

详见各子目录 `README.md`。
````

- [ ] **Step C5.2: 验证**

```bash
head -3 docs/README.md
```

Expected: 首行 `# cfd--changer 文档总览`

### Task C6: 提交 Phase C

- [ ] **Step C6.1: 检查所有新文件**

```bash
git status
```

Expected: 5 个 untracked README.md

- [ ] **Step C6.2: 提交**

```bash
git add docs/README.md docs/plans/README.md docs/superpowers/README.md docs/superpowers/specs/README.md docs/superpowers/plans/README.md
git commit -m "docs: 加目录索引 README × 5

- docs/README.md (顶层索引)
- docs/plans/README.md (通用 plan 说明)
- docs/superpowers/README.md (工作流说明)
- docs/superpowers/specs/README.md (spec 列表 + STATUS)
- docs/superpowers/plans/README.md (工作流 plan 说明)"
```

---

## Phase D: 修复 technical/README.md 索引引用

**Files:**
- Modify: `docs/technical/README.md:78`
- Modify: `docs/technical/README.md:88`

### Task D1: 修 line 78 §3.5 "新功能应先写..."

- [ ] **Step D1.1: 确认原状**

```bash
sed -n '76,79p' docs/technical/README.md
```

Expected:
```
### 3.5 我要规划新功能

→ [09-sweep-risks-roadmap §2](09-sweep-risks-roadmap.md) 已有 roadmap
→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后归档到此处,删 plan
```

- [ ] **Step D1.2: 替换 line 78**

用 Edit 工具:
```
old_string: "→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后归档到此处,删 plan"
new_string: "→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后**直接删除**(git log 是历史;设计意图保留在 [`../superpowers/specs/`](../superpowers/specs/))"
```

- [ ] **Step D1.3: 验证**

```bash
sed -n '78p' docs/technical/README.md
```

Expected: 新文本

### Task D2: 修 line 88 §4 文档维护规则

- [ ] **Step D2.1: 确认原状**

```bash
sed -n '86,89p' docs/technical/README.md
```

Expected 第 88 行:
```
- **历史/进行中的设计文档** — 放 [`../plans/`](../plans/);完成后归档到此处,plans 中的文件随之删除
```

- [ ] **Step D2.2: 替换 line 88**

用 Edit 工具(替换原 1 行为 2 行):
```
old_string: "- **历史/进行中的设计文档** — 放 [`../plans/`](../plans/);完成后归档到此处,plans 中的文件随之删除"
new_string: "- **进行中的设计文档** — 通用 plan 放 [`../plans/`](../plans/);PRP/brainstorming 工作流的 plan 放 [`../superpowers/plans/`](../superpowers/plans/);完成后均直接删除\n- **设计意图保留** — brainstorming 产生的设计文档保留在 [`../superpowers/specs/`](../superpowers/specs/)(含 STATUS 头)"
```

- [ ] **Step D2.3: 验证**

```bash
sed -n '88,89p' docs/technical/README.md
```

Expected: 看到两行新内容

### Task D3: 提交 Phase D

- [ ] **Step D3.1: 检查差异**

```bash
git diff docs/technical/README.md
```

Expected: 2 处修改(line 78 + line 88)

- [ ] **Step D3.2: 提交**

```bash
git add docs/technical/README.md
git commit -m "docs(technical): 修 README §3.5 §4 plan/spec 引用

- §3.5: plan 完成后直接删除(不归档), 设计意图保留在 superpowers/specs/
- §4: 区分 docs/plans/(通用) 和 docs/superpowers/plans/(工作流)
- 同时引用两个目录, 都遵守完成即删的规则"
```

---

## Phase E: 同步项目 `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md §2` (项目结构)
- Modify: `CLAUDE.md §3.1` (计划先行,追加一行)

### Task E1: 同步 CLAUDE.md §2 项目结构

- [ ] **Step E1.1: 找到 §2 项目结构位置**

```bash
grep -n "项目结构" CLAUDE.md
```

Expected: 看到 §2 标题行号

- [ ] **Step E1.2: 确认原状**

```bash
grep -n "^├── docs/" CLAUDE.md
sed -n '/^├── docs\//,/^├── analysis_v2/p' CLAUDE.md
```

Expected:
```
├── docs/
│   ├── plans/            # 进行中的计划(完成后删除)
│   ├── technical/        # 已归档技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph
│   ├── translation/      # 翻译检查报告
│   └── superpowers/      # 内部 spec
```

- [ ] **Step E1.3: 替换**

用 Edit 工具:
```
old_string: "├── docs/
│   ├── plans/            # 进行中的计划(完成后删除)
│   ├── technical/        # 已归档技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph
│   ├── translation/      # 翻译检查报告
│   └── superpowers/      # 内部 spec"
new_string: "├── docs/
│   ├── README.md         # 顶层文档索引
│   ├── plans/            # 进行中的通用计划(完成后删除)
│   ├── user-manual/      # 终端用户手册(总览+分章)
│   ├── technical/        # 开发者技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph(老项目静态)
│   └── superpowers/      # brainstorming/PRP 工作流产物
│       ├── specs/        # 设计文档(保留, 含 STATUS 头)
│       └── plans/        # 工作流生成的 implementation plan(完成后删除)"
```

- [ ] **Step E1.4: 验证**

```bash
sed -n '/^├── docs\//,/^├── analysis_v2/p' CLAUDE.md
```

Expected: 看到新结构(无 translation, 含 README + user-manual + superpowers/{specs,plans})

### Task E2: §3.1 追加 superpowers plan 说明

- [ ] **Step E2.1: 找到 §3.1 末尾**

```bash
grep -n "### 3.1 计划先行" CLAUDE.md
grep -n "### 3.2 TDD" CLAUDE.md
```

Expected: 看到 §3.1 起止行号

- [ ] **Step E2.2: 确认 §3.1 末段原状**

```bash
grep -n "完成后归档至 \`docs/technical" CLAUDE.md
sed -n '/完成后归档至/,/### 3.2 TDD/p' CLAUDE.md
```

Expected: 看到段尾 + 下一个标题

- [ ] **Step E2.3: 在 §3.1 末尾追加说明段**

用 Edit 工具,在 "完成后归档..." 那段之后(`### 3.2 TDD` 之前)追加一段:

```
old_string: "完成后归档至 `docs/technical/`,**删除** `docs/plans/` 中的原文件(不保留历史)。

### 3.2 TDD"
new_string: "完成后归档至 `docs/technical/`,**删除** `docs/plans/` 中的原文件(不保留历史)。

> 特殊地,使用 brainstorming/PRP 工作流(superpowers skill)时, plan 可放在 `docs/superpowers/plans/`(完成后同样删除); 对应设计文档保留在 `docs/superpowers/specs/` 并更新 `**Status:**` 行。

### 3.2 TDD"
```

- [ ] **Step E2.4: 验证**

```bash
grep -A 3 "完成后归档至 \`docs/technical" CLAUDE.md
```

Expected: 看到追加的说明段

### Task E3: 提交 Phase E

- [ ] **Step E3.1: 检查差异**

```bash
git diff CLAUDE.md
```

Expected: §2 重写 + §3.1 追加一段

- [ ] **Step E3.2: 提交**

```bash
git add CLAUDE.md
git commit -m "docs(claude): 同步 §2 docs 结构 + §3.1 追加 superpowers plan 说明

- §2: 移除已删的 translation/, 加 user-manual/ + superpowers/{specs,plans}/, 加 README.md
- §3.1: 追加说明 — brainstorming/PRP 工作流可用 docs/superpowers/plans/, 设计文档保留在 specs/
- 本次改动经用户预先确认 (符合 §4 禁止事项 #6)"
```

---

## Phase F: 验收与 smoke check

### Task F1: 死链扫描

- [ ] **Step F1.1: 检查 docs/translation 残留引用**

```bash
grep -rE "docs/translation|translation_check_report" docs/ inp_tool/ *.md 2>&1 | grep -v "^Binary"
```

Expected: 仅可能出现在 spec 自身和本 plan(过程记录),**不应出现在 README 或代码**

- [ ] **Step F1.2: 检查 CallGraph.md v1 残留引用**

```bash
grep -rE "CFD_GUI_CallGraph\.md([^_]|$)" docs/ inp_tool/ *.md 2>&1 | grep -v "^Binary"
```

Expected: 空结果(允许 `_v2.md`)

- [ ] **Step F1.3: 检查已删 plan 残留引用**

```bash
grep -rE "sweep-completeness-pbs-naming\.md" docs/ inp_tool/ *.md 2>&1 | grep -v "^Binary"
```

Expected: 仅出现在 spec 自身(`sweep-completeness-pbs-naming-design.md` — 注意 `-design.md` 后缀,不是 plan)和本 plan

### Task F2: pytest smoke check

- [ ] **Step F2.1: 确认 conda 环境**

```bash
conda run -n cfdchanger python -c "import sys; assert sys.version_info[:2] == (3, 8); print('OK', sys.version)"
```

Expected: `OK 3.8.x ...`

- [ ] **Step F2.2: 跑全部测试**

```bash
cd /home/fz/project/cfd--changer && conda run -n cfdchanger pytest -q inp_tool/tests/ 2>&1 | tail -10
```

Expected: 全绿(`X passed in Y.YYs`)。如有失败,**STOP 并报告** — docs 改动应无影响,但需排除

### Task F3: 验收 checklist (11 条)

- [ ] **Step F3.1: 运行 spec §7 全部验收**

```bash
cd /home/fz/project/cfd--changer

echo "=== 1. find docs 文件数 ===" && find docs -type f | wc -l
echo "=== 2. ls docs/ 不含 translation ===" && ls docs/ | grep -v "^translation$" && echo "(no translation/)"
echo "=== 3. ls docs/cfd-gui/ 仅 2 文件 ===" && ls docs/cfd-gui/
echo "=== 4. ls docs/plans/ ===" && ls docs/plans/
echo "=== 5. ls docs/superpowers/plans/ ===" && ls docs/superpowers/plans/
echo "=== 6. docs/README.md ===" && head -3 docs/README.md
echo "=== 7. specs/README.md ===" && head -3 docs/superpowers/specs/README.md
echo "=== 8. 3 spec 的 Status 行 ===" && grep -H "Status" docs/superpowers/specs/2026-06-0*.md docs/superpowers/specs/2026-06-10-sweep*.md
echo "=== 9-11. 见 F1 ==="
echo "=== 12. CLAUDE.md §2 ===" && sed -n '/^├── docs\//,/^├── analysis_v2/p' CLAUDE.md | head -10
```

Expected: 各条返回预期值

---

## Phase G: PR 流程

### Task G1: push feature 分支

- [ ] **Step G1.1: 查看本地 commits**

```bash
git log origin/main..HEAD --oneline
```

Expected: 5-6 个 commits(spec + Phase A-E)

- [ ] **Step G1.2: push**

```bash
git push -u origin docs/cleanup-2026-06-10
```

Expected: 推送成功,返回 PR 创建提示 URL

### Task G2: 创建 PR

- [ ] **Step G2.1: 创建 PR**

```bash
gh pr create --title "docs: 整理 docs/ 目录 (2026-06-10)" --body "$(cat <<'EOF'
## 背景

docs/ 目录经过多个版本迭代后出现过期/已发布/已被取代的文档,以及索引与真实结构不一致的问题。本 PR 一次性整理。

详见 [spec: docs/superpowers/specs/2026-06-10-docs-cleanup-design.md](../blob/docs/cleanup-2026-06-10/docs/superpowers/specs/2026-06-10-docs-cleanup-design.md)。

## 主要改动

### 删除 (3 文件 + 1 目录, -3167 行)

- 已发布 v0.9.0 的 implementation plan (commit 4e45428)
- CFD_GUI_CallGraph.md v1 (已被 v2 取代, 无引用)
- 2026-05-23 翻译检查报告 + 空 translation 目录

### 新增 (5 份索引 README)

- docs/README.md (顶层索引)
- docs/plans/README.md + docs/superpowers/{README, specs/README, plans/README}.md

### 修改 (5 文件)

- 3 份 spec 加 \`**Status:**\` 头(统一英文 key, 区分待实施/已实现)
- docs/technical/README.md §3.5 §4 修引用(plan 完成后删除而非归档; 区分通用/工作流 plan)
- CLAUDE.md §2 同步真实结构(去 translation, 加 superpowers/{specs,plans}); §3.1 追加 superpowers 说明

## 测试

- [x] grep 扫死链 3 条(translation / CallGraph v1 / 已发布 plan)
- [x] pytest smoke check 全绿
- [x] spec §7 验收 checklist 11 条通过

## 风险

- 纯 docs 改动, 零代码改动
- CLAUDE.md 改动经用户预先确认(符合 §4 禁止事项 #6 要求)

## 合并后

按规则删除本 PR 引入的 plan 文件 docs/plans/2026-06-10_docs-cleanup.md
EOF
)"
```

Expected: 输出 PR URL

- [ ] **Step G2.2: 监控 CI(如有)**

```bash
gh pr checks --watch
```

Expected: 所有 check 通过(docs-only 改动一般无 CI 影响)

### Task G3: 等用户 merge

- [ ] **Step G3.1: 通知用户**

报告 PR URL,等用户 review + merge。

---

## Phase H: merge 后清理

> ⚠️ 本 Phase 在用户 merge PR **之后**执行,不能在 PR 阶段做。

### Task H1: 切回 main + 拉新

- [ ] **Step H1.1: 切 main**

```bash
git switch main
git pull --rebase origin main
```

Expected: main 已含本次 merge

### Task H2: 删本 plan 文件

- [ ] **Step H2.1: 删 plan**

```bash
rm docs/plans/2026-06-10_docs-cleanup.md
git add docs/plans/2026-06-10_docs-cleanup.md
git commit -m "docs(plan): 删除已完成 plan docs-cleanup (按规则)"
git push origin main
```

> 注:这一步是直接 push main 的小型 docs 改动 — 单行删除,符合 feature-branch §1 表中的"小型 docs 微调"例外。
> 也可选择再开个微小分支走 PR,但按规则单纯删 plan 文件可直推。

### Task H3: 删 feature 分支

- [ ] **Step H3.1: 删本地 + 远程**

```bash
git branch -d docs/cleanup-2026-06-10
git push origin --delete docs/cleanup-2026-06-10
```

Expected: 两侧分支均已删

### Task H4: 同步 superpowers/specs/README.md + spec Status

- [ ] **Step H4.1: 更新本 spec 的 Status**

由于本 spec(`2026-06-10-docs-cleanup-design.md`)对应的整理已完成,把其 Status 从 "✅ 已批准,待实施" 改为 "✅ 已完成 (PR #XX, commit <sha>)":

用 Edit 工具修改 `docs/superpowers/specs/2026-06-10-docs-cleanup-design.md` 第 4 行 `**Status**: ✅ 已批准,待实施` → `**Status**: ✅ 已完成 (PR #XX, commit <sha>)`。

同时更新 `docs/superpowers/specs/README.md` 的 docs-cleanup 行 Status。

```bash
git add docs/superpowers/specs/
git commit -m "docs(spec): docs-cleanup spec Status → 已完成"
git push origin main
```

---

## 完成状态总览

| Phase | 内容 | Commits |
|---|---|---|
| (前置) | spec 写入 + commit | 1 (`ec09721`) |
| A | 删除 3 文件 + 1 目录 | 1 |
| B | 更新 3 份 spec Status | 1 |
| C | 新增 5 份 README | 1 |
| D | 修 technical/README §3.5 §4 | 1 |
| E | 同步 CLAUDE.md §2 + §3.1 | 1 |
| F | 验收 + smoke check | 0 (无 commit) |
| G | push + PR | 0 (无 commit) |
| **PR merge** | — | (用户操作) |
| H | 删 plan + 清分支 + 更新 spec Status | 2 (post-merge) |

**总 commits: 8**(含 spec 前置 + post-merge 清理)。

---

## 备注

- 本 plan 自身按规则在 merge 后(Phase H)删除
- spec(`2026-06-10-docs-cleanup-design.md`)保留,Status 更新为"已完成"
- 整个流程为后续 docs 维护提供模板:遇到过期文档 → 建分支 → spec + plan → 执行 → PR → 清理
