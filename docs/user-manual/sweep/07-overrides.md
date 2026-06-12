# 07 — 字段覆盖(改 alpha/ma 之外的字段)

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
## 1. 什么场景需要 overrides

`sweeps` + `freestream preset` 帮你处理了**所有**跟"飞行状态"相关的字段(alpha/beta/ma/U/V/W/T/p)。但你可能还想改:

- **时间步参数**(`tsteps.ntstep`, `tsteps.cflbot`)
- **输出频率**(`options.ntplot`, `options.ntoutfv`)
- **湍流模型**(`options.turbmodel` 之类)
- **任意的** `block.keyword` 组合

这就是 `overrides` 的用途。

## 2. 两种写法

**风格 1:嵌套**(块 → 字段 → 值,推荐,更清晰)

```yaml
overrides:
  tsteps:
    ntstep: 50000
    cflbot: 0.001
  options:
    ntoutfv: 5000
    ntplot:  1000
```

**风格 2:点号 key**(更紧凑,适合少量字段)

```yaml
overrides:
  "tsteps.ntstep": 50000
  "tsteps.cflbot": 0.001
  "options.ntoutfv": 5000
```

两种风格效果**完全一样**,可任选。

## 3. 实际例子

### 3.1 加大时间步数 + 加密输出频率

```yaml
sweeps:
  alpha: [0, 4, 8]
  mach:  [0.6, 0.8]
overrides:
  tsteps:
    ntstep: 100000      # 从默认 50000 加大
    cflbot: 0.0005      # 减小 CFL
  options:
    ntplot: 500         # 每 500 步存一次 plot
    ntoutfv: 2000       # 每 2000 步输出场平均
```

→ 6 个 case 全部用这些设置。

### 3.2 每个 case 不同(用 sweep 当作 key)

想"alpha=0 时 cfl=0.001,alpha=8 时 cfl=0.0005"?`overrides` 不直接支持,**改用多个模板或多次 sweep**。

或者:用 Python 脚本在 `generate()` 之后逐 case 改:

```python
from inp_tool import CaseSweep, generate
from inp_tool import parse_file, write

cs = CaseSweep.from_dict({...})
report = generate(cs, dry_run=True)

# 按 alpha 改 cflbot
for case in report.cases:
    inp = parse_file(case.path)
    if case.params["alpha"] >= 5:
        inp.set("tsteps", "cflbot", 0.0005)
    else:
        inp.set("tsteps", "cflbot", 0.001)
    write(inp, case.path)
```

### 3.3 完全手动速度分量(关闭 preset)

如果 CFD++ 的 alpha/beta 方向约定和默认不一样:

```yaml
sweeps:
  alpha: [0, 4, 8]
  mach:  [0.6, 0.8]
freestream:
  enabled: false        # 关闭 preset
overrides:
  guiopts:
    aero_u: 250.0      # 完全自己给
    aero_v: 0.0
    aero_w: 0.0
```

→ 不再自动算 `aero_u/v/w`,直接用你给的值。

### 3.4 改 T_inf 但不动 P_inf

```yaml
sweeps:
  alpha: [0, 5]
  T_inf: [280, 290, 300]   # 扫描温度
  # p_inf 不扫 → 不写 sweeps
  # 但希望所有 case 都有 aero_pres = 101325
overrides:
  guiopts:
    aero_pres: 101325.0
```

## 4. overrides 的应用时机

`overrides` 在 **preset 之后** 应用。所以:

- preset 已经把 `aero_u/v/w` 算好写进 guiopts
- 然后 overrides 用新值覆盖(如果有 aero_u/v/w 在 overrides 里)

`overrides` 优先级 **高于** preset。

## 5. 模板里没有的块/字段怎么办?

- **块不存在**(如老版本 CFD++ 的 .inp 没 `guiopts`)→ `WARN` 但不抛,跳过
- **字段不存在于块里** → `append`(在块尾追加,避免破坏既有结构)

如果你想看到所有警告,运行时用 `--verbose`:

```bash
inp-tool sweep tpl.inp sweep.yaml --verbose
```

或在 Python 里:

```python
import logging
logging.basicConfig(level=logging.WARNING)
```

## 6. 写覆盖但不破坏 preset

如果你**只想**改 1 个字段,其它保持 preset 自动算的:

```yaml
sweeps:
  alpha: [0, 4, 8]
  mach:  [0.6, 0.8]
overrides:
  tsteps:
    ntstep: 20000   # 改了 tsteps.ntstep
                    # 其它(pres、re、refvel) 仍由 preset 算
```

`overrides.tsteps.ntstep` 只覆盖 `tsteps.ntstep`,不影响 `aero_u/v/w` 之类。

## 7. 出错排查

| 错误 | 原因 | 修法 |
|---|---|---|
| `WARN: override block 'xxx' not found` | 模板里没这个块 | 确认模板 .inp 确实没此块;或用块名拼写 |
| 字段没改 | key 拼错(大小写、空格) | 严格按模板里的 `block.keyword` 大小写 |
| 重复字段(一个改、一个 append) | 模板里字段拼写和 overrides 不一致 | 用 `inp-tool get` 看模板里的精确字段名 |

**调试命令:**

```bash
# 看模板里有哪些字段
inp-tool info tpl.inp
inp-tool parse tpl.inp -b tsteps -f
```

下一步:[08-多入口使用](./08-multiple-uis.md) — CLI / Python / Web GUI 怎么选。
