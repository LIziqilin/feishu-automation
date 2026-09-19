#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最终验证：所有任务计划状态+心跳任务触发+系统健康表+总结"""
import subprocess
import json
import os
import sys
import time
import datetime

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)
python = sys.executable

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"

def run_cmd(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")

print("=" * 70)
print("【最终验证报告】系统稳定性修复验证")
print(f"验证时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# 1. 所有任务计划状态
print("\n【1】所有任务计划状态")
print("-" * 70)
tasks = [
    "V16_MorningReport", "V16_NoonReport", "V16_EveningReport",
    "V16_LearningPoll", "V16_DailyMaintenance",
    "FeishuAssistant-Heartbeat-Morning", "FeishuAssistant-Heartbeat-Noon",
    "FeishuAssistant-Heartbeat-Night"
]
for task in tasks:
    code, stdout, stderr = run_cmd(["schtasks", "/query", "/tn", f"\\{task}", "/fo", "LIST", "/v"])
    status = "未知"
    last_run = "未知"
    last_result = "未知"
    next_run = "未知"
    for line in stdout.split("\n"):
        if "Status:" in line:
            status = line.split(":", 1)[1].strip()
        elif "Last Run Time:" in line:
            last_run = line.split(":", 1)[1].strip()
        elif "Last Result:" in line:
            last_result = line.split(":", 1)[1].strip()
        elif "Next Run Time:" in line:
            next_run = line.split(":", 1)[1].strip()

    result_icon = "✓" if last_result in ("0", "267009") else "⚠"
    print(f"  {result_icon} {task}")
    print(f"    状态={status}, 上次运行={last_run}, 结果={last_result}, 下次={next_run}")

# 2. 手动触发心跳任务并验证
print("\n【2】手动触发心跳任务验证")
print("-" * 70)
code, stdout, stderr = run_cmd(["schtasks", "/run", "/tn", "\\FeishuAssistant-Heartbeat-Morning"])
print(f"  触发结果: {stdout.strip()[:100]}")
time.sleep(8)  # 等待任务完成

code, stdout, stderr = run_cmd(["schtasks", "/query", "/tn", "\\FeishuAssistant-Heartbeat-Morning", "/fo", "LIST", "/v"])
for line in stdout.split("\n"):
    if "Last Run Time:" in line or "Last Result:" in line:
        print(f"  {line.strip()}")

# 3. 心跳表最新记录
print("\n【3】心跳表最新5条记录")
print("-" * 70)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblJmm0ZIgqlYmyt", "--as", "user",
       "--limit", "50", "--format", "json"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    # 按时间排序
    def get_time(row):
        rec = dict(zip(fields, row))
        return str(rec.get("心跳时间", ""))
    rows_sorted = sorted(rows, key=get_time, reverse=True)
    for i, row in enumerate(rows_sorted[:5]):
        rec = dict(zip(fields, row))
        print(f"  {i+1}. 时间={rec.get('心跳时间')}, 来源={rec.get('来源')}, 状态={rec.get('状态')}")
except Exception as e:
    print(f"  解析失败: {e}")

# 4. 系统健康表最新记录
print("\n【4】系统健康表最新3条记录")
print("-" * 70)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblxJMndPNtZ7XyG", "--as", "user",
       "--limit", "10", "--format", "json"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    def get_check_time(row):
        rec = dict(zip(fields, row))
        return str(rec.get("最近检查时间", ""))
    rows_sorted = sorted(rows, key=get_check_time, reverse=True)
    for i, row in enumerate(rows_sorted[:3]):
        rec = dict(zip(fields, row))
        print(f"  {i+1}. 检查项={rec.get('检查项')}, 时间={rec.get('最近检查时间')}, 状态={rec.get('处理状态')}")
except Exception as e:
    print(f"  解析失败: {e}")

# 5. DLQ状态
print("\n【5】DLQ队列状态")
print("-" * 70)
dlq_file = os.path.join(scripts_dir, ".dlq_queue.json")
if os.path.exists(dlq_file):
    with open(dlq_file, "r", encoding="utf-8") as f:
        dlq = json.load(f)
    print(f"  消息数: {len(dlq.get('messages', []))}")
    print(f"  统计: {dlq.get('stats')}")
else:
    print("  DLQ文件不存在")

# 6. 系统状态
print("\n【6】系统状态文件")
print("-" * 70)
state_file = os.path.join(scripts_dir, ".system_state.json")
if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    print(f"  状态: {state.get('status')}")
    print(f"  最后成功: {state.get('last_success_time')}")
    print(f"  最后维护: {state.get('last_maintenance')}")
    print(f"  维护版本: {state.get('maintenance_version', 'N/A')}")

print("\n" + "=" * 70)
print("验证完成")
print("=" * 70)
