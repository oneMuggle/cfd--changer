"""Debug tokenize - check brace depth at end"""
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')

text = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()

# 手动跟踪 read_word 的 brace 处理
i = 0
n = len(text)
line = 1
events = []
depth = 0
in_brace = False
brace_start_line = 0
while i < n:
    c = text[i]
    if c == '\n':
        line += 1
    if in_brace:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                events.append(('CLOSE', line, i))
                in_brace = False
    else:
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            line += 1
            i += 1
            continue
        if c == '{':
            in_brace = True
            depth = 1
            brace_start_line = line
            events.append(('OPEN', line, i))
    i += 1
    if i > 5000 and len(events) > 0 and events[-1][0] == 'OPEN':
        break

print(f'Total events: {len(events)}')
print(f'Final state: in_brace={in_brace}, depth={depth}, line={line}, i={i}')
for e in events[:30]:
    print(' ', e)
