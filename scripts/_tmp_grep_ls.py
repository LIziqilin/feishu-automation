# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
p = r"D:\AI-Tools\feishu\V13方案增强\scripts\learning_system.py"
t = open(p, encoding='utf-8').read().splitlines()
print("total", len(t))
for i, l in enumerate(t, 1):
    if re.search(r'(def cmd_|add_argument|--poll|--consume|def main|VALID_RESULTS|def _handle_answer|def handle_answer|answer)', l):
        print(i, l)
