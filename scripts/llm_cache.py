# -*- coding: utf-8 -*-
"""llm_cache.py — DeepSeek 结果缓存 + request_hash 去重（V49）
=============================================================
策略：对 prompt 内容做 sha256（不含时间戳/随机ID，保证前缀稳定），
相同请求直接返回缓存，不再调模型，省 Token。
存储：scripts/.llm_cache.json （带 TTL，默认7天）
用法：
  from llm_cache import get_cache, set_cache
  hit = get_cache("deepseek-chat", prompt)
  if hit: return hit
  ans = call_deepseek(prompt); set_cache("deepseek-chat", prompt, ans)
"""
import json, time, hashlib
from pathlib import Path

CACHE_FILE = Path(__file__).parent / ".llm_cache.json"
TTL = 7 * 24 * 3600  # 7天


def _key(model, prompt):
    s = f"{model}||{prompt.strip()}"
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:32]


def _load():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(d):
    CACHE_FILE.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


def get_cache(model, prompt):
    d = _load()
    k = _key(model, prompt)
    item = d.get(k)
    if not item:
        return None
    if time.time() - item["ts"] > TTL:
        return None
    return item["answer"]


def set_cache(model, prompt, answer):
    d = _load()
    k = _key(model, prompt)
    d[k] = {"ts": time.time(), "answer": answer, "model": model}
    # 简单防膨胀：超过500条清掉最旧的
    if len(d) > 500:
        items = sorted(d.items(), key=lambda kv: kv[1].get("ts", 0))
        d = dict(items[-400:])
    _save(d)


if __name__ == "__main__":
    # 自测：同一问两次，第二次应命中缓存
    m = "deepseek-chat"
    q = "备份几点跑"
    print("第一次:", get_cache(m, q) or "(未命中，将调模型)")
    set_cache(m, q, "凌晨3点跑（测试缓存内容）")
    hit = get_cache(m, q)
    print("第二次:", hit)
    print("✅ request_hash 去重工作正常" if hit else "❌ 缓存未命中")
