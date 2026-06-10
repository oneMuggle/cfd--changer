# docs/superpowers/ — brainstorming/PRP 工作流产物

本目录归档 [`superpowers`](https://github.com/anthropics/claude-code) 插件的 brainstorming + writing-plans + executing-plans 工作流产物。

## 子目录

| 路径 | 用途 | 生命周期 |
|---|---|---|
| [`specs/`](specs/) | 设计文档（brainstorming 产物） | **保留**,含 `**Status:**` 头追踪实现状态 |
| [`plans/`](plans/) | implementation plan（writing-plans 产物） | 完成后**立即删除**（同 [`../plans/`](../plans/)） |

## 与 docs/plans/ 的关系

- `docs/plans/` — 通用 plan（手写、协作产生）
- `docs/superpowers/plans/` — 工作流自动生成的 plan

两者**生命周期一致**（完成即删）,区别仅在 plan 来源。

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
