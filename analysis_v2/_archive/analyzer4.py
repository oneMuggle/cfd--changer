"""
CFD++ GUI 调用关系分析器 v4 - 优化版
"""
import os
import re
import json
import bisect
from collections import defaultdict

GUI_SRC = r"D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src"
OUTPUT_DIR = r"E:\ProgrammingData\python\cfd++changer\analysis_v2"

ENTRY_FILES = {
    'cfd++.tk': 'CFD++主GUI',
    'mcfdsol.tk': 'META Visualizer',
    'mcfdplt.tk': '残差绘图(简单)',
    'mcfdplt2.tk': '残差绘图(run_cmd)',
    'mcfdtplt.tk': '残差绘图(工具栏)',
    'mcfdpplt.tk': '探针绘图',
    'mcfdfplt.tk': '力/力矩绘图',
    'mcfdfft.tk': 'FFT分析',
    'mcfd1dp.tk': 'XY曲线绘图',
    'logview.tk': '日志查看器',
}


def collect_files():
    files = []
    for entry in sorted(os.listdir(GUI_SRC)):
        full = os.path.join(GUI_SRC, entry)
        if not os.path.isfile(full):
            continue
        if entry.endswith('.tcl') or entry.endswith('.tk'):
            files.append(entry)
    return files


def parse_file(text):
    """解析一个文件,返回 sources, procs。
    procs 每个有: name, args, body_start_line, body_end_line, body
    """
    sources = []
    procs = []

    # 预计算行起始位置
    line_starts = [0]
    for k in range(text.count('\n')):
        line_starts.append(text.find('\n', line_starts[-1]) + 1)
    line_starts.append(len(text))  # 哨兵

    def pos_to_line(pos):
        return bisect.bisect_right(line_starts, pos) - 1

    n = len(text)
    i = 0  # char position
    while i < n:
        c = text[i]
        # 跳过空白
        if c in ' \t\r\n':
            i += 1
            continue
        # 注释
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue
        # 读一个 word
        start = i
        if c == '{':
            # brace 字符串
            depth = 1
            i += 1
            while i < n and depth > 0:
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                i += 1
            word = text[start:i]
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\' and i + 1 < n:
                    i += 2
                    continue
                i += 1
            if i < n:
                i += 1
            word = text[start:i]
        elif c == '[':
            depth = 1
            i += 1
            while i < n and depth > 0:
                if text[i] == '[':
                    depth += 1
                elif text[i] == ']':
                    depth -= 1
                i += 1
            word = text[start:i]
        else:
            while i < n:
                c2 = text[i]
                if c2 in ' \t\r\n;#':
                    break
                if c2 in '{["':
                    break
                if c2 == '\\' and i + 1 < n and text[i+1] in '\n\r':
                    i += 2
                    if i < n and text[i-1] == '\r' and text[i] == '\n':
                        i += 1
                    continue
                if c2 == '\\' and i + 1 < n:
                    i += 2
                    continue
                i += 1
            word = text[start:i]
        # word 是当前词
        # 检查是否是 'source' 或 'proc'
        if word == 'source':
            # 下一个 word 是 filename
            # 跳过空白
            while i < n and text[i] in ' \t\r\n':
                if text[i] == '\n':
                    pass
                i += 1
            # 读 filename
            fn_start = i
            if i < n and text[i] in '{["':
                # 字符串
                c2 = text[i]
                if c2 == '{':
                    depth = 1
                    i += 1
                    while i < n and depth > 0:
                        if text[i] == '{': depth += 1
                        elif text[i] == '}': depth -= 1
                        i += 1
                elif c2 == '"':
                    i += 1
                    while i < n and text[i] != '"':
                        if text[i] == '\\' and i + 1 < n: i += 2
                        else: i += 1
                    if i < n: i += 1
                else:
                    depth = 1
                    i += 1
                    while i < n and depth > 0:
                        if text[i] == '[': depth += 1
                        elif text[i] == ']': depth -= 1
                        i += 1
                fn = text[fn_start:i]
            else:
                while i < n and text[i] not in ' \t\r\n;#{["':
                    if text[i] == '\\' and i + 1 < n and text[i+1] in '\n\r':
                        i += 2
                        if i < n and text[i-1] == '\r' and text[i] == '\n': i += 1
                        continue
                    if text[i] == '\\' and i + 1 < n: i += 2
                    else: i += 1
                fn = text[fn_start:i]
            sources.append((pos_to_line(start), fn))
        elif word == 'proc':
            # proc NAME { ARGS } { BODY
            # 跳过空白
            while i < n and text[i] in ' \t\r\n':
                i += 1
            # 读 name
            name_start = i
            while i < n and text[i] not in ' \t\r\n{["':
                i += 1
            proc_name = text[name_start:i]
            # 跳过空白
            while i < n and text[i] in ' \t\r\n':
                i += 1
            # 读 args (brace 字符串)
            if i < n and text[i] == '{':
                args_start = i
                depth = 1
                i += 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                args_text = text[args_start:i]
            else:
                args_text = ''
            # 跳过空白
            while i < n and text[i] in ' \t\r\n':
                i += 1
            # 读 body (brace 字符串)
            if i < n and text[i] == '{':
                body_start = i + 1
                body_start_line = pos_to_line(i)
                depth = 1
                i += 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                body_end = i - 1  # 不含 }
                body_end_line = pos_to_line(body_end)
                body_text = text[body_start:body_end]
                procs.append({
                    'name': proc_name,
                    'args': args_text.strip(),
                    'body_start_line': body_start_line + 1,
                    'body_end_line': body_end_line + 1,
                    'body': body_text,
                })
        # 其他 word 跳过,继续主循环
    return sources, procs


