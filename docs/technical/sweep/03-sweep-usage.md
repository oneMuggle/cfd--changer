# 05 — 三入口详细用法

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
**模块:** `inp_tool.sweep`  ·  **对应源码:** `cli.py` / `api.py` / `__init__.py`

---

> **视角定位:** 开发者视角(Python / CLI / FastAPI 完整 API)。用户视角的扫哪些字段见 [user-manual/sweep/01-sweeping](../../user-manual/sweep/01-sweeping.md),4 种入口速览见 [user-manual/sweep/05-multiple-uis](../../user-manual/sweep/05-multiple-uis.md)。

## 1. Python API

### 1.1 最简示例

```python
from inp_tool import CaseSweep, FreestreamPreset, generate

cs = CaseSweep.from_dict({
    "template":   "examples/mcfd_v2_modified.inp",
    "output_dir": "examples/sweep_cases",
    "sweeps": {
        "alpha": [0, 4, 8],          # deg
        "beta":  [0],
        "mach":  [0.6, 0.8],
        "T_inf": [288.15],
        "p_inf": [101325.0],
    },
    # naming 不写 → 自动生成 "case_{alpha}_{mach}"
    "manifest": {"path": "examples/sweep_cases/manifest.json"},
    "freestream": {"enabled": True, "gamma": 1.4, "R": 287.05},
})

report = generate(cs)         # -> SweepReport (6 cases by 3*1*2)
print(f"generated {report.total} cases")

for c in report.cases:
    print(f"  {c.case_id}  alpha={c.params['alpha']}  mach={c.params['mach']}")
```

### 1.2 不使用 preset(手动改 aero_u/v/w)

```python
cs = CaseSweep.from_dict({
    "template":   "tpl.inp",
    "output_dir": "cases",
    "sweeps": {"alpha": [0, 5, 10]},
    "freestream": {"enabled": False},   # 跳过几何分解
    "overrides": {
        "guiopts": {
            "aero_u": 250.0,            # 手动给
            "aero_v": 0.0,
            "aero_w": 0.0,
        }
    }
})
```

### 1.3 编程构造(免去 dict)

```python
from inp_tool.sweep import (
    SweepSpec, FreestreamPreset, CaseSweep, generate
)

cs = CaseSweep(
    template="tpl.inp",
    output_dir="out",
    sweeps=SweepSpec(values={"alpha": [0, 5, 10], "mach": [0.6, 0.8]}),
    naming="case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
    freestream=FreestreamPreset(gamma=1.4, R=287.05),
    manifest_path="out/manifest.json",
)
report = generate(cs)
```

### 1.4 dry-run(预演)

```python
report = generate(cs, dry_run=True)
# 不写盘,但 SweepReport 完整
print(report.to_dict())  # dict 形式
print(report.to_json())  # json 字符串
```

## 2. CLI

### 2.1 JSON 配置(推荐,适合脚本/复现)

```bash
inp-tool sweep examples/mcfd_v2_modified.inp examples/sweep_demo.json --out ./cases
```

`--out` 覆盖 config 里的 `output_dir`。`--manifest` 同理。

### 2.2 单独使用(无 config 文件)

```bash
inp-tool sweep tpl.inp \
    --alpha 0,4,8 \
    --beta 0,2 \
    --mach 0.6,0.8 \
    --t-inf 288.15 \
    --p-inf 101325 \
    --out ./cases \
    --manifest ./cases/manifest.json
```

- `--alpha 0,4,8` = 列表扫描(多个值笛卡尔积展开)
- `--t-inf 288.15` = 单值辅助参数(可省略,不进 naming)
- `--dry-run` = 不写盘

### 2.3 YAML 配置(需 `[yaml]` extras)

```bash
conda run -n cfdchanger pip install -e .[yaml]
inp-tool sweep examples/sweep_demo.yaml --out ./cases
```

详见 [05-sweep-friendly-uis.md §1](05-sweep-friendly-uis.md)。

### 2.4 交互式(-i)

```bash
inp-tool sweep -i
```

走 prompt 序列,所有字段有 default,回车接受。详见 [05-sweep-friendly-uis.md §2](05-sweep-friendly-uis.md)。

### 2.5 输出示例

```
$ inp-tool sweep examples/sweep_demo.json --out /tmp/c
[sweep] generated 6 cases -> /tmp/c
  - case_aoa00_b00_ma0.60.inp  (alpha=0.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa00_b00_ma0.80.inp  (alpha=0.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
  - case_aoa04_b00_ma0.60.inp  (alpha=4.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa04_b00_ma0.80.inp  (alpha=4.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
  - case_aoa08_b00_ma0.60.inp  (alpha=8.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa08_b00_ma0.80.inp  (alpha=8.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
[sweep] manifest -> ./cases/manifest.json
```

`-v / --verbose` 在 >20 cases 时强制列出每个 case。

### 2.6 exit code 语义

| Code | 含义 |
|---|---|
| 0 | 成功(包括 dry-run) |
| 2 | 模板/配置不存在,或 sweep 配置无效 |
| 1 | 内部错误(unhandled exception) |

