#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
可观测性埋点模块（M2）— SLO 指标采集（trace_id / 延迟 / 成功率 / 成本）
=====================================================================
轻量、零依赖。JSONL append-only 落盘，供 acceptance_run / 健康巡检聚合。
指标：trace_id、ts、task、layer、ok、latency_ms、model、tokens、cost_cny、error。
"""
import json, time, uuid, os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRACE_LOG = ROOT / "runtime" / "metrics" / "traces.jsonl"

# 成本系数（元/千token，按硅基流动牌价近似；本地Ollama计0）
COST_PER_1K = {"Qwen/Qwen2.5-7B-Instruct": 0.0, "deepseek-ai/DeepSeek-V3.2": 0.001,
               "deepseek-ai/DeepSeek-V2.5": 0.0,  # 已下线，保留兼容映射
               "qwen2.5:1.5b": 0.0, "offline": 0.0}

class Span:
    def __init__(self, task, layer="L1", model=None):
        self.trace_id = uuid.uuid4().hex[:16]
        self.task = task
        self.layer = layer
        self.model = model
        self.t0 = time.time()
        self.tokens = 0
        self.span_events = []

    def add(self, **kw):
        self.span_events.append(kw)
        if "tokens" in kw:
            self.tokens += int(kw["tokens"] or 0)

    def finish(self, ok=True, error=None):
        dt = round((time.time() - self.t0) * 1000, 1)
        cost = round(self.tokens / 1000 * COST_PER_1K.get(self.model or "", 0.0), 6)
        rec = {
            "trace_id": self.trace_id, "ts": datetime.now().isoformat(timespec="milliseconds"),
            "task": self.task, "layer": self.layer, "ok": bool(ok),
            "latency_ms": dt, "model": self.model, "tokens": self.tokens,
            "cost_cny": cost, "error": error, "events": self.span_events,
        }
        TRACE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(TRACE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

def read_traces(limit=1000):
    if not TRACE_LOG.exists():
        return []
    lines = TRACE_LOG.read_text(encoding="utf-8").splitlines()[-limit:]
    out = []
    for l in lines:
        try:
            out.append(json.loads(l))
        except Exception:
            pass
    return out

def summarize(limit=1000):
    """聚合 SLO 指标：成功率、P95延迟、成本、分任务统计"""
    tr = read_traces(limit)
    if not tr:
        return {"count": 0, "note": "无埋点数据"}
    ok = sum(1 for t in tr if t["ok"])
    lats = sorted(t["latency_ms"] for t in tr)
    p95 = lats[int(len(lats) * 0.95) - 1] if len(lats) > 1 else lats[0]
    by_task = {}
    for t in tr:
        b = by_task.setdefault(t["task"], {"n": 0, "ok": 0, "lat_ms": []})
        b["n"] += 1; b["ok"] += 1 if t["ok"] else 0; b["lat_ms"].append(t["latency_ms"])
    for k, v in by_task.items():
        v["success_rate"] = round(v["ok"] / v["n"], 3)
        v["p95_ms"] = sorted(v["lat_ms"])[int(len(v["lat_ms"]) * 0.95) - 1]
        v.pop("lat_ms")
    return {
        "count": len(tr),
        "success_rate": round(ok / len(tr), 3),
        "p95_ms": p95,
        "total_cost_cny": round(sum(t.get("cost_cny", 0) for t in tr), 4),
        "by_task": by_task,
    }

if __name__ == "__main__":
    import sys, io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    s = Span("GT-03", "L1", "Qwen/Qwen2.5-7B-Instruct")
    s.add(tokens=320, step="query")
    s.finish(ok=True)
    print(json.dumps(summarize(), ensure_ascii=False, indent=2))
