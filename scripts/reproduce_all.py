#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一键复现全套验收证据（M2 独立复现）
========================================
用途：任何第三方验收人，在干净环境执行本脚本，即可按顺序复跑全套证据电池，
      并生成可核对的 manifest（每步退出码 + 证据文件）。

用法：
    python reproduce_all.py            # 复跑全部（不含耗时最长的评测可选跳过）
    python reproduce_all.py --quick    # 跳过 eval(100条) 与 golden(12条) 长项
输出：acceptance/evidence/reproduce/manifest_<ts>.json
"""
import os, sys, io, json, subprocess, argparse, time
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
EVID = ROOT / "acceptance" / "evidence" / "reproduce"

PY = sys.executable
LOCK_FILE = ROOT / "acceptance" / ".acceptance.lock"
LOCK_STALE_HOURS = 2.0  # 锁龄超此值视为僵死锁，可覆盖


def _pid_alive(pid):
    """跨平台检测进程是否存活（不依赖 psutil）。"""
    if pid <= 0:
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                             capture_output=True, timeout=10)
        return str(pid) in (out.stdout or b"").decode("utf-8", "ignore")
    except Exception:
        # tasklist 不可用则保守按"存活"处理，避免误覆盖真锁
        return True


def _destructive_running():
    """检测是否有破坏性进程（taskkill/强制杀进程）正在运行——
    验收期禁止并发破坏操作，否则制造观测者自伤型假故障。"""
    bad = []
    for img in ("taskkill.exe",):
        try:
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {img}", "/NH"],
                                 capture_output=True, timeout=10)
            txt = (out.stdout or b"").decode("utf-8", "ignore")
            if img.lower() in txt.lower():
                bad.append(img)
        except Exception:
            pass
    return bad


def acquire_lock():
    """获取验收互斥锁；已在跑则拒绝，僵死锁可覆盖。返回锁文件路径。"""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            old = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            age_h = (time.time() - old.get("ts", 0)) / 3600.0
            if age_h < LOCK_STALE_HOURS and _pid_alive(old.get("pid", 0)):
                print(f"[互斥] 另一验收进程仍在跑 (pid={old.get('pid')}, {age_h:.1f}h前启动)，拒绝并发。")
                print(f"[互斥] 若确认是僵死锁，删除 {LOCK_FILE} 后重试。")
                sys.exit(3)
            print(f"[互斥] 发现旧锁({age_h:.1f}h)已僵死/进程不在，覆盖。")
        except Exception:
            print("[互斥] 旧锁损坏，按僵死锁覆盖。")
    LOCK_FILE.write_text(json.dumps({"pid": os.getpid(), "ts": time.time()},
                                    ensure_ascii=False), encoding="utf-8")
    return LOCK_FILE


def release_lock(lock):
    try:
        if lock and Path(lock).exists():
            Path(lock).unlink()
    except Exception:
        pass


BATTERY = [
    ("服务守护(自愈)", ["service_watchdog.py"], "watchdog", 180),
    ("安全审计", ["security_audit.py"], "security", 120),
    ("红队(真实护栏)", ["redteam_suite.py"], "redteam", 180),
    ("混沌演练", ["chaos_drill.py"], "chaos", 300),
    ("恢复演练(隔离)", ["restore_drill.py"], "restore", 300),
    ("写路径端到端(TEST_)", ["golden_write_e2e.py"], "golden_write", 300),
    ("离线模型评测", ["offline_model_eval.py"], "offline_model", 300),
    ("异地副本复制", ["offsite_replicate.py"], "offsite", 300),
    ("连续运行监视", ["uptime_monitor.py"], "uptime", 120),
    ("效率客观度量", ["efficiency_objective.py"], "efficiency", 120),
    ("观测埋点聚合", ["observability.py"], None, 120),
    ("慢速项:评测100条", ["eval_run.py"], "eval", 900),
    ("慢速项:黄金任务12", ["golden_e2e.py"], "golden", 600),
    ("M0验收脚手架", ["acceptance_run.py"], "runs", 900),
    ("评分卡", ["slo_monitor.py"], "scorecard", 120),
    ("独立复核", ["independent_verify.py"], "independent", 600),
    ("独立抽样复现(10条)", ["independent_sample.py", "--n", "10", "--seed", "20260916"], "independent", 600),
]
QUICK_SKIP = {"eval_run.py", "golden_e2e.py", "acceptance_run.py"}


def run_step(name, cmd, quick):
    if quick and cmd[0] in QUICK_SKIP:
        return {"name": name, "script": cmd[0], "skipped": True}
    t0 = time.time()
    try:
        r = subprocess.run([PY] + cmd, cwd=str(SCRIPTS), capture_output=True,
                           timeout=1800, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        out = (r.stdout or b"").decode("utf-8", "replace")
        err = (r.stderr or b"").decode("utf-8", "replace")
        tb = "Traceback" in (out + err)
        return {"name": name, "script": cmd[0], "rc": r.returncode, "traceback": tb,
                "elapsed_s": round(time.time() - t0, 1),
                "tail": [l for l in (out + err).splitlines() if l.strip()][-1:],
                "evidence_hint": next((l.split("证据", 1)[1].strip(" :") for l in out.splitlines()
                                       if "证据" in l), None)}
    except subprocess.TimeoutExpired:
        return {"name": name, "script": cmd[0], "rc": None, "timeout": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="跳过耗时的评测/黄金/M0 长项")
    args = ap.parse_args()
    lock = acquire_lock()
    import atexit
    atexit.register(release_lock, lock)  # 无论正常/异常退出都释放锁
    badprocs = _destructive_running()
    if badprocs:
        print(f"[互斥] 警告：检测到破坏性进程 {badprocs} 正在运行——")
        print("[互斥] 验收期间并发 taskkill/杀进程会制造观测者自伤型假故障，建议先结束再复跑。")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    results = []
    print("=" * 70)
    print(f"一键复现全套验收证据  quick={args.quick}  {ts}")
    print("=" * 70)
    for name, cmd, ev, _to in BATTERY:
        r = run_step(name, cmd, args.quick)
        results.append(r)
        if r.get("skipped"):
            print(f"[SKIP] {name}")
        else:
            flag = "OK " if r.get("rc") == 0 and not r.get("traceback") else "BAD"
            print(f"[{flag}] {name:24s} rc={r.get('rc')} {r.get('elapsed_s','')}s {(r.get('tail') or [''])[0][:60]}")
    bad = [r["script"] for r in results if not r.get("skipped") and (r.get("rc") != 0 or r.get("traceback"))]
    manifest = {"ts": ts, "quick": args.quick, "total": len(results),
                "failed": bad, "all_pass": not bad, "steps": results}
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"manifest_{ts}.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"复现完成: {'全部通过' if not bad else '失败项=' + ','.join(bad)}")
    print("manifest:", p)
    return 0 if not bad else 3


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
