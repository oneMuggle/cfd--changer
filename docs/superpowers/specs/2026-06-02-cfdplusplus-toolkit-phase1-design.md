# cfdplusplus_toolkit — Phase 1 设计 (resid_tool 后处理)

| 字段 | 值 |
|---|---|
| **Spec 作者** | brainstorming session, 2026-06-02 |
| **状态** | 设计稿，待人工 review |
| **目标读者** | 后续 writing-plans 阶段（实现工程师） |
| **范围** | Phase 1 — `resid_tool` 新包 + 顶层目录重命名 |
| **不在范围** | 2D 截面 / 3D 体绘制（后续 Phase）、参数化扫描、几何/网格对接、HTML 报告 |

---

## 1. 背景与动机

`cfd++changer` 仓库目前以 **前处理**（`inp_tool` — mcfd.inp 解析/修改/diff 库 + CLI + FastAPI Web）和 **GUI 文档翻译** 为主。用户希望把它打造成"CFD++ 前处理 **和** 后处理"的一体化工具集。

`inp_tool` 已成熟（55 测试、80% 覆盖率、双 extras 依赖分层）。本次 Phase 1 **只新增 `resid_tool` 子包**（聚焦 1D 时间历史：残差曲线），并把仓库顶层目录从 `cfd++changer` 重命名为 `cfdplusplus_toolkit`，以表达"工具集"的品牌意图。

后续 Phase（不在本文档）将引入 2D/3D 场量可视化、参数化扫描、几何/网格对接、报告生成等。

---

## 2. 目标 / 非目标

### 2.1 目标 (Phase 1)

1. **新建 `resid_tool/`** Python 包，对称于 `inp_tool/`：
   - 解析 ASCII 残差 log（带表头 / `#` `!` 注释 / 空白分隔 / NaN 容错）
   - 提供 `ResidLog` / `Run` / `RunSet` 数据模型（stdlib only 核心）
   - 绘制时间历史对比曲线（PNG via matplotlib + 交互式 HTML via plotly）
   - 4 个 CLI 子命令：`info` / `plot` / `compare` / `export`
   - FastAPI Web 服务（端口 8766）+ 原生 JS 单页前端
   - ≥80% 行覆盖率，5 个 pytest 模块
2. **顶层目录重命名** `cfd++changer` → `cfdplusplus_toolkit`，所有文档 / 脚本硬编码路径同步更新
3. **保持 `inp_tool` 不变**：功能、API、CLI、测试、覆盖率全部维持

### 2.2 非目标 (Phase 1)

- 2D 截面 / 3D 体绘制 / 流线 / 动画
- 参数化扫描 / 拉丁超立方 / 正交试验
- 几何 / 网格导入（IGES / STEP / STL）
- HTML/PDF 报告生成
- 求解器调度（"按 case 跑 CFD++"）
- PyPI 发布（`inp_tool` 和 `resid_tool` 都不发布）

---

## 3. 范围

### 3.1 输入数据契约

- **单 run 目录**：`<run_dir>/` 包含
  - `mcfd.inp` （可选；用于通过 `inp_tool` 读取元数据）
  - `mcfd.resid` （默认残差 log；可通过 `--resid-file` 改名）
- **多 run 对比**：用户在 CLI / Web 显式列出多个 `<run_dir>`
- **残差 log 格式**：
  - UTF-8 编码（自动剥离 BOM）
  - CRLF / LF / CR 换行
  - 以 `#` 或 `!` 开头的整行视为注释（可配置）
  - 第一个非空非注释行 = 表头（按任意空白切分）
  - 后续非空行 = 数据，按空白切分，单元解析为 `float`（支持 `1e-5` `+Inf` `-Inf` `nan`）
  - 列数不一致 / 单元无法解析 → 记 warning，跳过该行 / 该单元（默认不抛错）

### 3.2 残差 log 样例（设计约束）

```
# CFD++ residuals, case: wing_aoa5, run 2026-06-01
# solver: CFD++ 14.0
# grid: 2.1M cells, CFL=0.5
iter   time      res_mass    res_mom_x   res_mom_y   res_mom_z   res_energy
0      0.0       1.234e-3    5.6e-4      4.3e-4      5.1e-4      8.7e-4
100    1.0e-3    8.7e-5      2.1e-5      1.9e-5      2.0e-5      6.5e-5
500    5.0e-3    2.1e-6      5.4e-7      4.9e-7      5.1e-7      1.7e-6
```

