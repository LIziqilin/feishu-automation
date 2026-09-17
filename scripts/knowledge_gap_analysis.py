#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""知识缺口智能推荐脚本（V15新增）
分析各领域卡片数量和掌握度，自动发现知识缺口并生成推荐
"""
import datetime
import json
import os
import urllib.request
import urllib.error
from collections import defaultdict

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
CHAT_ID = 'oc_1fe154e172ab04622b7ffa810ac172bc'
LEARNING_TABLE = 'tblpLvxyYpDJgF92'
REVIEW_FLOW_TABLE = 'tblbznzCSpPhSz93'

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


def get_records(token, table_id, limit=200):
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{table_id}/records?page_size={limit}"
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
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
        print(f"  报告发送失败: {e}")
        return False


def main():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"=== 知识缺口智能推荐 {now_str} ===")

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
    print(f"📚 共 {len(cards)} 张卡片")

    # 按领域统计
    domain_count = defaultdict(int)
    domain_掌握度 = defaultdict(list)
    
    for card in cards:
        fields = card.get("fields", {})
        # 获取领域（分类字段）
        domain = fields.get("分类", "未分类")
        if isinstance(domain, list):
            domain = domain[0].get("text", "未分类") if domain else "未分类"
        elif isinstance(domain, dict):
            domain = domain.get("text", "未分类")
        
        # 获取掌握度
        mastery = fields.get("掌握度M", 0)
        if isinstance(mastery, (int, float)):
            domain_掌握度[domain].append(mastery)
        else:
            domain_掌握度[domain].append(2)  # 默认中等
        
        domain_count[domain] += 1

    # 生成报告
    report = f"📊 知识缺口智能推荐\n时间：{now_str}\n\n"
    report += "📚 各领域卡片分布：\n"
    
    # 按数量排序
    sorted_domains = sorted(domain_count.items(), key=lambda x: x[1], reverse=True)
    for domain, count in sorted_domains:
        avg_mastery = sum(domain_掌握度[domain]) / len(domain_掌握度[domain]) if domain_掌握度[domain] else 0
        report += f"  {domain}: {count}张卡片，平均掌握度{avg_mastery:.1f}\n"

    # 识别缺口
    report += "\n⚠️ 知识缺口分析：\n"
    
    total_cards = len(cards)
    weak_domains = []
    sparse_domains = []
    
    for domain, count in sorted_domains:
        avg_mastery = sum(domain_掌握度[domain]) / len(domain_掌握度[domain]) if domain_掌握度[domain] else 0
        
        # 掌握度低（<3）的薄弱领域
        if avg_mastery < 3.0:
            weak_domains.append((domain, avg_mastery, count))
        
        # 卡片数少（<3张）的稀疏领域
        if count < 3:
            sparse_domains.append((domain, count))

    if weak_domains:
        report += "\n🔴 薄弱领域（掌握度低）：\n"
        for domain, mastery, count in weak_domains:
            report += f"  - {domain}: 掌握度{mastery:.1f}（{count}张卡片）\n"
            report += f"    建议：增加复习频率，重点巩固\n"
    else:
        report += "  ✅ 无薄弱领域\n"

    if sparse_domains:
        report += "\n🟡 稀疏领域（卡片少）：\n"
        for domain, count in sparse_domains:
            report += f"  - {domain}: 仅{count}张卡片\n"
            report += f"    建议：补充该领域知识点\n"
    else:
        report += "  ✅ 无稀疏领域\n"

    # 总体建议
    report += "\n💡 总体建议：\n"
    if len(weak_domains) > 2:
        report += "  - 薄弱领域较多，建议本周重点复习薄弱领域\n"
    if len(sparse_domains) > 2:
        report += "  - 稀疏领域较多，建议补充知识卡片\n"
    report += "  - 保持每周学习节奏，逐步完善知识体系\n"

    print(report)

    # 发送报告
    if send_report(token, report):
        print("\n✅ 知识缺口报告已发送到飞书群")
    else:
        print("\n❌ 报告发送失败")

    print(f"\n=== 分析完成 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ===")
    return 0


if __name__ == "__main__":
    exit(main())
