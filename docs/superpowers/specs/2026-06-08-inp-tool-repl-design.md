# inp-tool REPL — 设计文档

**日期**: 2026-06-08
**作者**: brainstorming with user
**Status:** ✅ 已实现 v0.7.1 (commit 40dbdbf)
**目标版本**: inp-tool v0.5.0

---

## 1. 目标

为 `inp-tool` 添加一个交互式 shell(REPL)子命令,使用户可以:

- 一次加载一个或多个 `.inp` 文件,在同一会话中反复探索、读取、修改、比对
- 用短命令操作当前文件,不必重复键入子命令名、文件路径
- 在多文件之间切换,做 diff、对比、调参
- 缓冲修改,显式 `save` 才写盘,避免误操作
- 撤销最近修改(undo)
- 设定会话变量并在命令中插值(例如 sweep 参数)
- 在 REPL 中直接执行 shell 命令(shell escape)

预期体验接近 Claude Code / opencode 风格:一个"进入"即用的环境,而不是每次手动起新进程。

## 2. 非目标(YAGNI 划线)

明确不在本版本实现:

- 远程文件 / git 集成
- 多 tab / split pane / TUI 框架(textual/prompt_toolkit)
- 语法高亮 / 主题 / 颜色
- 插件机制
- 撤销树(只支持线性 undo)
- readline 之外的高级编辑模式(vi/emacs)

## 3. 入口

新增子命令 `inp-tool shell`:

```bash
$ inp-tool shell                              # 空进入
$ inp-tool shell mcfd_v1.inp mcfd_v2.inp     # 预加载两个文件
```

预加载时,每个路径的默认 alias = `Path(path).stem`(去后缀),若冲突自动追加 `_2` / `_3` / ... 并提示用户。

启动后:

```
inp-tool v0.5.0 interactive shell. Type 'help' for commands, 'exit' to quit.
inp>
```

## 4. 架构

### 4.1 新增/改动文件

```
inp_tool/
├── cli.py            # 改 1 处:加 `shell` 子命令,委托到 repl.main()
├── repl.py           # 新增:ShellREPL(cmd.Cmd),命令分发
├── repl_state.py     # 新增:ReplSession / LoadedFile / UndoLog
├── repl_completer.py # 新增:InpCompleter,Tab 补全器
├── repl_history.py   # 新增:~/.inp_history 读写
└── tests/
    ├── test_repl.py            # 新增
    ├── test_repl_state.py      # 新增
    ├── test_repl_completer.py  # 新增
    └── test_repl_history.py    # 新增
```

### 4.2 复用原则

`cli.py` 已有的 `cmd_<name>(args)` handler 函数(8 个:`parse / get / set / diff / info / sweep / completion`)在 REPL 中**直接复用**。REPL 把每条命令字符串解析成 `argparse.Namespace`,再调对应 handler。

因此 `cli.py` 实际改动只有一处:

```python
# 现有 main() 中,sub.add_parser 块尾追加:
sshell = sub.add_parser('shell', help='进入交互式 shell (REPL)')
sshell.add_argument('files', nargs='*', help='启动时预加载的文件(自动按 basename 起别名)')
# ... 现有子命令全部保留 ...
# 末尾:
def cmd_shell(args):
    from .repl import main as repl_main
    repl_main(args.files)
```

`completion` 子命令在 REPL 中**不暴露**(REPL 自身的 Tab 补全已经覆盖,避免重复)。

### 4.3 模块职责

| 模块 | 职责 | 不做的事 |
|---|---|---|
| `repl_state.py` | 纯数据类 + 状态变更方法(load / unload / set / undo) | 不知道有 REPL 存在,无 IO |
| `repl.py` | 继承 `cmd.Cmd`,分发命令字符串,调用 state 方法,捕获 stdout 输出 | 不直接做补全(history) |
| `repl_completer.py` | 给定 (session, 当前 token, 上下文) → 返回候选词列表 | 不修改 session |
| `repl_history.py` | 读 / 写 `~/.inp_history`,行数上限 1000,跨平台降级 | 不存命令执行结果 |

## 5. 状态模型

