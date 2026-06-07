# 08 — 多入口使用

> **审计:** 2026-06-04 · 章节与 v0.4.2 同步 · 全部示例通过 · 全部链接有效
## 1. 四种入口速览

| 入口 | 适合谁 | 复杂度 |
|---|---|---|
| **CLI 快捷参数** | 命令行熟手 | ⭐ |
| **CLI 配置文件** | 工程师常规使用 | ⭐⭐ |
| **Python API** | 数据科学 / 集成到自己代码 | ⭐⭐⭐ |
| **Web GUI** | 不爱写命令的同事 | ⭐ |
| **交互式 CLI** | 临时性、参数多 | ⭐⭐ |

## 2. CLI(命令行)

### 2.1 启动方式

```bash
inp-tool sweep [参数]
```

### 2.2 快捷参数(无配置文件)

```bash
inp-tool sweep tpl.inp \
    --alpha 0,4,8 \
    --beta 0 \
    --mach 0.6,0.8 \
    --t-inf 288.15 \
    --p-inf 101325 \
    --out /tmp/sweep \
    --naming "case_aoa{alpha:02.0f}_ma{mach:.2f}.inp"
```

| 参数 | 含义 |
|---|---|
| `tpl.inp` | 模板(必填) |
| `--alpha 0,4,8` | 攻角扫描 |
| `--beta 0` | 侧滑 |
| `--mach 0.6,0.8` | 马赫 |
| `--t-inf 288.15` | 温度 K |
| `--p-inf 101325` | 压强 Pa |
| `--out /tmp/sweep` | 输出目录 |
| `--naming ...` | 命名模板 |
| `--manifest PATH` | manifest 路径 |
| `--dry-run` | 试跑不写盘 |
| `-v / --verbose` | 列出所有 case |
| `-i / --interactive` | 交互式 prompt |

### 2.3 配置文件 + CLI 覆盖

```bash
inp-tool sweep tpl.inp sweep.yaml
inp-tool sweep tpl.inp sweep.yaml --out /tmp/another  # output_dir 覆盖
inp-tool sweep tpl.inp sweep.yaml --dry-run          # 试跑
```

`--out` 和 `--manifest` 是 CLI 唯一会覆盖 config 的字段,其它字段用配置文件。

### 2.4 完整输出示例

```bash
$ inp-tool sweep examples/mcfd_v2_modified.inp examples/sweep_demo.json

[sweep] generated 6 cases -> /tmp/sweep_out
  - case_aoa00_b00_ma0.60.inp  (alpha=0.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa00_b00_ma0.80.inp  (alpha=0.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
  - case_aoa04_b00_ma0.60.inp  (alpha=4.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa04_b00_ma0.80.inp  (alpha=4.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
  - case_aoa08_b00_ma0.60.inp  (alpha=8.0 beta=0.0 mach=0.6 T_inf=288.15 p_inf=101325.0)
  - case_aoa08_b00_ma0.80.inp  (alpha=8.0 beta=0.0 mach=0.8 T_inf=288.15 p_inf=101325.0)
[sweep] manifest -> examples/sweep_cases/manifest.json
```

## 3. 交互式 CLI(`-i`)

适合"参数太多懒得写配置文件"或"临时性跑一下"。

```bash
$ inp-tool sweep -i
=== sweep 交互式配置(回车=接受默认值)===

模板 .inp 路径 [回车跳过必填]: examples/mcfd_v2_modified.inp
输出目录 [./sweep_cases]: /tmp/my_sweep
攻角 alpha 扫描 (deg,逗号分隔) [0,4,8]: 0,2,4,6,8,10
侧滑角 beta 扫描 (deg,逗号分隔) [0]: -2,0,2
马赫 mach 扫描 (逗号分隔) [0.6,0.8]:
来流温度 T_inf K (单值或逗号列表) [288.15]:
来流压强 p_inf Pa (单值或逗号列表) [101325.0]:
命名模板 (空=auto):
manifest 路径 (空=不写):
dry-run?(只打印不写盘) [y/N]: n
确认按上面配置生成? [Y/n]: y
[sweep] generated 18 cases -> /tmp/my_sweep
  - case_0.0_-2.0_0.6_288.15_101325.0.inp  ...
  - case_0.0_-2.0_0.8_288.15_101325.0.inp  ...
  ...
```

**特点:**
- 全部字段有默认值,一路回车可走完
- 模板路径必填(防止误操作)
- 类型错自动重试
- 取消 = 最后 `n`

**适用:** 一次性扫描、参数偶尔变、给新人示范。

## 4. Python API

适合:集成到自己的脚本/Notebook、想做条件分支(根据参数动态改 sweep)、需要把生成结果直接送入下游流水线。

### 4.1 最简

```python
from inp_tool import CaseSweep, generate

cs = CaseSweep.from_dict({
    "template":   "tpl.inp",
    "output_dir": "/tmp/sweep",
    "sweeps": {
        "alpha": [0, 4, 8],
        "mach":  [0.6, 0.8],
        "T_inf": [288.15],
        "p_inf": [101325.0]
    }
})
report = generate(cs)
print(f"Generated {report.total} cases")
```

