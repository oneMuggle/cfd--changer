# 计划:sweep 整算例目录生成(source_dir + per-case dir)

> **状态:** 待用户确认(2026-06-09)
> **对应版本:** v0.8.0(预计)
> **优先级:** 高(用户每次跑 sweep 都要手动复制网格/配置,体验严重断链)
> **前置:** v0.7.0(cases/groups/CSV 灵活化)、v0.7.1(i18n + wizard)已合入 main

---

## 1. 背景

当前 `inp_tool.sweep.generate()` **只写 `mcfd.inp` 一个文件**,但实际算例是一个**完整目录**:

```
/home/fz/project/cfd--changer/reference/suanli/   (544MB)
├── mcfd.inp                  ← 模板,会被修改
├── cellsin.bin        155M   ← 网格(必须随算例)
├── nodesin.bin        123M   ← 节点(必须)
├── nodesout.bin       123M   ← 输出文件(下次运行时被覆写,可选)
├── cgrpsin.bin.1       18M   ← 网格(必须)
├── exbcsin.bin        4.1M   ← 边界条件(必须)
├── mcfd.bc                   ← 配置(必须)
├── mcfd.grp                  ← 配置(必须)
├── npfopts.inp               ← 配置(必须)
├── pltopts.inp               ← 配置(必须)
├── scalegr.inp               ← 配置(必须)
├── temp.rea                  ← 配置(必须)
├── run_cfdpp.pbs             ← 作业脚本(必须)
├── C.dat / CO.dat / CO2.dat / O.dat / O2.dat  ← 物性(必须)
├── mcfd.inp.bak              ← 备份(不要)
├── nodesin.bin.bak           ← 备份(不要)
├── npfopts.inp.bak           ← 备份(不要)
└── mlog/                     ← 上次运行日志(可选)
    ├── cellvols_c.log
    ├── mcfdgui_c.log
    └── scalegr_c.log
```

**问题:** 用户跑 `inp-tool sweep config.json` 后,只在 `output_dir` 下得到 N 个孤立的 `mcfd.inp`,**没有网格、没有配置、没有物性文件**,根本跑不起来。用户必须手动 `cp -r suanli/* sweep_cases/case_xxx/`,体验断链。

## 2. 目标

| # | 目标 | 验收 |
|---|------|------|
| G1 | sweep 把基础算例目录**完整复制**到每个子算例,只覆盖 `mcfd.inp` | 用 `reference/suanli` 跑 6-case sweep,每个子目录可直接 `qsub` |
| G2 | 默认排除 `*.bak` 和 `mlog/`(运行时输出,不应打包) | 排除规则可在测试里显式断言 |
| G3 | 支持三种复制策略:`copy` / `hardlink` / `symlink`,默认 `hardlink`(零空间浪费 + 跨平台兼容) | CLI + YAML + API 三处可配 |
| G4 | 100% 向后兼容 | 不给 `source_dir` 时,行为与 v0.7.1 完全一致;现有 60+ 测试零修改全绿 |
| G5 | `manifest.json` 记录 `source_dir` + 复制策略 + 每个 case 的文件清单 | JSON 字段可读、可被下游脚本消费 |
| G6 | `--dry-run` 支持(只列要做的事,不算 hardlink、不写盘) | dry-run 输出含"将创建 N 个目录,复制 M 个文件" |
| G7 | 性能:100 cases × 544MB 用 hardlink 时延 < 5s(全是 inode 操作,无 IO) | smoke 测试通过 |
| G8 | 覆盖率 ≥ 80% | pytest --cov 锁线 |

## 3. 非目标(明确不做)

- ❌ 跨算例共享 dedup(超出硬链接场景,留给 v0.9+)
- ❌ 把 `output_dir` 自动放在 `source_dir/sweep_*`(用户希望输出目录可随意)
- ❌ 重新生成网格/物性文件(假定基础算例已经准备好)
- ❌ 修改 `source_dir` 自身的文件(只读)
- ❌ `mlog/` 智能合并(只做"含/不含"二元)

## 4. 涉及文件

