#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
开机/登录自愈（M4 连续性加固）
================================
背景：本机为笔记本（T480），且计划任务默认「电池时不启动」——
      一旦断电/重启，任务会静默停摆，导致「连续30天」硬门槛断档。
本脚本在每次**登录/开机**时运行，做两件事：
  1) 服务自愈：调用 service_watchdog，确保 Ollama/AnythingLLM/ObsidianREST 在线
  2) 断档留痕：把本次上线写入 runtime/boot_log.jsonl，并检出与上一条之间的断档窗口
不删除任何数据；只做启动与记录。
输出证据：acceptance/evidence/boot/boot_<ts>.json
"""
import os, sys, io, json, subprocess, argparse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
EVID = ROOT / "acceptance" / "evidence" / "boot"
BOOT_LOG = RUNTIME / "boot_log.jsonl"
SCRIPTS = ROOT / "scripts"
GAP_HOURS = 26.0  # 相邻两次上线超过此间隔即视为断档


def last_boot_record():
    if not BOOT_LOG.exists():
        return None
    lines = [l for l in BOOT_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except Exception:
        return None


def run_script(name, args=None, timeout=180):
    p = SCRIPTS / name
    if not p.exists():
        return {"script": name, "error": "missing"}
    cmd = [sys.executable, str(p)] + (args or [])
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return {"script": name, "rc": r.returncode}
    except Exception as e:
        return {"script": name, "error": str(e)[:150]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-watchdog", action="store_true", help="跳过服务自愈")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    now = datetime.now()
    prev = last_boot_record()
    gap_h = None
    if prev:
        try:
            gap_h = round((now - datetime.fromisoformat(prev["ts_iso"])).total_seconds() / 3600, 2)
        except Exception:
            gap_h = None
    gap_detected = bool(gap_h is not None and gap_h > GAP_HOURS)

    steps = []
    if not args.no_watchdog:
        steps.append(run_script("service_watchdog.py", timeout=240))
    # 计划任务自愈（M4）：登录后校验并修复损坏的任务注册，防止重启后断档
    steps.append(run_script("task_selfheal.py", args=["--apply", "--wait", "20"], timeout=600))

    rec = {
        "ts": ts, "ts_iso": now.isoformat(timespec="seconds"),
        "host": os.environ.get("COMPUTERNAME", "?"),
        "prev_ts": prev["ts_iso"] if prev else None,
        "gap_hours": gap_h,
        "gap_detected": gap_detected,
        "gap_threshold_hours": GAP_HOURS,
        "steps": steps,
    }

    RUNTIME.mkdir(parents=True, exist_ok=True)
    with open(BOOT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"boot_{ts}.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"登录自愈完成：gap={gap_h}h 断档={gap_detected} 服务自愈={steps}")
    print("证据:", p)
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
