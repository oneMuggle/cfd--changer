# docs/ 结构重整 Phase 2 — 内容去重 + 跨维度导航

**Status:** ✅ 已完成 (PR #21, commits a92b2f4/6660078, branch docs/restruct-phase2)
**Date:** 2026-06-12
**Phase:** 2 of 2(Phase 1: 子目录拆分 + 重设编号,commit 037308d/74fd817/e11f03d/d706173/07079ff,PR #20 已 merge)
**前置:** docs/ 现状(Phase 1 后)— 35 章节,13 个 README

---

## 1. 背景

Phase 1 把 `docs/technical/` 和 `docs/user-manual/` 从"按编号扁平"重整为"按职能子目录 + 子目录内 01-N 连续",35 章节已 git mv 到 5+5 个子目录。

但**章节内容本身**仍有重复:

- 同一概念在不同章节复述(用户视角 vs 开发者视角,但内容 50-80% 重复)
- 8 个重复候选已识别(spec §3.1)
- 1 个**误归档**: `technical/ux/01-ux-friendly-cli.md` 实际是 2026-06-09 写的 plan(PR #2 实施计划),不是 UX 章节
- **缺跨维度导航**: 现有 docs/README + 子目录 README 是"按目录/子目录"组织,**没有**"按主题/受众/任务"3 维度导航

Phase 2 解决内容去重 + 加跨维度导航。

---

## 2. 目标

1. **去重 8 个重复点**(按"中度互引 + 高度合并"原则)
2. **修复 1 个误归档**(`technical/ux/01-ux-friendly-cli.md` → `docs/superpowers/specs/`)
3. **新增 `docs/INDEX.md` 跨维度导航**(按主题 / 按受众 / 按任务 3 维度)

---

## 3. 设计

### 3.1 8 个重复点处理

#### R1: sweep 用法(中度重复)

| 章节 | 视角 | 处理 |
|---|---|---|
| `user-manual/sweep/01-sweeping.md` | 用户视角(扫哪些字段) | 顶部加 1 行链接到 technical 章 |
| `user-manual/sweep/05-multiple-uis.md` | 用户视角(4 种入口) | 顶部加链接到 technical 章(开发者详讲) |
| `technical/sweep/03-sweep-usage.md` | 开发者视角(Python/CLI/FastAPI 完整 API) | 顶部加链接到 user 章(用户简版) |

具体编辑:
- 3 个文件顶部 "## 1. ..." 之前加一段 "**视角定位:** ... 详细 API 见 [technical/sweep/03](../technical/sweep/03-sweep-usage.md)" 之类的链接段
- 标题行不动

#### R2: wizard/REPL(中度重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `user-manual/interactive/01-repl-quickstart.md` | 5 个最常用 REPL 命令 | 顶部加 "**全功能见 [02-repl-tour](02-repl-tour.md)**" |
| `user-manual/interactive/02-repl-tour.md` | REPL 全功能 | 顶部加 "**5 命令速查见 [01-repl-quickstart](01-repl-quickstart.md)**" |
| `user-manual/interactive/03-wizard-tasks.md` | 3 个 wizard | 顶部加 "**REPL 基础见 [02-repl-tour](02-repl-tour.md)**" |
| `technical/ux/01-ux-friendly-cli.md` | (实际是 plan) | 见 §3.2 归档修复 |

#### R3: sweep 配置字段(中度重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `user-manual/sweep/02-config-files.md` | JSON/YAML 配置(用户视角) | 末尾"## 字段全表"或"## 关联"段加链接到 `reference/01-mcfd-inp-field-reference.md` |
| `user-manual/reference/01-mcfd-inp-field-reference.md` | 10 块 × 全部字段(参考手册) | 顶部加 "**配置文件写法见 [sweep/02-config-files](../sweep/02-config-files.md)**" |

#### R4: sweep 案例(低度重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `technical/sweep/08-sweep-case-study.md` | 案例研究(1D/2D 物理量校验) | 顶部加 "**完整可跑示例见 [user-manual/sweep/06-examples](../../user-manual/sweep/06-examples.md)**" |
| `user-manual/sweep/06-examples.md` | 6 个端到端真实场景 | 顶部加 "**物理量校验见 [technical/sweep/08-sweep-case-study](../../technical/sweep/08-sweep-case-study.md)**" |

**处理:互引**(轻量)

#### R5: 友好入口(中度重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `user-manual/sweep/05-multiple-uis.md` | 4 种入口速览(用户视角) | 顶部加 "**YAML/交互式/Web GUI 实现细节见 [technical/sweep/05-friendly-uis](../../technical/sweep/05-sweep-friendly-uis.md)**" |
| `technical/sweep/05-sweep-friendly-uis.md` | 友好入口实现(开发者) | 顶部加 "**用户视角见 [user-manual/sweep/05-multiple-uis](../../user-manual/sweep/05-multiple-uis.md)**" |

**处理:互引**(类似 R1)

#### R6: 整算例目录(中度重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `technical/sweep/10-sweep-case-dir.md` | source_dir/CopyStrategy/per_dir 实现 | 顶部加 "**用户视角的 source_dir 用法见 [user-manual/sweep/02-config-files](../../user-manual/sweep/02-config-files.md) §X**" |
| `user-manual/sweep/02-config-files.md` | JSON 配置含 source_dir 字段 | 加 1 段 "**整算例目录模式(per_dir)见 [technical/sweep/10](../../technical/sweep/10-sweep-case-dir.md)**" |

**处理:互引**

#### R7: 方程感知(同子目录)

| 章节 | 内容 | 处理 |
|---|---|---|
| `technical/sweep/11-equation-aware-config.md` | v0.9.0/0.9.1 方程感知(检测 + 初始化) | 顶部加 "**v0.10.0 sweep 扩展(per-case 覆盖)见 [12-equation-sweep-extend](12-equation-sweep-extend.md)**" |
| `technical/sweep/12-equation-sweep-extend.md` | v0.10.0 sweep 按 case 切方程 | 顶部加 "**v0.9.x 方程感知背景见 [11-equation-aware-config](11-equation-aware-config.md)**" |
| `user-manual/interactive/03-wizard-tasks.md` | v0.11.0 wizard 含方程感知步骤(仅 1 处提及) | 在 wizard sweep 步骤段加链接 "**详见 [technical/sweep/11](../../technical/sweep/11-equation-aware-config.md) + [12](../../technical/sweep/12-equation-sweep-extend.md)**" |

**处理:互引**

#### R8: 打包/分发(中度重复,实际不重复)

| 章节 | 内容 | 处理 |
|---|---|---|
| `technical/release/01-cli-packaging.md` | PyInstaller 配置(开发者) | 顶部加 "**用户使用 standalone 见 [user-manual/advanced/01-packaging](../../user-manual/advanced/01-packaging.md)**" |
| `user-manual/advanced/01-packaging.md` | 用打包版本(用户) | 顶部加 "**打包构建过程见 [technical/release/01-cli-packaging](../../technical/release/01-cli-packaging.md)**" |

**评估:重复度**约 30-50%(开发者讲"怎么打",用户讲"怎么用"),**实际是"互补"关系,不是真正重复**。处理:互引,不合并。

---

### 3.2 误归档修复:`technical/ux/01-ux-friendly-cli.md`

**文件实际内容:** 2026-06-09 写的 plan,标题 "# 计划:i18n + Wizard 任务向导(PR #2)",含背景/目标/涉及文件/实施步骤。这是 v0.7.1 PR #2 的实施计划。

**问题:** Phase 1 改名时没识别它是 plan,直接 `git mv` 到 `technical/ux/01-ux-friendly-cli.md`。

**处理:**
1. `git mv docs/technical/ux/01-ux-friendly-cli.md docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`
2. 文件第 1 段加 `**Status:** ✅ 已实施(PR #2 后的 v0.7.1+,实际已合入 main)`
3. `docs/technical/ux/README.md` §1 段改为"UX 章节尚未单独成文;UX 设计的实操内容见 [`user-manual/interactive/`](../../user-manual/interactive/)"

**注:** 不动 plan 文件内的"实施步骤"内容(那些是 v0.7.1 时代的历史,改写违反"不重写历史"原则)。

---

### 3.3 `docs/INDEX.md` 跨维度导航(新文件)

三维度,**每个维度是一张大表**:

```markdown
# docs/ 跨维度导航(Phase 2 新增)

> 不知道从哪读起?按下面三种方式之一跳。
>
> 已有 docs/README + 子目录 README 是"按目录"组织;本 INDEX 是"按主题/受众/任务"组织。

---

## 1. 按主题(我要解决 X 问题)

| 任务 | 主章节 | 补充 |
|---|---|---|
| 扫一组参数 | [user-manual/sweep/01-sweeping](../user-manual/sweep/01-sweeping.md) | [tech sweep-usage](../technical/sweep/03-sweep-usage.md) 完整 API |
| 改 alpha/ma 之外的字段 | [user-manual/sweep/04-overrides](../user-manual/sweep/04-overrides.md) | — |
| 用 JSON/YAML 配置 sweep | [user-manual/sweep/02-config-files](../user-manual/sweep/02-config-files.md) | [reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) 字段全表 |
| 改命名规则 | [user-manual/sweep/03-naming](../user-manual/sweep/03-naming.md) | — |
| 用 wizard 任务向导 | [user-manual/interactive/03-wizard-tasks](../user-manual/interactive/03-wizard-tasks.md) | [01 quickstart](../user-manual/interactive/01-repl-quickstart.md) + [02 tour](../user-manual/interactive/02-repl-tour.md) |
| 查某个 .inp 字段 | [user-manual/reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) | — |
| 用打包版本(standalone) | [user-manual/advanced/01-packaging](../user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) 打包过程 |
| 端到端教程 | [user-manual/advanced/02-software-tutorial](../user-manual/advanced/02-software-tutorial.md) | — |

## 2. 按受众(我是 Y 类用户)

| 受众 | 起点 | 关键章节 |
|---|---|---|
| **新用户(CFD 工程师)** | [user-manual/README](../user-manual/README.md) | [basics/01-03](../user-manual/basics/) + [sweep/01-07](../user-manual/sweep/) |
| **偶尔用 / 不爱记命令** | [user-manual/interactive/README](../user-manual/interactive/README.md) | [01 quickstart](../user-manual/interactive/01-repl-quickstart.md) + [03 wizard](../user-manual/interactive/03-wizard-tasks.md) |
| **数据科学 / 集成到自己代码** | [user-manual/sweep/05-multiple-uis §Python API](../user-manual/sweep/05-multiple-uis.md) | [tech sweep/03-sweep-usage §1 Python API](../technical/sweep/03-sweep-usage.md) |
| **运维/分发** | [user-manual/advanced/01-packaging](../user-manual/advanced/01-packaging.md) | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) |
| **开发者(读代码/扩展)** | [technical/README](../technical/README.md) | [architecture/01](../technical/architecture/01-architecture-overview.md) → [sweep/02](../technical/sweep/02-sweep-architecture.md) |
| **贡献者** | [technical/sweep/07-risks-roadmap §4 贡献指南](../technical/sweep/07-sweep-risks-roadmap.md) | [tech sweep/06-testing](../technical/sweep/06-sweep-testing.md) 测试结构 |

## 3. 按任务(我要做 Y 任务)

| 任务 | 关键章节 |
|---|---|
| 跑通第一个 sweep | [basics/03-quickstart](../user-manual/basics/03-quickstart.md) |
| 扫 alpha-mach | [sweep/01-sweeping](../user-manual/sweep/01-sweeping.md) + [06-examples 例 1](../user-manual/sweep/06-examples.md) |
| 整算例目录复制 | [tech sweep/10-case-dir](../technical/sweep/10-sweep-case-dir.md) |
| 方程感知(per-case 切) | [tech sweep/11-equation-aware](../technical/sweep/11-equation-aware-config.md) + [12-equation-extend](../technical/sweep/12-equation-sweep-extend.md) |
| 查 .inp 字段 | [reference/01-mcfd-inp-field-reference](../user-manual/reference/01-mcfd-inp-field-reference.md) |
| 改 REPL 启动面板 | [tech specs/2026-06-09-ux-friendly-cli (plan, 已实施 v0.7.1)](../superpowers/specs/2026-06-09-ux-friendly-cli-design.md) |
| 写 wizard | [interactive/03-wizard-tasks](../user-manual/interactive/03-wizard-tasks.md) |
| 查 sweep 出错原因 | [sweep/07-faq](../user-manual/sweep/07-faq.md) |
| 打包 standalone | [tech release/01-cli-packaging](../technical/release/01-cli-packaging.md) + [user advanced/01](../user-manual/advanced/01-packaging.md) |
| 跑 CI / 修 CI | [tech release/02-ci-cd](../technical/release/02-ci-cd.md) |
| 提 issue | GitHub issues |

---

## 4. 维护

- INDEX.md 由人在 Phase 2 后手工维护(不自动生成)
- 新增章节时,在 §1/§2/§3 适当位置加一行
- 章节归档时,从 INDEX 移除
```

**注意:** §3 中 ux/01-ux-friendly-cli.md 链接在归档后会失效(因为该文件会移到 specs/),写时按"归档后"路径写。实际写入计划时:
- 实际写入链接:`../superpowers/specs/2026-06-09-ux-friendly-cli-design.md`
- 描述: "(plan, 已实施 v0.7.1)"

---

## 4. Commit 策略(2 commit)

### Commit 1:`docs(cleanup): Phase 2 去重 — 8 处互引 + ux plan 归档`

范围:
- 13 个章节文件顶部加 1-2 行互引(详见 §3.1)
- `git mv docs/technical/ux/01-ux-friendly-cli.md docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md`
- 在该文件第 1 段加 `**Status:** ✅ 已实施(PR #2 后的 v0.7.1+)`
- `docs/technical/ux/README.md` §1 段改"UX 章节尚未单独成文"
- `docs/superpowers/specs/README.md` 加一行 status 表条目

### Commit 2:`docs(cleanup): Phase 2 加 docs/INDEX.md 跨维度导航`

范围:
- 新建 `docs/INDEX.md`(内容见 §3.3)
- 在 `docs/README.md` §常用入口 加 "→ [INDEX.md](INDEX.md) — 跨维度导航" 链接
- 验证所有 INDEX.md 链接指向真实文件

---

## 5. 验证清单

每个 commit 之后跑:
- [ ] Python 跨文件链接检查:0 broken
- [ ] 旧路径残留:0
- [ ] git grep "docs/technical/ux/01-ux-friendly-cli.md" 无引用(归档后)
- [ ] git grep "docs/superpowers/specs/2026-06-09-ux-friendly-cli-design.md" 引用 ≥ 1(INDEX + 新 spec README)
- [ ] `docs/superpowers/specs/README.md` status 表新增条目
- [ ] 8 个重复点互引 19 处编辑(commit 1 范围,16 个 unique 文件)全到位
- [ ] `docs/INDEX.md` §1/§2/§3 三维度表格存在,链接全可点
- [ ] `docs/README.md` §常用入口 包含 INDEX 链接
- [ ] 章节正文**未改**(本 Phase 只加互引 + 归档,不改章节内容)
- [ ] 3 平台 CI pass

---

## 6. 排除项(明确不做)

- ❌ 不动章节**正文内容**(本 Phase 只加互引,内容修订属其他 PR)
- ❌ 不删任何章节(归档 plan 不算删章节)
- ❌ 不改章节文件名 / 编号
- ❌ 不改 v0.7.1 计划 plan 内的"实施步骤"细节
- ❌ 不重新生成 INDEX.md(自动生成)— 本 Phase 是手工写
- ❌ 不动 cfd-gui/、plans/、CLAUDE.md、inp_tool/ 下的 README
- ❌ 不动 docs/superpowers/specs/2026-06-{02,08,10,11}-*.md(5 个已完成 spec,保持原状)
- ❌ 不动 docs/superpowers/specs/README.md 中已完成 spec 的 status 描述(只加 1 个新条目)
- ❌ 不为 v0.11.0 wizard-equation-axes 补新章节(留作单独 PR,本 spec 范围)
- ❌ 不合并任何章节(R1-R8 全部互引,无合并)
