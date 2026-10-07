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

# V51.12: 导入缓存模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_cache import get_cache, set_cache

# 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # 环境变量优先
DEEPSEEK_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"  # V4 flash

# V53: Coze熔断——Coze连续失败/空回复后，冷却期内直接走DeepSeek，避免每次白等40秒轮询
_COZE_COOLDOWN = 1800  # 30分钟
# 熔断状态用文件持久化（webapi每次ask都新起子进程，内存变量会丢）
_CIRCUIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".coze_circuit")

def _circuit_read():
    try:
        return float(open(_CIRCUIT_FILE).read().strip())
    except Exception:
        return 0.0

def _circuit_write(ts):
    try:
        open(_CIRCUIT_FILE, "w").write(str(ts))
    except Exception:
        pass

# V51.12: 固定系统提示词前缀（利用DeepSeek前缀缓存，降低50-90%输入成本）
# 公共前缀稳定不变，只有用户问题部分变化
_SYSTEM_PREFIX = (
    "你是一个专业的中文AI助手，擅长学习辅导、任务管理和知识问答。"
    "回答简洁准确，不编造内容。"
)

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
        if not msgs or not msgs[0].get("content", "").strip():
            return False, "coze 返回空回复，自动切DeepSeek"
        return True, msgs[0]["content"].strip()
    except Exception as e:
        return False, f"coze 失败: {e}"


def _call_deepseek(prompt, timeout=60):
    """通道2：DeepSeek V4 flash（OpenAI 兼容）+ 缓存 + 前缀缓存"""
    # V51.12: 先查缓存（request_hash去重）
    hit = get_cache(DEEPSEEK_MODEL, prompt)
    if hit:
        print(f"[llm_router] 缓存命中（request_hash去重，省Token）")
        return True, hit

    key = DEEPSEEK_API_KEY
    if not key:
        return False, "DEEPSEEK_API_KEY 未设置"
    # V51.12: 使用固定system前缀（利用DeepSeek prompt caching）
    body = json.dumps({
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PREFIX},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 600,  # V51.12: 限制输出，降低成本
    }).encode()
    req = urllib.request.Request(DEEPSEEK_BASE + "/v1/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        d = json.loads(r.read().decode())
        answer = d["choices"][0]["message"]["content"]
        # V51.12: 写入缓存
        set_cache(DEEPSEEK_MODEL, prompt, answer)
        return True, answer
    except urllib.error.HTTPError as e:
        return False, f"deepseek HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, f"deepseek 失败: {e}"


def chat(prompt):
    """统一入口：Coze 优先，失败自动切 DeepSeek（V53: Coze熔断快速回退）"""
    t0 = time.time()
    # 熔断冷却期内（文件持久化）：直接跳过Coze，避免白等~40秒
    _dead = _circuit_read()
    if time.time() < _dead:
        print(f"[llm_router] Coze熔断中（剩余{int(_dead-time.time())}s）→ 直连DeepSeek")
        ok2, resp2 = _call_deepseek(prompt)
        if ok2:
            print(f"[llm_router] DeepSeek 通道 ✅ ({time.time()-t0:.1f}s)")
            return resp2
        return f"[DeepSeek失败] {resp2}"
    ok, resp = _call_coze(prompt)
    if ok:
        print(f"[llm_router] Coze 通道 ✅ ({time.time()-t0:.1f}s)")
        return resp
    # Coze失败/空回复 → 触发熔断，冷却期内不再试Coze
    _circuit_write(time.time() + _COZE_COOLDOWN)
    print(f"[llm_router] Coze 失败 → 熔断{_COZE_COOLDOWN}s并切 DeepSeek: {resp}")
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
