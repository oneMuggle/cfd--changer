"""
CFD++ GUI 调用关系分析器 v10 - 修复 $ 变量引用
"""
import os
import re
import json
import bisect
from collections import defaultdict

GUI_SRC = r"D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src"
OUTPUT_DIR = r"E:\ProgrammingData\python\cfd++changer\analysis_v2"

ENTRY_FILES = {
    'cfd++.tk': 'CFD++主GUI', 'mcfdsol.tk': 'META Visualizer',
    'mcfdplt.tk': '残差绘图(简单)', 'mcfdplt2.tk': '残差绘图(run_cmd)',
    'mcfdtplt.tk': '残差绘图(工具栏)', 'mcfdpplt.tk': '探针绘图',
    'mcfdfplt.tk': '力/力矩绘图', 'mcfdfft.tk': 'FFT分析',
    'mcfd1dp.tk': 'XY曲线绘图', 'logview.tk': '日志查看器',
}


def collect_files():
    return sorted([e for e in os.listdir(GUI_SRC)
                   if os.path.isfile(os.path.join(GUI_SRC, e))
                   and (e.endswith('.tcl') or e.endswith('.tk'))])


def make_line_starts(text):
    ls = [0]
    pos = 0
    while True:
        pos = text.find('\n', pos)
        if pos == -1: break
        ls.append(pos + 1)
        pos += 1
    return ls


def find_source_and_procs(text, line_starts):
    sources = []
    procs = []
    n = len(text)
    i = 0
    while i < n:
        c = text[i]
        if c in ' \t\r\n;':
            i += 1
            continue
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '{':
            depth = 1; i += 1
            while i < n and depth > 0:
                if text[i] == '{': depth += 1
                elif text[i] == '}': depth -= 1
                i += 1
            continue
        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\' and i + 1 < n: i += 2
                else: i += 1
            if i < n: i += 1
            continue
        if c == '[':
            depth = 1; i += 1
            while i < n and depth > 0:
                if text[i] == '[': depth += 1
                elif text[i] == ']': depth -= 1
                i += 1
            continue
        # 普通 word,支持 $VAR 和 ${VAR}
        start = i
        while i < n:
            c2 = text[i]
            if c2 in ' \t\r\n;#': break
            # $var 或 ${var} 是变量引用,作为 word 一部分
            if c2 == '$' and i + 1 < n and text[i+1] == '{':
                # ${var} 整个读作一个 unit
                i += 2  # skip ${
                depth = 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                continue
            if c2 == '[':
                break  # [cmd] 是单独的 word
            if c2 == '{':
                break  # {string} 是单独的 word
            if c2 == '"':
                break
            if c2 == '\\' and i + 1 < n and text[i+1] in '\n\r':
                i += 2
                if i < n and text[i-1] == '\r' and text[i] == '\n': i += 1
                continue
            if c2 == '\\' and i + 1 < n:
                i += 2
                continue
            i += 1
        word = text[start:i]
        if word == 'source':
            # 读 filename - 同样支持 ${var}
            while i < n and text[i] in ' \t\r\n': i += 1
            fn_start = i
            while i < n:
                c2 = text[i]
                if c2 in ' \t\r\n;#': break
                if c2 == '$' and i + 1 < n and text[i+1] == '{':
                    i += 2
                    depth = 1
                    while i < n and depth > 0:
                        if text[i] == '{': depth += 1
                        elif text[i] == '}': depth -= 1
                        i += 1
                    continue
                if c2 in '{["': break
                if c2 == '\\' and i + 1 < n:
                    if text[i+1] in '\n\r':
                        i += 2
                        if i < n and text[i-1] == '\r' and text[i] == '\n': i += 1
                        continue
                    i += 2
                    continue
                i += 1
            fn = text[fn_start:i]
            line = bisect.bisect_right(line_starts, start) - 1
            sources.append((line + 1, fn))
        elif word == 'proc':
            while i < n and text[i] in ' \t\r\n': i += 1
            name_start = i
            while i < n and text[i] not in ' \t\r\n{["': i += 1
            proc_name = text[name_start:i]
            while i < n and text[i] in ' \t\r\n': i += 1
            if i < n and text[i] == '{':
                args_start = i + 1
                depth = 1; i += 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                args_text = text[args_start:i-1]
            else:
                args_text = ''
            while i < n and text[i] in ' \t\r\n': i += 1
            if i < n and text[i] == '{':
                body_start = i + 1
                body_start_line = bisect.bisect_right(line_starts, i) - 1
                depth = 1; i += 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                body_end = i - 1
                body_end_line = bisect.bisect_right(line_starts, body_end) - 1
                body_text = text[body_start:body_end]
                procs.append({
                    'name': proc_name, 'args': args_text.strip(),
                    'body_start_line': body_start_line + 1,
                    'body_end_line': body_end_line + 1,
                    'body': body_text,
                })
    return sources, procs


