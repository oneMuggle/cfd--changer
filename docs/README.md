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

### 不知道从哪读起?

→ [INDEX.md](INDEX.md) — 跨维度导航(按主题 / 按受众 / 按任务 三种方式)

### 想跟进进行中的设计

→ [`superpowers/specs/README.md`](superpowers/specs/README.md) — spec 列表 + STATUS

## 维护规则

- **过期文档立即删除**,不保留历史(git log 是唯一历史)
- **新增功能模块** → user-manual + technical 同步加章节(从下一个可用编号继续)
- **进行中的 plan** → `plans/` 或 `superpowers/plans/`,完成后删
- **brainstorming 产生的设计** → `superpowers/specs/`,完成后更新 Status 行
- **章节按"主题组 → 子目录"组织** — 不再"按编号"索引;子目录内编号 01-N 连续

详见各子目录 `README.md`。
