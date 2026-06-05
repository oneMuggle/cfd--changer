# 03 — 批量算例生成器(sweep)总览

> **审计:** 2026-06-04 · 章节与 v0.4.0 同步 · 全部示例通过 · 全部链接有效
**模块:** `inp_tool.sweep`  ·  **版本:** v0.4.0  ·  **状态:** 已发布(PR #1 已合入 main)

---

## 1. 一句话

基于一个 `mcfd.inp` 样例,扫描 (alpha, beta, Mach, ...) 一次生成 N 个 `.inp` 变体 + 一份 `manifest.json` 索引。

## 2. 解决的问题

CFD++ `mcfd.inp` 的批量参数研究(攻角/侧滑角/马赫扫描)历来靠手工复制 + 文本编辑器改值,易错且不可追溯。`inp_tool` v0.3 已提供 parser/writer/diff 三件套,但仍需用户自己写胶水代码。v0.4 起新增 `inp_tool.sweep` 声明式批量生成器,补完这条链路。

## 3. 适用场景

| 场景 | 示例 |
|---|---|
| 飞行器气动参数扫描 | alpha ∈ {0,2,4,6,8,10}°,Mach ∈ {0.6,0.8} |
| 进气道畸变指数研究 | 7 个进口测点压差组合 |
| 翼型结冰工况 | alpha × beta × Re 笛卡尔积 |
| 大规模 DOE | 100+ 算例一键生成,后续送调度 |

## 4. 三种入口

| 入口 | 一行示例 | 适用 |
|---|---|---|
| **Python API** | `from inp_tool import CaseSweep, generate` | 集成到自己脚本/Notebook |
| **CLI** | `inp-tool sweep tpl.inp --alpha 0,4,8 --mach 0.6,0.8` | 终端用户 |
| **FastAPI** | `POST /api/sweep` | Web GUI / 远程调用 |

详见 [05-sweep-usage.md](05-sweep-usage.md)。

## 5. v0.4.0 友好层(降低使用门槛)

| 层 | 触发方式 | 解决的问题 |
|---|---|---|
| **YAML 配置** | `inp-tool sweep foo.yaml` | JSON 难手写,需 `[yaml]` extras |
| **交互式 CLI** | `inp-tool sweep -i` | 忘记参数名时一步步问 |
| **Web GUI** | 浏览器切"批量生成"标签 | 不爱写命令行的同事 |
| **Shell 补全** | `eval "$(inp-tool completion bash)"` | Tab 补全子命令 |

详见 [07-sweep-friendly-uis.md](07-sweep-friendly-uis.md)。

## 6. 关键能力

- **笛卡尔积展开** — N 个 sweep 轴自动展开
- **几何分解 preset** — `(alpha, beta, Mach, T)` → `(U, V, W)` 自动算出 `aero_u/v/w` 与 `refvel`
- **命名模板** — Python `str.format(**params)` 风格;冲突自动追加 `_1`, `_2`...
- **manifest 索引** — 包含 template hash、所有 case 的 params + applied 字段,供下游脚本消费
- **dry-run** — 试运行不算不写
- **overrides 两种风格** — `{block: {keyword: val}}` 或 `{"block.keyword": val}`

详见 [04-sweep-architecture.md](04-sweep-architecture.md)。

## 7. 已知风险(高优)

1. **几何分解方向假设** — 默认 `U=Ma·a·cos(α)·cos(β)`, `V=Ma·a·sin(β)`, `W=Ma·a·sin(α)·cos(β)` 可能与某些 CFD++ 版本不一致。**缓解:** `freestream.enabled=false` 跳过 preset,只用 `overrides` 手动改 `aero_u/v/w`。
2. **round-trip 空白重构造** — `inp_tool` v0.2 已知限制(不是 sweep 引入的)。**缓解:** 已记录,后续可加 preserve-format 选项。

详见 [09-sweep-risks-roadmap.md](09-sweep-risks-roadmap.md)。

## 8. 测试 & 质量门

- 134/134 测试通过(55 既有 + 79 新增)
- 整体覆盖率 81%, `sweep.py` 自身 93%
- 端到端验证(CLI/YAML/交互式/Web 全部跑通)

详见 [08-sweep-testing.md](08-sweep-testing.md)。

## 9. 后续工作(roadmap)

- v0.5: 完整 YAML schema + `pyyaml` 默认进依赖
- v0.6: 进度条 / 流式生成 / 任务取消
- v0.7: 与 CFD++ 求解器集成(批量提交作业)

详见 [09-sweep-risks-roadmap.md](09-sweep-risks-roadmap.md) §2。

## 10. 子文档索引

| 文件 | 主题 |
|---|---|
| [04-sweep-architecture.md](04-sweep-architecture.md) | 数据模型 / 流程图 / generate 主流程 |
| [05-sweep-usage.md](05-sweep-usage.md) | Python / CLI / FastAPI 详细用法 |
| [06-sweep-freestream.md](06-sweep-freestream.md) | 几何分解公式 / 适用条件 / 字段映射 |
| [07-sweep-friendly-uis.md](07-sweep-friendly-uis.md) | YAML / 交互式 / Web GUI / Shell 补全 |
| [08-sweep-testing.md](08-sweep-testing.md) | 测试结构 / 覆盖率 / 端到端 |
| [09-sweep-risks-roadmap.md](09-sweep-risks-roadmap.md) | 风险登记 / 后续工作 |

## 11. 与 inp_tool 其他模块的关系

```
inp_tool/
├── parser.py  ──┐
├── writer.py  ──┤
├── model.py   ──┼──> sweep.py (本模块)  ──> 多个 .inp + manifest.json
├── diff.py    ──┘                ▲
│                                  │
└── api.py / cli.py / web/ ───────┘ (三个入口)
```

- 依赖: `parser.parse_file` / `writer.write` / `model.InpFile`(无新增运行时依赖)
- 不修改既有 5 个模块
- 总新增 ~600 行(234 sweep.py + ~370 测试/CLI/UI)
