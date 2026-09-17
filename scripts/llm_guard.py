#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LLM 调用守卫（M2/M3）— 限流退避 + 成本预算 + 熔断
==================================================
解决蓝图缺口：
  - 429/Retry-After 未处理（外部API写规范）
  - 月成本无预算上限（单位经济性）
  - 连续失败无熔断（稳定性）

用法：
    from llm_guard import guarded_call
    r = guarded_call(fn, model="deepseek-ai/DeepSeek-V2.5", est_tokens=800)
纯标准库；预算/用量落盘 runtime/llm_usage.json（月度滚动）。
"""
import json, time, os, sys
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USAGE = ROOT / "runtime" / "llm_usage.json"

# 预算（元/月）：DeepSeek Flash 为主，约25元/月
MONTHLY_BUDGET_CNY = float(os.environ.get("LLM_MONTHLY_BUDGET_CNY", "30"))
MAX_RETRIES = 4
BASE_BACKOFF = 1.5          # 秒，指数退避基数
CIRCUIT_FAILS = 5           # 连续失败阈值
CIRCUIT_COOLDOWN = 300      # 熔断冷却秒

COST_PER_1K = {
    "deepseek-chat": 0.001, "deepseek-ai/DeepSeek-V2.5": 0.001,
    "Qwen/Qwen2.5-7B-Instruct": 0.002, "qwen2.5:1.5b": 0.0, "offline": 0.0,
}
_state = {"fails": 0, "open_until": 0.0}

def _load():
    if USAGE.exists():
        try:
            return json.loads(USAGE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save(d):
    USAGE.parent.mkdir(parents=True, exist_ok=True)
    USAGE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def month_key():
    return date.today().strftime("%Y-%m")

def spent_this_month():
    d = _load()
    return float(d.get(month_key(), {}).get("cost_cny", 0.0))

def record_cost(model, tokens):
    d = _load()
    mk = month_key()
    rec = d.setdefault(mk, {"cost_cny": 0.0, "calls": 0, "tokens": 0})
    cost = tokens / 1000 * COST_PER_1K.get(model, 0.0)
    rec["cost_cny"] = round(rec["cost_cny"] + cost, 6)
    rec["calls"] += 1
    rec["tokens"] += int(tokens or 0)
    _save(d)
    return rec["cost_cny"]

def budget_left():
    return round(MONTHLY_BUDGET_CNY - spent_this_month(), 4)

def circuit_open():
    return time.time() < _state["open_until"]

def _retry_after(exc):
    """从异常/响应头解析 Retry-After（秒）。注意：HTTP 状态码 429 不是等待值。"""
    # 1) 显式响应头（requests/urllib3 风格）
    hdr = getattr(exc, "headers", None)
    if hdr:
        try:
            v = hdr.get("Retry-After") or hdr.get("retry-after")
            if v is not None:
                f = float(v)
                if 0 <= f <= 3600:
                    return f
        except Exception:
            pass
    # 2) 显式 retry_after 属性
    ra = getattr(exc, "retry_after", None)
    if ra is not None:
        try:
            f = float(ra)
            if 0 <= f <= 3600:
                return f
        except Exception:
            pass
    # 3) 文本：仅取 "Retry-After: N" 后的数字，不把状态码 429 当等待值
    import re
    m = re.search(r"retry[-_ ]?after\D{0,4}(\d+(?:\.\d+)?)", str(exc), re.IGNORECASE)
    if m:
        try:
            f = float(m.group(1))
            if 0 <= f <= 3600:
                return f
        except Exception:
            pass
    return None

def guarded_call(fn, model="deepseek-chat", est_tokens=800, on_degrade=None, max_retries=None):
    """
    受控调用：
      - 熔断开启 → 直接降级
      - 预算不足 → 降级
      - 429 → 按 Retry-After / 指数退避重试
      - 连续失败达阈值 → 熔断冷却
    返回 (ok, result_or_none, meta)
    """
    meta = {"model": model, "attempts": 0, "degraded": False, "reason": None}
    if circuit_open():
        meta.update(degraded=True, reason="circuit_open")
        return False, (on_degrade() if on_degrade else None), meta
    if spent_this_month() + est_tokens / 1000 * COST_PER_1K.get(model, 0) > MONTHLY_BUDGET_CNY:
        meta.update(degraded=True, reason="budget_exceeded")
        return False, (on_degrade() if on_degrade else None), meta

    last = None
    tries = max_retries if max_retries is not None else MAX_RETRIES
    for i in range(tries):
        meta["attempts"] = i + 1
        try:
            res = fn()
            _state["fails"] = 0
            meta["month_spent_cny"] = record_cost(model, est_tokens)
            return True, res, meta
        except Exception as e:
            last = e
            wait = _retry_after(e)
            if wait is None:
                wait = BASE_BACKOFF ** (i + 1)
            time.sleep(min(wait, 30))
    _state["fails"] += 1
    if _state["fails"] >= CIRCUIT_FAILS:
        _state["open_until"] = time.time() + CIRCUIT_COOLDOWN
        meta["reason"] = "circuit_tripped"
    meta["degraded"] = True
    meta["error"] = str(last)[:200]
    return False, (on_degrade() if on_degrade else None), meta

def status():
    return {
        "month": month_key(),
        "spent_cny": spent_this_month(),
        "budget_cny": MONTHLY_BUDGET_CNY,
        "left_cny": budget_left(),
        "circuit_open": circuit_open(),
        "consecutive_fails": _state["fails"],
    }

if __name__ == "__main__":
    sys.stdout = __import__("io").TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    print(json.dumps(status(), ensure_ascii=False, indent=2))
