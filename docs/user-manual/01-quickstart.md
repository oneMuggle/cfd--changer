# 01 — 快速开始

> **5 分钟跑通 inp-tool**

---

## 第 1 步:启动 REPL

```bash
$ inp-tool shell
inp-tool v0.7.1 交互式外壳
════════════════════════════════════════════
  欢迎使用 inp-tool!输入 `tutorial` 走完 5 步快速上手,`wizard` 走任务向导。
  快速开始(5 个最常用命令):
    load <路径>          加载 .inp 文件
    info                 查看当前文件结构
    aero Ma=0.8 alpha=5  设置来流参数
    save                 保存到原文件
    sweep ...            批量生成算例
inp>
```

## 第 2 步:加载一个 .inp 文件

```bash
inp> load examples/mcfd_v2_modified.inp
✓ 已加载:mcfd_v2_modified  (examples/mcfd_v2_modified.inp)
inp[mcfd_v2_modified]>
```

提示符变成 `inp[mcfd_v2_modified]>` 表示当前正在编辑这个文件。

## 第 3 步:查看文件结构

```bash
inp[mcfd_v2_modified]> info
文件: examples/mcfd_v2_modified.inp
头部注释行: 0
顶层语句: 0

块列表:
  [ 0] guiopts         L   1- 10    9 stmts    9 unique keys
  [ 1] physics         L  11- 20    7 stmts    7 unique keys
  ...
```

## 第 4 步:改来流参数

```bash
inp[mcfd_v2_modified]> aero Ma=0.8 alpha=5
aero: Ma 0.6→0.8, alpha 0→5
Ma=0.8  α=5°  β=0°  T=288K  p=1.013e+05Pa
U=271.1  V=0  W=23.72  |V|=272.2  refvel=272.2
```

U/V/W 自动重算。也可只改一个:

```bash
inp[mcfd_v2_modified]> aero alpha=10
aero: alpha 5→10
Ma=0.8  α=10°  β=0°  T=288K  p=1.013e+05Pa
U=268.0  V=0  W=47.16  |V|=272.2  refvel=272.2
```

## 第 5 步:保存

```bash
inp[mcfd_v2_modified]> save
✓ 已保存:mcfd_v2_modified -> examples/mcfd_v2_modified.inp
```

## 第 6 步:批量生成(走任务向导)

```bash
inp[mcfd_v2_modified]> wizard sweep
═══ inp-tool 向导菜单 ═══
请选择向导(输入编号):
  [1] modify-file  修改单个 .inp 的来流参数
  [2] sweep        批量生成算例(交互式)
  [3] diff         比较两个 .inp 文件的差异
  [Q] 退出
> 2
```

详细见 [03-tasks.md](03-tasks.md)。

## 不进入 REPL,直接命令行

```bash
# 看文件信息
inp-tool info examples/mcfd_v2_modified.inp

# 改一个值
inp-tool set examples/mcfd_v2_modified.inp guiopts aero_alpha 5.0 -o /tmp/modified.inp

# 批量生成(单行,适合脚本)
inp-tool sweep examples/mcfd_v2_modified.inp \
    --alpha 0,5,10,15 \
    --mach 0.6,0.8 \
    --out ./my_sweep

# 从 CSV 跑(Excel 维护的 case)
inp-tool sweep cases.csv \
    --template examples/mcfd_v2_modified.inp \
    --naming "case_a{alpha:02.0f}_b{beta:02.0f}.inp" \
    --out ./out
```

## 下一步

- [02-repl-tour.md](02-repl-tour.md) — REPL 全部命令
- [03-tasks.md](03-tasks.md) — 3 个任务向导详细
