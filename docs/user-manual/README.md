# cfd--changer 用户手册(总览)

> 本目录是 `inp_tool` 的**用户操作手册**,面向**最终用户** — 用 sweep 工具做 CFD 参数扫描的工程师。
>
> 关注:**怎么用** / **怎么用好**,不涉及内部架构、源码、测试。
>
> 想了解**为什么这样设计**、**怎么实现的**,看 [../technical/](../technical/)。

---

## 1. 5 分钟上手路径

| 你的时间 | 读什么 |
|---|---|
| 5 分钟 | [03-快速开始](03-quickstart.md) — 跑通第一个批量生成 |
| 30 分钟 | [04-扫描参数](04-sweeping.md) + [05-配置文件](05-config-files.md) |
| 1 小时 | 完整读 01-06,熟悉所有概念 |
| 1 周 | 加上 07-10,处理所有边界情况 |

## 2. 章节目录

| # | 标题 | 内容简介 | 阅读时间 |
|---|---|---|---|
| [01-introduction](01-introduction.md) | 介绍:这是给谁用的 | `inp_tool` 是什么 / 解决什么 / 不解决什么 | 3 分钟 |
| [02-installation](02-installation.md) | 安装 | 系统要求 / conda 环境 / 离线安装 / 验证 | 5 分钟 |
| [03-quickstart](03-quickstart.md) | 快速开始 | 5 分钟跑通第一个批量生成,三种姿势 | 5 分钟 |
| [04-sweeping](04-sweeping.md) | 扫描参数 | 可扫哪些字段 / 笛卡尔积 / 来流参数 / 几何分解 | 15 分钟 |
| [05-config-files](05-config-files.md) | 配置文件 | JSON vs YAML vs CLI 怎么选 / 字段详解 | 15 分钟 |
| [06-naming](06-naming.md) | 命名规则 | `str.format` 模板 / 格式说明符 / 校验规则 | 10 分钟 |
| [07-overrides](07-overrides.md) | 字段覆盖 | 改 alpha/ma 之外的字段(时间步、输出频率等) | 15 分钟 |
| [08-multiple-uis](08-multiple-uis.md) | 多入口使用 | CLI / Python / Web GUI / 交互式 / Shell 补全 怎么选 | 15 分钟 |
| [09-examples](09-examples.md) | 完整示例 | 6 个端到端真实场景 | 20 分钟 |
| [10-faq](10-faq.md) | 常见问题 | 安装/运行/几何分解/路径/性能/Web GUI/调试 | 边用边查 |
| [11-packaging](11-packaging.md) | 打包与分发 | PyInstaller onedir / standalone CLI / cross-platform | 10 分钟 |
| [12-mcfd-inp-field-reference](12-mcfd-inp-field-reference.md) | mcfd.inp 完整字段参考 | 10 块 × 全部字段, sweep 字段映射 | 30 分钟 |
| [13-cli-api-reference](13-cli-api-reference.md) | CLI / FastAPI / Python 速查 | 7 子命令 + 12 端点 + 24 符号 | 10 分钟 |
| [14-software-tutorial](14-software-tutorial.md) | 端到端教程 | 5 个真实工作流 (alpha-Mach / Web GUI / CI / 单文件 / SLURM) | 30 分钟 |
| [15-glossary](15-glossary.md) | 术语表 | A-Z 80+ 词条 | 边用边查 |

## 3. 选读指南

### 3.1 我是工程师,想扫一组参数

→ [03-快速开始](03-quickstart.md) 跑通第一个
→ [04-扫描参数](04-sweeping.md) 看能扫什么字段
→ [05-配置文件](05-config-files.md) 写 JSON / YAML
→ [09-例 1](09-examples.md) 直接抄模板

### 3.2 我想改 alpha/ma 之外的字段

→ [07-字段覆盖](07-overrides.md)
→ 看 `inp-tool parse tpl.inp -b tsteps -f` 拿模板字段名

### 3.3 我想集成到自己代码(Python)

→ [08-多入口 §4](08-multiple-uis.md) Python API
→ [09-例 4 / 例 5](09-examples.md) 端到端模板

### 3.4 老板/同事不爱用命令行

→ [08-多入口 §5](08-multiple-uis.md) Web GUI
→ 启动 `python run_server.py`,浏览器开 `http://127.0.0.1:8765/`

### 3.5 出错了

→ [10-FAQ](10-faq.md) 90% 的问题都有
→ 实在不行提 issue: <https://github.com/oneMuggle/cfd--changer/issues>

### 3.6 我想查某个 .inp 字段是什么意思

→ [12-mcfd-inp-field-reference](12-mcfd-inp-field-reference.md) 完整字段表(10 块 × 全部字段)
→ §4 节专列 sweep 关注的字段(对应 sweep 轴)

## 4. 与其他文档的关系

| 文档 | 视角 | 适合 |
|---|---|---|
| **[本目录 `docs/user-manual/`](.)** | 终端用户(我) | 想用好工具 |
| [`docs/technical/`](../technical/) | 开发者(看代码/扩展) | 想改工具 / 加功能 / 排查内部 bug |
| [`inp_tool/README.md`](../../inp_tool/README.md) | inp_tool 包自述 | 安装 + Python/CLI/Web API 速查 |
| [`CLAUDE.md`](../../CLAUDE.md) | 项目级硬约束(conda/Py3.8/Win7) | 任何修改前必读 |
| `inp_tool/examples/` | 样例 .inp + 配置 | 直接拿 sample 改 |

## 5. 文档维护规则

- **不保留历史版本** — 过期内容直接覆盖
- **新功能加章节** — 从 `11-` 继续编号
- **示例代码必须能跑** — 用户复制粘贴就跑不通会很挫败
- **截图 / 录屏** — 当前无(待加);如有 v0.4 之后的 GUI 更新,加 `screenshots/` 子目录
- **英文版** — 当前仅中文;如有需求,起 `docs/user-manual-en/`

## 6. 快速跳转

- **安装:** [02-安装](02-installation.md)
- **5 分钟上手:** [03-快速开始](03-quickstart.md)
- **看示例:** [09-完整示例](09-examples.md)
- **查 .inp 字段:** [12-mcfd-inp-field-reference](12-mcfd-inp-field-reference.md)
- **用 CLI / API:** [13-cli-api-reference](13-cli-api-reference.md)
- **遇到问题:** [10-FAQ](10-faq.md)
- **想理解内部:** [../technical/](../technical/)