注：此为设计阶段约定的样例，**用户暂无真实样本**。如真实样本字段命名/格式有偏差，在 parser 单元测试与时间列启发式里扩展。

---

## 4. 架构

### 4.1 顶层目录布局（Phase 1 完成后）

```
cfdplusplus_toolkit/                 ← 顶层（git mv 自 cfd++changer/）
├── README.md                        ← 品牌名 + 顶层导航
├── docs/
│   ├── cfd-gui/                     ← 既有
│   ├── translation/                 ← 既有
│   ├── resid-tool/                  ← 新增：resid_tool 文档
│   │   ├── quickstart.md
│   │   ├── api.md
│   │   └── data-format.md
│   ├── _archive/
│   │   └── cleanup-plan-2026-06-02.md  ← 旧 cleanup-plan 归档
│   └── superpowers/
│       └── specs/
│           └── 2026-06-02-cfdplusplus-toolkit-phase1-design.md   ← 本文档
├── inp_tool/                        ← 既有（前处理核心）
├── resid_tool/                      ← 新增（后处理核心，Phase 1 范围）
│   ├── pyproject.toml
│   ├── README.md
│   ├── src/resid_tool/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── model.py
│   │   ├── parser.py
│   │   ├── plotter.py
│   │   ├── cli.py
│   │   ├── api.py
│   │   └── web/
│   │       ├── index.html
│   │       ├── app.js
│   │       └── style.css
│   └── tests/
│       ├── conftest.py
│       ├── test_parser.py
│       ├── test_model.py
│       ├── test_plotter.py
│       ├── test_cli.py
│       └── test_api.py
├── html/  html_cn/  gui_src_cn/     ← 既有
├── analysis_v2/                     ← 既有
└── scripts/                         ← 既有（更新硬编码路径）
```

### 4.2 运行时数据流

```
   <run_dir>/mcfd.inp  ─parse─►  inp_tool.InpFile  ─┐
                                                     ├─► Run{ meta, log }
   <run_dir>/mcfd.resid ─parse─►  resid_tool.ResidLog ┘
                                                     ↓
                                              RunSet (list[Run])
                                                     ↓
                                            plotter.plot_png() / plot_html()
                                                     ↓
                                              *.png | *.html
```

### 4.3 依赖分层

| Extras | 依赖 |
|---|---|
| 核心（`pip install resid_tool`） | stdlib only |
| `[plot]` | matplotlib, plotly |
| `[api]` | fastapi, uvicorn, pydantic |
| `[dev]` | pytest, pytest-cov, httpx, matplotlib, plotly |

`inp_tool>=0.3` 列入核心 `dependencies`（用于可选读 mcfd.inp 元数据，缺失不抛错）。

---

## 5. 数据模型 (`model.py`)

```python
@dataclass
class ResidLog:
    path: Path                       # 源文件
    columns: list[str]               # 表头列名（保留原始大小写）
    data: list[list[float]]          # N 行 × M 列
    header_comments: list[str]       # 解析时跳过的 # / ! 注释行
    parse_warnings: list[str]        # 非致命问题

    @property
    def n_rows(self) -> int: ...
    @property
    def n_cols(self) -> int: ...
    def col(self, name: str) -> list[float]: ...        # 按名取列
    def is_empty(self) -> bool: ...
    def time_column(self) -> str | None: ...            # 启发式检测 X 轴

@dataclass
class Run:
    path: Path                       # <run_dir>
    name: str                        # 显示名（默认 = path.name）
    log: ResidLog
    mcfd_meta: dict[str, Any]        # 来自 inp_tool；缺 mcfd.inp 时为 {}
    errors: list[str]                # 装载阶段非致命错误

@dataclass
class RunSet:
    runs: list[Run]

    def names(self) -> list[str]: ...
    def columns(self) -> set[str]: ...
    def get(self, name: str) -> Run: ...
    def filter(self, predicate) -> RunSet: ...
    def time_column(self) -> str | None:
        """若所有 run 共享同一时间列名 → 返回该名；否则返回 None（plotter 将各 run 用各自的 X 轴）。"""
```

### 5.1 时间列检测（按优先级）

