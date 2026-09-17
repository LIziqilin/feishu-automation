#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
独立抽样复现（M4 硬门槛 #4）
==============================
蓝图要求：由**独立验收人**随机抽取 ≥10 条任务，独立复跑，结果可核对。
本工具：
  1) 从评测集(eval_set.jsonl) + 黄金任务(golden_tasks.jsonl) 合并池中**随机抽样** N 条（默认10）
  2) 记录抽样种子(seed)与抽样清单 → 任何人可用同 seed 复现同一批
  3) 逐条独立复跑判定（复用 eval_run 的检索/裁判逻辑，不依赖施工者自评）
  4) 输出「抽样清单 + 逐条结果 + 通过率 + 复核人填写区」

用法：
  python independent_sample.py                # 随机抽 10 条（随机种子）
  python independent_sample.py --n 20 --seed 42
  python independent_sample.py --reviewer "张三"   # 签名留痕

产出 acceptance/evidence/independent/sample_<ts>.json
不写生产表；只读 + 离线判定。
"""
import sys, io, os, json, random, argparse, importlib.util
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
ACC = ROOT / "acceptance"
OUT = ACC / "evidence" / "independent"


def load_pool():
    """抽样池：评测集(eval_set.jsonl，100条，schema 与裁判一致)。
    golden_tasks.jsonl（12条黄金任务定义）由 golden_e2e.py 单独验收，
    此处不混入（其 schema 为任务定义而非可判定用例，混入会导致误判）。"""
    pool = []
    ep = ACC / "eval_set.jsonl"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("category") and (d.get("input") or d.get("task")):
                d["_src"] = "eval_set"
                pool.append(d)
    return pool


def judge(case):
    """独立判定：与施工方 eval_run 使用相同公开判据，但由本脚本调用。"""
    try:
        er = importlib.import_module("eval_run")
    except Exception as e:
        return False, f"import eval_run 失败: {e}"
    cat = case.get("category") or case.get("type") or "golden"
    if cat == "golden":
        fn = getattr(er, "judge_golden", None)
    else:
        fn = getattr(er, "judge_safety", None)
    if fn is None:
        return False, "judge 函数缺失"
    try:
        return fn(case)
    except Exception as e:
        return False, f"judge 异常: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--seed", type=int, default=None, help="随机种子（留空=系统随机）")
    ap.add_argument("--reviewer", default="", help="独立验收人姓名")
    args = ap.parse_args()

    sys.path.insert(0, str(SCRIPTS))
    pool = load_pool()
    if not pool:
        print("评测池为空，无法抽样"); return 2

    seed = args.seed if args.seed is not None else random.randrange(1, 10**9)
    rng = random.Random(seed)
    n = min(args.n, len(pool))
    picked = rng.sample(pool, n)

    rows = []
    for c in picked:
        ok, detail = judge(c)
        rows.append({
            "id": c.get("id"), "src": c.get("_src"),
            "category": c.get("category") or c.get("type"),
            "input": (c.get("input") or c.get("task") or "")[:120],
            "intent": c.get("intent"), "pass": bool(ok), "detail": str(detail)[:160],
            "ref": c.get("ref"),
        })

    passed = sum(1 for r in rows if r["pass"])
    rate = round(passed / len(rows), 3) if rows else 0
    report = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "purpose": "M4 硬门槛#4：独立验收人随机抽样复现",
        "seed": seed, "n": n, "pool_size": len(pool),
        "reviewer": args.reviewer or "(待填写)",
        "passed": passed, "total": len(rows), "pass_rate": rate,
        "gate_pass": rate >= 0.95,
        "reproduce_hint": f"同 seed 复现: python independent_sample.py --n {n} --seed {seed}",
        "signature_block": {"reviewer": args.reviewer or "____", "date": "____",
                            "verdict": "____", "note": "独立验收人签字区"},
        "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"sample_{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"独立抽样复现: {passed}/{len(rows)} ({rate*100:.1f}%) gate={'PASS' if rate>=0.95 else 'FAIL'} seed={seed}")
    for r in rows:
        print(f"  [{'PASS' if r['pass'] else 'FAIL'}] {r['id']} {r['category']} {str(r['input'])[:50]}")
    print(f"  复现命令: python independent_sample.py --n {n} --seed {seed}")
    print("证据:", p)
    return 0 if rate >= 0.95 else 2


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