def find_globals_in_body(body):
    gl = []
    for line in body.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'): continue
        m = re.match(r'^global\s+(.+)$', s)
        if m:
            for v in m.group(1).split():
                if not v.startswith('#'): gl.append(v)
    return gl


def find_exec_in_body(body):
    res = []
    for i, line in enumerate(body.split('\n'), 1):
        s = line.strip()
        if not s or s.startswith('#'): continue
        m = re.match(r'^\s*exec\s+(\S+)', line)
        if m: res.append((i, 'exec', m.group(1)))
        if 'blt::bgexec' in line:
            m = re.search(r'blt::bgexec\s+(\S+)', line)
            if m: res.append((i, 'bgexec', m.group(1)))
        if 'eval exec' in line: res.append((i, 'eval_exec', '<var>'))
    return res


def find_calls_in_body(body, all_known):
    calls = defaultdict(int)
    for line in body.split('\n'):
        s = line.strip()
        if not s or s.startswith('#'): continue
        for w in re.findall(r'[a-zA-Z_][\w:]*', s):
            if w in all_known: calls[w] += 1
    return dict(calls)


def main():
    files = collect_files()
    print(f"Files: {len(files)}", flush=True)
    fd_all = {}
    all_procs = set()
    import time
    t0 = time.time()
    for idx, fn in enumerate(files):
        path = os.path.join(GUI_SRC, fn)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        line_starts = make_line_starts(text)
        sources, procs = find_source_and_procs(text, line_starts)
        for p in procs:
            all_procs.add(p['name'])
        fd_all[fn] = {'sources': sources, 'procs': procs}
        if idx % 20 == 0:
            print(f'  [{idx}/{len(files)}] {fn}: {len(procs)}p {len(sources)}s ({time.time()-t0:.1f}s)', flush=True)
    print(f"\nPhase 1 done in {time.time()-t0:.1f}s, total procs: {len(all_procs)}", flush=True)

    t1 = time.time()
    for fn, fd in fd_all.items():
        for p in fd['procs']:
            p['globals'] = find_globals_in_body(p['body'])
            p['execs'] = find_exec_in_body(p['body'])
            p['calls'] = find_calls_in_body(p['body'], all_procs)
    print(f"Phase 2 done in {time.time()-t1:.1f}s", flush=True)

    out_json = os.path.join(OUTPUT_DIR, 'analysis_v10.json')
    out = {}
    for fn, fd in fd_all.items():
        out[fn] = {
            'sources': fd['sources'],
            'procs': [
                {
                    'name': p['name'], 'args': p['args'][:200],
                    'body_start_line': p['body_start_line'],
                    'body_end_line': p['body_end_line'],
                    'globals': p['globals'],
                    'execs': p['execs'],
                    'calls': p['calls'],
                    'body_size': len(p['body']),
                } for p in fd['procs']
            ],
            'is_entry': fn in ENTRY_FILES,
            'entry_title': ENTRY_FILES.get(fn, ''),
        }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Saved: {out_json} ({os.path.getsize(out_json)/1024:.1f} KB)", flush=True)


if __name__ == '__main__':
    main()
