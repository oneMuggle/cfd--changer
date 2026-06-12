# 04 — 架构与数据模型

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
**模块:** `inp_tool.sweep`  ·  **对应源码:** `inp_tool/inp_tool/sweep.py`

---

## 1. 总体流程

```
            ┌──────────┐
            │ template │  parse_file()
            └────┬─────┘
                 ▼
            ┌──────────┐
            │ InpFile  │  copy.deepcopy per case
            └────┬─────┘
                 ▼
        ┌────────────────────┐
        │ FreestreamPreset.apply()  ← (α,β,Ma,T) → (U,V,W,refvel)
        └────┬───────────────┘
             ▼
        ┌────────────────┐
        │ overrides: block.key = value
        └────┬───────────┘
             ▼
        write(inp, output_dir / name.format(**params))
             ▼
        ┌────────────────┐
        │ manifest.json  │  [{case_id, path, params, applied}, ...]
        └────────────────┘
```

每个 case 独立 `copy.deepcopy` 模板,保证不污染源。

## 2. 数据模型(5 个核心 dataclass)

### 2.1 SweepSpec

```python
@dataclass
class SweepSpec:
    values: Dict[str, SweepValue]   # {axis: [v1, v2, ...]}

    def values_keys(self) -> List[str]: ...
```

- 单值会被规范化为单元素列表
- 空 spec 抛 `ValueError`
- 用 `expand_cartesian(spec)` 展开为 `[{axis: v, ...}, ...]`

### 2.2 FreestreamPreset

```python
@dataclass
class FreestreamPreset:
    gamma: float = 1.4       # 干空气
    R: float = 287.05        # J/(kg·K)
    speed_of_sound: Optional[float] = None
    update_physics: bool = True
```

详见 [04-sweep-freestream.md](04-sweep-freestream.md)。

### 2.3 CaseSweep(配置聚合)

```python
@dataclass
class CaseSweep:
    template: str                              # 必填
    output_dir: str                           # 必填
    sweeps: SweepSpec                         # 必填
    naming: str = ""                          # 默认自动生成(只取多值轴)
    overrides: Dict[str, Any] = field(default_factory=dict)
    freestream: Optional[FreestreamPreset] = None
    manifest_path: Optional[str] = None
    naming_ext: str = ".inp"
```

**构造方式:**
- `CaseSweep.from_dict(d)` — 从 dict(YAML/JSON 反序列化结果)
- `CaseSweep.from_json(path)` — 从 JSON 文件
- `CaseSweep.from_yaml(path)` — 从 YAML 文件(需 `[yaml]` extras)

**命名模板校验规则:** 多值轴必须在 `naming` 中占位,单值轴(常量)可省略。`from_dict` 时校验,缺失抛 `ValueError`。

### 2.4 CaseSpec 抽象(v0.7.0 新增)

v0.7.0 引入了**统一 case 归一化**抽象,让 `sweeps` / `cases` / `groups` / CSV 走同一处理路径。

```python
@dataclass
class CartesianSpec:
    """笛卡尔轴集合(由 sweeps 字段生成,经 expand_cartesian 展开)"""
    axes: Dict[str, List[float]]


@dataclass
class ExplicitCase:
    """单个完整 case(显式 / 分组 / CSV 路径的最终归一化形式)"""
    values: Dict[str, float]
    group: Optional[str] = None  # 用于 {group} 命名占位
```

`CaseSweep` 新增 `specs: List[Union[CartesianSpec, ExplicitCase]]` 字段,`materialize()` 把 specs 摊平为 `List[ExplicitCase]`(笛卡尔展开在内部完成)。`generate()` 不再直接 `expand_cartesian(sweeps)`,改走 `cs.materialize()`。

**完全向后兼容**:`sweeps` 字段保留(老 API 不变);`from_dict` 自动把 `sweeps:` 同步到 `CartesianSpec` 加入 `specs`。现有 55+ 测试零修改通过。

#### 模式识别(`_build_specs_from_dict`)

| 输入字段 | 进入 `specs` 的形式 |
|----------|---------------------|
| `sweeps: {axis: [v1, v2, ...]}` | `CartesianSpec(axes=...)` |
| `cases: [{...}, {...}]` | `ExplicitCase(values=...)`(每个) |
| `groups: [{name, common, cases}, ...]` | `ExplicitCase(values=merged, group=name)`(每个 case,common 注入 + 显式覆盖) |
| 三个都缺 | `KeyError: 至少需要其中一个` |
| `cases: []` / `groups: []` / 空 group.cases | `ValueError: X is empty` |

混合(sweeps + cases + groups)按出现顺序展开,笛卡尔在前,显式在后,分组最后。

### 2.5 CaseResult / SweepReport