1. 列名 ∈ {`time`, `t`, `physical_time`, `iter`, `step`, `n`} → 视为 X 轴
2. 用户显式 `RunSet.plot(x="column_name")` 覆盖
3. 否则默认第一列 + 警告

### 5.2 `Run.name` 来源

- `--label "name=<display>"` 自定义
- 否则 `path.name`（最后一段目录名）
- 重复 basename 时加 `parent/basename` 消歧

### 5.3 `mcfd_meta` 内容（只读）

```python
def _load_mcfd_meta(run_dir: Path) -> dict:
    inp = run_dir / "mcfd.inp"
    if not inp.exists():
        return {}
    try:
        from inp_tool import parse_file
        parsed = parse_file(inp)
        return {
            "case_name": parsed.get("physics", "gasnam"),
            "ntstep":    parsed.get("tsteps", "ntstep"),
            "cflbot":    parsed.get("tsteps", "cflbot"),
        }
    except Exception as e:
        return {"_inp_error": str(e)}
```

缺 mcfd.inp / inp_tool 缺失 / 解析失败 → 不抛错，`mcfd_meta={}` 或 `{"_inp_error": ...}`。

---

## 6. 解析器 (`parser.py`)

### 6.1 公共 API

```python
def parse_file(path: str | Path, *, delimiter: str | None = None,
               comment_prefixes: tuple[str, ...] = ("#", "!"),
               encoding: str = "utf-8",
               strict: bool = False) -> ResidLog:
    """解析单个残差 log。

    strict=True 时首个错误即抛 ParseError；
    strict=False (默认) 时非致命问题写入 ResidLog.parse_warnings。
    """
```

### 6.2 解析规则

1. 编码默认 UTF-8，自动剥离 BOM
2. CRLF / LF / CR 都接受
3. 以 `#` 或 `!` 开头的整行跳过（`comment_prefixes` 可改）
4. 空行跳过
5. 表头 = 第一个非空非注释行；列名按 `delimiter` 切分（默认任意空白）
6. 数据行按 `delimiter` 切分；解析为 `float`（支持 `1e-5` `+Inf` `-Inf` `nan`）
7. 列数不一致 → `parse_warnings`（`strict=True` 抛 `ParseError`）
8. 重复列名 → 重命名 `col` / `col_2` / `col_3`，记 warning
9. 整列 NaN → 保留，记 warning
10. 混合制表符/空格 → `re.split(r'\s+', line.strip())`

### 6.3 错误处理矩阵

| 情况 | 行为 |
|---|---|
| 文件不存在 | 抛 `FileNotFoundError` |
| 编码错误 | 抛 `UnicodeDecodeError`（提示换 encoding） |
| 表头缺失（直接是数字） | 抛 `ParseError("no header found")` |
| 全部行被注释 | 抛 `ParseError("no data rows")` |
| 单行列数不符 | warning + 跳过该行 |
| 单元无法解析为 float | warning + 该单元置 `NaN` |
| 单列全 NaN | warning，保留列 |
| 文件 > 100 MB | warning，提示用 iterrows 模式（v0.2） |

---

## 7. 绘图器 (`plotter.py`)

### 7.1 公共 API

```python
def plot_png(runs: RunSet, *, x: str | None = None,
             columns: list[str] | None = None,
             out: str | Path, log_y: bool = True,
             title: str | None = None,
             dpi: int = 120) -> Path: ...

def plot_html(runs: RunSet, *, x: str | None = None,
              columns: list[str] | None = None,
              out: str | Path, log_y: bool = True,
              title: str | None = None) -> Path: ...

def plot_compare_png(runs: RunSet, *, columns: list[str],
                     out_dir: str | Path,
                     log_y: bool = True) -> list[Path]: ...
```

### 7.2 设计要点

1. **多 run 颜色映射**：matplotlib `tab10` 色板，按 `runs.names()` 顺序循环；图例 = `run.name`
2. **每图变量数**：
   - `plot_png` / `plot_html` 默认一个 figure 包含**所有**列（共享 X 轴 + 子图网格 `ceil(√M) × ⌈M/√M⌉`）
   - `plot_compare_png` 把每列**拆成单图**（10+ 列时更可读）