| 文件 | 动作 | 估行数 |
|------|------|--------|
| `inp_tool/inp_tool/sweep.py` | 加 `source_dir` / `copy_strategy` / `exclude` 字段,新 `_copy_case_files()` / `_render_layout_filename()` | +180 / -20 |
| `inp_tool/inp_tool/cli.py` | 加 `--source-dir` / `--copy-strategy` / `--exclude` flag;`interactive` prompt 加对应问题 | +60 |
| `inp_tool/inp_tool/wizard.py` | sweep wizard 加源目录选择 | +30 |
| `inp_tool/inp_tool/__init__.py` | 导出 `CopyStrategy` 枚举 | +10 |
| `inp_tool/tests/test_sweep_case_dir.py` (新) | per-case 目录模式全套测试 | +220 |
| `inp_tool/tests/test_sweep_copy_strategy.py` (新) | copy / hardlink / symlink 三模式 | +180 |
| `inp_tool/tests/test_sweep_backward.py` | 加断言:`source_dir=None` 时输出仍是扁平 .inp 文件 | +20 |
| `docs/technical/04-sweep-architecture.md` | 加 §9 整算例目录模式 + 流程图 | +60 |
| `docs/technical/05-sweep-usage.md` | 加 §7 实战案例(基于 `reference/suanli`) | +100 |
| `docs/user-manual/18-wizard-tasks.md` | wizard 章节加源目录步骤 | +30 |
| `CHANGELOG.md` | v0.8.0 段 | +15 |
| **本计划文档** | 实施完成后归档到 `docs/technical/17-sweep-case-dir.md`,**删除** plans 版 | +300 |

净代码 +450(含测试),文档 +200。

## 5. 技术方案

### 5.1 数据模型

```python
class CopyStrategy(str, Enum):
    COPY = "copy"        # shutil.copy2(慢,占空间)
    HARDLINK = "hardlink"  # os.link(快,零空间,跨 inode 但同 FS)
    SYMLINK = "symlink"    # os.symlink(零空间,跨 FS,Windows 需 dev mode)


@dataclass
class CaseSweep:
    template: str
    output_dir: str
    sweeps: SweepSpec
    naming: str = ""
    overrides: Dict[str, Any] = field(default_factory=dict)
    freestream: Optional[FreestreamPreset] = None
    manifest_path: Optional[str] = None
    naming_ext: str = ".inp"
    specs: List[Union[CartesianSpec, ExplicitCase]] = field(default_factory=list)

    # v0.8.0 新增:
    source_dir: Optional[str] = None          # 基础算例目录(整目录复制)
    copy_strategy: CopyStrategy = CopyStrategy.HARDLINK
    exclude: List[str] = field(default_factory=lambda: [
        "*.bak", "*.BAK",
        "mlog",                  # 目录
        "nodesout.bin",          # 求解器输出,下次会被覆写
    ])
```

### 5.2 generate() 新流程

```python
def generate(sweep: CaseSweep, dry_run: bool = False) -> SweepReport:
    if not dry_run:
        os.makedirs(sweep.output_dir, exist_ok=True)

    template_inp = parse_file(sweep.template)
    flat = sweep.materialize()
    layout = _resolve_layout(sweep)  # "per_dir" or "flat"

    report = SweepReport(template=sweep.template, layout=layout)
    used_names: Dict[str, int] = {}

    for case_spec in flat:
        params = case_spec.values
        # ... freestream + overrides (不变) ...

        # 命名:per_dir 模式无 ext,flat 模式带 .inp
        ext = "" if layout == "per_dir" else sweep.naming_ext
        name = _disambiguate(render_case_name(sweep.naming, params, ext=ext), used_names)

        # 关键差异:per_dir 模式目标是子目录
        target = (Path(sweep.output_dir) / name) if layout == "per_dir" \
                 else Path(sweep.output_dir) / name  # flat 时 = 老 .inp 路径

        if not dry_run:
            if layout == "per_dir":
                _copy_case_files(
                    src=Path(sweep.source_dir),
                    dst=target,
                    template_inp=template_inp,
                    strategy=sweep.copy_strategy,
                    exclude=sweep.exclude,
                )
                # 写修改后的 mcfd.inp(覆盖复制来的)
                write_preserve(deepcopy(template_inp_with_overrides), target / "mcfd.inp")
            else:
                write_preserve(deepcopy(template_inp_with_overrides), str(target))

        # manifest 记录 file list(per_dir 模式)
        case = CaseResult(
            case_id=name,
            path=str(target),
            params=params,
            applied=applied,
            files_copied=... if layout == "per_dir" else None,
        )
        report.cases.append(case)
    # ... manifest 写盘(不变) ...
```

### 5.3 `_copy_case_files()` 核心

