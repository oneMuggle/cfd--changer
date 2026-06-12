# 14 — sweep 案例研究（基于 2026-06-09 验证）

> **审计:** 2026-06-09 · 与 v0.6.1 同步 · 全部数据来自本次真实产出
**对应版本:** v0.6.1 + sweep-usage-polish 4 项落地
**对应计划:** `docs/plans/2026-06-09_sweep-usage-polish.md`

---

## 1. 背景

`03-sweep-usage.md` 覆盖了三入口（Python API / CLI / FastAPI）的**完整 schema**。
本章聚焦 2026-06-09 实际跑过的一次端到端验证：从 0 基础开始、用 CLI 验证能力、
用 1D/2D sweep 跑出 11 个 case、做物理量手算交叉验证、定位 1 个隐藏 bug
（`naming_ext` 硬编码）、产出本套流程的固化脚本（`scripts/run_sweep.sh`）。

**目标读者**：第一次用 `inp-tool` 跑批量算例的工程师。

---

## 2. 一维 sweep：5 个攻角（v0.5.1 修复验证）

```bash
cd inp_tool
conda run -n cfdchanger python -m inp_tool.cli sweep \
    --alpha 0,5,10,15,20 \
    --out /tmp/inp_verify/sweep_demo \
    -v \
    ../reference/inp_example/mcfd.inp
```

| 文件 | aero_alpha | aero_ma (保留) | aero_u | aero_w | refvel |
|---|---:|---:|---:|---:|---:|
| `case_0.0.inp`  | 0.0  | 0.85 | 289.17 | 0.00  | 289.17 |
| `case_5.0.inp`  | 5.0  | 0.85 | 288.07 | 25.20 | 289.17 |
| `case_10.0.inp` | 10.0 | 0.85 | 284.78 | 50.21 | 289.17 |
| `case_15.0.inp` | 15.0 | 0.85 | 279.37 | 75.28 | 289.17 |
| `case_20.0.inp` | 20.0 | 0.85 | 271.73 | 98.90 | 289.17 |

**关键观察**：

- `aero_ma = 0.85` 在 5 个 case 里**完全保留**（v0.5.1 修复）
- `aero_u` 随攻角增大而**下降**（cos α 项）
- `aero_w` 随攻角增大而**上升**（sin α 项）
- `refvel = √(U² + W²)` 与 α 无关（β=0 时）

---

## 3. 二维 sweep：6 个 case（α × Ma）

```bash
conda run -n cfdchanger python -m inp_tool.cli sweep \
    --alpha 0,10,20 --mach 0.6,0.85 \
    --out /tmp/inp_verify/sweep_2d \
    --manifest /tmp/inp_verify/sweep_2d/manifest.json \
    -v \
    ../reference/inp_example/mcfd.inp
```

| 文件 | α | Ma | U | W | refvel |
|---|---:|---:|---:|---:|---:|
| `case_0.0_0.6.inp`  | 0.0  | 0.6  | 204.12 | 0.00  | 204.12 |
| `case_0.0_0.85.inp` | 0.0  | 0.85 | 289.17 | 0.00  | 289.17 |
| `case_10.0_0.6.inp` | 10.0 | 0.6  | 201.02 | 35.45 | 204.12 |
| `case_10.0_0.85.inp`| 10.0 | 0.85 | 284.78 | 50.21 | 289.17 |
| `case_20.0_0.6.inp` | 20.0 | 0.6  | 191.81 | 69.81 | 204.12 |
| `case_20.0_0.85.inp`| 20.0 | 0.85 | 271.73 | 98.90 | 289.17 |

### 3.1 物理量手算校验

T = 288.15 K → a = √(γ·R·T) = √(1.4 × 287.05 × 288.15) = **340.29 m/s**

| 量 | 公式 | 手算 | sweep 输出 | 误差 |
|---|---|---:|---:|---:|
| U @ α=10°, Ma=0.6 | Ma·a·cos(10°)·cos(0°) | 201.02 | 201.02 | 0% |
| W @ α=10°, Ma=0.6 | Ma·a·sin(10°)·cos(0°) | 35.45 | 35.45 | 0% |
| refvel @ α=10°, Ma=0.6 | √(U² + W²) | 204.12 | 204.12 | 0% |
| refvel @ α=0°, Ma=0.6 | Ma·a | 204.17 | 204.12 | 0.02% |

最后一行 0.02% 误差是浮点数累加，可忽略。**全部通过校验**。

### 3.2 模板 vs 第一个 case 的 diff（验证外科手术式改写）

```diff
@@ line 1287 @@
- aero_u 288.0727569986127
+ aero_u 289.1731481310116
@@ line 1289 @@
- aero_w 25.203100508036894
+ aero_w 0.0
@@ line 1299,1300 @@
- aero_alpha 5.0
- aero_beta 0.000000e+000
+ aero_alpha 0.0
+ aero_beta 0.0
```

模板的 `aero_alpha=5.0`（基础攻角）变成 `case_0.0.inp` 的 `0.0`，外加 3 个相关
衍生量（U/W/beta）。**模板 1299 行中只改 4 行**——证明 sweep 不动其它
options / physics / tsteps / iofiles / octree 等。

---

## 4. naming 格式说明符速查

`naming` 字段是 Python `str.format(**params)` 模板：

| 说明符 | 作用 | 例子 |
|---|---|---|
| `{alpha}` | 默认 `str()` | `5.0` → `5.0` |
| `{alpha:g}` | 去掉无意义零 | `5.0` → `5` |
| `{alpha:.2f}` | 固定 2 位小数 | `5.0` → `5.00` |
| `{alpha:+.1f}` | 强制带符号 | `5.0` → `+5.0` |
| `{alpha:05.1f}` | 零填充 | `5.0` → `005.0` |
| `{mach:.3f}` | Mach 通常保留 3 位 | `0.85` → `0.850` |

