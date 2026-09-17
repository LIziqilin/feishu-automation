#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess, json

all_msgs = []
page_token = None
for page in range(10):
    cmd = ["lark-cli", "im", "+chat-messages-list",
           "--chat-id", "oc_1fe154e172ab04622b7ffa810ac172bc",
           "--order", "desc", "--page-size", "50", "--format", "json"]
    if page_token: cmd += ["--page-token", page_token]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    d = json.loads(r.stdout)
    data = d.get('data', {})
    all_msgs.extend(data.get('messages', []))
    page_token = data.get('page_token')
    if not data.get('has_more') or not page_token: break

print("=== 所有'已创建任务'回执的完整sender ===")
for m in all_msgs:
    c = m.get('content','')
    try: c = json.loads(c).get('text',c)
    except: pass
    if '已创建任务' in c:
        print(f"[{m.get('create_time')}] {c[:40]}")
        print(f"   sender完整: {json.dumps(m.get('sender',{}), ensure_ascii=False)}")
        print(f"   msg_type: {m.get('msg_type')}, mid: {m.get('message_id')}")
        print()
