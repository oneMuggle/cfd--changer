# analysis_v2/_archive/

Archived 2026-06-02 as part of root-level project cleanup (Step 1: archive 31 superseded analyzer scripts; only `analyzer11.py` + `gen_report2.py` remain at the parent level).

31 superseded scripts from the CFD++ GUI call-graph analysis working session
(2026-06-01). Two canonical scripts remain at the parent level:

| File (parent dir) | Role |
|---|---|
| `analyzer11.py` | GUI call-graph analyzer v11 (with `source` regex fallback) |
| `gen_report2.py` | Report generator v2 (37 KB) |

## Categories

- **Analyzer evolution (v1 → v10)**: `analyzer.py`, `analyzer2.py` … `analyzer10.py`.
  Naming convention: `analyzer{N+1}.py` is v{N+1} (so `analyzer.py` is v1).
  All superseded by `analyzer11.py`.
- **Report generator v1**: `gen_report.py`. Superseded by `gen_report2.py`.
- **Runner**: `analyzer3_run.py` — entry point for v3; resurrect together
  with `analyzer3.py` if you need it.
- **Early debug utilities**: `debug_brace.py`, `count_braces.py`.
- **Side investigation**: `probe_inp.py` — 2026-06-02 one-shot `mcfd.inp`
  format survey, not part of the analyzer line.
- **One-off test scripts** (16): `test_*.py` — exercise specific behavior of
  an old analyzer (N ∈ {2, 3, 5, 8}). Listed alphabetically below.

`test_a3_v2.py`, `test_analyzer3.py`, `test_brace.py`, `test_brace2.py`,
`test_brace_scan.py`, `test_braces.py`, `test_depth.py`, `test_init.py`,
`test_main_loop.py`, `test_one.py`, `test_pos.py`, `test_speed.py`,
`test_trace.py`, `test_v5.py`, `test_v8.py`, `test_v8b.py`.

## Resurrecting a script

These files are kept for archaeology, not for active use. To re-run one, `mv` it back:

```bash
mv analysis_v2/_archive/analyzer3.py analysis_v2/
mv analysis_v2/_archive/test_analyzer3.py analysis_v2/
python analysis_v2/analyzer3.py
```

Mtimes are preserved from their original locations — the move was `mv`,
not copy-then-edit. Files are byte-identical to what was in the parent
directory before 2026-06-02.
