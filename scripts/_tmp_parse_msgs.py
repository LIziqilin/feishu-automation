# -*- coding: utf-8 -*-
import re, io, sys, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
raw = open('_tmp_msgs2.json', 'rb').read().decode('utf-16')
print("LEN", len(raw))
for kw in ['今日复习', '三件事', '到期提醒', '待办', '复利', '维保']:
    print(kw, kw in raw)
print("=== create_time list ===")
print(re.findall(r'"create_time"\s*:\s*"?([0-9\- :]+)', raw)[:20])
print("=== sample tail ===")
print(raw[-600:])