### 5.1 数据类(`repl_state.py`)

```python
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

@dataclass
class LoadedFile:
    alias: str                  # 'v1' 或 Path(path).stem
    path: Path                  # 原始路径
    inp: InpFile                # 解析后的模型(parser.parse_file)
    dirty: bool = False         # 是否有未保存修改
    last_saved_text: Optional[str] = None  # 用于 diff 与 undo 基线

@dataclass
class UndoEntry:
    alias: str
    block: str
    key: str
    old_values: list            # 改前值,可能为多 token

class UndoLog:
    """线性 undo,只回滚 set 改的 (alias, block, key)"""
    def __init__(self, maxlen: int = 100):
        self._entries: Deque[UndoEntry] = deque(maxlen=maxlen)
    def push(self, entry: UndoEntry) -> None: ...
    def pop(self) -> Optional[UndoEntry]: ...
    def __len__(self) -> int: ...

@dataclass
class ReplSession:
    files: Dict[str, LoadedFile] = field(default_factory=dict)
    current: Optional[str] = None
    undo: UndoLog = field(default_factory=UndoLog)
    variables: Dict[str, str] = field(default_factory=dict)
```

### 5.2 不变量

- `session.files` 任何 alias 必对应唯一 `LoadedFile`
- `session.current` 始终是 `session.files` 中已有的 alias(`None` 表示无文件)
- `set` 改变 `dirty = True`,并 push 一条 `UndoEntry`
- `save` 写盘成功后才清 `dirty` 并更新 `last_saved_text`
- `unload` 拒绝 dirty alias(除非显式 `-f`)

## 6. 命令集(REPL 内部)

### 6.1 完整命令表

| 命令 | 语法 | 行为 |
|---|---|---|
| `load` | `load <path> [as <alias>]` | 解析文件,加入 session,设为 current |
| `unload` | `unload <alias> [-f]` | 移除 alias(默认拒绝 dirty) |
| `files` | `files` | 列出所有 alias、path、状态、current 标记 |
| `use` | `use <alias>` | 切换 current 指针 |
| `status` | `status` | 每个 alias 的未保存 key/block 列表 |
| `save` | `save` / `save <alias>` / `save as <path>` | 写回磁盘 |
| `info` | `info` | 复用 `cmd_info`,作用于 current |
| `get` | `get <key> [-b BLOCK]` | 复用 `cmd_get`,作用于 current |
| `set` | `set <block> <key> <value>` | 复用 `cmd_set`,作用于 current,标记 dirty,push undo |
| `diff` | `diff <other>` | 复用 `cmd_diff`,左 = current,右 = other |
| `sweep` | `sweep --config <yaml>` | 复用 `cmd_sweep`;交互模式默认从 `session.variables` 取值 |
| `parse` | `parse` | 复用 `cmd_parse`,作用于 current |
| `undo` | `undo [N=1]` | 弹出最近 N 条 undo,逐条回滚 |
| `let` | `let <name>=<value>` | 存会话变量;语法与 `set` 完全不冲突,使用 `=` 作为标识 |
| `shell` | `! <cmd>` | subprocess.run,透传 stdout/stderr,exit code 非零时打印 |
| `history` | `history [N=20]` | 列出最近 N 条 |
| `rerun` | `!<N>` | 重新执行 history 第 N 条 |
| `help` | `help [<cmd>]` | 列出全部命令 / 显示具体命令语法 |
| `exit` / `quit` / EOF | | 退出;有 dirty 时提示 |

### 6.2 current 别名覆盖语法

任何操作命令前可加 `<alias>:` 前缀,显式指定目标,绕过 current:

```
inp> v1:get refvel -b physics
inp> v2:set physics refvel 75.0
inp> v1:diff v2
```

实现:REPL 在 `onecmd` 入口检测 `<word>:` 前缀,临时切换 `current`,再分发剩余部分。

### 6.3 变量插值

命令字符串中 `$name` 在分发前替换为 `session.variables[name]`:

- 未定义变量 → `error: undefined variable: $name`
- `$$` 转义为字面 `$`
- 不开启递归插值(替换后不再扫描)
- 路径中常用:`sweep --output $outdir` 若 `$outdir` 已设

