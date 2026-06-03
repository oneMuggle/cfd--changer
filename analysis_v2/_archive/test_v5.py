"""Test parse_file on small file"""
import sys, time
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
from analyzer5 import parse_file, GUI_SRC
import os

fn = 'bcsort.tcl'
path = os.path.join(GUI_SRC, fn)
with open(path, 'r', encoding='utf-8', errors='replace') as f:
    text = f.read()
print(f'size={len(text)}', flush=True)
t0 = time.time()
sources, procs = parse_file(text)
print(f'parse: {len(procs)} procs, {len(sources)} sources in {time.time()-t0:.2f}s', flush=True)
print('done')
