#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""每周自动分析学习数据脚本（V15新增）
每周日自动运行，分析本周学习数据，生成周报推送到飞书群
"""
import datetime
import json
import os
import urllib.request
import urllib.error

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
CHAT_ID = 'oc_1fe154e172ab04622b7ffa810ac172bc'
LEARNING_TABLE = 'tblpLvxyYpDJgF92'
FLOW_TABLE = 'tblbznzCSpPhSz93'

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


def get_records(token, table_id, limit=100):
    """获取表记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{table_id}/records?page_size={limit}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return resp.get("data", {}).get("items", [])
        return []
    except Exception as e:
        print(f"  查询失败: {e}")
        return []


def send_report(token, report_text):
    """发送周报到飞书群"""
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    content = json.dumps({"text": report_text})
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
        return resp.get("code") == 0
    except Exception as e:
        print(f"  周报发送失败: {e}")
        return False


def main():
    now = datetime.datetime.now()
    week_start = now - datetime.timedelta(days=7)
    now_str = now.strftime("%Y-%m-%d %H:%M")
    print(f"=== 每周学习数据分析 {now_str} ===")

    app_id = load_secret("FEISHU_APP_ID")
    app_secret = load_secret("FEISHU_APP_SECRET")
    if not app_id or not app_secret:
        print("❌ 无飞书凭证")
        return 1

    tr = get_token(app_id, app_secret)
    if tr.get("code") != 0:
        print("❌ Token获取失败")
        return 1
    token = tr["tenant_access_token"]

    # 获取学习卡片
    cards = get_records(token, LEARNING_TABLE, limit=100)
    total_cards = len(cards)
    print(f"📚 总卡片数：{total_cards}")

    # 获取复习流水
    flows = get_records(token, FLOW_TABLE, limit=200)
    total_flows = len(flows)
    print(f"📝 总答题数：{total_flows}")

    # 统计本周答题（简单统计，按结果分类）
    correct = sum(1 for f in flows if f.get("fields", {}).get("结果") == "会")
    wrong = sum(1 for f in flows if f.get("fields", {}).get("结果") == "不会")
    fuzzy = sum(1 for f in flows if f.get("fields", {}).get("结果") == "模糊")

    accuracy = (correct / total_flows * 100) if total_flows > 0 else 0

    print(f"  会：{correct}")
    print(f"  模糊：{fuzzy}")
    print(f"  不会：{wrong}")
    print(f"  正确率：{accuracy:.1f}%")

    # 生成周报
    report = (
        f"📊 每周学习周报\n"
        f"时间：{week_start.strftime('%m-%d')} ~ {now.strftime('%m-%d')}\n"
        f"\n"
        f"📚 学习数据：\n"
        f"  总卡片数：{total_cards}\n"
        f"  总答题数：{total_flows}\n"
        f"  正确率：{accuracy:.1f}%\n"
        f"\n"
        f"📈 答题分布：\n"
        f"  ✅ 会：{correct}（{correct/total_flows*100:.1f}%）\n"
        f"  🟡 模糊：{fuzzy}（{fuzzy/total_flows*100:.1f}%）\n"
        f"  ❌ 不会：{wrong}（{wrong/total_flows*100:.1f}%）\n"
        f"\n"
        f"💡 建议：\n"
    )

    if accuracy < 60:
        report += "  - 正确率偏低，建议增加复习频率\n"
    elif accuracy < 80:
        report += "  - 正确率良好，继续保持\n"
    else:
        report += "  - 正确率优秀，可尝试加快进度\n"

    if wrong > total_flows * 0.3:
        report += "  - 错题较多，建议加强错题本练习\n"

    # 发送周报
    if send_report(token, report):
        print("\n✅ 周报已发送到飞书群")
    else:
        print("\n❌ 周报发送失败")

    print(f"\n=== 分析完成 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    return 0


if __name__ == "__main__":
    exit(main())
