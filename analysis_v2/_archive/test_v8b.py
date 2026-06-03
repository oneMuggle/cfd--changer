import time
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
from analyzer8 import find_source_and_procs, make_line_starts

t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
print('size', len(t), flush=True)
ls = make_line_starts(t)
print('ls', len(ls), flush=True)
t0 = time.time()
s, p = find_source_and_procs(t, ls)
print('parse time', round(time.time()-t0, 2), 'procs', len(p), 'sources', len(s), flush=True)