```python
def _copy_case_files(
    src: Path, dst: Path, template_inp: InpFile,
    strategy: CopyStrategy, exclude: List[str],
) -> List[str]:
    """返回实际复制/链接的文件相对路径列表(供 manifest 用)"""
    dst.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []

    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        # 排除目录
        dirs[:] = [d for d in dirs if not _match_any(str(rel / d), exclude)]
        for f in files:
            rel_path = rel / f
            if _match_any(str(rel_path), exclude):
                continue
            src_f = Path(root) / f
            dst_f = dst / rel_path
            dst_f.parent.mkdir(parents=True, exist_ok=True)
            if strategy == CopyStrategy.COPY:
                shutil.copy2(src_f, dst_f)
            elif strategy == CopyStrategy.HARDLINK:
                os.link(src_f, dst_f)  # 失败 → 退化为 copy(同 FS 几乎不会失败)
            elif strategy == CopyStrategy.SYMLINK:
                os.symlink(src_f, dst_f)  # 失败 → 退化为 hardlink
            copied.append(str(rel_path))

    return copied


def _match_any(name: str, patterns: List[str]) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(name, p) for p in patterns)
```

### 5.4 向后兼容矩阵

| `source_dir` | `layout` | 行为 | 现有测试 |
|---|---|---|---|
| `None`(未给) | `flat` | 旧:每个 case = 1 个 `mcfd.inp` 文件 | 全绿 |
| 给出路径 | `per_dir` | 新:每个 case = 1 个子目录(完整算例) | 新测试覆盖 |

**关键:** `_resolve_layout()` 根据 `sweep.source_dir is not None` 切换,不引入新 bool 字段,避免冗余。

### 5.5 manifest 扩展

```json
{
  "template": "reference/suanli/mcfd.inp",
  "template_sha256": "...",
  "generated_at": "2026-06-09T20:30:00",
  "layout": "per_dir",                  ← 新
  "source_dir": "reference/suanli",     ← 新
  "copy_strategy": "hardlink",          ← 新
  "exclude": ["*.bak", "mlog", "..."],  ← 新
  "total": 6,
  "cases": [
    {
      "case_id": "case_aoa04_ma0.80",
      "path": "sweep_cases/case_aoa04_ma0.80",
      "files": ["mcfd.inp", "cellsin.bin", "nodesin.bin", ...],  ← 新
      "params": {...},
      "applied": {...}
    }
  ]
}
```

## 6. 实施阶段

### 阶段 0 — 开工前
- [ ] 0.1 写本计划
- [ ] 0.2 分支:`git switch -c feat/sweep-case-dir`
- [ ] 0.3 基线:`pytest` 全绿(60+ 测试)

### 阶段 1 — 数据模型扩展(零行为变化)
- [ ] 1.1 RED:`test_sweep_backward.py` 加断言 `source_dir=None` 时仍写扁平 .inp
- [ ] 1.2 GREEN:加 `CopyStrategy` enum + `CaseSweep` 三个新字段(默认 None / HARDLINK / 常用排除)
- [ ] 1.3 GREEN:`from_dict` 解析 `source_dir` / `copy_strategy` / `exclude`
- [ ] 1.4 GREEN:`_resolve_layout()` 工具函数
- [ ] 1.5 现有 60+ 测试零修改全绿

### 阶段 2 — 目录复制核心
- [ ] 2.1 RED:`test_sweep_case_dir.py` — `source_dir=tmpdir/base/` 跑 sweep,断言每个 case 子目录含全部文件
- [ ] 2.2 GREEN:`_copy_case_files()` 骨架(先支持 COPY 策略)
- [ ] 2.3 RED:默认排除 `*.bak` / `mlog/` / `nodesout.bin`
- [ ] 2.4 GREEN:排除规则 + `_match_any`
- [ ] 2.5 RED:目标目录已存在 → 报错
- [ ] 2.6 GREEN:目标已存在时抛 `FileExistsError`,提示用户加 `--force` 或换 naming
- [ ] 2.7 RED:写 `mcfd.inp` 覆盖复制来的版本
- [ ] 2.8 GREEN:复制完后 `write_preserve()` 覆盖

### 阶段 3 — 复制策略
- [ ] 3.1 RED:`test_sweep_copy_strategy.py` 三种策略各 1 个测试
- [ ] 3.2 GREEN:COPY(shutil.copy2)
- [ ] 3.3 GREEN:HARDLINK(os.link,失败 → 退化 COPY)
- [ ] 3.4 GREEN:SYMLINK(os.symlink,失败 → 退化 HARDLINK)
- [ ] 3.5 RED:cross-FS 硬链接失败时退化
- [ ] 3.6 GREEN:try/except OSError 自动退化

### 阶段 4 — manifest 扩展
- [ ] 4.1 RED:per_dir 模式 manifest 含 `layout` / `source_dir` / `copy_strategy` / `files`
- [ ] 4.2 GREEN:扩展 `SweepReport.to_dict()`
- [ ] 4.3 RED:flat 模式 manifest 仍只有老字段(无 layout 字段)
- [ ] 4.4 GREEN:`_resolve_layout` 决定字段是否写入

