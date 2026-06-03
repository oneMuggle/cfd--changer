"""CFD++ GUI 调用关系分析器 v2"""
import os, json, sys

GUI_SRC = r"D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src"
OUTPUT_DIR = r"E:\ProgrammingData\python\cfd++changer\analysis_v2"


def collect_files():
    files = []
    for entry in sorted(os.listdir(GUI_SRC)):
        full = os.path.join(GUI_SRC, entry)
        if not os.path.isfile(full):
            continue
        if entry.endswith('.tcl') or entry.endswith('.tk'):
            files.append(entry)
    return files


def tokenize(text):
    stmts = []
    i = 0
    n = len(text)
    line = 1

    def skip_ws():
        nonlocal i, line
        while i < n:
            c = text[i]
            if c in ' \t':
                i += 1
            elif c == '\r':
                i += 1
            elif c == '\n':
                i += 1
                line += 1
            elif c == '\\' and i + 1 < n and text[i+1] in '\n\r':
                i += 1
                if text[i] == '\r' and i + 1 < n and text[i+1] == '\n':
                    i += 1
                if i < n:
                    i += 1
                line += 1
            elif c == '#':
                while i < n and text[i] != '\n':
                    i += 1
            else:
                break

    def read_word():
        nonlocal i, line
        if i >= n:
            return None
        c = text[i]
        start_line = line
        start = i
        if c == '{':
            depth = 1
            i += 1
            while i < n and depth > 0:
                c2 = text[i]
                if c2 == '{':
                    depth += 1
                elif c2 == '}':
                    depth -= 1
                elif c2 == '\n':
                    line += 1
                i += 1
            return text[start:i], start_line
        elif c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\' and i + 1 < n:
                    if text[i+1] == '\n':
                        line += 1
                    i += 2
                    continue
                if text[i] == '\n':
                    line += 1
                i += 1
            if i < n:
                i += 1
            return text[start:i], start_line
        elif c == '[':
            depth = 1
            i += 1
            while i < n and depth > 0:
                c2 = text[i]
                if c2 == '[':
                    depth += 1
                elif c2 == ']':
                    depth -= 1
                elif c2 == '\\' and i + 1 < n:
                    if text[i+1] == '\n':
                        line += 1
                    i += 2
                    continue
                elif c2 == '\n':
                    line += 1
                i += 1
            return text[start:i], start_line
        else:
            while i < n:
                c2 = text[i]
                if c2 in ' \t\r\n;#':
                    break
                if c2 in '{(["':
                    break
                if c2 == '\\' and i + 1 < n and text[i+1] in '\n\r':
                    i += 2
                    if i < n and text[i-1] == '\r' and text[i] == '\n':
                        i += 1
                    line += 1
                    continue
                if c2 == '\\' and i + 1 < n:
                    i += 2
                    continue
                i += 1
            return text[start:i], start_line

    skip_ws()
    while i < n:
        w = read_word()
        if w is None:
            break
        cmd_text, cmd_line = w
        args = []
        while i < n:
            c = text[i]
            if c in ';\n':
                break
            if c in ' \t\r':
                i += 1
                continue
            if c == '#':
                while i < n and text[i] != '\n':
                    i += 1
                break
            if c == '\\' and i + 1 < n and text[i+1] in '\n\r':
                i += 2
                if i < n and text[i-1] == '\r' and text[i] == '\n':
                    i += 1
                line += 1
                continue
            nw = read_word()
            if nw is None:
                break
            args.append(nw[0])
        stmts.append((cmd_text, args, cmd_line))
        while i < n and text[i] in ';\n\r':
            if text[i] == '\n':
                line += 1
            i += 1
        skip_ws()
    return stmts


def find_procs(text):
    procs = []
    n = len(text)
    i = 0
    line = 1
    while i < n:
        idx = text.find('proc', i)
        if idx == -1:
            break
        before = text[idx-1] if idx > 0 else ' '
        after = text[idx+4] if idx+4 < n else ' '
        if before in ' \t\n\r;' and after in ' \t\n\r':
            j = idx + 4
            cur_line = line
            while j < n and text[j] in ' \t\n\r':
                if text[j] == '\n':
                    line += 1
                j += 1
            name_start = j
            while j < n and text[j] not in ' \t\n\r{["':
                j += 1
            proc_name = text[name_start:j]
            while j < n and text[j] in ' \t\n\r':
                if text[j] == '\n':
                    line += 1
                j += 1
            if j < n and text[j] == '{':
                args_start = j
                depth = 1
                j += 1
                while j < n and depth > 0:
                    if text[j] == '{':
                        depth += 1
                    elif text[j] == '}':
                        depth -= 1
                    elif text[j] == '\n':
                        line += 1
                    j += 1
                proc_args = text[args_start+1:j-1]
                while j < n and text[j] in ' \t\n\r':
                    if text[j] == '\n':
                        line += 1
                    j += 1
                if j < n and text[j] == '{':
                    body_start_line = line
                    body_start_pos = j + 1
                    depth = 1
                    j += 1
                    while j < n and depth > 0:
                        if text[j] == '{':
                            depth += 1
                        elif text[j] == '}':
                            depth -= 1
                        elif text[j] == '\n':
                            line += 1
                        j += 1
                    body_end_pos = j - 1
                    body_end_line = line
                    procs.append({
                        'name': proc_name,
                        'args': proc_args,
                        'body_start': body_start_pos,
                        'body_end': body_end_pos,
                        'body_start_line': body_start_line,
                        'body_end_line': body_end_line,
                        'define_line': cur_line,
                    })
                    i = j
                    continue
        i = idx + 4
    return procs


def analyze_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    stmts = tokenize(text)
    procs = find_procs(text)
    return {'statements': stmts, 'procs': procs}


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


def main():
    files = collect_files()
    print(f"Files: {len(files)}")
    all_data = {}
    for fn in files:
        path = os.path.join(GUI_SRC, fn)
        try:
            data = analyze_file(path)
        except Exception as e:
            print(f"  ERROR {fn}: {e}")
            data = {'statements': [], 'procs': []}
        sources = [s for s in data['statements'] if s[0] == 'source']
        all_data[fn] = {
            'statements': data['statements'],
            'procs': data['procs'],
            'is_entry': fn in ENTRY_FILES,
            'entry_title': ENTRY_FILES.get(fn, ''),
        }
        print(f"  {fn}: {len(data['procs'])} procs, {len(sources)} sources, {len(data['statements'])} stmts")
    out_json = os.path.join(OUTPUT_DIR, 'analysis_v2.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=1)
    print(f"\nSaved: {out_json}")
    print(f"Size: {os.path.getsize(out_json)/1024:.1f} KB")


if __name__ == '__main__':
    main()
