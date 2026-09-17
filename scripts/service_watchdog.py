#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
服务守护（M2/M3）— 关键本地服务探活 + 自愈重启
==============================================
背景：AnythingLLM 为 Electron 桌面应用，无常驻守护；崩溃后端口可能残留/消失，
      导致健康巡检误判、RAG 不可用。本脚本探活 → 自愈 → 复验 → 留证。
安全（R1/R3）：只启动进程，绝不删除数据/配置；重启失败仅告警，不反复狂拉。
产出 acceptance/evidence/watchdog/watchdog_<ts>.json
"""
import sys, io, json, time, ssl, subprocess, urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "acceptance" / "evidence" / "watchdog"

ANYTHINGLLM_EXE = Path(r"C:\Users\Administrator\AppData\Local\Programs\AnythingLLM\AnythingLLM.exe")
OBSIDIAN_EXE = r"D:\AI\obsidian安装包\安装流程\Obsidian.exe"

# name, probe_url, restart(kind,arg), ready_timeout_s, insecure_tls
# kind: "explorer"=经 explorer 拉新实例; "kill_explorer"=先清障再 explorer 拉起（用于僵尸进程）
SERVICES = [
    ("Ollama", "http://localhost:11434/", None, 0, False),
    ("AnythingLLM", "http://localhost:3001/api/ping", ("kill_exe", ANYTHINGLLM_EXE), 120, False),
    ("ObsidianREST", "https://127.0.0.1:27124/", ("kill_explorer", OBSIDIAN_EXE), 90, True),
]

# 重启前需清理的僵尸进程映像名（2026-09-16 修复：Obsidian 进程在但插件未监听）
KILL_IMAGES = {
    "kill_exe": ["AnythingLLM.exe"],
    "kill_explorer": ["Obsidian.exe"],
}


def _kill_alive(images):
    """强杀残留进程（优雅关闭会留幽灵进程；仅清障，不碰任何数据，R3）"""
    killed = []
    for img in images:
        try:
            r = subprocess.run(["taskkill", "/F", "/IM", img, "/T"],
                               capture_output=True, timeout=30)
            out = (r.stdout or b).decode("gbk", "replace") + (r.stderr or b).decode("gbk", "replace")
            if r.returncode == 0 or "SUCCESS" in out or "成功" in out:
                killed.append(img)
        except Exception:
            pass
    return killed


def _ssl_ctx(insecure):
    if not insecure:
        return None
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE
    return c


def probe(url, timeout=6, insecure=False):
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout,
                                    context=_ssl_ctx(insecure)) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return True, f"HTTP {e.code}"          # 有响应即视为在跑
    except Exception as e:
        return False, str(e)[:90]


def start_app(kind, arg):
    try:
        imgs = KILL_IMAGES.get(kind)
        killed = _kill_alive(imgs) if imgs else []
        if kind in ("explorer", "kill_explorer"):
            # Obsidian 需通过 explorer 走用户会话（兼容远程桌面）
            subprocess.Popen(["explorer.exe", str(arg)])
        else:
            DETACHED = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
            subprocess.Popen([str(arg)], creationflags=DETACHED,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        info = "spawned" + (f",killed={killed}" if killed else "")
        return True, info
    except Exception as e:
        return False, str(e)[:90]


def main():
    results = []
    for name, url, restart, ready_to, insecure in SERVICES:
        ok, detail = probe(url, insecure=insecure)
        action = "none"
        if not ok and restart:
            spawned, sinfo = start_app(*restart)
            action = f"restart({sinfo})"
            if spawned:
                deadline = time.time() + ready_to
                while time.time() < deadline:
                    time.sleep(5)
                    ok, detail = probe(url, insecure=insecure)
                    if ok:
                        break
        results.append({"service": name, "up": ok, "detail": detail, "action": action})

    up = sum(1 for r in results if r["up"])
    recovered = [r for r in results if r["up"] and r["action"].startswith("restart")]
    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "total": len(results), "up": up,
        "down": [r["service"] for r in results if not r["up"]],
        "recovered": [r["service"] for r in recovered],
        "results": results,
    }
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"watchdog_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"服务守护: {up}/{len(results)} 在线" +
          (f" | 已自愈重启: {report['recovered']}" if recovered else "") +
          (f" | ⚠仍宕: {report['down']}" if report['down'] else ""))
    for r in results:
        print(f"  [{'OK ' if r['up'] else 'BAD'}] {r['service']:14} {r['detail']} action={r['action']}")
    print("证据:", p)
    return 0 if up == len(results) else 2


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
