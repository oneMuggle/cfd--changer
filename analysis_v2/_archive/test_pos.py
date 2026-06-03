import time
t = open(r'D:\software\CFD++\METACOMP\mlib\mcfd.18.5\exec\gui_src\bcstuff.tcl', encoding='utf-8', errors='replace').read()
n = len(t)
pos = 1206894
print('Around pos', pos, ':')
print(repr(t[pos-50:pos+200]))
