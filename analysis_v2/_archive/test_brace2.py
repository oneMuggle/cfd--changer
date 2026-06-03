"""Debug: track all brace changes"""
text = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()

i = 0
n = len(text)
line = 1
events = []
depth = 0
in_brace = False
in_comment = False
max_i = 6000  # 只看前 6000 字符
while i < n and i < max_i:
    c = text[i]
    if c == '\n':
        line += 1
    if in_brace:
        if c == '{':
            depth += 1
            events.append(('INNER_OPEN', line, i, depth))
        elif c == '}':
            depth -= 1
            events.append(('INNER_CLOSE', line, i, depth))
            if depth == 0:
                events.append(('OUTER_CLOSE', line, i))
                in_brace = False
    else:
        if c == '#':
            in_comment = True
        if c == '\n':
            in_comment = False
        if not in_comment:
            if c == '{':
                in_brace = True
                depth = 1
                events.append(('OUTER_OPEN', line, i))
    i += 1

print(f'Events ({len(events)}):')
for e in events:
    print(' ', e)
