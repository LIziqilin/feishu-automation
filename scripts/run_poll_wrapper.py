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
    result = subprocess.run(["lark-cli", "--version"], capture_output=True, timeout=10)
    log(f"lark-cli版本: {(result.stdout or b'').decode('utf-8','replace').strip()} (退出码: {result.returncode})")
except Exception as e:
    log(f"lark-cli测试失败: {e}")

# 运行learning_system.py --poll
log("开始运行learning_system.py --poll")
try:
    # 修复：Windows 控制台默认 GBK，子进程输出为 UTF-8，
    # 原 text=True 用 GBK 解码 → UnicodeDecodeError（实测 0xae 报错）。
    # 改为显式 bytes + utf-8 容错解码，并强制子进程 UTF-8 输出。
    _child_env = dict(os.environ)
    _child_env["PYTHONIOENCODING"] = "utf-8"
    _child_env["PYTHONUTF8"] = "1"
    result = subprocess.run(
        [sys.executable, "learning_system.py", "--poll"],
        capture_output=True,
        timeout=120,
        cwd=work_dir,
        env=_child_env
    )
    _out = (result.stdout or b"").decode("utf-8", errors="replace")
    _err = (result.stderr or b"").decode("utf-8", errors="replace")
    log(f"Python退出码: {result.returncode}")
    log(f"Python stdout:\n{_out}")
    if _err:
        log(f"Python stderr:\n{_err}")

    # 写入心跳
    log("开始写入心跳...")
    try:
        hb_result = subprocess.run(
            [sys.executable, "heartbeat.py"],
            capture_output=True,
            timeout=30,
            cwd=work_dir,
            env=_child_env
        )
        log(f"心跳写入退出码: {hb_result.returncode}")
        if hb_result.stdout:
            log(f"心跳写入输出: {(hb_result.stdout or b'').decode('utf-8','replace')}")
        if hb_result.stderr:
            log(f"心跳写入错误: {(hb_result.stderr or b'').decode('utf-8','replace')}")
    except Exception as e:
        log(f"心跳写入异常: {e}")

    log("=== 任务计划结束 ===")
    sys.exit(result.returncode)
except Exception as e:
    log(f"运行异常: {e}")
    log("=== 任务计划异常结束 ===")
    sys.exit(1)
