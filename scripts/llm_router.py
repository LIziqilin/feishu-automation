#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""llm_router.py — V46 统一 LLM 网关（多通道 fallback）
====================================================================
LLM 调用统一入口，按优先级自动切换：
  通道1：Coze Bot（主，复杂任务）
  通道2：DeepSeek V4 flash（fallback，额度耗尽/Coze失败时自动切）

设计原则：
- 上层业务不关心用哪个模型，只调 chat(prompt)
- 每个通道失败/额度耗尽自动切下一个
- 日志记录每次走了哪个通道、耗时、是否fallback

用法：
  python llm_router.py "你的问题"
  python llm_router.py --check
"""
import os, sys, json, time, urllib.request, urllib.error

# 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # 环境变量优先
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # V4 flash

# Coze 配置文件
COZE_CONFIG = r"D:\AI-Tools\shared\coze_config.json"


def _load_coze():
    try:
        with open(COZE_CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _call_coze(prompt, timeout=120):
    """通道1：Coze Bot"""
    cfg = _load_coze()
    token = cfg.get("coze_api_token", "")
    bot_id = cfg.get("bot_id", "")
    if not token or not bot_id:
        return False, "coze_config 缺失"

    # POST /v3/chat
    body = json.dumps({
        "bot_id": bot_id, "user_id": "feishu-v46-router", "stream": False,
        "auto_save_history": True,
        "additional_messages": [{"role": "user", "content": prompt, "content_type": "text"}],
    }).encode()
    req = urllib.request.Request("https://api.coze.cn/v3/chat", data=body,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=30)
        d = json.loads(r.read().decode())
        chat_id = d.get("data", {}).get("id")
        conv_id = d.get("data", {}).get("conversation_id")
        if not chat_id:
            return False, f"coze no chat_id: {d.get('code')}"
        # 轮询
        for _ in range(20):
            time.sleep(2)
            req2 = urllib.request.Request(
                f"https://api.coze.cn/v3/chat/retrieve?chat_id={chat_id}&conversation_id={conv_id}",
                headers={"Authorization": "Bearer " + token})
            d2 = json.loads(urllib.request.urlopen(req2, timeout=15).read().decode())
            if d2.get("data", {}).get("status") == "completed":
                break
        # 取消息
        req3 = urllib.request.Request(
            f"https://api.coze.cn/v3/chat/message/list?chat_id={chat_id}&conversation_id={conv_id}",
            headers={"Authorization": "Bearer " + token})
        d3 = json.loads(urllib.request.urlopen(req3, timeout=15).read().decode())
        msgs = [m for m in d3.get("data", []) if m.get("type") == "answer"]
        return True, msgs[0]["content"] if msgs else "coze 无回复"
    except Exception as e:
        return False, f"coze 失败: {e}"


def _call_deepseek(prompt, timeout=60):
    """通道2：DeepSeek V4 flash（OpenAI 兼容）"""
    key = DEEPSEEK_API_KEY
    if not key:
        return False, "DEEPSEEK_API_KEY 未设置"
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
    }).encode()
    req = urllib.request.Request(DEEPSEEK_BASE + "/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(r.read().decode())
        return True, d["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return False, f"deepseek HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, f"deepseek 失败: {e}"


def chat(prompt):
    """统一入口：Coze 优先，失败自动切 DeepSeek"""
    t0 = time.time()
    ok, resp = _call_coze(prompt)
    if ok:
        print(f"[llm_router] Coze 通道 ✅ ({time.time()-t0:.1f}s)")
        return resp
    print(f"[llm_router] Coze 失败 → 切 DeepSeek: {resp}")
    ok2, resp2 = _call_deepseek(prompt)
    if ok2:
        print(f"[llm_router] DeepSeek 通道 ✅ ({time.time()-t0:.1f}s)")
        return resp2
    return f"[全部通道失败] Coze: {resp} | DeepSeek: {resp2}"


def check():
    print("=== LLM 网关自检 ===")
    ok, r = _call_coze("ping")
    print(f"Coze: {'✅' if ok else '❌'} {r[:80]}")
    ok2, r2 = _call_deepseek("ping")
    print(f"DeepSeek: {'✅' if ok2 else '❌'} {r2[:80]}")
    print(f"当前策略：Coze 优先 → DeepSeek fallback")


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        q = " ".join(a for a in sys.argv[1:] if not a.startswith("-"))
        if not q:
            print("用法: python llm_router.py '你的问题'")
            sys.exit(1)
        print(chat(q))
