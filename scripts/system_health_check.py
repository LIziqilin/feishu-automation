#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
V39 系统健康自检脚本（防复发机制）
检查项：任务计划/心跳/健康表/DLQ/系统状态/脚本/备份
用法：python system_health_check.py [--fix]
--fix: 自动修复可修复的问题（如重建任务计划）
"""
import subprocess
import json
import os
import sys
import re
import datetime
import glob

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(SCRIPTS_DIR)
PYTHON = sys.executable
LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"

TASKS = [
    "V16_MorningReport", "V16_NoonReport", "V16_EveningReport",
    "V16_LearningPoll", "V16_DailyMaintenance",
    "FeishuAssistant-Heartbeat-Morning", "FeishuAssistant-Heartbeat-Noon",
    "FeishuAssistant-Heartbeat-Night",
]

CRITICAL_SCRIPTS = [
    "learning_system.py", "run_morning_wrapper.py", "run_noon_wrapper.py",
    "run_evening_wrapper.py", "run_poll_wrapper.py", "run_maintenance_wrapper.py",
    "heartbeat.py", "backup_with_rotation.py", "dlq_consumer.py",
    "v19_integration.py", "config_local.py",
]

results = []

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    icon = "✓" if passed else "✗"
    print(f"  {icon} [{status}] {name}" + (f" - {detail}" if detail else ""))
    return passed

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        def _dec(b):
            try:
                return b.decode("utf-8")
            except Exception:
                try:
                    return b.decode("gbk", errors="replace")
                except Exception:
                    return b.decode("utf-8", errors="replace")
        return r.returncode, _dec(r.stdout), _dec(r.stderr)
    except Exception as e:
        return -1, "", str(e)

print("=" * 70)
print(f"V39 系统健康自检  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ========== 1. 任务计划检查 ==========
print("\n【1】任务计划检查（8个）")
print("-" * 70)
task_failures = 0
for task in TASKS:
    # V49: 用 PowerShell Get-ScheduledTask 取结果码/命令行(纯ASCII,绕开schtasks中文编码)
    code, out_res, _ = run_cmd(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-ScheduledTask -TaskName '{task}' | Get-ScheduledTaskInfo).LastTaskResult"])
    last_result = out_res.strip().splitlines()[-1].strip() if out_res.strip() else "?"
    code, out_act, _ = run_cmd(
        ["powershell", "-NoProfile", "-Command",
         f"(Get-ScheduledTask -TaskName '{task}').Actions.Execute"])
    task_to_run = out_act.strip()
    result_ok = last_result in ("0", "267009", "267011")
    has_full_path = bool(re.search(r"[DC]:[\\/]", task_to_run))
    code2, xml_out, _ = run_cmd(["schtasks", "/query", "/tn", f"\\{task}", "/xml"])
    has_start_when = "StartWhenAvailable>true" in xml_out
    all_ok = result_ok and has_full_path and has_start_when
    detail = f"结果={last_result}, 完整路径={'Y' if has_full_path else 'N'}, StartWhenAvailable={'Y' if has_start_when else 'N'}"
    if not check(task, all_ok, detail):
        task_failures += 1

# ========== 2. 心跳表检查 ==========
print("\n【2】心跳表最近更新")
print("-" * 70)
code, stdout, stderr = run_cmd(
    [LARK, "base", "+record-list", "--base-token", BASE,
     "--table-id", "tblJmm0ZIgqlYmyt", "--as", "user", "--limit", "50",
     "--sort-json", json.dumps([{"field": "心跳时间", "desc": True}], ensure_ascii=False),
     "--format", "json"],
    timeout=60
)
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    # 找心跳时间字段
    time_idx = None
    for i, f in enumerate(fields):
        if "时间" in f or "time" in f.lower():
            time_idx = i
            break
    if time_idx is not None and rows:
        # 遍历所有记录找最新时间
        latest_dt = None
        latest_time_str = ""
        for row in rows:
            t = str(row[time_idx])
            if t and t != "None" and t != "":
                try:
                    if "T" in t:
                        dt = datetime.datetime.fromisoformat(t.replace("Z", "+00:00").replace("+08:00", ""))
                    elif len(t) >= 19:
                        dt = datetime.datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
                    elif t.isdigit():
                        # 毫秒时间戳
                        dt = datetime.datetime.fromtimestamp(int(t) / 1000)
                    else:
                        continue
                    if latest_dt is None or dt > latest_dt:
                        latest_dt = dt
                        latest_time_str = t
                except:
                    continue
        if latest_dt:
            hours_ago = (datetime.datetime.now() - latest_dt).total_seconds() / 3600
            check("心跳表最近更新", hours_ago < 12, f"最近={latest_time_str}, {hours_ago:.1f}小时前")
        else:
            check("心跳表最近更新", False, "无有效时间记录")
    else:
        check("心跳表最近更新", False, "无记录或字段未找到")
except Exception as e:
    check("心跳表最近更新", False, f"查询失败: {str(e)[:80]}")

# ========== 3. 健康表最近更新 ==========
print("\n【3】健康表最近更新")
print("-" * 70)
code, stdout, stderr = run_cmd(
    [LARK, "base", "+record-list", "--base-token", BASE,
     "--table-id", "tblxJMndPNtZ7XyG", "--as", "user", "--limit", "100",
     "--sort-json", json.dumps([{"field": "最近检查时间", "desc": True}], ensure_ascii=False),
     "--format", "json"],
    timeout=60
)
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    # 找最近检查时间字段
    time_idx = None
    for i, f in enumerate(fields):
        if "最近检查" in f or "时间" in f:
            time_idx = i
            break
    if time_idx is not None and rows:
        # 遍历所有记录找最新时间
        latest_dt = None
        latest_time_str = ""
        for row in rows:
            t = str(row[time_idx])
            if t and t != "None" and t != "":
                try:
                    if "T" in t:
                        dt = datetime.datetime.fromisoformat(t.replace("Z", "+00:00").replace("+08:00", ""))
                    elif len(t) >= 19:
                        dt = datetime.datetime.strptime(t[:19], "%Y-%m-%d %H:%M:%S")
                    elif t.isdigit():
                        dt = datetime.datetime.fromtimestamp(int(t) / 1000)
                    else:
                        continue
                    if latest_dt is None or dt > latest_dt:
                        latest_dt = dt
                        latest_time_str = t
                except:
                    continue
        if latest_dt:
            hours_ago = (datetime.datetime.now() - latest_dt).total_seconds() / 3600
            check("健康表最近更新", hours_ago < 24, f"最近={latest_time_str}, {hours_ago:.1f}小时前")
        else:
            check("健康表最近更新", False, "无有效时间记录")
    else:
        check("健康表最近更新", False, "无记录或字段未找到")
except Exception as e:
    check("健康表最近更新", False, f"查询失败: {str(e)[:80]}")

# ========== 4. DLQ检查 ==========
print("\n【4】DLQ死信队列")
print("-" * 70)
dlq_file = os.path.join(SCRIPTS_DIR, ".dlq_queue.json")
if os.path.exists(dlq_file):
    with open(dlq_file, "r", encoding="utf-8") as f:
        dlq = json.load(f)
    msgs = dlq.get("messages", [])
    dead_count = sum(1 for m in msgs if m.get("status") == "dead")
    check("DLQ无死信消息", dead_count == 0, f"总消息={len(msgs)}, 死信={dead_count}")
else:
    check("DLQ无死信消息", True, "DLQ文件不存在（视为空）")

# ========== 5. 系统状态检查 ==========
print("\n【5】系统状态文件")
print("-" * 70)
state_file = os.path.join(SCRIPTS_DIR, ".system_state.json")
if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    last_success = state.get("last_success_time", "")
    status = state.get("status", "")
    if last_success:
        try:
            dt = datetime.datetime.fromisoformat(last_success.replace("Z", "+00:00").replace("+08:00", ""))
            hours_ago = (datetime.datetime.now() - dt).total_seconds() / 3600
            check("系统状态正常", status == "poll_completed" and hours_ago < 1,
                  f"状态={status}, 最后成功={last_success}, {hours_ago:.1f}小时前")
        except:
            check("系统状态正常", status == "poll_completed", f"状态={status}")
    else:
        check("系统状态正常", False, "无last_success_time")
else:
    check("系统状态正常", False, "系统状态文件不存在")

# ========== 6. 关键脚本检查 ==========
print("\n【6】关键脚本存在性+语法")
print("-" * 70)
script_failures = 0
for script in CRITICAL_SCRIPTS:
    path = os.path.join(SCRIPTS_DIR, script)
    exists = os.path.exists(path)
    syntax_ok = False
    if exists:
        code, _, _ = run_cmd([PYTHON, "-m", "py_compile", path])
        syntax_ok = code == 0
    if check(script, exists and syntax_ok,
              "存在" if exists and syntax_ok else ("不存在" if not exists else "语法错误")):
        pass
    else:
        script_failures += 1

# ========== 7. 备份检查 ==========
print("\n【7】备份文件")
print("-" * 70)
backup_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), "backups")
if os.path.exists(backup_dir):
    backups = glob.glob(os.path.join(backup_dir, "*.json"))
    if backups:
        latest_backup = max(backups, key=os.path.getmtime)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(latest_backup))
        hours_ago = (datetime.datetime.now() - mtime).total_seconds() / 3600
        size = os.path.getsize(latest_backup) / 1024
        check("备份最近24小时内", hours_ago < 24,
              f"最新={os.path.basename(latest_backup)}, {size:.0f}KB, {hours_ago:.1f}小时前, 共{len(backups)}个备份")
    else:
        check("备份最近24小时内", False, "备份目录为空")
else:
    check("备份最近24小时内", False, f"备份目录不存在: {backup_dir}")

# ========== 8. 推送记录检查 ==========
print("\n【8】今日推送记录（幂等保护）")
print("-" * 70)
push_record_file = os.path.join(SCRIPTS_DIR, ".push_records.json")
if os.path.exists(push_record_file):
    try:
        with open(push_record_file, "r", encoding="utf-8") as f:
            push_data = json.load(f)
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_records = push_data.get(today, {})
        now_hour = datetime.datetime.now().hour
        # 检查应该已推送的报告
        expected = []
        if now_hour >= 8:  # 早报07:30后应已推送
            expected.append("morning")
        if now_hour >= 12:  # 午报12:00后应已推送
            expected.append("noon")
        if now_hour >= 21:  # 晚报21:00后应已推送
            expected.append("evening")
        missing = [r for r in expected if r not in today_records]
        check("应推送报告均已推送", len(missing) == 0,
              f"今日已推送: {list(today_records.keys())}, 缺失: {missing if missing else '无'}")
    except Exception as e:
        check("推送记录文件可读", False, f"解析失败: {str(e)[:50]}")
else:
    check("推送记录文件存在", False, "推送记录文件不存在（首次运行可能正常）")

# ========== 汇总 ==========
print("\n" + "=" * 70)
print("【自检汇总】")
print("=" * 70)
total = len(results)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = total - passed
print(f"  总计: {total}项, 通过: {passed}项, 失败: {failed}项")
if failed > 0:
    print("\n  失败项:")
    for name, status, detail in results:
        if status == "FAIL":
            print(f"    ✗ {name}: {detail}")
    print(f"\n  退出码: 1（有{failed}项失败）")
    sys.exit(1)
else:
    print("\n  ✓ 全部通过")
    print("  退出码: 0")
    sys.exit(0)
