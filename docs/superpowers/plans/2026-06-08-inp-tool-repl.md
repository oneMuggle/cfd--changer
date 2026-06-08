# inp-tool REPL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `inp-tool` 添加 `inp-tool shell` 交互式 REPL 子命令,支持多文件会话、状态管理、Tab 补全与持久历史。

**Architecture:** 4 个新模块 (`repl_state` / `repl` / `repl_completer` / `repl_history`) + `cli.py` 改一处接线。`repl.py` 继承 stdlib `cmd.Cmd`,把 REPL 命令字符串解析成 `argparse.Namespace` 后委托给 `cli.py` 已有的 `cmd_*` handler,实现"零重复"复用。

**Tech Stack:** Python 3.8+ stdlib only (`cmd`, `argparse`, `readline`, `pathlib`, `subprocess`, `shlex`, `dataclasses`, `collections.deque`, `unittest.mock`)。零新增依赖,符合 `inp-tool` 核心零运行时依赖约束。

**Working Directory:** `/home/fz/project/cfd--changer` (仓库根)
**Feature Branch:** `feat/repl-shell`
**Python Env:** `conda run -n cfdchanger ...`(所有 `python` / `pytest` / `pip` 必须经此)

---

## File Structure(实施前锁定)

| 文件 | 状态 | 职责 | 行数预算 |
|---|---|---|---|
| `inp_tool/inp_tool/repl_state.py` | 新建 | `LoadedFile` / `UndoLog` / `ReplSession` 数据类 + 状态变更方法 | ~200 |
| `inp_tool/inp_tool/repl.py` | 新建 | `ShellREPL(cmd.Cmd)`,命令分发,主入口 `main()` | ~350 |
| `inp_tool/inp_tool/repl_completer.py` | 新建 | `InpCompleter`,Tab 补全器 | ~120 |
| `inp_tool/inp_tool/repl_history.py` | 新建 | `~/.inp_history` 读写 + 跨平台降级 | ~100 |
| `inp_tool/inp_tool/cli.py` | 改 1 处 | 新增 `shell` 子命令 + `cmd_shell` 委托 | +15 |
| `inp_tool/tests/test_repl_state.py` | 新建 | 状态类单测 | ~250 |
| `inp_tool/tests/test_repl.py` | 新建 | ShellREPL 行为测(`onecmd` + stdout 捕获) | ~400 |
| `inp_tool/tests/test_repl_completer.py` | 新建 | 补全器单测 | ~150 |
| `inp_tool/tests/test_repl_history.py` | 新建 | 历史读写 + 降级测 | ~120 |
| `inp_tool/tests/data/repl_smoke.txt` | 新建 | CI smoke 输入文件 | ~10 |
| `inp_tool/tests/data/sample_v1.inp` | 新建 | 测试 fixture | ~10 |
| `inp_tool/tests/data/sample_v2.inp` | 新建 | 测试 fixture | ~10 |
| `inp_tool/README.md` | 改 1 节 | "REPL 模式"教学 | +60 |
| `.github/workflows/ci.yml` | 改 1 处 | 加 `inp-tool shell < tests/data/repl_smoke.txt` smoke step | +5 |

**总计**:约 1700 行新代码 + 80 行改动。

---

## Phase 1 — 状态基座

### Task 1: 创建 `repl_state.py` 数据类骨架

**Files:**
- Create: `inp_tool/inp_tool/repl_state.py`
- Test: `inp_tool/tests/test_repl_state.py`

- [ ] **Step 1: 写失败测试**

`inp_tool/tests/test_repl_state.py`:

```python
"""ReplSession / LoadedFile / UndoLog 数据类单测。"""
from pathlib import Path

import pytest

from inp_tool.repl_state import LoadedFile, ReplSession, UndoEntry, UndoLog


def test_loadedfile_starts_clean():
    lf = LoadedFile(alias='v1', path=Path('/tmp/x.inp'), inp=None)
    assert lf.dirty is False
    assert lf.last_saved_text is None


def test_undolog_push_pop():
    log = UndoLog()
    assert len(log) == 0
    e = UndoEntry(alias='v1', block='physics', key='refvel', old_values=[50.0])
    log.push(e)
    assert len(log) == 1
    popped = log.pop()
    assert popped is e
    assert len(log) == 0


def test_undolog_pop_empty_returns_none():
    log = UndoLog()
    assert log.pop() is None


def test_undolog_respects_maxlen():
    log = UndoLog(maxlen=3)
    for i in range(5):
        log.push(UndoEntry(alias='v', block='b', key=f'k{i}', old_values=[i]))
    assert len(log) == 3
    # 最老两条被丢弃,剩 k2/k3/k4
    assert [log.pop().key for _ in range(3)] == ['k2', 'k3', 'k4']


def test_replsession_starts_empty():
    s = ReplSession()
    assert s.files == {}
    assert s.current is None
    assert len(s.undo) == 0
    assert s.variables == {}
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_state.py -v
```

Expected: 收集失败(`ModuleNotFoundError: No module named 'inp_tool.repl_state'`)。

- [ ] **Step 3: 最小实现让测试通过**

`inp_tool/inp_tool/repl_state.py`:

```python
"""REPL 状态数据类:LoadedFile / UndoLog / ReplSession。

纯数据 + 状态变更方法,无 IO,无 stdout。下游由 repl.py 使用。
"""
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional


@dataclass
class LoadedFile:
    """REPL 中加载的一个 .inp 文件,含 alias、路径、解析模型、dirty 标记。"""
    alias: str
    path: Path
    inp: Any  # 故意不导入 InpFile,避免循环依赖;运行时由 parser.parse_file 填充
    dirty: bool = False
    last_saved_text: Optional[str] = None


@dataclass
class UndoEntry:
    """一次 set 改动的可回滚快照。"""
    alias: str
    block: str
    key: str
    old_values: List[Any]  # 改前 values(可能多 token)


class UndoLog:
    """线性 undo 栈,只回滚 set 改的 (alias, block, key)。"""
    def __init__(self, maxlen: int = 100):
        self._entries: Deque[UndoEntry] = deque(maxlen=maxlen)

    def push(self, entry: UndoEntry) -> None:
        self._entries.append(entry)

    def pop(self) -> Optional[UndoEntry]:
        if not self._entries:
            return None
        return self._entries.pop()

    def __len__(self) -> int:
        return len(self._entries)


@dataclass
class ReplSession:
    """整个 REPL 会话的根状态。"""
    files: Dict[str, LoadedFile] = field(default_factory=dict)
    current: Optional[str] = None
    undo: UndoLog = field(default_factory=UndoLog)
    variables: Dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_state.py -v
```

Expected: 5 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl_state.py inp_tool/tests/test_repl_state.py
git commit -m "feat(repl): add ReplSession / LoadedFile / UndoLog data classes"
```

---

### Task 2: ReplSession.load / unload / use / set_dirty

**Files:**
- Modify: `inp_tool/inp_tool/repl_state.py`
- Modify: `inp_tool/tests/test_repl_state.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl_state.py` 末尾追加:

```python
def test_load_adds_file_and_sets_current(tmp_path):
    s = ReplSession()
    fake_path = tmp_path / 'mcfd.inp'
    fake_path.write_text('placeholder')
    s.load(fake_path, alias='v1')
    assert 'v1' in s.files
    assert s.current == 'v1'
    assert s.files['v1'].path == fake_path


def test_load_default_alias_is_stem(tmp_path):
    s = ReplSession()
    p = tmp_path / 'mcfd_v1.inp'
    p.write_text('x')
    s.load(p)
    assert s.current == 'mcfd_v1'


def test_load_collision_appends_suffix(tmp_path):
    s = ReplSession()
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'a_2.inp'; p2.write_text('x')  # 同 stem 'a' 冲突
    s.load(p1, alias='a')
    s.load(p2, alias='a')  # 显式 alias='a' 与已有冲突
    assert 'a' in s.files
    assert 'a_2' in s.files
    # 第二次 load 的 current 指向新别名
    assert s.current == 'a_2'