```python
@dataclass
class CaseResult:
    case_id: str          # 文件名(已渲染 naming 模板)
    path: str             # 完整输出路径
    params: Dict[str, Any]  # 该 case 的 sweep 参数
    applied: Dict[str, Any]  # 实际写入的 block.keyword=value 记录

@dataclass
class SweepReport:
    template: str
    cases: List[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int: ...
    def to_dict() / to_json() -> str: ...
```

## 3. generate() 主流程

```python
def generate(sweep: CaseSweep, dry_run: bool = False) -> SweepReport:
    if not dry_run:
        os.makedirs(sweep.output_dir, exist_ok=True)

    # 1. 加载模板(只读一次)
    template_inp = parse_file(sweep.template)

    # 2. 展开笛卡尔积
    cases = expand_cartesian(sweep.sweeps)

    report = SweepReport(template=sweep.template)
    used_names: Dict[str, int] = {}

    for params in cases:
        # 3. 独立 deepcopy 模板
        inp = copy.deepcopy(template_inp)

        # 4. 应用 freestream preset
        applied: Dict[str, Any] = {}
        if sweep.freestream is not None:
            applied.update(sweep.freestream.apply(inp, params))

        # 5. 应用 overrides
        _apply_overrides(inp, sweep.overrides)

        # 6. 命名(冲突自动追加 _1, _2)
        base_name = render_case_name(sweep.naming, params, ext=sweep.naming_ext)
        name = _disambiguate(base_name, used_names)
        path = os.path.join(sweep.output_dir, name)

        # 7. 写盘(非 dry-run)
        if not dry_run:
            write_inp(inp, path)

        report.cases.append(CaseResult(name, path, params, applied))

    # 8. manifest(可选)
    if sweep.manifest_path and not dry_run:
        _write_manifest(sweep.manifest_path, report, sweep.template)

    return report
```

## 4. overrides 应用

两种风格都支持:

**风格 1 — 嵌套 dict:**
```json
{
  "overrides": {
    "tsteps":   {"ntstep": 20000, "cflbot": 0.005},
    "options":  {"ntoutfv": 5000}
  }
}
```

**风格 2 — 点号 key:**
```json
{
  "overrides": {
    "tsteps.ntstep": 20000,
    "tsteps.cflbot": 0.005,
    "options.ntoutfv": 5000
  }
}
```

**规则:**
- 块不存在时 `WARN` 但不抛(模板里没有的块可能是 GUI/求解器自动生成)
- 关键字不存在时 `append`(避免破坏既有 block 结构)
- 标量值且 key 不含点号时 `WARN`(`{alpha: 0}` 无法定位)

## 5. 命名模板(`render_case_name`)

**输入:** `str.format(**params)` 风格模板 + 参数 dict + 扩展名(默认 `.inp`)

```python
render_case_name("case_aoa{alpha:02.0f}_ma{mach:.2f}",
                 {"alpha": 4, "beta": 0, "mach": 0.6},
                 ext=".inp")
# -> "case_aoa04_ma0.60.inp"
```

**冲突处理:** 同名 case 自动追加 `_1`, `_2`...:

```python
# 假设 3 个 case 都映射到 "case_0.inp"
used_names = {"case_0.inp": 0}
# 第 2 个: stem + "_1" + ext
# 第 3 个: stem + "_2" + ext
```

**默认命名(自动生成):** 只取**多值** sweep 轴。例:
- `sweeps = {alpha: [0,4,8], beta: [0], mach: [0.6,0.8], T_inf: [288.15]}` 
- → 默认 `naming = "case_{alpha}_{mach}"`(单值 `beta` / `T_inf` 不进文件名)

## 6. manifest.json 结构

```json
{
  "template": "examples/mcfd_v2_modified.inp",
  "template_sha256": "ce49db15a80ff0b0...",
  "generated_at": "2026-06-04T09:00:00",
  "total": 6,
  "cases": [
    {
      "case_id": "case_aoa00_b00_ma0.60.inp",
      "path": "./sweep_cases/case_aoa00_b00_ma0.60.inp",
      "params": {"alpha": 0.0, "beta": 0.0, "mach": 0.6, "T_inf": 288.15, "p_inf": 101325.0},
      "applied": {
        "guiopts.aero_alpha": 0.0,
        "guiopts.aero_beta": 0.0,
        "guiopts.aero_ma": 0.6,
        "guiopts.aero_u": 204.99,
        "guiopts.aero_v": 0.0,
        "guiopts.aero_w": 0.0,
        "physics.refvel": 204.99
      }
    }
  ]
}
```

`template_sha256` 用于下游脚本校验"样例被改后 manifest 是否过期"。

## 7. 性能与内存