def find_globals_in_body(body):
    globals_list = []
    for line in body.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'^global\s+(.+)$', stripped)
        if m:
            for v in m.group(1).split():
                if not v.startswith('#'):
                    globals_list.append(v)
    return globals_list


def find_exec_in_body(body):
    results = []
    for i, line in enumerate(body.split('\n'), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        m = re.match(r'^\s*exec\s+(\S+)', line)
        if m:
            results.append((i, 'exec', m.group(1)))
        if 'blt::bgexec' in line:
            m = re.search(r'blt::bgexec\s+(\S+)', line)
            if m:
                results.append((i, 'bgexec', m.group(1)))
        if 'eval exec' in line:
            results.append((i, 'eval_exec', '<var>'))
    return results


def find_calls_in_body(body, all_known_procs):
    calls = defaultdict(int)
    for line in body.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        # 找所有 word
        words = re.findall(r'[a-zA-Z_][\w:]*', stripped)
        for w in words:
            if w in all_known_procs:
                calls[w] += 1
    return dict(calls)


def main():
    files = collect_files()
    print(f"Files: {len(files)}", flush=True)
    file_data = {}
    all_procs = set()

    import time
    t0 = time.time()
    for idx, fn in enumerate(files):
        path = os.path.join(GUI_SRC, fn)
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        sources, procs = parse_file(text)
        for p in procs:
            all_procs.add(p['name'])
        file_data[fn] = {'sources': sources, 'procs': procs}
        if idx % 20 == 0:
            print(f'  [{idx}/{len(files)}] {fn}: {len(procs)} procs, {len(sources)} sources ({time.time()-t0:.1f}s)', flush=True)

    print(f"\nPhase 1 done in {time.time()-t0:.1f}s. Total procs: {len(all_procs)}", flush=True)

    t1 = time.time()
    for fn, fd in file_data.items():
        for p in fd['procs']:
            p['globals'] = find_globals_in_body(p['body'])
            p['execs'] = find_exec_in_body(p['body'])
            p['calls'] = find_calls_in_body(p['body'], all_procs)
    print(f"Phase 2 done in {time.time()-t1:.1f}s", flush=True)

    out_json = os.path.join(OUTPUT_DIR, 'analysis_v4.json')
    out = {}
    for fn, fd in file_data.items():
        out[fn] = {
            'sources': fd['sources'],
            'procs': [
                {
                    'name': p['name'],
                    'args': p['args'][:200],
                    'body_start_line': p['body_start_line'],
                    'body_end_line': p['body_end_line'],
                    'globals': p['globals'],
                    'execs': p['execs'],
                    'calls': p['calls'],
                    'body_size': len(p['body']),
                }
                for p in fd['procs']
            ],
            'is_entry': fn in ENTRY_FILES,
            'entry_title': ENTRY_FILES.get(fn, ''),
        }
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"Saved: {out_json} ({os.path.getsize(out_json)/1024:.1f} KB)", flush=True)


if __name__ == '__main__':
    main()
