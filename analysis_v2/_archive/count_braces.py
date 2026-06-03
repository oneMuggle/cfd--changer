"""Check brace count per line"""
t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()
lines = t.split('\n')
cum = 0
for i, line in enumerate(lines[:50], 1):
    o = line.count('{')
    c = line.count('}')
    cum += o - c
    marker = ''
    if o > 0 or c > 0:
        marker = f'  [o={o} c={c} cum={cum}]'
    print(f'L{i:3d}: {line}{marker}')
