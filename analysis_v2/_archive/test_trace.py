import time
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')

# 复制 analyzer8 的函数,加 print
from analyzer8 import make_line_starts

def find_sp(text, line_starts):
    sources = []
    procs = []
    n = len(text)
    i = 0
    proc_count = 0
    brace_count = 0
    while i < n:
        c = text[i]
        if c in ' \t\r\n': i += 1; continue
        if c == '#':
            while i < n and text[i] != '\n': i += 1
            continue
        if c == '{':
            brace_count += 1
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
        start = i
        while i < n:
            c2 = text[i]
            if c2 in ' \t\r\n;#': break
            if c2 in '{["': break
            if c2 == '\\' and i + 1 < n and text[i+1] in '\n\r':
                i += 2
                if i < n and text[i-1] == '\r' and text[i] == '\n': i += 1
                continue
            if c2 == '\\' and i + 1 < n:
                i += 2
                continue
            i += 1
        word = text[start:i]
        if proc_count < 5 and word == 'proc':
            print(f'  Found proc at pos {start}, line {text[:start].count(chr(10))+1}, scanning body...', flush=True)
        if word == 'proc':
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
                t0 = time.time()
                depth = 1; i += 1
                while i < n and depth > 0:
                    if text[i] == '{': depth += 1
                    elif text[i] == '}': depth -= 1
                    i += 1
                body_end = i - 1
                if proc_count < 5:
                    print(f'    Body scan: {round(time.time()-t0,2)}s, size={body_end-body_start}, name={proc_name}', flush=True)
                proc_count += 1
                procs.append(proc_name)
    print(f'Total braces skipped: {brace_count}, procs: {proc_count}', flush=True)
    return sources, procs

t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)
t0 = time.time()
ls = make_line_starts(t)
print('ls done', flush=True)
s, p = find_sp(t, ls)
print('total time', round(time.time()-t0, 2), 'procs', len(p), flush=True)
