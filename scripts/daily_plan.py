# -*- coding: utf-8 -*-
"""
daily_plan.py — V13 波次2 每日复习队列生成（早报/晚间复盘数据源）
从飞书读卡 + 流水派生 → 用 study_planner 规划今日清单 → 输出文本 + 可选写回
用法:
  python daily_plan.py [--date 2026-09-09] [--quota 3] [--write] 
"""
import sys, io, json, argparse
from datetime import date, datetime
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService
import review_engine as eng
import study_planner as sp


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--quota', type=int, default=3)
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()

    c = FeishuClient()
    svc = ReviewService(c)
    # 1) 先派生全部卡（含初始态）
    res = svc.derive_and_apply(rebuild_all=True, dry_run=True)
    # 2) 读卡全量（含前置依赖/场景/错因）
    cards_raw = c.read_records(TABLES['学习卡片表'], page_size=500)
    cards, by_id = [], {}
    for r in cards_raw:
        f = r.get('fields', {})
        cid = r['record_id']
        st = plain(f.get('卡片状态')) or 'NOT_STARTED'
        # 前置依赖解析：学号引用 "rec_xxx"
        dep = plain(f.get('前置依赖'))
        dep_state = None
        if dep and dep.startswith('rec'):
            try:
                dep_rec = c.get_record(TABLES['学习卡片表'], dep)
                dep_state = plain(dep_rec['fields'].get('卡片状态')) or 'NOT_STARTED'
            except Exception:
                dep_state = None
        card = {'card_id': cid, '状态': st,
                '下次复习日期': f.get('下次复习日期'),
                '创建日期': f.get('创建日期'),
                '前置依赖': dep, '依赖状态': dep_state,
                '科目': plain(f.get('科目')) or '',
                '标题': plain(f.get('卡片问题正面')) or ''}
        cards.append(card)
        by_id[cid] = card
    # 3) 规划今日
    plan = sp.daily_plan(cards, today, quota=a.quota)
    # 4) 输出
    print('=== 今日复习队列 %s ===' % today.isoformat())
    print('到期 %d 张 / 新卡 %d 张 / 前置过滤 %d 张 / 合计 %d 张'
          % (len(plan['due']), len(plan['new']), len(plan['skipped_prereq']), plan['total']))
    if plan['note']:
        print('提示: %s' % plan['note'])
    for cid in plan['due']:
        print('  [到期] %s' % (by_id[cid]['标题'] or cid))
    for cid in plan['new']:
        print('  [新卡] %s' % (by_id[cid]['标题'] or cid))
    if plan['skipped_prereq']:
        print('  前置未就绪(不排): %s' % ', '.join(
            by_id[c]['标题'][:12] or c for c in plan['skipped_prereq']))
    # 5) 可选写回待办（占位：可接任务表）
    if a.write:
        print('\n(write 模式已启用——当前仅输出，写回任务表接入波次2后续)')
    print('DAILY_PLAN_DONE')


if __name__ == '__main__':
    main()
