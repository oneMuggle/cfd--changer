# docs/ 目录整理 — 设计文档

**日期**: 2026-06-10
**作者**: brainstorming with user
**Status:** ✅ 已完成 (PR #15, commit 45c9845)

---

## 1. 背景与目标

### 1.1 问题

经盘点 `docs/` 目录,发现以下不一致与过期项:

1. **`docs/plans/` 目录不存在**,但 `docs/technical/README.md` §4 引用了它
2. **`docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md`** 对应 v0.9.0 功能已合并发布 (commit `4e45428`),按项目规则 plan 完成后应删除
3. **`docs/cfd-gui/CFD_GUI_CallGraph.md` (v1, 396 行)** 已被 `CFD_GUI_CallGraph_v2.md` (2484 行) 取代,无文档引用
4. **`docs/translation/translation_check_report.md`** 是 2026-05-23 一次性检查报告,结论"翻译已 100% 完成",已过期
5. **顶层 `docs/` 无 README**,新用户/贡献者不知道每个子目录用途
6. **项目 `CLAUDE.md §2` 文档结构** 与 docs 实际状态不一致(列了 `translation/`,没列 `superpowers/{specs,plans}/`)

### 1.2 目标

- 删除已过期 / 已发布 / 已被取代的文档
- 建立 `docs/plans/` 作为**通用 plan 目录**(非 superpowers 工作流也能用)
- 保留 `docs/superpowers/{specs,plans}/` 作为 brainstorming/PRP 工作流的产物归档
- 为所有子目录写 README,清晰说明用途与生命周期
- 修复所有失效内部链接
- 同步项目 `CLAUDE.md §2` 的文档结构描述

### 1.3 非目标

- 不重写已有 `technical/` `user-manual/` 章节内容
- 不动 `inp_tool/` 包代码或测试
- 不创建英文版文档
- 不动 `CLAUDE.md §3.1`(plan 路径仍为 `docs/plans/`)

---

## 2. 目录结构(整理后)

```
docs/
├── README.md                            # 新建: 顶层文档索引
├── plans/                               # 新建: 通用 plan 目录
│   └── README.md                        # 新建: 目录用途说明
├── user-manual/                         # 不变: 18 章 + README
├── technical/                           # 微改: 修 README §4 引用
├── cfd-gui/                             # 删 v1: 仅保留 Engineering_Handbook + CallGraph_v2
└── superpowers/                         # 工作流产物
    ├── README.md                        # 新建: 工作流说明
    ├── specs/                           # 保留: 加 STATUS 头
    │   ├── README.md                    # 新建: spec 列表 + 状态
    │   ├── 2026-06-02-cfdplusplus-toolkit-phase1-design.md  (+ Status: 待实施)
    │   ├── 2026-06-08-inp-tool-repl-design.md               (+ Status: 已实现 v0.7.1)
    │   ├── 2026-06-10-sweep-completeness-pbs-naming-design.md (+ Status: 已实现 v0.9.0)
    │   └── 2026-06-10-docs-cleanup-design.md                (本文件)
    └── plans/                           # 仅保留进行中
        ├── README.md                    # 新建: 目录用途说明
        └── (空; 已删 sweep-completeness-pbs-naming.md)

(删除)
docs/translation/                        # 整个目录删除
docs/cfd-gui/CFD_GUI_CallGraph.md        # v1 删除
```

---

## 3. 具体改动清单

### 3.1 删除项

| 路径 | 类型 | 删除原因 |
|---|---|---|
| `docs/superpowers/plans/2026-06-10-sweep-completeness-pbs-naming.md` | 2669 行 plan | 对应 v0.9.0 commit `4e45428` 已合并发布 |
| `docs/cfd-gui/CFD_GUI_CallGraph.md` | 396 行 | 已被 v2 (2484 行) 取代,无引用 |
| `docs/translation/translation_check_report.md` | 102 行 | 2026-05-23 一次性报告,结论已达成 |
| `docs/translation/` | 空目录 | 报告删除后空,无未来用途 |

### 3.2 修改项 (3 份 spec 更新 STATUS 行)

三份已有 spec 的头部均已有"状态/Status"行,**就地替换**(不新增):

| 文件 | 原状态行(替换前) | 新状态行(替换后) |
|---|---|---|
| `2026-06-02-cfdplusplus-toolkit-phase1-design.md` | 第 6 行表格行 `\| **状态** \| 设计稿,待人工 review \|` | `\| **Status** \| 待实施 (resid_tool 后处理工具,未启动) \|` |
| `2026-06-08-inp-tool-repl-design.md` | 第 5 行 `**状态**: 已批准,待实现` | `**Status:** ✅ 已实现 v0.7.1 (commit 40dbdbf)` |
| `2026-06-10-sweep-completeness-pbs-naming-design.md` | 第 5 行 `**状态**: 已批准,待实现` | `**Status:** ✅ 已实现 v0.9.0 (commit 4e45428)` |

风格统一为 `**Status:**`(英文),与本 spec 及未来 spec 模板一致。

### 3.3 新建文档 (5 份 README + 1 份本 spec)

#### A. `docs/README.md` — 顶层索引

包含:
- 子目录速查表(7 行: README / plans / user-manual / technical / cfd-gui / superpowers/specs / superpowers/plans)
- 常用入口(新用户 → quickstart; 看架构 → architecture-overview; 改代码前 → CLAUDE.md)
- 指向 `inp_tool/README.md` 的入口(包级 README)

#### B. `docs/plans/README.md` — 通用 plan 占位

说明:
- 本目录放**进行中**的 implementation plan
- 命名 `YYYY-MM-DD_<name>.md`
- 完成后**立即删除**(不归档,不留历史 — git log 是唯一历史)
- 与 `docs/superpowers/plans/` 的区别:本目录是通用 plan(手写、协作产生); superpowers/plans/ 是 PRP/brainstorming 工作流自动产物

#### C. `docs/superpowers/README.md` — 工作流说明

说明:
- 本目录是 brainstorming + writing-plans + executing-plans 工作流产物归档
- specs/ 保留(含 STATUS 头, 用于追溯设计意图)
- plans/ 与 docs/plans/ 同语义(完成即删, 仅过程留 git log)

#### D. `docs/superpowers/specs/README.md` — spec 状态列表

包含 4 份 spec 的 1 行简介 + STATUS + 链接的表格。

#### E. `docs/superpowers/plans/README.md` — superpowers plan 占位

类似 B,但强调"由 PRP/brainstorming 工作流生成"。

#### F. `docs/superpowers/specs/2026-06-10-docs-cleanup-design.md` — 本文件

### 3.4 修改 `docs/technical/README.md`

**第 78 行** §3.5(我要规划新功能):

当前:
```
→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后归档到此处,删 plan
```

改为(完成后**直接删除**,不归档):
```
→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后删除(git log 是历史; 设计意图保留在 `../superpowers/specs/`)
```

**第 88 行** §4 文档维护规则,改为:

```markdown
- **进行中的设计文档** — 通用 plan 放 [`../plans/`](../plans/);PRP/brainstorming 工作流的 plan 放 [`../superpowers/plans/`](../superpowers/plans/);完成后均直接删除
- **设计意图保留** — brainstorming 产生的设计文档保留在 [`../superpowers/specs/`](../superpowers/specs/)(含 STATUS 头)
```

### 3.5 修改项目根 `CLAUDE.md §2` 项目结构

**当前**(约第 87 行):

```
├── docs/
│   ├── plans/            # 进行中的计划(完成后删除)
│   ├── technical/        # 已归档技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph
│   ├── translation/      # 翻译检查报告
│   └── superpowers/      # 内部 spec
```

**改为**:

```
├── docs/
│   ├── README.md         # 顶层文档索引
│   ├── plans/            # 进行中的通用计划(完成后删除)
│   ├── user-manual/      # 终端用户手册(总览+分章)
│   ├── technical/        # 开发者技术手册(总览+分章)
│   ├── cfd-gui/          # CFD++ GUI 手册与 call graph(老项目静态)
│   └── superpowers/      # brainstorming/PRP 工作流产物
│       ├── specs/        # 设计文档(保留, 含 STATUS 头)
│       └── plans/        # 工作流生成的 implementation plan(完成后删除)
```

**§3.1 主体路径不动** —— 仍指向 `docs/plans/<YYYY-MM-DD>_<name>.md`;**仅追加一行**说明:
> 特殊地,使用 brainstorming/PRP 工作流时, plan 可放在 `docs/superpowers/plans/`(完成后同样删除)。

---

## 4. 净影响

| 维度 | 变化 |
|---|---|
| 文件删除 | 3 个(共 ~3167 行) |
| 目录删除 | 1 个(`docs/translation/`) |
| 文件新建 | 6 个(共 ~150 行 README + 本 spec) |
| 文件修改 | 5 个(3 spec STATUS 头 + technical/README + CLAUDE.md) |
| **净行数** | **约 -3000 行** |
| 代码改动 | 0 |
| 测试改动 | 0 |

---

## 5. 风险与缓解

| 风险 | 概率 | 缓解 |
|---|---|---|
| docs 链接失效未发现 | 中 | 整理后用 `grep -r "docs/translation\|CFD_GUI_CallGraph\.md\|sweep-completeness-pbs-naming\.md"` 扫一遍 |
| 删 `CallGraph.md` v1 影响外部 | 低 | 已 grep 全 `docs/` 与 `inp_tool/` 无引用; 外部如有引用应升 v2 |
| pytest 受 docs 删除影响 | 极低 | inp_tool 测试不读 docs/;但仍 smoke check 一次 |
| 删 v0.9.0 plan 丢失实现细节 | 低 | 详细仍在 spec(已加 STATUS 头);代码本身 + git log + spec 三层保证 |
| 改 CLAUDE.md §2 影响其他 agent | 低 | 改后仍是真实文档结构, 不会误导;且本次改动与用户预先确认 |

---

## 6. 实施工作流

按项目 `feature-branch-workflow.md`:

```
1. ✅ git switch -c docs/cleanup-2026-06-10  (已完成)
2. 写本 spec  (本文件)
3. 写 implementation plan → docs/plans/2026-06-10_docs-cleanup.md
4. 按 plan 执行(删 + 改 + 新建)
5. grep 扫死链
6. conda run -n cfdchanger pytest -q (smoke)
7. git add + commit(分多个 commit:删除/新建/修索引/改 CLAUDE.md)
8. git push -u origin docs/cleanup-2026-06-10
9. gh pr create
10. 用户 review + merge
11. merge 后清理: 删本 plan(本身也是 plan) + 删 feature 分支
```

---

## 7. 验收标准

- [ ] `find docs -type f | wc -l` 减少 3
- [ ] `ls docs/` 不含 `translation/`
- [ ] `ls docs/cfd-gui/` 仅含 2 个文件 (Engineering_Handbook + CallGraph_v2)
- [ ] `ls docs/plans/` 含 README.md(以及当前 plan,后续清除)
- [ ] `ls docs/superpowers/plans/` 仅含 README.md(plan 已删)
- [ ] `cat docs/README.md` 列出全部子目录
- [ ] `cat docs/superpowers/specs/README.md` 列出 4 份 spec 含 STATUS
- [ ] 3 份已实现 spec 的第 5 行附近有 `**Status:**` 行
- [ ] `grep -r "docs/translation" docs/ inp_tool/ *.md` 无结果
- [ ] `grep -r "CFD_GUI_CallGraph\.md[^_]" docs/ *.md` 无结果(允许 `_v2.md`)
- [ ] `cat CLAUDE.md` §2 项目结构已同步真实状态
- [ ] `conda run -n cfdchanger pytest -q` 全绿(smoke)

---

## 8. 后续维护

- 整理工作完成后, **删除** `docs/plans/2026-06-10_docs-cleanup.md`(implementation plan)
- 本 spec 文件保留在 `docs/superpowers/specs/` 作为决策记录
- 未来 docs 再次出现"已发布的 plan 滞留"或"链接失效"等问题, 可参考本次流程
