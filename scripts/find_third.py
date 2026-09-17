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

print(f"共{len(all_msgs)}条")
print("=== 所有含'第三'或'测试'的消息（完整）===")
for m in all_msgs:
    c = m.get('content','')
    raw = c
    try: c = json.loads(c).get('text',c)
    except: pass
    if '第三' in c:
        st = m.get('sender',{}).get('sender_type','?')
        print(f"[{m.get('create_time')}][{st}] mid={m.get('message_id')}")
        print(f"   内容repr: {repr(c[:120])}")
        print()
