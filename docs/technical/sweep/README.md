# Sweep(批量算例生成模块)

> sweep 是 inp_tool 的**核心模块**,负责按笛卡尔积 / 列表 / 整目录复制 / 方程感知等多种模式批量生成 mcfd.inp 算例。

## 章节

| # | 标题 | 内容简介 | 状态 |
|---|---|---|---|
| [**01-sweep-overview**](01-sweep-overview.md) | **sweep 总览** | 背景 / 目标 / 三入口 / 关键能力 / 风险速览 | 当前主线 |
| [02-sweep-architecture](02-sweep-architecture.md) | sweep 架构 & 数据模型 | 流程图 / 5 个 dataclass / `generate()` 主流程 | 当前主线 |
| [03-sweep-usage](03-sweep-usage.md) | sweep 三入口详细用法 | Python API / CLI / FastAPI 完整示例 | 当前主线 |
| [04-sweep-freestream](04-sweep-freestream.md) | FreestreamPreset 几何分解 | 公式 / 默认参数 / 方向假设 | 当前主线 |
| [05-sweep-friendly-uis](05-sweep-friendly-uis.md) | v0.4.2 友好入口 | YAML / 交互式 CLI / Web GUI | 当前主线 |
| [06-sweep-testing](06-sweep-testing.md) | sweep 测试与质量门 | 测试结构 / 覆盖率 / 端到端清单 | 当前主线 |
| [07-sweep-risks-roadmap](07-sweep-risks-roadmap.md) | sweep 风险登记 & roadmap | 8 项风险 + 后续工作 | 当前主线 |
| [08-sweep-case-study](08-sweep-case-study.md) | sweep 案例研究 | 1D/2D sweep + 物理量校验 + 已知坑 | 当前主线 |
| [09-sweep-flexible](09-sweep-flexible.md) | sweep 灵活化 (v0.7.0) | cases/groups/CSV/分组继承(已归档,供回顾) | 已归档 |
| [**10-sweep-case-dir**](10-sweep-case-dir.md) | **sweep 整算例目录 (v0.8.0)** | source_dir / CopyStrategy / per_dir 模式 | **当前主线** |
| [**11-equation-aware-config**](11-equation-aware-config.md) | **方程感知配置 (v0.9.0/0.9.1)** | 9 eqnset 位置 + 5 湍流 + 3 气体 + 4 preset | **当前主线** |
| [12-equation-sweep-extend](12-equation-sweep-extend.md) | 方程感知扩展 (v0.10.0) | sweep 按 case 切方程/湍流/气体(枚举轴 + per-case 覆盖 + alias) | 当前主线 |
| [**13-pbs-submit-watch**](13-pbs-submit-watch.md) | **PBS 批量提交 + 运行中监控 (v0.14.0)** | cluster/batch/monitor 三模块架构 / 数据契约 / 与 sweep 集成 | **当前主线** |

## 速读路径

- **5 分钟了解 sweep** → [01-sweep-overview](01-sweep-overview.md)
- **要写配置跑批量** → [03-sweep-usage](03-sweep-usage.md)
- **要改 sweep 代码** → [02-sweep-architecture](02-sweep-architecture.md) + 源码 `inp_tool/inp_tool/sweep.py`
- **遇坑查风险** → [07-sweep-risks-roadmap](07-sweep-risks-roadmap.md)

## 关联目录

- 上级: [`../README.md`](../README.md) — 技术手册总览
- 同级: [`../architecture/`](../architecture/) — 底层架构(本目录依赖)
- 上游用户: [`../../user-manual/sweep/`](../../user-manual/sweep/) — 用户视角的 sweep 用法
