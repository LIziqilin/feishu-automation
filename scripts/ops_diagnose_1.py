#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""排查：系统事件日志最近10条 + 飞书群07:00-10:00消息"""
import subprocess, json, sys

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
CHAT = "oc_1fe154e172ab04622b7ffa810ac172bc"

print("=" * 60)
print("【1】系统事件日志表最近10条")
print("=" * 60)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblPreh1ipB9LQpf", "--as", "user",
       "--limit", "10", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    for i, row in enumerate(rows):
        rec = dict(zip(fields, row))
        log_type = rec.get("log_type", "N/A")
        time_val = rec.get("时间", rec.get("创建时间", "N/A"))
        detail = str(rec.get("详情", rec.get("事件描述", "")))[:100]
        print(f"  {i+1}. type={log_type}, time={time_val}")
        print(f"     detail={detail}")
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {r.stdout[:500]}")

print()
print("=" * 60)
print("【2】飞书群最近30条消息（找早报）")
print("=" * 60)
cmd = [LARK, "im", "+chat-messages-list", "--chat-id", CHAT,
       "--limit", "30", "--order", "desc"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    messages = d["data"]["messages"]
    for i, msg in enumerate(messages):
        sender = msg.get("sender", {}).get("name", "unknown")
        content = msg.get("content", "")[:80]
        create_time = msg.get("create_time", "")
        msg_type = msg.get("msg_type", "")
        print(f"  {i+1}. [{create_time}] {sender} ({msg_type}): {content}")
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {r.stdout[:500]}")

print()
print("=" * 60)
print("【3】学习卡表状态分布")
print("=" * 60)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblpLvxyYpDJgF92", "--as", "user",
       "--limit", "20", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    status_idx = fields.index("卡片状态") if "卡片状态" in fields else -1
    title_idx = fields.index("卡片问题正面") if "卡片问题正面" in fields else -1
    status_count = {}
    for row in rows:
        if status_idx >= 0:
            s = row[status_idx]
            if isinstance(s, list):
                s = s[0] if s else "空"
            status_count[s] = status_count.get(s, 0) + 1
    print(f"  总卡片数: {len(rows)}")
    print(f"  状态分布: {status_count}")
except Exception as e:
    print(f"  解析失败: {e}")
