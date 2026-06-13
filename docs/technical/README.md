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
| [`ux/`](ux/README.md) | UX 友好 CLI + GUI 设计 | 1 | [01-gui-architecture](ux/01-gui-architecture.md) |
| [`intro/`](intro/README.md) | 项目级概念(占位) | 0 | — |

---

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
