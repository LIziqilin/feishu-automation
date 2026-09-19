#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""V39 全系统深度诊断：任务/脚本/数据/日志/备份 全面扫描"""
import subprocess
import json
import os
import sys
import datetime
import glob

scripts_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(scripts_dir)
python = sys.executable

LARK = r"C:\Users\Administrator\AppData\Local\hermes\node\lark-cli.cmd"
BASE = "X8N1bvN3na99dFsyu0gcU8zTnHf"

def run_cmd(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", errors="replace"), r.stderr.decode("utf-8", errors="replace")
    except Exception as e:
        return -1, "", str(e)

def lark_base(cmd_args, timeout=60):
    cmd = [LARK, "base"] + cmd_args + ["--base-token", BASE, "--as", "user", "--format", "json"]
    return run_cmd(cmd, timeout=timeout)

print("=" * 70)
print(f"V39 全系统深度诊断  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 70)

# ========== 1. 任务计划状态 ==========
print("\n【1】任务计划状态（8个）")
print("-" * 70)
tasks = [
    "V16_MorningReport", "V16_NoonReport", "V16_EveningReport",
    "V16_LearningPoll", "V16_DailyMaintenance",
    "FeishuAssistant-Heartbeat-Morning", "FeishuAssistant-Heartbeat-Noon",
    "FeishuAssistant-Heartbeat-Night"
]
task_issues = []
for task in tasks:
    code, stdout, stderr = run_cmd(["schtasks", "/query", "/tn", f"\\{task}", "/fo", "LIST", "/v"])
    info = {}
    for line in stdout.split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            info[key.strip()] = val.strip()
    status = info.get("Status", "?")
    last_result = info.get("Last Result", "?")
    last_run = info.get("Last Run Time", "?")
    next_run = info.get("Next Run Time", "?")

    # 检查StartWhenAvailable
    code2, xml_out, _ = run_cmd(["schtasks", "/query", "/tn", f"\\{task}", "/xml"])
    has_start_when = "StartWhenAvailable>true" in xml_out

    # 检查路径乱码
    has_garbled = "鏂规" in xml_out or "澧炲己" in xml_out or "å¢žå¼º" in xml_out

    issue = ""
    if last_result not in ("0", "267009", "267011"):
        issue = f"⚠ LastResult={last_result}"
        task_issues.append(f"{task}: LastResult={last_result}")
    if not has_start_when:
        issue += " ⚠无StartWhenAvailable"
        task_issues.append(f"{task}: 无StartWhenAvailable")
    if has_garbled:
        issue += " ⚠路径乱码"
        task_issues.append(f"{task}: 路径乱码")

    icon = "✓" if not issue else "⚠"
    print(f"  {icon} {task}")
    print(f"    状态={status}, 上次={last_run}, 结果={last_result}, 下次={next_run}")
    print(f"    StartWhenAvailable={'✓' if has_start_when else '✗'}, 路径乱码={'✗' if has_garbled else '✓'}")
    if issue:
        print(f"    问题: {issue}")

# ========== 2. 脚本语法检查 ==========
print("\n【2】生产脚本语法检查")
print("-" * 70)
py_files = glob.glob(os.path.join(scripts_dir, "*.py"))
# 排除诊断/临时脚本
exclude = ["ops_", "diagnose", "test_", "tmp_", "cleanup_test"]
prod_scripts = [f for f in py_files if not any(ex in os.path.basename(f) for ex in exclude)]
syntax_errors = []
for f in sorted(prod_scripts):
    fname = os.path.basename(f)
    code, stdout, stderr = run_cmd([python, "-m", "py_compile", f])
    if code == 0:
        print(f"  ✓ {fname}")
    else:
        print(f"  ✗ {fname}: {stderr.strip()[:100]}")
        syntax_errors.append(fname)

# ========== 3. 关键脚本存在性检查 ==========
print("\n【3】关键脚本存在性检查")
print("-" * 70)
critical_scripts = [
    "learning_system.py", "run_morning_wrapper.py", "run_noon_wrapper.py",
    "run_evening_wrapper.py", "run_poll_wrapper.py", "run_maintenance_wrapper.py",
    "heartbeat.py", "backup_with_rotation.py", "dlq_consumer.py",
    "v19_integration.py", "config_local.py"
]
missing_scripts = []
for s in critical_scripts:
    path = os.path.join(scripts_dir, s)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"  ✓ {s} ({size} bytes)")
    else:
        print(f"  ✗ {s} 不存在!")
        missing_scripts.append(s)

# ========== 4. 系统事件日志表字段+log_type白名单 ==========
print("\n【4】系统事件日志表字段结构")
print("-" * 70)
code, stdout, stderr = lark_base(["+field-list", "--table-id", "tblPreh1ipB9LQpf"])
try:
    d = json.loads(stdout)
    fields = d.get("data", {}).get("fields", [])
    log_type_options = []
    severity_options = []
    source_options = []
    for f in fields:
        fname = f.get("field_name", "?")
        ftype = f.get("type", "?")
        opts = f.get("property", {}).get("options", [])
        opt_names = [o.get("name", "") for o in opts] if opts else []
        print(f"  {fname} (type={ftype}) {'选项=' + str(opt_names) if opt_names else ''}")
        if "log_type" in fname.lower() or "类型" in fname:
            log_type_options = opt_names
        if "severity" in fname.lower() or "级别" in fname:
            severity_options = opt_names
        if "source" in fname.lower() or "来源" in fname:
            source_options = opt_names
except Exception as e:
    print(f"  解析失败: {e}")
    print(f"  stdout: {stdout[:300]}")

# 检查learning_system.py中使用的log_type值
print("\n  learning_system.py中使用的log_type值:")
log_types_used = set()
try:
    with open(os.path.join(scripts_dir, "learning_system.py"), "r", encoding="utf-8") as f:
        content = f.read()
    import re
    matches = re.findall(r'write_system_log\(\s*["\']([^"\']+)["\']', content)
    log_types_used = set(matches)
    for lt in sorted(log_types_used):
        in_whitelist = lt in log_type_options if log_type_options else "未知"
        print(f"    {lt} {'✓在白名单' if in_whitelist == True else '⚠不在白名单!' if in_whitelist == False else ''}")
except Exception as e:
    print(f"  检查失败: {e}")

# ========== 5. 系统健康表 ==========
print("\n【5】系统健康表最近记录")
print("-" * 70)
code, stdout, stderr = lark_base(["+record-list", "--table-id", "tblxJMndPNtZ7XyG", "--limit", "10"])
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    def get_check_time(row):
        rec = dict(zip(fields, row))
        return str(rec.get("最近检查时间", ""))
    rows_sorted = sorted(rows, key=get_check_time, reverse=True)
    for i, row in enumerate(rows_sorted[:5]):
        rec = dict(zip(fields, row))
        print(f"  {i+1}. {rec.get('检查项')}: 时间={rec.get('最近检查时间')}, 状态={rec.get('处理状态')}")
except Exception as e:
    print(f"  解析失败: {e}")

# ========== 6. 心跳表 ==========
print("\n【6】心跳表最近记录")
print("-" * 70)
code, stdout, stderr = lark_base(["+record-list", "--table-id", "tblJmm0ZIgqlYmyt", "--limit", "50"])
try:
    d = json.loads(stdout)
    fields = d["data"]["fields"]
    rows = d["data"]["data"]
    def get_hb_time(row):
        rec = dict(zip(fields, row))
        return str(rec.get("心跳时间", ""))
    rows_sorted = sorted(rows, key=get_hb_time, reverse=True)
    for i, row in enumerate(rows_sorted[:5]):
        rec = dict(zip(fields, row))
        print(f"  {i+1}. 时间={rec.get('心跳时间')}, 来源={rec.get('来源')}, 状态={rec.get('状态')}")
except Exception as e:
    print(f"  解析失败: {e}")

# ========== 7. DLQ状态 ==========
print("\n【7】DLQ队列状态")
print("-" * 70)
dlq_file = os.path.join(scripts_dir, ".dlq_queue.json")
if os.path.exists(dlq_file):
    with open(dlq_file, "r", encoding="utf-8") as f:
        dlq = json.load(f)
    msgs = dlq.get("messages", [])
    print(f"  消息数: {len(msgs)}")
    print(f"  统计: {dlq.get('stats')}")
    for m in msgs:
        print(f"    - {m.get('message_id')}: status={m.get('status')}, error={m.get('error_type')}")
else:
    print("  DLQ文件不存在")

# ========== 8. 系统状态 ==========
print("\n【8】系统状态文件")
print("-" * 70)
state_file = os.path.join(scripts_dir, ".system_state.json")
if os.path.exists(state_file):
    with open(state_file, "r", encoding="utf-8") as f:
        state = json.load(f)
    for k, v in state.items():
        print(f"  {k}: {v}")
else:
    print("  系统状态文件不存在")

# ========== 9. 备份文件 ==========
print("\n【9】备份文件")
print("-" * 70)
backup_dir = os.path.join(scripts_dir, "backups")
if os.path.exists(backup_dir):
    backups = sorted(glob.glob(os.path.join(backup_dir, "*.json")), key=os.path.getmtime, reverse=True)
    print(f"  备份目录: {backup_dir}")
    print(f"  备份文件数: {len(backups)}")
    for b in backups[:5]:
        size = os.path.getsize(b)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(b)).strftime("%Y-%m-%d %H:%M")
        print(f"    {os.path.basename(b)} ({size/1024:.0f}KB, {mtime})")