### 阶段 5 — CLI + wizard
- [ ] 5.1 RED:`inp-tool sweep config.json --source-dir reference/suanli` 跑通
- [ ] 5.2 GREEN:CLI flag 解析
- [ ] 5.3 RED:interactive prompt 加源目录问题
- [ ] 5.4 GREEN:`build_sweep_config_interactive()` 加 3 个新 prompt
- [ ] 5.5 RED:wizard sweep 路径加源目录
- [ ] 5.6 GREEN:`wizard.sweep_wizard()` 引导用户选源目录

### 阶段 6 — dry-run 与边界
- [ ] 6.1 RED:`--dry-run` 打印将做什么,不实际写盘
- [ ] 6.2 GREEN:per_dir 模式 dry-run 打印"将创建 N 个目录 + 复制 M 个文件"
- [ ] 6.3 RED:`--force` 覆盖已存在目录
- [ ] 6.4 GREEN:`force` 标志位 + 删除已存在再重做
- [ ] 6.5 RED:`source_dir` 不存在报错信息友好
- [ ] 6.6 GREEN:提前检查 + 清晰错误

### 阶段 7 — 真实算例 smoke
- [ ] 7.1 临时把 `reference/suanli/mcfd.inp` 复制为 fixture(只 4 个文件,小一点)
- [ ] 7.2 smoke:用 fixture 跑 4-case sweep,逐个验证子目录完整
- [ ] 7.3 smoke:对 `reference/suanli` 真实跑(因含 544MB,需 gitignore 输出)

### 阶段 8 — 文档与收尾
- [ ] 8.1 `04-sweep-architecture.md` 加 §9
- [ ] 8.2 `05-sweep-usage.md` 加 §7 实战
- [ ] 8.3 `user-manual/18-wizard-tasks.md` wizard 步骤
- [ ] 8.4 `CHANGELOG.md` v0.8.0 段
- [ ] 8.5 覆盖率 ≥ 80%
- [ ] 8.6 `simplify` + `code-review` agent
- [ ] 8.7 commit + push + PR
- [ ] 8.8 监控 CI + merge + 清理分支
- [ ] 8.9 归档本计划 → `docs/technical/17-sweep-case-dir.md`,**删除** plans 版

## 7. 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| HIGH | 100 cases × 544MB 用 COPY 策略 = 54GB 磁盘 | 默认 HARDLINK;CLI 默认值 + 文档醒目提示 |
| MEDIUM | hardlink 跨 FS 失败(罕见,如 `source_dir` 在另一 mount) | try/except 退化 COPY,WARN 提示 |
| MEDIUM | symlink 在 Windows 需 developer mode | 默认 HARDLINK,文档说明 |
| MEDIUM | 排除规则过严导致算例缺文件 | 默认排除保守(`*.bak` / `mlog` / `nodesout.bin`);用户可 override |
| MEDIUM | `reference/suanli` 在仓库里,纳入版本控制负担大 | 加 `.gitignore` 规则;真实算例测试不 commit 输出 |
| LOW | wizard / CLI / YAML / API 四处入口要保持一致 | 阶段 5 集中处理;`from_dict` 是唯一底层入口 |
| LOW | manifest schema 变化破坏下游脚本 | 只**新增**字段,删字段才破坏 |

## 8. 兼容性

- **API:** `CaseSweep` 新增字段都带默认值 → 现有调用零修改
- **YAML/JSON:** 现有 config 全部继续可用(不给 `source_dir` = 老行为)
- **CLI:** `inp-tool sweep config.json`(无新 flag)与 v0.7.1 完全一致
- **测试:** 60+ 现有零修改 + ~40 新增 = 100+
- **覆盖率:** ≥ 80%

## 9. 验收

- [ ] 现有 60+ 测试零修改全绿
- [ ] 新增 40+ 测试全绿
- [ ] 覆盖率 ≥ 80%
- [ ] 用 `reference/suanli` 跑 6-case sweep 后,每个子目录 `qsub run_cfdpp.pbs` 链路通(虽然我们不真跑)
- [ ] 老 YAML 无 `source_dir` 时输出仍是扁平 .inp
- [ ] manifest 含 `layout` / `source_dir` / `copy_strategy` / `files` 字段
- [ ] CHANGELOG v0.8.0 段
- [ ] PR merge 到 main + 打 tag

## 10. 不在本次范围

- ❌ 增量更新(下次跑只改 mcfd.inp,不动其他文件)— 留给 v0.9
- ❌ 跨算例 dedup(用 reflink / btrfs)— 留给 v0.9
- ❌ `output_dir` 与 `source_dir` 同源时自动 in-place
- ❌ Windows long path 支持
- ❌ GUI 集成
