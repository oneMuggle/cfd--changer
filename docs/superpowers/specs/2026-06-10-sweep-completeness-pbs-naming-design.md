# sweep 完整性检查 + pbs 可选生成 + 任务名建议 — 设计文档

**日期**: 2026-06-10
**作者**: brainstorming with user
**状态**: 已批准,待实现
**目标版本**: inp-tool v0.9.0
**前置**: v0.8.2(wizard sweep 整目录模式必填)

---

## 1. 背景与目标

v0.8.0-v0.8.2 实现了 sweep **整算例目录模式**(`source_dir` + `CopyStrategy`),把基础算例完整复制到每个子算例。但仍有 3 个体验断链:

| 痛点 | 影响 |
|------|------|
| 基础算例不完整时,用户直到 `qsub` 才发现 | 浪费时间,可能 24h 后才发现网格缺 |
| 每个算例的 `run_*.pbs` 任务名是硬编码的(Marspathfinder-Ini),批量提交时队列/调度无法区分 | 100 case 全部同名,pbs 队列里无法追踪 |
| 用户必须手动复制并改 pbs | 工作流断在"复制"和"改任务名"两步 |

**目标版本 v0.9.0 解决这三件事**:

1. **完整性检查**:选中 source_dir 后,自动检查 `.inp` 必备 block(硬错)+ 网格/物性/pbs(软提示)
2. **pbs 可选生成**:wizard 多一步"是否生成 pbs?",默认 yes;按 sweep 参数自动重新填 `#PBS -N`
3. **任务名建议**:默认按变动的多值轴生成短名(如 `Marspath_a04_m0.60`),用户可输入模板覆盖

---

## 2. 非目标(YAGNI)

