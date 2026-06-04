# 08 — 测试与质量门

**测试框架:** pytest 8  ·  **目标覆盖率:** ≥80%(sweep 自身 ≥90%)

---

## 1. 测试结构

```
inp_tool/tests/
├── conftest.py             # 共享 fixture
├── test_api.py             # FastAPI 既有端点(8 端点)
├── test_cli.py             # CLI 既有子命令 + version
├── test_diff.py            # diff 模块
├── test_parser.py          # mcfd.inp 解析
├── test_sweep.py           # ⭐ SweepSpec / FreestreamPreset / 命名 / 数据结构
├── test_sweep_generate.py  # ⭐ CaseSweep 配置 / generate() 主流程
├── test_sweep_cli.py       # ⭐ inp-tool sweep 子命令
├── test_sweep_api.py       # ⭐ POST /api/sweep
├── test_sweep_yaml.py      # ⭐ YAML 加载 (v0.4.1)
├── test_sweep_interactive.py # ⭐ 交互式 CLI (v0.4.1)
├── test_completion.py      # ⭐ Shell 补全 (v0.4.1)
└── test_writer.py          # mcfd.inp 写回
```

⭐ = 新增(sweep + 友好层)

## 2. 测试统计

| 阶段 | 测试数 | 涵盖 |
|---|---|---|
| v0.4 核心 | 54 | sweep 数据模型 / generate / CLI / API |
| v0.4.1 友好层 | 25 | YAML / 交互式 / 补全 |
| **合计 sweep** | **79** | — |
| 既有 inp_tool | 55 | parser / writer / diff / cli / api |
| **总计** | **134** | 4 skip(外部 INP_DIR 缺失) |

## 3. 覆盖率报告

```
Name                   Stmts   Miss  Cover
----------------------------------------------------
inp_tool/sweep.py        246    17    93%   ← 本模块重点
inp_tool/cli.py          269    49    82%
inp_tool/api.py          255    40    84%
inp_tool/parser.py       126    21    83%
inp_tool/writer.py        69     5    93%
inp_tool/diff.py          94    25    73%
inp_tool/model.py        163    48    71%
inp_tool/__init__.py       6     0   100%
inp_tool/__main__.py       4     0   100%
----------------------------------------------------
TOTAL                   1286   241    81%   ← 整体 81% (≥80% 目标)
```

`sweep.py` 未覆盖行(17 行,主要是 `_iso_now` 时间戳 + 几个边界 case,详见 `Missing` 列)。

## 4. 关键测试设计

### 4.1 FreestreamPreset 公式验证

每个公式用 3 组独立 case 验证:

```python
def test_refvel_is_mach_times_speed_of_sound(self):
    preset = FreestreamPreset(gamma=1.4, R=287.05)
    for alpha, beta in [(0, 0), (5, 3), (10, -4), (-2, 2)]:
        params = {"alpha": alpha, "beta": beta, "mach": 0.7, "T_inf": 300.0}
        uvw = preset.compute_uvw(params)
        a = math.sqrt(1.4 * 287.05 * 300.0)
        refvel = math.sqrt(uvw["U"]**2 + uvw["V"]**2 + uvw["W"]**2)
        assert math.isclose(refvel, 0.7 * a, rel_tol=1e-9)
```

### 4.2 round-trip 验证

```python
def test_round_trip_preserves_alpha_in_generated_inp(self, ...):
    report = generate(sweep)
    case = report.cases[0]
    re_parsed = parse_file(case.path)
    assert re_parsed.get("guiopts", "aero_alpha") == expected_alpha
```

### 4.3 交互式 CLI 用 monkeypatch

```python
def test_minimal_run(self, monkeypatch, tmp_path):
    answers = iter([
        str(tpl), str(out), "0,4,8", "0", "0.6,0.8",
        "", "", "", "", "n", "y",
    ])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    cfg = build_sweep_config_interactive()
    assert cfg["sweeps"]["alpha"] == [0.0, 4.0, 8.0]
```

