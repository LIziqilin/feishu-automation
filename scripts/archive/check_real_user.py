#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess, json

all_msgs = []
page_token = None
for page in range(10):
    cmd = ["lark-cli", "im", "+chat-messages-list",
           "--chat-id", "oc_1fe154e172ab04622b7ffa810ac172bc",
           "--order", "desc", "--page-size", "50", "--format", "json"]
    if page_token:
        cmd += ["--page-token", page_token]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    d = json.loads(r.stdout)
    data = d.get('data', {})
    all_msgs.extend(data.get('messages', []))
    page_token = data.get('page_token')
    if not data.get('has_more') or not page_token:
        break

all_msgs.sort(key=lambda m: m.get('create_time',''))
sys_prefix = ('✅','✓','❓','📅','📊','🎯','📈','💪','⚠️','📋','💡','🔍','↩️','📇','📭','☀️','🌙','☁️','<','🔴')
print(f"共{len(all_msgs)}条")
print("=== 今天所有【真实用户指令】===")
for m in all_msgs:
    ct = m.get('create_time','')
    if not ct.startswith('2026-09-15'): continue
    c = m.get('content','')
    try: c = json.loads(c).get('text',c)
    except: pass
    c = c.strip()
    if not c or c.startswith(sys_prefix): continue
    st = m.get('sender',{}).get('sender_type','?')
    print(f"[{ct[11:]}][{st}] {c[:70]}")
