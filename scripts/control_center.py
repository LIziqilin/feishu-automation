# -*- coding: utf-8 -*-
"""control_center.py — 系统统一总控入口（V49）
================================================================
一个程序封装所有核心脚本、桥接与三报。双击/命令行调用即可，不用记脚本名。

用法：
  python control_center.py            显示菜单
  python control_center.py health     系统健康自检
  python control_center.py bridge     8桥接巡检
  python control_center.py llm "问题"  LLM问答（Coze优先→DeepSeek）
  python control_center.py backup     立即备份
  python control_center.py webapi on|off|status   常驻API服务
  python control_center.py report morning|noon|evening
  python control_center.py assistant wrong_answer|weekly_report|profile|health
  python control_center.py all        一键全量自检
"""
import os, sys, subprocess, time
from pathlib import Path

HERE = Path(__file__).parent
sys.executable_py = sys.executable
PY = r"C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
os.chdir(HERE)
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"


def run(script, *args):
    cmd = [PY, "-X", "utf-8", str(HERE / script)] + list(args)
    print(f"\n$ {script} {' '.join(args)}")
    subprocess.run(cmd, cwd=str(HERE))


MENU = """
====================================================
        AI 个人效率系统 · 总控中心 (V49)
====================================================
  [1] health     系统健康自检（计划任务/心跳/备份）
  [2] bridge     8 桥接巡检
  [3] llm        LLM 问答（Coze→DeepSeek 双通道）
  [4] backup     立即备份 + 异地
  [5] webapi      常驻 API/Webhook 服务 on/off/status
  [6] report     早/午/晚报
  [7] assistant   DeepSeek 4助手（错题/周报/画像/健康）
  [8] all        一键全量自检
  [0] quit
===================================================="""


def main():
    args = sys.argv[1:]
    if not args:
        while True:
            print(MENU)
            c = input("请选择> ").strip()
            if c == "0": break
            elif c == "1": run("system_health_check.py")
            elif c == "2": run("bridge_health_check.py")
            elif c == "3": run("llm_router.py", input("你的问题: ").strip())
            elif c == "4": run("backup_with_rotation.py")
            elif c == "5":
                sub = input("on/off/status> ").strip()
                if sub == "on":
                    run("run_webapi.vbs") if False else os.system(f'start "" wscript "{HERE/"run_webapi.vbs"}"')
                    print("webapi 已启动")
                elif sub == "off":
                    os.system('powershell -c "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force}"')
                    print("webapi 已停止")
                else:
                    os.system('powershell -c "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { \'webapi 运行中\' } else { \'webapi 未运行\' }"')
            elif c == "6":
                which = input("morning/noon/evening> ").strip()
                run(f"run_{which}_wrapper.py")
            elif c == "7":
                which = input("wrong_answer/weekly_report/profile/health> ").strip()
                run("deepseek_assistants.py", which)
            elif c == "8":
                run("system_health_check.py"); run("bridge_health_check.py")
                run("llm_router.py", "--check")
            else:
                print("无效")
        return

    cmd = args[0]
    if cmd == "health": run("system_health_check.py")
    elif cmd == "bridge": run("bridge_health_check.py")
    elif cmd == "llm": run("llm_router.py", *args[1:])
    elif cmd == "backup": run("backup_with_rotation.py")
    elif cmd == "webapi":
        sub = args[1] if len(args) > 1 else "status"
        if sub == "on": os.system(f'start "" wscript "{HERE/"run_webapi.vbs"}"')
        elif sub == "off": os.system('powershell -c "Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {Stop-Process -Id $_.OwningProcess -Force}"')
        else: os.system('powershell -c "if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) { \'webapi 运行中 8765\' } else { \'webapi 未运行\' }"')
    elif cmd == "report": run(f"run_{args[1]}_wrapper.py") if len(args) > 1 else print("需 morning/noon/evening")
    elif cmd == "assistant": run("deepseek_assistants.py", args[1] if len(args) > 1 else "wrong_answer")
    elif cmd == "all":
        run("system_health_check.py"); run("bridge_health_check.py"); run("llm_router.py", "--check")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
