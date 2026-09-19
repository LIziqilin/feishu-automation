# -*- coding: utf-8 -*-
"""ask_cloud.py — GitHub Actions 云端问答：DeepSeek 回答 -> 推飞书总控群（零依赖标准库）"""
import os, json, urllib.request

Q = os.environ.get("Q", "").strip()
DS_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
APP_ID = os.environ.get("FEISHU_APP_ID", "")
APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
CHAT_ID = os.environ.get("CHAT_ID", "")


def post(url, body, headers=None):
    h = {"Content-Type": "application/json"}
    if headers: h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def ds_answer(q):
    body = {"model": "deepseek-chat", "messages": [
        {"role": "system", "content": "你是个人AI助理，简洁回答，150字内。"},
        {"role": "user", "content": q}], "max_tokens": 400, "temperature": 0.5}
    d = post("https://api.deepseek.com/v1/chat/completions", body,
             {"Authorization": f"Bearer {DS_KEY}"})
    return d["choices"][0]["message"]["content"].strip()


def feishu_token():
    d = post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
             {"app_id": APP_ID, "app_secret": APP_SECRET})
    return d["tenant_access_token"]


def send_group(text):
    tok = feishu_token()
    body = {"receive_id": CHAT_ID, "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False)}
    d = post("https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
             body, {"Authorization": f"Bearer {tok}"})
    return d.get("code", -1)


if __name__ == "__main__":
    print("Q:", Q)
    ans = ds_answer(Q)
    print("A:", ans)
    code = send_group(f"☁️ 云端问答（关机可用）\n问：{Q}\n答：{ans}")
    print("飞书推送 code:", code, "=0 成功")
