# 04 — 扫描参数

> **审计:** 2026-06-04 · 章节与 v0.4.0 同步 · 全部示例通过 · 全部链接有效
## 1. 什么是"扫描"

`inp_tool` 接受**多个**扫描轴,每个轴有一组值。它会把所有轴**笛卡尔积**展开成 N 个 case:

```
2 个 alpha × 3 个 mach = 6 个 case
3 个 alpha × 2 个 mach × 2 个 altid = 12 个 case
```

## 2. 哪些字段可以扫

任何 `guiopts` 块里以 `aero_` 开头的字段,以及 `physics` 块里以 `ref` 开头的字段:

| 字段 | 含义 | 单位 | 常用范围 |
|---|---|---|---|
| `aero_alpha` | 攻角 | 度 | -10 ~ 20 |
| `aero_beta` | 侧滑角 | 度 | -10 ~ 10 |
| `aero_ma` | 马赫数 | — | 0 ~ 5 |
| `aero_u` | X 速度 | m/s | 0 ~ 1000 |
| `aero_v` | Y 速度 | m/s | -100 ~ 100 |
| `aero_w` | Z 速度 | m/s | -100 ~ 100 |
| `aero_temp` | 来流温度 | K | 200 ~ 320 |
| `aero_pres` | 来流压强 | Pa | 1000 ~ 1000000 |
| `aero_re` | 来流雷诺数 | — | 1e4 ~ 1e8 |
| `aero_altid` | 高度/湍流强度 | — | 0 ~ 20000 |

加上 `physics.refvel` / `reftem` / `refpre` 等参考量。

## 3. 怎么写配置

```yaml
sweeps:
  alpha: [0, 4, 8]            # 3 个值 → 扫描
  mach:  [0.6, 0.8]           # 2 个值
  T_inf: [288.15]             # 1 个值(辅助参数,不进文件名)
```

### 3.1 多值 vs 单值

- **多值** = `[a, b, c]` — 真的扫描,会展开成多个 case
- **单值** = `[288.15]` 或 `288.15` — 辅助常量,所有 case 都用这个值

判断标准:**进文件名的字段必须多值**(否则文件名区分不了 case)。

### 3.2 写法技巧

**写法 1:逗号分隔字符串(CLI 快捷)**

```bash
inp-tool sweep tpl.inp --alpha 0,2,4,6,8 --beta -4,0,4 --mach 0.6,0.8
```

**写法 2:列表(配置文件)**

```json
{"sweeps": {"alpha": [0, 2, 4, 6, 8], "beta": [-4, 0, 4], "mach": [0.6, 0.8]}}
```

**写法 3:范围(需要先用 Python 展开)**

CLI 不直接支持 `0..10 step 2`,需要先在 Python 里展开:

```python
import json
spec = {"sweeps": {"alpha": list(range(0, 11, 2))}}  # 0,2,4,6,8,10
with open("sweep.json", "w") as f:
    json.dump(spec, f)
```

## 4. 笛卡尔积展开示例

输入:

```yaml
sweeps:
  alpha: [0, 5]        # 2 个
  beta:  [-3, 0, 3]    # 3 个
  mach:  [0.6, 0.8]    # 2 个
```

展开:**2 × 3 × 2 = 12 个 case**

| # | alpha | beta | mach | 输出文件名(示例) |
|---|---|---|---|---|
| 1 | 0 | -3 | 0.6 | case_a00_b-03_m0.60.inp |
| 2 | 0 | -3 | 0.8 | case_a00_b-03_m0.80.inp |
| 3 | 0 | 0 | 0.6 | case_a00_b00_m0.60.inp |
| 4 | 0 | 0 | 0.8 | case_a00_b00_m0.80.inp |
| 5 | 0 | 3 | 0.6 | case_a00_b03_m0.60.inp |
| 6 | 0 | 3 | 0.8 | case_a00_b03_m0.80.inp |
| 7 | 5 | -3 | 0.6 | case_a05_b-03_m0.60.inp |
| ... | ... | ... | ... | ... |

## 5. 来流参数(`T_inf`, `p_inf`)

`T_inf` 和 `p_inf` **不是** `guiopts` 块里的字段。它们是 `inp_tool` 内部用的"辅助参数",会被自动转成 `guiopts.aero_temp` / `aero_pres` 和 `physics.reftem` / `refpre`。

```yaml
sweeps:
  T_inf: [288.15]   # 自动写进 guiopts.aero_temp 和 physics.reftem
  p_inf: [101325.0] # 自动写进 guiopts.aero_pres 和 physics.refpre
```

> 如果你的样例里这些字段位置不一样,见 [07-字段覆盖](07-overrides.md) 手动指定。

## 6. 速度分量的自动计算(几何分解)

`inp_tool` 内置一个"来流 preset":给定 `(alpha, beta, mach, T)`,自动算 `(U, V, W)` 和总速 `refvel`:

```
a = √(γ · R · T)        # 声速
U = Ma · a · cos(α) · cos(β)
V = Ma · a · sin(β)     # 侧滑
W = Ma · a · sin(α) · cos(β)   # 垂直(法向)
```

> ⚠️ **方向假设:** 默认 `α` 影响垂直(W),`β` 影响侧滑(V)。如果你的 CFD++ 版本不是这个约定,看 [07-字段覆盖 §关闭 preset](07-overrides.md) 手动给 `aero_u/v/w`。

### 关闭 preset(纯手动模式)

```yaml
sweeps:
  alpha: [0, 5, 10]
freestream:
  enabled: false
overrides:
  guiopts:
    aero_u: 250.0
    aero_v: 0.0
    aero_w: 0.0
```

## 7. 扫描量上限与性能

| 算例数 | 内存 | 写盘时间(SSD) |
|---|---|---|
| 100 | ~5MB | <1 秒 |
| 1,000 | ~50MB | ~5 秒 |
| 10,000 | ~500MB | ~50 秒 |

> 10000 个 case 是 ~1 分钟。如果你想扫几十万个,联系项目维护者(并行写盘还没做)。

## 8. 实战模板

**模板 1:典型气动扫描**

```yaml
sweeps:
  alpha: [0, 2, 4, 6, 8, 10]   # 6 个
  mach:  [0.6, 0.8]            # 2 个
  T_inf: [288.15]
  p_inf: [101325.0]
# 6 × 2 = 12 个 case
```

**模板 2:含侧滑**

```yaml
sweeps:
  alpha: [0, 5, 10]
  beta:  [-4, 0, 4]
  mach:  [0.6, 0.8]
  T_inf: [288.15]
  p_inf: [101325.0]
# 3 × 3 × 2 = 18 个 case
```

**模板 3:DOE 大规模**

```yaml
sweeps:
  alpha: [0, 2, 4, 6, 8, 10, 12]    # 7
  mach:  [0.50, 0.65, 0.80, 0.95]    # 4
  altid: [0, 5000, 10000]            # 3
  T_inf: [288.15]
  p_inf: [101325.0]
# 7 × 4 × 3 = 84 个 case
```

下一步:[05-配置文件](05-config-files.md) — JSON vs YAML vs CLI 快捷 怎么选。
