"""
inp_tool v0.2 demo
"""
import sys, os
sys.path.insert(0, r'E:\ProgrammingData\python\cfd++changer\inp_tool')

from inp_tool import parse_file, write, diff
from inp_tool.writer import to_text

INP_DIR = r'E:\softwareData\edge\download\inp'
OUT_DIR = r'E:\ProgrammingData\python\cfd++changer\inp_tool\examples'

# 1. 解析
print('=== 1. 解析 mcfd.inp ===')
inp = parse_file(os.path.join(INP_DIR, 'mcfd.inp'))
print(f'  块数: {len(inp.block_list)} (含重复 system)')
for b in inp.block_list:
    print(f'    [{inp.block_list.index(b)}] {b.name}  L{b.begin_line}-{b.end_line}  ({len(b.statements)} stmts)')
print(f'  顶层语句数: {len(inp.top_stmts)}')

# 2. 多行 values (info set)
print('\n=== 2. 多行 values 复合语句(修复 1)===')
seq_stmts = [s for s in inp.top_stmts if s.keyword.startswith('seq')]
print(f'  顶层 seq.# 语句数: {len(seq_stmts)}')
if seq_stmts:
    s = seq_stmts[0]
    print(f'  第一个 seq: {s.keyword} {s.values_raw}')
    print(f'  children 行数: {len(s.children)}')
    if s.children:
        print(f'  第一个 child: {s.children[0].keyword} {s.children[0].values_raw}')

# 3. 重复块(修复 2)
print('\n=== 3. 重复同名块(修复 2)===')
sys_blocks = inp.all_blocks('system')
print(f'  system 块数: {len(sys_blocks)}')
for i, b in enumerate(sys_blocks):
    print(f'  system[{i}]  L{b.begin_line}-{b.end_line}  {len(b.statements)} stmts')

# 4. 访问 + 修改
print('\n=== 4. 访问 + 修改 ===')
print(f'  tsteps.cflbot = {inp.get("tsteps", "cflbot")}')
print(f'  tsteps.ntstep = {inp.get("tsteps", "ntstep")}')
inp.set('tsteps', 'cflbot', 0.005)
inp.set('tsteps', 'ntstep', 50000)
inp.set('physics', 'gasnam', 'N2')
print(f'  新 cflbot = {inp.get("tsteps", "cflbot")}')

# 5. 行尾注释保留(修复 3)
print('\n=== 5. 行尾注释保留(修复 3)===')
cfl_stmt = inp.get_block('tsteps').get_stmt('cflbot')
print(f'  cflbot comment: {cfl_stmt.comment_after!r}')

# 6. 写回 + 重新解析
print('\n=== 6. 写回 + 重新解析 ===')
out_path = os.path.join(OUT_DIR, 'mcfd_v2_modified.inp')
write(inp, out_path)
print(f'  写入: {out_path}')
re_parsed = parse_file(out_path)
assert re_parsed.get('tsteps', 'cflbot') == 0.005
assert re_parsed.get('tsteps', 'ntstep') == 50000
assert re_parsed.get('physics', 'gasnam') == 'N2'
# 检查 children 也保留
seq2 = [s for s in re_parsed.top_stmts if s.keyword.startswith('seq')]
assert len(seq2[0].children) == len(seq_stmts[0].children)
print('  [OK] round-trip 成功(值、children、块都保留)')

# 7. Diff
print('\n=== 7. Diff 原始 vs 修改 ===')
orig = parse_file(os.path.join(INP_DIR, 'mcfd.inp'))
r = diff(orig, re_parsed)
print(f'  差异: {len(r)} 条')
for e in r.changes:
    print(f'    {e}')

# 8. unified 风格
print('\n=== 8. Unified diff ===')
print(r.unified('mcfd.inp', 'mcfd_v2_modified.inp'))
