# 03 — 任务向导

> **面向:** 想用 wizard 完成任务而**不是手动记命令**的用户

---

## 概述

`wizard` 提供 3 个任务导向的向导。每个向导是**完成具体工作的工具**,带步骤提示和选择菜单,无需记命令。

无参 `wizard` 显示菜单,有参 `wizard <子命令>` 直接进对应向导。

## 1. `wizard modify-file`(修改单个 .inp 文件)

**用途:** 加载一个 .inp,改它的来流参数,保存到磁盘。

**5 步:**
1. 选择输入文件(可用当前已加载的)
2. 选择要修改的字段(Ma / α / β / T / p)
3. 输入新值
4. 预览变更
5. 选择输出路径(覆盖 / 同目录加 `_modified` 后缀 / 自定义)

### 完整示例

```
inp> wizard modify-file
═══════════════════════════════════════════════════════════
  向导:修改单个 .inp 文件
═══════════════════════════════════════════════════════════
用途:打开一个 .inp,改它的来流参数(Ma/α/β/T/p),保存到磁盘。

──── 步骤 1/5: select file ────
加载一个 .inp 文件,作为修改目标。
  当前已加载: examples/mcfd_v2_modified.inp
  使用当前已加载文件? [Y/n]: y

──── 步骤 2/5: select fields ────
  可选项:1 2 3 4 5 all done Q
  (1=Ma 2=alpha 3=beta 4=T 5=p)
  字段: 1 2
  (选 Ma + alpha)

──── 步骤 3/5: enter values ────
  Ma 新值: 0.8
  alpha 新值: 5

──── 步骤 4/5: preview ────
  预览变更:
    Ma → 0.8
    alpha → 5.0
  确认继续? [Y/n]: y

──── 步骤 5/5: output ────
  输出: examples/mcfd_v2_modified_modified.inp

──── 执行 ────
  → 加载 examples/mcfd_v2_modified.inp
  → 应用 2 个字段修改
  → 写入 examples/mcfd_v2_modified_modified.inp
  (modify-file 真实写入实现见后续 PR。本次为占位骨架。)

✓ 向导完成。
```

## 2. `wizard sweep`(批量生成算例)

**用途:** 从 1 个模板出发,扫一组参数,生成 N 个 .inp 文件。

**8 步(v0.8.0 起 + 源目录提示):**
1. 模板 .inp 路径
2. 选择 sweep 模式:**笛卡尔** / **显式列表** / **分组继承** / **CSV 文件**
3. 填参(根据所选模式)
4. 命名模板(`{alpha}` `{beta}` `{mach}` `{T}` `{p}` `{group}` 占位符)
5. 输出目录 + manifest 选项
6. 预览
7. 执行 → 调用 PR #1 的 `sweep.generate()`

### 4 种模式选型

| 模式 | 何时用 | YAML 字段 |
|------|--------|-----------|
| **笛卡尔** | 轴正交,各扫 N 个值 | `sweeps: {alpha: [0,5,10], mach: [0.6,0.8]}` |
| **显式列表** | 不规则 / case 数量少 | `cases: [{...}, {...}]` |
| **分组继承** | 几组共参,组内 case 列表 | `groups: [{name, common, cases}]` |
| **CSV** | Excel 维护 | `cases.csv`(第一行表头) |

### 完整示例(显式列表 — 用户原话场景)

**4 个 case:流场 1 攻角 10/20,各攻角下不同侧滑**

