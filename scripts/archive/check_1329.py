#!/usr/bin/env python
# -*- coding: utf-8 -*-
import subprocess, json, datetime

all_msgs = []
page_token = None
for page in range(8):
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

def parse_ts(ct):
    try:
        v = int(ct)
        # 毫秒
        if v > 1000000000000:
            return datetime.datetime.fromtimestamp(v/1000)
        return datetime.datetime.fromtimestamp(v)
    except:
        return None

# 找到第三个测试回执的位置
target_idx = None
for i, m in enumerate(all_msgs):
    c = m.get('content','')
    try: c = json.loads(c).get('text',c)
    except: pass
    if '第三个测试' in c:
        target_idx = i
        print(f"找到'第三个测试'，索引{i}，create_time原始值={m.get('create_time')}, 解析={parse_ts(m.get('create_time'))}")

print()
if target_idx is not None:
    print("=== 该消息前后10条（desc顺序）===")
    for i in range(max(0,target_idx-10), min(len(all_msgs), target_idx+10)):
        m = all_msgs[i]
        c = m.get('content','')
        try: c = json.loads(c).get('text',c)
        except: pass
        ts = parse_ts(m.get('create_time'))
        st = m.get('sender',{}).get('sender_type','?')
        mark = " <<<" if i == target_idx else ""
        print(f"[{ts}][{st}] {c[:70]}{mark}")
