# docs/superpowers/plans/ — 工作流 implementation plan

本目录存放 brainstorming/PRP 工作流（`writing-plans` skill）自动生成的 plan。

## 当前状态

（目录为空 — 上一个 plan `sweep-completeness-pbs-naming` 对应 v0.9.0 已发布,按规则删除）

## 命名约定

`YYYY-MM-DD-<feature-name>.md`（由 `writing-plans` skill 自动生成）

## 生命周期

1. brainstorming → spec（放 [`../specs/`](../specs/)）
2. writing-plans → plan（放本目录）
3. executing-plans / subagent-driven-development → 实施 + commit
4. 完成后 → **立即删除 plan + 更新 spec STATUS 行**

## 与 ../plans/ 的区别

| 目录 | 来源 |
|---|---|
| [`../plans/`](../plans/) | 通用 plan（手写、协作） |
| **本目录** | brainstorming/PRP 工作流自动生成 |

两者**生命周期一致**（完成即删）。
