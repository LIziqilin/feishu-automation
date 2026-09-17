# -*- coding: utf-8 -*-
import io, sys, subprocess, re, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
os.environ["PATH"] = r"C:\Users\Administrator\AppData\Local\hermes\node" + ";" + os.environ.get("PATH", "")

CHAT = "oc_1fe154e172ab04622b7ffa810ac172bc"
LARK = r"C:\Users\Administrator\AppData\Roaming\QClaw\npm-global\lark-cli.cmd"
r = subprocess.run([LARK, "im", "+chat-messages-list", "--chat-id", CHAT,
                    "--as", "user", "--page-size", "50", "--order", "desc"],
                   capture_output=True, timeout=90)
raw = r.stdout
print("rc", r.returncode, "bytes", len(raw))
for enc in ("utf-8", "utf-16", "utf-8-sig", "gbk"):
    try:
        txt = raw.decode(enc)
        if '"create_time"' in txt:
            print("decoded with", enc)
            break
    except Exception:
        continue
else:
    txt = raw.decode("utf-8", "replace")

blocks = txt.split('"create_time"')
print("blocks", len(blocks))
for i in range(1, len(blocks)):
    m = re.search(r'"\s*([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2})', blocks[i])
    t = m.group(1) if m else "?"
    prev = blocks[i - 1]
    kws = [k for k in ("今日复习", "三件事", "到期提醒", "今日待办", "答案", "下次复习") if k in prev]
    if kws:
        print(t, "|", ",".join(kws))
