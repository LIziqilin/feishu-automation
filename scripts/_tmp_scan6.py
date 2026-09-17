# -*- coding: utf-8 -*-
import io, sys, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
txt = open('_m.txt', 'rb').read().decode('utf-8-sig', errors='replace')
objs = re.split(r'\n\s*\{\s*\n\s*"chat_id"', txt)
print("objs", len(objs) - 1)
rows = []
for o in objs[1:]:
    cm = re.search(r'"create_time"\s*:\s*"([0-9\- :]+)"', o)
    ct = cm.group(1) if cm else "?"
    cm2 = re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', o)
    content = cm2.group(1) if cm2 else ""
    try:
        content = json.loads('"' + content + '"')
    except Exception:
        pass
    rows.append((ct, content))
rows.sort()
for ct, content in rows:
    c = content.replace("\n", " | ")
    print(ct, "||", c[:90])
