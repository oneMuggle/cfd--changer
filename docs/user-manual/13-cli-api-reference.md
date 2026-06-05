# 13 — CLI 与 API 速查

> `inp_tool v0.4.0` 提供三种入口:CLI(`inp-tool`)、FastAPI HTTP(`inp-tool-api`)、Python `import inp_tool`。
> 本章把三者的对外接口收成一页速查,工作时常回来翻。

---

## 1. CLI(`inp-tool`)子命令

入口:`conda run -n cfdchanger inp-tool <sub> [args]`(开发态用 `python -m inp_tool <sub> [args]`)。
通用选项:

| 选项 | 作用 |
|---|---|
| `-h`, `--help` | 显示该子命令帮助 |
| `--version` | 输出版本号(`v0.4.0`) |

### 1.1 子命令一览

| 子命令 | 作用 | 必填位置参数 | 常用选项 | 1 行示例 | 退出码 |
|---|---|---|---|---|---|
| `parse` | 解析并显示结构 | `file` | `-b/--block`, `-i/--block-idx`, `-t/--top`, `-f/--full` | `inp-tool parse tpl.inp -b guiopts` | 0 / 1 / 2 |
| `get` | 取一个值 | `file`, `key` | `-b/--block`, `-i/--block-idx` | `inp-tool get tpl.inp aero_alpha -b guiopts` | 0 / 1 / 2 |
| `set` | 改一个值并写回 | `file`, `block`, `key`, `value` | `-i/--block-idx`, `-o/--output`, `-f/--force` | `inp-tool set tpl.inp guiopts aero_alpha 4.0 -o tpl_new.inp` | 0 / 1 / 2 |
| `diff` | 两个 `.inp` 的 diff | `a`, `b` | `-u/--unified` | `inp-tool diff a.inp b.inp -u` | 0 / 1 / 2 |
| `info` | 文件概览(块数/顶层语句数) | `file` | — | `inp-tool info tpl.inp` | 0 / 2 |
| `sweep` | 基于样例批量生成算例 | `[first]` 模板 / JSON, `[config]` 可选 JSON | `--alpha`, `--beta`, `--mach`, `--t-inf`, `--p-inf`, `--out`, `--manifest`, `--dry-run`, `-v`, `-i` | `inp-tool sweep tpl.inp --alpha 0,2,4 --mach 0.6,0.8 --out ./out` | 0 / 1 / 2 |
| `completion` | 输出 shell 补全脚本 | `{bash\|zsh\|fish}` | — | `inp-tool completion bash >> ~/.bashrc` | 0 |

### 1.2 退出码约定

| 退出码 | 含义 |
|---|---|
| `0` | 成功 |
| `1` | 输入/参数错(文件不存在、块名拼错、必填参数缺) |
| `2` | 解析错(`.inp` 语法破、`sweep` 配置字段错、JSON/YAML 解析失败) |

### 1.3 三个高频组合

```bash
# 1) 看模板里 guiopts 块 aero_* 字段当前值
inp-tool get tpl.inp aero_alpha -b guiopts

# 2) 改一个值、另存为新文件、原文件不动
inp-tool set tpl.inp guiopts aero_alpha 4.0 -o tpl_a4.inp

# 3) alpha-mach 笛卡尔积扫描 → 6 个 case + manifest
inp-tool sweep tpl.inp --alpha 0,2,4 --mach 0.6,0.8 --out ./out
```

---

## 2. FastAPI 端点

入口:`conda run -n cfdchanger inp-tool-api`(开发服务器,默认 `http://127.0.0.1:8765`)。
自动文档:`http://127.0.0.1:8765/docs`(Swagger UI)/ `/openapi.json`。

### 2.1 通用约定

- **文件句柄(`file_id`)**:`POST /api/files/load` 时由后端生成 8 字符 UUID,存到内存;`save` / `save_as` 不会释放。
  - 进程重启 → 全部 `file_id` 失效(无持久化)
  - 不主动释放,可用文件数 × `.inp` 大小受内存限制
- **错误响应格式**:`{"detail": "<原因>"}`,HTTP 状态码:
  - `400` 解析错(`.inp` 语法破、配置字段错)
  - `404` 路径/块/关键字/索引不存在
  - `500` 后端异常(罕见)