3. **X 轴**：默认 `RunSet.time_column()`（run 共享同一 X 列名才用，否则各 run 用各自的）；用户可显式覆盖
4. **Y 轴**：`log_y=True` 默认（残差用对数）
5. **Y 轴 ≤ 0 在 log 模式下**：warning + clip 到 `1e-30`（不抛错）
6. **空数据**：warning + 跳过该 run
7. **输出文件名**：
   - `plot_png` 单图：`{out_prefix}.png`
   - `plot_html` 单图：`{out_prefix}.html`
   - `plot_compare_png` 多图：`{out_prefix}_{col_sanitized}.png`
8. **HTML 交互**（plotly）：可隐藏曲线、缩放、hover 数值、导出 PNG
9. **样式**：
   - PNG：matplotlib `seaborn-v0_8-whitegrid`
   - HTML：plotly 默认白色主题

### 7.3 依赖边界

- 内部不依赖 numpy（`zip(*data)` 切列）
- matplotlib / plotly 导入在函数内 `try/except ImportError`，给友好提示
- `resid_tool.plotter` 暴露 `is_available() -> bool` 探测

---

## 8. CLI (`cli.py`)

### 8.1 命令

```bash
# 单/多 run 信息
resid-tool info <run_dir> [...]  [--resid-file mcfd.resid]

# 单 run 画图
resid-tool plot <run_dir>
  [--resid-file mcfd.resid]
  --out out.png | out.html              # 扩展名决定 png/html
  [--columns col1,col2,...]             # 默认全部
  [--x column]                          # 默认启发式
  [--linear]                            # 关闭 log_y
  [--title TEXT]

# 多 run 对比
resid-tool compare <run_dir> [...]
  [--resid-file mcfd.resid]
  --out-prefix PATH                     # 无扩展名；按格式加后缀
  [--format png,html,both]              # 默认 both
  [--columns col1,col2,...]
  [--x column] [--linear] [--title TEXT]
  [--per-column]                        # 每列单独成图

# 残差 log 解析 → CSV / JSON
resid-tool export <run_dir>
  --format csv | json
  --out out.csv | out.json
```

### 8.2 顶层行为

- `resid-tool --version` → `0.1.0`
- `resid-tool --help` → 各子命令帮助（argparse）
- **无参数 / 错误参数** → 退出码 `2` + 提示到 stderr
- **解析失败 run** → 退出码 `1` + warning 到 stderr（不阻断）
- **全部成功** → 退出码 `0`

### 8.3 标签管理

- 多 run 时按路径 basename 自动赋名；重复 basename → `parent/basename` 消歧
- `--label "name=<display>"` 自定义：
  ```bash
  resid-tool compare runA runB --label "runA=baseline" --label "runB=with_fins"
  ```

### 8.4 与 inp_tool CLI 对称

| 维度 | inp_tool | resid_tool |
|---|---|---|
| console_script | `inp-tool` | `resid-tool` |
| 入口模块 | `python -m inp_tool` | `python -m resid_tool` |
| 主命令动词 | `info / parse / get / set / diff` | `info / plot / compare / export` |
| `--help` 风格 | argparse | argparse |

---

## 9. Web / API (`api.py` + `web/`)

### 9.1 启动

```bash
pip install -e resid_tool/[api]
python -m resid_tool.api             # http://127.0.0.1:8766
# 或
resid-tool-api                       # console_script
```

> 端口：inp_tool 用 8765，resid_tool 用 8766，可同时跑。

### 9.2 REST 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 静态 HTML 首页 |
| `GET` | `/docs` | OpenAPI 文档（FastAPI 自带） |
| `GET` | `/api/runs?paths=<csv>` | 返回 `[{name, path, columns, n_rows, errors}]` |
| `GET` | `/api/runs/{name}/column/{col}` | 返回 `{x: [...], y: [...]}` |
| `GET` | `/api/plot.png?runs=<csv>&cols=<csv>&x=<col>&linear=<bool>` | 流式返回 PNG |
| `GET` | `/api/plot.html?runs=<csv>&cols=<csv>&x=<col>&linear=<bool>` | 返回 plotly 嵌入 HTML |
| `POST` | `/api/export` | body: `{runs, columns, format}` → 下载 CSV / JSON |

### 9.3 前端 (`web/`)

