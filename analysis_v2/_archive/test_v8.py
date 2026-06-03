import time
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
import analyzer8

t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)
t0 = time.time()
ls = analyzer8.make_line_starts(t)
print('line_starts', len(ls), 'time', round(time.time() - t0, 2), flush=True)
t1 = time.time()
s, p = analyzer8.find_source_and_procs(t, ls)
print('parse', len(p), 'procs,', len(s), 'sources, time', round(time.time() - t1, 2), flush=True)
print('first 3 procs:', [x['name'] for x in p[:3]])
