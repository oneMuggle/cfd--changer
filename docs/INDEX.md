# docs/ 跨维度导航(Phase 2 新增)

> 不知道从哪读起?按下面三种方式之一跳。
>
> 已有 docs/README + 子目录 README 是"按目录"组织;本 INDEX 是"按主题/受众/任务"组织。

---

## 1. 按主题(我要解决 X 问题)

| 任务 | 主章节 | 补充 |
|---|---|---|
| 扫一组参数 | [user-manual/sweep/01-sweeping](user-manual/sweep/01-sweeping.md) | [tech sweep-usage](technical/sweep/03-sweep-usage.md) 完整 API |
| 改 alpha/ma 之外的字段 | [user-manual/sweep/04-overrides](user-manual/sweep/04-overrides.md) | — |
| 用 JSON/YAML 配置 sweep | [user-manual/sweep/02-config-files](user-manual/sweep/02-config-files.md) | [reference/01-mcfd-inp-field-reference](user-manual/reference/01-mcfd-inp-field-reference.md) 字段全表 |
| 改命名规则 | [user-manual/sweep/03-naming](user-manual/sweep/03-naming.md) | — |
| 用 wizard 任务向导 | [user-manual/interactive/03-wizard-tasks](user-manual/interactive/03-wizard-tasks.md) | [01 quickstart](user-manual/interactive/01-repl-quickstart.md) + [02 tour](user-manual/interactive/02-repl-tour.md) |
| 查某个 .inp 字段 | [user-manual/reference/01-mcfd-inp-field-reference](user-manual/reference/01-mcfd-inp-field-reference.md) | — |
| 用打包版本(standalone) | [user-manual/advanced/01-packaging](user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](technical/release/01-cli-packaging.md) 打包过程 |
| 端到端教程 | [user-manual/advanced/02-software-tutorial](user-manual/advanced/02-software-tutorial.md) | — |

## 2. 按受众(我是 Y 类用户)

| 受众 | 起点 | 关键章节 |
|---|---|---|
| **新用户(CFD 工程师)** | [user-manual/README](user-manual/README.md) | [basics/01-03](user-manual/basics/) + [sweep/01-07](user-manual/sweep/) |
| **偶尔用 / 不爱记命令** | [user-manual/interactive/README](user-manual/interactive/README.md) | [01 quickstart](user-manual/interactive/01-repl-quickstart.md) + [03 wizard](user-manual/interactive/03-wizard-tasks.md) |
| **数据科学 / 集成到自己代码** | [user-manual/sweep/05-multiple-uis §Python API](user-manual/sweep/05-multiple-uis.md) | [tech sweep/03-sweep-usage §1 Python API](technical/sweep/03-sweep-usage.md) |
| **运维/分发** | [user-manual/advanced/01-packaging](user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](technical/release/01-cli-packaging.md) |
| **开发者(读代码/扩展)** | [technical/README](technical/README.md) | [architecture/01](technical/architecture/01-architecture-overview.md) → [sweep/02](technical/sweep/02-sweep-architecture.md) |
| **贡献者** | [technical/sweep/07-risks-roadmap §4 贡献指南](technical/sweep/07-sweep-risks-roadmap.md) | [tech sweep/06-testing](technical/sweep/06-sweep-testing.md) 测试结构 |

## 3. 按任务(我要做 Y 任务)

| 任务 | 关键章节 |
|---|---|
| 跑通第一个 sweep | [basics/03-quickstart](user-manual/basics/03-quickstart.md) |
| 扫 alpha-mach | [sweep/01-sweeping](user-manual/sweep/01-sweeping.md) + [06-examples 例 1](user-manual/sweep/06-examples.md) |
| 整算例目录复制 | [tech sweep/10-case-dir](technical/sweep/10-sweep-case-dir.md) |
| 方程感知(per-case 切) | [tech sweep/11-equation-aware](technical/sweep/11-equation-aware-config.md) + [12-equation-extend](technical/sweep/12-equation-sweep-extend.md) |
| 查 .inp 字段 | [reference/01-mcfd-inp-field-reference](user-manual/reference/01-mcfd-inp-field-reference.md) |
| 改 REPL 启动面板 | [tech specs/2026-06-09-ux-friendly-cli (plan, 已实施 v0.7.1)](superpowers/specs/2026-06-09-ux-friendly-cli-design.md) |
| 写 wizard | [interactive/03-wizard-tasks](user-manual/interactive/03-wizard-tasks.md) |
| 查 sweep 出错原因 | [sweep/07-faq](user-manual/sweep/07-faq.md) |
| 打包 standalone | [tech release/01-cli-packaging](technical/release/01-cli-packaging.md) + [user advanced/01](user-manual/advanced/01-packaging.md) |
| 跑 CI / 修 CI | [tech release/02-ci-cd](technical/release/02-ci-cd.md) |
| 提 issue | GitHub issues |

---

## 4. 维护

- INDEX.md 由人在 Phase 2 后手工维护(不自动生成)
- 新增章节时,在 §1/§2/§3 适当位置加一行
- 章节归档时,从 INDEX 移除