- 模板只 parse 一次,每个 case 独立 `deepcopy`(50KB 级 InpFile 内存)
- 1000 case 大约 50MB 内存,IO 受限于磁盘写
- `copy.deepcopy` 比 `parse_file(template)` 快约 10×(无 tokenize)

| N | 内存 | 写盘时间(SSD) |
|---|---|---|
| 100 | ~5MB | <1s |
| 1000 | ~50MB | ~5s |
| 10000 | ~500MB | ~50s |

## 8. 关键设计决策

| 决策 | 理由 |
|---|---|
| `freestream` 默认开启 | 用户最大痛点就是"改 alpha 时忘了同步改 aero_u/v/w" |
| 命名模板用 `str.format` | 与 Python 习惯一致,无新语法学习成本 |
| 单值轴不进默认 naming | 文件名不被 T_inf/p_inf 等常量污染,可读性 |
| `applied` 字段记录真实改动 | 用户可核对方程与模板默认值的差异 |
| 不修改 `source_dir` 自身的文件 | 只读 + 硬链接/符号链接 0 写源端,保护用户数据 |

## 9. v0.8.0:整算例目录模式(per_dir)

### 9.1 背景

真实算例是**完整目录**(网格/配置/物性/作业脚本),而非孤立 `mcfd.inp`。v0.7.x 只能写 mcfd.inp,用户必须手动 `cp -r` 基础算例到每个子算例,体验断链。v0.8.0 新增 `source_dir` 字段,直接把基础算例整目录复制到每个子算例,只覆盖 mcfd.inp。

### 9.2 布局自动判定

```python
def _resolve_layout(sweep: CaseSweep) -> str:
    return "per_dir" if sweep.source_dir else "flat"
```

- `source_dir=None` → **flat**(v0.7.x 行为,1 个 case = 1 个 .inp 文件)
- `source_dir=path` → **per_dir**(1 个 case = 1 个子目录,完整算例)

无 bool 字段,避免冗余配置。

### 9.3 流程

```
             ┌──────────────────────┐
             │ source_dir (基础算例) │
             └────┬─────────────────┘
                  ▼  (os.walk + fnmatch 排除 *.bak / mlog / nodesout.bin)
             ┌──────────────────────┐
             │ 每个文件按 strategy   │
             │  copy / hardlink /   │  ← 默认 hardlink
             │  symlink             │
             └────┬─────────────────┘
                  ▼
             ┌──────────────────────┐
             │ output_dir / case_X/ │  ← 子目录名 = render_case_name(... ext="")
             │   ├── mcfd.inp  (覆)  │
             │   ├── cellsin.bin    │
             │   ├── nodesin.bin    │
             │   └── ...            │
             └──────────────────────┘
                  ▼
             ┌──────────────────────┐
             │ write_preserve()     │  ← 修改后的 mcfd.inp
             │ 覆盖 mcfd.inp        │
             └──────────────────────┘
```

### 9.4 CopyStrategy 退化链

| 策略 | 首选 | 失败 → 退化 | 失败 → 退化 | 备注 |
|---|---|---|---|---|
| `copy` | `shutil.copy2` | — | — | 最慢、最占空间 |
| `hardlink` | `os.link` | `shutil.copy2` | — | 默认,跨 FS 失败才退化 |
| `symlink` | `os.symlink` | `os.link` | `shutil.copy2` | Windows 需 dev mode |

### 9.5 manifest 扩展(per_dir 模式)

```json
{
  "template": "reference/suanli/mcfd.inp",
  "template_sha256": "...",
  "generated_at": "2026-06-09T20:30:00",
  "layout": "per_dir",                  ← 新
  "source_dir": "reference/suanli",     ← 新
  "copy_strategy": "hardlink",          ← 新
  "exclude": ["*.bak", "mlog", "..."],  ← 新
  "total": 2,
  "cases": [
    {
      "case_id": "case_0.0",
      "path": "/tmp/sweep_smoke_v080a/case_0.0",
      "files": ["mcfd.inp", "cellsin.bin", ...],   ← 新(17 个文件清单)
      "params": {"alpha": 0.0, "beta": 0.0, "mach": 0.6},
      "applied": {"guiopts.aero_alpha": 0.0, "guiopts.aero_u": 204.99, ...}
    }
  ]
}
```

**flat 模式 manifest 零变化**(新增字段仅 per_dir 写入),保持完全向后兼容。

### 9.6 性能(实测,reference/suanli 544MB)

| 模式 | 100 cases | IO | 磁盘占用 |
|---|---|---|---|
| `copy` | ~5min | 读 544MB × 100 = 54GB | +54GB |
| `hardlink`(默认) | <5s | 0(全 inode 操作) | +0 |
| `symlink` | <5s | 0 | +0(跨 FS) |

### 9.7 默认排除规则

