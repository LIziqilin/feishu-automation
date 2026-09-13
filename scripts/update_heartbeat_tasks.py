#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""更新3个心跳任务计划：删除旧任务，创建新任务指向新路径"""
import subprocess
import sys

PYTHON = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
SCRIPT = r"D:\AI-Tools\feishu\V13方案增强\scripts\heartbeat.py"

tasks = [
    ("FeishuAssistant-Heartbeat-Morning", "08:00"),
    ("FeishuAssistant-Heartbeat-Noon", "14:00"),
    ("FeishuAssistant-Heartbeat-Night", "22:00"),
]

def run_cmd(cmd, timeout=30):
    """执行命令，返回(ok, stdout, stderr)"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, shell=True)
        stdout = r.stdout.decode("utf-8", errors="replace") if r.stdout else ""
        stderr = r.stderr.decode("utf-8", errors="replace") if r.stderr else ""
        return r.returncode == 0, stdout, stderr
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as e:
        return False, "", str(e)

print("=" * 60)
print("Update heartbeat scheduled tasks")
print("=" * 60)

for task_name, run_time in tasks:
    print(f"\n[{task_name}] ({run_time})")

    # 1. Delete old task
    del_cmd = f'schtasks /delete /tn "{task_name}" /f'
    ok_del, out_del, err_del = run_cmd(del_cmd, timeout=15)
    print(f"  Delete: {'OK' if ok_del else 'FAIL - ' + err_del[:80]}")

    # 2. Create new task
    # tr value needs escaped quotes for cmd
    tr_value = f'\\"{PYTHON}\\" \\"{SCRIPT}\\"'
    create_cmd = (f'schtasks /create /tn "{task_name}" /tr "{tr_value}" '
                  f'/sc daily /st {run_time} /ru Administrator /rl highest /f')
    ok_create, out_create, err_create = run_cmd(create_cmd, timeout=30)
    if ok_create:
        print(f"  Create: OK")
    else:
        print(f"  Create: FAIL - {err_create[:120]}")
        # Try without /rl highest
        create_cmd2 = (f'schtasks /create /tn "{task_name}" /tr "{tr_value}" '
                       f'/sc daily /st {run_time} /ru Administrator /f')
        ok_create2, out_create2, err_create2 = run_cmd(create_cmd2, timeout=30)
        print(f"  Create (retry): {'OK' if ok_create2 else 'FAIL - ' + err_create2[:120]}")

# Verify
print("\n" + "=" * 60)
print("Verify task status")
print("=" * 60)

for task_name, run_time in tasks:
    query_cmd = f'schtasks /query /tn "{task_name}" /v /fo LIST'
    ok, out, err = run_cmd(query_cmd, timeout=15)
    if ok:
        status = "Unknown"
        next_run = "Unknown"
        last_run = "Unknown"
        last_result = "Unknown"
        task_to_run = "Unknown"
        for line in out.split("\n"):
            line = line.strip()
            if line.startswith("Status:"):
                status = line.split(":", 1)[1].strip()
            elif line.startswith("Next Run Time:"):
                next_run = line.split(":", 1)[1].strip()
            elif line.startswith("Last Run Time:"):
                last_run = line.split(":", 1)[1].strip()
            elif line.startswith("Last Result:"):
                last_result = line.split(":", 1)[1].strip()
            elif line.startswith("Task To Run:"):
                task_to_run = line.split(":", 1)[1].strip()

        print(f"\n{task_name} ({run_time}):")
        print(f"  Status: {status}")
        print(f"  Next Run: {next_run}")
        print(f"  Last Run: {last_run} (result: {last_result})")
        print(f"  Task To Run: {task_to_run[:120]}")
    else:
        print(f"\n{task_name}: Query FAIL - {err[:80]}")

print("\n" + "=" * 60)
print("Done")
print("=" * 60)
