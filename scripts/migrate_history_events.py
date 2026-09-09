# -*- coding: utf-8 -*-
"""
migrate_history_events.py — V13 波次2 历史复习迁移事件（事件溯源口径统一）
背景：波次0把8张有复习痕迹的卡标为LEARNING，但复习流水表为空（V11旧字段有
      "复习次数/上次复习日期"真实历史，未纳入事件流）。事件溯源下派生以流水为唯一真相，
      导致旧"下次复习日期"残留、队列误判。
方案：把历史事实以「迁移事件」纳入流水（来源=历史迁移，不伪造新复习）：
      - 有"上次复习日期"的卡 → 1条事件(会, 上次复习日期)
      - 只有"复习次数"的卡 → 1条事件(会, 创建日期) 保守处理
      - 完成后 --rebuild-all 派生，旧"下次复习日期"由派生覆盖
用法: python migrate_history_events.py [--dry-run] [--apply]
"""
import sys, io, argparse
from datetime import datetime, timezone, timedelta
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService, make_event_id
import review_engine as eng

CST = timezone(timedelta(hours=8))


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    c = FeishuClient()
    svc = ReviewService(c)

    cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                           field_names=['卡片问题正面', '复习次数', '上次复习日期', '创建日期', '卡片状态'])
    # 已有流水的 event_id（防重复迁移）
    existing = set()
    for r in c.read_records(TABLES['复习流水表'], page_size=500, field_names=['event_id']):
        e = plain(r.get('fields', {}).get('event_id'))
        if e:
            existing.add(e)

    plan = []
    for r in cards:
        f = r.get('fields', {})
        rid = r['record_id']
        rev = plain(f.get('复习次数'))
        try:
            revn = int(float(rev)) if rev not in (None, '') else 0
        except Exception:
            revn = 0
        if revn < 1:
            continue
        lr = f.get('上次复习日期')
        cr = f.get('创建日期')
        day_ms = lr or cr or None
        if not day_ms:
            continue
        day = datetime.fromtimestamp(day_ms / 1000, CST).date().isoformat()
        eid = make_event_id(rid, eng.KNOWN, day_ms)
        if eid in existing:
            continue
        plan.append({'card_id': rid, 'day': day, 'event_id': eid,
                     'title': str(f.get('卡片问题正面'))[:18]})
    print('待迁移历史事件 %d 条（有复习次数但未入流水）:' % len(plan))
    for p in plan:
        print('  %s %s -> %s' % (p['day'], p['title'], p['card_id']))
    if a.dry_run or not a.apply:
        print('\n[dry-run] 未写库。--apply 将写入流水并 --rebuild-all 派生')
        return 0
    # 写入迁移事件
    rows = []
    for p in plan:
        ms = int(datetime.fromisoformat(p['day']).timestamp() * 1000)
        rows.append({'fields': {
            '卡片ID': p['card_id'], '卡片标题': p['title'], '结果': eng.KNOWN,
            '客户端时间戳': ms, '自然日': p['day'], '来源': '历史迁移',
            'event_id': p['event_id']}})
    created = c.batch_create(TABLES['复习流水表'], rows)
    print('写入迁移事件 %d 条' % len(created))
    # 派生
    res = svc.derive_and_apply(rebuild_all=True)
    print('派生完成: 写回 %d / 跳过 %d' % (len(res['changed']), res['skipped']))
    print('MIGRATE_HISTORY_DONE')


if __name__ == '__main__':
    main()
