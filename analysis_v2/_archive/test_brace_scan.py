import time
t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)

# 测我的 brace 扫描循环
n = len(t)
t0 = time.time()
i = 0
total_braces = 0
while i < n:
    c = t[i]
    if c == '{':
        depth = 1
        i += 1
        while i < n and depth > 0:
            if t[i] == '{': depth += 1
            elif t[i] == '}': depth -= 1
            i += 1
        total_braces += 1
    else:
        i += 1
print('brace scan time', round(time.time()-t0, 2), 'braces', total_braces, flush=True)