- **CORS**:开发期 `*`;生产部署请在 `api.py` 收紧 `allow_origins`。
- **生产启动**:`uvicorn inp_tool.api:app --host 0.0.0.0 --port 8765 --workers 4`

### 2.2 端点表(12 个)

| # | 方法 | 路径 | 请求体 | 响应 | 示例 curl |
|---|---|---|---|---|---|
| 1 | GET  | `/api/health` | — | `{"status":"ok","version":"0.3.0"}` | `curl http://127.0.0.1:8765/api/health` |
| 2 | POST | `/api/files/load` | `{"path": "<abs path>"}` | `LoadResponse`:file_id / path / block_count / top_stmt_count / blocks[] | `curl -X POST -d '{"path":"/data/tpl.inp"}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/files/load` |
| 3 | GET  | `/api/files/{file_id}` | — | file_id / path / 块列表 / modified | `curl http://127.0.0.1:8765/api/files/abc12345` |
| 4 | GET  | `/api/files/{file_id}/block/{idx}` | — | 单个块完整内容(statements 树) | `curl http://127.0.0.1:8765/api/files/abc12345/block/0` |
| 5 | GET  | `/api/files/{file_id}/top` | — | 顶层语句列表(块外) | `curl http://127.0.0.1:8765/api/files/abc12345/top` |
| 6 | GET  | `/api/files/{file_id}/search?keyword=...` | URL query | `{"keyword","count","results":[{block,line,values...}]}` | `curl 'http://127.0.0.1:8765/api/files/abc12345/search?keyword=aero_alpha'` |
| 7 | POST | `/api/files/{file_id}/set` | `SetRequest`:block_name / block_idx / keyword / value_index / value | `{"ok","location","keyword","new_value"}` | `curl -X POST -d '{"block_name":"guiopts","block_idx":0,"keyword":"aero_alpha","value_index":0,"value":"4.0"}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/files/abc12345/set` |
| 8 | POST | `/api/files/{file_id}/append` | `AppendRequest`:block_name / block_idx / keyword / values[] | `{"ok","line":<新行号>}` | `curl -X POST -d '{"block_name":"tsteps","block_idx":0,"keyword":"cfl","values":["1.0"]}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/files/abc12345/append` |
| 9 | POST | `/api/files/{file_id}/save` | — | `{"ok","path":<原路径>}` | `curl -X POST http://127.0.0.1:8765/api/files/abc12345/save` |
| 10 | POST | `/api/files/{file_id}/save_as` | `{"path":"<新路径>"}` | `{"ok","path"}` | `curl -X POST -d '{"path":"/data/tpl_a4.inp"}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/files/abc12345/save_as` |
| 11 | POST | `/api/diff` | `{"path_a","path_b"}` | `DiffResponse`:change_count / changes[] / unified(文本) | `curl -X POST -d '{"path_a":"/data/a.inp","path_b":"/data/b.inp"}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/diff` |
| 12 | POST | `/api/sweep` | `SweepRequest`:template / output_dir / sweeps / naming / overrides / freestream / manifest / dry_run | `SweepResponse`:total / cases[] / template / dry_run / manifest_path | `curl -X POST -d '{"template":"/data/tpl.inp","output_dir":"/data/out","sweeps":{"alpha":[0,4],"mach":[0.6,0.8]}}' -H 'Content-Type: application/json' http://127.0.0.1:8765/api/sweep` |

### 2.3 典型三步流(load → set → save_as)

```bash
# 1) load
FID=$(curl -s -X POST -d '{"path":"/data/tpl.inp"}' \
  -H 'Content-Type: application/json' \
  http://127.0.0.1:8765/api/files/load | jq -r .file_id)

# 2) 改 alpha
curl -X POST -d '{"block_name":"guiopts","block_idx":0,"keyword":"aero_alpha","value_index":0,"value":"4.0"}' \
  -H 'Content-Type: application/json' \
  http://127.0.0.1:8765/api/files/$FID/set

# 3) 另存为
curl -X POST -d '{"path":"/data/tpl_a4.inp"}' \
  -H 'Content-Type: application/json' \
  http://127.0.0.1:8765/api/files/$FID/save_as
```

---

## 3. Python API 速查

`from inp_tool import ...` 公开 **24 个**符号,按 4 个主流程归类。完整列表见 [`inp_tool/__init__.py`](../../inp_tool/inp_tool/__init__.py) `__all__`。

