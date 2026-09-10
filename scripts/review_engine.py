# -*- coding: utf-8 -*-
"""
review_engine.py — 学习卡五态状态机纯引擎（V13 事件溯源核心，无任何 IO / 飞书依赖）
输入一张卡按时间排序的复习事件，输出可派生的全部学习状态。
设计铁律（V13 融合定稿）：
  * 状态可派生就不存储：本引擎是唯一真相，卡片表状态字段只是派生快照，可随时 --rebuild-all 重算
  * 同一自然日多条流水取【当日末条】（允许当天改判）
  * 升 REVIEWING 必须同时：累计正确>=3 且 跨>=3 个不同自然日 且 最长正确间隔>=3 天（防"一日精通"）
  * 升 MASTERED 必须轮次走完 120 档 且 具备毕业输出（应用场景/费曼/实战三选一）
  * 下行：不会→连对归零、档内退1档；REVIEWING 连错2次降 LEARNING；MASTERED 错1次降 REVIEWING
  * 模糊：不升不降，次日重排
  * 不自动归档：仅产出 180 天无反馈候选名单交周报人工确认，MASTERED 豁免
"""
from datetime import date, datetime, timedelta

KNOWN, UNKNOWN, FUZZY = '会', '不会', '模糊'
NOT_STARTED, LEARNING, REVIEWING, MASTERED, ARCHIVED = \
    'NOT_STARTED', 'LEARNING', 'REVIEWING', 'MASTERED', 'ARCHIVED'

# 档位 → 间隔天数；0-2 LEARNING，3-7 REVIEWING，8-9 MASTERED
LEVEL_GAP = {0: 1, 1: 2, 2: 4, 3: 7, 4: 15, 5: 30, 6: 60, 7: 120, 8: 180, 9: 365}


def status_of_level(level):
    if level is None:
        return NOT_STARTED
    if level <= 2:
        return LEARNING
    if level <= 7:
        return REVIEWING
    return MASTERED


def _to_day(v):
    """接受 date / datetime / 'YYYY-MM-DD' / 毫秒时间戳，统一成 date。"""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, (int, float)):
        # 毫秒时间戳
        return datetime.fromtimestamp(v / 1000).date()
    if isinstance(v, str):
        return datetime.strptime(v[:10], '%Y-%m-%d').date()
    raise ValueError('无法解析日期: %r' % (v,))


def collapse_events(events):
    """同一自然日多条事件取当日时间最晚一条。
    events: [{'result':会/不会/模糊, 'day':date|str|ts, 'ts':可选datetime排序键}]
    返回 [(date, result), ...] 按日升序。"""
    latest = {}
    for e in events:
        d = _to_day(e['day'])
        order = e.get('ts')
        if order is None:
            order = datetime.combine(d, datetime.min.time())
        if isinstance(order, (int, float)):
            order = datetime.fromtimestamp(order / 1000)
        if d not in latest or order >= latest[d][0]:
            latest[d] = (order, e['result'])
    return [(d, latest[d][1]) for d in sorted(latest)]


class Derived:
    def __init__(self):
        self.status = NOT_STARTED
        self.level = None
        self.streak = 0                 # 当前连续正确
        self.correct_days = set()       # 正确去重自然日
        self.first_correct_day = None
        self.last_correct_day = None
        self.last_event_day = None
        self.max_correct_gap = 0        # 相邻正确最长间隔（天）
        self.known_count = 0
        self.consec_unknown_review = 0
        self.next_due = None

    def to_dict(self):
        return {
            'status': self.status,
            'level': self.level,
            'streak': self.streak,
            'correct_day_count': len(self.correct_days),
            'first_correct_day': self.first_correct_day.isoformat() if self.first_correct_day else None,
            'last_correct_day': self.last_correct_day.isoformat() if self.last_correct_day else None,
            'last_event_day': self.last_event_day.isoformat() if self.last_event_day else None,
            'max_correct_gap': self.max_correct_gap,
            'known_count': self.known_count,
            'next_due': self.next_due.isoformat() if self.next_due else None,
        }


def derive(events, has_output=False, today=None):
    """从事件序列重算一张卡。has_output=是否已具备毕业输出（应用场景/费曼/实战任一）。"""
    daily = collapse_events(events)
    s = Derived()
    for day, result in daily:
        s.last_event_day = day
        if result == KNOWN:
            if s.level is None:
                s.level = 0
            else:
                target = s.level + 1
                # LEARNING 顶档(2) → REVIEWING(3) 的跨日/间隔门槛
                if s.level == 2:
                    new_gap = s.max_correct_gap
                    if s.last_correct_day is not None:
                        new_gap = max(new_gap, (day - s.last_correct_day).days)
                    n_days = len(s.correct_days | {day})
                    if not (s.known_count + 1 >= 3 and n_days >= 3 and new_gap >= 3):
                        target = 2  # 不满足间隔效应，停在 4 天档继续观察
                # REVIEWING 顶档(7) → MASTERED(8) 的毕业输出门槛
                if s.level == 7 and target == 8 and not has_output:
                    target = 7
                s.level = min(target, 9)
            s.streak += 1
            s.known_count += 1
            s.correct_days.add(day)
            s.consec_unknown_review = 0
            if s.first_correct_day is None:
                s.first_correct_day = day
            if s.last_correct_day is not None:
                s.max_correct_gap = max(s.max_correct_gap, (day - s.last_correct_day).days)
            s.last_correct_day = day
            s.next_due = day + timedelta(days=LEVEL_GAP[s.level])
        elif result == UNKNOWN:
            s.streak = 0
            if s.level is None:
                s.level = 0
            cur = status_of_level(s.level)
            if cur == MASTERED:
                s.level = 3                      # 错1次降 REVIEWING 7天档
                s.consec_unknown_review = 0
            elif cur == REVIEWING:
                s.consec_unknown_review += 1
                if s.consec_unknown_review >= 2:
                    s.level = 0                  # 连错2次降 LEARNING 1天档
                    s.consec_unknown_review = 0
                else:
                    s.level = max(3, s.level - 1)  # 档内退1档，不低于7天档
            else:
                s.level = max(0, s.level - 1)    # LEARNING 退1档，最低1天
            s.next_due = day + timedelta(days=LEVEL_GAP[s.level])
        elif result == FUZZY:
            if s.level is None:
                s.level = 0
            s.next_due = day + timedelta(days=1)   # 不升不降，次日重排
        else:
            raise ValueError('未知复习结果: %r' % (result,))
    s.status = status_of_level(s.level)
    return s


def archive_candidates(cards_states, today, inactive_days=180):
    """产出归档候选：仅 LEARNING/REVIEWING 且距最后事件>=180天；MASTERED 豁免；NOT_STARTED 不归档。
    cards_states: {card_id: Derived.to_dict()}；返回候选 id 列表。"""
    today = _to_day(today)
    out = []
    for cid, d in cards_states.items():
        if d['status'] not in (LEARNING, REVIEWING):
            continue
        led = d['last_event_day']
        if led is None:
            continue
        if (today - _to_day(led)).days >= inactive_days:
            out.append(cid)
    return out


def due_cards(cards_states, today):
    """返回 next_due <= today 的待复习 card_id 列表（NOT_STARTED/ARCHIVED 不排程）。"""
    today = _to_day(today)
    out = []
    for cid, d in cards_states.items():
        if d['status'] in (NOT_STARTED, ARCHIVED) or not d['next_due']:
            continue
        if _to_day(d['next_due']) <= today:
            out.append(cid)
    return out
