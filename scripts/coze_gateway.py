#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""coze_gateway.py — V45 Coze 工作流/机器人接入（复杂 agentic 任务通道）
====================================================================
群指令「智能：xxx」-> 调 Coze Bot（finished Brain个人AI助理）执行复杂任务。
凭据：D:\AI-Tools\shared\coze_config.json（coze_api_token / bot_id）。

注意：Coze Bot 需先在 coze.cn 控制台「发布」到 "Agent As API" 渠道，
否则 API 返回 code=4015。未发布时本脚本返回明确提示（不阻塞主系统）。

用法：
  python coze_gateway.py "要执行的复杂任务描述"
  python coze_gateway.py --check        # 检查连接状态
"""
import os, sys, json, time, uuid, urllib.request, urllib.error

CONFIG = r"D:\AI-Tools\shared\coze_config.json"
API = "https://api.coze.cn"


def _load():
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _call(method, path, body=None, timeout=120):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + _load()["coze_api_token"],
                 "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=timeout)
        return r.status, json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except Exception:
            return e.code, {"code": -1, "msg": f"HTTP {e.code}"}
    except Exception as e:
        return -1, {"code": -1, "msg": str(e)}


def check():
    cfg = _load()
    print("Coze Bot:", cfg.get("bot_name"), "| token 有效期至:", cfg.get("token_expires_at"))
    st, d = _call("POST", "/v3/chat", {
        "bot_id": cfg["bot_id"], "user_id": "feishu-v45-check", "stream": False,
        "auto_save_history": False,
        "additional_messages": [{"role": "user", "content": "ping", "content_type": "text"}],
    }, timeout=30)
    if d.get("code") == 0:
        print("✅ Coze 通道可用")
        return True
    print(f"⚠️ Coze 通道不可用：code={d.get('code')} msg={d.get('msg')}")
    print("   → 请在 coze.cn 控制台将 Bot 发布到「Agent As API」渠道后重试")
    return False


def run(task, timeout=120):
    cfg = _load()
    st, d = _call("POST", "/v3/chat", {
        "bot_id": cfg["bot_id"], "user_id": "feishu-v45-" + uuid.uuid4().hex[:8],
        "stream": False, "auto_save_history": False,
        "additional_messages": [{"role": "user", "content": task, "content_type": "text"}],
    }, timeout=timeout)
    if d.get("code") == 0:
        # v3/chat 返回 chat_id，需轮询 /v3/chat/messages/retrieve
        chat_id = d.get("data", {}).get("id") or d.get("data", {}).get("chat_id")
        for _ in range(30):
            time.sleep(2)
            st2, d2 = _call("GET", f"/v3/chat/messages/retrieve?chat_id={chat_id}&conversation_id=" + (d.get("data", {}).get("conversation_id") or ""))
            if d2.get("code") == 0:
                msgs = d2.get("data", [])
                answers = [m["content"] for m in msgs if m.get("role") == "assistant" and m.get("content")]
                if answers:
                    return True, answers[-1]
                if any(m.get("type") == "function_call" for m in msgs):
                    continue
                if msgs and msgs[-1].get("role") == "assistant":
                    return True, msgs[-1].get("content", "（空回复）")
        return False, "Coze 任务超时（120s 内未完成）"
    if d.get("code") == 4015:
        return False, "Coze Bot 未发布到「Agent As API」渠道，请在 coze.cn 控制台发布后重试"
    return False, f"Coze 调用失败 code={d.get('code')} msg={d.get('msg')}"


def main():
    args = sys.argv[1:]
    if args and args[0] == "--check":
        sys.exit(0 if check() else 1)
    if not args:
        print("用法：python coze_gateway.py \"任务\" | python coze_gateway.py --check")
        return
    task = " ".join(args)
    ok, resp = run(task)
    print(resp[:1500] if ok else "⚠️ " + resp[:300])


if __name__ == "__main__":
    main()
