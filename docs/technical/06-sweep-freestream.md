# 06 — FreestreamPreset 几何分解

> **审计:** 2026-06-04 · 章节与 v0.4.0 同步 · 全部示例通过 · 全部链接有效
**对应源码:** `inp_tool/sweep.py::FreestreamPreset`  ·  **版本:** v0.4

---

## 1. 公式

给定 `(alpha_deg, beta_deg, mach, T_inf)` 与 `(gamma, R)`:

```
a = sqrt(gamma · R · T_inf)              # 声速
U = mach · a · cos(alpha) · cos(beta)
V = mach · a · sin(beta)
W = mach · a · sin(alpha) · cos(beta)
refvel = sqrt(U² + V² + W²)              # = mach · a
```

**关键不变量:** `refvel = mach · a`(旋转不变),不论 alpha/beta 怎么转。

## 2. 默认参数

| 参数 | 默认 | 物理意义 |
|---|---|---|
| `gamma` | 1.4 | 干空气绝热指数 |
| `R` | 287.05 | 干空气气体常数 J/(kg·K) |
| `speed_of_sound` | None | 显式覆盖 a = sqrt(γ·R·T) 的计算 |
| `update_physics` | True | 是否同步写 `physics.refvel/reftem/refpre` |

**适用气体的非默认值:**

| 气体 | gamma | R (J/(kg·K)) |
|---|---|---|
| 干空气 | 1.40 | 287.05 |
| N₂ | 1.40 | 296.80 |
| O₂ | 1.40 | 259.84 |
| He | 1.66 | 2077.0 |
| CO₂ | 1.30 | 188.92 |
| H₂ | 1.41 | 4124.0 |

## 3. 字段映射

`FreestreamPreset.apply(inp, params)` 会更新以下字段:

### guiopts 块(飞参 / 前处理)

| 字段 | 来源 | 写入条件 |
|---|---|---|
| `aero_alpha` | `params["alpha"]` | 总写 |
| `aero_beta` | `params["beta"]`(默认 0) | 总写 |
| `aero_ma` | `params["mach"]`(默认 0) | 总写 |
| `aero_u` | 公式 U | 总写 |
| `aero_v` | 公式 V | 总写 |
| `aero_w` | 公式 W | 总写 |
| `aero_temp` | `params["T_inf"]`(默认 288.15) | 总写 |
| `aero_pres` | `params["p_inf"]` | 仅当提供时 |
| `aero_re` | 不自动算(由 reynolds 数场景手动给) | — |

**写入策略:** `gb.set(key, value)` 优先;不存在则 `gb.append(key, value)`(在块尾追加)。

### physics 块(参考物理量)

| 字段 | 来源 | 写入条件 |
|---|---|---|
| `refvel` | 公式 `sqrt(U²+V²+W²)` | update_physics=True |
| `reftem` | `params["T_inf"]` | update_physics=True |
| `refpre` | `params["p_inf"]` | update_physics=True 且提供了 p_inf |

## 4. 方向假设(用户必读)

```
        W (vertical)
        ↑
        │   ╱ α  (alpha 在 Y-Z 平面 → 影响 W)
        │  ╱
        │ ╱   → U (streamwise / x)
        └──────────→ U
       ╱
      ╱ β  (beta 在 X-Z 平面 → 影响 V)
     ↓
     V (sideward / y)
```

| 角度 | 影响的速度分量 | CFD++ 习惯 |
|---|---|---|
| alpha (α) | W(垂直速度,法向) | 多数版本 |
| beta (β) | V(侧滑速度) | 多数版本 |

**重要:** 不同 CFD++ 版本对 alpha/beta 与 U/V/W 的对应**可能略有差异**。在不确定时:

```python
# 方案 A: 完全跳过 preset,手动给 aero_u/v/w
cs = CaseSweep.from_dict({
    ...,
    "freestream": {"enabled": False},
    "overrides": {
        "guiopts": {
            "aero_u": my_U,
            "aero_v": my_V,
            "aero_w": my_W,
        }
    }
})

# 方案 B: 显式给 speed_of_sound
cs = CaseSweep.from_dict({
    ...,
    "freestream": {
        "enabled": True,
        "speed_of_sound": 340.29,   # 显式覆盖,不依赖 T
        "gamma": 1.4,
        "R": 287.05
    }
})
```

## 5. 验证公式正确性

下面的等式应**始终**成立:

| 等式 | 解释 |
|---|---|
| `refvel == mach · a` | 旋转不变性 |
| `cos(α)² · cos(β)² + sin(β)² + sin(α)² · cos(β)² == 1` | 三角度正交归一 |
| `U² + V² + W² == refvel²` | 模长守恒 |

### 单元测试覆盖

`test_sweep.py::TestFreestreamPreset` 测了:
- 纯 X 方向(α=β=0):`U = Ma·a`,`V=W=0`
- 纯 alpha(β=0):`W = Ma·a·sin(α)`,`U = Ma·a·cos(α)`,`V=0`
- 纯 beta(α=0):`V = Ma·a·sin(β)`,`U = Ma·a·cos(β)`,`W=0`
- 任意 (α,β):`refvel = Ma·a`(循环测多组)
- 显式 `speed_of_sound` 覆盖
- `apply()` 实际写入 InpFile 并 round-trip
- guiopts 块缺失时 warn 不抛

## 6. 数值稳定性

- 极端 alpha(如 89°):`cos(α) ≈ 0`,`sin(α) ≈ 1`,无精度问题
- 极端 beta:同
- 极低 Mach(如 0.01):`U/V/W` 都很小,但 `refvel` 仍准确
- 极高 Mach(如 5.0):标准浮点精度足够

## 7. 物理量单位约定

| 量 | 单位 | 来源 |
|---|---|---|
| alpha, beta | 度(deg) | CFD++ `aero_alpha/beta` 用度 |
| T_inf | K | CFD++ `aero_temp` 用 K |
| p_inf | Pa | CFD++ `aero_pres` 用 Pa |
| U, V, W | m/s | 标准 SI |
| a, refvel | m/s | 标准 SI |
| mach | 无量纲 | Ma |

**注意:** 如果您的样例里用"度"以外的单位(如弧度),需在 `overrides` 里手动转换。本模块假设输入与输出均为 SI 衍生单位。
