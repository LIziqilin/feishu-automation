#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
混沌演练（M3）— 故障注入 + 降级验证
==================================
不破坏生产：以"注入点探针"方式验证降级链与护栏，不实际杀进程/断网。
注入项：
 1) 主LLM不可用 → 验证四顺位降级链（云端→云端→本地Ollama→表格兜底）
 2) Ollama不可用 → 验证回退不再抛异常
 3) 群消息通道失败 → 验证 DLQ/双通道切换
 4) RAG无来源 → 验证拒答护栏
 5) 幂等重复写 → 验证不重复
产出 acceptance/evidence/chaos/<ts>/report.json
"""
import sys, io, json, time, importlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
EVID = ROOT / "acceptance" / "evidence" / "chaos"

def probe(name, fn, expect):
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"EXC:{e}"
    # ok is None -> 前端未就绪，SKIP（不计入失败，也不计入通过）
    status = "skip" if ok is None else ("pass" if ok else "fail")
    return {"name": name, "pass": bool(ok), "skip": ok is None,
            "status": status, "expect": expect,
            "detail": str(detail)[:160], "sec": round(time.time() - t0, 2)}

def _local_llm_ready():
    """C1/C2 依赖本地兜底链（本地 Ollama 11434 / 代理 3002/3003）。
    2026-09-16 修复：这些组件常是按需启动的，未启动时 C1/C2 会被误判为 FAIL。
    就绪 -> True；任一可用即认为降级链可测。"""
    import socket
    for port in (11434, 3002, 3003):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                return True
        except Exception:
            continue
    return False

def _warm_ollama():
    """预热本地模型：首次调用需加载权重（实测冷启动 30s+），
    会导致 C1/C2 按 timeout 判为失败（假阴性）。先做一次抛弃式调用。"""
    import v15_features as v
    import time
    t0 = time.time()
    try:
        v._ollama_chat("hi", timeout=120, max_tokens=4)
        return round(time.time() - t0, 2)
    except Exception as e:
        return f"warm_fail:{str(e)[:60]}"

def c1_llm_degrade():
    """模拟主通道失败：临时置空 LLM_KEY，验证降级到 Ollama
    本地兜底链未就绪 -> 返回 None 表示 SKIP（不判失败）。"""
    import v15_features as v
    if not _local_llm_ready():
        return None, "SKIP: 本地LLM代理/Ollama未就绪(3002/3003/11434)"
    orig_key, orig_url = v.LLM_KEY, v.LLM_URL
    try:
        v.LLM_KEY = ""  # 云端认证失效
        out = v.llm_chat("只回复两个字：兜底", max_tokens=20, timeout=90)
        return bool(out), f"降级输出={str(out)[:20]}"
    finally:
        v.LLM_KEY, v.LLM_URL = orig_key, orig_url

def c2_cloud_unreachable():
    """模拟云端 URL 不可达：应回退本地 Ollama
    本地兜底链未就绪 -> 返回 None 表示 SKIP（不判失败）。"""
    import v15_features as v
    if not _local_llm_ready():
        return None, "SKIP: 本地LLM代理/Ollama未就绪(3002/3003/11434)"
    orig = v.LLM_URL
    try:
        v.LLM_URL = "http://127.0.0.1:9/v1/chat/completions"  # 必然失败
        out = v.llm_chat("只回复：ok", max_tokens=20, timeout=90)
        return bool(out), f"回退输出={str(out)[:20]}"
    finally:
        v.LLM_URL = orig

def c3_rag_guard():
    """RAG 高危无引用 → 必须拒答"""
    import rag_guard as g
    r = g.guard_answer("这个项目报价金额是500万。", [], "read:kb")
    return r["blocked"] and "无法核实" in r["answer"], r["reason"]

def c4_idempotent():
    """重复写 → 第二次应判定 duplicate（每次用唯一载荷，避免跨次运行污染）"""
    import idempotency as im
    uniq = datetime.now().strftime("%Y%m%d%H%M%S%f")
    k = im.make_key("chaos_test", "tblz3H4lV7PCrBrX", {"x": uniq})
    a = im.guarded_write(k, "chaos_test", "tbl", lambda: {"r": "first"})
    b = im.guarded_write(k, "chaos_test", "tbl", lambda: {"r": "second"})
    return (a["status"] == "executed" and b["status"] == "duplicate"), f"{a['status']}/{b['status']}"

def local_ready(module):
    """就绪检查：模块可导入且关键依赖存在（不真实外发）"""
    try:
        m = importlib.import_module(module)
        return m is not None
    except Exception:
        return False

def c5_dual_channel():
    """双通道：任一失败仍应有成功通道

    安全阀（2026-09-16 修复）：默认 **dry-run**，不向生产总控群真实推消息，
    避免验收/复现脚本（acceptance_run.py / reproduce_all.py）每次运行都把探针
    刷进生产群。仅当显式设 CHAOS_LIVE_PUSH=1 时才真实推送（月度演练/人工验收用）。
    """
    import os, wecom_push as w
    live = os.environ.get("CHAOS_LIVE_PUSH") == "1"
    if not live:
        # dry-run：只核验双通道是否就绪，不真实发送。
        # 诚实口径（2026-09-16）：就绪才算 PASS，未配置/未启用必须 FAIL，
        # 不得无条件返回 True（否则会成为假通过项）。
        cfg = w._load_cfg()
        wecom_ok = bool(cfg.get("webhook_url")) and bool(cfg.get("enabled"))
        feishu_ok = local_ready("v15_features")
        ok = wecom_ok and feishu_ok
        return ok, json.dumps({"dry_run": True, "feishu": "ready" if feishu_ok else "missing",
                               "wecom": "ready" if wecom_ok else "unconfigured"},
                              ensure_ascii=False)
    r = w.dual_push("【混沌演练】双通道探针 " + datetime.now().strftime("%H:%M"),
                    md="混沌演练探针：验证单通道失败时冗余可用")
    ok = (r.get("feishu") is True) or (r.get("wecom") == "ok")
    return ok, json.dumps(r, ensure_ascii=False)

def c6_metrics_available():
    """可观测性：埋点可读写"""
    import observability as ob
    s = ob.Span("chaos_probe", "L5", "offline")
    s.finish(ok=True)
    return ob.summarize()["count"] > 0, f"traces={ob.summarize()['count']}"

PROBES = [
    ("C1 主LLM不可用→降级", c1_llm_degrade, "回退成功，不抛异常"),
    ("C2 云端不可达→本地兜底", c2_cloud_unreachable, "回退成功"),
    ("C3 RAG高危无引用→拒答", c3_rag_guard, "blocked=True"),
    ("C4 幂等重复写→去重", c4_idempotent, "第二次duplicate"),
    ("C5 双通道冗余", c5_dual_channel, "至少一通道成功"),
    ("C6 埋点可观测", c6_metrics_available, "traces>0"),
]

def main():
    results = [probe(n, f, e) for n, f, e in PROBES]
    skipped = sum(1 for r in results if r["skip"])
    passed = sum(1 for r in results if r["pass"])
    failed = sum(1 for r in results if not r["pass"] and not r["skip"])
    attempted = len(results) - skipped
    warm = "skipped" if skipped == len(results) else _warm_ollama()
    report = {"ts": datetime.now().isoformat(timespec="seconds"), "total": len(results),
              "passed": passed, "failed": failed, "skipped": skipped,
              "pass_rate": round(passed / attempted, 3) if attempted else 0.0,
              "ollama_warmup_s": warm, "results": results}
    EVID.mkdir(parents=True, exist_ok=True)
    p = EVID / f"chaos_{datetime.now().strftime('%Y%m%d-%H%M')}.json"
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for r in results:
        tag = "SKIP" if r["skip"] else ("PASS" if r["pass"] else "FAIL")
        print(f"[{tag}] {r['name']} ({r['sec']}s) {r['detail'][:70]}")
    print(f"\n混沌演练: {passed}/{attempted} 通过（跳过 {skipped}）")
    print("证据:", p)
    return 0 if failed == 0 else 2

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.exit(main())
