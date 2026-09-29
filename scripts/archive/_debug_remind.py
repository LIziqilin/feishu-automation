# -*- coding: utf-8 -*-
"""排查提醒功能"""
import subprocess, json

# 1. 检查任务表最近记录
print("=== 1. 任务表最近5条记录 ===")
r = subprocess.run(
    ["lark-cli", "base", "+record-list", "--base-token", "X8N1bvN3na99dFsyu0gcU8zTnHf",
     "--table-id", "tblz3H4lV7PCrBrX", "--as", "user", "--limit", "5",
     "--sort-json", '[{"field":"创建日期","desc":true}]', "--format", "json"],
    capture_output=True, text=True, encoding="utf-8", timeout=30
)
try:
    d = json.loads(r.stdout)
    fields = d.get("data", {}).get("fields", [])
    rows = d.get("data", {}).get("data", [])
    print("字段:", fields)
    for row in rows[:5]:
        # 找任务名称和类别字段
        print("  记录:", row[:8])
except Exception as e:
    print("解析失败:", e)
    print(r.stdout[:500])

# 2. 检查send_due_reminder在哪里被调用
print("\n=== 2. 检查提醒触发机制 ===")
import os
script_dir = r"D:\AI-Tools\feishu\V13方案增强\scripts"
with open(os.path.join(script_dir, "learning_system.py"), "r", encoding="utf-8") as f:
    ls = f.read()

# 找send_due_reminder调用位置
for i, line in enumerate(ls.split("\n"), 1):
    if "send_due_reminder" in line or "due_reminder" in line.lower():
        print(f"  行{i}: {line.strip()}")