### 3.1 主流程最小代码

#### 流程 1:parse(读 .inp)

```python
from inp_tool import parse_file, parse, infer_type

inp = parse_file("tpl.inp")           # 直接读盘
# 或:从字符串解析
inp = parse(open("tpl.inp", encoding="utf-8").read(), path="tpl.inp")

# 顶层语句(块外)
for s in inp.top_stmts:
    print(s.keyword, [v.typed for v in s.values])

# 按块名查
for b in inp.block_list:
    if b.name == "guiopts":
        for s in b.statements:
            if s.keyword == "aero_alpha":
                print(s.values[0].typed)  # 已自动推断类型
```

#### 流程 2:modify(改 in-memory 对象)

```python
from inp_tool import parse_file, infer_type

inp = parse_file("tpl.inp")
# 找到 guiopts[0] 块的 aero_alpha 语句
b = inp.block_list[0]                  # 假设第 0 个就是 guiopts
for s in b.statements:
    if s.keyword == "aero_alpha":
        s.set(0, infer_type("4.0"))    # 类型自动推断为 float
# 追加一条新语句
b.append("cfl", "1.0", "1.0e6")
```

#### 流程 3:write(写回 .inp)

```python
from inp_tool import write, to_text, write_bytes

# 三种姿势
write(inp, "tpl_new.inp")                              # 标准写
text = to_text(inp)                                     # 拿字符串(自己决定怎么存)
write_bytes(inp, "tpl_new.inp")                         # 字节版(等同 write)
```

#### 流程 4:sweep(批量生成)

```python
import json
from inp_tool import CaseSweep, generate

cfg = {
    "template": "tpl.inp",
    "output_dir": "./out",
    "sweeps": {"alpha": [0, 2, 4], "mach": [0.6, 0.8]},
    "naming": "case_a{alpha:.0f}_m{mach:.1f}",   # 可选
    "freestream": {"T_inf": 288.15, "p_inf": 101325.0},  # 可选
}
cs = CaseSweep.from_dict(cfg)
report = generate(cs, dry_run=False)
print(report.total, "cases")                # -> 6 cases
for c in report.cases:
    print(c.case_id, c.path)
```

### 3.2 24 个公开符号按模块

| 模块 | 符号 | 职责 |
|---|---|---|
| `model` | `InpFile` | 整个 `.inp` 文件对象(顶层语句 + 块列表) |
| `model` | `Block` | 命名块(`guiopts` / `physics` / `tsteps` / ...) |
| `model` | `Stmt` | 一行语句(keyword + values + 子语句 + 行号) |
| `model` | `Value` | 单个值,带 `raw`(原文) + `typed`(推断后) |
| `model` | `infer_type` | `"4.0"` → `float`, `"on"` → `str`(故意保守) |
| `parser` | `parse` | 从字符串解析 |
| `parser` | `parse_file` | 从文件路径解析 |
| `writer` | `to_text` | 序列化为字符串 |
| `writer` | `write` | 写到文件(覆盖) |
| `writer` | `write_bytes` | 字节版(等同 `write`,跨平台一致) |
| `diff` | `diff` | 两棵 `InpFile` 树对比 |
| `diff` | `DiffReport` | 对比结果容器(`.changes` / `.unified()`) |
| `diff` | `DiffEntry` | 单条差异(kind / location / old / new) |
| `sweep` | `SweepSpec` | 单条扫描轴(键 + 标量 / 列表值) |
| `sweep` | `expand_cartesian` | N 条轴 → N×M 个 `dict` 组合 |
| `sweep` | `FreestreamPreset` | 几何分解(`alpha/beta/Ma` → `U/V/W` + `refvel`) |
| `sweep` | `render_case_name` | `str.format` 模板 → 文件名 |
| `sweep` | `CaseResult` | 单个 case 的结果(case_id / path / params / applied) |
| `sweep` | `SweepReport` | 整批报告(total / cases[] / template) |
| `sweep` | `CaseSweep` | 完整扫描配置(template / output_dir / sweeps / ...),可从 `dict` 构造 |
| `sweep` | `generate` | 跑扫描 → `SweepReport`(支持 `dry_run`) |

