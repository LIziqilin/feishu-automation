#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""早报任务包装脚本：设置环境变量并运行learning_system.py --select"""

import os
import sys
import subprocess

# 设置PATH包含hermes lark-cli路径
hermes_path = r"C:\Users\Administrator\AppData\Local\hermes\node"
os.environ["PATH"] = hermes_path + ";" + os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置工作目录
work_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(work_dir)

# 运行learning_system.py --select
result = subprocess.run(
    [sys.executable, "learning_system.py", "--select"],
    capture_output=True,
    timeout=120,
    cwd=work_dir
)

# 输出结果（UTF-8解码）
if result.stdout:
    sys.stdout.write(result.stdout.decode("utf-8", errors="replace"))
if result.stderr:
    sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))

sys.exit(result.returncode)
