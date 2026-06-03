"""Debug brace tracking"""
text = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()
text = text[:2000]
i = 0
n = len(text)
line = 1
events = []
depth = 0
in_str = None
iters = 0
while i < n and iters < 5000:
    c = text[i]
    iters += 1
    if c == '\n':
        line += 1
        i += 1
        continue
    if c == '\r':
        i += 1
        continue
    if in_str is None:
        if c == '#':
            while i < n and text[i] != '\n':
                i += 1
            continue
        if c == '{':
            in_str = '{'
            depth = 1
            events.append(('OPEN_BRACE', line, i))
            i += 1
            continue
        if c == '"':
            in_str = 'DOUBLE_QUOTE'
            i += 1
            continue
        if c == '[':
            in_str = '['
            i += 1
            continue
    elif in_str == 'DOUBLE_QUOTE':
        if c == '\\' and i+1 < n:
            i += 2
            continue
        if c == '"':
            in_str = None
        i += 1
    elif in_str == 'BRACE':
        if c == '{':
            depth += 1
            events.append(('NESTED_OPEN', line, i, depth))
        elif c == '}':
            depth -= 1
            if depth == 0:
                events.append(('CLOSE_BRACE', line, i))
                in_str = None
        i += 1
    elif in_str == '[':
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                in_str = None
        i += 1
    else:
        i += 1
print('Events:')
for e in events:
    print(' ', e)
