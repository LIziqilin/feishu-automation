# -*- coding: utf-8 -*-
import io, sys, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
raw = open('_m.txt', 'rb').read()
txt = raw.decode('utf-8-sig', errors='replace')
if '"create_time"' not in txt:
    txt = raw.decode('utf-16', errors='ignore')

# 用正则抓 content 字段（可能含 \uXXXX 转义）
items = re.findall(r'"content"\s*:\s*"(.*?)"\s*,\s*"create_time"\s*:\s*"?([0-9\- :]+)', txt, re.S)
print("items", len(items))
for content, t in items:
    try:
        s = content.encode('utf-8').decode('unicode_escape').encode('latin1').decode('utf-8', 'replace')
    except Exception:
        s = content
    kws = [k for k in ("今日复习", "三件事", "到期提醒", "今日待办", "下次复习", "复利") if k in s]
    print(t, "|", (",".join(kws) if kws else s.replace("\\n", " / ")[:60]))
