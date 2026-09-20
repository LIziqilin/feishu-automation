#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""deepseek_gateway.py — DeepSeek V4 Flash API 网关（OpenAI 兼容）
====================================================================
用途：飞书多维表格 AI 额度耗尽后，自动切 DeepSeek V4 Flash。
与 coze_gateway.py 同接口：run(prompt) -> (ok, text)

配置：D:\\AI-Tools\\shared\\deepseek_config.json
  {
    "api_key": "sk-xxx",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-chat",
    "fallback_to_deepseek_when_coze_quota_exhausted": true
  }

用法：
  python deepseek_gateway.py "你好"
  python deepseek_gateway.py --check
"""
import os, sys, json, urllib.request, urllib.error

CONFIG = r"D:\AI-Tools\shared\deepseek_config.json"
DEFAULT_BASE = "https://api.deepseek.com"


def _load():
    if os.path.exists(CONFIG):
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    # 回退到环境变量
    return {
        "api_key": os.getenv("DEEPSEEK_API_KEY", ""),
        "base_url": os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
    }


def run(prompt, system=None, max_tokens=800, temperature=0.3, timeout=90):
    """统一接口：run(prompt) -> (ok, text)"""
    cfg = _load()
    key = cfg.get("api_key", "")
    if not key:
        return False, "未配置 DeepSeek API key（shared/deepseek_config.json）"
    base = cfg.get("base_url", DEFAULT_BASE).rstrip("/")
    model = cfg.get("model", "deepseek-chat")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode()

    req = urllib.request.Request(base + "/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(r.read().decode("utf-8", errors="replace"))
        text = d["choices"][0]["message"]["content"]
        usage = d.get("usage", {})
        return True, text
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode("utf-8", errors="replace"))
            return False, f"HTTP {e.code}: {err.get('error', {}).get('message', str(err))[:200]}"
        except Exception:
            return False, f"HTTP {e.code}"
    except Exception as e:
        return False, str(e)


def check():
    cfg = _load()
    print(f"DeepSeek 模型: {cfg.get('model')} | base: {cfg.get('base_url')}")
    ok, resp = run("ping，回复 pong 即可", max_tokens=20)
    print("✅ 连通" if ok else f"❌ {resp}")
    return ok


# ========== 智能路由：Coze 优先，额度耗尽自动切 DeepSeek ==========
def smart_run(prompt, max_tokens=800):
    """先试 Coze，失败/额度耗尽自动切 DeepSeek。返回 (ok, text, channel)"""
    try:
        import coze_gateway
        ok, resp = coze_gateway.run(prompt[:500])
        if ok:
            return True, resp, "coze"
        # 额度耗尽/限流/4015 等 → 切 DeepSeek
        if any(k in str(resp) for k in ["4015", "quota", "额度", "限流", "429", "rate", "403"]):
            ok2, resp2 = run(prompt, max_tokens=max_tokens)
            if ok2:
                return True, resp2, "deepseek-fallback"
            return False, f"Coze失败({resp[:80]}) + DeepSeek也失败({resp2[:80]})", "none"
        return False, resp, "coze-failed"
    except Exception as e:
        ok2, resp2 = run(prompt, max_tokens=max_tokens)
        if ok2:
            return True, resp2, "deepseek-direct"
        return False, str(e), "none"


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    elif len(sys.argv) > 1:
        ok, resp = run(" ".join(sys.argv[1:]))
        print(resp if ok else f"❌ {resp}")
