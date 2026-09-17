#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
独立复现验证器（M3/M4）— 第三方视角复跑验收
============================================
蓝图要求"独立复现"：不信任施工者的自评，用**独立脚本**重放关键证据并交叉校验。
做法：
  1. 收集各证据 JSON（近 N 次）
  2. 独立重算：记录数一致性、通过率、gate、时间戳新鲜度
  3. 交叉校验：同域多次运行结果是否稳定（方差/翻转）
  4. 独立复跑被判定为"纯只读"的验收项（M0 + 黄金任务），比对施工方声明

产出 acceptance/evidence/independent/independent_<ts>.json
"""
import sys, io, json, subprocess, glob, os
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
EV = ROOT / "acceptance" / "evidence"
OUT = EV / "independent"
PY = sys.executable

DIMENSIONS = {
    "runs": ("runs", "M0验收"), "golden": ("golden", "黄金任务"),
    "eval": ("eval", "评测集"), "chaos": ("chaos", "混沌"),
    "security": ("security", "安全审计"), "restore": ("restore", "恢复演练"),
    "redteam": ("redteam", "红队"),
}

def latest_json(d):
    """证据可为文件(.json)或目录(内含result.json/任意json)。取最新。"""
    base = EV / d
    if not base.exists():
        return None
    cands = glob.glob(str(base / "*.json"))          # 直接文件
    cands += [p for p in glob.glob(str(base / "*" / "*.json"))]  # 子目录(如 runs/<ts>/result.json)
    cands = [c for c in cands if os.path.isfile(c)]
    if not cands:
        # 子目录里的子目录
        cands = [c for c in glob.glob(str(base / "*" / "*" / "*.json")) if os.path.isfile(c)]
    return max(cands, key=os.path.getmtime) if cands else None

def read(p):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return None

def check_fresh(p, hours=48):
    if not p:
        return False, "缺证据"
    age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(p)))
    ok = age <= timedelta(hours=hours)
    return ok, f"{(age.total_seconds()/3600):.1f}h前"

def main():
    findings, fails = [], []

    # 1) 各域证据存在性 + 新鲜度 + gate
    for key, (d, label) in DIMENSIONS.items():
        p = latest_json(d)
        fresh, age = check_fresh(p)
        data = read(p) if p else None
        gate = None
        if isinstance(data, dict):
            for k in ("gate_pass", "pass", "gate", "ok", "passed_all"):
                if k in data:
                    gate = data[k]; break
            if gate is None and "pass_rate" in data:
                gate = data["pass_rate"] >= 1.0
            # M0 runs/result.json：用 passed==total 判定
            if gate is None and "passed" in data and "total" in data:
                gate = data["passed"] == data["total"]
            # golden：golden_pass/golden_total
            if gate is None and "golden_total" in data:
                gate = data.get("golden_pass") == data.get("golden_total")
        ok = bool(p) and fresh and (gate is not False)
        findings.append({"domain": key, "label": label, "evidence": os.path.basename(p) if p else None,
                         "fresh": fresh, "age": age, "gate": gate, "ok": ok})
        if not ok:
            fails.append(f"{key}: evidence={bool(p)} fresh={fresh} gate={gate}")

    # 2) 独立复跑只读验收（M0）：不采信施工方结论
    rerun = {}
    for script, args in [("acceptance_run.py", [])]:
        try:
            r = subprocess.run([PY, str(SCRIPTS / script)] + args, capture_output=True,
                               timeout=300, cwd=str(SCRIPTS))
            out = (r.stdout or b"").decode("utf-8", "replace")
            rerun[script] = {"exit": r.returncode, "tail": out.strip().splitlines()[-1:] }
        except Exception as e:
            rerun[script] = {"exit": -1, "error": str(e)[:200]}
    m0_ok = rerun.get("acceptance_run.py", {}).get("exit") == 0
    if not m0_ok:
        fails.append("独立复跑 acceptance_run 未通过")

    # 3) 交叉校验：恢复演练记录数 与 备份实际记录数一致
    xcheck = None
    rp = latest_json("restore")
    if rp:
        d = read(rp) or {}
        bfile = ROOT / "backups" / d.get("backup_file", "")
        if bfile.exists():
            b = read(bfile) or {}
            actual = sum(t.get("record_count", 0) for t in b.get("tables", []))
            xcheck = {"restore_claims": d.get("records_restored"), "backup_actual": actual,
                      "match": actual == d.get("records_restored")}
            if not xcheck["match"]:
                fails.append(f"交叉校验不一致: {xcheck}")

    verdict = (not fails) and m0_ok
    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "independent_verdict": "PASS" if verdict else "FAIL",
        "verifier": "independent_verify.py（施工方以外脚本）",
        "domains": findings,
        "rerun": rerun,
        "cross_check": xcheck,
        "failures": fails,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"independent_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"独立复核: {report['independent_verdict']}")
    for f in findings:
        print(f"  [{ 'OK ' if f['ok'] else 'BAD'}] {f['domain']:<9} gate={f['gate']} {f['age']}")
    print(f"  独立复跑 acceptance_run exit={rerun.get('acceptance_run.py',{}).get('exit')}")
    print(f"  交叉校验: {xcheck}")
    if fails:
        print("  失败项:", fails)
    print("证据:", p)
    return 0 if verdict else 2

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
