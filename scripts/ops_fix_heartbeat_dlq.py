#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证心跳表更新 + 手动运行heartbeat.py"""
import subprocess, json, os, sys

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)
python = sys.executable

print("=" * 60)
print("【1】手动运行heartbeat.py")
print("=" * 60)
r = subprocess.run([python, "heartbeat.py"], capture_output=True, timeout=60, cwd=scripts_dir)
print(f"  退出码: {r.returncode}")
stdout = r.stdout.decode("utf-8", errors="replace")
stderr = r.stderr.decode("utf-8", errors="replace")
if stdout:
    print(f"  stdout: {stdout[:500]}")
if stderr:
    print(f"  stderr: {stderr[:500]}")

print()
print("=" * 60)
print("【2】心跳表最近5条")
print("=" * 60)
LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblJmm0ZIgqlYmyt", "--as", "user",
       "--limit", "5", "--format", "json"]
r = subprocess.run(cmd, capture_output=True, timeout=60)
try:
    d = json.loads(r.stdout)
    fields = d["data"]["fields"]
    for row in d["data"]["data"]:
        rec = dict(zip(fields, row))
        print(f"  时间={rec.get('心跳时间')}, 来源={rec.get('来源')}, 状态={rec.get('状态')}, 备注={rec.get('备注')}")
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {r.stdout[:300]}")

print()
print("=" * 60)
print("【3】DLQ清理（移除测试dead消息）")
print("=" * 60)
dlq_file = os.path.join(scripts_dir, ".dlq_queue.json")
if os.path.exists(dlq_file):
    with open(dlq_file, "r", encoding="utf-8") as f:
        dlq = json.load(f)
    original_count = len(dlq.get("messages", []))
    # 移除测试消息（message_id以test_开头或status=dead且error_type=circuit_open）
    dlq["messages"] = [
        m for m in dlq.get("messages", [])
        if not (m.get("message_id", "").startswith("test_") or
                (m.get("status") == "dead" and m.get("error_type") == "circuit_open"))
    ]
    removed = original_count - len(dlq["messages"])
    dlq["stats"]["total"] = len(dlq["messages"])
    dlq["stats"]["dead"] = len([m for m in dlq["messages"] if m.get("status") == "dead"])
    dlq["stats"]["pending"] = len([m for m in dlq["messages"] if m.get("status") == "pending"])
    with open(dlq_file, "w", encoding="utf-8") as f:
        json.dump(dlq, f, ensure_ascii=False, indent=2)
    print(f"  原始消息数: {original_count}")
    print(f"  移除测试消息: {removed}")
    print(f"  剩余消息数: {len(dlq['messages'])}")
    print(f"  DLQ状态: {dlq['stats']}")
else:
    print("  DLQ文件不存在")
