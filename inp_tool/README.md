# inp_tool — mcfd.inp 解析 / 修改 / diff 工具 v0.3

mcfd.inp 是 CFD++ 求解器的输入文件格式。本工具提供:
- **解析**  → `InpFile` 数据结构(支持重复同名块、多行 values 复合语句)
- **修改**  → 按 `block.keyword` 改值,自动推断类型
- **round-trip**  → 写回时保留行尾注释
- **diff**  → 两个文件的语义差异报告
- **FastAPI 后端**  → REST API + 浏览器 GUI(`inp_tool.api`)

## Install

```bash
cd inp_tool

# 核心(parser / writer / diff / CLI,无额外依赖)
pip install -e .

# 含 FastAPI 后端(fastapi / uvicorn / pydantic)
pip install -e .[api]

# 含开发工具(pytest / pytest-cov / httpx for TestClient)
pip install -e .[dev]
```

安装后可用:
- **`inp-tool`** console script(同 `python -m inp_tool`)
- **`python -m inp_tool`** 入口
- **`python -m inp_tool.api`** 或 **`python run_server.py`** 启动 Web GUI(http://127.0.0.1:8765)

## v0.2 修复的 4 个限制

| 限制 | 修复 |
|---|---|
| 多行 `values` 每行作为独立 Stmt | 复合 Stmt,后续 `values` 行挂载到 `seq.#` 的 `children` 列表 |
| 重复同名块只保留最后一次 | `InpFile.block_list` 保留全部;`all_blocks(name)` 取所有同名 |
| 行尾注释在 round-trip 重排 | `comment_after` 始终保留并接回 |
| 字符串值带空格按空白分 | 已支持 `{...}` 和 `"..."` 引号字符串 |

## 快速使用

### Python API

```python
from inp_tool import parse_file, write, diff
from inp_tool.writer import to_text

# 读
inp = parse_file('case.inp')
print(inp.get('tsteps', 'cflbot'))        # 0.001
print(inp.get('physics', 'gasnam'))      # 'Air'

# 修改
inp.set('tsteps', 'cflbot', 0.005)
inp.set('tsteps', 'ntstep', 50000)
inp.set('physics', 'gasnam', 'N2')
inp.set('physics', 'refvel', 50.0)

# 写(UTF-8, LF 换行)
write(inp, 'case_new.inp')

# 读文本(不写盘)
text = to_text(inp)

# 重复同名块(例如 mcfd.inp 的 system 出现 2 次)
sys_blocks = inp.all_blocks('system')   # -> [Block, Block, ...]

# 复合语句(info set 的 seq.# + values)
seq_stmts = [s for s in inp.top_stmts if s.keyword.startswith('seq')]
first = seq_stmts[0]
print(first.values_raw)                 # seq.# 的主行 values
for c in first.children:                # 后续多行 values
    print(c.values_raw)

# diff
orig = parse_file('case.inp')
new = parse_file('case_new.inp')
r = diff(orig, new)
print(r)                  # 详细
print(r.unified('old', 'new'))   # unified 风格
```

### CLI

```bash
# 块列表
python -m inp_tool.cli info mcfd.inp

# 显示某个块的内容
python -m inp_tool.cli parse mcfd.inp -b tsteps -f
python -m inp_tool.cli parse mcfd.inp -b system -i 1  # 第二个同名 system

# 取值
python -m inp_tool.cli get mcfd.inp cflbot -b tsteps
python -m inp_tool.cli get mcfd.inp gasnam -b physics

# 改值
python -m inp_tool.cli set mcfd.inp tsteps cflbot 0.005 -o case_new.inp
python -m inp_tool.cli set mcfd.inp physics gasnam N2
python -m inp_tool.cli set mcfd.inp system mc_filecopy a.bin b.bin -i 0  # 改第一个 system

# diff
python -m inp_tool.cli diff old.inp new.inp
python -m inp_tool.cli diff old.inp new.inp -u
```

## 数据模型

```
InpFile
├── header_comments: list[str]
├── block_list: list[Block]         # 全部块,按出现顺序,同名都保留
├── top_stmts: list[Stmt]
├── top_decor: list[(line, str)]
├── tail_lines: list[str]
└── (兼容) blocks: dict[name, list[Block]]

Block
├── name, begin_line, end_line
├── statements: list[Stmt]
├── pre_comments, trailing_comments: list[str]

Stmt
├── keyword, values: list[Value]
├── children: list[Stmt]            # 多行 values 复合语句
├── line, raw, comment_after

Value
├── raw, typed
```

## 测试

```bash
cd inp_tool
pip install -e .[dev]                          # 含 pytest + pytest-cov + httpx

# 跑全部测试(55 个)
pytest -v

# 跑全部 + 覆盖率
pytest --cov=inp_tool --cov-report=term-missing

# 跳过需要外部 INP_DIR (E:\softwareData\edge\download\inp) 的 4 个真实样本回归
pytest -m "not external"
```

55 个测试全过(parser / writer / diff / cli / api 五大模块,加上 4 个外标记的真实样本回归测试,目录不存在时自动 skip)。整体行覆盖率 **≥80%**(plan 目标)。

## v0.4 新增:批量算例生成 (sweep)

基于一个 mcfd.inp 样例,扫描 (alpha, beta, mach, ...) 一次生成 N 个变体 + 一份 manifest 索引。

### 多种用户友好入口 (v0.4.1)

| 入口 | 命令 | 适用 |
|---|---|---|
| Python API | `from inp_tool import CaseSweep, generate` | 集成到自己脚本 |
| CLI (JSON) | `inp-tool sweep examples/sweep_demo.json` | 标准用法 |
| CLI (YAML) | `inp-tool sweep examples/sweep_demo.yaml` | 手写更友好,需 `[yaml]` extras |
| CLI (交互) | `inp-tool sweep -i` | 忘记参数名时一步步问 |
| CLI (快捷) | `inp-tool sweep tpl.inp --alpha 0,4,8 --mach 0.6,0.8` | 临时一次性 |
| Web GUI | 浏览器 `http://127.0.0.1:8765/`,切"批量生成"标签 | 不爱写命令行的同事 |
| Shell 补全 | `inp-tool completion bash >> ~/.bashrc` | Tab 补全子命令 |

#### YAML 配置示例

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

#### 交互式 CLI

```bash
$ inp-tool sweep -i
=== sweep 交互式配置(回车=接受默认值)===

模板 .inp 路径 [回车跳过]: examples/mcfd_v2_modified.inp
输出目录 [./sweep_cases]: /tmp/my_cases
攻角 alpha 扫描 (deg,逗号分隔) [0,4,8]:
侧滑角 beta 扫描 (deg,逗号分隔) [0]: -2,0,2
马赫 mach 扫描 (逗号分隔) [0.6,0.8]: 0.5,0.7,0.9
来流温度 T_inf K (单值或逗号列表) [288.15]:
来流压强 p_inf Pa (单值或逗号列表) [101325.0]:
命名模板 (空=auto):
manifest 路径 (空=不写):
dry-run?(只打印不写盘) [y/N]: n
确认按上面配置生成? [Y/n]: y
[sweep] generated 27 cases -> /tmp/my_cases
```

#### Shell 补全

```bash
# bash
inp-tool completion bash >> ~/.bashrc && source ~/.bashrc
# zsh
inp-tool completion zsh > "${fpath[1]}/_inp-tool"
# fish
inp-tool completion fish > ~/.config/fish/completions/inp-tool.fish
```

### Python API

```python
from inp_tool import CaseSweep, FreestreamPreset, generate

cs = CaseSweep.from_dict({
    "template": "examples/mcfd_v2_modified.inp",
    "output_dir": "examples/sweep_cases",
    "sweeps": {
        "alpha": [0, 4, 8],          # deg
        "beta":  [0],
        "mach":  [0.6, 0.8],
        "T_inf": [288.15],            # K(单值,辅助)
        "p_inf": [101325.0],          # Pa(单值,辅助)
    },
    "naming": "case_aoa{alpha:02.0f}_b{beta:02.0f}_ma{mach:.2f}.inp",
    "manifest": {"path": "examples/sweep_cases/manifest.json"},
    "freestream": {"enabled": True, "gamma": 1.4, "R": 287.05},
})

report = generate(cs)        # -> SweepReport (6 cases by cartesian 3*1*2)
print(f"generated {report.total} cases")
for c in report.cases:
    print(f"  - {c.case_id}  alpha={c.params['alpha']}  mach={c.params['mach']}")
```

### CLI

```bash
# 用 JSON 配置文件
inp-tool sweep examples/mcfd_v2_modified.inp examples/sweep_demo.json --out examples/sweep_cases

# 或用 --alpha / --beta / --mach 快捷参数
inp-tool sweep examples/mcfd_v2_modified.inp \
    --alpha 0,4,8 --beta 0 --mach 0.6,0.8 \
    --t-inf 288.15 --p-inf 101325 \
    --out examples/sweep_cases \
    --manifest examples/sweep_cases/manifest.json

# Dry run(只打印不写盘)
inp-tool sweep examples/sweep_demo.json --dry-run
```

### FastAPI

```bash
curl -X POST http://127.0.0.1:8765/api/sweep \
     -H "Content-Type: application/json" \
     -d @examples/sweep_demo.json
# -> {"total": 6, "cases": [...], "template": "...", ...}
```

### FreestreamPreset 公式

`aero_u / aero_v / aero_w` 自动按几何分解:

```
a = sqrt(gamma · R · T_inf)
U = Ma · a · cos(α) · cos(β)
V = Ma · a · sin(β)
W = Ma · a · sin(α) · cos(β)
refvel = sqrt(U² + V² + W²)        # 模长 = Ma·a
```

同时更新 `guiopts.aero_alpha/beta/ma/u/v/w/temp/pres` 与 `physics.refvel/reftem/refpre`。

> 假设 α 在 Y-Z 平面(影响 W)、β 在 X-Z 平面(影响 V)。如果你的 CFD++ 版本定义不同,可以在 `freestream: {enabled: false}` 关闭 preset,只用 `overrides` 字段手动改 `aero_u/v/w`。

### 命名规则

`naming` 模板是 Python `str.format()` 风格,占位符 = sweep 字段名。单值轴(如 `T_inf`)不必出现在命名中;多值轴必须出现,否则报错。冲突时自动追加 `_1`, `_2`...

### 完整测试

```bash
# Phase 1-5 全部 sweep 测试(sweep / generate / cli / api 四个模块)
pytest tests/test_sweep.py tests/test_sweep_generate.py tests/test_sweep_cli.py tests/test_sweep_api.py -v
```

## 已知限制 (v0.2 残留)

- 多行 values 只能配 seq.# / seq# 模式(其他复合头需扩展)
- 重复块按出现位置配对,如果 a/b 文件同名块数量不同会报 remove/add
- to_text 输出总是重构造(不保留原文件的空白风格,如 tab/空格混用)
- 没有 schema 验证(无效的 keyword/值不会报错)

## 路线图

- v0.3: JSON/YAML 互转(便于跨工具协作)
- v0.4: 批量算例生成器(sweep)✅ **已完成**
- v0.5: 集成到现代 GUI(后续项目)
