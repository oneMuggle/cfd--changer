# 06 — 命名规则

## 1. 为什么命名重要

`inp_tool` 默认会生成 N 个文件,名字不取好就成了 `case_0.inp`、`case_1.inp`,三个月后没人记得哪个对应哪个参数。

好的命名 = 看到文件名立刻知道是哪个 case。

## 2. 自动命名(不指定时)

如果你在配置里**不写** `naming`,`inp_tool` 会自动生成,**只取多值 sweep 字段**:

```yaml
sweeps:
  alpha: [0, 4, 8]      # 多值 → 进文件名
  beta:  [0]            # 单值 → 不进
  mach:  [0.6, 0.8]     # 多值 → 进
  T_inf: [288.15]       # 单值 → 不进
```

默认 naming = `case_{alpha}_{mach}`

输出:

```
case_0.0_0.6.inp
case_0.0_0.8.inp
case_4.0_0.6.inp
case_4.0_0.8.inp
case_8.0_0.6.inp
case_8.0_0.8.inp
```

## 3. 自定义命名

`naming` 字段是 **Python `str.format()` 风格**的模板,占位符 = sweep 字段名。

### 3.1 基础格式

```yaml
naming: "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
```

| 占位符 | 含义 | 例子 |
|---|---|---|
| `{alpha}` | 默认格式 | `0.0`, `4.0` |
| `{alpha:02.0f}` | 浮点,2 位整数+小数 | `00`, `04`, `08` |
| `{alpha:+.1f}` | 浮点,带正负号 | `+0.0`, `-4.0` |
| `{alpha:+03d}` | 整数,带正负号,3 位补零 | `+00`, `-04` |
| `{mach:.2f}` | 浮点,2 位小数 | `0.60`, `0.80` |

### 3.2 常见命名模板

**风洞测试习惯:**

```yaml
naming: "aoa{alpha:+03d}_b{beta:+03d}_ma{mach:.2f}_re{reynolds:.2e}.inp"
# 输出: aoa+00_b+00_ma0.60_re1.00e+06.inp
```

**DOE 任务号:**

```yaml
naming: "run{run_id:03d}_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
# 输出: run001_aoa00_ma0.60.inp
```

**带工况描述:**

```yaml
naming: "{case_tag}_alpha{alpha:02.0f}_beta{beta:+03d}.inp"
# 输出: cruise_alpha00_beta+00.inp
```

### 3.3 冲突处理

如果两个 case 的参数展开后文件名一样(理论上不应发生,但用户可能自定 naming 时搞错),`inp_tool` 自动追加 `_1`, `_2`...:

```
case_alpha0.inp       # 第 1 个
case_alpha0_1.inp     # 第 2 个
case_alpha0_2.inp     # 第 3 个
```

## 4. 命名校验规则

`naming` 模板**必须**包含所有**多值** sweep 字段。否则报错:

```yaml
sweeps:
  alpha: [0, 4, 8]   # 多值
  mach:  [0.6, 0.8]  # 多值
naming: "case_aoa{alpha:02.0f}.inp"  # 缺 {mach}
```

→ 错误:`naming template 'case_aoa{alpha:02.0f}.inp' is missing sweep key placeholders for multi-value axes: ['mach']`

**为什么强制?** 因为同 `alpha` 不同 `mach` 的 case 名字一样会覆盖,数据丢失。

## 5. 单值字段不进 naming(默认行为)

单值 sweep(如 `T_inf: [288.15]`)默认**不**进 naming,因为它对所有 case 都一样,放进文件名没区分作用,反而污染。

**例:**

```yaml
sweeps:
  alpha: [0, 5]            # 多值
  T_inf: [288.15]          # 单值
  p_inf: [101325.0]        # 单值
# 默认 naming: "case_{alpha}"
# 输出: case_0.0.inp, case_5.0.inp
```

如果想强制单值进 naming(罕见),写出来:

```yaml
sweeps:
  alpha: [0, 5]
  T_inf: [288.15]
naming: "case_T{T_inf}_a{alpha:02.0f}.inp"
# 输出: case_T288.15_a00.inp, case_T288.15_a05.inp
```

## 6. 文件名长度

`naming` 太长会让文件系统抱怨(Linux 限制 255 字符)。建议命名总长 ≤ 80 字符。

**太长怎么办:** 用短字段名 + 简写格式:

```yaml
# 短
naming: "a{alpha:02.0f}_b{beta:+02d}_m{mach:.2f}.inp"  # 30 字符

# 长
naming: "case_at_alpha_{alpha:04.1f}_deg_at_beta_{beta:+04.1f}_deg_at_mach_{mach:.3f}.inp"  # 80+ 字符
```

## 7. 中文命名(可以但不推荐)

```yaml
naming: "案例_{alpha:02.0f}.inp"
```

技术上是合法的,但:
- Windows 编码可能踩坑
- 同事/CI 系统可能传 UTF-8 出问题
- shell 命令处理中文文件名容易出 bug

**建议:** 命名用 ASCII,内容(报告、描述)用中文。

## 8. 出错排查

| 错误 | 原因 |
|---|---|
| `KeyError: 'alpha'` | naming 用了 `alpha` 但 sweeps 里没有 |
| `KeyError: 'mach'` | 同上 |
| 文件名太长(>255) | naming 拼太长了 |
| 多个 case 名字一样 | 命名缺多值字段;被 `inp_tool` 自动加 `_1` 后缀解决 |

下一步:[07-字段覆盖](07-overrides.md) — 想改 alpha/mach 之外的字段怎么办。