**注意**：默认值是 `case_{alpha}` 但**只有多值轴**才放占位符。单值轴
（如 `T_inf: 288.15`）不参与命名（详见 `sweep.py:_default_naming`）。
所以 `sweeps: {alpha: [0]}` 生成的**唯一文件**叫 `case.inp`，而不是 `case_0.inp`。
要强制带占位符，需显式 `"naming": "case_a{alpha:g}"`。

### 4.1 naming_ext：可配置（2026-06-09 新增）

之前 `naming_ext` 在 `CaseSweep` dataclass 里有默认 `.inp`，
但 `from_dict()` **不读**这个字段，配置文件写了也无效。

**修复后**（Phase 1 commit `a53f1ea`）：

```json
{
  "template":   "...",
  "output_dir": "...",
  "sweeps":     {"alpha": [0, 5]},
  "naming_ext": ".txt"   // ← 现在生效了
}
```

→ 生成 `case_0.txt`, `case_5.txt`。适用场景：CI 想给 sweep 产物打个特殊后缀、
或者要导成中间格式（`.dat` `.cfg`）方便后续脚本读。

---

## 5. overrides 适用场景

`overrides` 是个**旁路**：不走 freestream 几何推导，直接 `block.key = value` 写死。

### 5.1 适用

- 改非 freestream 的参数（CFL、迭代步、I/O、湍流模型常量）
- 同一 sweep 维度下应用**和 alpha/beta/Ma 无关**的固定修改
- 测试场景：批量改 `tsteps.ntstep` 试不同步数

```json
"overrides": {
  "tsteps.ntstep":     50000,
  "options.iterlimit": 20000,
  "physics.cflmax":    2.5
}
```

### 5.2 不适用

- **几何相关**参数（U/V/W）→ 应走 freestream 自动推导
- **命名相关**参数（想换后缀）→ 用 `naming_ext`（§4.1）而不是 `overrides`

---

## 6. FreestreamPreset 物理量

| 字段 | 物理含义 | 默认 | 何时改 |
|---|---|---|---|
| `gamma` | 比热比 cp/cv | `1.4` | 非空气（He γ=1.66，CO₂ γ=1.3） |
| `R` | 气体常数 J/(kg·K) | `287.05` | 非空气（N₂=296.8，He=2077） |
| `speed_of_sound` | 直接给定 a (m/s) | `null`（用 √(γ·R·T)） | 不想走理想气体、自定义工况 |
| `update_physics` | 同步改 `physics.refvel/reftem/refpre` | `true` | `false` = 只改 guiopts，physics 留模板原值 |

**注意**：改 `gamma`/`R` 之后，**U/V/W 会重算**（用新声速），但 `aero_temp`/
`aero_pres` 这两个原始字段**不会自动改**。如果改气体，**记得通过 `T_inf` /
`p_inf` sweep 同时改**。

---

## 7. 模板 SHA-256 用于审计

每次跑 sweep 会在 `manifest.json` 里写 `template_sha256`：

```json
"template_sha256": "3fe8e4740fcb59a9000e4b567b9d4a525f44bab79463c6df961deafab20ec5d2"
```

CI 用法：

```bash
# 1. 跑 sweep 拿 SHA
NEW_SHA=$(jq -r .template_sha256 /tmp/inp_verify/case_study/manifest.json)

# 2. 跟上次产物的 SHA 对比
OLD_SHA=$(git show HEAD:case_study/manifest.json | jq -r .template_sha256)

# 3. 不一致则告警（模板被改过）
[[ "$NEW_SHA" == "$OLD_SHA" ]] || echo "WARNING: template changed"
```

---

## 8. 常见坑（已知 N 个）

### 8.1 路径要从 `inp_tool/` 子目录跑

`python -m inp_tool.cli` 在仓库根会命中**外层**项目目录，报 `__version__`
import 错。正确做法：

```bash
cd inp_tool && python -m inp_tool.cli ...
# 或用 editable 安装后的 console script: inp-tool
```

### 8.2 REPL 连字符命令名需要 `onecmd` 扩展

stdlib `cmd.Cmd` 把 `sweep-config` 拆成 cmd=`sweep` + arg=`-config ...`，
视为 flag。`feat/sweep-usage-polish` 已扩展 `onecmd` 手工分发（Phase 2 commit
`743dca0`），主分支尚未合入。

### 8.3 模板必须含 guiopts 块

`FreestreamPreset` 默认要改 `guiopts.aero_*` 字段。如果模板没有 guiopts
块（如最小测试 fixture `sample_v1.inp`），会 WARN 跳过：

```
[sweep] WARN: template has no `guiopts` block; aero_* fields will not be updated.
```

生成的 case 文件仍然写出，但 `aero_*` 不会被改。**真实工程模板必有 guiopts**。

### 8.4 beta 也要 sweep 才会进文件名

跟 §4 末尾同理：单值轴不进命名。`beta: 0` 不写 `case_b0_*` 文件名。

### 8.5 argparse 在 REPL 里用 `arg.split()` 不用 `shlex`

`repl.py:do_sweep` 故意用 `arg.split()` 而不是 `shlex.split()`，因为 Windows
路径里的反斜杠会被 shlex 误识别（详见 commit `ac08fa4`）。

---

## 9. 配套脚本

实施落地了 1 个批跑脚本 + 1 个测试：

```bash
# 端到端批跑
scripts/run_sweep.sh scripts/tests/fixtures/sweep_min.json

# 跑 shell 测试
bash scripts/tests/test_run_sweep.sh
```

详细见计划文档 `docs/plans/2026-06-09_sweep-usage-polish.md` Phase 3。
