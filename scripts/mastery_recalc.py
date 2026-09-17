#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mastery_recalc.py —— 掌握度M重算（修复 D1：掌握度不累积）

问题：复习/费曼流程写入了「复习次数」「费曼打分_AI」「连续正确次数」，
但全系统没有任何代码把这三个信号翻译成「掌握度M」，导致字段长期冻结在 0/1，
复习形同虚设、个性化推荐与掌握率失真。

方案：透明、可回滚的重算。
  掌握度M = clamp(
      0.25*min(复习次数,8)/8*5
    + 0.45*费曼打分_AI/5*5
    + 0.30*min(连续正确次数,4)/4*5 , 0, 5)
  即：复习次数(25%) + 费曼验证(45%) + 连续正确(30%) 加权，满分5。
  状态为 MASTERED 时直接给 5；NEW/未开始且0次复习给 0。

仅读取现有字段、写回掌握度M，不动其他字段；不删数据（R3）。
"""
import sys
sys.path.insert(0, '.')
import v15_features as v

CARD_TABLE = 'tblpLvxyYpDJgF92'


def _num(x, default=0.0):
    try:
        if x is None or x == '':
            return default
        return float(x)
    except Exception:
        return default


def calc_mastery(fields):
    status = fields.get('卡片状态')
    if isinstance(status, list):
        status = status[0].get('text', '') if status else ''
    if status == 'MASTERED':
        return 5.0
    rev = _num(fields.get('复习次数'))
    feynman = _num(fields.get('费曼打分_AI'))
    streak = _num(fields.get('连续正确次数'))
    if rev <= 0 and feynman <= 0 and streak <= 0:
        return 0.0
    m = (0.25 * min(rev, 8) / 8 * 5
         + 0.45 * min(feynman, 5) / 5 * 5
         + 0.30 * min(streak, 4) / 4 * 5)
    return round(min(5.0, max(0.0, m)), 2)


def main():
    cards = v.list_records(CARD_TABLE)
    print(f'待重算卡片: {len(cards)}张')
    updated = 0
    total_m = 0.0
    for c in cards:
        f = c['fields']
        new_m = calc_mastery(f)
        old_m = _num(f.get('掌握度M'))
        total_m += new_m
        # 仅在变化>0.01时写回，减少API调用
        if abs(new_m - old_m) > 0.01:
            v.update_record(CARD_TABLE, c['record_id'], {'掌握度M': new_m})
            updated += 1
            print(f"  {c['record_id'][:8]} 掌握度M {old_m} -> {new_m} (状态={f.get('卡片状态')}, 复习={_num(f.get('复习次数'))}, 费曼={_num(f.get('费曼打分_AI'))})")
    avg = total_m / len(cards) if cards else 0
    print(f'完成: 更新{updated}张, 平均掌握度M={avg:.2f}')
    graded = sum(1 for c in cards if calc_mastery(c['fields']) >= 3.5)
    print(f'毕业(>=3.5)卡片: {graded}/{len(cards)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
