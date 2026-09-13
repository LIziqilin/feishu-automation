#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""晚报任务包装脚本：设置环境变量并推送晚报"""

import os
import sys
import json
import subprocess

# 设置PATH包含hermes lark-cli路径
hermes_path = r"C:\Users\Administrator\AppData\Local\hermes\node"
os.environ["PATH"] = hermes_path + ";" + os.environ.get("PATH", "")
os.environ["PYTHONIOENCODING"] = "utf-8"

# 设置工作目录
work_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(work_dir)

# 添加脚本目录到sys.path
sys.path.insert(0, work_dir)

try:
    from v19_integration import DailyPusher
    
    # 推送晚报
    result = DailyPusher.push_report(
        "evening",
        chat_id="oc_1fe154e172ab04622b7ffa810ac172bc"
    )
    
    if result.get("success"):
        print(f"晚报推送成功: {result.get('message_id', 'N/A')}")
        sys.exit(0)
    else:
        print(f"晚报推送失败: {result.get('error', '未知错误')}")
        sys.exit(1)
except Exception as e:
    print(f"晚报推送异常: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