- 单页 `index.html` + 少量原生 JS（不引框架）
- UI：
  - **多选 run**：文件夹浏览 + 列表
  - **多选列**：自动从 `/api/runs` 拉取并集
  - **X 轴选择**：默认 `time` / `iter`，下拉
  - **输出格式切换**：PNG / HTML
  - **生成按钮** → 调 `/api/plot.*` → 内嵌 `<img>` 或 `<iframe>`
- 复用 `inp_tool/web/` 样式（CSS 变量统一）

### 9.4 安全 & 限制

- **路径白名单**：默认只接受 *API server 启动时所在目录（`os.getcwd()`）* 的子目录（防任意文件读）
- **CLI 启动加 `--allow-path <dir>`** 可放宽白名单（可多次指定；接受多个根目录）
- **文件大小**：`/api/plot.*` 检查 run_dir 总体积；>500 MB 拒绝 + 提示
- **超时**：plot 渲染 > 30s → 504
- **跨域**：默认同源，`--cors-origins` 启动参数放宽

---

## 10. 错误处理

### 10.1 错误级别

| 级别 | 类型 | 行为 |
|---|---|---|
| **Fatal** | `ParseError`, `FileNotFoundError`, `UnicodeDecodeError` | 抛异常，CLI 退出码 2 |
| **Per-Run Error** | 单 run 解析失败、列缺失、空 log | `Run.errors` 记录，warning 到 stderr，CLI 退出码 1 |
| **Soft Warning** | 重复列名、单行坏、列全 NaN、文件过大、Y 轴含 0/负值用 log | `parse_warnings` 记录，**默认不打印**，需 `--verbose` 才显示 |

### 10.2 异常层次

```python
class ResidToolError(Exception): ...
class ParseError(ResidToolError): ...
class PlotError(ResidToolError): ...
class IncompatibleRunsError(ResidToolError): ...
```

### 10.3 CLI 退出码

| 退出码 | 含义 |
|---|---|
| `0` | 全部成功 |
| `1` | 部分 run 失败（输出物仍生成） |
| `2` | 参数错误 / fatal 异常 |

### 10.4 Web 端点错误

- 4xx：参数错（路径白名单违反、列名不存在）
- 5xx：内部错（绘图失败、文件 IO）
- 错误体统一：`{"error": "<msg>", "detail": "<optional>"}`

### 10.5 日志

- CLI 默认 WARNING 级别；`--verbose` → INFO；`-vv` → DEBUG
- Web 走 uvicorn 自身的 logger

---

## 11. 测试策略

### 11.1 目标

- **行覆盖率 ≥ 80%**（与 inp_tool 对齐）
- **5 个 pytest 模块** 对应 5 个核心组件
- 1 个外部样本回归（`-m external` 模式，目录不存在自动 skip）

### 11.2 模块划分

```
resid_tool/tests/
├── conftest.py                 # 共享 fixture
├── test_parser.py              # 解析器（核心，约 25 用例）
├── test_model.py               # Run / RunSet 行为（约 10 用例）
├── test_plotter.py             # plot_png / plot_html（约 8 用例；tmpdir 验证文件 + 字节大小）
├── test_cli.py                 # CLI 端到端（约 10 用例；subprocess.run 调 console_script）
└── test_api.py                 # FastAPI TestClient（约 8 用例；与 inp_tool 一致）
```

### 11.3 关键 fixture

- `simple_resid_log(tmp_path)`：5 列 100 行标准 ASCII log
- `comment_only_header_log`：只有 `#` 注释 + 1 行表头 + 1 行数据
- `malformed_log`：混合有效行 + 坏行（列数不一致）→ 验证 `parse_warnings`
- `multi_run_dir`：3 个子目录，每个含 1 个 resid log
- `noisy_log`：含 NaN / Inf / 重复列名 → 验证各种 warning
- `real_sample_dir`：`pytest -m external` 模式，从 `RESID_DIR` 环境变量读

### 11.4 覆盖维度

| 维度 | 测什么 |
|---|---|
| 正常路径 | 解析 → 模型 → 绘图 → CLI 端到端 |
| 边界 | 空文件、零行、零列、单值、巨大数 (1e300)、极小数 (1e-300) |
| 错误 | 文件不存在、编码错、表头缺失、CLI 错误参数 |
| 多 run | 3 run 对比、时间列一致/不一致、空 run 跳过 |
| 性能（软目标） | 100k 行 log 解析 < 2s；10k 行 plot_png < 5s |
| API | 200 / 4xx / 5xx；路径白名单违反；CORS |

