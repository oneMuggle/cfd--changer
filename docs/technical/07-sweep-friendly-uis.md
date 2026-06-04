# 07 — v0.4.1 友好入口

**对应版本:** v0.4.1  ·  **PR:** 与 PR #1 同分支

---

## 1. YAML 配置

### 1.1 安装

```bash
conda run -n cfdchanger pip install -e .[yaml]
# 或
pip install inp-tool[yaml]
```

`[yaml]` extras = `pyyaml>=6.0`(在 Python 3.8 兼容)。

### 1.2 YAML 示例

```yaml
# examples/sweep_demo.yaml
template: examples/mcfd_v2_modified.inp
output_dir: examples/sweep_cases
sweeps:
  alpha: [0.0, 4.0, 8.0]
  beta:  [0.0]
  mach:  [0.60, 0.80]
  T_inf: [288.15]
  p_inf: [101325.0]
naming: "case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}.inp"
manifest:
  path: examples/sweep_cases/manifest.json
freestream:
  enabled: true
  gamma: 1.4
  R: 287.05
```

### 1.3 用法

```bash
inp-tool sweep examples/sweep_demo.yaml --out /tmp/cases
```

CLI 自动识别 `.yaml` / `.yml` / `.json` 后缀。

### 1.4 Python API

```python
from inp_tool import CaseSweep
cs = CaseSweep.from_yaml("examples/sweep_demo.yaml")
```

缺 `pyyaml` 时给清晰提示:
```
ImportError: YAML support requires `pyyaml`. Install via:  pip install inp-tool[yaml]
```

### 1.5 测试

`tests/test_sweep_yaml.py` 8 个用例:加载、Unicode 保留、与 JSON 等价、空文件/坏语法/文件不存在/freestream disabled。

## 2. 交互式 CLI

### 2.1 触发

```bash
inp-tool sweep -i
```

### 2.2 流程

```
=== sweep 交互式配置(回车=接受默认值)===

模板 .inp 路径 [回车跳过必填]: examples/mcfd_v2_modified.inp
输出目录 [./sweep_cases]: /tmp/cases
攻角 alpha 扫描 (deg,逗号分隔) [0,4,8]: 0,2,4,6,8,10
侧滑角 beta 扫描 (deg,逗号分隔) [0]: -2,0,2
马赫 mach 扫描 (逗号分隔) [0.6,0.8]: 0.5,0.7,0.9
来流温度 T_inf K (单值或逗号列表) [288.15]:
来流压强 p_inf Pa (单值或逗号列表) [101325.0]:
命名模板 (空=auto): case_aoa{alpha:02.0f}_ma{mach:.2f}.inp
manifest 路径 (空=不写):
dry-run?(只打印不写盘) [y/N]: n
确认按上面配置生成? [Y/n]: y
[sweep] generated 27 cases -> /tmp/cases
  - case_aoa00_ma0.50.inp  (alpha=0.0 beta=0.0 mach=0.5 ...)
  ...
```

### 2.3 行为

- 全部字段有 default,**回车=接受**
- 模板路径**必填**(防止误操作)
- 文件不存在时循环提示
- 类型错误(int/float)自动重试
- y/N 输入循环(支持中文 是/否)
- 取消 = confirm 选 n → return None
- 输出 0/2 = 成功/取消,**不写盘**

### 2.4 非 TTY

`stdin` 是 pipe 时仍可用(用 heredoc 喂输入做 e2e 测试)。`sys.stdin is None` 时才报错(罕见的"无 stdin"环境)。

### 2.5 测试

`tests/test_sweep_interactive.py` 11 个用例:prompt/confirm 各种分支、用 `monkeypatch.setattr("builtins.input", ...)` 模拟。

## 3. Web GUI

### 3.1 入口

启动服务后,浏览器开 `http://127.0.0.1:8765/`,顶栏有"编辑器"和"批量生成"两个标签。

### 3.2 表单字段

| 字段 | 默认 | 备注 |
|---|---|---|
| 模板路径 | (空,必填) | Windows 路径 `D:\path\to\mcfd.inp` |
| 输出目录 | `./sweep_cases` | |
| alpha (deg) | `0,4,8` | 逗号分隔 |
| beta (deg) | `0` | |
| mach | `0.6,0.8` | |
| T_inf K | `288.15` | |
| p_inf Pa | `101325` | |
| naming 模板 | `case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}.inp` | |
| dry-run | 复选框 | 默认不勾 |

### 3.3 行为

- 点"生成" → `POST /api/sweep`(前端 fetch,无页面刷新)
- 成功后渲染返回的 `cases[]` 为表格
- 失败时显示红色错误(`!` 开头)
- 单值轴空时自动从 sweeps 字典中移除

### 3.4 测试

Web 端未写 Playwright e2e(可选)。后端 `POST /api/sweep` 有完整单测,Web 调它即可。手动验证:启动服务 → 浏览器开 → 切换标签 → 填表 → 生成 → 看返回。

## 4. Shell 补全

### 4.1 bash

```bash
# 临时启用
eval "$(inp-tool completion bash)"

# 永久
inp-tool completion bash >> ~/.bashrc
source ~/.bashrc
```

效果:`inp-tool <TAB><TAB>` 列出 `parse / get / set / diff / info / sweep / completion`,`inp-tool sweep -<TAB>` 列出 `--alpha --beta --mach --out --dry-run -i`...

### 4.2 zsh

```bash
inp-tool completion zsh > "${fpath[1]}/_inp-tool"
# 重启 shell 或:
autoload -U compinit && compinit
```

### 4.3 fish

```bash
inp-tool completion fish > ~/.config/fish/completions/inp-tool.fish
```

### 4.4 测试

`tests/test_completion.py` 6 个用例:三个 shell 各有输出,含正确关键字(`complete -F` / `#compdef` / `complete -c`),未知 shell 抛 `ValueError`。

## 5. 选择指南

| 用户 | 推荐入口 |
|---|---|
| 数据科学/ML 工程师 | Python API + Jupyter Notebook |
| 一次性临时跑 | CLI 快捷 `--alpha --beta --mach` |
| 复现性(同事/审稿) | JSON 或 YAML config + Git |
| 忘记参数名 | 交互式 `-i` |
| 非工程同事 | Web GUI |
| 经常用 CLI | 装 Shell 补全 |
| 批量跑 100+ 算例 | Python API(易断点/可观察) |

## 6. 组合用法

CLI + Python 混用:

```bash
# 1) CLI 跑通 baseline
inp-tool sweep tpl.inp --alpha 0 --mach 0.6 --out /tmp/baseline

# 2) Python 加载结果,跑扩展
python -c "
from inp_tool import parse_file
inp = parse_file('/tmp/baseline/case_0.0_0.0_0.6.inp')
print('aero_alpha =', inp.get('guiopts', 'aero_alpha'))
"

# 3) 覆盖某 case 的某字段
python -c "
from inp_tool import CaseSweep, generate
cs = CaseSweep.from_dict({
    'template': '/tmp/baseline/case_0.0_0.0_0.6.inp',
    'output_dir': '/tmp/refined',
    'sweeps': {'alpha': [0, 5, 10]},
    'overrides': {'tsteps.ntstep': 50000},
})
generate(cs)
"
```
