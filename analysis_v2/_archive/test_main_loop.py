import time
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
from analyzer8 import make_line_starts

t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)
n = len(t)
ls = make_line_starts(t)
i = 0
proc_count = 0
last_print = time.time()
while i < n:
    c = t[i]
    if time.time() - last_print > 2:
        print(f'  i={i} ({i*100//n}%) proc_count={proc_count}', flush=True)
        last_print = time.time()
    if c in ' \t\r\n': i += 1; continue
    if c == '#':
        while i < n and t[i] != '\n': i += 1
        continue
    if c == '{':
        depth = 1; i += 1
        while i < n and depth > 0:
            if t[i] == '{': depth += 1
            elif t[i] == '}': depth -= 1
            i += 1
        continue
    if c == '"':
        i += 1
        while i < n and t[i] != '"':
            if t[i] == '\\' and i + 1 < n: i += 2
            else: i += 1
        if i < n: i += 1
        continue
    if c == '[':
        depth = 1; i += 1
        while i < n and depth > 0:
            if t[i] == '[': depth += 1
            elif t[i] == ']': depth -= 1
            i += 1
        continue
    start = i
    while i < n:
        c2 = t[i]
        if c2 in ' \t\r\n;#': break
        if c2 in '{["': break
        if c2 == '\\' and i + 1 < n and t[i+1] in '\n\r':
            i += 2
            if i < n and t[i-1] == '\r' and t[i] == '\n': i += 1
            continue
        if c2 == '\\' and i + 1 < n:
            i += 2
            continue
        i += 1
    word = t[start:i]
    if word == 'proc':
        proc_count += 1
        while i < n and t[i] in ' \t\r\n': i += 1
        name_start = i
        while i < n and t[i] not in ' \t\r\n{["': i += 1
        proc_name = t[name_start:i]
        while i < n and t[i] in ' \t\r\n': i += 1
        if i < n and t[i] == '{':
            depth = 1; i += 1
            while i < n and depth > 0:
                if t[i] == '{': depth += 1
                elif t[i] == '}': depth -= 1
                i += 1
        while i < n and t[i] in ' \t\r\n': i += 1
        if i < n and t[i] == '{':
            depth = 1; i += 1
            while i < n and depth > 0:
                if t[i] == '{': depth += 1
                elif t[i] == '}': depth -= 1
                i += 1
print('DONE i=', i, 'procs=', proc_count, flush=True)
