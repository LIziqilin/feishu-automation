#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""最终验证：飞书群最近消息+系统日志validation错误排查+所有任务状态"""
import subprocess
import json
import os
import sys
import datetime

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"
CHAT = "oc_1fe154e172ab04622b7ffa810ac172bc"

def run_cmd(cmd, timeout=30):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")

print("=" * 70)
print("【1】飞书群最近10条消息（确认LearningPoll正常发回执）")
print("=" * 70)
cmd = [LARK, "im", "+chat-messages-list", "--chat-id", CHAT,
       "--limit", "10", "--order", "desc"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
try:
    d = json.loads(stdout)
    for i, msg in enumerate(d["data"]["messages"][:10]):
        sender = msg.get("sender", {}).get("name", "?")
        content = msg.get("content", "")[:80]
        create_time = msg.get("create_time", "")
        print(f"  {i+1}. [{create_time}] {sender}: {content}")
except Exception as e:
    print(f"  解析失败: {e}")

print()
print("=" * 70)
print("【2】系统事件日志表字段结构（排查validation错误）")
print("=" * 70)
cmd = [LARK, "base", "+field-list", "--base-token", BASE,
       "--table-id", "tblPreh1ipB9LQpf", "--as", "user", "--format", "json"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
try:
    d = json.loads(stdout)
    fields = d.get("data", {}).get("fields", [])
    for f in fields:
        fname = f.get("field_name", "?")
        ftype = f.get("type", "?")
        options = f.get("property", {}).get("options", [])
        opt_str = ", ".join([o.get("name", "") for o in options]) if options else ""
        print(f"  {fname} (type={ftype}) {opt_str}")
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {stdout[:500]}")

print()
print("=" * 70)
print("【3】系统事件日志表最近5条（看log_type值）")
print("=" * 70)
cmd = [LARK, "base", "+record-list", "--base-token", BASE,
       "--table-id", "tblPreh1ipB9LQpf", "--as", "user",
       "--limit", "5", "--format", "json"]
code, stdout, stderr = run_cmd(cmd, timeout=60)
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    for row in d["data"]["data"][:5]:
        rec = dict(zip(fields, row))
        print(f"  log_type={rec.get('log_type')}, 详情={str(rec.get('详情',''))[:60]}")
except Exception as e:
    print(f"  解析失败: {e}")

print()
print("=" * 70)
print("【4】所有任务计划最终状态")
print("=" * 70)
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
    result_icon = "✓" if last_result in ("0", "267009", "267011") else "⚠"
    print(f"  {result_icon} {task}")
    print(f"    状态={status}, 上次={last_run}, 结果={last_result}, 下次={next_run}")

print()
print("=" * 70)
print("验证完成")
print("=" * 70)