---

## 12. 顶层重命名

### 12.1 改动清单

| 改动 | 位置 |
|---|---|
| 目录改名 | `git mv cfd++changer/ cfdplusplus_toolkit/` |
| 根 `README.md` | 改品牌名 + 项目描述（"CFD++ 前处理 + 后处理工具集"） |
| `docs/cleanup-plan.md` | 归档为 `docs/_archive/cleanup-plan-2026-06-02.md`（标"已执行"） |
| `scripts/translate_*.py` | 顶部硬编码 Windows 路径更新 |
| `analysis_v2/analyzer11.py` | 路径引用更新 |
| `inp_tool/README.md` | `cfd++changer` → `cfdplusplus_toolkit` |
| `inp_tool.egg-info/` | 删掉，rebuild |
| `pyproject.toml`（inp_tool） | `name` 不变（仍 `inp_tool`），README 引用换名 |

### 12.2 风险

- 脚本硬编码路径改起来琐碎但不复杂
- 不影响 `inp_tool` 包对外接口（CLI / API 不变）

### 12.3 Commit 策略

- `rename: cfd++changer → cfdplusplus_toolkit` 单 commit
- `feat(resid_tool): 初始 0.1.0 实现` 单 commit（或拆成子模块多个 commit）
- 总收尾 commit `docs: 更新 README 反映新品牌名 + resid_tool 文档`

---

## 13. Phase 1 验收清单

### 13.1 包与代码

- [ ] `resid_tool/` 包结构齐全：`pyproject.toml` / `README.md` / `src/resid_tool/` / `tests/`
- [ ] 核心 stdlib only；`[plot]` `[api]` `[dev]` extras 完整
- [ ] 4 个 CLI 子命令 + argparse help
- [ ] FastAPI 8766 端口可启动；OpenAPI 文档可访问
- [ ] 原生 JS 单页可加载、列出 run、选列、生成图

### 13.2 测试

- [ ] 5 个 pytest 模块全部通过
- [ ] `pytest --cov=resid_tool --cov-report=term-missing` ≥ 80%
- [ ] `pytest -m "not external"` 跳过外部样本时仍全过
- [ ] `inp_tool` 55 个测试全过、覆盖率不变

### 13.3 文档与重命名

- [ ] 根 `README.md` 反映新品牌名 + 顶层目录地图
- [ ] `docs/resid-tool/` 三份文档（quickstart / api / data-format）就位
- [ ] 文档无死链
- [ ] 顶层目录从 `cfd++changer/` → `cfdplusplus_toolkit/`
- [ ] 翻译脚本 / 分析脚本硬编码路径同步更新
- [ ] `git log` 显示 rename commit + resid_tool commit + 文档收尾

---

## 14. 后续 Phase（不在本文档）

| Phase | 主题 | 简述 |
|---|---|---|
| 2 | 2D/3D 场量可视化 | PLT / Tecplot 解析、截面云图、流线、体绘制 |
| 3 | 参数化扫描 | Jinja 模板 + sweep + RunSet 增强 |
| 4 | 几何/网格对接 | IGES / STEP / STL 转换、网格统计、边界层检查 |
| 5 | 报告 | HTML/PDF 报告（嵌图 + 工况对比 + 摘要） |
| 6 | PyPI 发布 | `inp_tool` 和 `resid_tool` 发到 PyPI |

---

## 15. 开放问题（待真实样本验证）

1. 残差 log 的列名规范（CFD++ 实际用 `RMS_DENSITY` / `RES_MASS` / `mass_res` 还是其他？）—— 需真实样本
2. 时间列名（CFD++ 是 `time` / `phys_time` / `iter` / `step` 还是其他？）—— 需真实样本
3. 文件体积（典型单个 case 残差 log 多大？100MB 警告阈值是否合理？）—— 需真实样本
4. mcfd.inp 中哪些字段值得放入 `mcfd_meta`（用户最关心的展示元数据）—— Phase 1 取 `gasnam` / `ntstep` / `cflbot`，后续按反馈扩展

Phase 1 实施时若拿到真实样本，**优先在 parser 单元测试 + 时间列启发式里扩展**，不阻塞其他模块开发。
