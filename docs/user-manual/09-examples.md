# 09 — 完整示例

## 例 1:典型气动参数扫描(项目自带)

**目标:** 翼型/小展弦比机翼,6 个 alpha × 2 个 mach = 12 个 case。

**步骤 1:** 准备配置文件 `sweep_aero.yaml`:

```yaml
template: inp_tool/examples/mcfd_v2_modified.inp
output_dir: ./out_aero
sweeps:
  alpha: [0, 2, 4, 6, 8, 10]    # 6 个
  mach:  [0.6, 0.8]             # 2 个
  T_inf: [288.15]               # 海平面标准
  p_inf: [101325.0]
naming: "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
manifest:
  path: ./out_aero/manifest.json
```

**步骤 2:** 试跑(dry-run):

```bash
inp-tool sweep inp_tool/examples/mcfd_v2_modified.inp sweep_aero.yaml --dry-run
# 期望输出 12 个 case 的文件名
```

**步骤 3:** 真跑:

```bash
inp-tool sweep inp_tool/examples/mcfd_v2_modified.inp sweep_aero.yaml
```

**步骤 4:** 验证:

```bash
ls out_aero/
# 12 个 .inp + manifest.json

grep aero_alpha out_aero/case_aoa04_ma0.60.inp
# 期望: aero_alpha 4.0
```

**步骤 5:** 把 `out_aero/` 喂给 CFD++ 求解器(Linux):

```bash
for f in out_aero/*.inp; do
    mcrun "$f" -np 16 &
done
wait
```

---

## 例 2:含侧滑的失速特性研究

**目标:** 大迎角失速研究,alpha × beta 联合扫描。

**`sweep_stall.yaml`:**

```yaml
template: my_aircraft.inp
output_dir: ./out_stall
sweeps:
  alpha: [10, 12, 14, 16, 18, 20, 22, 24]   # 高迎角
  beta:  [-4, -2, 0, 2, 4]                  # 含侧滑
  mach:  [0.30]                              # 低速失速
  T_inf: [288.15]
  p_inf: [101325.0]
overrides:
  tsteps:
    ntstep: 80000
    cflbot: 0.0005        # 失速工况 CFL 减小
  options:
    ntplot: 100           # 加密输出
naming: "stall_aoa{alpha:02.0f}_b{beta:+03d}_ma{mach:.2f}.inp"
manifest:
  path: ./out_stall/manifest.json
```

**运行:**

```bash
inp-tool sweep my_aircraft.inp sweep_stall.yaml
# 8 × 5 = 40 个 case
```

---

## 例 3:DOE 大规模参数扫描(从 Python 生成配置)

**目标:** 100+ 算例,LHS / Sobol 采样。

**`gen_doe_config.py`:**

```python
"""生成 DOE 扫描配置(用 SALib 做 Latin Hypercube Sampling)"""
import json

# 假设你想用 SALib
# from SALib.sample import latin as salib_lhs
# problem = {
#     'num_vars': 4,
#     'names': ['alpha', 'beta', 'mach', 'altid'],
#     'bounds': [[0, 15], [-5, 5], [0.4, 0.95], [0, 15000]],
# }
# samples = salib_lhs.sample(problem, 200)

# 简化版:均匀网格
import numpy as np
np.random.seed(42)
n = 200
alphas = np.random.uniform(0, 15, n).round(2).tolist()
betas  = np.random.uniform(-5, 5, n).round(2).tolist()
machs  = np.random.uniform(0.4, 0.95, n).round(3).tolist()
altids = np.random.uniform(0, 15000, n).round(0).tolist()

config = {
    "template":   "aircraft.inp",
    "output_dir": "./out_doe",
    "sweeps": {
        "alpha": alphas,
        "beta":  betas,
        "mach":  machs,
        "altid": altids,
        "T_inf": [288.15],
        "p_inf": [101325.0],
    },
    "naming": "doe_{alpha:05.2f}_{beta:+05.2f}_{mach:.3f}_{altid:05.0f}.inp",
    "manifest": {"path": "./out_doe/manifest.json"},
}

with open("sweep_doe.json", "w") as f:
    json.dump(config, f, indent=2)

print(f"Generated sweep_doe.json with {n} cases")
```

