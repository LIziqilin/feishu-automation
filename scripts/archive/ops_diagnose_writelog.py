#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""诊断write_system_log失败根因：测试+record-upsert完整返回+batch-create"""
import json
import subprocess
import os

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
TABLE = "tblPreh1ipB9LQpf"

print("=" * 70)
print("【1】+record-upsert完整返回（不解析，看原始JSON）")
print("=" * 70)
data = {
    "log_type": ["SYSTEM"],
    "message": "V39-diagnose-upsert-test",
    "severity": ["INFO"],
    "source": ["diagnose"],
    "detail": "诊断测试",
    "timestamp": "2026-09-14 11:40:00",
    "resolved": False,
}
fname = "tmp_diagnose.json"
with open(fname, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False)

# 不用shell=True
r = subprocess.run(
    [LARK, "base", "+record-upsert", "--base-token", BASE,
     "--table-id", TABLE, "--as", "user", "--json", "@" + fname],
    capture_output=True, timeout=30
)
print("returncode:", r.returncode)
print("stdout:", r.stdout.decode("utf-8", errors="replace")[:500])
print("stderr:", r.stderr.decode("utf-8", errors="replace")[:200])

# 用shell=True（模拟learning_system.py的run_cmd）
print()
print("【2】shell=True方式（模拟learning_system.py的run_cmd）")
r2 = subprocess.run(
    [LARK, "base", "+record-upsert", "--base-token", BASE,
     "--table-id", TABLE, "--as", "user", "--json", "@" + fname],
    capture_output=True, timeout=30, shell=True
)
print("returncode:", r2.returncode)
print("stdout:", r2.stdout.decode("utf-8", errors="replace")[:500])
print("stderr:", r2.stderr.decode("utf-8", errors="replace")[:200])

print()
print("=" * 70)
print("【3】+record-batch-create测试（替代upsert）")
print("=" * 70)
batch_data = {
    "records": [
        {
            "fields": {
                "log_type": ["SYSTEM"],
                "message": "V39-diagnose-batch-create-test",
                "severity": ["INFO"],
                "source": ["diagnose"],
                "detail": "batch-create测试",
                "timestamp": "2026-09-14 11:40:00",
                "resolved": False,
            }
        }
    ]
}
fname2 = "tmp_diagnose_batch.json"
with open(fname2, "w", encoding="utf-8") as f:
    json.dump(batch_data, f, ensure_ascii=False)

r3 = subprocess.run(
    [LARK, "base", "+record-batch-create", "--base-token", BASE,
     "--table-id", TABLE, "--as", "user", "--json", "@" + fname2],
    capture_output=True, timeout=30
)
print("returncode:", r3.returncode)
print("stdout:", r3.stdout.decode("utf-8", errors="replace")[:500])
print("stderr:", r3.stderr.decode("utf-8", errors="replace")[:200])

print()
print("=" * 70)
print("【4】查询最近5条记录，确认哪些测试写入了")
print("=" * 70)
r4 = subprocess.run(
    [LARK, "base", "+record-list", "--base-token", BASE,
     "--table-id", TABLE, "--as", "user", "--limit", "5", "--format", "json"],
    capture_output=True, timeout=30
)
try:
    d = json.loads(r4.stdout.decode("utf-8", errors="replace"))
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    for i, row in enumerate(rows[:5]):
        rec = dict(zip(fields, row))
        print("  " + str(i+1) + ". msg=" + str(rec.get("message", ""))[:60] + ", source=" + str(rec.get("source", "")))
except Exception as e:
    print("解析失败: " + str(e))

# 清理
for f in [fname, fname2]:
    try:
        os.remove(f)
    except:
        pass

print()
print("诊断完成")
