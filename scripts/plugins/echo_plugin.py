# -*- coding: utf-8 -*-
"""echo_plugin.py — 示例插件：回显事件并记录
==========================================
演示插件接口：NAME / info() / handle(event)。
真实第三方插件可放同目录，遵循同样接口即可被自动加载。"""
NAME = "echo"


def info():
    return {"version": "1.0", "desc": "示例插件：回显事件并写记录，用于验证插件机制"}


def handle(event):
    etype = event.get("type", "unknown")
    payload = event.get("payload", {})
    line = f"[echo-plugin] 收到事件 type={etype} payload={payload}"
    # 简单落一行到插件日志（不依赖任何服务）
    from pathlib import Path
    log = Path(__file__).parent / "_plugin_events.log"
    with open(log, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    return f"已记录事件 {etype}"
