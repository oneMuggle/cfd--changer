# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [v0.14.0] - 2026-06-14

### Added
- **集群配置 + 调度器适配 (`inp_tool.cluster`)** (Phase 1, PR #26)
  - `SchedulerType` enum: `torque` (默认, 10.10.10.251) / `slurm` (备) / `pbspro` (留接口)
  - `TorqueAdapter` / `SlurmAdapter`: 双调度器命令构造 + 输出解析
    - `parse_submit_stdout` (qsub `1234.head01` vs sbatch `Submitted batch job 1234`)
    - `parse_qstat_f` (Torque) / `parse_squeue` (Slurm) / `parse_qstat_user` (列格式计数)
  - `ClusterConfig` dataclass: 全量配置 (host / user / ssh_key / queue / 限流 / 资源 / 路径 / 列映射)
    - 持久化到 `~/.inp_tool/cluster.json` (Win/Linux 都支持)
  - `SshClusterClient`: 真 SSH 客户端 (4 种认证: ssh-key / password via sshpass / proxycommand / 默认)
    - `submit` / `status` / `status_many` / `cancel` / `list_user_jobs` /
      `tail` / `rsync_to` / `rsync_from` / `check_concurrency` / `probe`
  - `LocalDryRunClient`: 不真提交,只记录命令 (单元测试 + `--dry-run`)
  - `probe_scheduler()`: ssh 远端自动探测 qstat vs sinfo 识别调度器

- **批量提交 (`inp_tool.batch`)** (Phase 2, PR #27)
  - `PbsSubmission` / `PbsBatchResult` dataclass
  - `submit_sweep()`: 读 `sweep_report.json` → 遍历 pbs_submissions →
    `cluster.submit()` → 写回 manifest (`pbs_submissions` 段追加)
  - `--skip-existing` (默认 True) / `--limit` / `--dry-run` / `--no-respect-concurrency`
  - 并发限流 (Q3 = 暂停等待, 5 分钟超时)

- **PBS 状态查询 (`inp_tool.batch`)** (Phase 3, PR #28)
  - `SweepStatusEntry` dataclass
  - `query_sweep_status()`: 读 `sweep_report.json` → 调 `cluster.status()` 聚合
  - `summarize_states()` / `format_progress_table()`: 给 CLI 用
  - 错误处理: 单 `status()` 失败 → `state="Unknown"` / `live=False`, 不抛

- **运行中监控 (`inp_tool.monitor`)** (Phase 4, PR #29) — **用户最初核心需求**
  - `parse_info0_meta()`: 解析 `minfo0.mpf1d` → `{col_name: index}` 动态映射
  - `Info0Parser`: `parse_line` / `tail_progress` (列名动态 + 列索引可覆盖)
  - `CaseProgress` dataclass (step / time / dt / cfl_global / cfl_local /
    rhs_avg / rhs_max / eigenvalue / last_update)
  - `CaseMonitor` / `SweepMonitor`: refresh + history + watch loop
  - **用户需求达成**:
    - 监控当前计算步数: `CaseProgress.current_step`
    - 监控 CFL 数: `CaseProgress.current_cfl_local` (ramp 0.1→20.0)
    - 监控残差曲线: `history('current_rhs_avg')` / `('current_rhs_max')`

- **批量取消 + 重跑 (`inp_tool.batch`)** (Phase 5+6, PR #30)
  - `PbsCancelResult` / `cancel_sweep()`: 取消 active job, 默认跳过 C/E
  - `PbsRerunResult` / `rerun_sweep()`: 取消指定 state + 重新提交 (写临时 manifest)
  - `pbs run` 一站式 (submit + 立即 watch)

- **新 CLI 子命令** (5 个二级子命令, 全部走 `inp-tool <verb> <noun>`):
  - `inp-tool cluster probe / config / test` (Phase 1)
  - `inp-tool pbs submit / status / watch / cancel / rerun / run` (Phase 2-6)

- **新公共导出** (`from inp_tool import ...`):
  - 集群: `SchedulerType / ClusterConfig / ClusterInfo / PbsJobStatus /
    TorqueAdapter / SlurmAdapter / SshClusterClient / LocalDryRunClient / probe_scheduler`
  - 批量: `PbsSubmission / PbsBatchResult / submit_sweep`
  - 状态: `SweepStatusEntry / query_sweep_status / summarize_states / format_status_table`
  - 监控: `Info0Parser / CaseProgress / CaseMonitor / SweepMonitor /
    parse_info0_meta / format_progress_table / DEFAULT_INFO0_COLUMNS`
  - 取消: `PbsCancelResult / cancel_sweep / PbsRerunResult / rerun_sweep`

- **新测试** (累计 +239 用例, 共 906 passed, 覆盖率 80.66%)
  - `test_pbs_name.py` (25) / `test_cluster.py` (25) / `test_schedulers.py` (19)
  - `test_batch.py` (33, 含 cancel + rerun) / `test_pbs_status.py` (10) /
    `test_pbs_cli.py` (21) / `test_monitor.py` (21)

- **新文档** (本版本)
  - `docs/user-manual/20-pbs-cluster.md` (用户向)
  - `docs/technical/sweep/13-pbs-submit-watch.md` (开发者向)

### Changed
- **PBS 任务名校验 (v0.13 bug fix)** (Phase 0, PR #25)
  - `render_pbs_name` 默认 `max_len` 200 → 15 (集群 `-N` 硬约束)
  - `extract_pbs_basename` 默认 `max_len` 8 → 14 (留 1 给 suffix)
  - 新增 `validate_pbs_name()` (长度 / 首字符 / 空白 / 字符集 4 规则)
  - 新增 `PbsValidationError` 异常类
  - `write_pbs()` 写出前自动校验, 违规 raise
  - 常量 `PBS_NAME_MAX_LEN = 15`
- **inp_tool 保持零运行时依赖**: cluster / batch / monitor / cli 全部 stdlib only

### Fixed
- v0.13 已知 bug: PBS 任务名超 15 字符提交会被集群拒 (#25)
- 集群配置 hardcoded (`q02` / `10.10.10.251` / `20 jobs` / ssh key 无) → 全可配置 (Phase 1)

### Notes
- **真实 mcfd.info0 数据列名与直觉不符**: minfo0.mpf1d 的 `CFL_global` 列实际是
  `cflglo` 残差上界 (常值 `1e15`); `CFL_local` 列才是真实 CFL ramp (0.1→20.0)。
  这是 CFD++ 内部命名约定, `monitor.py` 用 column index 而非 name 拿值规避。
- **真实集群 smoke test 待用户给 ssh key + 集群访问**。
- 累计代码: +2531 行生产代码, +2640 行测试 (含 Phase 0-6)。

## [v0.13.0] - 2026-06-13

### Changed
- **DetectController** 切到真实 :func:`inp_tool.equations.detect_equations`(v0.9.1 + v0.11.0 API)
  - 替换 v0.12 简化关键字扫描(``has_reftem`` / ``has_turbulence`` 等启发式)
  - :data:`DetectionReport` 现在 wrap :class:`EquationSystemReport` 的薄 adapter
  - 保留 v0.12 字段(has_reftem / has_reynolds / has_chemistry / is_two_temperature /
    turb_keywords / notes / recommended_fields)以不破坏 DetectPanel 引用
  - **新增真实字段**:``turbulence_model`` / ``energy_model`` / ``gas_model`` / ``n_species`` /
    ``gasnam`` / ``sweeps_equation_warnings``
  - ``run(inp, *, intended_axes=None)`` 支持 wizard step_4b/4c axis 透传
- **PresetDialog** 切到真实 preset 类(替换 v0.12 hardcoded ``_PRESETS`` dict)
  - ``turb`` → :func:`make_turbulence_preset` (:class:`SSTKOmegaPreset`,I=0.01/L=0.01/U_ref=204)
  - ``2t`` → :class:`TwoTemperaturePreset`(T_trans=300/T_vib=300)
  - ``species`` → :class:`SpeciesPreset`(fractions={'N2': 0.79, 'O2': 0.21})
  - ``accept(inp)`` 后置注入;preset.apply(inp) 改写
  - 捕获 :class:`EquationRewriteError` + :class:`TwoTemperatureError` + 兜底 ``Exception``
    → 错误标签(不弹模态 QMessageBox — 避免阻塞自动化测试)
- **DetectPanel** UI 增强
  - 新增 4 字段:能量/TurbulenceModel/GasModel/物种数(从 EquationSystemReport 透传)
  - 警告区双拆分:notes(方程自身) + sweeps_equation_warnings(wizard axis 告警)
  - ``run(inp, intended_axes=None)`` 透传给 controller

### Fixed
- **CI** 改用 ``--ignore-glob='tests/test_gui_*.py'`` 跳过 macOS GUI 测试
  (替代 v0.12 显式 ``--ignore`` 列表;新增 GUI test 文件自动跳过)
  原因:macOS ARM runner 缺 PySide2 5.15.2.1 wheel

### Tests
- 763 passed, 6 skipped, 0 回归(原 v0.12 759 + v0.13 新增 18 - 删除 1 旧 test 文件 = +4)
- 新增 ``test_gui_detect_controller_adapter.py`` (8 测试)
- 新增 ``test_gui_preset_dialog_v013.py`` (7 测试)
- 删除 ``test_gui_detect_controller.py`` (v0.12 简化扫描语义已废弃)
- ``test_gui_detect_panel.py`` / ``test_gui_main_window_integration.py``:fixture 加 ``seq.# eqnset_define`` SST

## [v0.12.0] - 2026-06-13

### Added
- **新包 `inp_tool_gui/`**(PySide2 5.15.2.1,Win7 兼容的 Qt 最后稳定版)
  - 入口:`inp-tool-gui` / `python -m inp_tool_gui`
  - 中心区 4 标签页 QTabWidget:**文件**(InpTreeWidget 树形) / **检测**(DetectPanel + 3 个 Preset) / **Sweep**(SweepForm + 结果表) / **对比**(DiffViewer 双栏 diff)
  - 菜单 / 工具栏 / 状态栏齐全;`Ctrl+O/S/Z/Y/Q` 等标准快捷键
  - undo / redo 栈 + dirty 标志自动管理(走 EditController)
  - 顶层语句 + 块两层,同名块加 `[N]` 后缀区分
- **新 extras `[gui]` / `[gui-build]`**(`pyproject.toml`)
  - `[gui]`:仅 `PySide2==5.15.2.1`(零依赖核心不被污染)
  - `[gui-build]`:`PySide2` + `pyinstaller`(打包用)
- **新 console_script `inp-tool-gui`**(`pyproject.toml [project.scripts]`)
- **`setuptools.packages`** 加 `inp_tool_gui`(并列包,不进 inp_tool core)
- **`inp_tool_gui.spec`** PyInstaller 配置:hiddenimports 列 PySide2 子模块 + shiboken2 + inp_tool core;`console=False`(Win 避免后台黑窗)
- **Controllers**(零 PySide2 依赖,纯 Python)
  - `FileController`:open / save / set_value / get_value / current_path / is_open / inp
  - `EditController`:set_value + undo/redo 栈 + dirty 标志 + UndoEntry dataclass
  - `SweepController`:load_from_yaml/json/dict + preview + run + last_report
  - `DetectController`:run(inp) → DetectionReport(reftem/reynolds/turb/chem/2T 标志 + notes + recommended_fields)
  - `DiffController`:load_pair(a, b) → DiffReport + unified_text
- **Widgets**
  - `InpTreeWidget`:3 层树(顶层语句 / block / stmt / value);populate / refresh_value / value_edit_requested signal
  - `ValueEditorDialog`:按 typed 推断 kind(bool > int > float > str);重写 accept() 走校验路径(失败保持打开 + 就地错误标签,不弹模态 QMessageBox — 避免阻塞自动化测试)
  - `DetectPanel`:`run(inp)` 渲染报告 + 警告区 + 推荐字段应用按钮
  - `PresetDialog`:3 类 preset(turb/2t/species),`accept()` 批量调 EditController.set_value
  - `SweepForm`:加载 YAML/JSON + 同步运行 + QTableWidget 4 列展示 CaseResult
  - `DiffViewer`:QTextBrowser 渲染 unified diff,行首 + / - / @@ 加色
- **文档**:`docs/user-manual/interactive/04-gui.md`(用户)+ `docs/technical/ux/01-gui-architecture.md`(开发者)
- **测试**:97 个 GUI 测试,全过;Linux + PySide2 5.15.2.1 + cfdchanger (Py3.8) 全部 offscreen 平台跑通

### Notes
- **重大变更**:在 v0.9.1 + v0.10.0 + v0.11.0 之后,以 v0.12.0 发布 GUI 子系统。DetectController 简化版(基于关键字扫描)作为本次起点;v0.13.x 期间将切换到真实 `detect_equations()` (v0.9.1 已上线) + `TurbulencePresetBase.apply` (v0.11.0 已上线)
- v0.12 简化版:SweepForm 同步运行(后续可加 QThread);关闭时不弹"未保存"(后续 closeEvent 增强)
- Win7 物理机自测留给用户(详见 `docs/user-manual/interactive/04-gui.md` §5 自测 checklist)

## [v0.11.0] - 2026-06-12

### Added
- **wizard.py**: `step_4b_equation_axes` — 向导式选择 turbulence/energy/gas 3 个 axis(仅 Cartesian,8→10 步) [PR #18]
- **wizard.py**: `step_4c_equation_overrides` — per-case 覆盖 I/L/U_ref 或温度(4b 选了 axis 才出现) [PR #18]
- **wizard.py**: `_read_template_value` / `multi_menu` helper(模板默认值读取 + 多选菜单) [PR #18]
- **wizard.py**: `step_4a_detect` 末尾新增 "你选的 axis 与 template 不兼容" 段 [PR #18]
- **equations.py**: `EquationSystemReport.sweeps_equation_warnings: List[str]` 字段(wizard 消费,独立于 notes) [PR #18]
- **equations.py**: `detect_equations(inp, intended_axes=None)` 接受可选 axis 参数,比对用户选 vs template 状态 [PR #18]

### Fixed
- **wizard.py**: `step_6_preview` 未把 `data["turbulence"]` / `data["energy_overrides"]` 喂给 `CaseSweep.from_dict`,导致 step_4c 的 per-case 覆盖是死端(C1 修复) [PR #18]
- **equations.py**: `set_turbulence_model` / `set_energy_model` / `set_gas_type` 3 个新写函数,改 `eqnset_define` v4/v5/v6 + 联动 `physics.tnoneq_numeqns` / `vibtem` / `reftem`
- **equations.py**: `EquationRewriteError` 异常 + `EquationRewriteIssue` 数据类
- **equations.py**: `TurbulencePresetBase.clear_incompatible_fields: bool` 字段 + `apply(inp, model=...)` 签名
- **equations.py**: `EquationSystemReport.sweeps_equation_warnings: List[str]` 字段(wizard 消费,独立于 notes)
- **equations.py**: `detect_equations(inp, intended_axes=None)` 接受可选 axis 参数,比对用户选 vs template 状态
- **sweep.py**: SweepSpec 枚举轴识别(`turbulence` / `energy` / `gas` 三个 key 名)+ 短名 alias(`sst` / `sa` / `2t` / `none` 等)
- **sweep.py**: `CaseSweep.equation_switches` 字段(opt-out 开关)
- **sweep.py**: `TurbulenceInit` dataclass + `_resolve_turb_init()` + `turbulence.overrides` per-case 覆盖
- **sweep.py**: `CaseSweep.energy_overrides` 字段(per-case 温度覆盖)
- **sweep.py**: `generate()` 末尾循环重排:先切模型 → 选 preset → 应用
- **cli.py**: `sweep` 子命令加 `--strict-equations` / `--no-switch-turbulence` / `--no-switch-energy` / `--no-switch-gas` flag
- **wizard.py**: `step_4b_equation_axes` — 向导式选择 turbulence/energy/gas 3 个 axis(仅 Cartesian,8→10 步)
- **wizard.py**: `step_4c_equation_overrides` — per-case 覆盖 I/L/U_ref 或温度(4b 选了 axis 才出现)
- **wizard.py**: `_read_template_value` / `multi_menu` helper(模板默认值读取 + 多选菜单)
- **wizard.py**: `step_4a_detect` 末尾新增 "你选的 axis 与 template 不兼容" 段
- **tests/**: `test_equation_rewrite.py` / `test_sweep_equation_axes.py` + 8 个 wizard 集成/单元测试文件
- **docs/**: `technical/19-equation-sweep-extend.md` §19.7 增 "Wizard 集成" 小节

## [v0.9.1] - 2026-06-11

### Added
- **`equations.py` GasModel 新增 `MULTI_TEMP`** 枚举(对应 eqnset_define v6=11 + tnoneq_numeqns=1 双温热非平衡)。
- **`EquationSystemReport.gas_code` 字段**:保留 eqnset_define 第 2 行第 0 位的原始整数(0/1/11),供 wizard 追溯使用。
- **CLI `info --detect` flag**:`inp-tool info <file> --detect` 在文件概览后追加方程系统/湍流模型/气体类型检测报告 + 一致性告警。
- **REPL 新增 3 个语义化命令**(v0.9.1 方程感知组):
  - `detect` — 显示当前 file 的检测报告
  - `turb I=<x> L=<y> [U=<z>]` — 按检测到的湍流模型(SST/k-ε/SA/Goldberg)写 `guiopts.turbi_*` 初始化字段(层流自动拒绝)
  - `2t T=<x> Tvib=<y>` — 双温联动写 `physics.tnoneq_numeqns=1`、`reftem`、`vibtem`,缺一抛 `TwoTemperatureError`
- **`docs/technical/18-equation-aware-config.md`**(参数表固化):eqnset_define 31 个 values 中 9 个语义位置 + 5 湍流模型 × 3 气体类型实测真值表 + 4 个常见误区(`gasnam` / `ntrbst` / `dfceli` / `ifwfne` / `infsets`)。
- **测试 +20**:5 个 v6 单元(`TestDetectGas`)+ 1 个 multi_temp suanli 端到端 + 1 个 two_temperature_layered + 2 个 `info --detect` CLI + 13 个 REPL equations(`test_repl_equations.py`)。
- **WizardModifyFile 加 `step_1a_detect`**(加载文件后立即展示方程系统/湍流/气体检测报告 + 推荐字段)。
- **WizardSweep 加 `step_4a_detect`**(展示 template 的方程系统报告,让用户在 naming/pbs 前清楚 template 配置)。
- **CaseSweep YAML/JSON 字段 `turbulence` / `two_temperature`**:`from_dict` 解析 + `generate()` 末尾应用 preset
  - YAML 例:`turbulence: {enabled: true, I: 0.01, L: 0.01, U_ref: 204}`
  - YAML 例:`two_temperature: {T_trans: 300, T_vib: 200}`
  - 自动检测 template 湍流模型选 preset(SST/k-ε/SA/Goldberg);层流 template 启用 turbulence 时抛 `ValueError`
- **集成测试 +14**(`test_sweep_equations_integration.py`):覆盖 `from_dict` 解析 / `generate()` apply / wizard step 注册 + 烟测。

### Changed
- **`detect_equations()` 改用 eqnset_define v6 判别 GasModel**(替代 v0.9.0 的 gasnam 启发式 — 实测 7 个 compare/ 文件全部 gasnam=Air,旧逻辑误判)。
- **一致性校验**:v6==11 ⇔ tnoneq_numeqns==1 不匹配时写 `report.notes` 警告(不阻断)。
- **REPL `REPL_COMMANDS` / 命令分组**:新增"方程感知"组(detect/turb/2t)。
- **`docs/technical/README.md`**:章节数 16 → 17。

### Fixed
- **14 个 pre-existing CLI subprocess 测试失败**(`test_cli.py` / `test_sweep_cli.py` / `test_sweep_cli_csv.py`):根因是从仓库根跑 subprocess 时 Python 把外层 `./inp_tool/` 当 namespace package,触发 `ImportError: cannot import name '__version__'`。修复:所有 subprocess 调用加 `cwd=tmp_path`。

### Migration
- **API 用户**:`EquationSystemReport` 新增 `gas_code` 字段(向后兼容);`GasModel.MULTI_TEMP` 是新枚举值,既有代码 `== GasModel.PERFECT_GAS` 等比较不受影响。
- **CLI 用户**:`info` 不传 `--detect` 时输出与 v0.9.0 完全一致。
- **REPL 用户**:3 个新命令是加法,旧命令零变化。
## [v0.9.0] - 2026-06-10

### Added
- **新模块 `inp_tool.pbs`**(零运行时依赖,纯 stdlib):`PbsConfig` / `PbsIssue` dataclass + 6 个公开 API
  - `detect_pbs_template()`:从 source_dir glob `run_*.pbs`,多模板打印 warning 到 stderr
  - `validate_base_case_dir()`:文件级检查(mcfd.inp 必填 / 网格/物性/配置软提示)+ block 级检查(`tsteps` / `physics` warning,`chemkin` / `restart` warning)。所有 block 检查为 warning 而非 error,保持向后兼容(老 fixture 用 `tsteps` / `end` 格式不被破坏)
  - `render_pbs_name()`:默认短名 / 用户模板覆盖 / `max_len` 截断 / 特殊字符 sanitization
  - `write_pbs()`:替换或追加 `#PBS -N` 行,支持 `template_text` in-memory 参数(避免 hardlink 副作用)
  - `extract_pbs_basename()`:从 `#PBS -N` 截前 N 字符作 base
- **`CaseSweep.pbs: Optional[PbsConfig]`** 字段 + `from_dict` 解析 `pbs:` 子字典 + `from_yaml` / `from_json` 透传
- **`SweepValidationError`** 异常类(预留给 v0.9.x 后期严格模式)
- **`generate()` 整合**(per_dir 模式 + `sweep.pbs` 启用时):
  - 开头调 `validate_base_case_dir()`,warning 打印到 stderr(不阻断)
  - 每个 case 末尾调 `write_pbs()`,in-memory template 读一次(循环外),循环内 unlink hardlink + write 避免 case 间同步
  - `CaseResult.pbs_name` / `pbs_template` 字段
  - `SweepReport.to_dict()` per_dir 模式加 `pbs_enabled` 顶层 + 每 case `pbs_name` / `pbs_template`
- **CLI 新增**:`inp-tool sweep --pbs/--no-pbs`(默认 yes)+ `--pbs-naming` 模板 flag
- **WizardSweep 加 `step_5a_pbs`**(7 步):确认是否生成 pbs + 展示建议任务名 + 用户输模板
- **`__init__.py` 导出** `PbsConfig` / `PbsIssue` / 5 个 pbs 函数
- **测试**:33 个 pbs 单测 + 12 个 sweep 集成 = 共 45 个新测;全 suite **449 passed, 6 skipped**,0 回归

### Changed
- **`__version__` 0.8.3 → 0.9.0**

### Migration
- **API 用户**:`CaseSweep` 新增 `pbs` 字段(默认 None),现有 YAML/JSON config 零修改
- **CLI 用户**:不传 `--pbs` 仍走默认(yes),传 `--no-pbs` 关;`--pbs-naming` 给具体模板
- **Wizard 用户**:多了 step_5a_pbs 一步(默认 yes,enter 接受建议名或输模板)

## [v0.8.4] - 2026-06-10

### Added
- **WizardSweep 整目录模式为默认**:`wizard sweep` 从 8 步缩为 6 步,`source_dir` 必填(基础算例目录),模板路径自动取 `source_dir/mcfd.inp`。扁平模式(只写 mcfd.inp)从 wizard 中完全移除,与"完整算例目录扫一组参数"的主流场景对齐
- **新 step 顺序**:`source_dir` → `copy_strategy` → `output` → `mode` → `params` → `naming` → `preview+execute`(原 step_7/step_8 合并为 step_6)
- **`build_sweep_config_interactive` 同步必填**:source_dir 提到第一位,`copy_strategy` 必填(因 source_dir 必填),cfg 始终含 source_dir/copy_strategy
- **CLI `[DEPRECATION]` 提示**:`inp-tool sweep` 不传 `--source-dir` 时,stderr 打印 `[DEPRECATION]` 引导用户改用 `--source-dir`,行为不变(扁平仍可走,向后兼容)
- **新增 `force` 选项**:wizard step_6 新增"目标子目录已存在时覆盖?"确认,沿用 `CaseSweep.generate(force=...)` API
- **测试覆盖**:7 个 wizard_sweep test + 4 个 sweep_interactive test + 2 个 menu test + 2 个 CLI deprecation test = 共 15 个新/重写测试,全部 404 passed

### Migration
- **wizard 用户**:现在必须先指定 source_dir(基础算例目录),template 自动取其下 mcfd.inp
- **CLI 用户**:不传 `--source-dir` 仍可走扁平(老用法兼容),但 stderr 会打 deprecation 提示
- **API 用户**:`CaseSweep.source_dir` 字段、`CopyStrategy` 枚举、`generate()` 签名均未变,无 breaking change

## [v0.8.3] - 2026-06-09

### Fixed
- **Standalone binary 缺 [api]+[yaml]+setuptools._vendor.backports** (3 重原因):
 1. **release.yml build job 装少了 deps**:只装 `.[build]`,没装 `.[api,yaml]`,PyInstaller Analysis 找不到 yaml/fastapi → 不打包。修复:build job 装 `.[api,yaml,build]`
 2. **setuptools 75+ 的 `pyi_rth_pkgres` hook 触发 jaraco.context 内部 `from . import backports`**:backports 是 setuptools 内置的 vendor 子模块(顶层不可见),PyInstaller 默认不打包。修复:hiddenimports 加 `setuptools._vendor.backports` + `setuptools._vendor.backports.tarfile`

## [v0.8.2] - 2026-06-09

### Fixed
- **Standalone binary 缺 PyYAML 模块**:`inp_tool.spec` 的 `hiddenimports` 缺 `'yaml'`(PyYAML 是 `[yaml]` extras,静态分析看不见),导致:
  - REPL `wizard sweep` step_3 输入 YAML 时崩 (`ModuleNotFoundError: No module named 'yaml'`)
  - CLI `--config sweep.yaml/.yml` 不能用(.json/.csv 仍可用)
  - 修复:在 `inp_tool.spec` 的 `hiddenimports` 加 `'yaml'` → 下次 release workflow 自动重新打包

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
