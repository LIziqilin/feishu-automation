#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深度排查：任务计划XML + processed_messages + DailyMaintenance错误 + DLQ"""
import subprocess, json, os, sys

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)

print("=" * 60)
print("【1】V16_MorningReport任务计划XML（查触发器）")
print("=" * 60)
# 导出任务计划XML
r = subprocess.run(["schtasks", "/query", "/tn", "\\V16_MorningReport", "/xml"],
                   capture_output=True, timeout=30)
xml_content = r.stdout.decode("utf-8", errors="replace")
# 提取关键部分
for line in xml_content.split("\n"):
    if any(k in line for k in ["StartBoundary", "Enabled", "Exec", "Command", "Arguments", "WorkingDirectory", "DaysInterval", "WeeksInterval"]):
        print(f"  {line.strip()}")

print()
print("=" * 60)
print("【2】processed_messages.json（检查重复处理）")
print("=" * 60)
pm_file = os.path.join(scripts_dir, ".processed_messages.json")
if os.path.exists(pm_file):
    with open(pm_file, "r", encoding="utf-8") as f:
        pm = json.load(f)
    if isinstance(pm, dict):
        print(f"  总记录数: {len(pm)}")
        # 查最近10条
        items = sorted(pm.items(), key=lambda x: x[1].get("processed_at", "") if isinstance(x[1], dict) else "", reverse=True)[:10]
        for i, (mid, info) in enumerate(items):
            if isinstance(info, dict):
                print(f"  {i+1}. {mid[:20]}... at={info.get('processed_at','?')}, type={info.get('type','?')}, content={str(info.get('content',''))[:50]}")
            else:
                print(f"  {i+1}. {mid[:20]}... = {str(info)[:80]}")
        # 检查是否有重复的message_id
        print(f"  唯一message_id数: {len(set(pm.keys()))}")
    elif isinstance(pm, list):
        print(f"  总记录数: {len(pm)}")
        for i, item in enumerate(pm[-10:]):
            print(f"  {i+1}. {str(item)[:100]}")
else:
    print("  文件不存在!")

print()
print("=" * 60)
print("【3】手动运行run_maintenance_wrapper.py（查错误）")
print("=" * 60)
python = sys.executable
r = subprocess.run([python, "run_maintenance_wrapper.py"],
                   capture_output=True, timeout=180, cwd=scripts_dir)
print(f"  退出码: {r.returncode}")
stdout = r.stdout.decode("utf-8", errors="replace")
stderr = r.stderr.decode("utf-8", errors="replace")
if stdout:
    print(f"  stdout（最后30行）:")
    for line in stdout.split("\n")[-30:]:
        if line.strip():
            print(f"    {line[:120]}")
if stderr:
    print(f"  stderr（最后20行）:")
    for line in stderr.split("\n")[-20:]:
        if line.strip():
            print(f"    {line[:120]}")

print()
print("=" * 60)
print("【4】DLQ队列状态")
print("=" * 60)
dlq_file = os.path.join(scripts_dir, ".dlq_queue.json")
if os.path.exists(dlq_file):
    with open(dlq_file, "r", encoding="utf-8") as f:
        dlq = json.load(f)
    print(f"  DLQ内容: {json.dumps(dlq, ensure_ascii=False, indent=2)[:1000]}")
else:
    print("  DLQ文件不存在")

print()
print("=" * 60)
print("【5】系统状态文件")
print("=" * 60)
state_file = os.path.join(scripts_dir, ".system_state.json")
if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    print(f"  系统状态: {json.dumps(state, ensure_ascii=False, indent=2)[:800]}")
else:
    print("  系统状态文件不存在")
