"""Run analyzer3 with progress print"""
import sys, time
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\analysis_v2')
import os, json
from collections import defaultdict
import analyzer3

GUI_SRC = analyzer3.GUI_SRC
OUTPUT_DIR = analyzer3.OUTPUT_DIR

files = analyzer3.collect_files()
print(f"Files: {len(files)}", flush=True)
all_procs = set()
file_data = {}

t_start = time.time()
for idx, fn in enumerate(files):
    if idx % 10 == 0:
        print(f'[{idx}/{len(files)}] Phase1: {fn}...', flush=True)
    path = os.path.join(GUI_SRC, fn)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    sources = analyzer3.find_source_lines(text)
    procs = analyzer3.find_procs_in_text(text)
    for p in procs:
        all_procs.add(p['name'])
    file_data[fn] = {
        'sources': sources,
        'procs': procs,
    }

print(f"\nPhase 1 done in {time.time()-t_start:.1f}s", flush=True)
print(f"Total procs: {len(all_procs)}", flush=True)

# Phase 2
t2 = time.time()
for idx, (fn, fd) in enumerate(file_data.items()):
    if idx % 10 == 0:
        print(f'[{idx}/{len(file_data)}] Phase2: {fn}...', flush=True)
    for p in fd['procs']:
        p['globals'] = analyzer3.find_globals_in_body(p['body'])
        p['execs'] = analyzer3.find_exec_in_body(p['body'])
        p['calls'] = analyzer3.find_calls_in_body(p['body'], all_procs)
print(f"\nPhase 2 done in {time.time()-t2:.1f}s", flush=True)

# 输出
out_json = os.path.join(OUTPUT_DIR, 'analysis_v3.json')
out = {}
for fn, fd in file_data.items():
    out[fn] = {
        'sources': fd['sources'],
        'procs': [
            {
                'name': p['name'],
                'args': p['args'][:200],
                'body_start_line': p['body_start_line'],
                'body_end_line': p['body_end_line'],
                'globals': p['globals'],
                'execs': p['execs'],
                'calls': p['calls'],
                'body_size': len(p['body']),
            }
            for p in fd['procs']
        ],
        'is_entry': fn in analyzer3.ENTRY_FILES,
        'entry_title': analyzer3.ENTRY_FILES.get(fn, ''),
    }
with open(out_json, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"Saved: {out_json} ({os.path.getsize(out_json)/1024:.1f} KB)", flush=True)