### 6.4 sweep 在 REPL 中的特殊行为

`cmd_sweep` 已有 `build_sweep_config_interactive`(`_prompt` / `_confirm`),REPL 改造该路径:

- 提示用户输入时,先看 `session.variables` 中是否有同名 key,有则作为默认值
- 生成的算例文件**不进入** REPL session(用户如要继续探索某一份,可手动 `load`)

## 7. Tab 补全

### 7.1 补全器接口

```python
class InpCompleter:
    def __init__(self, session: ReplSession): self.session = session

    # 静态 / 全局
    def complete_command(self, text: str) -> List[str]: ...
    def complete_shell(self, text: str) -> List[str]: ...

    # 状态相关
    def complete_alias(self, text: str) -> List[str]: ...
    def complete_block(self, alias: str, text: str) -> List[str]: ...
    def complete_key(self, alias: str, block: str, text: str) -> List[str]: ...
```

### 7.2 分发表(基于 token 位置)

| 命令 | 参数位置 | 调用的 completor |
|---|---|---|
| 任意 | 第 1 token,且不含 `:` | `complete_command` |
| 任意 | 第 1 token 含 `:`(如 `v1:` 或 `v1:g`) | 拆分前缀,候选 = 已加载 alias 中以 `<prefix>:` 形式可成对者;若 `:` 后面有非空 text,再叠加 `complete_command` 在 `:` 后的部分 |
| `load` | path | 路径(用 stdlib) |
| `unload` / `use` / `save` | alias | `complete_alias` |
| `get` / `set` | `-b` 之后 | `complete_block(current)` |
| `get` / `set` | key(已带 `-b`) | `complete_key(current, block)` |
| `!` | 之后 | `complete_shell` |

### 7.3 边界

- 无 current 时,任何依赖 `current` 的补全直接返回 `[]`,不报错
- alias 不存在时同样返回 `[]`
- 补全候选若以 `text` 为前缀才返回,空 `text` 返回全部

## 8. 历史

### 8.1 文件位置与格式

- 路径:`~/.inp_history`
- 格式:每行一条命令,纯文本,无时间戳(MVP 简化)
- 上限 1000 行,超出 FIFO

### 8.2 生命周期

| 阶段 | 行为 |
|---|
| 启动 | 读 `~/.inp_history`,载入 readline buffer(Unix)或自管 deque(Win 降级) |
| 每条命令 | 执行后(无论成功失败)追加 |
| 退出 | 一次性写回 |

### 8.3 跨平台降级

- Unix / macOS:用 `readline` 模块
- Windows:探测 `pyreadline3` 或 `pyreadline`,有则用,无则纯内存 + `history` 命令
- 任何情况下 `history` 命令都能列出(从内存读)

## 9. 错误处理

### 9.1 错误展示样式

统一前缀 `error: `,后接一句话原因 + 上下文,REPL 不退出:

```
inp> get refvel -b physics
error: 'physics' is not a known block in 'v1'. available: iofiles, tsteps, options, octree, physics, probe, debug, guiopts
inp>
```

### 9.2 错误表

| 失败 | 消息 |
|---|---|
| 路径不存在 | `error: file not found: <path>` |
| 解析失败 | `error: parse failed at line <N>: <detail>` |
| key 找不到 | `error: key '<k>' not found in block '<b>'(available: ...)` |
| value 类型不匹配 | `error: cannot parse '<v>' as <type> for key '<k>'` |
| alias 未加载 | `error: alias '<a>' not loaded. type 'files' to see loaded.` |
| 写盘无权限 | `error: permission denied: <path>` |
| undo 空 | `nothing to undo` |
| shell 命令非零退出 | 打印 stderr,`exit code: N` |
| 变量未定义 | `error: undefined variable: $<name>` |
| sweep 部分成功 | 报告成功 N / 失败 M,逐个列失败原因 |

### 9.3 信号

