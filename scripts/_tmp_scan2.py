# -*- coding: utf-8 -*-
import io, sys, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
raw = open('_m.txt', 'rb').read()
txt = raw.decode('utf-8-sig', errors='replace')
if '"create_time"' not in txt:
    txt = raw.decode('utf-16', errors='ignore')
blocks = txt.split('"create_time"')
print("blocks", len(blocks))
for i in range(1, len(blocks)):
    m = re.search(r'"\s*([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})', blocks[i])
    t = m.group(1) if m else "?"
    prev = blocks[i - 1]
    kws = [k for k in ("今日复习", "三件事", "到期提醒", "今日待办", "答案", "下次复习", "复利") if k in prev]
    print(t, "|", ",".join(kws) if kws else "-")