**运行:**

```bash
python gen_doe_config.py
inp-tool sweep aircraft.inp sweep_doe.json
# 200 个 case,~10 秒
```

---

## 例 4:Python 脚本里调 + 拿到 SweepReport 直接送 CFD 调度器

```python
#!/usr/bin/env python
"""生成 sweep,然后调公司内部调度器跑每个 case。"""
import subprocess
import json
from pathlib import Path
from inp_tool import CaseSweep, generate

# 1) 准备配置
cs = CaseSweep.from_dict({
    "template":   Path("/cfd/templates/mcfd.inp"),
    "output_dir": Path("/cfd/runs/aoa_scan"),
    "sweeps": {
        "alpha": [0, 5, 10, 15],
        "mach":  [0.6, 0.8],
        "T_inf": [288.15],
        "p_inf": [101325.0],
    },
    "naming": "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp",
    "manifest_path": "/cfd/runs/aoa_scan/manifest.json",
})

# 2) 生成 .inp
report = generate(cs)
print(f"✓ {report.total} cases generated")

# 3) 提交到调度器
for case in report.cases:
    job_id = submit_to_scheduler(
        input_file=case.path,
        nproc=16,
        walltime="02:00:00",
    )
    print(f"  {case.case_id} -> job {job_id}")
```

---

## 例 5:在 Jupyter Notebook 里交互探索

```python
import matplotlib.pyplot as plt
from inp_tool import CaseSweep, generate, parse_file

# 第一次:小扫描
cs = CaseSweep.from_dict({
    "template":   "tpl.inp",
    "output_dir": "/tmp/sweep",
    "sweeps": {
        "alpha": [0, 5, 10, 15, 20],
        "mach":  [0.5, 0.7, 0.9],
        "T_inf": [288.15],
        "p_inf": [101325.0],
    },
})
report = generate(cs)

# 把每个 case 的 aero_alpha/mach 抽出来画图
alphas = [c.params["alpha"] for c in report.cases]
machs  = [c.params["mach"]  for c in report.cases]

plt.figure(figsize=(8, 4))
plt.scatter(alphas, machs)
plt.xlabel("alpha (deg)")
plt.ylabel("Mach")
plt.title(f"Sweep Design: {report.total} cases")
plt.grid(True)
plt.show()
```

---

## 例 6:从 manifest 反查某个 case 怎么生成的

```bash
# 想问"case_aoa04_ma0.60.inp 是怎么生成的?"
cat /tmp/sweep/manifest.json | python -c "
import json, sys
m = json.load(sys.stdin)
for c in m['cases']:
    if c['case_id'] == 'case_aoa04_ma0.60.inp':
        print(json.dumps(c, indent=2))
"
```

输出:

```json
{
  "case_id": "case_aoa04_ma0.60.inp",
  "path": "/tmp/sweep/case_aoa04_ma0.60.inp",
  "params": {
    "alpha": 4.0, "beta": 0.0, "mach": 0.6, "T_inf": 288.15, "p_inf": 101325.0
  },
  "applied": {
    "guiopts.aero_alpha": 4.0,
    "guiopts.aero_beta": 0.0,
    "guiopts.aero_ma": 0.6,
    "guiopts.aero_u": 203.67,
    "guiopts.aero_v": 0.0,
    "guiopts.aero_w": 14.24,
    "guiopts.aero_temp": 288.15,
    "physics.refvel": 204.81,
    "physics.reftem": 288.15
  }
}
```

审计/复现就这么简单。

下一步:[10-常见问题](10-faq.md) — 遇到问题先翻这里。
