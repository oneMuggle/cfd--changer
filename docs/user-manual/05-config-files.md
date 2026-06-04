# 05 — 配置文件

## 1. 三种方式对比

| 方式 | 适用场景 | 优点 | 缺点 |
|---|---|---|---|
| **CLI 快捷参数** | 临时一次性 | 无需文件 | 长参数难复现 |
| **JSON 配置文件** | 推荐默认 | 标准格式,无依赖,易复现 | 写起来稍繁 |
| **YAML 配置文件** | 长期/共享 | 人类友好,易 review | 需要 `[yaml]` extras |

## 2. JSON 配置

**最小示例:**

```json
{
  "template":   "examples/mcfd_v2_modified.inp",
  "output_dir": "/tmp/sweep_out",
  "sweeps": {
    "alpha": [0, 4, 8],
    "mach":  [0.6, 0.8],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  }
}
```

**完整示例(含 naming、preset、overrides、manifest):**

```json
{
  "template":   "D:\\cfd\\mcfd.inp",
  "output_dir": "D:\\cfd\\sweep_out",
  "sweeps": {
    "alpha": [0, 2, 4, 6, 8, 10],
    "beta":  [-4, 0, 4],
    "mach":  [0.6, 0.8],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  },
  "naming": "case_aoa{alpha:02.0f}_b{beta:+03d}_ma{mach:.2f}.inp",
  "overrides": {
    "tsteps":   {"ntstep": 50000, "cflbot": 0.001},
    "options":  {"ntoutfv": 5000}
  },
  "freestream": {
    "enabled": true,
    "gamma": 1.4,
    "R": 287.05
  },
  "manifest": {
    "path": "D:\\cfd\\sweep_out\\manifest.json"
  }
}
```

**调用:**

```bash
inp-tool sweep mcfd.inp sweep.json
# --out 可覆盖 output_dir
inp-tool sweep mcfd.inp sweep.json --out /tmp/another
```

## 3. YAML 配置

**安装要求:**

```bash
pip install inp-tool[yaml]
# 或 conda 装 pyyaml
```

**最小示例(对比 JSON 同一份):**

```yaml
template: examples/mcfd_v2_modified.inp
output_dir: /tmp/sweep_out
sweeps:
  alpha: [0, 4, 8]
  mach:  [0.6, 0.8]
  T_inf: [288.15]
  p_inf: [101325.0]
```

**完整示例:**

```yaml
template: D:\cfd\mcfd.inp
output_dir: D:\cfd\sweep_out
sweeps:
  alpha: [0, 2, 4, 6, 8, 10]
  beta:  [-4, 0, 4]
  mach:  [0.6, 0.8]
  T_inf: [288.15]
  p_inf: [101325.0]
naming: "case_aoa{alpha:02.0f}_b{beta:+03d}_ma{mach:.2f}.inp"
overrides:
  tsteps:
    ntstep: 50000
    cflbot: 0.001
  options:
    ntoutfv: 5000
freestream:
  enabled: true
  gamma: 1.4
  R: 287.05
manifest:
  path: D:\cfd\sweep_out\manifest.json
```

**调用:**

```bash
inp-tool sweep mcfd.inp sweep.yaml
```

## 4. 字段详解

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `template` | ✅ | string | 模板 .inp 路径(绝对/相对) |
| `output_dir` | ✅ | string | 输出目录,不存在则自动创建 |
| `sweeps` | ✅ | dict | {字段名: [值列表]} |
| `naming` | ⬜ | string | 命名模板,空则自动生成 |
| `overrides` | ⬜ | dict | 字段覆盖规则(详见 [07](07-overrides.md)) |
| `freestream` | ⬜ | dict | 来流 preset 配置 |
| `manifest.path` | ⬜ | string | 索引文件输出路径 |
| `naming_ext` | ⬜ | string | 文件扩展名,默认 `.inp` |

### 4.1 `sweeps` 字段

```yaml
sweeps:
  <sweep_field>: [v1, v2, ...]   # 多值(扫描)或单值(常量)
```

任意数量的字段。

### 4.2 `naming` 字段

Python `str.format(**params)` 风格,**占位符 = sweep 字段名**。详见 [06-命名规则](06-naming.md)。

### 4.3 `overrides` 字段

两种风格,详见 [07-字段覆盖](07-overrides.md):

```json
// 风格 1:嵌套
"overrides": {
  "tsteps":   {"ntstep": 20000}
}

// 风格 2:点号
"overrides": {
  "tsteps.ntstep": 20000
}
```

### 4.4 `freestream` 字段

```yaml
freestream:
  enabled: true             # 默认 true
  gamma: 1.4               # 干空气
  R: 287.05                # J/(kg·K)
  speed_of_sound: null     # 显式声速,跳过 sqrt(gamma·R·T)
  update_physics: true     # 是否同时写 physics.refvel/reftem/refpre
```

要"完全手动"模式,设 `enabled: false`。

### 4.5 `manifest` 字段

```yaml
manifest:
  path: /tmp/sweep_out/manifest.json
```

不写就**不生成** manifest(默认)。建议总是开,便于审计。

## 5. 选择指南

| 场景 | 推荐 |
|---|---|
| 一次性探索 | CLI 快捷参数 |
| 长期复现的扫描 | YAML |
| 进 CI / 自动化 | JSON |
| 跟同事 review | YAML(易读) |
| 在 Python 脚本里生成配置 | JSON(dump 简单) |

## 6. 验证配置

不确定配置对不对?加 `--dry-run` 跑一遍,看会生成什么,但不写盘:

```bash
inp-tool sweep mcfd.inp sweep.yaml --dry-run
# 期望输出每个 case 的文件名和参数
```

## 7. 常见错误

| 错误 | 原因 | 修法 |
|---|---|---|
| `KeyError: 'template'` | 缺 `template` 字段 | 加上 |
| `naming template ... is missing sweep key` | naming 没包含所有多值 sweep 字段 | 补上 `{alpha}` 之类占位符 |
| `JSON parse error` | JSON 语法错(逗号、引号) | 用 `python -m json.tool < sweep.json` 校验 |
| `template not found` | 路径不对 | 用绝对路径或 cd 到正确目录 |

下一步:[06-命名规则](06-naming.md) — 怎么让生成的文件名有意义。
