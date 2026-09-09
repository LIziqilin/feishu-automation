# -*- coding: utf-8 -*-
"""
learning_metrics.py — V13 波次2 学习侧周报数据源（同构漏斗三指标）
1) 素材处置率：知识索引表 近7天新增 且 已处置（转卡/升活跃/淘汰）占比
2) 来源知识ID 转化率：学习卡(带来源知识ID) / 全部学习卡；且按来源ID聚合到洞察/决策
3) 复习完成率：本周应复习 vs 实际复习（流水表）
用法: python learning_metrics.py [--json]
"""
import sys, io, argparse, json
from datetime import datetime, timezone, timedelta
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES

CST = timezone(timedelta(hours=8))


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    c = FeishuClient()
    now = datetime.now(CST)
    week_ago = int((now - timedelta(days=7)).timestamp() * 1000)

    # 1) 素材处置率
    idx = c.read_records(TABLES['知识索引表'], page_size=500,
                         field_names=['标题', '创建日期', '知识池', '状态'])
    new7 = [r for r in idx
            if r.get('fields', {}).get('创建日期')
            and int(r.get('fields', {})['创建日期']) >= week_ago]
    disposed = [r for r in new7
                if plain(r.get('fields', {}).get('知识池')) == '活跃池'
                or plain(r.get('fields', {}).get('状态')) in ('已处置', '转卡', '淘汰')]
    dispose_rate = len(disposed) * 100 / len(new7) if new7 else 100.0

    # 2) 来源知识ID 转化率
    cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                           field_names=['卡片问题正面', '来源知识ID', '卡片状态'])
    total_cards = len(cards)
    linked = [r for r in cards if plain(r.get('fields', {}).get('来源知识ID'))]
    link_rate = len(linked) * 100 / total_cards if total_cards else 0.0

    # 3) 复习完成率（本周流水）
    flow = c.read_records(TABLES['复习流水表'], page_size=500,
                          field_names=['客户端时间戳', '来源'])
    wk_start = week_ago
    wk_flow = [r for r in flow
               if r.get('fields', {}).get('客户端时间戳')
               and int(r.get('fields', {})['客户端时间戳']) >= wk_start]
    flow_cnt = len(wk_flow)
    # 本周应复习 ≈ 学习卡中非归档有状态卡数（简化口径）
    active_cards = [r for r in cards if plain(r.get('fields', {}).get('卡片状态')) in ('LEARNING', 'REVIEWING')]
    due_est = max(len(active_cards), 1) * 3  # 每人每日3张估算
    complete_rate = flow_cnt * 100 / due_est if due_est else 0.0

    metrics = {
        '素材7天处置率': {'新增': len(new7), '已处置': len(disposed), '率': round(dispose_rate, 1)},
        '来源知识ID转化率': {'学习卡总数': total_cards, '带来源ID': len(linked), '率': round(link_rate, 1)},
        '本周复习完成率': {'本周流水': flow_cnt, '估算应复习': due_est, '率': round(min(complete_rate, 100), 1)},
    }
    if a.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return
    print('=== 学习侧周报指标（同构漏斗三指标） ===')
    for k, v in metrics.items():
        print('%-14s %s' % (k, v))
    print('LEARNING_METRICS_DONE')


if __name__ == '__main__':
    main()
