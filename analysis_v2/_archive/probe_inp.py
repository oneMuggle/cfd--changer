"""mcfd.inp 格式普查 - 扫所有样本统计结构"""
import os, re
from collections import Counter, defaultdict

INP_DIR = r'E:\softwareData\edge\download\inp'
files = sorted([f for f in os.listdir(INP_DIR) if f.endswith('.inp')])

print(f'Files: {len(files)}')
sizes = []
block_count = Counter()
kw_count = Counter()
block_presence = defaultdict(int)  # 每个 block 在多少个文件里出现
line_starts = {}  # 文件 -> 行数

# 块正则
block_pat = re.compile(r'^(\w+)\s+(begin|end)\s*$')
# 语句:首词
stmt_pat = re.compile(r'^([a-zA-Z_][\w]*)\s*(.*)$')

for fn in files:
    path = os.path.join(INP_DIR, fn)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    sizes.append(len(text))
    lines = text.split('\n')
    line_starts[fn] = len(lines)
    in_block = None
    for line in lines:
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        m = block_pat.match(s)
        if m:
            name, kind = m.group(1), m.group(2)
            if kind == 'begin':
                in_block = name
                block_presence[name] += 1
            elif kind == 'end':
                in_block = None
            continue
        m2 = stmt_pat.match(s)
        if m2:
            kw = m2.group(1)
            kw_count[kw] += 1

print(f'\n文件大小: min={min(sizes)} max={max(sizes)} avg={sum(sizes)//len(sizes)} bytes')
print(f'行数: min={min(line_starts.values())} max={max(line_starts.values())}')

print(f'\n=== Block 出现频度 ===')
for b, c in sorted(block_presence.items(), key=lambda x: -x[1]):
    print(f'  {b}: {c}/{len(files)}')

print(f'\n=== 高频 keyword (前 30) ===')
for kw, c in kw_count.most_common(30):
    print(f'  {kw}: {c}')

# 找每个文件第一个非空非注释行
print(f'\n=== 头部前 3 行(去注释) ===')
for fn in files[:5]:
    path = os.path.join(INP_DIR, fn)
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        text = f.read()
    lines = [l.strip() for l in text.split('\n') if l.strip() and not l.strip().startswith('#')]
    print(f'  {fn}: {lines[:3]}')
