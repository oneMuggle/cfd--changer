"""inp-tool 交互式 REPL。

继承 stdlib cmd.Cmd,把每条用户输入解析后委托给 cli.py 的 cmd_* handler。
状态由 ReplSession 管理,IO 通过 stdout/stderr。
"""
import cmd
import math
import sys
from typing import Dict, List, Optional

# NOTE: readline 是 Unix-only stdlib,Windows 没有。
# 因此 readline 必须在能用的地方做 late import:
# - ShellREPL.complete() (此文件内,line 103)
# - HistoryStore.bind_readline() (repl_history.py,try-guarded)
# 这里禁止写 `import readline`,否则 Windows 整个 repl 模块
# 都 import 不进来,并级联破坏从 .repl import REPL_COMMANDS
# 的 repl_completer。

from . import __version__
from .repl_history import HistoryStore
from .repl_state import ReplSession


# REPL 暴露的命令名集合(给 help / 补全用)
REPL_COMMANDS = {
    'load', 'unload', 'files', 'use', 'status', 'save',
    'info', 'get', 'set', 'diff', 'sweep', 'parse',
    'aero',  # 单算例 freestream 编辑
    'undo', 'let', 'help', 'history', 'exit', 'quit',
}


class ShellREPL(cmd.Cmd):
    intro = (
        f"inp-tool {__version__} interactive shell. "
        "Type 'help' for commands, 'exit' to quit."
    )
    prompt = 'inp> '

    def __init__(self, session: Optional[ReplSession] = None, completekey: str = 'tab'):
        super().__init__(completekey=completekey)
        self.session = session or ReplSession()
        self._refresh_prompt()
        # Lazy import: repl_completer imports REPL_COMMANDS from repl, so direct
        # top-level import in repl.py would create a cycle.
        from .repl_completer import InpCompleter
        self._completer = InpCompleter(self.session)
        self.history = HistoryStore()
        self.history.load()
        self.history.bind_readline()

    def onecmd(self, line):
        """在分发到 cmd.Cmd 前,先剥离 '<alias>:' 前缀,再做 $var 插值,最后记入历史。"""
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

    # ----- Tab 补全 ------------------------------------------------------

    def complete(self, text, state):
        """cmd.Cmd 调用入口。state 是第 N 次按 Tab(0..N-1)。

        简化策略:基于第一个 token 决定补全类别,忽略 state 索引
        (readline 会从返回列表中按顺序取第 state 个)。
        """
        try:
            import readline
            line = readline.get_line_buffer()
        except ImportError:
            line = ''  # 非 readline 环境(Windows 或非交互)下无 line buffer
        tokens = line.split()
        if not tokens or (len(tokens) == 1 and not text):
            # 第一个 token
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

    # ----- 内部辅助 -------------------------------------------------------

    def _refresh_prompt(self) -> None:
        if self.session.current:
            self.prompt = f'inp[{self.session.current}]> '
        else:
            self.prompt = 'inp> '

    def _err(self, msg: str) -> None:
        print(f'error: {msg}', file=sys.stderr)

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
        # $$ → $ 转义处理,但不展开 $var
        self.session.variables[name] = value.replace('$$', '$')

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
            # 恢复:把值写回(当前数据模型下 old_values 必为单值)
            from .model import infer_type
            b.set(entry.key, infer_type(entry.old_values[0]))
            # TODO: multi-value undo(待 Value.raw 支持 list 字段时启用)
            # 写盘(对齐 cmd_set 的语义:do_get 走 cmd_get 读盘)
            from .writer import write as writer_write
            writer_write(lf.inp, str(lf.path))
            lf.dirty = True
            print(f'undone: {entry.alias}.{entry.block}.{entry.key} restored')

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
        """files — 列出已加载 alias / 路径 / 状态(按 alias 字母序)"""
        if not self.session.files:
            print('(no files loaded)')
            return
        for a, lf in sorted(self.session.files.items()):
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

    def do_unload(self, arg):
        """unload ALIAS [-f] — 移除 alias(默认拒绝 dirty)"""
        parts = arg.strip().split()
        if not parts:
            self._err('unload requires an alias')
            return
        non_flags = [p for p in parts if p != '-f']
        if not non_flags:
            self._err('unload requires an alias')
            return
        alias = non_flags[0]
        force = '-f' in parts
        try:
            self.session.unload(alias, force=force)
        except KeyError:
            self._err(f"alias '{alias}' not loaded.")
            return
        except RuntimeError as e:
            self._err(str(e))
            return
        if self.session.current is None:
            self._refresh_prompt()

    def do_status(self, arg):
        """status — 列出每个 alias 的未保存改动

        TODO: 与 do_files 共享输出格式;若 status 演化(undo count, save time 等),可分裂
        """
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
        except PermissionError as e:
            self._err(f'permission denied: {path} ({e})')
            return
        except OSError as e:
            self._err(f'write failed: {path} ({e})')
            return
        self.session.files[alias].dirty = False
        self.session.files[alias].last_saved_text = to_text(self.session.files[alias].inp)
        self.session.files[alias].path = path
        print(f'saved: {alias} -> {path}')

    def do_exit(self, arg):
        """exit the REPL"""
        return True

    def do_quit(self, arg):
        """alias for exit"""
        return True

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
            # 同步 lf.inp 与磁盘(cmd_set 内部 parse+write,不动我们的指针)
            from .parser import parse_file
            lf.inp = parse_file(str(lf.path))
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

    def do_sweep(self, arg):
        """sweep [args...] — 批量生成算例(委托 cmd_sweep)"""
        from .cli import cmd_sweep
        try:
            tokens = arg.split()
        except ValueError as e:
            self._err(f'parse error: {e}')
            return
        # 构建一个与 cli.py sweep subparser 一致的本地 parser
        # (subparser 的 --t-inf 映射 dest=t_inf,--p-inf 映射 dest=p_inf)
        from argparse import ArgumentParser
        p = ArgumentParser(prog='sweep', add_help=False)
        p.add_argument('first', nargs='?', default=None)
        p.add_argument('config', nargs='?', default=None)
        p.add_argument('--alpha', default=None)
        p.add_argument('--beta', default=None)
        p.add_argument('--mach', default=None)
        p.add_argument('--t-inf', dest='t_inf', default=None)
        p.add_argument('--p-inf', dest='p_inf', default=None)
        p.add_argument('--out', default=None)
        p.add_argument('--manifest', default=None)
        p.add_argument('--dry-run', dest='dry_run', action='store_true')
        p.add_argument('-v', '--verbose', dest='verbose', action='store_true')
        p.add_argument('-i', '--interactive', dest='interactive', action='store_true')
        try:
            ns = p.parse_args(tokens)
        except SystemExit:
            # argparse 在参数错误时会 sys.exit;拦截并提示
            self._err('sweep: invalid arguments (see above)')
            return
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

    # ----- 单算例 freestream 编辑(do_aero) ----------------------------

    def _aero_keymap(self, key: str) -> Optional[str]:
        """把用户输入的 key 归一化到内部 state key。未知返回 None。"""
        k = key.lower()
        if k in ('ma', 'mach'):
            return 'ma'
        if k in ('alpha', 'aoa'):
            return 'alpha'
        if k == 'beta':
            return 'beta'
        if k in ('t', 't_inf', 't-inf', 'temp', 'temperature'):
            return 'T'
        if k in ('p', 'p_inf', 'p-inf', 'pres', 'pressure'):
            return 'p'
        return None

    def _aero_current(self) -> Dict[str, float]:
        """读当前 freestream 状态。缺失字段用项目级 fallback(mach=0,T=288.15,p=101325)。"""

        def _existing(block, key, cast, default):
            if block is None:
                return default
            v = block.get_value(key)
            if v is None:
                return default
            try:
                return cast(v.typed)
            except (TypeError, ValueError):
                return default

        if not self.session.current:
            return {
                'ma': 0.0, 'alpha': 0.0, 'beta': 0.0,
                'T': 288.15, 'p': 101325.0,
                'u': 0.0, 'v': 0.0, 'w': 0.0, 'refvel': 0.0,
            }
        lf = self.session.files[self.session.current]
        gb = lf.inp.get_block('guiopts', 0)
        pb = lf.inp.get_block('physics', 0)
        ma = _existing(gb, 'aero_ma', float, 0.0)
        alpha = _existing(gb, 'aero_alpha', float, 0.0)
        beta = _existing(gb, 'aerobeta', float, 0.0)
        T = _existing(gb, 'aero_temp', float, 288.15)
        p = _existing(gb, 'aero_pres', float, 101325.0)
        u = _existing(gb, 'aero_u', float, 0.0)
        v = _existing(gb, 'aero_v', float, 0.0)
        w = _existing(gb, 'aero_w', float, 0.0)
        refvel = _existing(pb, 'refvel', float, 0.0)
        return {
            'ma': ma, 'alpha': alpha, 'beta': beta, 'T': T, 'p': p,
            'u': u, 'v': v, 'w': w, 'refvel': refvel,
        }

    def _aero_raw(self, keymap: Dict[str, str]) -> Dict[str, str]:
        """读 guiopts 字段的 raw 字符串表示(给 undo 用)。
        仅对 keymap 中列出的 internal key 返回值。
        """
        out: Dict[str, str] = {}
        if not self.session.current:
            return out
        lf = self.session.files[self.session.current]
        gb = lf.inp.get_block('guiopts', 0)
        if gb is None:
            return out
        for internal, kw in keymap.items():
            v = gb.get_value(kw)
            if v is not None:
                out[internal] = v.raw
        return out

    def _aero_format(self, state: Dict[str, float]) -> str:
        """格式化 1 行 freestream 状态摘要。"""
        mag = math.sqrt(state['u'] ** 2 + state['v'] ** 2 + state['w'] ** 2)
        # 角度显示 1 位小数,其他用紧凑表示
        return (
            f"Ma={state['ma']:.4g}  α={state['alpha']:.1f}°  "
            f"β={state['beta']:.1f}°  T={state['T']:.4g}K  p={state['p']:.4g}Pa\n"
            f"U={state['u']:.4g}  V={state['v']:.4g}  W={state['w']:.4g}  "
            f"|V|={mag:.4g}  refvel={state['refvel']:.4g}"
        )

    def _aero_apply(
        self, new: Dict[str, float], changed: set,
        keymap: Dict[str, str], old_raw_map: Dict[str, str],
    ) -> None:
        """把 new 写回 lf.inp 的 guiopts / physics 块,标 dirty,推 undo。

        - new: 完整的新状态(mach/alpha/beta/T/p/u/v/w/refvel)
        - changed: 用户显式改的 internal key 集合
        - keymap: internal key -> guiopts keyword 的映射
        - old_raw_map: 改前对应 guiopts keyword 的 raw 字符串(供 undo)
        """
        from .parser import parse_file
        from .writer import write as writer_write
        from .repl_state import UndoEntry

        alias = self.session.current
        lf = self.session.files[alias]
        gb = lf.inp.get_block('guiopts', 0)
        pb = lf.inp.get_block('physics', 0)
        if gb is None or pb is None:
            self._err('aero: current file has no guiopts or physics block')
            return

        def _set_or_append(block, key, value):
            if block.set(key, value):
                return False  # 已存在,更新
            block.append(key, value)
            return True  # 新增

        # guiopts:写所有 8 个字段(强耦合)
        guiopts_pairs = {
            'aero_alpha': new['alpha'],
            'aerobeta': new['beta'],
            'aero_ma': new['ma'],
            'aero_u': new['u'],
            'aero_v': new['v'],
            'aero_w': new['w'],
            'aero_temp': new['T'],
            'aero_pres': new['p'],
        }
        for k, v in guiopts_pairs.items():
            _set_or_append(gb, k, v)

        # physics:refvel 总是写(recompute);reftem/refpre 跟随 T/p
        _set_or_append(pb, 'refvel', new['refvel'])
        if 'T' in changed:
            _set_or_append(pb, 'reftem', new['T'])
        if 'p' in changed:
            _set_or_append(pb, 'refpre', new['p'])

        # 写盘
        writer_write(lf.inp, str(lf.path))
        # 同步 lf.inp(避免连续 set 后 in-memory 落后)
        lf.inp = parse_file(str(lf.path))
        lf.dirty = True

        # 推 undo:只针对用户显式改的 guiopts 字段;
        # physics.refvel/reftem/refpre 是派生的,不单独 undo。
        for k in changed:
            guiopts_key = keymap[k]
            # 优先用 raw(给 infer_type 还原);缺失则用 typed 强转字符串
            if k in old_raw_map:
                old_raw = old_raw_map[k]
            else:
                # 新增的字段(模板没有),没有 old — 跳过 undo 推送
                # 这是空 old,do_undo 恢复时再处理
                old_raw = ''
            self.session.undo.push(UndoEntry(
                alias=alias, block='guiopts', key=guiopts_key,
                old_values=[old_raw],
            ))

    def do_aero(self, arg):
        """aero — 显示当前 freestream 状态(无参)或改 freestream(KEY=VALUE)"""
        if not self.session.current:
            self._err('aero: no file is current. use `load <path>` first.')
            return
        current = self._aero_current()

        if not arg.strip():
            print(self._aero_format(current))
            return

        # 解析 KEY=VALUE 串
        changes: Dict[str, float] = {}
        for token in arg.split():
            if '=' not in token:
                self._err(f'aero: expected KEY=VALUE, got {token!r}')
                return
            key, _, val = token.partition('=')
            key = key.strip()
            try:
                num = float(val)
            except ValueError:
                self._err(f'aero: {key} must be a number, got {val!r}')
                return
            norm = self._aero_keymap(key)
            if norm is None:
                self._err(
                    f"aero: unknown key {key!r}. supported: Ma, alpha, beta, T, p"
                )
                return
            changes[norm] = num

        # merge:changes 覆盖 current
        new_state = {**current, **changes}

        # 重算 U/V/W
        from .sweep import FreestreamPreset
        uvw = FreestreamPreset().compute_uvw({
            'alpha': new_state['alpha'],
            'beta': new_state['beta'],
            'mach': new_state['ma'],
            'T_inf': new_state['T'],
        })
        new_state['u'] = uvw['U']
        new_state['v'] = uvw['V']
        new_state['w'] = uvw['W']
        new_state['refvel'] = math.sqrt(
            uvw['U'] ** 2 + uvw['V'] ** 2 + uvw['W'] ** 2
        )

        # 读旧 raw(供 undo 用);只对用户改的字段
        keymap = {
            'ma': 'aero_ma',
            'alpha': 'aero_alpha',
            'beta': 'aerobeta',
            'T': 'aero_temp',
            'p': 'aero_pres',
        }
        old_raw_map = self._aero_raw(keymap)

        # 写回
        self._aero_apply(new_state, set(changes.keys()), keymap, old_raw_map)

        # 打印
        order = ['ma', 'alpha', 'beta', 'T', 'p']
        labels = {'ma': 'Ma', 'alpha': 'alpha', 'beta': 'beta', 'T': 'T', 'p': 'p'}
        change_str = ', '.join(
            f"{labels[k]} {current[k]}→{changes[k]}" for k in order if k in changes
        )
        print(f'aero: {change_str}')
        print(self._aero_format(new_state))


def main(preload: Optional[List[str]] = None) -> int:
    """REPL 入口。从 CLI 的 `shell` 子命令调用。

    preload: 启动时预加载的文件路径列表(自动按 basename 起 alias)。

    行为分流:
    - tty 模式: 走 cmd.Cmd.cmdloop() 交互式
    - 非 tty 模式 (管道/文件重定向): 逐行读 stdin,处理完即退出
    """
    import sys
    repl = ShellREPL()
    for path in preload or []:
        repl.onecmd(f'load {path}')
    if sys.stdin.isatty():
        try:
            repl.cmdloop()
        except KeyboardInterrupt:
            print()  # 换行
    else:
        # 非交互式: 读 stdin 的所有行,逐条 onecmd,EOF 后退出
        for line in sys.stdin:
            line = line.rstrip('\n')
            if not line:
                continue
            repl.onecmd(line)
    return 0