else:
    print(f"  备份目录不存在: {backup_dir}")
    # 查找其他备份位置
    for pattern in [os.path.join(scripts_dir, "backup*.json"), os.path.join(scripts_dir, "..", "backup*.zip")]:
        found = glob.glob(pattern)
        if found:
            print(f"  找到备份: {found[:3]}")

# ========== 10. 问题汇总 ==========
print("\n" + "=" * 70)
print("【问题汇总】")
print("=" * 70)
all_issues = []
if task_issues:
    all_issues.extend(task_issues)
    print(f"\n  任务计划问题 ({len(task_issues)}):")
    for i in task_issues:
        print(f"    - {i}")
if syntax_errors:
    all_issues.extend([f"语法错误: {s}" for s in syntax_errors])
    print(f"\n  脚本语法错误 ({len(syntax_errors)}):")
    for s in syntax_errors:
        print(f"    - {s}")
if missing_scripts:
    all_issues.extend([f"脚本缺失: {s}" for s in missing_scripts])
    print(f"\n  关键脚本缺失 ({len(missing_scripts)}):")
    for s in missing_scripts:
        print(f"    - {s}")

# log_type白名单不匹配
if log_type_options and log_types_used:
    mismatched = [lt for lt in log_types_used if lt not in log_type_options]
    if mismatched:
        all_issues.extend([f"log_type不在白名单: {lt}" for lt in mismatched])
        print(f"\n  log_type白名单不匹配 ({len(mismatched)}):")
        for lt in mismatched:
            print(f"    - {lt} (白名单: {log_type_options})")

if not all_issues:
    print("\n  ✓ 未发现问题")
else:
    print(f"\n  总计: {len(all_issues)} 个问题待处理")

print("\n诊断完成")
