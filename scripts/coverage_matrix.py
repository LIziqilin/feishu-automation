# -*- coding: utf-8 -*-
"""
coverage_matrix.py — V13 波次2 目标-知识域覆盖矩阵（周报数据源）
读学习卡真实科目/状态 → 按冲刺知识域聚合 → 输出覆盖矩阵文本
用法: python coverage_matrix.py [--domains 考证,认知,酒店工程,财商,沟通] [--json]
"""
import sys, io, argparse, json
from datetime import date
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
import study_planner as sp

DEFAULT_DOMAINS = ['考证', '认知', '酒店工程', '财商', '沟通']


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--domains', default=','.join(DEFAULT_DOMAINS))
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    domains = [d.strip() for d in a.domains.split(',') if d.strip()]

    c = FeishuClient()
    cards_raw = c.read_records(TABLES['学习卡片表'], page_size=500,
                               field_names=['卡片问题正面', '科目', '卡片状态'])
    cards = []
    for r in cards_raw:
        f = r.get('fields', {})
        cards.append({'card_id': r['record_id'],
                      '科目': plain(f.get('科目')) or '未分类',
                      '状态': plain(f.get('卡片状态')) or 'NOT_STARTED',
                      '标题': str(plain(f.get('卡片问题正面')))[:16]})
    m = sp.coverage_matrix(cards, domains)
    if a.json:
        print(json.dumps({'date': date.today().isoformat(), 'matrix': m,
                          'cards': cards}, ensure_ascii=False, indent=2))
        return
    print('=== 目标-知识域覆盖矩阵 %s ===' % date.today().isoformat())
    print('%-10s %6s %8s  %s' % ('知识域', '总卡', '已掌握', '缺口'))
    for d in domains:
        v = m[d]
        flag = '⚠ 缺口' if v['gap'] else '✓'
        print('%-10s %6d %8d  %s' % (d, v['total'], v['mastered'], flag))
    gaps = [d for d in domains if m[d]['gap']]
    print('\n补卡优先级（最大缺口优先）: %s' % (' > '.join(gaps) if gaps else '无缺口'))
    print('COVERAGE_MATRIX_DONE')


if __name__ == '__main__':
    main()