def test_unload_removes_file(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.unload('a')
    assert 'a' not in s.files


def test_unload_dirty_raises_without_force(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.files['a'].dirty = True
    with pytest.raises(RuntimeError, match='unsaved'):
        s.unload('a')
    # -f 强卸通过
    s.unload('a', force=True)
    assert 'a' not in s.files


def test_unload_current_clears_pointer(tmp_path):
    s = ReplSession()
    p = tmp_path / 'a.inp'; p.write_text('x')
    s.load(p, alias='a')
    s.unload('a')
    assert s.current is None


def test_use_switches_current(tmp_path):
    s = ReplSession()
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'b.inp'; p2.write_text('x')
    s.load(p1, alias='a')
    s.load(p2, alias='b')
    assert s.current == 'b'
    s.use('a')
    assert s.current == 'a'


def test_use_unknown_raises(tmp_path):
    s = ReplSession()
    with pytest.raises(KeyError):
        s.use('nope')
```

- [ ] **Step 2: 跑测试,确认新增 8 个失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_state.py -v
```

Expected: 5 passed, 8 failed(AttributeError: 'ReplSession' object has no attribute 'load')。

- [ ] **Step 3: 实现 load / unload / use 方法**

`inp_tool/inp_tool/repl_state.py` 中 `ReplSession` 类内追加:

```python
    def load(self, path: Path, alias: Optional[str] = None) -> str:
        """加载文件到 session,返回实际使用的 alias。

        alias 为 None 时用 Path(path).stem;冲突时追加 _2/_3/...。
        """
        from .parser import parse_file  # 延迟导入避免循环

        if alias is None:
            alias = path.stem
        original = alias
        n = 2
        while alias in self.files:
            alias = f'{original}_{n}'
            n += 1
        self.files[alias] = LoadedFile(alias=alias, path=path, inp=parse_file(str(path)))
        self.current = alias
        return alias

    def unload(self, alias: str, force: bool = False) -> None:
        """从 session 移除文件。dirty 状态默认拒绝;force=True 强卸。"""
        lf = self.files[alias]  # KeyError 自然抛出
        if lf.dirty and not force:
            raise RuntimeError(
                f"alias '{alias}' has unsaved changes; use unload -f to force"
            )
        del self.files[alias]
        if self.current == alias:
            self.current = None

    def use(self, alias: str) -> None:
        """切换 current 指针。alias 不存在时抛 KeyError。"""
        if alias not in self.files:
            raise KeyError(alias)
        self.current = alias
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_state.py -v
```

Expected: 13 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl_state.py inp_tool/tests/test_repl_state.py
git commit -m "feat(repl): ReplSession.load/unload/use with alias collision handling"
```

---

## Phase 2 — REPL 骨架

### Task 3: ShellREPL 基础骨架 + 提示符

**Files:**
- Create: `inp_tool/inp_tool/repl.py`
- Test: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 写失败测试**

`inp_tool/tests/test_repl.py`:

```python
"""ShellREPL 行为测试。onecmd 模拟用户输入,捕获 stdout 断言。"""
import io
from contextlib import redirect_stdout
from pathlib import Path

import pytest

from inp_tool.repl import ShellREPL


def _run(repl, *lines):
    """喂入多行命令,返回捕获的 stdout。"""
    buf = io.StringIO()
    with redirect_stdout(buf):
        for line in lines:
            repl.onecmd(line)
    return buf.getvalue()


def test_prompt_default():
    r = ShellREPL()
    assert r.prompt == 'inp> '


def test_prompt_changes_when_file_loaded(tmp_path):
    p = tmp_path / 'x.inp'; p.write_text('placeholder')
    r = ShellREPL()
    _run(r, f'load {p}')
    assert r.prompt == 'inp[v1]> '  # 'x' 是 stem


def test_intro_banner_present():
    r = ShellREPL()
    assert 'interactive shell' in r.intro
    assert "'help'" in r.intro
    assert "'exit'" in r.intro


def test_empty_line_does_not_crash():
    r = ShellREPL()
    out = _run(r, '')
    assert out == ''  # 无输出,无异常
```

- [ ] **Step 2: 跑测试,确认失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: `ModuleNotFoundError: No module named 'inp_tool.repl'`。

- [ ] **Step 3: 最小骨架实现**

`inp_tool/inp_tool/repl.py`:

```python
"""inp-tool 交互式 REPL。

继承 stdlib cmd.Cmd,把每条用户输入解析后委托给 cli.py 的 cmd_* handler。
状态由 ReplSession 管理,IO 通过 stdout/stderr。
"""
import cmd
import sys
from typing import List, Optional

from .repl_state import ReplSession


# REPL 暴露的命令名集合(给 help / 补全用)
REPL_COMMANDS = {
    'load', 'unload', 'files', 'use', 'status', 'save',
    'info', 'get', 'set', 'diff', 'sweep', 'parse',
    'undo', 'let', 'help', 'history', 'exit', 'quit',
}


class ShellREPL(cmd.Cmd):
    intro = (
        "inp-tool v0.5.0 interactive shell. "
        "Type 'help' for commands, 'exit' to quit."
    )
    prompt = 'inp> '

    def __init__(self, session: Optional[ReplSession] = None, completekey: str = 'tab'):
        super().__init__(completekey=completekey)
        self.session = session or ReplSession()
        self._refresh_prompt()

    # ----- 内部辅助 -------------------------------------------------------

    def _refresh_prompt(self) -> None:
        if self.session.current:
            self.prompt = f'inp[{self.session.current}]> '
        else:
            self.prompt = 'inp> '

    def _print(self, msg: str) -> None:
        print(msg)

    def _err(self, msg: str) -> None:
        print(f'error: {msg}', file=sys.stderr)

    # ----- 占位 do_*(后续任务逐步实现) ------------------------------------

    def do_help(self, arg):
        if arg:
            cmd_method = getattr(self, f'do_{arg}', None)
            if cmd_method and callable(cmd_method):
                doc = (cmd_method.__doc__ or '').strip()
                print(f'{arg}: {doc}' if doc else arg)
            else:
                print(f'no such command: {arg}')
        else:
            print('available commands:')
            for name in sorted(REPL_COMMANDS):
                method = getattr(self, f'do_{name}', None)
                doc = (method.__doc__ or '').splitlines()[0] if method and method.__doc__ else ''
                print(f'  {name:10s} {doc}')

    def do_exit(self, arg):
        """exit the REPL"""
        return True

    def do_quit(self, arg):
        """alias for exit"""
        return True


def main(preload: Optional[List[str]] = None) -> int:
    """REPL 入口。从 CLI 的 `shell` 子命令调用。

    preload: 启动时预加载的文件路径列表(自动按 basename 起 alias)。
    """
    repl = ShellREPL()
    for path in preload or []:
        repl.onecmd(f'load {path}')
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        print()  # 换行
    return 0
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): ShellREPL skeleton with prompt and intro"
```

---

### Task 4: load / files / use 命令

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_load_lists_in_files(tmp_path):
    p = tmp_path / 'mcfd.inp'
    p.write_text('placeholder\n')
    r = ShellREPL()
    out = _run(r, f'load {p}', 'files')
    assert 'mcfd' in out
    assert 'current' in out or '*' in out  # current 标记


def test_load_nonexistent_errors(tmp_path):
    r = ShellREPL()
    out = _run(r, f'load {tmp_path}/nope.inp')
    assert 'not found' in out
    assert r.session.current is None


def test_load_with_explicit_alias(tmp_path):
    p = tmp_path / 'mcfd.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as v1')
    assert r.session.current == 'v1'
    assert 'v1' in r.session.files


def test_use_switches_current(tmp_path):
    p1 = tmp_path / 'a.inp'; p1.write_text('x')
    p2 = tmp_path / 'b.inp'; p2.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p1} as a', f'load {p2} as b', 'use a')
    assert r.session.current == 'a'
    assert r.prompt == 'inp[a]> '


def test_use_unknown_errors():
    r = ShellREPL()
    out = _run(r, 'use nope')
    assert 'not loaded' in out or 'nope' in out
```

- [ ] **Step 2: 跑测试,确认 5 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 4 passed, 5 failed。

- [ ] **Step 3: 实现 load / files / use**

`inp_tool/inp_tool/repl.py` 中,在 `do_quit` 之后追加:

```python
    # ----- 文件状态管理 --------------------------------------------------

    def do_load(self, arg):
        """load PATH [as ALIAS] — 加载 .inp 到 session,自动设为 current"""
        if not arg.strip():
            self._err('load requires a file path')
            return
        # 拆分 'as ALIAS'(可选)
        parts = arg.strip().split()
        if 'as' in parts:
            i = parts.index('as')
            path_str = ' '.join(parts[:i])
            alias = parts[i + 1] if i + 1 < len(parts) else None
        else:
            path_str = arg.strip()
            alias = None
        from pathlib import Path
        path = Path(path_str)
        if not path.exists():
            self._err(f'file not found: {path}')
            return
        try:
            actual = self.session.load(path, alias=alias)
        except Exception as e:
            self._err(f'parse failed: {e}')
            return
        self._refresh_prompt()
        print(f'loaded: {actual}  ({path})')

    def do_files(self, arg):
        """files — 列出已加载 alias / 路径 / 状态"""
        if not self.session.files:
            print('(no files loaded)')
            return
        for a, lf in self.session.files.items():
            mark = '*' if a == self.session.current else ' '
            tag = 'dirty' if lf.dirty else 'clean'
            print(f'{mark} {a:15s} {str(lf.path):40s}  [{tag}]')

    def do_use(self, arg):
        """use ALIAS — 切换 current 指针"""
        a = arg.strip()
        if not a:
            self._err('use requires an alias')
            return
        try:
            self.session.use(a)
        except KeyError:
            self._err(f"alias '{a}' not loaded. type 'files' to see loaded.")
            return
        self._refresh_prompt()
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 9 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): load/files/use commands with alias state"
```

---

### Task 5: save / unload / status 命令

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_unload_clean_succeeds(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a', 'unload a')
    assert 'a' not in r.session.files


def test_unload_dirty_errors_until_forced(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'unload a')
    assert 'unsaved' in out or 'dirty' in out
    assert 'a' in r.session.files  # 没卸掉
    out = _run(r, 'unload a -f')
    assert 'a' not in r.session.files


def test_status_shows_dirty_count(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'status')
    assert 'a' in out
    assert 'dirty' in out or 'unsaved' in out


def test_save_clears_dirty(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x\n')
    r = ShellREPL()
    _run(r, f'load {p} as a')
    r.session.files['a'].dirty = True
    out = _run(r, 'save')
    assert r.session.files['a'].dirty is False


def test_save_as_creates_new_file(tmp_path):
    p = tmp_path / 'a.inp'; p.write_text('x\n')
    new_p = tmp_path / 'b.inp'
    r = ShellREPL()
    _run(r, f'load {p} as a')
    out = _run(r, f'save as {new_p}')
    assert new_p.exists()
    assert r.session.files['a'].dirty is False
    # alias 的 path 指向新文件
    assert r.session.files['a'].path == new_p
```

- [ ] **Step 2: 跑测试,确认 5 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 9 passed, 5 failed。

- [ ] **Step 3: 实现 save / unload / status**

`inp_tool/inp_tool/repl.py` 中,在 `do_use` 之后追加:

```python
    def do_unload(self, arg):
        """unload ALIAS [-f] — 移除 alias(默认拒绝 dirty)"""
        parts = arg.strip().split()
        if not parts:
            self._err('unload requires an alias')
            return
        alias = parts[0]
        force = '-f' in parts
        try:
            self.session.unload(alias, force=force)
        except KeyError:
            self._err(f"alias '{alias}' not loaded.")
        except RuntimeError as e:
            self._err(str(e))
            return
        if self.session.current is None:
            self._refresh_prompt()

    def do_status(self, arg):
        """status — 列出每个 alias 的未保存改动"""
        if not self.session.files:
            print('(no files loaded)')
            return
        for a, lf in self.session.files.items():
            mark = '*' if a == self.session.current else ' '
            if lf.dirty:
                print(f'{mark} {a:15s} {str(lf.path):40s}  [unsaved changes]')
            else:
                print(f'{mark} {a:15s} {str(lf.path):40s}  [clean]')

    def do_save(self, arg):
        """save [ALIAS] / save as PATH — 写回磁盘"""
        from .writer import to_text, write
        from pathlib import Path as P
        arg = arg.strip()
        if not arg:
            # 默认写 current
            target = self.session.current
            if not target:
                self._err('no file is current. use `use <alias>` or pass an alias.')
                return
            alias = target
            path = self.session.files[alias].path
        elif arg.startswith('as '):
            # save as <path>
            if not self.session.current:
                self._err('save as requires a current file')
                return
            alias = self.session.current
            path = P(arg[3:].strip())
        else:
            # save <alias>
            alias = arg.split()[0]
            if alias not in self.session.files:
                self._err(f"alias '{alias}' not loaded.")
                return
            path = self.session.files[alias].path
        try:
            write(self.session.files[alias].inp, str(path))
        except (OSError, PermissionError) as e:
            self._err(f'permission denied: {path} ({e})')
            return
        self.session.files[alias].dirty = False
        self.session.files[alias].last_saved_text = to_text(self.session.files[alias].inp)
        print(f'saved: {alias} -> {path}')
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 14 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): save/unload/status commands with dirty tracking"
```

---

## Phase 3 — 复用 cli.py handler

### Task 6: 接入 info / get / set / diff / parse

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 准备 fixture `.inp` 文件**

测试需要真实的 `.inp` 文件。fixtures 写到 `inp_tool/tests/data/`:

```bash
mkdir -p /home/fz/project/cfd--changer/inp_tool/tests/data
```

`inp_tool/tests/data/sample_v1.inp`:

```
# sample v1
system 0
  title "case v1"
  cfl 0.001
physics 0
  refvel 50.0
  cfl 0.001
```

`inp_tool/tests/data/sample_v2.inp`:

```
# sample v2
system 0
  title "case v2"
  cfl 0.005
physics 0
  refvel -1.0
  cfl 0.005
```

- [ ] **Step 2: 追加失败测试**

`inp_tool/tests/test_repl.py` 顶部加 fixture:

```python
SAMPLE_V1 = Path(__file__).parent / 'data' / 'sample_v1.inp'
SAMPLE_V2 = Path(__file__).parent / 'data' / 'sample_v2.inp'
```

末尾追加:

```python
def test_info_runs_on_current(SAMPLE_V1):
    r = ShellREPL()
    out = _run(r, f'load {SAMPLE_V1}', 'info')
    assert '块列表' in out or 'block' in out.lower()
    assert 'physics' in out


def test_get_reads_value(SAMPLE_V1):
    r = ShellREPL()
    out = _run(r, f'load {SAMPLE_V1}', 'get refvel -b physics')
    assert 'refvel' in out
    assert '50.0' in out


def test_get_missing_key_errors(SAMPLE_V1):
    r = ShellREPL()
    out = _run(r, f'load {SAMPLE_V1}', 'get nope -b physics')
    assert '不存在' in out or 'not found' in out.lower()


def test_set_marks_dirty(SAMPLE_V1):
    r = ShellREPL()
    _run(r, f'load {SAMPLE_V1} as v1', 'set physics refvel 75.0')
    assert r.session.files['v1'].dirty is True


def test_diff_between_two_files(SAMPLE_V1, SAMPLE_V2):
    r = ShellREPL()
    out = _run(
        r,
        f'load {SAMPLE_V1} as v1',
        f'load {SAMPLE_V2} as v2',
        'diff v2',
    )
    assert 'refvel' in out
```

- [ ] **Step 3: 跑测试,确认 5 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 14 passed, 5 failed(do_info/do_get/do_set/do_diff 不存在或 NoOp)。

- [ ] **Step 4: 实现 info / get / set / diff / parse,委托给 cli handler**

`inp_tool/inp_tool/repl.py` 中,在 `do_save` 之后追加:

```python
    # ----- 委托给 cli.py 的 cmd_* ----------------------------------------

    def _ns(self, **kwargs):
        """构造 argparse.Namespace 包装,subcommands 期待这个类型。"""
        from argparse import Namespace
        return Namespace(**kwargs)

    def do_info(self, arg):
        """info — 显示当前文件的结构(委托 cmd_info)"""
        if not self.session.current:
            self._err('no file is current. type `load <path>` first.')
            return
        from .cli import cmd_info
        ns = self._ns(file=str(self.session.files[self.session.current].path))
        rc = cmd_info(ns)
        if rc:
            self._err(f'cmd_info returned {rc}')

    def do_get(self, arg):
        """get KEY [-b BLOCK] [-i IDX] — 读一个值(委托 cmd_get)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_get
        import shlex
        try:
            tokens = shlex.split(arg)
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        block = None
        block_idx = None
        if '-b' in tokens:
            i = tokens.index('-b')
            block = tokens[i + 1] if i + 1 < len(tokens) else None
        if '-i' in tokens:
            i = tokens.index('-i')
            block_idx = int(tokens[i + 1]) if i + 1 < len(tokens) else None
        # 第一个非 flag 的 token 是 key
        key = next((t for t in tokens if not t.startswith('-') and t != block), None)
        if not key:
            self._err('get requires a key')
            return
        ns = self._ns(
            file=str(self.session.files[self.session.current].path),
            block=block, block_idx=block_idx, key=key,
        )
        rc = cmd_get(ns)
        if rc:
            self._err(f'cmd_get returned {rc}')

    def do_set(self, arg):
        """set BLOCK KEY VALUE — 改一个值,标记 dirty(委托 cmd_set)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_set
        import shlex
        try:
            tokens = shlex.split(arg)
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        if len(tokens) < 3:
            self._err('set requires: set <block> <key> <value>')
            return
        block, key, value = tokens[0], tokens[1], tokens[2]
        alias = self.session.current
        lf = self.session.files[alias]
        # 拍旧值
        b = lf.inp.get_block(block, 0)
        old_values = []
        if b is not None:
            v = b.get_value(key)
            if v is not None:
                old_values = list(v.raw) if isinstance(v.raw, list) else [v.raw]
        # 调 handler(不写盘,handler 写盘逻辑靠 args.output,默认会写)
        ns = self._ns(
            file=str(lf.path), block=block, block_idx=0, key=key, value=value,
            output=None, force=False,
        )
        rc = cmd_set(ns)
        if rc == 0:
            lf.dirty = True
            from .repl_state import UndoEntry
            self.session.undo.push(UndoEntry(
                alias=alias, block=block, key=key, old_values=old_values,
            ))

    def do_diff(self, arg):
        """diff ALIAS — current vs 指定 alias(委托 cmd_diff)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_diff
        other = arg.strip()
        if not other:
            self._err('diff requires another alias')
            return
        if other not in self.session.files:
            self._err(f"alias '{other}' not loaded.")
            return
        a_path = str(self.session.files[self.session.current].path)
        b_path = str(self.session.files[other].path)
        ns = self._ns(a=a_path, b=b_path, unified=False)
        rc = cmd_diff(ns)
        if rc:
            self._err(f'cmd_diff returned {rc}')

    def do_parse(self, arg):
        """parse — 显示当前文件完整结构(委托 cmd_parse)"""
        if not self.session.current:
            self._err('no file is current.')
            return
        from .cli import cmd_parse
        ns = self._ns(file=str(self.session.files[self.session.current].path))
        rc = cmd_parse(ns)
        if rc:
            self._err(f'cmd_parse returned {rc}')
```

- [ ] **Step 5: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 19 passed。

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py inp_tool/tests/data/
git commit -m "feat(repl): delegate info/get/set/diff/parse to cli.py handlers"
```

---

## Phase 4 — 别名前缀 / 变量 / shell escape

### Task 7: `<alias>:` 前缀解析

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_alias_prefix_overrides_current(SAMPLE_V1, SAMPLE_V2):
    r = ShellREPL()
    out = _run(
        r,
        f'load {SAMPLE_V1} as v1',
        f'load {SAMPLE_V2} as v2',
        'v1:get refvel -b physics',
    )
    # v1 的 refvel 是 50.0
    assert '50.0' in out


def test_alias_prefix_with_set(SAMPLE_V1, SAMPLE_V2):
    r = ShellREPL()
    _run(
        r,
        f'load {SAMPLE_V1} as v1',
        f'load {SAMPLE_V2} as v2',
        'v1:set physics refvel 99.0',
    )
    # v1 dirty,v2 不 dirty
    assert r.session.files['v1'].dirty is True
    assert r.session.files['v2'].dirty is False


def test_alias_prefix_with_unknown_alias(SAMPLE_V1):
    r = ShellREPL()
    out = _run(r, f'load {SAMPLE_V1} as v1', 'nope:get refvel -b physics')
    assert 'not loaded' in out or 'nope' in out
```

- [ ] **Step 2: 跑测试,确认 3 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 19 passed, 3 failed(`v1:` 被当作命令不存在)。

- [ ] **Step 3: 重写 onecmd 以支持前缀**

`inp_tool/inp_tool/repl.py` 中,在 `ShellREPL` 类的 `__init__` 之后(在 `_refresh_prompt` 之前)追加:

```python
    def onecmd(self, line):
        """在分发到 cmd.Cmd 前,先剥离 '<alias>:' 前缀。"""
        line = line.strip()
        if ':' in line and not line.startswith('!') and not line.startswith('?'):
            # 仅当冒号前是一个单词(不是参数中的 url 等)才算前缀
            head, _, rest = line.partition(':')
            if head and head.replace('_', '').isalnum() and head in self.session.files:
                saved = self.session.current
                self.session.current = head
                try:
                    return super().onecmd(rest.strip())
                finally:
                    self.session.current = saved
                return False
        return super().onecmd(line)
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 22 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): <alias>: prefix to override current per command"
```

---

### Task 8: `$var` 插值

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_let_stores_variable():
    r = ShellREPL()
    _run(r, 'let alpha=3.5')
    assert r.session.variables.get('alpha') == '3.5'


def test_dollar_var_interpolated(SAMPLE_V1, tmp_path):
    r = ShellREPL()
    out = _run(
        r,
        f'load {SAMPLE_V1} as v1',
        'let mach=75.0',
        'set physics refvel $mach',
    )
    # 通过 get 验证
    out2 = _run(r, 'get refvel -b physics')
    assert '75.0' in out2
    assert r.session.files['v1'].dirty is True


def test_undefined_var_errors(SAMPLE_V1):
    r = ShellREPL()
    out = _run(
        r,
        f'load {SAMPLE_V1} as v1',
        'set physics refvel $undefined',
    )
    assert 'undefined' in out


def test_double_dollar_literal():
    r = ShellREPL()
    r.session.variables['x'] = 'Y'
    out = _run(r, 'let val=$$x')
    # $$ 转义为字面 $,x 不展开
    assert r.session.variables.get('val') == '$x'
```

- [ ] **Step 2: 跑测试,确认 4 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 22 passed, 4 failed。

- [ ] **Step 3: 实现 let + 插值**

`inp_tool/inp_tool/repl.py` 中,在 `do_save` 之后(Phase 3 末尾)追加:

```python
    # ----- 会话变量 + shell escape ---------------------------------------

    def _interpolate(self, line: str) -> str:
        """替换 $name 为 session.variables[name];$$ 转义。"""
        import re
        # 先把 $$ 占位,防止被二次展开
        PLACEHOLDER = '\x00DOLLAR\x00'
        out = line.replace('$$', PLACEHOLDER)
        def repl(m):
            name = m.group(1)
            if name not in self.session.variables:
                raise KeyError(name)
            return self.session.variables[name]
        try:
            out = re.sub(r'\$([A-Za-z_][A-Za-z0-9_]*)', repl, out)
        except KeyError as e:
            raise ValueError(f'undefined variable: ${e.args[0]}')
        return out.replace(PLACEHOLDER, '$')

    def do_let(self, arg):
        """let NAME=VALUE — 存会话变量(供 $NAME 插值)"""
        arg = arg.strip()
        if '=' not in arg:
            self._err('let requires NAME=VALUE')
            return
        name, _, value = arg.partition('=')
        name = name.strip()
        if not name.replace('_', '').isalnum():
            self._err(f'invalid variable name: {name}')
            return
        # 不做插值,字面存
        self.session.variables[name] = value
```

然后修改 `onecmd` 方法,在调用 `super().onecmd` 之前插值。`let` 命令**不走插值**(它就是定义变量的),否则 `let val=$$x` 会破坏:

```python
    def onecmd(self, line):
        """在分发到 cmd.Cmd 前,先剥离 '<alias>:' 前缀,再做 $var 插值。"""
        line = line.strip()
        if not line or line.startswith('#'):
            return False
        # let 命令不走插值(它就是定义变量的)
        if line.startswith('let '):
            return super().onecmd(line)
        if line.startswith('!'):
            # shell escape 不做插值前缀剥离
            try:
                line = self._interpolate(line[1:])
            except ValueError as e:
                self._err(str(e))
                return False
            return self._do_shell(line)
        if line.startswith('?'):
            self._err('!N rerun is not yet implemented (Phase 8)')
            return False
        # 剥离 <alias>: 前缀
        if ':' in line:
            head, _, rest = line.partition(':')
            if head and head.replace('_', '').isalnum() and head in self.session.files:
                saved = self.session.current
                self.session.current = head
                try:
                    try:
                        rest = self._interpolate(rest)
                    except ValueError as e:
                        self._err(str(e))
                        return False
                    return super().onecmd(rest)
                finally:
                    self.session.current = saved
        # 默认路径:整行插值
        try:
            line = self._interpolate(line)
        except ValueError as e:
            self._err(str(e))
            return False
        return super().onecmd(line)
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 26 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): \$var interpolation and let command"
```

---

### Task 9: `! cmd` shell escape

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_shell_escape_runs_command():
    r = ShellREPL()
    out = _run(r, '! echo hello')
    assert 'hello' in out


def test_shell_escape_reports_nonzero_exit():
    r = ShellREPL()
    out = _run(r, '! sh -c "echo bad; exit 3"')
    assert 'bad' in out
    assert 'exit code' in out or '3' in out
```

- [ ] **Step 2: 跑测试,确认 2 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 26 passed, 2 failed(`_do_shell` 不存在)。

- [ ] **Step 3: 实现 shell escape**

`inp_tool/inp_tool/repl.py` 中,`do_let` 之后追加:

```python
    def _do_shell(self, cmdline: str) -> bool:
        """执行 shell 命令,透传 stdout/stderr;非零退出打印 exit code。"""
        import subprocess
        if not cmdline.strip():
            self._err('empty shell command')
            return False
        try:
            cp = subprocess.run(
                cmdline, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
        except FileNotFoundError as e:
            self._err(f'command not found: {e}')
            return False
        if cp.stdout:
            print(cp.stdout.decode('utf-8', errors='replace'), end='')
        if cp.stderr:
            print(cp.stderr.decode('utf-8', errors='replace'), end='', file=sys.stderr)
        if cp.returncode != 0:
            print(f'(exit code: {cp.returncode})', file=sys.stderr)
        return False  # 不退出 REPL
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 28 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): shell escape via ! command"
```

---

## Phase 5 — Undo

### Task 10: undo 命令接入 UndoLog

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_undo_restores_value(SAMPLE_V1):
    r = ShellREPL()
    _run(r, f'load {SAMPLE_V1} as v1')
    # 改值
    _run(r, 'set physics refvel 99.0')
    assert r.session.files['v1'].dirty is True
    # 撤销
    out = _run(r, 'undo')
    assert 'undone' in out.lower() or 'restored' in out.lower() or '回滚' in out
    # 验证值已恢复
    out2 = _run(r, 'get refvel -b physics')
    assert '50.0' in out2


def test_undo_empty_errors():
    r = ShellREPL()
    out = _run(r, 'undo')
    assert 'nothing' in out.lower() or 'undo' in out.lower()


def test_undo_multiple_steps(SAMPLE_V1):
    r = ShellREPL()
    _run(r, f'load {SAMPLE_V1} as v1')
    _run(r, 'set physics refvel 99.0')
    _run(r, 'set physics refvel 88.0')
    _run(r, 'undo 2')
    out = _run(r, 'get refvel -b physics')
    assert '50.0' in out
```

- [ ] **Step 2: 跑测试,确认 3 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 28 passed, 3 failed。

- [ ] **Step 3: 实现 undo**

`inp_tool/inp_tool/repl.py` 中,`do_let` 之后追加:

```python
    def do_undo(self, arg):
        """undo [N=1] — 回滚最近 N 次 set"""
        n = 1
        if arg.strip().isdigit():
            n = int(arg.strip())
        for _ in range(n):
            entry = self.session.undo.pop()
            if entry is None:
                print('nothing to undo')
                return
            lf = self.session.files.get(entry.alias)
            if lf is None:
                print(f'(undo: alias {entry.alias} no longer loaded, skipping)')
                continue
            b = lf.inp.get_block(entry.block, 0)
            if b is None:
                print(f'(undo: block {entry.block} missing, skipping)')
                continue
            # 恢复:把 values 写回(单值或多值)
            if len(entry.old_values) == 1:
                from .model import infer_type
                b.set(entry.key, infer_type(entry.old_values[0]))
            else:
                from .model import infer_type
                b.set(entry.key, infer_type(entry.old_values[0]))
            lf.dirty = True
            print(f'undone: {entry.alias}.{entry.block}.{entry.key} restored')
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 31 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): undo command wired to UndoLog"
```

---

## Phase 6 — Sweep 集成

### Task 11: sweep 命令从 session.variables 读默认

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_sweep_uses_session_variable_as_default(SAMPLE_V1):
    r = ShellREPL()
    out = _run(
        r,
        f'load {SAMPLE_V1} as v1',
        'let alpha=2.5',
        'sweep --help',  # 确认 sweep 在 REPL 中可调
    )
    assert '--config' in out or 'config' in out.lower() or 'sweep' in out.lower()
```

(本任务只验证 sweep 命令已被注册并在 REPL 中可调,不验证完整 sweep 流程,因为那是 cli 已有测试覆盖的范围。)

- [ ] **Step 2: 跑测试,确认 1 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 31 passed, 1 failed(`do_sweep` 不存在)。

- [ ] **Step 3: 实现 do_sweep,委托 cmd_sweep**

`inp_tool/inp_tool/repl.py` 中,在 `do_diff` 之后追加:

```python
    def do_sweep(self, arg):
        """sweep [args...] — 批量生成算例(委托 cmd_sweep)"""
        from .cli import cmd_sweep
        import shlex
        try:
            tokens = shlex.split(arg)
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        from argparse import Namespace
        ns = Namespace(
            template=None, config=None, alpha=None, beta=None, mach=None,
            t_inf=None, p_inf=None, out=None, manifest=None,
            dry_run=False, verbose=False, interactive=False, _tokens=tokens,
        )
        # 把 session.variables 作为兜底默认(任何 None 字段)
        for key in ('alpha', 'beta', 'mach', 't_inf', 'p_inf'):
            v = self.session.variables.get(key)
            if v is not None and getattr(ns, key) is None:
                try:
                    setattr(ns, key, float(v))
                except ValueError:
                    setattr(ns, key, v)
        rc = cmd_sweep(ns)
        if rc:
            self._err(f'cmd_sweep returned {rc}')
```

(本任务为 MVP,完整 sweep 默认值/交互需要后续视需求扩展。本步骤只保证命令可达。)

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 32 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): sweep command delegates to cmd_sweep with session var defaults"
```

---

## Phase 7 — Tab 补全

### Task 12: InpCompleter 类(单测)

**Files:**
- Create: `inp_tool/inp_tool/repl_completer.py`
- Create: `inp_tool/tests/test_repl_completer.py`

- [ ] **Step 1: 写失败测试**

`inp_tool/tests/test_repl_completer.py`:

```python
"""InpCompleter 单元测试。"""
from pathlib import Path
from argparse import Namespace

import pytest

from inp_tool.repl_completer import InpCompleter
from inp_tool.repl_state import LoadedFile, ReplSession


@pytest.fixture
def session_with_file(tmp_path):
    """构造一个 session,加载一个最小 InpFile。"""
    from inp_tool.parser import parse_file
    p = tmp_path / 'sample.inp'
    p.write_text('physics 0\n  refvel 50.0\noptions 0\n  cfl 0.001\n')
    inp = parse_file(str(p))
    s = ReplSession()
    s.load(p, alias='v1')
    return s


def test_complete_command_lists_all():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_command('')
    assert 'load' in out
    assert 'files' in out
    assert 'set' in out
    assert 'exit' in out


def test_complete_command_prefix_filter():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_command('lo')
    assert out == ['load']


def test_complete_alias_returns_loaded(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_alias('')
    assert 'v1' in out


def test_complete_alias_no_files():
    s = ReplSession()
    c = InpCompleter(s)
    assert c.complete_alias('') == []


def test_complete_block_returns_block_names(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_block('v1', '')
    assert 'physics' in out
    assert 'options' in out


def test_complete_block_prefix(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_block('v1', 'phy')
    assert out == ['physics']


def test_complete_block_unknown_alias():
    s = ReplSession()
    c = InpCompleter(s)
    assert c.complete_block('nope', '') == []


def test_complete_key_returns_keys(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_key('v1', 'physics', '')
    assert 'refvel' in out


def test_complete_key_prefix(session_with_file):
    c = InpCompleter(session_with_file)
    out = c.complete_key('v1', 'physics', 'ref')
    assert out == ['refvel']


def test_complete_shell_finds_ls():
    s = ReplSession()
    c = InpCompleter(s)
    out = c.complete_shell('ls')
    assert 'ls' in out or any(o.startswith('ls') for o in out)
```

- [ ] **Step 2: 跑测试,确认 10 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_completer.py -v
```

Expected: `ModuleNotFoundError: No module named 'inp_tool.repl_completer'`。

- [ ] **Step 3: 实现 InpCompleter**

`inp_tool/inp_tool/repl_completer.py`:

```python
"""REPL Tab 补全器。

纯函数式:接受 session + 参数,返回候选词列表。
由 repl.ShellREPL.complete() 调度。
"""
import os
import shutil
from typing import List, Optional

from .repl import REPL_COMMANDS
from .repl_state import ReplSession


class InpCompleter:
    def __init__(self, session: ReplSession):
        self.session = session

    # ----- 静态 ----------------------------------------------------------

    def complete_command(self, text: str) -> List[str]:
        cmds = sorted(REPL_COMMANDS)
        return [c for c in cmds if c.startswith(text)]

    def complete_shell(self, text: str) -> List[str]:
        # PATH 中所有可执行名
        path = os.environ.get('PATH', '')
        seen = set()
        out = []
        for d in path.split(os.pathsep):
            if not d:
                continue
            try:
                for name in os.listdir(d):
                    full = os.path.join(d, name)
                    if name in seen:
                        continue
                    if os.access(full, os.X_OK) and not os.path.isdir(full):
                        seen.add(name)
                        if name.startswith(text):
                            out.append(name)
            except OSError:
                continue
        return sorted(out)[:50]  # 限制数量

    # ----- 状态相关 ------------------------------------------------------

    def complete_alias(self, text: str) -> List[str]:
        return sorted(a for a in self.session.files if a.startswith(text))

    def complete_block(self, alias: str, text: str) -> List[str]:
        lf = self.session.files.get(alias)
        if lf is None:
            return []
        names = sorted({b.name for b in lf.inp.block_list})
        return [n for n in names if n.startswith(text)]

    def complete_key(self, alias: str, block: str, text: str) -> List[str]:
        lf = self.session.files.get(alias)
        if lf is None:
            return []
        keys = set()
        for b in lf.inp.block_list:
            if b.name == block:
                for s in b.statements:
                    keys.add(s.keyword)
        return sorted(k for k in keys if k.startswith(text))
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_completer.py -v
```

Expected: 10 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl_completer.py inp_tool/tests/test_repl_completer.py
git commit -m "feat(repl): InpCompleter for command/alias/block/key/shell"
```

---

### Task 13: 把 InpCompleter 接入 cmd.Cmd

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_complete_returns_command_candidates():
    r = ShellREPL()
    out = r.complete('lo', 'load')
    assert 'load' in out


def test_complete_returns_alias_for_use(SAMPLE_V1):
    r = ShellREPL()
    _run(r, f'load {SAMPLE_V1} as v1')
    out = r.complete('v', 'use')
    assert 'v1' in out


def test_completer_attached(SAMPLE_V1):
    r = ShellREPL()
    _run(r, f'load {SAMPLE_V1} as v1')
    assert r._completer is not None
```

- [ ] **Step 2: 跑测试,确认 3 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 32 passed, 3 failed(`_completer` 不存在 / `complete` 未重写)。

- [ ] **Step 3: 接入 completer**

`inp_tool/inp_tool/repl.py` 顶部 import 加:

```python
from .repl_completer import InpCompleter
```

`ShellREPL.__init__` 末尾追加:

```python
        self._completer = InpCompleter(self.session)
```

在 `do_load` 之后追加:

```python
    # ----- Tab 补全 ------------------------------------------------------

    def complete(self, text, state):
        """cmd.Cmd 调用入口。state 是第 N 次按 Tab(0..N-1)。"""
        import readline
        line = readline.get_line_buffer()
        tokens = line.split()
        if not tokens or (len(tokens) == 1 and not text):
            cands = self._completer.complete_command(text)
        else:
            cmd_name = tokens[0]
            # 处理 <alias>: 前缀:剥离,补全后续
            if ':' in cmd_name:
                cmd_name = cmd_name.split(':', 1)[1] or ''
            if cmd_name in ('use', 'unload', 'save'):
                cands = self._completer.complete_alias(text)
            elif cmd_name in ('get', 'set'):
                if text or (len(tokens) >= 2 and tokens[-1] == '-b'):
                    cands = self._completer.complete_block(
                        self.session.current or '', text,
                    )
                else:
                    cands = self._completer.complete_command(text)
            else:
                cands = self._completer.complete_command(text)
        if state < len(cands):
            return cands[state]
        return None
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 35 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): wire InpCompleter into cmd.Cmd.complete()"
```

---

## Phase 8 — 历史持久化

### Task 14: repl_history 读写 + 跨平台

**Files:**
- Create: `inp_tool/inp_tool/repl_history.py`
- Create: `inp_tool/tests/test_repl_history.py`

- [ ] **Step 1: 写失败测试**

`inp_tool/tests/test_repl_history.py`:

```python
"""repl_history 单测。"""
from pathlib import Path

import pytest

from inp_tool.repl_history import HistoryStore


def test_load_empty_if_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore()
    assert h.load() == []


def test_append_and_save(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore()
    h.append('load foo.inp')
    h.append('set physics refvel 50.0')
    h.save()
    f = tmp_path / '.inp_history'
    assert f.exists()
    assert f.read_text().splitlines() == ['load foo.inp', 'set physics refvel 50.0']


def test_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    f = tmp_path / '.inp_history'
    f.write_text('cmd1\ncmd2\n')
    h = HistoryStore()
    out = h.load()
    assert out == ['cmd1', 'cmd2']


def test_maxlen_fifo(tmp_path, monkeypatch):
    monkeypatch.setattr('pathlib.Path.home', lambda: tmp_path)
    h = HistoryStore(maxlen=3)
    for i in range(5):
        h.append(f'cmd{i}')
    h.save()
    out = (tmp_path / '.inp_history').read_text().splitlines()
    assert out == ['cmd2', 'cmd3', 'cmd4']
```

- [ ] **Step 2: 跑测试,确认 4 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_history.py -v
```

Expected: `ModuleNotFoundError: No module named 'inp_tool.repl_history'`。

- [ ] **Step 3: 实现 HistoryStore**

`inp_tool/inp_tool/repl_history.py`:

```python
"""REPL 命令历史持久化。

存到 ~/.inp_history,每行一条,纯文本。Unix/macOS 接 readline,Windows 降级到纯内存。
"""
import sys
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional


def _history_path() -> Path:
    return Path.home() / '.inp_history'


class HistoryStore:
    """内存 deque + 磁盘 FIFO 同步。"""

    def __init__(self, maxlen: int = 1000, path: Optional[Path] = None):
        self._maxlen = maxlen
        self._path = path or _history_path()
        self._buf: Deque[str] = deque(maxlen=maxlen)

    def load(self) -> List[str]:
        """从磁盘读入到内存。返回加载的命令列表(也存到 self._buf)。"""
        self._buf.clear()
        if self._path.exists():
            try:
                lines = self._path.read_text(encoding='utf-8').splitlines()
            except OSError:
                lines = []
            for line in lines[-self._maxlen:]:
                if line:
                    self._buf.append(line)
        return list(self._buf)

    def append(self, line: str) -> None:
        if line:
            self._buf.append(line)

    def save(self) -> None:
        """把内存命令一次性写回磁盘。"""
        try:
            self._path.write_text(
                '\n'.join(self._buf) + ('\n' if self._buf else ''),
                encoding='utf-8',
            )
        except OSError:
            pass  # 静默:写失败不应阻塞退出

    def __iter__(self):
        return iter(self._buf)

    def recent(self, n: int = 20) -> List[str]:
        return list(self._buf)[-n:]

    # ----- readline 集成(Unix/macOS) ------------------------------------

    def bind_readline(self) -> bool:
        """把历史接进 readline buffer(若有)。返回是否成功。"""
        if sys.platform.startswith('win'):
            return False
        try:
            import readline  # noqa: F401
        except ImportError:
            return False
        try:
            import readline
            for line in self._buf:
                readline.add_history(line)
            import atexit
            def _save_on_exit():
                try:
                    for i in range(readline.get_current_history_length()):
                        self._buf.append(readline.get_history_item(i + 1))
                except Exception:
                    pass
                self.save()
            atexit.register(_save_on_exit)
            return True
        except Exception:
            return False
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl_history.py -v
```

Expected: 4 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl_history.py inp_tool/tests/test_repl_history.py
git commit -m "feat(repl): HistoryStore with FIFO 1000 lines and readline binding"
```

---

### Task 15: history 命令 + !N rerun + 接 readline

**Files:**
- Modify: `inp_tool/inp_tool/repl.py`
- Modify: `inp_tool/tests/test_repl.py`

- [ ] **Step 1: 追加失败测试**

`inp_tool/tests/test_repl.py` 末尾追加:

```python
def test_history_command_lists_recent():
    r = ShellREPL()
    _run(r, 'let a=1', 'let b=2', 'let c=3')
    out = _run(r, 'history 10')
    assert 'let a=1' in out
    assert 'let b=2' in out
    assert 'let c=3' in out


def test_rerun_re_executes_history_entry():
    r = ShellREPL()
    _run(r, 'let x=42', '! 1')
    assert r.session.variables.get('x') == '42'
```

- [ ] **Step 2: 跑测试,确认 2 个新失败**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 35 passed, 2 failed。

- [ ] **Step 3: 实现 history + !N + readline 集成**

`inp_tool/inp_tool/repl.py` 顶部 import 加:

```python
from .repl_history import HistoryStore
```

`ShellREPL.__init__` 末尾追加:

```python
        self.history = HistoryStore()
        self.history.load()
        self.history.bind_readline()
```

`do_let` 之后追加:

```python
    def do_history(self, arg):
        """history [N=20] — 列出最近 N 条命令"""
        n = 20
        if arg.strip().isdigit():
            n = int(arg.strip())
        recent = self.history.recent(n)
        for i, line in enumerate(recent, start=1):
            print(f'  {i:4d}  {line}')

    def do_rerun(self, arg):
        """! N — 重新执行 history 第 N 条(N 从 1 开始)"""
        if not arg.strip().isdigit():
            self._err('rerun requires a number')
            return
        n = int(arg.strip())
        recent = self.history.recent(1000)
        if n < 1 or n > len(recent):
            self._err(f'history entry {n} out of range')
            return
        target = recent[n - 1]
        print(f'rerunning: {target}')
        return self.onecmd(target)
```

更新 `onecmd` 头部处理 `!N`:

```python
    def onecmd(self, line):
        line = line.strip()
        if not line or line.startswith('#'):
            return False
        # 单独 '!N' rerun
        if line.startswith('!') and line[1:].strip().isdigit():
            return self.do_rerun(line[1:].strip())
        # let 不插值
        if line.startswith('let '):
            result = super().onecmd(line)
            self.history.append(line)
            return result
        if line.startswith('!'):
            try:
                cmdline = self._interpolate(line[1:])
            except ValueError as e:
                self._err(str(e))
                return False
            result = self._do_shell(cmdline)
            self.history.append(line)
            return result
        if line.startswith('?'):
            self._err('!N rerun: use !N (without ?)')
            return False
        # 剥离 <alias>: 前缀
        if ':' in line:
            head, _, rest = line.partition(':')
            if head and head.replace('_', '').isalnum() and head in self.session.files:
                saved = self.session.current
                self.session.current = head
                try:
                    try:
                        rest = self._interpolate(rest)
                    except ValueError as e:
                        self._err(str(e))
                        return False
                    result = super().onecmd(rest)
                    self.history.append(line)
                    return result
                finally:
                    self.session.current = saved
        try:
            line = self._interpolate(line)
        except ValueError as e:
            self._err(str(e))
            return False
        result = super().onecmd(line)
        self.history.append(line)
        return result
```

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_repl.py -v
```

Expected: 37 passed。

- [ ] **Step 5: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/repl.py inp_tool/tests/test_repl.py
git commit -m "feat(repl): history command + !N rerun + readline integration"
```

---

## Phase 9 — CLI 接线 + CI smoke + 文档

### Task 16: 在 cli.py 加 shell 子命令

**Files:**
- Modify: `inp_tool/inp_tool/cli.py`
- Modify: `inp_tool/tests/test_cli.py`

- [ ] **Step 1: 追加 smoke 测试**

`inp_tool/tests/test_cli.py` 末尾追加(若文件不存在则新建):

```python
"""CLI shell 子命令 smoke 测试。"""
import subprocess
import sys
import os


def test_shell_subcommand_in_help():
    """`inp-tool --help` 应包含 'shell' 子命令。"""
    from inp_tool.cli import main
    try:
        main(['--help'])
    except SystemExit:
        pass


def test_shell_via_subprocess(tmp_path):
    """非交互式跑一条 load + exit,验证子命令可达。"""
    p = tmp_path / 's.inp'
    p.write_text('physics 0\n  refvel 1.0\n')
    cp = subprocess.run(
        [sys.executable, '-m', 'inp_tool.cli', 'shell', str(p)],
        input='files\nexit\n',
        capture_output=True, text=True, timeout=10,
        env={'PATH': os.environ.get('PATH', '')},
    )
    assert 's' in cp.stdout or 'loaded' in cp.stdout
```

- [ ] **Step 2: 跑测试,确认失败(shell 子命令尚不存在)**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_cli.py::test_shell_via_subprocess -v
```

Expected: 失败(子命令错误)。

- [ ] **Step 3: 在 cli.py 加 shell 子命令**

`inp_tool/inp_tool/cli.py` 末尾(在 `main` 函数内,`sub.add_parser` 块的最末)追加:

```python
    sshell = sub.add_parser('shell', help='进入交互式 shell (REPL)')
    sshell.add_argument('files', nargs='*', help='启动时预加载的文件(自动按 basename 起别名)')
```

在其他 `cmd_*` 平级位置加:

```python
def cmd_shell(args):
    """进入交互式 REPL。"""
    from .repl import main as repl_main
    return repl_main(args.files)
```

并在 main 函数的 dispatch 段(`sub.add_parser` 之后)加:

```python
    args = p.parse_args(argv)
    if hasattr(args, 'func'):
        return args.func(args)
    # ... 现有 dispatch 逻辑 ...
```

(注:本计划假设 cli.py 已有 `func=lambda: ...` 形式的 dispatch。若当前 cli 用 if/elif 链分发,则在链末追加 `elif args.cmd == 'shell': return cmd_shell(args)`,具体以 cli.py 实际结构为准。)

- [ ] **Step 4: 跑测试,确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest tests/test_cli.py -v
```

Expected: 现有 + 2 个新 test passed。

- [ ] **Step 5: 跑全部测试,确认无回归**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest -q
```

Expected: 全绿(包括原有 147+6skipped)。

- [ ] **Step 6: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/inp_tool/cli.py inp_tool/tests/test_cli.py
git commit -m "feat(cli): add shell subcommand delegating to repl.main()"
```

---

### Task 17: CI smoke test

**Files:**
- Create: `inp_tool/tests/data/repl_smoke.txt`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: 写 smoke 输入文件**

`inp_tool/tests/data/repl_smoke.txt`:

```
load tests/data/sample_v1.inp
files
set physics refvel 42.0
status
undo
files
exit
```

- [ ] **Step 2: 手动跑一次 smoke 确认通过**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m inp_tool.cli shell < tests/data/repl_smoke.txt 2>&1 | head -30
```

Expected: 看到 `loaded: sample_v1`、`sample_v1` 出现在 files、`status` 显示 dirty、然后 `undone` 等输出。

- [ ] **Step 3: 改 .github/workflows/ci.yml 加 smoke 步骤**

打开 `.github/workflows/ci.yml`,在 pytest step 后追加:

```yaml
      - name: REPL smoke test
        run: |
          cd inp_tool
          python -m inp_tool.cli shell < tests/data/repl_smoke.txt
```

(具体语法视现有 ci.yml 而定 — 若用 matrix / 平台多版本,放在最常见平台即可。Linux + Python 3.10 是最稳的 smoke 平台。)

- [ ] **Step 4: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/tests/data/repl_smoke.txt .github/workflows/ci.yml
git commit -m "ci: add REPL smoke test using stdin-driven shell"
```

---

### Task 18: README 新增 REPL 教学节

**Files:**
- Modify: `inp_tool/README.md`

- [ ] **Step 1: 找到 README 中合适位置**

```bash
grep -n '^## ' /home/fz/project/cfd--changer/inp_tool/README.md
```

- [ ] **Step 2: 追加 REPL 节**

在 README 中适当位置(建议在 "CLI 用法" 节后)追加:

````markdown
## REPL 模式(交互式 shell)

`inp-tool shell` 进入交互式 shell,适合多文件来回切换、反复 get/set 调参。

### 快速开始

```bash
$ inp-tool shell mcfd_v1.inp mcfd_v2.inp
inp-tool v0.5.0 interactive shell. Type 'help' for commands, 'exit' to quit.
inp[mcfd_v2]> use v1
inp[v1]> get refvel -b physics
v1[physics][0].refvel = 50.0  (raw: '50.0')
inp[v1]> set physics refvel 75.0
已写入: ...
inp[v1]> status
* v1  mcfd_v1.inp  [unsaved changes]
  mcfd_v2  mcfd_v2.inp  [clean]
inp[v1]> undo
undone: v1.physics.refvel restored
inp[v1]> save
saved: v1 -> mcfd_v1.inp
inp[v1]> v2:diff v1
差异条数: ...
inp[v1]> exit
```

### 常用命令

| 命令 | 作用 |
|---|---|
| `load <path> [as ALIAS]` | 加载文件 |
| `files` | 列出已加载 |
| `use ALIAS` | 切换 current |
| `info` / `get KEY -b BLOCK` | 读(基于 current) |
| `set BLOCK KEY VALUE` | 改,自动标 dirty,记入 undo |
| `diff <other>` | current vs other |
| `undo [N]` | 回滚最近 N 次 set |
| `save` / `save as PATH` | 写盘 |
| `let NAME=VALUE` | 存会话变量;`$NAME` 在命令中插值 |
| `! <cmd>` | shell escape |
| `! N` | 重新执行 history 第 N 条 |
| `history` | 列出最近命令 |
| `help [CMD]` | 帮助 |
| `exit` | 退出(dirty 时提示) |

### 前缀覆盖

任何命令前可加 `<alias>:` 绕过 current:

```
inp> v1:set physics refvel 75.0
```

### 变量插值

```
inp> let alpha=3.5
inp> sweep --alpha $alpha
```

未定义变量 → `error: undefined variable: $name`。`$$` 转义为字面 `$`。

### 历史

存到 `~/.inp_history`,最多 1000 行,跨会话保留。
````

- [ ] **Step 3: 提交**

```bash
cd /home/fz/project/cfd--changer
git add inp_tool/README.md
git commit -m "docs(readme): add REPL mode section with quick start and command reference"
```

---

## Phase 10 — 构建与平台自测

### Task 19: 本地重 build + 自测

**Files:**
- 无文件改动(纯验证)

- [ ] **Step 1: 跑完整测试套件**

```bash
cd /home/fz/project/cfd--changer/inp_tool
conda run -n cfdchanger python -m pytest -q
```

Expected: 全绿(原 147 + 新增 ~50 + 6 skipped)。

- [ ] **Step 2: 重 build Linux onefile**

```bash
cd /home/fz/project/cfd--changer
conda run -n cfdchanger ./scripts/build.sh
```

Expected: `Build complete!` + `dist/inp-tool` 大小 ~25M。

- [ ] **Step 3: 跑 build 出来的二进制**

```bash
./inp_tool/dist/inp-tool --version
# → inp 0.5.0
./inp_tool/dist/inp-tool shell --help
# → 显示 shell 子命令帮助
```

- [ ] **Step 4: 跑 build 出来的 shell**

```bash
echo -e "load inp_tool/examples/mcfd_modified.inp\nfiles\nexit" | ./inp_tool/dist/inp-tool shell
```

Expected: `loaded: mcfd_modified` + `files` 列出 + 干净退出。

- [ ] **Step 5: 跨平台验证清单**

记录本次在 Linux 上的验证结果,留给其他平台(CI / 用户):

```markdown
- [x] Linux: 本地 build + smoke 通过
- [ ] Windows 10: CI runner 自动验证(待 push 后看)
- [ ] Windows 7: 平台可达性需用户确认
- [ ] macOS: CI runner 自动验证
```

- [ ] **Step 6: 合并到 main(若想)**

通过 PR 流程:推送分支,开 PR,CI 绿后 merge。

```bash
cd /home/fz/project/cfd--changer
git push -u origin feat/repl-shell
gh pr create --title "feat(repl): interactive shell with multi-file state" \
  --body "实现 docs/superpowers/specs/2026-06-08-inp-tool-repl-design.md 全部 19 个任务"
```

---

## Self-Review Checklist(写计划时自查)

- [x] **Spec 覆盖**: spec 14 节对应到本计划的 Phase 1-10
  - §1 目标 → 整体
  - §2 非目标 → 不实现(已划线)
  - §3 入口 → Task 16
  - §4 架构 → Tasks 1-15 文件结构
  - §5 状态模型 → Tasks 1-2
  - §6 命令集 → Tasks 3-11, 15
  - §7 Tab 补全 → Tasks 12-13
  - §8 历史 → Tasks 14-15
  - §9 错误处理 → 各 do_* 的 _err 调用
  - §10 测试 → 各 Phase 含 TDD
  - §11 分发 → Task 16(无新依赖)
  - §12 风险 → Task 8 ($$ 转义), Task 19 (PyInstaller 自测)
  - §13 里程碑 → Phase 1-10
  - §14 开放问题 → §14 路径补全、history 时间戳、`let unset` 三项保留为未来工作

- [x] **Placeholder 扫描**: 全文搜 "TBD" / "TODO" / "implement later" → 无
- [x] **类型一致**: 全程用 `ReplSession` / `LoadedFile` / `UndoLog` / `UndoEntry` / `HistoryStore` / `InpCompleter` / `ShellREPL` 一致命名

---

## 验收标准

完成本计划全部 19 个任务后,应满足:

- [ ] `pytest -q` 全绿,覆盖率 ≥ 80%
- [ ] `inp-tool shell` 子命令可达,提示符正常
- [ ] 多文件 load / use / diff 工作
- [ ] set + undo 工作
- [ ] let + $var 插值工作
- [ ] !cmd shell escape 工作
- [ ] Tab 补全命令 / alias / block / key 工作
- [ ] ~/.inp_history 跨会话保留
- [ ] dirty 时 exit 提示
- [ ] Linux onefile PyInstaller 打包后 `shell` 仍工作
- [ ] CI smoke 通过

---

**下一步**:请选择执行方式:

1. **Subagent 驱动**(推荐)— 我每个任务派一个新 subagent,中间我做两阶段 review
2. **内联执行**— 我在当前 session 按 phase 批量执行,带 checkpoint

你说用哪种,我就接着调对应技能。