### 4.4 subprocess 跑 CLI

```python
def test_sweep_runs_with_config_file(self, sweep_config, tmp_path):
    rc, out, err = _run_cli("sweep", str(sweep_config))
    assert rc == 0
    assert len(list((tmp_path / "cases").glob("*.inp"))) == 4
```

### 4.5 FastAPI TestClient

```python
def test_sweep_runs_and_returns_report(self, client, template_inp, tmp_path):
    r = client.post("/api/sweep", json={...})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 4
    assert len(data["cases"]) == 4
```

## 5. 端到端验证(每次发布前必跑)

```bash
# 1) 全套测试
conda run -n cfdchanger pytest tests/ -q
# 期望: 134 passed, 4 skipped (外部 INP_DIR 缺失)

# 2) 覆盖率
conda run -n cfdchanger pytest tests/ --cov=inp_tool --cov-report=term
# 期望: sweep.py ≥ 90%, 整体 ≥ 80%

# 3) JSON CLI
conda run -n cfdchanger python -m inp_tool.cli sweep examples/sweep_demo.json --out /tmp/e2e_json
# 期望: 6 case + manifest

# 4) YAML CLI
conda run -n cfdchanger python -m inp_tool.cli sweep examples/sweep_demo.yaml --out /tmp/e2e_yaml
# 期望: 6 case

# 5) 交互式 CLI
TPL=examples/mcfd_v2_modified.inp
echo -e "$TPL\n/tmp/e2e_i\n0,4,8\n0\n0.6,0.8\n\n\n\nn\ny" \
  | /home/fz/anaconda3/envs/cfdchanger/bin/python -m inp_tool.cli sweep -i
# 期望: 6 case

# 6) Shell 补全
conda run -n cfdchanger python -m inp_tool.cli completion bash | head -3
# 期望: "# bash completion for inp-tool"

# 7) 抽查关键字段(几何分解验证)
grep -E "^aero_(alpha|u|w|ma) " /tmp/e2e_json/case_aoa04_b00_ma0.60.inp
# 期望:
#   aero_alpha 4.0
#   aero_ma    0.6
#   aero_u     203.67...  (= 0.6 * 340.3 * cos(4°))
#   aero_w     14.24...   (= 0.6 * 340.3 * sin(4°))
```

## 6. CI 集成建议(待办)

```yaml
# .github/workflows/ci.yml
name: tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: conda-incubator/setup-miniconda@v3
        with:
          environment-file: environment.yml
      - run: conda install -n cfdchanger -c conda-forge python=3.8
      - run: conda run -n cfdchanger pip install -e .[api,dev,yaml]
      - run: conda run -n cfdchanger pytest tests/ --cov=inp_tool --cov-fail-under=80
```

## 7. 性能基准(开发机参考)

| 算例数 | parse | deepcopy | preset | overrides | write | 总计 |
|---|---|---|---|---|---|---|
| 10 | 0.05s | 0.01s | 0.001s | <0.001s | 0.05s | 0.1s |
| 100 | 0.05s | 0.10s | 0.01s | 0.01s | 0.5s | 0.7s |
| 1000 | 0.05s | 1.0s | 0.1s | 0.1s | 5s | 6.3s |
| 10000 | 0.05s | 10s | 1s | 1s | 50s | 62s |

瓶颈:磁盘 IO(每个 case 写 50KB),SSD 上 10000 case ~1 分钟。

## 8. 已知测试 gap

| 项 | 原因 | 缓解 |
|---|---|---|
| `apply` 物理 `refpre` 单测未覆盖 | `p_inf` 未传入时跳过 | 已有 E2E 验证 |
| `web/index.html` UI 无 e2e | Playwright 未集成 | 手动浏览器验证 |
| `completion zsh` 端到端不可用 | 容器无 zsh | 输出文本断言 |
| 真实 INP_DIR 回归测试 skip | Windows 路径硬编码 | `--external` 标记,生产环境启用 |
