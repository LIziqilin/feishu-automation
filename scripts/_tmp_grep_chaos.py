# -*- coding: utf-8 -*-
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = r"D:\AI-Tools\feishu\V13方案增强\scripts\chaos_drill.py"
t = open(p, encoding='utf-8').read()
lines = t.splitlines()
print("total lines", len(lines))
for i, l in enumerate(lines, 1):
    if ("c1_" in l) or ("c2_" in l) or ("def c" in l and "(" in l) or ("C1" in l) or ("C2" in l) or ("proxy" in l.lower()) or ("3003" in l) or ("3002" in l) or ("proxy_ready" in l):
        print(i, l)
