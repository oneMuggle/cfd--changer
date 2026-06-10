# docs/plans/ — 通用 implementation plan

本目录存放**进行中**的通用 implementation plan（手写、协作产生、非 brainstorming/PRP 工作流自动产物）。

## 命名约定

`YYYY-MM-DD_<feature-name>.md` (如 `2026-06-10_docs-cleanup.md`)

## 生命周期

1. **新功能开发前** — 写 plan 到本目录
2. **开发过程中** — 用 `- [ ]` / `- [x]` 标记进度
3. **完成后立即删除** — git log 是唯一历史,plan 不归档
4. **设计意图保留** — brainstorming 阶段产生的设计文档保留在 [`../superpowers/specs/`](../superpowers/specs/)（含 STATUS 头）

## 与 superpowers/plans/ 的区别

| 目录 | 来源 | 适用 |
|---|---|---|
| **本目录** `docs/plans/` | 手写 / 协作 / 非工作流 | 通用 plan |
| [`../superpowers/plans/`](../superpowers/plans/) | brainstorming + writing-plans skill | PRP 工作流自动产物 |

两者**生命周期一致**（完成即删）,区别仅在 plan 来源。
