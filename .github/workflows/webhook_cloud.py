# -*- coding: utf-8 -*-
"""webhook_cloud.py — GitHub Actions 云端事件：推飞书总控群（零依赖标准库）"""
import os, json, urllib.request

APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
TITLE = os.environ.get("TITLE", "云端事件")
TEXT = os.environ.get("TEXT", "")


def post(url, body, headers=None):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


tok = post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
           {"app_id": APP_ID, "app_secret": APP_SECRET})["tenant_access_token"]
body = {"receive_id": CHAT_ID, "msg_type": "text",
        "content": json.dumps({"text": f"🔔 {TITLE}\n{TEXT}"}, ensure_ascii=False)}
d = post("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
         body, {"Authorization": f"Bearer {tok}"})
print("飞书推送 code:", d.get("code", -1))
