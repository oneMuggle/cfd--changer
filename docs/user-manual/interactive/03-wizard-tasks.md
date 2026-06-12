# 03 — 任务向导

> **面向:** 想用 wizard 完成任务而**不是手动记命令**的用户

---

> **速查定位:** 3 个 wizard(modify-file / sweep / diff)。REPL 基础见 [02-repl-tour](02-repl-tour.md),5 命令快速开始见 [01-repl-quickstart](01-repl-quickstart.md)。

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

**7 步(v0.8.4 + v0.9.0):**
1. 源算例目录(必填,基础算例根)
2. 输出目录 + manifest 选项
3. 选择 sweep 模式:**笛卡尔** / **显式列表** / **分组继承** / **CSV 文件**
4. 填参(根据所选模式)
5. 命名模板(`{alpha}` `{beta}` `{mach}` `{T}` `{p}` `{group}` 占位符)
6. **v0.9.0 新增 pbs 步骤**:是否生成 pbs 脚本 + 任务名模板
7. 预览 + 执行

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
适用:从 1 个完整基础算例目录出发,扫一组参数,生成 N 个完整算例子目录。

──── 步骤 1/7: source_dir ────
  基础算例目录(必填,完整算例根目录,例:/home/.../reference/suanli):
  reference/suanli
  ✓ pbs 模板: reference/suanli/run_cfdpp.pbs
  [validate] warning: MISSING_BLOCK:chemkin ...

──── 步骤 2/7: output ────
  输出目录 [./sweep_cases]: /tmp/my_sweep
  生成 manifest.json? [Y/n]: n

──── 步骤 3/7: mode ────
选择 sweep 模式:
  [1] 笛卡尔积 sweeps: {axis: [v1, v2]}
  ...

──── 步骤 4/7: params ────
  ...

──── 步骤 5/7: naming ────
  命名模板(可用 {alpha} {beta} {mach} ...):
  case_a{alpha:02.0f}_b{beta:02.0f}

──── 步骤 5a/7: pbs (v0.9.0 新增) ────
  是否生成 pbs 脚本? [Y/n]: y
  pbs 任务名建议(可改): Marspath_a10_b05
  任务名模板(空=接受建议,例 Mars-{alpha}-{beta}):

──── 步骤 6/7: preview ────
  预览(简化):
    源目录: reference/suanli (策略: hardlink)
    模板: reference/suanli/mcfd.inp
    模式: 1
    输出: /tmp/my_sweep
    命名: case_a{alpha:02.0f}_b{beta:02.0f}
    pbs 任务名建议: Marspath_a10_b05
  确认生成? [Y/n]: y
  目标子目录已存在时覆盖? [y/N]: n

──── 步骤 7/7: preview ────
  生成 4 个算例 (整目录) → /tmp/my_sweep

✓ 向导完成。
```

输出:
```
case_a10_b05/  ← 完整算例
  ├── mcfd.inp           (修改后)
  ├── cellsin.bin        (硬链接,0 空间)
  └── run_cfdpp.pbs      (任务名: Marspath_a10_b05)
case_a10_b08/  ...
case_a20_b10/  ...
case_a20_b15/  ...
```

### 整算例目录模式(v0.8.0+)

如果基础算例是**完整目录**(含网格/配置/物性/脚本,如 `reference/suanli/`),普通 sweep 只会生成孤立的 mcfd.inp,跑不起来。v0.8.0 起,设 `source_dir` 后,wizard 会**把基础算例整目录复制到每个子算例**,只覆盖 mcfd.inp。

CLI 等价命令(同样效果):
```bash
inp-tool sweep config.yaml \
  --source-dir /path/to/reference/suanli \
  --copy-strategy hardlink \
  --pbs-naming 'Mars-{alpha}-{mach}'
```

### pbs 脚本可选生成(v0.9.0 新增)

v0.8.x 整目录模式会复制 `run_*.pbs` 到每个子算例,但任务名是源模板里硬编码的(如 `Marspathfinder-Ini`),批量提交时无法区分 case。v0.9.0 起,wizard / CLI 可选生成 pbs,按 sweep 参数自动重新填 `#PBS -N`。

wizard 新增 `step 5a/7: pbs`(默认 yes),CLI 加 `--pbs/--no-pbs` + `--pbs-naming` 模板 flag。

任务名建议默认按"变动多值轴"生成短名:
- `Marspathfinder-Ini` (8 字符) → `Marspath`(base)
- `sweeps: {alpha: [0, 4, 8]}` → `Marspath_a00`, `Marspath_a04`, `Marspath_a08`

用户可输入模板覆盖:
- `Mars-{alpha}-{mach}` → `Mars-0-0.6`, `Mars-4-0.6`, `Mars-4-0.8`(每个 case 不同)
- `MyRun`(具体名) → 所有 case 共享 `MyRun`

如果源目录缺 `run_*.pbs` 模板,wizard 自动关闭 pbs 生成并打印 warning。

输出示例(`/tmp/my_sweep/`):
```
case_a10_b05/   ← 完整算例
  ├── mcfd.inp           (修改后)
  ├── cellsin.bin        (硬链接,0 空间)
  ├── nodesin.bin
  ├── mcfd.bc / mcfd.grp
  ├── npfopts.inp / pltopts.inp
  ├── C.dat / O2.dat / ...
  └── run_cfdpp.pbs      (任务名: #PBS -N Marspath_a10_b05)
case_a10_b08/
  └── run_cfdpp.pbs      (任务名: #PBS -N Marspath_a10_b08)
...
manifest.json   ← 含 layout/source_dir/copy_strategy/files/pbs_enabled/pbs_name
```

**复制策略选 `hardlink`(默认)** 最经济:100 个 case × 544MB = 0 额外磁盘。改 `mcfd.inp` 时只影响自身,网格是只读共享。

### 完整性检查(v0.9.0 新增)

选中 source_dir 后,wizard 自动跑完整性检查(只 warn,不阻断):
- `mcfd.inp` 必须存在
- `tsteps` / `physics` block 建议存在(标准 mcfd 用 `xxx begin/end` 格式)
- `chemkin` / `restart` block 软提示(部分算例类型需要)
- 网格/物性/配置/ pbs 模板缺失软提示

完整性 error 抛 `SweepValidationError`(当前默认不抛,严格模式留给 v0.9.x 后期)。

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

> v0.11.0 wizard sweep 涉及的"step_4b 选 axis + step_4c per-case 覆盖"细节见 [technical/sweep/11](../../technical/sweep/11-equation-aware-config.md) + [technical/sweep/12](../../technical/sweep/12-equation-sweep-extend.md)。

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

- [01-repl-quickstart.md](./01-repl-quickstart.md) — 5 分钟快速跑通
- [02-repl-tour.md](./02-repl-tour.md) — REPL 全功能
