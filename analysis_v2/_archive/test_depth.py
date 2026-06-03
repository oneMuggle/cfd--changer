"""Deep debug: track running depth"""
text = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\cfd++.tk', encoding='utf-8', errors='replace').read()

i = 0
n = len(text)
line = 1
events = []
depth = 0
in_brace = False
in_comment = False

while i < n:
    c = text[i]
    if c == '\n':
        line += 1
    if in_brace:
        if c == '{':
            depth += 1
            events.append((line, i, '{', depth))
        elif c == '}':
            depth -= 1
            events.append((line, i, '}', depth))
            if depth == 0:
                events.append((line, i, 'OUTER_CLOSE', 0))
                in_brace = False
    else:
        if c == '#' and not in_comment:
            in_comment = True
        elif c == '\n':
            in_comment = False
        if not in_comment and c == '{':
            in_brace = True
            depth = 1
            events.append((line, i, 'OUTER_OPEN', depth))
    i += 1
    if i > 3000 and len(events) > 50:
        break

# Print first 50 events with running depth
print(f'Total events: {len(events)}')
for ev in events[:50]:
    ln, pos, what, d = ev
    print(f'L{ln} pos{pos}: {what} depth={d}')
