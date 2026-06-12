# cfd--changer 技术手册(总览)

> **审计:** 2026-06-12 · 章节与 v0.11.0 同步 · 全部示例通过 · 全部链接有效
> 本目录是项目各功能模块的**架构/API/实现细节**文档,面向开发者(读代码、改代码、写扩展)。

---

## 1. 文档组织

- **总览(本文件)** — 索引 + 选读指南
- **章节文件** — 每个独立模块/主题一个文件,聚焦单一话题(50-200 行)
- **命名:** `XX-topic-name.md`,`XX` 是两位数编号
  - `03-` 起的 sweep 模块是当前主线
  - 后续模块(如有)接 `20-` 继续编号
- **cfd-gui 调研材料**([`../cfd-gui/`](../cfd-gui/))独立成目录,不在本目录收录

---

## 2. 章节目录

| # | 标题 | 内容简介 | 状态 |
|---|---|---|---|
| [**03-sweep-overview**](03-sweep-overview.md) | **sweep 模块总览** | 背景 / 目标 / 三入口 / 关键能力 / 风险速览 / 子文档索引 | **当前主线** |
| [04-sweep-architecture](sweep/04-sweep-architecture.md) | sweep 架构 & 数据模型 | 流程图 / 5 个 dataclass / `generate()` 主流程 / overrides / 命名 / manifest / 性能 | 当前主线 |
| [05-sweep-usage](sweep/05-sweep-usage.md) | sweep 三入口详细用法 | Python API / CLI / FastAPI 完整示例 + 配置 schema + 错误处理 | 当前主线 |
| [06-sweep-freestream](sweep/06-sweep-freestream.md) | FreestreamPreset 几何分解 | 公式 / 默认参数 / 字段映射 / 方向假设 / 数值稳定性 | 当前主线 |
| [07-sweep-friendly-uis](sweep/07-sweep-friendly-uis.md) | v0.4.2 友好入口 | YAML / 交互式 CLI / Web GUI / Shell 补全 | 当前主线 |
| [08-sweep-testing](sweep/08-sweep-testing.md) | sweep 测试与质量门 | 测试结构 / 覆盖率 / 关键测试设计 / 端到端验证清单 | 当前主线 |
| [09-sweep-risks-roadmap](sweep/09-sweep-risks-roadmap.md) | sweep 风险登记 & roadmap | 8 项风险 + v0.5/v0.6/v0.7 后续工作 + 贡献指南 | 当前主线 |
| [10-cli-packaging](release/10-cli-packaging.md) | CLI 打包与发布 | PyInstaller onedir / standalone / cross-platform | 当前主线 |
| [11-ci-cd](release/11-ci-cd.md) | CI/CD 配置 | GitHub Actions matrix + environment.yml | 当前主线 |
| [**12-architecture-overview**](architecture/12-architecture-overview.md) | **inp_tool 架构总览** | 包结构 / 模块依赖 / 数据流 / 入口点 / 外部依赖 | **基础** |
| [13-core-modules](architecture/13-core-modules.md) | 核心模块设计 | parser / writer / model / diff 4 模块详细 | 当前主线 |
| [14-sweep-case-study](sweep/14-sweep-case-study.md) | sweep 案例研究 | 基于 2026-06-09 验证的 1D/2D sweep + 物理量校验 + naming 速查 + 已知坑 | 当前主线 |
| [15-ux-friendly-cli](ux/15-ux-friendly-cli.md) | UX 友好 CLI 设计 | REPL 启动面板 / i18n / wizard 任务流 / 交互细节 | 当前主线 |
| [16-sweep-flexible](sweep/16-sweep-flexible.md) | sweep 灵活化 (cases/groups/CSV) | v0.7.0 模式:笛卡尔+显式列表+分组继承+CSV+混合 | 已归档 |
| [**17-sweep-case-dir**](sweep/17-sweep-case-dir.md) | **sweep 整算例目录 (v0.8.0)** | source_dir / CopyStrategy / per_dir 模式 / 排除规则 / smoke 验证 | **当前主线** |
| [**18-equation-aware-config**](sweep/18-equation-aware-config.md) | **方程感知配置 (v0.9.0/0.9.1)** | eqnset_define 9 个位置 + 5 湍流模型 + 3 气体类型 + 4 preset + 7 文件实测固化 | **当前主线** |
| [19-equation-sweep-extend](sweep/19-equation-sweep-extend.md) | 方程感知扩展 (v0.10.0) | sweep 按 case 切方程/湍流/气体(枚举轴 + per-case 覆盖 + alias) | 当前主线 |

