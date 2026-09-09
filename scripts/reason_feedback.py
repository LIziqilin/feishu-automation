# -*- coding: utf-8 -*-
"""
reason_feedback.py — V13 波次2 错因回路（写回飞书 + 周复盘聚合）
点"不会"时非阻断选填错因：没理解 / 遗忘 / 卡面差
用法:
  python reason_feedback.py --card recXXX --reason 遗忘          # 写回该卡错因字段
  python reason_feedback.py --weekly                             # 周复盘：按错因聚合分布
"""
import sys, io, argparse
from datetime import date
from collections import Counter
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
import study_planner as sp


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--card', default=None)
    ap.add_argument('--reason', default=None)
    ap.add_argument('--weekly', action='store_true')
    a = ap.parse_args()
    c = FeishuClient()

    if a.weekly:
        cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                               field_names=['卡片问题正面', '错因'])
        agg = Counter()
        rows = []
        for r in cards:
            f = r.get('fields', {})
            reason = plain(f.get('错因'))
            if reason:
                agg[reason] += 1
                rows.append((str(plain(f.get('卡片问题正面')))[:14], reason))
        print('=== 本周错因分布 ===')
        for reason, n in agg.most_common():
            print('  %s: %d 张' % (reason, n))
        if rows:
            print('\n明细:')
            for t, reason in rows:
                print('  [%s] %s' % (reason, t))
        else:
            print('（本周暂无错因记录）')
        print('REASON_WEEKLY_DONE')
        return 0

    if not a.card or not a.reason:
        print('需要 --card 与 --reason（%s 之一）' % '/'.join(sp.REASON_OPTIONS))
        return 2
    ok, msg = sp.fill_reason_feedback('不会', a.reason)
    if not ok:
        print('参数错误: %s' % msg)
        return 2
    c.update_record(TABLES['学习卡片表'], a.card, {'错因': a.reason})
    print('已写回卡 %s 错因=%s' % (a.card, a.reason))
    print('REASON_FEEDBACK_DONE')


if __name__ == '__main__':
    main()
