# -*- coding: utf-8 -*-
import io, sys, subprocess, re, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ["PATH"] = r"C:\Users\Administrator\AppData\Roaming\QClaw\npm-global" + ";" + os.environ.get("PATH", "")
LARK = r"C:\Users\Administrator\AppData\Roaming\QClaw\npm-global\lark-cli.cmd"
CHAT = "oc_1fe154e172ab04622b7ffa810ac172bc"
r = subprocess.run([LARK, "im", "+chat-messages-list", "--chat-id", CHAT,
                    "--as", "user", "--page-size", "60", "--order", "desc"],
                   capture_output=True, timeout=90)
raw = r.stdout
txt = raw.decode("utf-8-sig", errors="replace")
# 逐条： message_id, create_time, content
recs = re.findall(r'"message_id"\s*:\s*"([^"]+)".*?"create_time"\s*:\s*"?([0-9\- :]+)"?.*?"content"\s*:\s*"(.*?)"\s*\}', txt, re.S)
print("recs", len(recs))
seen = {}
for mid, t, content in recs:
    try:
        s = json.loads('"' + content + '"')
    except Exception:
        s = content
    key = s[:40]
    dup = "DUP" if key in seen else "   "
    seen[key] = t
    line = s.replace("\n", " | ")
    print(f"{t} {dup} {line[:70]}")
