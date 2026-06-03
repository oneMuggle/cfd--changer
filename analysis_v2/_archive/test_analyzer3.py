"""Test find_procs speed"""
import sys, time
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
import analyzer3

# 只测试几个文件
test_files = ['cfd++.tk', 'bcstuff.tcl', 'mcfdsol.tk', 'run_mcfd.tcl', 'gui_menu.tcl']
for fn in test_files:
    path = f'E:/software/CFD++/METACOMP/mlib/mcfd.18.5/exec/gui_src/{fn}'
    print(f'Reading {fn}...', flush=True)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    print(f'  size={len(text)}', flush=True)
    t0 = time.time()
    sources = analyzer3.find_source_lines(text)
    print(f'  sources: {len(sources)} in {time.time()-t0:.2f}s', flush=True)
    t1 = time.time()
    procs = analyzer3.find_procs_in_text(text)
    print(f'  procs: {len(procs)} in {time.time()-t1:.2f}s', flush=True)
print('done')
