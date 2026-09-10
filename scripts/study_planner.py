# -*- coding: utf-8 -*-
"""
study_planner.py — V13 波次2 学习侧增强（超级学习/教育专家定稿）
纯函数规划器（无 IO 依赖，可单测）+ 飞书 IO 封装：

1) 每日队列规划 daily_plan：
   - 到期卡优先（next_due<=today，含模糊次日重排）
   - 新卡（NOT_STARTED）补足到日配额：每日<=2 张
   - 前置依赖过滤：B 的前置依赖 A 未达 LEARNING 时，B 不排入今日
   - 不足配额按实数推送，不硬凑
2) 错因回路：点"不会"时非阻断三选一（没理解/遗忘/卡面差），周复盘聚合
3) 应用场景两段式：REVIEWING 时提示填写（验收>=50%），MASTERED 毕业必需
4) 目标-知识域覆盖矩阵：8-12 冲刺知识域 × 现有卡/MASTERED/缺口
"""
from datetime import date, datetime, timedelta

NOT_STARTED, LEARNING, REVIEWING, MASTERED = \
    'NOT_STARTED', 'LEARNING', 'REVIEWING', 'MASTERED'
DAILY_QUOTA = 3       # 每日总卡数（基础版2/专业版3，此处取3；调用方可传）
NEW_CARD_CAP = 2      # 新卡每日<=2

REASON_OPTIONS = ('没理解', '遗忘', '卡面差')
# 引用引擎档位（避免 import 环）
LEVEL_GAP_DEFAULT = {0: 1, 1: 2, 2: 4, 3: 7, 4: 15, 5: 30, 6: 60, 7: 120, 8: 180, 9: 365}


def _d(v):
    if isinstance(v, date):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000).date()
    if isinstance(v, str):
        return datetime.strptime(v[:10], '%Y-%m-%d').date()
    raise ValueError('bad date %r' % (v,))


def daily_plan(cards, today, quota=DAILY_QUOTA, new_cap=NEW_CARD_CAP):
    """cards: [{'card_id','状态','下次复习日期','前置依赖','依赖状态':LEARNING|None,'创建日期'}]
    返回 {'due':[...], 'new':[...], 'skipped_prereq':[...], 'total':N, 'note':str}
    due=到期卡id列表；new=新卡id列表；skipped_prereq=因前置依赖未达被过滤的到期卡。"""
    today = _d(today)
    due, new, skipped = [], [], []
    for c in cards:
        st = c.get('状态')
        if st == NOT_STARTED:
            new.append(c['card_id'])
            continue
        if st in (LEARNING, REVIEWING, MASTERED):
            nd = c.get('下次复习日期')
            if nd and _d(nd) <= today:
                # 前置依赖过滤：依赖卡未达 LEARNING
                dep_state = c.get('依赖状态')
                if dep_state and dep_state != LEARNING:
                    skipped.append(c['card_id'])
                    continue
                due.append((c['card_id'], nd))
    # 到期卡按到期先后排序（最久未复习优先）
    due.sort(key=lambda x: _d(x[1]))
    due = [cid for cid, _ in due]
    # 新卡截断：每日<=new_cap，且总数不超过配额剩余
    remaining = max(0, quota - len(due))
    new_take = new[:min(new_cap, remaining)]
    # 到期卡超配额：今日取前 quota 张，剩余顺延（迁移期历史堆积分多日消化）
    over_quota = len(due) > quota
    if over_quota:
        due = due[:quota]
        new_take = []
    total = len(due) + len(new_take)
    note_parts = []
    if skipped:
        note_parts.append('已过滤 %d 张前置依赖未就绪的到期卡' % len(skipped))
    if over_quota:
        note_parts.append('到期卡超配额，今日取前 %d 张（按到期先后），其余顺延' % quota)
    if total < quota:
        note_parts.append('不足 %d 张，按实数推送不硬凑' % (quota - total))
    note = '；'.join(note_parts)
    return {'due': due, 'new': new_take, 'skipped_prereq': skipped,
            'total': total, 'note': note}


def fill_reason_feedback(result, reason=None):
    """错因回路：'不会'时返回可填的错因选项；校验 reason 合法。返回 (ok, msg)。"""
    if result != '不会':
        return True, '非"不会"结果无需错因'
    if reason is None:
        return False, '请从 %s 中选择错因' % '/'.join(REASON_OPTIONS)
    if reason not in REASON_OPTIONS:
        return False, '错因必须是 %s 之一' % '/'.join(REASON_OPTIONS)
    return True, 'ok'


def scene_prompt(status, has_output, scene_filled):
    """应用场景两段式：
       REVIEWING 且有场景 → 不需提示（达标）；REVIEWING 无场景 → 提示（非阻断）
       MASTERED 毕业前无输出 → 阻断提示（必须三选一）。"""
    if status == REVIEWING:
        if scene_filled:
            return 'ok', ''
        return 'prompt', '已进入巩固期：填一句"我能用在哪"，更不易忘'
    if status == MASTERED and not has_output and not scene_filled:
        return 'block', '毕业前必填：应用场景/费曼自检/实战留痕 三选一'
    return 'ok', ''


def coverage_matrix(cards, domains):
    """目标-知识域覆盖矩阵。
    cards: [{'card_id','科目','状态'}]；domains: [知识域名,...]
    返回 {domain: {'total':N,'mastered':N,'gap':bool}}"""
    dom_map = {}
    for d in domains:
        dom_map[d] = {'total': 0, 'mastered': 0, 'gap': False}
    for c in cards:
        subj = (c.get('科目') or '未分类').strip()
        for d in domains:
            if subj == d or d in subj:
                dom_map[d]['total'] += 1
                if c.get('状态') == MASTERED:
                    dom_map[d]['mastered'] += 1
                break
    for d, v in dom_map.items():
        v['gap'] = v['total'] == 0 or v['mastered'] / max(v['total'], 1) < 0.5
    return dom_map


def next_due_preview(plan, cards_by_id, today, gaps=LEVEL_GAP_DEFAULT):
    """输出明日/多日到期预览（供早报）。"""
    today = _d(today)
    out = {}
    for cid in plan['due'] + plan['new']:
        c = cards_by_id.get(cid, {})
        nd = c.get('下次复习日期')
        if not nd:
            continue
        out[cid] = (nd.isoformat() if isinstance(nd, date) else str(nd)[:10])
    return out