## 3. FastAPI

### 3.1 启动服务

```bash
# 1) 一键启动
python run_server.py
# 浏览器: http://127.0.0.1:8765/docs

# 2) 手动 uvicorn
conda run -n cfdchanger uvicorn inp_tool.api:app --host 0.0.0.0 --port 8765
```

### 3.2 `POST /api/sweep`

**Request body(JSON):**
```json
{
  "template":   "D:\\cfd\\mcfd.inp",
  "output_dir": "D:\\cfd\\sweep",
  "sweeps": {
    "alpha": [0.0, 4.0, 8.0],
    "beta":  [0.0],
    "mach":  [0.60, 0.80],
    "T_inf": [288.15],
    "p_inf": [101325.0]
  },
  "naming":     "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
  "overrides":  {"tsteps": {"ntstep": 20000}},
  "freestream": {"enabled": true, "gamma": 1.4, "R": 287.05},
  "manifest":   {"path": "D:\\cfd\\sweep\\manifest.json"},
  "dry_run":    false
}
```

**Response 200(SweepResponse):**
```json
{
  "total": 6,
  "template": "D:\\cfd\\mcfd.inp",
  "dry_run": false,
  "manifest_path": "D:\\cfd\\sweep\\manifest.json",
  "cases": [
    {
      "case_id": "case_aoa00_ma0.60.inp",
      "path":    "D:\\cfd\\sweep\\case_aoa00_ma0.60.inp",
      "params":  {"alpha": 0.0, "beta": 0.0, "mach": 0.6, "T_inf": 288.15, "p_inf": 101325.0},
      "applied": {"guiopts.aero_alpha": 0.0, "guiopts.aero_u": 204.99, "physics.refvel": 204.99}
    }
  ]
}
```

**错误码:**

| Status | 含义 |
|---|---|
| 400 | 配置错误(`KeyError` / `ValueError` from `from_dict`) |
| 404 | template 不存在 |
| 500 | generate 内部错误(unhandled) |

### 3.3 curl 示例

```bash
curl -X POST http://127.0.0.1:8765/api/sweep \
     -H "Content-Type: application/json" \
     -d @examples/sweep_demo.json
# -> {"total": 6, "cases": [...], "template": "examples/mcfd_v2_modified.inp", ...}
```

### 3.4 OpenAPI 文档

`/docs`(Swagger UI)与 `/redoc` 自动生成。Pydantic schema(`SweepRequest` / `SweepResponse` / `CaseSchema`)有详细字段说明。

## 4. 配置文件完整 schema

`CaseSweep.from_dict(d)` 接受 dict,其 schema 等价于 CaseSweep dataclass:

```yaml
# 必填
template:    string            # 模板 .inp 路径
output_dir:  string            # 输出目录
sweeps:      { axis: [values] }  # 至少一个轴

# 可选
naming:      string            # 命名模板(空=自动)
overrides:   { ... }           # 覆盖规则(两种风格)
freestream:  { ... } | null    # preset 配置
manifest:    { path: string }  # manifest 路径
naming_ext:  string            # 默认 ".inp"
```

`freestream` 字段:
```yaml
freestream:
  enabled: bool               # 默认 true;false=完全跳过 preset
  gamma:    float             # 默认 1.4
  R:        float             # 默认 287.05
  speed_of_sound: float | null # 显式声速,跳过 sqrt(gamma·R·T)
  update_physics: bool        # 默认 true
```

## 5. 错误处理最佳实践

```python
import logging
logging.basicConfig(level=logging.INFO)  # 让 sweep 的 stderr WARN 显现

from inp_tool.sweep import CaseSweep, generate

try:
    cs = CaseSweep.from_dict(cfg)
except (KeyError, ValueError) as e:
    print(f"配置错误: {e}")
    sys.exit(2)

report = generate(cs, dry_run=True)  # 先 dry-run
if report.total > 1000:
    if not input(f"将生成 {report.total} 个 case,确认? [y/N]") == "y":
        sys.exit(0)

generate(cs)  # 真正写盘
```

## 6. 三种 case 模式(笛卡尔 / 显式列表 / 分组继承 / CSV)

> v0.7.0 新增。**完全向后兼容**:老 `sweeps:` YAML 零修改继续可用。

### 6.1 模式对照

| 模式 | YAML 字段 | 适用场景 |
|------|-----------|----------|
| 笛卡尔积 | `sweeps: {axis: [v1, v2]}` | 轴正交、维度少、值均匀(传统) |
| 显式列表 | `cases: [{...}, {...}, ...]` | case 数量少 / 不规则 / 要精确控制 |
| 分组继承 | `groups: [{name, common, cases}, ...]` | 几组共参 + 组内 case 列表 |
| CSV 文件 | `cases.csv`(CLI: `--template` + `--naming`) | Excel 维护、几百行 case |
| 混合 | `sweeps: {...}` + `cases: [...]` | 大部分笛卡尔 + 几个特例 |

