import time
t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), 'opens', t.count('{'), 'closes', t.count('}'), 'braces balanced?', t.count('{') == t.count('}'), flush=True)
# 计算嵌套深度峰值
n = len(t)
depth = 0
max_d = 0
for c in t:
    if c == '{':
        depth += 1
        if depth > max_d: max_d = depth
    elif c == '}':
        depth -= 1
print('max brace depth:', max_d, flush=True)
# 测一下普通的逐字符扫
t0 = time.time()
count = 0
for c in t:
    if c == '{': count += 1
print('count time', round(time.time()-t0, 2), flush=True)
