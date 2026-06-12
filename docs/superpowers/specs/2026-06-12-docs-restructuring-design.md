# docs/ 结构重整 Phase 1 — 拆子目录 + 子目录内重设编号

**Status:** 待实施
**Date:** 2026-06-12
**Phase:** 1 of 2(Phase 2 见末尾 §8)

---

## 1. 背景

`docs/` 在 2026-06-10(#15)与 2026-06-11(#19)两次清理后,目录结构与 README 索引已"够用",但出现三类**结构性**问题:

1. **章节归属混乱** — `technical/` 17 章把 sweep 主线、核心架构、CLI 打包、UX 混在一个目录,读 README 索引表时主题分块不明显
2. **章节编号不连续** — `technical/` 跳 01/02 两个编号,无 README 解释,新人易误判
3. **v0.11.0 章节未补** — wizard-equation-axes(PR #18)合入后,`technical/` 未对应补充新章节

本次重整解决 1 和 2;v0.11.0 章节问题**不在本 spec 范围**(属于内容修订,留待后续 PR)。

---

## 2. 目标

把 `docs/technical/` 和 `docs/user-manual/` 从"按编号连续扁平"重整为"按职能分子目录 + 子目录内 01-N 连续",便于:

- 读 README 索引表时,按主题组查找而非按编号顺序
- 跨子目录互引时路径短(`../sweep/01-overview.md`)
- 未来新章节按主题归位(无需选个"大编号")

---

## 3. 目标结构

### 3.1 `docs/technical/` 拆为 5 个子目录

| 子目录 | 包含章节(原编号 → 新编号) | 主题 |
|---|---|---|
| `intro/` | (占位) | 留作未来新章节/项目级概念 |
| `architecture/` | 12→01, 13→02 | inp_tool 架构总览 + 核心模块 |
| `sweep/` | 03→01, 04→02, 05→03, 06→04, 07→05, 08→06, 09→07, 14→08, 16→09, 17→10, 18→11, 19→12 | sweep 模块全部 |
| `release/` | 10→01, 11→02 | CLI 打包 + CI/CD |
| `ux/` | 15→01 | UX 友好 CLI |

**子目录总数:** 5(其中 `intro/` 本 Phase 不放章节,仅占位 + 简短 README)

### 3.2 `docs/user-manual/` 拆为 5 个子目录

| 子目录 | 包含章节(原编号 → 新编号) | 主题 |
|---|---|---|
| `basics/` | 01→01, 02→02, 03→03 | 介绍 / 安装 / 快速开始 |
| `sweep/` | 04→01, 05→02, 06→03, 07→04, 08→05, 09→06, 10→07 | sweep 入门到精通(含 FAQ) |
| `interactive/` | 16→01, 17→02, 18→03 | REPL + Wizard |
| `reference/` | 12→01, 13→02, 15→03 | 字段参考 + CLI/API 速查 + 术语表 |
| `advanced/` | 11→01, 14→02 | 打包 + 端到端教程 |

### 3.3 完整树状(Phase 1 完成后)

```
docs/
├── README.md                    # 重写
├── plans/                       # 不动
├── superpowers/                 # 不动
├── cfd-gui/                     # 不动(只读)
│
├── technical/
│   ├── README.md                # 重写:跨子目录索引
│   ├── intro/
│   │   └── README.md            # 新建:占位说明
│   ├── architecture/
│   │   ├── README.md
│   │   ├── 01-architecture-overview.md
│   │   └── 02-core-modules.md
│   ├── sweep/
│   │   ├── README.md
│   │   ├── 01-sweep-overview.md
│   │   ├── 02-sweep-architecture.md
│   │   ├── 03-sweep-usage.md
│   │   ├── 04-sweep-freestream.md
│   │   ├── 05-sweep-friendly-uis.md
│   │   ├── 06-sweep-testing.md
│   │   ├── 07-sweep-risks-roadmap.md
│   │   ├── 08-sweep-case-study.md
│   │   ├── 09-sweep-flexible.md
│   │   ├── 10-sweep-case-dir.md
│   │   ├── 11-equation-aware-config.md
│   │   └── 12-equation-sweep-extend.md
│   ├── release/
│   │   ├── README.md
│   │   ├── 01-cli-packaging.md
│   │   └── 02-ci-cd.md
│   └── ux/
│       ├── README.md
│       └── 01-ux-friendly-cli.md
│
└── user-manual/
    ├── README.md                # 重写:跨子目录索引
    ├── basics/
    │   ├── README.md
    │   ├── 01-introduction.md
    │   ├── 02-installation.md
    │   └── 03-quickstart.md
    ├── sweep/
    │   ├── README.md
    │   ├── 01-sweeping.md
    │   ├── 02-config-files.md
    │   ├── 03-naming.md
    │   ├── 04-overrides.md
    │   ├── 05-multiple-uis.md
    │   ├── 06-examples.md
    │   └── 07-faq.md
    ├── interactive/
    │   ├── README.md
    │   ├── 01-repl-quickstart.md
    │   ├── 02-repl-tour.md
    │   └── 03-wizard-tasks.md
    ├── reference/
    │   ├── README.md
    │   ├── 01-mcfd-inp-field-reference.md
    │   ├── 02-cli-api-reference.md
    │   └── 03-glossary.md
    └── advanced/
        ├── README.md
        ├── 01-packaging.md
        └── 02-software-tutorial.md
```

---

## 4. 编号规则

- **子目录内**编号 01-N 连续
- 编号代表"子目录内**阅读顺序**",**不再跨子目录比大小**
- 子目录 README 在第 1 节用一张"速读路径"表展示编号顺序
- 顶层 `docs/technical/README.md` 与 `docs/user-manual/README.md` 用"按主题组 → 子目录"组织,不再用"按编号"索引

---

## 5. 跨引用同步清单(必须改)

### 5.1 README 重写(3 个)

| 文件 | 改动 |
|---|---|
| `docs/README.md` | 重写 §子目录速查表 + §常用入口(各链接改新路径) |
| `docs/technical/README.md` | 重写 §2 章节目录 + §3 选读指南 + §5 模块间关系 + §6 快速跳转 |
| `docs/user-manual/README.md` | 重写 §2 章节目录 + §3 选读指南 + §4 与其他文档的关系 + §6 快速跳转 |

### 5.2 新建子目录 README(10 个)

`docs/technical/` 下 5 个 + `docs/user-manual/` 下 5 个。每个 README 至少包含:
- 用途一句话
- 子目录章节目录表(编号 + 标题 + 一句简介)
- 指向父目录 README 的链接

### 5.3 外部引用修复(必须 grep 确认)

| 文件 | 备注 |
|---|---|
| `CLAUDE.md` | 检查是否有 `docs/technical/12-...` 类引用 |
| `inp_tool/README.md` | 检查同上 |
| `docs/superpowers/specs/2026-06-02-cfdplusplus-toolkit-phase1-design.md` | 检查(待实施) |
| `docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md` | 检查 |
| `docs/superpowers/specs/2026-06-10-docs-cleanup-design.md` | 检查(可能引用 docs/ 内容) |
| `docs/superpowers/specs/2026-06-10-sweep-completeness-pbs-naming-design.md` | 检查 |
| `docs/superpowers/specs/2026-06-11-equation-sweep-extend-design.md` | 检查 |
| `docs/superpowers/specs/2026-06-11-wizard-equation-axes-design.md` | 检查 |

### 5.4 35 个章节文件内相对链接

每个章节内若有指向其他章节的相对链接(常见:章节末尾"相关章节"或"上一篇/下一篇"),全部同步。Phase 1 不做"上一/下一篇"自动插入,只保证**现有**相对链接不失效。

---

## 6. Commit 策略(3 commit)

### Commit 1:`docs(restruct): 拆 technical/ 和 user-manual/ 为子目录(不改文件名)`

- 创建 10 个子目录(intro/ + 5 technical + 5 user-manual 中 9 个实际有内容,intro/ 仅 README)
- 用 `git mv` 移动 35 个章节文件(technical/ 下 17 个:architecture 2 + sweep 12 + release 2 + ux 1;user-manual/ 下 18 个;technical/intro/ 当前为空)
- 同步更新 3 个顶层 README 与 35 个章节内相对链接
- 章节内编号保持原样(如 `12-architecture-overview.md` 移到 `technical/architecture/` 后仍叫 12)

**为什么先不改名:** 让 git history 干净(`git log --follow` 能追到人);reviewer 一眼看出"只是移动了位置"。

### Commit 2:`docs(restruct): 子目录内重设 01-N 编号`

- 在每个子目录内用 `git mv` 把旧编号文件改名为 01-N
- 同步更新所有相对链接(包括章节内自引、README 引用)
- 同步更新每个章节文件第 1 行的"上一篇/下一篇"或"相关章节"段(若有)

### Commit 3:`docs(restruct): 重写各 README + 新建子目录 README(按主题组索引)`

- 重写 `docs/README.md` / `docs/technical/README.md` / `docs/user-manual/README.md`
- 新建 10 个子目录 README
- 全部按"按主题组"组织(不再"按编号"索引)

---

## 7. 验证清单(每个 commit 之后必跑)

- [ ] `git grep -E "docs/(technical|user-manual)/[0-9]{2}-"` 无匹配(原路径全部清除)
- [ ] `git grep -E "\(\.\./[0-9]{2}-[^)]+\.md\)"` 无失效引用
- [ ] 每个子目录 README 至少 3 个文件链接
- [ ] `docs/README.md` 顶层导航可点
- [ ] `CLAUDE.md` / `inp_tool/README.md` 中 docs 引用正确
- [ ] 6 个 spec 中无失效 docs 引用
- [ ] 至少 1 个章节末尾"相关章节"链接正确(spot check 5 个)
- [ ] `git diff --stat` 在 commit 1 仅显示文件移动 + 链接修改,无意外内容修改

---

## 8. Phase 2 范围(本 spec 不实施,仅占位)

Phase 2 将:
- 扫描 35 个章节 + 6 个 spec 内容,找出重复点(常见候选:wizard 流程在多个章节、sweep 配置字段在多个章节、REPL 命令与 wizard 重复)
- 合并冗余 / 加互引
- 新增 `docs/INDEX.md` 统一导航(按主题 / 按受众 / 按任务)
- 单独走 brainstorming + spec,**不**在本 PR 实施

---

## 9. 排除项(明确不做)

- ❌ 不动 `cfd-gui/`(只读,且本项目不维护其内容)
- ❌ 不动 `superpowers/`(specs/ 已存档 + plans/ 当前空)
- ❌ 不动 `plans/`(当前空)
- ❌ 不合并重复章节(留 Phase 2)
- ❌ 不加 `docs/INDEX.md`(留 Phase 2)
- ❌ 不改任何章节的**正文内容**(本次只动归属和文件名;内容修订属其他 PR)
- ❌ 不为 v0.11.0(wizard-equation-axes)补新章节(留作单独 PR,本 spec 范围)
- ❌ 不改 `docs/superpowers/specs/README.md` 的章节列表(那些 spec 指向的是设计阶段名,不指向章节文件)