### 6.2 显式列表

```yaml
# cases_demo.yaml
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
cases:
  - {alpha: 10, beta:  5, mach: 0.6, T: 288.15, p: 101325}
  - {alpha: 10, beta:  8, mach: 0.6, T: 288.15, p: 101325}
  - {alpha: 20, beta: 10, mach: 0.6, T: 288.15, p: 101325}
  - {alpha: 20, beta: 15, mach: 0.6, T: 288.15, p: 101325}
naming: "case_a{alpha:02.0f}_b{beta:02.0f}.inp"
```

调用与笛卡尔一致(`inp-tool sweep cases_demo.yaml`)。

### 6.3 分组继承(您那个"流场 1"场景)

```yaml
# groups_demo.yaml
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
groups:
  - name: flow_1
    common: {T: 288.15, p: 101325, mach: 0.6}  # 三组共参
    cases:
      - {alpha: 10, beta:  5}
      - {alpha: 10, beta:  8}
      - {alpha: 20, beta: 10}
      - {alpha: 20, beta: 15}
naming: "{group}_a{alpha:02.0f}_b{beta:02.0f}.inp"
```

`common` 自动注入到组内每个 case,`cases` 字段可覆盖 `common`。`{group}` 在 naming 中替换为 `name`。

### 6.4 多组对比

```yaml
# multi_flow_demo.yaml
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
groups:
  - name: flow_1_sealevel
    common: {T: 288.15, p: 101325, mach: 0.6}
    cases: [{alpha: 10, beta: 5}, {alpha: 10, beta: 8}, {alpha: 20, beta: 10}, {alpha: 20, beta: 15}]
  - name: flow_2_high_alt
    common: {T: 250.0, p: 35000, mach: 0.85}
    cases: [{alpha: 5, beta: 0}, {alpha: 15, beta: 0}, {alpha: 25, beta: 0}]
  - name: flow_3_cruise
    common: {T: 273.0, p: 75000, mach: 0.78}
    cases: [{alpha: 2, beta: -3}, {alpha: 2, beta: 0}, {alpha: 2, beta: 3}]
naming: "{group}_a{alpha:02.0f}_b{beta:+03.0f}.inp"
```

输出 10 个 case,每个文件名带 `flow_*_` 前缀。

### 6.5 CSV 文件(Excel 友好)

```csv
# cases.csv
alpha,beta,mach,T,p
10,5,0.6,288.15,101325
10,8,0.6,288.15,101325
20,10,0.6,288.15,101325
20,15,0.6,288.15,101325
```

调用:

```bash
inp-tool sweep cases.csv \
    --template examples/mcfd_v2_modified.inp \
    --naming "case_a{alpha:02.0f}_b{beta:02.0f}.inp" \
    --out ./sweep_cases
```

**注意:** CSV 必须有表头;CSV 不含模板 / 输出 / 命名信息,需通过 CLI flag 提供。

### 6.6 混合(笛卡尔 + 特例)

```yaml
# mixed_demo.yaml
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
sweeps:
  alpha: [0, 5, 10, 15]   # 4 cases
  beta:  [0]              # 单值
cases:                     # 特例(有侧滑角)
  - {alpha: 5,  beta: 3}
  - {alpha: 10, beta: 5}
naming: "case_a{alpha:02.0f}_b{beta:02.0f}.inp"
```

`materialize()` 顺序:笛卡尔(4 个)→ 显式(2 个)= 共 6 个 case。

### 6.7 选型决策

| 你的数据形态 | 推荐模式 |
|--------------|----------|
| 5 个轴正交,各扫 3-5 个值 | 笛卡尔积(最简) |
| 4-10 个不规则 case | 显式列表 |
| 几组共参,组内几个 case | 分组继承 |
| Excel 维护,几百行 | CSV |
| 大部分轴正交 + 几个特例 | 混合 |
| LHS / Sobol 等智能采样 | 本次不支持(后续计划) |

## 7. 端到端脚本模板(放进自己的项目)

```python
#!/usr/bin/env python
"""基于 sweep 的批量算例生成脚本。"""
import sys
from pathlib import Path
from inp_tool import CaseSweep, generate

# 配置: 飞行器 alpha 扫描
TEMPLATE = Path("/path/to/mcfd.inp")
OUT_DIR  = Path("/path/to/sweep_alpha_sweep")
OUT_DIR.mkdir(parents=True, exist_ok=True)

cs = CaseSweep.from_dict({
    "template":   str(TEMPLATE),
    "output_dir": str(OUT_DIR),
    "sweeps": {
        "alpha": [0, 2, 4, 6, 8, 10],
        "mach":  [0.6, 0.8],
        "T_inf": [288.15],
        "p_inf": [101325.0],
    },
    "naming":  "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
    "manifest": {"path": str(OUT_DIR / "manifest.json")},
})

report = generate(cs)
print(f"✓ {report.total} cases -> {OUT_DIR}")
print(f"  manifest: {OUT_DIR}/manifest.json")
```
