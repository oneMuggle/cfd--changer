"""Test tokenize on one file"""
import sys
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
from analyzer2 import tokenize, find_procs

text = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()
print(f'File size: {len(text)} chars, {text.count(chr(10))+1} lines')
import time
t0 = time.time()
print('Starting tokenize...')
sys.stdout.flush()
stmts = tokenize(text)
print(f'Tokenize: {len(stmts)} stmts in {time.time()-t0:.2f}s')
sys.stdout.flush()
t1 = time.time()
print('Starting find_procs...')
sys.stdout.flush()
procs = find_procs(text)
print(f'find_procs: {len(procs)} procs in {time.time()-t1:.2f}s')
sys.stdout.flush()
print('Sample procs:', [p['name'] for p in procs[:5]])
print('Sample stmts:', stmts[:5])
