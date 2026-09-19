#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""全链路健康监控脚本（V15增强版）
检查各项服务状态，异常时写入系统健康表 + 飞书群告警
"""
import datetime
import json
import os
import time
import urllib.request
import urllib.error

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
HEALTH_TABLE = 'tblxJMndPNtZ7XyG'
CHAT_ID = 'oc_1fe154e172ab04622b7ffa810ac172bc'

ENV_CANDIDATES = [
    r"C:\Users\Administrator\AppData\Local\hermes\profiles\agent6_scheduler\scripts\feishu_insight_link.env",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "feishu_insight_link.env"),
]


def load_secret(key):
    v = os.environ.get(key)
    if v:
        return v
    for p in ENV_CANDIDATES:
        try:
            for line in open(p, encoding="utf-8-sig"):
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, _, val = line.partition("=")
                    if k.strip() == key:
                        return val.strip()
        except Exception:
            continue
    return ""


def get_token(app_id, app_secret):
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def check_service(name, url, timeout=5, retries=3, backoff=2.0):
    """检查服务是否正常（带重试，避免瞬时抖动误报宕机）。
    2026-09-16 加固：AnythingLLM 为 Electron 桌面应用，存在秒级 flapping；
    retries 2→3、backoff 1.0→2.0，使 <14s 的瞬时抖动不再误判为宕机。"""
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True, "HTTP 404 (服务运行中)"
            last = f"HTTP {e.code}"
        except Exception as e:
            last = str(e)[:100]
        if attempt < retries:
            time.sleep(backoff)
    return False, last or "unknown"


def write_health_record(fields):
    """写入系统健康表"""
    app_id = load_secret("FEISHU_APP_ID")
    app_secret = load_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        return False, "no app credentials"
    tr = get_token(app_id, app_secret)
    if tr.get("code") != 0:
        return False, "token_fail"
    token = tr["tenant_access_token"]
    url = "https://open.feishu.cn/open-apis/bitable/v1/apps/%s/tables/%s/records" % (BASE, HEALTH_TABLE)
    req = urllib.request.Request(
        url,
        data=json.dumps({"fields": fields}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return True, "ok"
        return False, f"code_{resp.get('code')}"
    except Exception as e:
        return False, str(e)[:100]


def send_alert_alert(token, alert_text):
    """发送飞书群告警消息"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    content = json.dumps({"text": alert_text})
    body = {
        "receive_id": CHAT_ID,
        "msg_type": "text",
        "content": content
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return True
        return False
    except Exception as e:
        print(f"  告警发送失败: {e}")
        return False


def main():
    now_ms = int(datetime.datetime.now().timestamp() * 1000)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    services = [
        ("Ollama本地模型", "http://localhost:11434/api/tags"),
        ("AnythingLLM知识库", "http://localhost:3001/"),
        ("飞书API连通性", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"),
    ]

    results = []
    all_ok = True
    failed_services = []

    for name, url in services:
        ok, msg = check_service(name, url)
        status = "正常" if ok else "异常"
        if not ok:
            all_ok = False
            failed_services.append(f"{name}({msg})")
        results.append({
            "检查项": f"服务健康-{name}",
            "实际状态": status,
            "最近检查时间": now_ms,
            "处理状态": status,
            "类型": "服务监控",
            # V41增强（2026-09-17）：补充组件健康度/系统健康评分——系统监控中心页面按此 Avg 渲染，
            # 缺值会导致页面显示 0% / 0.0/5.0。正常=100/5.0，异常=40/1.5（触发告警可视）。
            "组件健康度": 100 if ok else 40,
            "系统健康评分": 5.0 if ok else 1.5,
        })
        print(f"[{status}] {name}: {msg}")

    # 写入每条健康记录
    for fields in results:
        ok, note = write_health_record(fields)
        if ok:
            print(f"✅ 健康记录已写入: {fields['检查项']}")
        else:
            print(f"❌ 健康记录写入失败: {fields['检查项']} - {note}")

    # 异常告警到飞书群
    if not all_ok:
        app_id = load_secret("FEISHU_APP_ID")
        app_secret = load_secret("FEISHU_APP_SECRET")
        if app_id and app_secret:
            tr = get_token(app_id, app_secret)
            if tr.get("code") == 0:
                token = tr["tenant_access_token"]
                alert_text = (
                    f"⚠️ 系统健康告警\n"
                    f"时间：{now_str}\n"
                    f"异常服务：{', '.join(failed_services)}\n"
                    f"请及时检查！"
                )
                feishu_ok = send_alert_alert(token, alert_text)
                print(("✅ 告警已发送到飞书群" if feishu_ok else "❌ 飞书告警失败"))
                # 互为备用：无论飞书成功与否，同步推送企业微信群（飞书挂了企微兜底）
                try:
                    import sys as _s
                    _sd = os.path.dirname(os.path.abspath(__file__))
                    if _sd not in _s.path:
                        _s.path.insert(0, _sd)
                    import wecom_push
                    wok, wmsg = wecom_push.send_text(alert_text)
                    print(("✅ 告警已同步到企业微信" if wok else f"⚠️ 企业微信推送:{wmsg}"))
                except Exception as e:
                    print(f"⚠️ 企业微信推送异常: {e}")

    print(f"\n{'✅ 所有服务正常' if all_ok else '⚠️ 发现异常服务'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    exit(main())