| 触发 | 行为 |
|---|---|
| `Ctrl-C` 在命令执行中 | 取消该条,回 REPL 提示符(**不退出** REPL) |
| `Ctrl-D` 在空行 | 走 exit 流程 |
| exit 时有 dirty | `unsaved changes in: <aliases>. Exit anyway? [y/N]`,默认 N 取消退出 |

## 10. 测试

### 10.1 单元测试(目标覆盖率 ≥ 80%)

| 文件 | 覆盖点 |
|---|---|
| `test_repl_state.py` | `LoadedFile` dirty 跟踪;`UndoLog` push/pop/上限;`ReplSession` 切换 current |
| `test_repl.py` | `ShellREPL.onecmd(...)`:<br>• `load foo.inp` 后 `files` 列出<br>• `set` 标 dirty,`save` 清 dirty<br>• `undo` 回滚到原值<br>• `! ls` 透传 stdout<br>• dirty 时 exit 提示<br>• 错误命令不退出 REPL<br>• `<alias>:` 前缀覆盖 current<br>• `$var` 插值,未定义报错<br>• `let alpha=3.5` 存变量 |
| `test_repl_completer.py` | 补全正确性:命令 / alias / block / key / shell |
| `test_repl_history.py` | 读 / 写 ~/.inp_history,1000 行 FIFO,Win 降级路径 |

### 10.2 测试方法

- `cmd.Cmd` 是同步 stdin/stdout 类,测试用 `unittest.mock.patch('sys.stdout', new=io.StringIO())` + `onecmd('load foo.inp')`,然后断言 stdout
- 文件 fixture 走 `tmp_path`(pytest 内置)
- 避免 `pexpect`(跨平台脆弱),但若后续想做 e2e 可加 `[dev]` 依赖

### 10.3 集成 / smoke

CI 加一条非交互 smoke:`inp-tool shell < tests/data/repl_smoke.txt`,覆盖 `load → set → save → exit` 全流程,目标 < 2s。

## 11. 分发与 CI 影响

- `pyproject.toml` **无需改**(零新依赖,`cmd` / `readline` / `pathlib` 全是 stdlib)
- `scripts/build.sh` 重新 build 后,`inp-tool shell` 在 PyInstaller 单文件里照样工作
- 自测:本地 Linux + Windows 7(若可达)+ Win 10 三个平台都跑 smoke
- README 新增"REPL 模式"节,30 秒教学

## 12. 风险与缓解

| 风险 | 缓解 |
|---|---|
| `cmd.Cmd` 跨平台 readline 行为不一致 | 启动时探测;Win 自动 fallback 到内存 |
| undo 复杂、易出 bug | MVP 只回滚 `set`;`load` / `unload` / `save` 不入 undo 栈 |
| 变量插值在路径里被错误替换 | 显式 `$name` 语法,`$$` 转义,默认非递归 |
| PyInstaller onefile + readline 写 `~/.inp_history` | 走 `Path.home()` 绝对路径,自测覆盖 |
| REPL 启动慢影响 CI smoke | smoke 用单条 `load + exit`,目标 < 2s |
| `<alias>:` 前缀与未来 `set` 子命令语法冲突 | 限制前缀只用于 REPL 顶层,handler 内部不解析 |

## 13. 实施里程碑(供 plan 拆分)

1. `repl_state.py` + `test_repl_state.py`
2. `repl.py` 骨架 + `test_repl.py` 基础命令(load / files / use / save / exit),无补全无历史
3. 接 `cmd_*` handler(info / get / set / diff / parse)
4. `<alias>:` 前缀 + 变量插值 + `setvar` + `!` escape
5. `undo` 栈接入 set 流程
6. `sweep` 改造(读 `session.variables` 作默认)
7. `repl_completer.py` 全量补全
8. `repl_history.py` 持久化
9. CLI 接线 + CI smoke + 文档
10. 重 build + 平台自测

## 14. 开放问题(留待实现时决)

- 路径补全要不要支持 `~` 展开? stdlib `pathlib` 默认不展开,但可加。
- `history` 是否要加时间戳? MVP 纯文本,后续若用户要求再升。
- `let` 命令是否要加 `unset <name>` 配对? MVP 不加,`let <name>=` 清空也不必要(直接重启 REPL)。
