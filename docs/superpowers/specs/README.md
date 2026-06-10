# docs/superpowers/specs/ — 设计文档

本目录保留 brainstorming 阶段产生的设计文档。每份 spec 在第 1 行标题下方含 `**Status:**` 行追踪实现状态。

## 当前 spec 列表

| Spec | 简介 | Status |
|---|---|---|
| [2026-06-02 cfdplusplus-toolkit-phase1](2026-06-02-cfdplusplus-toolkit-phase1-design.md) | resid_tool 后处理工具（Phase 1） | 待实施 |
| [2026-06-08 inp-tool-repl](2026-06-08-inp-tool-repl-design.md) | inp-tool 交互式 REPL | ✅ 已实现 v0.7.1 (commit 40dbdbf) |
| [2026-06-10 sweep-completeness-pbs-naming](2026-06-10-sweep-completeness-pbs-naming-design.md) | sweep 完整性 + PBS 可选 + 任务名建议 | ✅ 已实现 v0.9.0 (commit 4e45428) |
| [2026-06-10 docs-cleanup](2026-06-10-docs-cleanup-design.md) | docs/ 目录整理 | ✅ 已完成 (PR #15, commit 45c9845) |

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
- 实现完成后,**立即更新 Status 行**（由 commit 触发）
- 大修改（架构变化、Phase 推进）→ 新建 spec,旧 spec 标 `❌ 已废弃 (替代: <new spec>)`
