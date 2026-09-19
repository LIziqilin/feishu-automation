#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""查群消息"""
import subprocess, json, datetime

cmd = ["lark-cli", "im", "+chat-messages-list",
       "--chat-id", "oc_1fe154e172ab04622b7ffa810ac172bc",
       "--order", "desc", "--page-size", "25", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
d = json.loads(r.stdout)
msgs = d.get('data', {}).get('messages', [])
print(f"消息数: {len(msgs)}")
print()
for m in msgs[:25]:
    sender = m.get('sender', {})
    st = sender.get('sender_type', '?')
    content = m.get('content', '')
    text = ''
    try:
        parsed = json.loads(content)
        text = parsed.get('text', str(parsed)[:100])
    except:
        text = str(content)[:100]
    ct = m.get('create_time', '')
    try:
        ts = datetime.datetime.fromtimestamp(int(ct)/1000).strftime('%m-%d %H:%M')
    except:
        ts = ct
    print(f"[{ts}][{st}] {text[:70]}")
