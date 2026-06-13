# cfd--changer 用户手册(总览)

> 本目录是 `inp_tool` 的**用户操作手册**,面向**最终用户** — 用 sweep 工具做 CFD 参数扫描的工程师。
>
> 关注:**怎么用** / **怎么用好**,不涉及内部架构、源码、测试。
>
> 想了解**为什么这样设计**、**怎么实现的**,看 [`../technical/`](../technical/)。

---

## 1. 5 分钟上手路径

| 你的时间 | 读什么 |
|---|---|
| 5 分钟 | [`basics/03-快速开始`](basics/03-quickstart.md) — 跑通第一个批量生成 |
| 30 分钟 | [`sweep/01-扫描参数`](sweep/01-sweeping.md) + [`sweep/02-配置文件`](sweep/02-config-files.md) |
| 1 小时 | 完整读 basics/ + sweep/ ,熟悉所有概念 |
| 1 周 | 加上 interactive/ + reference/ + advanced/ ,处理所有边界情况 |

## 2. 子目录索引

| 子目录 | 主题 | 章节数 | 起点章节 |
|---|---|---|---|
| [`basics/`](basics/README.md) | 入门(介绍 / 安装 / 快速开始) | 3 | [01-introduction](basics/01-introduction.md) |
| [`sweep/`](sweep/README.md) | sweep 入门到精通(含 FAQ) | 7 | [01-sweeping](sweep/01-sweeping.md) |
| [`interactive/`](interactive/README.md) | REPL + Wizard + 桌面 GUI | 4 | [01-repl-quickstart](interactive/01-repl-quickstart.md) |
| [`reference/`](reference/README.md) | 字段参考 + CLI/API 速查 + 术语表 | 3 | [01-mcfd-inp-field-reference](reference/01-mcfd-inp-field-reference.md) |
| [`advanced/`](advanced/README.md) | 打包 + 端到端教程 | 2 | [01-packaging](advanced/01-packaging.md) |

---

## 3. 选读指南

### 3.1 我是工程师,想扫一组参数

→ [`basics/03-快速开始`](basics/03-quickstart.md) 跑通第一个
→ [`sweep/01-扫描参数`](sweep/01-sweeping.md) 看能扫什么字段
→ [`sweep/02-配置文件`](sweep/02-config-files.md) 写 JSON / YAML
→ [`sweep/06-例`](sweep/06-examples.md) 直接抄模板

### 3.2 我想改 alpha/ma 之外的字段

→ [`sweep/04-字段覆盖`](sweep/04-overrides.md)
→ 看 `inp-tool parse tpl.inp -b tsteps -f` 拿模板字段名

### 3.3 我想集成到自己代码(Python)

→ [`sweep/05-多入口 §4`](sweep/05-multiple-uis.md) Python API
→ [`sweep/06-例 4 / 例 5`](sweep/06-examples.md) 端到端模板

### 3.4 老板/同事不爱用命令行

→ [`sweep/05-多入口 §5`](sweep/05-multiple-uis.md) Web GUI
→ 启动 `python run_server.py`,浏览器开 `http://127.0.0.1:8765/`

### 3.5 出错了

→ [`sweep/07-FAQ`](sweep/07-faq.md) 90% 的问题都有
→ 实在不行提 issue: <https://github.com/oneMuggle/cfd--changer/issues>

### 3.6 我想查某个 .inp 字段是什么意思

→ [`reference/01-mcfd-inp-field-reference`](reference/01-mcfd-inp-field-reference.md) 完整字段表(10 块 × 全部字段)
→ §4 节专列 sweep 关注的字段(对应 sweep 轴)

### 3.7 我想用交互式 REPL / wizard(不爱记命令)

→ [`interactive/01-repl-quickstart`](interactive/01-repl-quickstart.md) 5 个最常用 REPL 命令
→ [`interactive/02-repl-tour`](interactive/02-repl-tour.md) REPL 全功能
→ [`interactive/03-wizard-tasks`](interactive/03-wizard-tasks.md) 3 个任务向导(modify-file / sweep / diff)

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
- **新功能加章节** — 选主题所属子目录,编号接子目录内下一个可用号
- **示例代码必须能跑** — 用户复制粘贴就跑不通会很挫败
- **截图 / 录屏** — 当前无(待加);如有 v0.4 之后的 GUI 更新,加 `screenshots/` 子目录
- **英文版** — 当前仅中文;如有需求,起 `docs/user-manual-en/`

## 6. 快速跳转

- **安装:** [`basics/02-安装`](basics/02-installation.md)
- **5 分钟上手:** [`basics/03-快速开始`](basics/03-quickstart.md) 或 [`interactive/01-REPL-快速开始`](interactive/01-repl-quickstart.md)
- **用 REPL / wizard:** [`interactive/02-repl-tour`](interactive/02-repl-tour.md) + [`interactive/03-wizard-tasks`](interactive/03-wizard-tasks.md)
- **看示例:** [`sweep/06-完整示例`](sweep/06-examples.md)
- **查 .inp 字段:** [`reference/01-mcfd-inp-field-reference`](reference/01-mcfd-inp-field-reference.md)
- **用 CLI / API:** [`reference/02-cli-api-reference`](reference/02-cli-api-reference.md)
- **遇到问题:** [`sweep/07-FAQ`](sweep/07-faq.md)
- **想理解内部:** [`../technical/`](../technical/)