---

## 3. 选读指南

### 3.0 我想理解整体架构(无论改什么模块都建议先看)

→ [12-architecture-overview](architecture/12-architecture-overview.md) (10 分钟, 必读)
→ [13-core-modules](architecture/13-core-modules.md) 按需看具体模块

### 3.1 我是新用户,想用 sweep

→ [03-sweep-overview](03-sweep-overview.md) (5 分钟)
→ [05-sweep-usage](sweep/05-sweep-usage.md) 选你要的入口
→ [inp_tool/README.md](../../inp_tool/README.md) 安装与快速开始

### 3.2 我想理解 sweep 内部怎么工作

→ [03-sweep-overview](03-sweep-overview.md) 整体流程
→ [04-sweep-architecture](sweep/04-sweep-architecture.md) 数据模型 + `generate()` 主流程
→ [06-sweep-freestream](sweep/06-sweep-freestream.md) 公式细节
→ [源码 `inp_tool/inp_tool/sweep.py`](../../inp_tool/inp_tool/sweep.py) 234 行

### 3.3 我想贡献代码

→ [09-sweep-risks-roadmap §4](sweep/09-sweep-risks-roadmap.md) 贡献指南
→ [08-sweep-testing](sweep/08-sweep-testing.md) 测试结构 + 端到端验证清单
→ [项目根 `CLAUDE.md`](../../CLAUDE.md) 硬性约束(conda / Win7 / Py3.8)

### 3.4 我遇到了问题

→ [09-sweep-risks-roadmap §5](sweep/09-sweep-risks-roadmap.md) 已知"非 bug"
→ [06-sweep-freestream §4 方向假设](sweep/06-sweep-freestream.md) — 最常见的"值不对"问题
→ GitHub Issues(如有)

### 3.5 我要规划新功能

→ [09-sweep-risks-roadmap §2](sweep/09-sweep-risks-roadmap.md) 已有 roadmap
→ 新功能应先写 `docs/plans/YYYY-MM-DD_<name>.md`,完成后**直接删除**(git log 是历史;设计意图保留在 [`../superpowers/specs/`](../superpowers/specs/))

---

## 4. 文档维护规则

- **不在此保留历史版本** — 过期内容直接删除或覆盖
- **新功能模块** — 同步创建对应章节(从下一个可用编号开始)
- **大章节拆分** — 单一文件超 200 行时按主题拆成多个
- **代码改动** — 同步更新相关章节(架构、API、测试);如改 API,更新[05-sweep-usage](sweep/05-sweep-usage.md)和示例
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

对应文档: sweep 模块 → 03-09(本手册主线);架构总览 → [12-architecture-overview](architecture/12-architecture-overview.md);核心模块(parser/writer/diff/model) → [13-core-modules](architecture/13-core-modules.md);打包/CI → [10-cli-packaging](release/10-cli-packaging.md) / [11-ci-cd](release/11-ci-cd.md)。

---

## 6. 快速跳转

- **代码入口:** [`inp_tool/inp_tool/sweep.py`](../../inp_tool/inp_tool/sweep.py) / [`parser.py`](../../inp_tool/inp_tool/parser.py) / [`writer.py`](../../inp_tool/inp_tool/writer.py) / [`diff.py`](../../inp_tool/inp_tool/diff.py) / [`model.py`](../../inp_tool/inp_tool/model.py)
- **架构总览:** [12-architecture-overview](architecture/12-architecture-overview.md)
- **核心模块:** [13-core-modules](architecture/13-core-modules.md)
- **示例配置:** [`inp_tool/examples/sweep_demo.{json,yaml,py}`](../../inp_tool/examples/)
- **测试:** [`inp_tool/tests/test_sweep*.py`](../../inp_tool/tests/)
- **项目约束:** [`CLAUDE.md`](../../CLAUDE.md)
