# 02 — REPL 全功能指南

> **面向:** 想深入了解 inp-tool shell 所有命令的用户

---

## 启动

```bash
$ inp-tool shell
```

`inp-tool shell [files...]` 也支持预加载 0 或多个文件:

```bash
$ inp-tool shell baseline.inp modified.inp
# 自动预加载并设为 current = baseline
```

## 命令分组(中英)

```
【文件管理】
  load         加载 .inp 文件到会话
  unload       卸载已加载文件
  files        列出已加载文件
  use          切换当前文件
  status       查看未保存改动
  save         保存到磁盘

【编辑 / 查看】
  info         显示当前文件的 block 列表
  get          读一个字段值
  set          改一个字段值
  aero         改来流(Ma/α/β/T/p 一行)
  parse        看完整结构

【比较】
  diff         当前文件 vs 指定 alias

【批量生成】
  sweep        笛卡尔/显式/分组 sweep
  sweep-config 从 JSON/YAML 跑 sweep

【任务向导】
  tutorial     5 步引导教程(自动跑)
  wizard       任务向导(用户驱动)

【会话 / 调试】
  let          定义会话变量($var 引用)
  undo         回滚最近 set
  history      查看命令历史
  help         帮助
  exit / quit  退出
```

`help <cmd>` 看单命令详细帮助。

## 关键概念

### 1. 多个文件同时编辑

`inp-tool shell a.inp b.inp c.inp` 同时加载 3 个文件。提示符的 `[alias]` 表示当前指针。

```bash
inp> load a.inp
inp[a]> load b.inp
inp[b]> load c.inp
inp[c]> use a       # 切回 a
inp[a]> files        # 看所有
* a                 /path/a.inp  [clean]
  b                 /path/b.inp  [clean]
  c                 /path/c.inp  [clean]
```

`<alias>:cmd` 临时给单个命令覆盖 current(不切换指针):

```bash
inp[a]> b:get aero_alpha    # 在 b 的 context 跑 get
```

### 2. dirty 状态

`set` / `aero` / `let` 只改 in-memory,标 dirty,**不**写盘。`save` 显式写盘。

```bash
inp[a]> aero alpha=5     # dirty=True
inp[a]> status
* a   /path/a.inp  [unsaved changes]
inp[a]> save              # 写盘
inp[a]> status
* a   /path/a.inp  [clean]
```

退出时如有 dirty,会提示但不强制保存。

### 3. undo

回滚最近 set / aero / let。`undo [N]` 回滚 N 次。

```bash
inp[a]> set guiopts aero_alpha 5
inp[a]> set guiopts aero_ma 0.8
inp[a]> undo             # 撤销 ma=0.8
inp[a]> undo             # 撤销 alpha=5
```

### 4. 会话变量与插值

```bash
inp> let M=0.8
inp> let ALPHA=5
inp> set guiopts aero_ma $M
inp> set guiopts aero_alpha $ALPHA
```

`$$` 转义为字面 `$`。

### 5. Shell escape

```bash
inp> !ls                 # 跑 shell 命令
inp> !grep alpha mcfd.inp
```

非零 exit code 会打印 `(exit code: N)`,REPL 继续。

### 6. 历史 + rerun

```bash
inp> history             # 最近 20 条
inp> history 50          # 最近 50 条
inp> !3                  # 跑 history 第 3 条
inp> !N                  # 同上
```

## 错误信息(中文)

```bash
inp> get foo
错误: 尚未加载文件。请先用 `load <路径>` 加载 .inp 文件
     示例:load examples/mcfd_v2_modified.inp
```

每个错误都带"建议下一步"。`--lang en` 切英文。

## 退出

```bash
inp> exit
inp> quit
Ctrl+D                  # EOF
```

退出时如有 dirty,会提示但不强留(可重进 REPL 继续)。

## 切换语言

```bash
# CLI 启动时
inp-tool --lang en shell
inp-tool --lang zh shell    # 默认

# 环境变量
INP_TOOL_LANG=en inp-tool shell
```

## 下一步

- [03-tasks.md](03-tasks.md) — 3 个任务向导
