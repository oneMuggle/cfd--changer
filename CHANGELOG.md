# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [v0.8.1] - 2026-06-09

### Fixed
- **WizardSweep 缺 v0.8.0 引导**:原 v0.8.0 release 时漏了 REPL `wizard sweep` 命令的 source_dir 引导(只更新了 CLI flag + `inp-tool sweep -i`),导致 REPL user 拿不到 per_dir 模式。本次把 WizardSweep 从 7 步扩到 8 步(新增 step_5_source_dir:问基础算例目录 + 复制策略),三入口(CLI / interactive / REPL wizard) 完全一致
- **预览行增加源目录显示**:per_dir 模式时,step_7_preview 显式打印 `源目录: <path> (策略: hardlink)`,用户确认前能看到

## [v0.8.0] - 2026-06-09

### Added
- **整算例目录生成(sweep per-case dir 模式)**:从 `reference/suanli` 等基础算例目录一键复制 + 批量改 `mcfd.inp`,每个 case = 完整可运行算例目录(网格/配置/物性/脚本全到位),而非孤立 .inp 文件
- **`source_dir` 字段**:`CaseSweep.source_dir: Optional[str]`(None = 老 flat 行为,设值 = 整目录复制)
- **`CopyStrategy` 枚举**:`copy` / `hardlink`(默认,零空间)/ `symlink`,每种都支持失败自动退化(跨 FS / Windows 权限)
- **`_resolve_layout(cs) -> "flat" | "per_dir"`**:依据 `source_dir` 自动判定,无 bool 字段
- **`_copy_case_files()` 核心**:递归复制 + fnmatch 排除 + 友好错误(FileNotFoundError / FileExistsError)
- **CLI 4 个新 flag**:`--source-dir DIR` / `--copy-strategy {copy,hardlink,symlink}` / `--exclude PATTERN`(可多次传)/ `--force`(per_dir 时覆盖已存在)
- **interactive prompt**:`build_sweep_config_interactive()` 新增 source_dir + copy_strategy 引导(source_dir 非空时才问 copy_strategy)
- **manifest 扩展**:per_dir 模式 manifest 顶层新增 `layout` / `source_dir` / `copy_strategy` / `exclude`;每 case 新增 `files`(实际处理文件清单);flat 模式 manifest 零变化
- **`DEFAULT_EXCLUDE` 常量**:默认 `*.bak` / `*.BAK` / `mlog` / `nodesout.bin` / `*.log`
- **新模块导出**:`from inp_tool import CopyStrategy, DEFAULT_EXCLUDE`
- ~40 新测试:`test_sweep_case_dir.py` / `test_sweep_copy_strategy.py` / `test_sweep_interactive.py` 加 source_dir 用例
- **CLI help 自动更新**:`inp-tool sweep --help` 立即可见 4 个新 flag

### Changed
- `generate()` 新增 `force: bool = False` 形参(透传 CLI `--force`)
- `_copy_case_files()` 新增 `force: bool = False` 形参
- `build_sweep_config_interactive()` prompt 序列:11 → 12 步(加 source_dir)
- `CaseResult` 新增 `files_copied: Optional[List[str]]` 字段
- `SweepReport` 新增 `layout` / `source_dir` / `copy_strategy` / `exclude` 字段

### Compatibility
- 100% 向后兼容:不给 `source_dir` 时行为与 v0.7.1 完全一致;现有 359 测试零修改
- 现有 manifest 文件无需重写(flat 模式 manifest 字段集零变化)
- API 签名只有 additive 变化(新字段都带默认值)

### Verified
- 真实算例 smoke:`reference/suanli` (544MB) 跑 2-case sweep,hardlink 模式耗时 < 1s
- inode 共享验证:`cellsin.bin` 源/目标 st_ino 相同
- 排除规则验证:`*.bak` / `mlog/` / `nodesout.bin` / `*.log` 均未被打包
- manifest 字段:`layout=per_dir` / `source_dir` / `copy_strategy=hardlink` / `exclude` 全到位

## [v0.7.1] - 2026-06-09

### Added
- **i18n 基础设施**:`inp_tool/i18n.py` 纯 stdlib dict i18n + `t(key, **kw)` + `set_lang(zh|en)` + `INP_TOOL_LANG` 环境变量
- **REPL 中文化**:默认 zh,`--lang en` 切英文;intro / help / 错误带建议;启动打印"快速开始"面板(5 命令)
- **3 个任务向导**(`wizard` / `wizard modify-file` / `wizard sweep` / `wizard diff`):
  - `WizardBase` 抽象 + 通用 `input_text` / `confirm` / `menu` 组件
  - `WizardModifyFile` 5 步:选文件 → 选字段 → 输值 → 预览 → 输出
  - `WizardSweep` 7 步:模板 → 模式(笛卡尔/cases/groups/CSV)→ 填参 → 命名 → 输出 → 预览 → 执行(用 PR #1 新能力)
  - `WizardDiff` 3 步:基准 → 对比 → 输出格式
- **CLI `--lang` flag**:顶层 `--lang zh|en` 切语言
- **新模块**:`inp_tool/wizard.py`(`WizardCancel` / `WizardBase` / 3 个具体向导 / 4 个入口函数)
- **用户手册**:`docs/user-manual/` 新建,4 文件:README + 01-quickstart + 02-repl-tour + 03-tasks
- ~60 新测试:`test_i18n` / `test_repl_zh` / `test_wizard_{modify_file,sweep,diff,menu}`

### Compatibility
- 老 API 不变;`cs.sweeps.values` / `expand_cartesian(spec)` 等所有 v0.7.0 API 仍可用
- 老 CLI 调用零修改继续可用
- 老用户用 `--lang en` 切回英文(全功能等价)
- `tutorial` 命令保留(5 步自动演示)

## [v0.7.0] - 2026-06-09

### Added
- **sweep 灵活化**:三种新模式 + CSV loader,完全向后兼容
  - `CartesianSpec` / `ExplicitCase` dataclass + `CaseSweep.specs` 字段 + `materialize()` 方法
  - `cases:` 显式列表模式(`cases: [{...}, ...]`)
  - `groups:` 分组继承模式(`common` 字段自动注入,`{group}` 命名占位符)
  - 混合模式(`sweeps` + `cases` + `groups` 共存)
  - `CaseSweep.from_csv(path, template, output_dir, ...)` 加载 CSV(必填表头,列类型一致)
  - CLI 新增 `--template` / `--naming` flag 支持 CSV 模式:`inp-tool sweep cases.csv --template t.inp --naming "case_a{alpha}.inp"`
- 文档:`docs/technical/04-sweep-architecture.md` 加 §2.4 CaseSpec 抽象;`05-sweep-usage.md` 加 §6 三种模式 + 4 个完整示例(显式 / 分组 / 多组 / CSV)
- 60+ 新测试(`test_sweep_backward` / `test_sweep_explicit` / `test_sweep_groups` / `test_sweep_mixed` / `test_sweep_csv` / `test_sweep_cli_csv`)

### Changed
- `CaseSweep` 内部用 `specs` 列表统一 case 归一化;`generate()` 走 `materialize()` 路径
- 命名模板支持 `{group}` 占位符(由 `materialize` 注入)
- 现有 `sweeps:` YAML 行为零变化(241 老测试全绿)

### Compatibility
- `sweeps: SweepSpec` 字段保留,老 API `cs.sweeps.values` 仍可用
- `expand_cartesian(spec: SweepSpec)` 仍可独立调用
- 老 CLI 调用(`inp-tool sweep sweep.yaml --alpha ...`)零修改继续可用

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
