#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""数据一致性自动校验脚本（V15新增）
每日凌晨自动运行，校验飞书表和Obsidian数据一致性
发现差异自动告警到飞书群
"""
import datetime
import json
import os
import urllib.request
import urllib.error

BASE = 'X8N1bvN3na99dFsyu0gcU8zTnHf'
CHAT_ID = 'oc_1fe154e172ab04622b7ffa810ac172bc'

# 表ID映射
TABLES = {
    "任务总表": "tblz3H4lV7PCrBrX",
    "学习卡片表": "tblpLvxyYpDJgF92",
    "洞察笔记表": "tblaqKBl87V9C0q1",
}

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


def count_records(token, table_id):
    """统计表记录数"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/{table_id}/records?page_size=1"
    req = urllib.request.Request(
        url,
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.load(r)
        if resp.get("code") == 0:
            return resp.get("data", {}).get("total", 0)
        return -1
    except Exception as e:
        print(f"  查询失败: {e}")
        return -1


def count_obsidian_files(folder):
    """统计Obsidian文件夹中的md文件数"""
    vault_path = r"D:\AI\finished Brain"
    target_path = os.path.join(vault_path, folder)
    if not os.path.exists(target_path):
        return -1
    count = 0
    for root, dirs, files in os.walk(target_path):
        for f in files:
            if f.endswith(".md"):
                count += 1
    return count


def send_alert(token, alert_text):
    """发送飞书群告警"""
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
        return resp.get("code") == 0
    except Exception as e:
        print(f"  告警发送失败: {e}")
        return False


def main():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 数据一致性校验开始 {now_str} ===")

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

    # 飞书表记录数
    print("\n📊 飞书表记录数：")
    feishu_counts = {}
    for name, table_id in TABLES.items():
        count = count_records(token, table_id)
        feishu_counts[name] = count
        print(f"  {name}: {count} 条")

    # Obsidian文件数
    print("\n📁 Obsidian文件数：")
    obsidian_map = {
        "任务总表": "待办任务",
        "学习卡片表": "学习卡片",
        "洞察笔记表": "洞察笔记",
    }
    obsidian_counts = {}
    for name, folder in obsidian_map.items():
        count = count_obsidian_files(folder)
        obsidian_counts[name] = count
        print(f"  {folder}: {count} 个文件")

    # 一致性对比
    print("\n🔍 一致性对比（仅活跃任务）：")
    differences = []
    
    # 任务总表：只对比活跃任务（待办+进行中）
    # 已完成、已取消的不同步到Obsidian，属于正常现象
    f_task_active = 0  # 飞书活跃任务数
    o_task_active = 0  # Obsidian活跃任务数
    
    # 从飞书读取任务，统计活跃数
    app_id = load_secret("FEISHU_APP_ID")
    app_secret = load_secret("FEISHU_APP_SECRET")
    tr = get_token(app_id, app_secret)
    token = tr["tenant_access_token"]
    
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE}/tables/tblz3H4lV7PCrBrX/records?page_size=100"
    records = None
    for _att in range(3):
        try:
            req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token})
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.load(r)
            records = resp.get("data", {}).get("items", [])
            break
        except Exception as e:
            print(f"  飞书任务读取重试 {_att+1}/3: {e}")
            import time as _t
            _t.sleep(1.5 * (_att + 1))
    if records is None:
        print("  飞书任务读取失败: 3次重试后仍超时")
        records = []
    for rec in records:
        status = rec.get("fields", {}).get("状态", "")
        if isinstance(status, list):
            status = status[0].get("text", "") if status else ""
        # P2-4修复：飞书活跃定义与Obsidian对称——排除已完成/已取消/已归档等终态，其余均算活跃
        _feishu_done = ("已完成", "已取消", "已归档", "完成", "done", "archive")
        if status and status not in _feishu_done:
            f_task_active += 1
    
    # Obsidian活跃任务数（递归扫描待办任务根目录，排除已完成/归档）
    vault_path = r"D:\AI\finished Brain"
    task_root = os.path.join(vault_path, "待办任务")
    _done_markers = ("完成", "已完成", "已取消", "归档", "done", "archive", "cancel")
    _done_dirs = ("已完成", "已取消", "已归档", "归档", "done", "archive")
    if os.path.exists(task_root):
        for root, dirs, files in os.walk(task_root):
            # D5修复：完成态以“目录名”优先判定（Obsidian将已完成放入 待办任务/已完成/ 子目录），
            # 文件名不含“完成”字样，仅查文件名会误判为活跃。
            rel = os.path.relpath(root, task_root)
            if any(m in rel for m in _done_dirs):
                continue
            for f in files:
                if not f.endswith(".md"):
                    continue
                low = f.lower()
                if any(m in low for m in _done_markers):
                    continue
                o_task_active += 1
    
    print(f"  任务总表（活跃）: 飞书{f_task_active} vs Obsidian{o_task_active}")
    if abs(f_task_active - o_task_active) <= 10:
        print(f"    ✅ 一致（差异在可接受范围内）")
    else:
        diff = f_task_active - o_task_active
        print(f"    ❌ 差异 {diff} 条")
        differences.append(f"任务总表活跃任务: 飞书{f_task_active} vs Obsidian{o_task_active}")
    
    # 学习卡片和洞察笔记：单向校验（飞书为源，Obsidian 为沉淀/镜像子集）
    # 飞书多于 Obsidian = 正常（未沉淀/未同步到 Obsidian）；Obsidian 多于飞书 = 异常（脏文件）
    for name in ["学习卡片表", "洞察笔记表"]:
        f_count = feishu_counts.get(name, -1)
        o_count = obsidian_counts.get(name, -1)
        if f_count < 0 or o_count < 0:
            status = "⚠️ 无法校验"
        elif o_count > f_count + 2:
            status = f"❌ Obsidian 多出 {o_count - f_count} 条（疑似脏文件）"
            differences.append(f"{name}: 飞书{f_count} vs Obsidian{o_count}（Obsidian 多于飞书）")
        else:
            status = f"✅ 正常（飞书{f_count}，Obsidian{o_count}，飞书为源）"
        print(f"  {name}: {status}")

    # 告警
    if differences:
        alert_text = (
            f"⚠️ 数据一致性告警\n"
            f"时间：{now_str}\n"
            f"发现差异：\n"
            + "\n".join([f"  - {d}" for d in differences])
        )
        if send_alert(token, alert_text):
            print("\n✅ 告警已发送到飞书群")
        else:
            print("\n❌ 告警发送失败")
    else:
        print("\n✅ 数据一致性校验通过")

    print(f"\n=== 校验完成 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
    return 0 if not differences else 1


if __name__ == "__main__":
    exit(main())
