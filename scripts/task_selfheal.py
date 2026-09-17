#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
计划任务自愈（M4 连续性保障）
================================
背景（2026-09-16 实测发现）：
  计划任务的**注册状态**可能在长期运行后损坏：任务 XML 文本完全一致、
  查询属性正常、下次运行时间正常，但每次执行都以异常码结束
  （实测 rc=2 / 0xC000013A），且不产生任何输出/证据。
  临时诊断任务用同一命令、同一脚本却 100% 成功 —— 证明问题在任务注册本身。
  修法是**重新注册**（用同一份 XML 做 delete + create），实测 rc 2→0。

本脚本：探活关键任务 → 发现“上次结果为失败码” → 自动重注册 → 复验 →
        留证 acceptance/evidence/selfheal/selfheal_<ts>.json

安全：
  - 执行前把每个任务的原始 XML 备份到 workspace/schtask_xml_backup/<ts>/
  - 只重建白名单内的 V16_* 任务；不触碰其他任务（R3 不删生产配置）
  - 默认 --dry-run，只有显式 --apply 才真正重注册
  - 重注册后复跑一次并校验 rc==0 才算修复成功
"""
import os, sys, io, json, time, argparse, subprocess, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "acceptance" / "evidence" / "selfheal"
BACKUP_ROOT = Path(r"C:\Users\Administrator\.openclaw\workspace\schtask_xml_backup")

# 白名单：M4 连续性所依赖的任务
WATCH_TASKS = [
    "V16_DailyMaintenance", "V16_HourlyBackup", "V16_ServiceWatchdog",
    "V16_LearningPoll", "V16_MorningReport", "V16_NoonReport",
    "V16_EveningReport", "V16_BootRecover",
]
# 非失败码：空 / 0（成功） / 267011（从未运行） / 267009（正在运行，0x41301）
OK_CODES = {"", "0", "267011", "267009"}
RUNNING_CODES = {"267009"}  # 0x41301 SCHED_S_TASK_RUNNING
# 状态字段表示“正在运行”——绝不能对运行中的任务做 delete+create（会自杀）
RUNNING_STATES = ("运行中", "Running")


def query(task):
    r = subprocess.run(["schtasks", "/query", "/tn", task, "/fo", "LIST", "/v"],
                       capture_output=True, timeout=30)
    if r.returncode != 0:
        return None
    out = r.stdout.decode("gbk", errors="replace")
    d = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def get_xml(task):
    r = subprocess.run(["schtasks", "/query", "/tn", task, "/xml", "ONE"],
                       capture_output=True, timeout=30)
    if r.returncode != 0 or not r.stdout:
        return None
    return r.stdout


def decode_xml(raw):
    for enc in ("utf-8-sig", "utf-16", "gbk"):
        try:
            t = raw.decode(enc)
            if "<Task" in t:
                return t
        except Exception:
            continue
    return None


def reregister(task, backup_dir):
    raw = get_xml(task)
    if not raw:
        return False, "无法获取任务 XML"
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / f"{task}.xml").write_bytes(raw)
    xml = decode_xml(raw)
    if not xml:
        return False, "XML 解码失败"
    tmp = backup_dir / f"{task}_rebuild.xml"
    tmp.write_text(xml, encoding="utf-16")
    subprocess.run(["schtasks", "/delete", "/tn", task, "/f"], capture_output=True, timeout=30)
    r = subprocess.run(["schtasks", "/create", "/tn", task, "/xml", str(tmp), "/f"],
                       capture_output=True, timeout=30)
    if r.returncode != 0:
        return False, "重注册失败: " + r.stdout.decode("gbk", "replace")[:120]
    return True, "已重注册"


def verify(task, wait_s=25):
    subprocess.run(["schtasks", "/run", "/tn", task], capture_output=True, timeout=30)
    # 等待直至任务不再“运行中”（运行中≠失败），最长 wait_s*3 秒
    for _ in range(max(1, wait_s // 5)):
        time.sleep(5)
        d = query(task)
        if not d:
            break
        rc = str(d.get("上次结果", "")).strip()
        st = str(d.get("模式", "")) + str(d.get("Status", ""))
        if rc not in RUNNING_CODES and not any(s in st for s in RUNNING_STATES):
            break
    d = query(task)
    if not d:
        return None
    return d.get("上次结果", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正执行重注册（默认 dry-run）")
    ap.add_argument("--task", default=None, help="只处理指定任务")
    ap.add_argument("--wait", type=int, default=25, help="复验等待秒数")
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    tasks = [args.task] if args.task else WATCH_TASKS
    backup_dir = BACKUP_ROOT / ts

    findings, actions = [], []
    for t in tasks:
        d = query(t)
        if not d:
            findings.append({"task": t, "state": "not_found"})
            continue
        rc = str(d.get("上次结果", "")).strip()
        st = str(d.get("模式", "")) + str(d.get("Status", ""))
        running = rc in RUNNING_CODES or any(s in st for s in RUNNING_STATES)
        if running:
            findings.append({"task": t, "last_result": rc, "bad": False,
                             "note": "运行中，跳过（不对运行中任务重注册）"})
            continue
        bad = rc not in OK_CODES
        findings.append({"task": t, "last_result": rc, "bad": bad,
                         "last_run": d.get("上次运行时间", "")})
        if not bad:
            continue
        if not args.apply:
            actions.append({"task": t, "action": "would_reregister", "reason": f"rc={rc}"})
            continue
        ok, info = reregister(t, backup_dir)
        if not ok:
            actions.append({"task": t, "action": "reregister_failed", "detail": info})
            continue
        rc2 = verify(t, wait_s=args.wait)
        fixed = str(rc2).strip() == "0"
        actions.append({"task": t, "action": "reregistered",
                        "rc_before": rc, "rc_after": rc2, "verified": fixed})

    report = {"ts": ts, "mode": "apply" if args.apply else "dry-run",
              "tasks_checked": len(tasks), "findings": findings,
              "actions": actions,
              "backup_dir": str(backup_dir) if args.apply else None,
              "bad_count": sum(1 for f in findings if f.get("bad"))}
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"selfheal_{ts}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"计划任务自愈 [{report['mode']}]: 检查 {len(tasks)} 个，异常 {report['bad_count']} 个")
    for f in findings:
        if f.get("bad"):
            print(f"  [BAD ] {f['task']:24s} rc={f.get('last_result')}")
    for a in actions:
        print("  ->", a)
    print("证据:", p)
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
