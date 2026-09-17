# -*- coding: utf-8 -*-
import io, sys, subprocess, re, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ["PATH"] = r"C:\Users\Administrator\AppData\Roaming\QClaw\npm-global" + ";" + os.environ.get("PATH", "")
LARK = r"C:\Users\Administrator\AppData\Roaming\QClaw\npm-global\lark-cli.cmd"
CHAT = "oc_1fe154e172ab04622b7ffa810ac172bc"
r = subprocess.run([LARK, "im", "+chat-messages-list", "--chat-id", CHAT,
                    "--as", "user", "--page-size", "60", "--order", "desc"],
                   capture_output=True, timeout=90)
txt = r.stdout.decode("utf-8-sig", errors="replace")

# 每个对象的边界：以 "message_id" 切
objs = re.split(r'\{\s*"message_id"', txt)
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
    c = content.replace("\n", " | ").replace("\\n", " | ")
    print(ct, "||", c[:85])
