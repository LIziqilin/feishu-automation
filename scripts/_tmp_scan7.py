# -*- coding: utf-8 -*-
import io, sys, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
txt = open('_m.txt', 'rb').read().decode('utf-8-sig', errors='replace')
objs = re.split(r'\n\s*\{\s*\n\s*"chat_id"', txt)
rows = []
for o in objs[1:]:
    def g(pat):
        m = re.search(pat, o, re.S)
        return m.group(1) if m else ""
    ct = g(r'"create_time"\s*:\s*"([0-9\- :]+)"')
    mtype = g(r'"msg_type"\s*:\s*"([^"]+)"')
    sid = g(r'"id"\s*:\s*"([^"]+)"')
    sname = g(r'"name"\s*:\s*"([^"]+)"')
    stype = g(r'"sender_type"\s*:\s*"([^"]+)"')
    cm = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', o)
    content = ""
    if cm:
        try:
            content = json.loads('"' + cm.group(1) + '"')
        except Exception:
            content = cm.group(1)
    rows.append((ct, stype, sid, sname, mtype, content))
rows.sort()
for ct, stype, sid, sname, mtype, content in rows:
    c = content.replace("\n", " | ")
    print(f"{ct} | {stype:4} | {sid[:22]:22} | {mtype:11} | {c[:60]}")
