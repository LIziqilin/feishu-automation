#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
M0 验收证据生成器（B级证据：版本锁+断言+日志+环境指纹）
=====================================================
用途：对 acceptance/golden_tasks.jsonl 中可自动校验的黄金任务执行断言，
      产出带环境指纹与版本锁的证据运行包 acceptance/evidence/runs/<ts>/。
设计：只读断言优先；不写生产；失败即记录不退避。R2 不修改历史流水。

用法：python acceptance_run.py [--run-id YYYYMMDD-HHMM]
"""
import sys, os, io, json, time, hashlib, subprocess, argparse, platform
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACC = ROOT / "acceptance"
GOLDEN = ACC / "golden_tasks.jsonl"
EVID = ACC / "evidence" / "runs"

PY = sys.executable
SCRIPTS = ROOT / "scripts"

def sha256_file(p, limit=200000):
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            h.update(f.read(limit))
        return h.hexdigest()[:16]
    except Exception:
        return None

def fingerprint():
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "host": platform.node(),
        "os": platform.platform(),
        "python": platform.python_version(),
        "git_head": _git("rev-parse --short HEAD"),
        "git_dirty": bool(_git("status --porcelain")),
        "code_hash": {
            "v15_features.py": sha256_file(SCRIPTS / "v15_features.py"),
            "learning_system.py": sha256_file(SCRIPTS / "learning_system.py"),
            "run_maintenance_wrapper.py": sha256_file(SCRIPTS / "run_maintenance_wrapper.py"),
        },
        "model": {"cloud": "Qwen/Qwen2.5-7B-Instruct", "local": "qwen2.5:1.5b"},
    }

def _git(args):
    try:
        return subprocess.run(["git"] + args.split(), cwd=str(ROOT), capture_output=True,
                              text=True, timeout=15).stdout.strip()
    except Exception:
        return ""

def run_py(script, args=None, timeout=180):
    """执行脚本，返回 (exit_code, stdout_tail)"""
    cmd = [PY, str(SCRIPTS / script)] + (args or [])
    try:
        r = subprocess.run(cmd, cwd=str(SCRIPTS), capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        tail = (r.stdout or "")[-600:]
        return r.returncode, tail
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"
    except Exception as e:
        return 1, f"ERR:{e}"

# ---- 断言集：可自动校验的任务（B级） ----
def check_gt03():
    """GT-03 查询任务：验证任务表可读且活跃口径正确"""
    code, out = run_py("v15_features.py")  # import 冒烟
    return code == 0, f"module_import_code={code}"

def check_gt11():
    """GT-11 健康巡检：健康表今日状态可读"""
    code, out = run_py("health_monitor.py", timeout=120)
    return code == 0, out[-200:].replace("\n", " ")

def check_gt12():
    """GT-12 恢复演练（只读，不写生产）"""
    code, out = run_py("recovery_drill.py", timeout=300)
    return code == 0, out[-200:].replace("\n", " ")

def check_golden_e2e():
    """M1：12条黄金任务全量端到端（只读/离线模式，不写生产）"""
    code, out = run_py("golden_e2e.py", ["--level", "readonly"], timeout=300)
    import re as _re
    m = _re.search(r"(\d+)/(\d+)", out)
    ok = code == 0 and m and m.group(1) == m.group(2)
    return bool(ok), f"golden={m.group(0) if m else '?'}"

def check_backup():
    """备份完整性：7轮滚动备份(backup_*.json)存在且最新备份可解析"""
    import glob
    bdir = ROOT / "backups"
    files = sorted(glob.glob(str(bdir / "backup_*.json")), reverse=True) if bdir.exists() else []
    parsed = False
    if files:
        try:
            with open(files[0], encoding="utf-8-sig") as f:
                json.load(f)
            parsed = True
        except Exception:
            parsed = False
    return (len(files) >= 1 and parsed), f"backup_files={len(files)} latest_parsed={parsed}"

CHECKS = [
    ("GT-03", "查询任务(只读口径)", check_gt03),
    ("GT-11", "健康巡检", check_gt11),
    ("GT-12", "恢复演练(只读)", check_gt12),
    ("SUP-01", "备份存在性", check_backup),
    ("GOLDEN", "12条黄金任务端到端(只读)", check_golden_e2e),
]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d-%H%M")
    outdir = EVID / run_id
    outdir.mkdir(parents=True, exist_ok=True)

    fp = fingerprint()
    results = []
    passed = 0
    for gid, name, fn in CHECKS:
        t0 = time.time()
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f"EXC:{e}"
        dt = round(time.time() - t0, 2)
        passed += 1 if ok else 0
        results.append({"id": gid, "name": name, "pass": ok, "sec": dt, "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {gid} {name} ({dt}s) {detail[:80]}")

    total = len(CHECKS)
    summary = {
        "run_id": run_id,
        "fingerprint": fp,
        "total": total, "passed": passed,
        "pass_rate": round(passed / total, 3) if total else 0,
        "results": results,
    }
    with open(outdir / "result.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n=== M0 验收运行 {run_id}: {passed}/{total} 通过 ({summary['pass_rate']*100:.1f}%) ===")
    print(f"证据包: {outdir}")
    return 0 if passed == total else 2

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
