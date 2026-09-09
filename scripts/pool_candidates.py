# -*- coding: utf-8 -*-
"""
pool_candidates.py — V13 波次2 活跃池人工标记候选清单（池化阶段二前置）
阶段一规则（方案§7）：活跃池候选 = 人工高价值 ∪ 被关联(学习卡来源知识ID引用) ∪ 近90天创建
输出按主题分组，标记后用户在飞书改「知识池」字段为「活跃池」（≤100/主题≤30）
用法: python pool_candidates.py [--json] [--max 100]
"""
import sys, io, argparse, json
from datetime import datetime, timezone, timedelta
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
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
    ap.add_argument('--max', type=int, default=100)
    a = ap.parse_args()
    c = FeishuClient()
    now = datetime.now(CST)
    # 1) 被学习卡引用的来源知识ID
    cards = c.read_records(TABLES['学习卡片表'], page_size=500, field_names=['来源知识ID'])
    ref_ids = set()
    for r in cards:
        v = plain(r.get('fields', {}).get('来源知识ID'))
        if v:
            for part in str(v).replace('，', ',').split(','):
                part = part.strip()
                if part:
                    ref_ids.add(part)
    # 2) 知识索引全量
    idx = c.read_records(TABLES['知识索引表'], page_size=500,
                         field_names=['标题', '科目', '创建日期', 'last_recalled_at', '知识池'])
    cands = []
    for r in idx:
        f = r.get('fields', {})
        rid = r['record_id']
        title = str(plain(f.get('标题')) or rid)[:24]
        subj = plain(f.get('科目')) or '未分类'
        created = f.get('创建日期')
        recalled = f.get('last_recalled_at')
        pool = plain(f.get('知识池')) or ''
        reasons = []
        if rid in ref_ids:
            reasons.append('被学习卡引用')
        if created:
            dt = datetime.fromtimestamp(created / 1000, CST)
            if (now - dt).days <= 90:
                reasons.append('近90天创建')
        if recalled:
            reasons.append('有召回')
        if not reasons:
            continue
        cands.append({'record_id': rid, '标题': title, '科目': subj,
                      '理由': '、'.join(reasons), '知识池': pool})
    # 按科目分组
    by_subj = {}
    for cd in cands:
        by_subj.setdefault(cd['科目'], []).append(cd)
    total = len(cands)
    print('=== 活跃池人工标记候选（共 %d 条，上限 %d） ===' % (total, a.max))
    for subj, items in sorted(by_subj.items(), key=lambda x: -len(x[1])):
        print('\n[%s] %d 条' % (subj, len(items)))
        for it in items[:20]:
            print('  %s %s（%s）' % (it['record_id'], it['标题'], it['理由']))
        if len(items) > 20:
            print('  …共 %d 条' % len(items))
    print('\n标记方法：飞书知识索引表 → 把候选记录「知识池」改为「活跃池」（≤%d/主题≤30）' % a.max)
    if a.json:
        print(json.dumps({'total': total, 'candidates': cands}, ensure_ascii=False, indent=2))
    print('POOL_CANDIDATES_DONE')


if __name__ == '__main__':
    main()
