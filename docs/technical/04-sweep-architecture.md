# 04 — 架构与数据模型

> **审计:** 2026-06-04 · 章节与 v0.4.0 同步 · 全部示例通过 · 全部链接有效
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

详见 [06-sweep-freestream.md](06-sweep-freestream.md)。

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

### 2.4 CaseResult / SweepReport

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
| `dry_run` 单独参数 | CI 验证用,无需占位文件 |
| 不用 `eval()` / `exec()` | 任何用户输入的 str 都不参与代码求值,安全 |