```
inp> wizard sweep
═══════════════════════════════════════════════════════════
  向导:批量生成算例
═══════════════════════════════════════════════════════════
适用:从 1 个模板出发,扫一组参数,生成 N 个 .inp。

──── 步骤 1/7: template ────
模板 .inp 路径: examples/mcfd_v2_modified.inp

──── 步骤 2/7: mode ────
选择 sweep 模式:
  [1] 笛卡尔积 sweeps: {axis: [v1, v2]}
  [2] 显式列表 cases: [{...}, ...]
  [3] 分组继承 groups: [{name, common, cases}, ...]
  [4] CSV 文件 cases.csv
  [Q] 取消
> 2

──── 步骤 3/7: params ────
  显式列表:每行一个 case,如 {alpha: 10, beta: 5}
  cases(YAML 列表):
- {alpha: 10, beta: 5,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 10, beta: 8,  mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 10, mach: 0.6, T: 288.15, p: 101325}
- {alpha: 20, beta: 15, mach: 0.6, T: 288.15, p: 101325}

──── 步骤 4/7: naming ────
  命名模板(可用 {alpha} {beta} {mach} {T} {p} {group}):
  [case_{alpha}]: case_a{alpha:02.0f}_b{beta:02.0f}.inp

──── 步骤 5/7: output ────
  输出目录 [./sweep_cases]: /tmp/my_sweep
  生成 manifest.json? [Y/n]: n

──── 步骤 6/7: preview ────
  预览(简化):
    模板: examples/mcfd_v2_modified.inp
    模式: 2
    输出: /tmp/my_sweep
    命名: case_a{alpha:02.0f}_b{beta:02.0f}.inp
  确认生成? [Y/n]: y

──── 步骤 7/7: execute ────
  生成 4 个算例 → /tmp/my_sweep

✓ 向导完成。
```

输出:
```
case_a10_b05.inp
case_a10_b08.inp
case_a20_b10.inp
case_a20_b15.inp
```

### 整算例目录模式(v0.8.0+)

如果基础算例是**完整目录**(含网格/配置/物性/脚本,如 `reference/suanli/`),普通 sweep 只会生成孤立的 mcfd.inp,跑不起来。v0.8.0 起,设 `source_dir` 后,wizard 会**把基础算例整目录复制到每个子算例**,只覆盖 mcfd.inp。

CLI 等价命令(同样效果):
```bash
inp-tool sweep config.yaml \
  --source-dir /path/to/reference/suanli \
  --copy-strategy hardlink
```

输出示例(`/tmp/my_sweep/`):
```
case_a10_b05/   ← 完整算例
  ├── mcfd.inp           (修改后)
  ├── cellsin.bin        (硬链接,0 空间)
  ├── nodesin.bin
  ├── mcfd.bc / mcfd.grp
  ├── npfopts.inp / pltopts.inp
  ├── C.dat / O2.dat / ...
  └── run_cfdpp.pbs
case_a10_b08/
  ...
manifest.json   ← 含 layout/source_dir/copy_strategy/files
```

**复制策略选 `hardlink`(默认)** 最经济:100 个 case × 544MB = 0 额外磁盘。改 `mcfd.inp` 时只影响自身,网格是只读共享。

### CSV 模式示例

```
inp> wizard sweep
[走完 1, 2 选 4, 3 选 CSV]
──── 步骤 3/7: params ────
  CSV 文件路径: /tmp/cases.csv
[cases.csv 内容:]
  alpha,beta
  0,0
  5,0
  10,0
```

## 3. `wizard diff`(比较两个 .inp 文件)

**用途:** 看两个 .inp 文件的字段差异(基准 vs 派生)。

**3 步:**
1. 基准 .inp 路径
2. 对比 .inp 路径
3. 输出格式(side-by-side / unified diff / 仅显示有差异)

### 完整示例

```
inp> wizard diff
═══════════════════════════════════════════════════════════
  向导:比较两个 .inp 文件
═══════════════════════════════════════════════════════════
用途:看两个 .inp 文件的字段差异(基准 vs 派生)。

──── 步骤 1/3: baseline ────
基准 .inp 路径: baseline.inp

──── 步骤 2/3: other ────
对比 .inp 路径: modified.inp

──── 步骤 3/3: format ────
选择输出格式:
  [1] side-by-side(逐字段并排)
  [2] unified diff
  [3] 仅显示有差异的字段
  [Q] 取消
> 1

──── 执行 ────
=== baseline.inp → modified.inp ===
差异条数: 3
  guiopts.aero_alpha: 0.0 → 5.0
  guiopts.aero_ma: 0.6 → 0.8
  physics.refvel: 204.7 → 272.3

✓ 向导完成。
```

## 取消

任何步骤按 `Ctrl+C` 或输入 `Q`(菜单)即取消,向导打印 "已取消。" 并退出。

## 下一步

- [01-quickstart.md](01-quickstart.md) — 5 分钟快速跑通
- [02-repl-tour.md](02-repl-tour.md) — REPL 全功能
