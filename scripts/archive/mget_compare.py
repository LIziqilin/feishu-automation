#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess, json

ids = "om_x100b65b9354bc0acc4ac848b3d0f694,om_x100b65b9205a88bcc3e20ee540e6e87"
cmd = ["lark-cli", "im", "+messages-mget", "--message-ids", ids, "--format", "json"]
r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
d = json.loads(r.stdout)
msgs = d.get('data',{}).get('messages', d.get('data',{}).get('items',[]))
for m in msgs:
    print("=== 消息 ===")
    print("  message_id:", m.get('message_id'))
    print("  create_time:", m.get('create_time'))
    print("  deleted:", m.get('deleted'))
    # 所有顶层key
    print("  所有字段:", list(m.keys()))
    c = m.get('content','')
    try: c = json.loads(c).get('text', c)
    except: pass
    print("  content:", c[:60])
    s = m.get('sender',{})
    print("  sender:", s.get('name'), '/', s.get('sender_type'), '/', s.get('id','')[:20])
    print()
