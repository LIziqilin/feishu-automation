#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""任务计划包装脚本：设置环境变量并运行learning_system.py --poll"""

import os
import sys
import subprocess
from datetime import datetime

# 日志文件
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_python_debug.log")

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} - {msg}\n")

# 清空日志
with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write("")

log("=== 任务计划开始 ===")

# 设置PATH包含hermes lark-cli路径
hermes_path = r"C:\Users\Administrator\AppData\Local\hermes\node"
os.environ["PATH"] = hermes_path + ";" + os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"
log(f"PATH已设置: {os.environ['PATH'][:200]}...")

# 设置工作目录
work_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(work_dir)
log(f"工作目录: {os.getcwd()}")

# 测试lark-cli是否可用
try:
    result = subprocess.run(["lark-cli", "--version"], capture_output=True, text=True, timeout=10, shell=True)
    log(f"lark-cli版本: {result.stdout.strip()} (退出码: {result.returncode})")
except Exception as e:
    log(f"lark-cli测试失败: {e}")

# 运行learning_system.py --poll
log("开始运行learning_system.py --poll")
try:
    result = subprocess.run(
        [sys.executable, "learning_system.py", "--poll"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=work_dir
    )
    log(f"Python退出码: {result.returncode}")
    log(f"Python stdout:\n{result.stdout}")
    if result.stderr:
        log(f"Python stderr:\n{result.stderr}")
    log("=== 任务计划结束 ===")
    sys.exit(result.returncode)
except Exception as e:
    log(f"运行异常: {e}")
    log("=== 任务计划异常结束 ===")
    sys.exit(1)
