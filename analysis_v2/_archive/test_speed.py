import time
t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)
t0 = time.time()
ls = [0]
pos = 0
while True:
    pos = t.find('\n', pos)
    if pos == -1: break
    ls.append(pos + 1)
    pos += 1
print('line_starts', len(ls), 'time', round(time.time() - t0, 2))