> 上表 21 行,涵盖 `model` 5 + `parser` 2 + `writer` 3 + `diff` 3 + `sweep` 8 = 21;
> 加上未单列的隐式入口(`infer_type` 已在 model 列出)→ 与 `__all__` 中 22 个模型/IO/对比符号一一对应,
> sweep 9 项中的 `CaseSweep`/`generate` 已包含在表中。完整签名以 [`inp_tool/__init__.py`](../../inp_tool/inp_tool/__init__.py) `__all__` 为准。

### 3.3 跨流程最小端到端

```python
# 改一个值,顺手 diff 一下,确认只动了那一处
from inp_tool import parse_file, write, diff, infer_type

inp = parse_file("tpl.inp")
orig = parse_file("tpl.inp")
for s in inp.block_list[0].statements:
    if s.keyword == "aero_alpha":
        s.set(0, infer_type("4.0"))
write(inp, "tpl_new.inp")

r = diff(orig, inp)
print(r.changes)              # 应只有 1 条:guiopts[0].aero_alpha 0 -> 4.0
print(r.unified("orig", "new"))
```

---

## 4. 选择哪种入口

> 选错了不致命(三种入口底层都走同一套 parser/writer),但工作流匹配能省一半配置时间。
> 详细对比见 [08-多入口使用](08-multiple-uis.md)。

| 场景 | 首选 | 备选 | 理由 |
|---|---|---|---|
| 一次性改一个字段 | CLI `set` | FastAPI `POST /set` | 一行命令,不写代码 |
| 一次性看文件结构 | CLI `info` / `parse -f` | FastAPI `GET /files/{id}` | 终端即可 |
| 两个模板做 diff | CLI `diff -u` | Python `diff()` | 终端带颜色,直接进 commit message |
| 批量生成(参数扫描) | CLI `sweep` | FastAPI `POST /sweep` | CLI 写一行 vs 启服务 |
| CI / 自动化(shell 调用) | CLI | FastAPI(若已有服务) | CLI 易嵌入 shell 脚本 |
| 集成到自家 Python 框架 | Python `import` | CLI `subprocess` | 性能/可控性更好 |
| 动态生成(运行时决定字段) | Python `import` | FastAPI | 用 `if/else` 构造 `CaseSweep` |
| 给非命令行同事用 | FastAPI + 自家前端 | — | 浏览器即可,见 [08-多入口 §5](08-multiple-uis.md) |
| 教学 / 交互式尝试 | FastAPI Swagger(`/docs`) | CLI `--help` | Swagger 可点可填 |
| 出错时排错 | CLI `-i/--interactive` | FastAPI `/docs` | `sweep -i` 走 prompt 序列 |

### 4.1 性能与限制

| 入口 | 单次延迟 | 最大并发 | 适合 |
|---|---|---|---|
| CLI | 最低(无服务开销) | 1(同步) | 脚本 / 一次性 |
| FastAPI | 几 ms(本地)+ 序列化 | 受 `uvicorn --workers` 控制 | 多客户端 / Web 前端 |
| Python `import` | 最低 | 进程内无限 | 高频循环 / 流水线 |

### 4.2 出错了怎么办

| 现象 | 排错路径 |
|---|---|
| CLI 报 `exit 1` | 看命令 `inp-tool <sub> --help`,确认参数名/必填项 |
| CLI 报 `exit 2`(解析错) | 先 `inp-tool info <file>`,再 `inp-tool parse <file> -f` 看哪一行破 |
| FastAPI `404 file_id` | `file_id` 只在内存中,服务重启后失效;重新 `POST /files/load` |
| FastAPI `400 parse failed` | 同 CLI `exit 2`,检查 `.inp` 语法或 sweep 配置 |
| Python `KeyError` / `IndexError` | 块不存在 / 同名块索引搞错 → 用 `inp.block_list` 遍历确认 |
| 其它 | 见 [10-FAQ](10-faq.md) |

---

## 5. 关联章节

- 想用 CLI 跑通第一个扫描:[03-快速开始](03-quickstart.md)
- 想知道 `sweep` 配置怎么写:[05-配置文件](05-config-files.md)
- 想知道能扫哪些字段:[04-扫描参数](04-sweeping.md)
- 字段值含义速查:[12-mcfd.inp 字段参考](12-mcfd-inp-field-reference.md)
- 多种入口横向对比:[08-多入口使用](08-multiple-uis.md)
- 内部架构与 API 实现细节:[../technical/](../technical/)