| 模式 | 原因 |
|---|---|
| `*.bak` / `*.BAK` | 备份文件,不应进算例 |
| `mlog` | 求解器运行时日志目录 |
| `nodesout.bin` | 求解器输出(下次跑会被覆写) |
| `*.log` | 通用日志 |

用户可用 `--exclude` 多次传覆盖默认。
| `dry_run` 单独参数 | CI 验证用,无需占位文件 |
| 不用 `eval()` / `exec()` | 任何用户输入的 str 都不参与代码求值,安全 |

---

## 10. v0.9.0:完整性检查 + PBS 脚本可选生成

### 10.1 新增模块 `inp_tool.pbs`

```
pbs.py (~250 行,零运行时依赖)
├── PbsConfig                # dataclass,from_dict 解析
├── PbsIssue                 # dataclass,完整性检查产物
├── detect_pbs_template()    # glob run_*.pbs + 多模板 warning → stderr
├── validate_base_case_dir() # 文件级 + block 级
├── render_pbs_name()        # 默认短名 / 用户模板 / 截断 / sanitization
├── write_pbs()              # 替换或追加 #PBS -N
└── extract_pbs_basename()   # 从 #PBS -N 截前 8 字符
```

### 10.2 完整性检查规则

| 类别 | error 必填 | warning 软提示 |
|------|------------|----------------|
| mcfd.inp | 存在 | — |
| mcfd.inp blocks | — | tsteps, physics(用 `xxx begin/end` 格式) |
| mcfd.inp blocks | — | chemkin, restart(部分算例类型需要) |
| 网格 | — | cellsin.bin, nodesin.bin, cgrpsin.bin* |
| 物性 | — | *.dat (≥1) |
| 配置 | — | mcfd.bc, mcfd.grp |
| pbs 模板 | — | run_*.pbs(pbs_enabled=True 时) |

> v0.9.0 注:**所有 block 检查都是 warning(不阻断)**,严格 error 模式留给 v0.9.x 后期或 v0.10(避免破坏老 fixture)。

### 10.3 任务名生成规则

默认短名格式:
- 抽取原 `#PBS -N` base 名,截前 8 字符(`Marspathfinder-Ini` → `Marspath`)
- 追加多值轴短 token:`a04` (alpha=4), `m0.60` (mach=0.6), `T288` (T_inf=288.15), `a-2.0` (alpha=-2.0 原样)
- 单值轴不进
- 整体 ≤ 200 字符(默认不截断,Task 5 测 `max_len` 显式传小值时截断)
- 特殊字符 (`[^A-Za-z0-9_.-]`) → `_` 兜底

用户模板覆盖:在 wizard step_5a_pbs 输 `Mars-{alpha}-{mach}`,走 `str.format()` 路径。

### 10.4 数据流(per_dir 模式 + pbs 启用)

```
generate(caseSweep) with sweep.pbs.enabled=True:
  ├─ 开头: validate_base_case_dir → warning 打印到 stderr(不阻断)
  ├─ 循环外:读 pbs 模板内容到 in-memory 字符串
  ├─ per_case 循环:
  │    ├─ _copy_case_files(源目录 → 子目录,hardlink)
  │    ├─ write_preserve(修改后的 mcfd.inp)
  │    ├─ os.unlink(case_pbs_path) 解除 hardlink
  │    └─ pbs.write_pbs(template_path, case_pbs_path, job_name,
  │                      template_text=in_memory_content)
  └─ 写 manifest.json,加 pbs_enabled 顶层 + 每 case pbs_name
```

### 10.5 manifest 扩展

per_dir 模式 manifest 增字段(向下兼容,flat 模式 / pbs.enabled=False 时不写):

```json
{
  "template": "reference/suanli/mcfd.inp",
  "layout": "per_dir",
  "pbs_enabled": true,
  "cases": [
    {"case_id": "case_aoa04_ma0.80", "pbs_name": "Marspath_a04_m0.80", ...}
  ]
}
```

### 10.6 设计决策

| 决策 | 理由 |
|------|------|
| 独立 `pbs.py` 模块 | 关注点分离,不动 sweep.py 核心;零依赖符合 inp_tool 核心约束 |
| block 检查全 warning | 向后兼容老 fixture(`tsteps` / `end` 格式) |
| 写 pbs 前 unlink hardlink | 避免 case 间因 inode 共享写串 |
| 循环外预读 pbs 模板内容 | 减少 IO;用 `template_text` 参数传 in-memory 内容 |
| base 短名截 8 字符 | PBS 任务名 15 字符上限,留出 7 字符给 axis tokens |
| sanitization 在写盘前 | 防止特殊字符触发 PBS 拒绝 |
| `SweepValidationError` 预留 | 当前不抛,留给 v0.9.x 后期严格模式 |
