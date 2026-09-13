#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""日常维护任务包装脚本：derive全量重算 + 7轮滚动备份 + Phase5自动日检 + 系统状态更新"""

import os
import sys
import subprocess
import json
from datetime import datetime

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_maintenance_debug.log")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {msg}\n")

# 清空日志
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

log("=== 维护任务开始 ===")

# 设置PATH包含hermes lark-cli路径
hermes_path = r"C:\Users\Administrator\AppData\Local\hermes\node"
os.environ["PATH"] = hermes_path + ";" + os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"
log(f"PATH已设置: {os.environ['PATH'][:200]}...")

# 设置工作目录
work_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(work_dir)
log(f"工作目录: {os.getcwd()}")

exit_code = 0

# 1. derive全量重算
log("[维护] 执行derive全量重算...")
try:
    result = subprocess.run(
        [sys.executable, "review_derive.py", "--all"],
        capture_output=True,
        timeout=300,
        cwd=work_dir
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    log(f"derive退出码: {result.returncode}")
    log(f"derive stdout（最后500字符）: {stdout[-500:]}")
    if stderr:
        log(f"derive stderr: {stderr[-500:]}")
    if result.returncode != 0:
        log(f"[维护] derive重算失败，退出码: {result.returncode}")
        exit_code = result.returncode
    else:
        log("[维护] derive重算完成")
except Exception as e:
    log(f"[维护] derive重算异常: {e}")
    exit_code = 1

# 2. 7轮滚动备份
log("[维护] 执行7轮滚动备份...")
try:
    result = subprocess.run(
        [sys.executable, "backup_with_rotation.py"],
        capture_output=True,
        timeout=120,
        cwd=work_dir
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    log(f"备份退出码: {result.returncode}")
    log(f"备份 stdout（最后500字符）: {stdout[-500:]}")
    if stderr:
        log(f"备份 stderr: {stderr[-500:]}")
    if result.returncode != 0:
        log(f"[维护] 备份失败，退出码: {result.returncode}")
        exit_code = result.returncode
    else:
        log("[维护] 备份完成")
except Exception as e:
    log(f"[维护] 备份异常: {e}")
    exit_code = 1

# 3. Phase5自动日检
log("[维护] 执行Phase5自动日检...")
try:
    result = subprocess.run(
        [sys.executable, "phase5_daily_check.py"],
        capture_output=True,
        timeout=180,
        cwd=work_dir
    )
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""
    log(f"Phase5日检退出码: {result.returncode}")
    log(f"Phase5日检 stdout（最后500字符）: {stdout[-500:]}")
    if stderr:
        log(f"Phase5日检 stderr: {stderr[-500:]}")
    if result.returncode != 0:
        log(f"[维护] Phase5日检发现问题，退出码: {result.returncode}")
        # 不设置exit_code，因为Phase5日检发现问题不应该导致维护任务失败
    else:
        log("[维护] Phase5日检完成")
except Exception as e:
    log(f"[维护] Phase5日检异常: {e}")

# 3.5 消费索引健康检查（V21集成）
log("[维护] 执行消费索引健康检查...")
try:
    sys.path.insert(0, work_dir)
    from v19_integration import ConsumeIndexHealthChecker, AlertManager
    checker = ConsumeIndexHealthChecker(max_age_seconds=3600)  # 60分钟阈值
    check_result = checker.check()
    log(f"消费索引检查结果: healthy={check_result.get('healthy')}, reason={check_result.get('reason')}, index_age={check_result.get('index_age')}, pending={check_result.get('pending_messages')}")
    
    if not check_result.get('healthy') and check_result.get('pending_messages', 0) > 0:
        # 仅在索引过期且有未消费消息时才告警（消除永久误报）
        alert = AlertManager()
        alert_result = alert.send_alert(
            level='WARN',
            title='消费索引健康检查异常',
            message=f"索引过期: {check_result.get('reason')}, 年龄: {check_result.get('index_age')}s, 未消费消息: {check_result.get('pending_messages')}",
            channel='both'
        )
        log(f"消费索引告警已发送: feishu={alert_result.get('feishu')}, local={alert_result.get('local')}")
    else:
        log("[维护] 消费索引健康检查通过")
except Exception as e:
    log(f"[维护] 消费索引健康检查异常: {e}")

# 4. 更新系统状态文件
log("[维护] 更新系统状态文件...")
try:
    state_file = os.path.join(work_dir, ".system_state.json")
    state = {}
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
    state["last_success_time"] = datetime.now().isoformat()
    state["last_check"] = datetime.now().isoformat()
    state["last_maintenance"] = datetime.now().isoformat()
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    log("[维护] 系统状态文件已更新")
except Exception as e:
    log(f"[维护] 更新系统状态异常: {e}")

log(f"[维护] 日常维护任务结束，退出码: {exit_code}")
sys.exit(exit_code)
