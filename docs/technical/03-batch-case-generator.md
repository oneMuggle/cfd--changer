# 03 — 批量算例生成器 (sweep)

**模块:** `inp_tool.sweep`  ·  **版本:** v0.4.0  ·  **状态:** 已完成

---

## 1. 背景

CFD++ `mcfd.inp` 的批量参数研究(攻角/侧滑角/马赫扫描)历来靠手工复制 + 文本编辑器改值,易错且不可追溯。`inp_tool` v0.3 已提供 parser/writer/diff 三件套,v0.4 在其上叠加一层**声明式批量生成器**。

## 2. 目标

- 单一样例 → N 个变体(笛卡尔积展开)
- 高层 preset:`(alpha, beta, mach, T)` → `(U, V, W) + refvel` 自动几何分解
- 三种入口:Python API / CLI / FastAPI
- 输出一份 `manifest.json` 索引所有 case 的关键参数,便于后续调度/分析
- 80% 测试覆盖率,无新增运行时依赖

## 3. 架构

```
            ┌──────────┐
            │ template │  parse_file()
            └────┬─────┘
                 ▼
            ┌──────────┐
            │ InpFile  │  copy.deepcopy per case
            └────┬─────┘
                 ▼
        ┌────────────────┐
        │ FreestreamPreset.apply()   ← (alpha,beta,mach,T) → (U,V,W,refvel)
        └────┬───────────┘
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

## 4. 公开 API

```python
from inp_tool import (
    CaseSweep,        # 配置聚合
    FreestreamPreset, # 高层 preset
    generate,         # 主入口
    SweepSpec,        # 扫描定义
    expand_cartesian, # 笛卡尔积展开
    render_case_name, # 命名模板
    CaseResult,       # 单个 case 结果
    SweepReport,      # 整批报告
)
```

## 5. 数据模型

### SweepSpec

```python
@dataclass
class SweepSpec:
    values: Dict[str, SweepValue]   # {axis: [v1, v2, ...]}

    def values_keys(self) -> List[str]: ...
```

- 单值会被规范化为单元素列表
- 空 spec 抛 `ValueError`

### FreestreamPreset

```python
@dataclass
class FreestreamPreset:
    gamma: float = 1.4
    R: float = 287.05
    speed_of_sound: Optional[float] = None
    update_physics: bool = True
```

- 默认 `gamma=1.4, R=287.05`(干空气)
- 给出 `speed_of_sound` 时跳过 `sqrt(gamma·R·T)` 计算
- `update_physics=False` 时只更新 `guiopts`,不动 `physics.refvel/reftem/refpre`

**公式:**

```
a = sqrt(gamma · R · T_inf)
U = Ma · a · cos(α) · cos(β)
V = Ma · a · sin(β)
W = Ma · a · sin(α) · cos(β)
refvel = sqrt(U² + V² + W²) = Ma · a
```

**更新字段:**

| 字段 | 写入 |
|---|---|
| `guiopts.aero_alpha/beta/ma` | sweep 值 |
| `guiopts.aero_u/v/w` | preset 分解 |
| `guiopts.aero_temp/pres` | sweep 或原值 |
| `physics.refvel` | preset 总速 |
| `physics.reftem/refpre` | sweep |

### CaseSweep

```python
@dataclass
class CaseSweep:
    template: str
    output_dir: str
    sweeps: SweepSpec
    naming: str = ""                 # 自动生成默认
    overrides: Dict[str, Any] = {}    # 两种风格都支持
    freestream: Optional[FreestreamPreset] = None
    manifest_path: Optional[str] = None
    naming_ext: str = ".inp"
```

**命名模板校验:** 多值轴必须在 `naming` 中占位;单值轴(如常量 `T_inf`)可省略。

### generate()

```python
def generate(sweep: CaseSweep, dry_run: bool = False) -> SweepReport:
```

流程:
1. `parse_file(template)` 一次
2. `expand_cartesian(sweeps)` 得到 N 个 params dict
3. 每个 params: `copy.deepcopy(template)` → preset → overrides → 命名 → 写盘
4. 累积 CaseResult;若有 manifest_path 写一份 JSON
5. 返回 SweepReport

## 6. CLI

```bash
inp-tool sweep <template.inp> [sweep.json] [options]
```

- 单参数 + `.json` 后缀 → 直接按 config 模式
- 双参数 → template + config
- 快捷参数: `--alpha 0,4,8  --beta -2,0,2  --mach 0.6,0.8  --t-inf 288.15  --p-inf 101325`
- `--out DIR` `--manifest PATH` `--dry-run` `--verbose`

## 7. FastAPI

`POST /api/sweep` 请求体 = JSON config;响应 = `SweepResponse(total, cases[], template, dry_run, manifest_path)`。

## 8. 配置文件示例

参考 `inp_tool/examples/sweep_demo.json`:

```json
{
  "template": "examples/mcfd_v2_modified.inp",
  "output_dir": "examples/sweep_cases",
  "sweeps": {
    "alpha": [0.0, 4.0, 8.0],
    "beta":  [0.0],
    "mach":  [0.60, 0.80],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  },
  "naming": "case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}.inp",
  "manifest": {"path": "examples/sweep_cases/manifest.json"},
  "freestream": {"enabled": true, "gamma": 1.4, "R": 287.05}
}
```

## 9. 测试

| 文件 | 覆盖范围 | 用例数 |
|---|---|---|
| `tests/test_sweep.py` | SweepSpec / FreestreamPreset / 命名模板 / 数据结构 | 22 |
| `tests/test_sweep_generate.py` | CaseSweep 配置 / generate() 主流程 | 18 |
| `tests/test_sweep_cli.py` | `inp-tool sweep` 子命令 | 8 |
| `tests/test_sweep_api.py` | `POST /api/sweep` 端点 | 6 |
| **合计** | sweep 模块行覆盖率 **94%** | **54** |

## 10. 风险与限制

| 风险 | 缓解 |
|---|---|
| 几何分解的方向与 CFD++ 内部定义可能不一致 | `freestream.enabled=false` 跳过 preset,只用 overrides 手动改 `aero_u/v/w`;manifest 记录 `applied` 字段供用户核对 |
| 大批量(10k+)写盘慢 | 进度条(可选 `tqdm`);manifest 单独一次性写 |
| round-trip 后空白重构造(v0.2 已知) | 已是 inp_tool 全局限制,sweep 不可解;diff 文档中说明 |
| 命名模板字段名拼错 | 解析时校验,清晰报错 |
| 样例无 `guiopts` / `physics` 块 | preset 缺块时 warn 但不抛,继续用其它块 |

## 11. 后续工作

- v0.5: YAML 配置支持(`pyyaml` extras)
- v0.6: 进度条 / 流式生成 / 任务取消
- v0.7: 与 CFD++ 求解器集成(批量提交作业)
