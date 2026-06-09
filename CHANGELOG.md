# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [v0.6.1] - 2026-06-09

### Fixed
- `aero` 命令隐性写盘 — `_aero_apply` 之前在每次 `aero` 调用后自动调 `writer_write`,**不需要 `save`**。修复后:`aero` 只改 in-memory + 标 dirty + 推 undo(与 `set` / `let` 一致),磁盘文件**不变**。`save` 仍是显式写盘命令。

回归测试 `test_aero_does_not_write_to_disk_without_save` 用 MD5 哈希断言。235 passed / 6 skipped,无回归。详见 [PR #5](https://github.com/oneMuggle/cfd--changer/pull/5)。

## [v0.6.0] - 2026-06-08

### Added
- REPL `aero` 命令:统一管理 mcfd.inp 的攻角 / 来流参数
  - 无参 `aero` — 一行总览当前 `Ma / α / β / T / p / U / V / W / refvel`
  - `aero Ma=X alpha=Y beta=Z [T=X] [p=X]` — 一行多参设置,**U/V/W 自动几何分解**(复用 v0.5.1 修复后的 `FreestreamPreset`),未改字段保留模板值
  - `undo` — 撤销最近的 `aero` 改动
  - 与 `sweep`(批量扫)互补:`aero` 单点编辑,`sweep` 生成 N 个算例

### 用法

```bash
inp> aero                                  # 一行总览
Ma=0.8  α=0.0°  β=0.0°  T=288K  p=1.013e+05Pa
U=30  V=0  W=0  |V|=30  refvel=-1

inp> aero alpha=5                          # 改 α,U/V/W 自动重算
aero: alpha 0.0→5.0
Ma=0.8  α=5.0°  β=0.0°  T=288K  p=1.013e+05Pa
U=271.1  V=0  W=23.72  |V|=272.2  refvel=272.2

inp> aero Ma=0.85 alpha=10 beta=2         # 同时改 3 个
inp> undo                                  # 一键回滚
inp> save                                  # 写盘
```

### 回归覆盖
- 10 个新测试 (`test_aero_*`),234 passed / 6 skipped,无回归
- 详见 [PR #4](https://github.com/oneMuggle/cfd--changer/pull/4)

## [v0.5.1] - 2026-06-08

### Fixed
- `sweep` 子命令在只传 `--alpha`(不传 `--mach / --t-inf / --p-inf`)时,会**错误覆盖**模板的 `aero_ma / aero_temp / aero_pres / physics.refvel/reftem/refpre` 为硬编码默认值(`0 / 288.15 / 0`)。修复后:从模板 `guiopts` 块读这些值作默认,仅当用户显式 `--mach` 等才覆盖。`U/V/W` 始终基于解析后的 `mach + T` 重算。

回归覆盖 4 个新测试,224 passed / 6 skipped,无回归。详见 [PR #3](https://github.com/oneMuggle/cfd--changer/pull/3)。

## [v0.5.0] - 2026-06-08

### Added
- `inp-tool shell` 交互式 REPL 子命令(multi-file alias 状态 + current 指针)
- 多文件状态管理:`load` / `files` / `use` / `unload` / `status` / `save` / `save as`
- Buffer + 显式 save,dirty 跟踪,默认退出前不写盘
- Undo 栈(线性 LIFO,`undo [N]` 回滚最近 N 次 set)
- Session 变量 + `$var` 命令插值(`$$` 转义为字面 `$`)
- Shell escape `! <cmd>`(透传 stdout/stderr,非零退出打印 exit code)
- `<alias>:` 前缀覆盖 current 指针(per-command override)
- 委托 cli.py handler:`info` / `get` / `set` / `diff` / `parse` / `sweep`
- `sweep` REPL 命令从 `session.variables` 读默认
- Tab 补全:命令 / alias / 块名 / 键名 / shell 可执行名(`InpCompleter`)
- 持久历史:`~/.inp_history` 1000 行 FIFO,接 readline(Windows 降级到内存)
- `history` 命令 + `!N` rerun
- 4 个新模块:`repl_state` / `repl` / `repl_completer` / `repl_history`(零新增运行时依赖)
- PyInstaller onefile Linux 二进制已验证可独立运行 `inp-tool shell`

### Fixed
- `do_set` 后 `lf.inp` 与磁盘同步,避免连续 set + undo 链 desync
- `unload -f` 标志可放任意位置(此前 `-f a` 被误识别)
- `do_unload` KeyError 分支补 `return`,避免 fall-through
- `OSError` 与 `PermissionError` 错误消息分开(不再误标为 "permission denied")
- `do_sweep` 真正可用 — 原 plan 用 `Namespace(_tokens=...)` 但 `cmd_sweep` 不读 `_tokens`
- Windows `import readline` 顶层 import 崩溃(移到 complete() 内部 + try/except)
- REPL smoke 在非 tty stdin 下挂死(`main()` 改用 line-by-line driver)
- `do_sweep` 在 Windows 路径上 `shlex.split` 吃反斜杠(改用 `arg.split()`)
- `complete()` 方法内 `import readline` 加 try/except 保护(Windows 测试)
- `__version__` 与 shell banner 同步到 0.5.0(此前 0.4.2 vs 0.5.0 drift)
- `do_files` 输出排序确定性(原字典插入顺序不稳定)
- 移除死代码 `_print` helper
- `repl_history.bind_readline()` Windows 不可达代码标 `# pragma: no cover`(通过 80% 阈值)