- ❌ LSF / Slurm / SGE 等其他调度器适配(仅 PBS)
- ❌ 跨算例 dedup(reflink / btrfs)
- ❌ pbs 模板的多 cluster 适配(只保留 #PBS -N 行替换)
- ❌ pbs 模板中的 `$VAR` 引用追踪和重写(只动 `#PBS -N`)
- ❌ mcfd.inp 之外的 `.inp` 文件(`npfopts.inp` / `pltopts.inp`)的修改
- ❌ wizard 步骤合并(本版本接受 7 步,wizard 步骤下限 3 步是软约束)

---

## 3. 涉及文件

| 文件 | 动作 | 估行数 |
|------|------|--------|
| `inp_tool/inp_tool/pbs.py` | 新建:`PbsConfig` / `PbsIssue` / `render_pbs_name` / `validate_base_case_dir` / `detect_pbs_template` / `write_pbs` | +180 |
| `inp_tool/inp_tool/sweep.py` | 加 `pbs: Optional[PbsConfig]` 字段;`generate()` 在 per_dir 模式末尾挂 pbs 写;`from_dict` 解析 `pbs:` | +30 / -0 |
| `inp_tool/inp_tool/wizard.py` | `step_1` 增强(完整性检查 + pbs auto-detect);新增 `step_5a_pbs`;`step_6_preview` 打印建议名 | +80 |
| `inp_tool/inp_tool/cli.py` | `--pbs` / `--no-pbs` / `--pbs-naming` flag;`from_dict` 路径 | +30 |
| `inp_tool/inp_tool/__init__.py` | 导出 `PbsConfig` / `PbsIssue` | +5 |
| `inp_tool/tests/test_pbs.py` | 新建:渲染/校验/检测/写盘 4 组测试 | +250 |
| `inp_tool/tests/test_sweep_pbs_integration.py` | 新建:generate + pbs 集成 | +120 |
| `inp_tool/tests/test_wizard_sweep_pbs.py` | 新建:wizard 7 步流程 | +150 |
| `docs/technical/04-sweep-architecture.md` | 加 §10 pbs 模块 | +80 |
| `docs/user-manual/18-wizard-tasks.md` | wizard 步骤更新 | +30 |
| `CHANGELOG.md` | v0.9.0 段 | +15 |

净代码 +350(含测试),文档 +125。

---

## 4. 架构

```
inp_tool/
├── pbs.py          ← 新建 (~180 行,零运行时依赖)
│   ├── PbsConfig          (dataclass)
│   ├── PbsIssue           (dataclass)
│   ├── detect_pbs_template()   (从 source_dir 找 run_*.pbs)
│   ├── validate_base_case_dir()  (返回 List[PbsIssue])
│   ├── render_pbs_name()   (默认短名 / 用户模板覆盖)
│   └── write_pbs()         (读模板 → 替换 #PBS -N → 写出)
├── sweep.py        ← +30 行挂载点
│   ├── CaseSweep.pbs: Optional[PbsConfig]  (新字段,默认 None)
│   ├── generate() 开头: validate_base_case_dir(),error 抛 SweepValidationError
│   ├── generate() per_dir 末尾: pbs.write_pbs(per_case_dir, params, cs.pbs)
│   └── from_dict: 解析 pbs: dict
├── wizard.py       ← +80 行
│   ├── step_1_source_dir: 末尾加 validate + detect_pbs
│   ├── step_5a_pbs (新): enabled + naming 模板 2 个问题
│   └── step_6_preview: 打印 pbs 任务名建议
└── cli.py          ← +30 行
    ├── --pbs/--no-pbs flag
    └── --pbs-naming flag
```

**核心约束**:
- `pbs.py` 零运行时依赖(纯 stdlib:`re` + `pathlib` + `fnmatch` + `dataclasses`)
- `sweep.py` 现有 11 字段零修改(新字段带默认值 `None`)
- `generate()` 在 `source_dir is None`(flat 模式)时**完全不调** pbs 模块

---

## 5. 数据模型

### 5.1 `PbsConfig`(pbs.py)

```python
@dataclass
class PbsConfig:
    enabled: bool = True                 # 总开关
    template: Optional[str] = None       # 源目录 pbs 路径,默认 auto-detect
    naming: str = ""                     # 任务名模板,空 = 自动短名
    naming_ext: str = ""                 # 不带 .pbs 扩展
    detect_basename: bool = True         # 是否从原 #PBS -N 提取 base 短名
    basename_max_len: int = 8            # base 短名最大字符数

    @classmethod
    def from_dict(cls, d: Dict) -> "PbsConfig": ...
```

### 5.2 `PbsIssue`(pbs.py)

```python
@dataclass
class PbsIssue:
    code: str           # "MISSING_MCFD_INP" / "MISSING_BLOCK:physics" /
                        # "MISSING_GRID:cellsin.bin" / "MISSING_PBS_TEMPLATE" / ...
    severity: str       # "error" / "warning" / "info"
    path: str           # 缺的文件 / block 路径
    message: str        # 人类可读
```

### 5.3 `CaseSweep` 扩展(sweep.py)

```python
@dataclass
class CaseSweep:
    # ... 现有 11 字段不变 ...
    pbs: Optional[PbsConfig] = None      # 新增,默认 None = 不生成
```

`from_dict` 支持:
```json
{
  "sweeps": {...},
  "pbs": {
    "template": "/path/to/source.pbs",
    "naming": "Mars-{alpha}-{mach}"
  }
}
```

---

## 6. 完整性检查规则(`validate_base_case_dir`)

| 检查 | 文件/位置 | 严重度 | 阻断? |
|------|----------|--------|-------|
| `mcfd.inp` 存在 | `source_dir/mcfd.inp` | error | 是 |
| `tsteps` block 存在 | `mcfd.inp` 内 | error | 是 |
| `physics` block 存在 | `mcfd.inp` 内 | error | 是 |
| `chemkin` block 存在 | `mcfd.inp` 内 | warning | 否 |
| `restart` block 存在 | `mcfd.inp` 内 | warning | 否 |
| `cellsin.bin` 存在 | `source_dir/` | warning | 否 |
| `cgrpsin.bin*` 存在(glob) | `source_dir/` | warning | 否 |
| `nodesin.bin` 存在 | `source_dir/` | warning | 否 |
| `*.dat` 物性文件 ≥ 1 | `source_dir/` | warning | 否 |
| `run_*.pbs` 存在 | `source_dir/` | warning(若 pbs 开启) | 否 |
| `mcfd.bc` 存在 | `source_dir/` | warning | 否 |
| `mcfd.grp` 存在 | `source_dir/` | warning | 否 |

**关键 block 列表**:
```python
REQUIRED_BLOCKS = ["tsteps", "physics"]
WARN_BLOCKS = ["chemkin", "restart"]
```

**返回**:`List[PbsIssue]`,调用方决定 error 是否 raise。

**block 检测方式**:`InpFile` 对象调用 `has_block(name)`,如不存在则返回 False(若 `InpFile` 无此方法,在 `model.py` 加一个 2 行的 `has_block` 工具方法)。

---

## 7. 任务名生成(`render_pbs_name`)

### 7.1 默认短名规则

```python
def render_pbs_name(
    params: Dict[str, float],
    multi_value_axes: List[str],          # 来自 sweep.sweeps 过滤多值轴
    base_basename: str,                   # 从原 #PBS -N 提取,截前 basename_max_len 字符
    user_template: str = "",              # 用户在 wizard 输的覆盖模板
    max_len: int = 15,                    # PBS 任务名上限
) -> str:
```

**逻辑优先级**:
1. `user_template` 非空 → `user_template.format(**params)`
2. 否则用默认:`{base_basename}_{axis1_short}_{axis2_short}...`
   - `axis_short` 格式:
     - `alpha=4` → `a04`
     - `alpha=4.5` → `a04.5`(整数部分补零到 2 位)
     - `beta=0` → `b00`
     - `mach=0.6` → `m0.60`
     - `mach=0.85` → `m0.85`(原样保留小数)
     - `T_inf=288.15` → `T288`(整数优先,小数点后 2 位;纯整数去小数)
   - 多值轴顺序:按 sweep.sweeps 的 key 顺序
   - 单值轴不进入

**示例**:
- `params = {alpha: 4, beta: 0, mach: 0.6}`
- `multi_value_axes = ["alpha", "mach"]`
- `base_basename = "Marspathfinder-Ini"[:8]` = `"Marspath"`
- 默认输出:`"Marspath_a04_m0.60"`(16 字符,触发截断 → `"Marspath_a04_m0.6"`(15 字符))

### 7.2 长度保护

```python
def _truncate(name: str, max_len: int = 15) -> str:
    """超 PBS 长度限制时截断(默认 15 字符),加 . 提示"""
    if len(name) > max_len:
        return name[:max_len - 1] + "."
    return name
```

### 7.3 字符兜底

```python
import re
def _sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)
```

### 7.4 wizard 展示

preview 阶段打印建议名(用户可改):
```
  pbs 任务名建议(可改): Marspath_a04_m0.60
  (原 #PBS -N: Marspathfinder-Ini,base 短名 "Marspath")
  [enter 接受 / 输入新名 / 输入模板如 Mars-{alpha}-{mach}]
```

---

## 8. 数据流(完整)

```
[1] user: wizard sweep
       ↓
[2] step_1_source_dir: 选 source_dir
       ↓ validate_base_case_dir(source_dir)
       ↓ (a) error 存在 → 打印 + 询问"仍要继续吗?" → yes 才往下
       ↓ (b) warning 存在 → 打印 + 自动继续
       ↓ detect_pbs_template(source_dir) → 找 run_*.pbs
       ↓ (没找到 + pbs 开启 → warning + PbsConfig(enabled=False) 兜底)
       ↓
[3] step_2_output: 输出目录 + manifest
       ↓
[4] step_3_mode / step_4_params: 模式 + 参数
       ↓
[5] step_5_naming: case 命名模板
       ↓
[5a] step_5a_pbs (新):
       ↓ 询问"是否生成 pbs?"(默认 yes,基于 PbsConfig.enabled)
       ↓ 询问"pbs 任务名"(默认建议,enter 接受 / 改 / 输模板)
       ↓
[6] step_6_preview: 预览 + 覆盖确认 + 执行
       ↓ generate(cs)
       ↓   ├─ 开头: validate → error 抛 SweepValidationError
       ↓   ├─ per_dir 模式,每个 case 复制完后:
       ↓   │  pbs.write_pbs(per_case_dir, params, cs.pbs)
       ↓   └─ 写 manifest 时记录每 case 的 pbs_name 字段
```

---

## 9. 错误处理

| 场景 | 行为 |
|------|------|
| 源目录缺 `mcfd.inp` | wizard 打印 + 回到 step_1(已有) |
| `mcfd.inp` 缺 `tsteps` block | 完整性检查返回 error,wizard 询问"仍要继续吗?",继续则 `generate()` 再次校验,失败 throw `SweepValidationError` |
| 源目录有 `run_*.pbs` 但模板没 `#PBS -N` | warning,用 `case_pbs` 作 fallback basename |
| 源目录无任何 pbs | 完整性检查 warning + `PbsConfig(enabled=False)` 自动关闭 |
| 用户输入 pbs 模板含未知 `{x}` 占位符 | `KeyError` 友好提示"参数 x 不在 sweep 中" |
| 生成 pbs 时目标文件已存在 | 覆盖(per_dir 模式源是 hardlink 来的,新算例不会冲突) |
| `--no-pbs` 显式关 | `PbsConfig(enabled=False)`,完全不触发 |
| pbs 任务名超 15 字符 | 截断 + warning |
| 源目录有多个 `run_*.pbs` | 取第一个 + warning "发现多个 pbs,使用 X" |
| pbs 任务名含特殊字符(非 [A-Za-z0-9_-]) | `_sanitize()` 替换 + info 提示 |

---

## 10. manifest 扩展

per_dir 模式 manifest 增 2 个字段(向下兼容):

```json
{
  "template": "reference/suanli/mcfd.inp",
  "layout": "per_dir",
  "pbs_enabled": true,
  "cases": [
    {
      "case_id": "case_aoa04_ma0.80",
      "path": "sweep_cases/case_aoa04_ma0.80",
      "files": ["mcfd.inp", "run_cfdpp.pbs", ...],
      "pbs_name": "Marspath_a04_m0.80",
      "params": {...},
      "applied": {...}
    }
  ]
}
```

**flat 模式 manifest 不变**(`pbs_enabled` 字段不写入)。

---

## 11. 测试计划(目标覆盖率 ≥ 80%)

### 11.1 `tests/test_pbs.py`(新,~250 行)

| 测试组 | 用例数 | 关键覆盖 |
|--------|--------|----------|
| `TestRenderPbsName` | 8 | 默认短名 / 用户模板 / 单值轴不进 / 多值轴全进 / 截断 / 无 base / 字符兜底 / 负值 |
| `TestValidateBaseCase` | 10 | mcfd.inp 缺 / tsteps 缺 / 软提示网格缺 / 软提示 pbs 缺 / 多 pbs 警告 / 全通过 / chemkin 软提示 / 空目录 |
| `TestDetectPbsTemplate` | 4 | 找 run_*.pbs / 无 pbs / 多个 pbs / 显式 template 覆盖 |
| `TestWritePbs` | 5 | 替换 #PBS -N / 保留其他 #PBS / 模板无 #PBS -N 走 fallback / 任务名截断 / 特殊字符 |
| `TestPbsConfigFromDict` | 3 | 完整 dict / 部分 dict / 空 dict |

### 11.2 `tests/test_sweep_pbs_integration.py`(新,~120 行)

- `generate()` + `PbsConfig` 集成:6-case sweep 跑通,每个 case 目录含正确任务名的 pbs
- `pbs.enabled=False` 时不写 pbs
- flat 模式(无 source_dir)时 `PbsConfig` 完全不触发
- manifest 包含每 case 的 `pbs_name` 字段
- 完整性 error 抛 `SweepValidationError`

### 11.3 `tests/test_wizard_sweep_pbs.py`(新,~150 行)

- wizard step_5a_pbs:默认 yes / 默认 no / 用户改模板 / 任务名截断
- 完整性检查集成到 step_1:error / warning 路径
- 多 pbs 时的 warning 提示
- 中英文双语

### 11.4 回归测试

- 现有 60+ sweep/wizard 测试零修改(只在 `CaseSweep` 加 `pbs=None` 默认值)
- `source_dir=None`(flat 模式)时 pbs 模块零调用

### 11.5 真实算例 smoke

- 用 `reference/suanli` 跑 4-case sweep,断言每个子目录的 `run_cfdpp.pbs` 的 `#PBS -N` 行正确

---

## 12. 兼容性 & 风险

### 兼容性

- `CaseSweep` 新字段默认 `None` → 现有 YAML/JSON config 零修改
- `from_dict` 不给 `pbs:` → `PbsConfig` 字段走默认(enabled=False,不写 pbs)
- `generate()` 在 `source_dir is None` 时跳过 pbs 块
- 所有 60+ 现有测试不动

### 风险

| 等级 | 风险 | 缓解 |
|------|------|------|
| HIGH | 不同 HPC 集群 pbs 模板差异大(LSF/Slurm/PBS Pro/Torque) | 仅替换 `#PBS -N` 行,其余保留;wizard 不强求模板必须存在;失败 warning 不阻断 |
| MEDIUM | base 短名截断可能产生不直观名字 | 预览阶段展示原名 + 建议名,用户可改 |
| MEDIUM | wizard 步骤从 6 → 7 步,违反"3-5 步"软约束 | step_5a_pbs 极简(2 个问题),整体仍是 7 步可接受 |
| LOW | `*.pbs` 文件名约定不一(`run_cfdpp.pbs` / `submit.pbs` / `job.pbs`) | glob `run_*.pbs` 默认;允许 `PbsConfig.template` 显式覆盖 |
| LOW | pbs 任务名中含特殊字符触发 PBS 报错 | `re.sub(r"[^A-Za-z0-9_-]", "_", name)` 兜底 |
| LOW | pbs.py 单测需要 mock InpFile(model.py 真实结构) | 用最小 fixture .inp 文件做集成测试,避免 mock 复杂度 |

---

## 13. 验收清单

- [ ] `pbs.py` 全部公共函数有 ≥ 80% 覆盖率
- [ ] wizard sweep 7 步全跑通(中文/英文)
- [ ] `reference/suanli` 真实跑 4-case sweep,每个子目录的 pbs 任务名正确
- [ ] 现有 60+ 测试零修改全绿
- [ ] CHANGELOG v0.9.0 段
- [ ] docs/technical/04-sweep-architecture.md 加 §10
- [ ] docs/user-manual/18-wizard-tasks.md 更新 wizard 步骤
- [ ] PR 走 feature 分支 → CI → merge

---

## 14. 不在本次范围

- ❌ LSF / Slurm 适配
- ❌ 跨算例 dedup
- ❌ pbs 模板多 cluster 适配
- ❌ `$VAR` 引用追踪重写
- ❌ 非 mcfd.inp 的 .inp 文件修改
- ❌ wizard 步骤合并