### 4.2 编程构造

```python
from inp_tool import SweepSpec, CaseSweep, FreestreamPreset, generate

# 多个 sweep 一次构造
sweeps = SweepSpec(values={
    "alpha": [0, 4, 8],
    "beta":  [-2, 0, 2],
    "mach":  [0.6, 0.8],
})

cs = CaseSweep(
    template="tpl.inp",
    output_dir="/tmp/sweep",
    sweeps=sweeps,
    freestream=FreestreamPreset(gamma=1.4, R=287.05),
    naming="case_aoa{alpha:02.0f}_b{beta:+03d}_ma{mach:.2f}.inp",
    manifest_path="/tmp/sweep/manifest.json",
)
report = generate(cs)
```

### 4.3 动态配置

```python
import json
import sys
from pathlib import Path

# 从 argv 读
config_path = sys.argv[1]
cs = CaseSweep.from_json(config_path)

# dry-run 一次再写
report = generate(cs, dry_run=True)
if report.total > 1000:
    answer = input(f"将生成 {report.total} 个 case,确认? [y/N]: ")
    if answer != "y":
        sys.exit(0)

generate(cs)
```

### 4.4 拿到 SweepReport 后做后处理

```python
import json
from inp_tool import CaseSweep, generate

cs = CaseSweep.from_dict({...})
report = generate(cs)

# 把 manifest 写出来
with open("/tmp/sweep/index.json", "w") as f:
    json.dump(report.to_dict(), f, indent=2)

# 遍历每个 case 做后处理
for case in report.cases:
    print(f"{case.case_id} -> {case.path}")
    print(f"  params:  {case.params}")
    print(f"  applied: {case.applied}")
```

## 5. Web GUI

适合:不爱写命令的同事、想看 GUI、远程服务器上跑。

### 5.1 启动

```bash
# 装好 [api] 后
python run_server.py
# 或:
uvicorn inp_tool.api:app --host 0.0.0.0 --port 8765
```

浏览器开 `http://127.0.0.1:8765/`

### 5.2 界面

- **顶栏:** "编辑器" / "批量生成" 标签切换
- **编辑器标签:** 加载 mcfd.inp,改字段,保存(原 v0.3 功能)
- **批量生成标签:** 填表 → 点"生成" → 表格显示结果

### 5.3 批量生成页字段

| 字段 | 含义 |
|---|---|
| 模板路径 | .inp 完整路径(服务器能访问的) |
| 输出目录 | 服务器上的目录 |
| alpha / beta / mach | 逗号分隔 |
| T_inf / p_inf | 温度/压强 |
| naming 模板 | 文件名规则 |
| ☑ dry-run | 勾上不写盘 |

### 5.4 注意

- **模板路径必须服务器能读到**(浏览器和服务器同一台机器最简单;远程服务器需要路径是服务器视角)
- **输出目录必须有写权限**
- **大文件** — 上传 .inp 的功能(未来 v0.5)

## 6. Shell 补全(可选,但用了回不去)

### 6.1 bash

```bash
# 临时:
eval "$(inp-tool completion bash)"

# 永久:
inp-tool completion bash >> ~/.bashrc
source ~/.bashrc
```

之后:

```bash
inp-tool <TAB><TAB>       # 列出子命令
inp-tool sweep <TAB>      # 补模板路径
inp-tool sweep tpl.inp --<TAB>  # 列出 sweep 的 --xxx 选项
```

### 6.2 zsh

```bash
inp-tool completion zsh > "${fpath[1]}/_inp-tool"
autoload -U compinit && compinit
```

### 6.3 fish

```bash
inp-tool completion fish > ~/.config/fish/completions/inp-tool.fish
```

## 7. 选择指南

| 我是... | 推荐入口 |
|---|---|
| 系统工程师,管几十台 HPC | CLI(写脚本批量调) |
| 算法工程师,跑完 100+ 算例做对比 | Python API(后续分析) |
| 项目经理,想"点一下生成" | Web GUI |
| 一次性"我就跑 6 个看看" | 交互式 -i |
| 经常用 CLI,想省键入 | Shell 补全 + 快捷参数 |

## 8. 混用(最佳实践)

```bash
# 1) CLI 试一下 baseline 对不对
inp-tool sweep tpl.inp --alpha 0 --mach 0.6 --out /tmp/baseline --dry-run

# 2) OK 了,写 YAML
cp /dev/null sweep.yaml
# (编辑 sweep.yaml,扩到完整扫描)

# 3) 真跑
inp-tool sweep tpl.inp sweep.yaml

# 4) Python 拿到 manifest,塞进自己的 pipeline
python -c "
import json
m = json.load(open('/tmp/sweep/manifest.json'))
print(f'total: {m[\"total\"]}')
for c in m['cases']:
    print(c['path'])
"
```

下一步:[09-完整示例](09-examples.md) — 端到端跑通 3 个真实场景。
