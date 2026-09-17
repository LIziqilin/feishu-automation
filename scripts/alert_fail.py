#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""alert_fail.py — V45 云端失败告警（GitHub Actions 专用，零依赖）
====================================================================
在 workflow 失败时向总控群发告警消息。仅使用标准库 urllib 直连飞书 API，
环境变量：LARK_APP_ID / LARK_APP_SECRET / CHAT_ID（云端 workflow 注入 secrets）。
本地测试：python alert_fail.py "消息内容"
"""
import os, sys, json, urllib.request, urllib.error
from datetime import datetime

APP_ID = os.environ.get("LARK_APP_ID", "")
APP_SECRET = os.environ.get("LARK_APP_SECRET", "")
CHAT_ID = os.environ.get("CHAT_ID", "oc_1fe154e172ab04622b7ffa810ac172bc")


def _token():
    body = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8", errors="replace"))
    if d.get("code") != 0:
        raise RuntimeError(f"token接口失败 code={d.get('code')} msg={d.get('msg')}")
    return d["tenant_access_token"]


def send(text):
    tok = _token()
    payload = json.dumps({
        "receive_id": CHAT_ID, "msg_type": "text",
        "content": json.dumps({"text": text}, ensure_ascii=False),
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + tok},
        method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.loads(r.read().decode("utf-8", errors="replace"))
    return res.get("code") == 0, json.dumps(res, ensure_ascii=False)[:200]


def main():
    msg = sys.argv[1] if len(sys.argv) > 1 else "GitHub Actions 任务失败，请登录 Actions 页查看日志"
    text = (f"🚨 云端任务失败告警\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{msg}\n"
            "→ GitHub Actions 页查看：https://github.com/LIziqilin/feishu-automation/actions")
    if not (APP_ID and APP_SECRET):
        print("缺少 LARK_APP_ID/LARK_APP_SECRET 环境变量（本地直测需注入）")
        return 2
    try:
        ok, resp = send(text)
        print(("告警发送 OK: " if ok else "告警发送失败: ") + resp[:160])
        return 0 if ok else 1
    except Exception as e:
        print("告警发送异常:", str(e)[:200])
        return 1


if __name__ == "__main__":
    sys.exit(main())
