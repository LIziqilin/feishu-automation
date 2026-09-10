# -*- coding: utf-8 -*-
"""
review_io.py — 复习事件写入 + 状态派生回写（IO 编排层；纯逻辑在 review_engine）
三条复习路径（按钮 / 群指令 / 定时兜底）全部经此模块，杜绝分叉：
  log_event()      向「复习流水表」只追加一条（event_id 幂等，绝不 update/delete 流水）
  derive_and_apply() 读全部流水 → review_engine 重算 → 派生快照写回学习卡（仅变化时写）
"""
import sys
from datetime import datetime, date, timedelta, timezone
sys.path.insert(0, r'D:\AI-Tools\shared')
from feishu_sdk import FeishuClient, TABLES
import review_engine as eng

CST = timezone(timedelta(hours=8))
CARD, FLOW = TABLES['学习卡片表'], TABLES['复习流水表']


def day_to_ms(d):
    """date → 东八区当日 0 点毫秒时间戳（飞书 DateTime 字段要求）。"""
    if d is None:
        return None
    if isinstance(d, datetime):
        d = d.date()
    dt = datetime(d.year, d.month, d.day, tzinfo=CST)
    return int(dt.timestamp() * 1000)


def _plain(v):
    if isinstance(v, list) and v:
        if isinstance(v[0], dict):
            return v[0].get('text') or v[0].get('value')
        return v[0]
    return v


def make_event_id(card_id, result, client_ts_ms):
    return '%s|%s|%s' % (card_id, result, client_ts_ms)


class ReviewService:
    def __init__(self, client=None):
        self.c = client or FeishuClient()
        self._seen_eids = None   # 会话内 event_id 幂等缓存，懒加载（避免每次答题全表读）

    def _all_eids(self, refresh=False):
        if self._seen_eids is None or refresh:
            self._seen_eids = set()
            for r in self.c.read_records(FLOW, page_size=500, field_names=['event_id']):
                eid = _plain(r.get('fields', {}).get('event_id'))
                if eid:
                    self._seen_eids.add(eid)
        return self._seen_eids

    # ---------- 1) 只追加流水（幂等） ----------
    def log_event(self, card_id, result, client_dt=None, source='按钮',
                  card_title='', event_id=None):
        """result: 会/不会/模糊。client_dt: datetime（客户端答题时间，默认现在）。
        返回 (record_id, duplicated)；相同 event_id 已存在则不重复插入。"""
        if result not in (eng.KNOWN, eng.UNKNOWN, eng.FUZZY):
            raise ValueError('结果必须是 会/不会/模糊，收到 %r' % result)
        client_dt = client_dt or datetime.now(CST)
        ts_ms = int(client_dt.timestamp() * 1000)
        eid = event_id or make_event_id(card_id, result, ts_ms)
        if eid in self._all_eids():      # 会话缓存查重，仅首次加载一次流水表
            return None, True
        fields = {
            '卡片ID': card_id,
            '卡片标题': card_title,
            '结果': result,
            '客户端时间戳': ts_ms,
            '自然日': client_dt.strftime('%Y-%m-%d'),
            '来源': source,
            'event_id': eid,
        }
        rec = self.c.create_record(FLOW, fields)
        self._all_eids().add(eid)
        return rec['record_id'], False

    def log_events_batch(self, items):
        """批量追加多条流水（一次 batch_create）。items: [{card_id,result,client_dt,source,card_title}]"""
        rows, eids = [], []
        for it in items:
            cdt = it.get('client_dt') or datetime.now(CST)
            ms = int(cdt.timestamp() * 1000)
            eid = it.get('event_id') or make_event_id(it['card_id'], it['result'], ms)
            if eid in self._all_eids():
                continue
            rows.append({'fields': {
                '卡片ID': it['card_id'], '卡片标题': it.get('card_title', ''),
                '结果': it['result'], '客户端时间戳': ms,
                '自然日': cdt.strftime('%Y-%m-%d'), '来源': it.get('source', '按钮'),
                'event_id': eid}})
            eids.append(eid)
        if not rows:
            return []
        created = self.c.batch_create(FLOW, rows)
        self._all_eids().update(eids)
        return created

    def _create_event_raw(self, card_id, result, client_dt, source, card_title):
        """免全表查重的直接追加（即时路径用；重复由会话缓存与派生 event_id 去重兜底）。"""
        ts_ms = int(client_dt.timestamp() * 1000)
        eid = make_event_id(card_id, result, ts_ms)
        if self._seen_eids is not None and eid in self._seen_eids:
            return None, True
        rec = self.c.create_record(FLOW, {
            '卡片ID': card_id, '卡片标题': card_title, '结果': result,
            '客户端时间戳': ts_ms, '自然日': client_dt.strftime('%Y-%m-%d'),
            '来源': source, 'event_id': eid})
        if self._seen_eids is not None:
            self._seen_eids.add(eid)
        return rec['record_id'], False

    # ---------- 1b) 用户感知路径：只落流水（1 次写，即时回执；派生在后台/兜底） ----------
    def record_answer(self, card_id, result, source='按钮', client_dt=None, card_title=''):
        """点一次 会/不会/模糊：只把事件追加进流水表即返回。用户感知耗时≈1次写（<10s达标）。"""
        if result not in (eng.KNOWN, eng.UNKNOWN, eng.FUZZY):
            raise ValueError('结果必须是 会/不会/模糊')
        client_dt = client_dt or datetime.now(CST)
        return self._create_event_raw(card_id, result, client_dt, source, card_title)

    def rederive_one(self, card_id):
        """后台/兜底：重算单卡并回写派生快照。"""
        events = self._flow_for(card_id)
        card = self.c.get_record(CARD, card_id)['fields']
        d = eng.derive(events, has_output=self._has_output(card))
        snap = {k: v for k, v in self._snapshot(d, event_count=len(events)).items() if v is not None}
        self.c.update_record(CARD, card_id, snap)
        return d.to_dict()

    def answer_one(self, card_id, result, source='按钮', client_dt=None, card_title=''):
        """同步全流程：写流水→重算→回写（需要立即看到状态时用；交互主路径建议 record_answer+异步派生）。"""
        client_dt = client_dt or datetime.now(CST)
        self._create_event_raw(card_id, result, client_dt, source, card_title)
        return self.rederive_one(card_id)

    def answer_async(self, card_id, result, source='按钮', client_dt=None, card_title=''):
        """写流水即返回，派生在后台线程完成（用户不等派生；最终一致由 09:07 兜底再保证）。"""
        import threading
        self.record_answer(card_id, result, source, client_dt, card_title)
        t = threading.Thread(target=self.rederive_one, args=(card_id,), daemon=True)
        t.start()
        return t

    def _flow_for(self, card_id):
        return self._events_from_rows(self.c.read_records(FLOW, page_size=500), card_id)

    @staticmethod
    def _events_from_rows(rows, only_card=None, dedup=True):
        seen, out = set(), []
        for r in rows:
            f = r.get('fields', {})
            cid = _plain(f.get('卡片ID'))
            if only_card and cid != only_card:
                continue
            eid = _plain(f.get('event_id'))
            if dedup and eid:
                if eid in seen:
                    continue
                seen.add(eid)
            ts = f.get('客户端时间戳')
            out.append({'day': _plain(f.get('自然日')), 'result': _plain(f.get('结果')),
                        'ts': datetime.fromtimestamp(ts/1000, CST) if isinstance(ts, (int, float)) else None})
        return out

    # ---------- 2) 读流水 → 重算 → 回写 ----------
    def _load_flow(self):
        rows = self.c.read_records(FLOW, page_size=500)
        grouped = {}
        seen = set()
        for r in rows:
            f = r.get('fields', {})
            cid = _plain(f.get('卡片ID'))
            eid = _plain(f.get('event_id'))
            if eid:                      # event_id 幂等去重，防网络重试重复计数
                if eid in seen:
                    continue
                seen.add(eid)
            evs = self._events_from_rows([r], dedup=False)
            if cid and evs:
                grouped.setdefault(cid, []).extend(evs)
        return grouped

    @staticmethod
    def _has_output(fields):
        scene = _plain(fields.get('应用场景'))
        feynman = str(_plain(fields.get('费曼自检')) or '')
        practice = fields.get('实战留痕')
        return bool(scene) or ('过' in feynman) or practice is True

    @staticmethod
    def _snapshot(d, event_count=None):
        return {
            '卡片状态': d.status,
            '连续正确次数': d.streak,
            '复习次数': event_count if event_count is not None else d.known_count,
            '正确去重计数': len(d.correct_days),
            '首次正确日期': day_to_ms(d.first_correct_day),
            '最近正确日期': day_to_ms(d.last_correct_day),
            '上次复习日期': day_to_ms(d.last_event_day),
            '下次复习日期': day_to_ms(d.next_due),
        }

    def derive_and_apply(self, rebuild_all=False, dry_run=False):
        flow = self._load_flow()
        cards = self.c.read_records(CARD, page_size=500)
        changed, skipped = [], []
        for r in cards:
            f = r.get('fields', {})
            rid = r['record_id']
            events = flow.get(rid, [])
            has_out = self._has_output(f)
            if events:
                d = eng.derive(events, has_output=has_out)
                snap = self._snapshot(d, event_count=len(events))
            elif rebuild_all:
                # 无流水卡：保守初始态，不伪造任何日期
                rev = _plain(f.get('复习次数'))
                try:
                    revn = int(float(rev)) if rev not in (None, '') else 0
                except Exception:
                    revn = 0
                snap = {'卡片状态': eng.LEARNING if revn >= 1 else eng.NOT_STARTED}
            else:
                continue
            snap = {k: v for k, v in snap.items() if v is not None}
            if self._same(f, snap):
                skipped.append(rid); continue
            changed.append({'record_id': rid, 'fields': snap})
        if changed and not dry_run:
            # 批量一次写回（替代逐条 update），把 N 次写往返压成 1 次
            for i in range(0, len(changed), 500):
                self.c.batch_update(CARD, changed[i:i+500])
        return {'changed': [(x['record_id'], x['fields']) for x in changed],
                'skipped': len(skipped),
                'cards_total': len(cards), 'flow_groups': len(flow)}

    @staticmethod
    def _same(cur, snap):
        """派生快照与现值一致则跳过写（减少写次数与自动化触发）。"""
        for k, v in snap.items():
            now = _plain(cur.get(k))
            if k.endswith('日期') and isinstance(now, (int, float)) and isinstance(v, (int, float)):
                if abs(now - v) > 60000:  # 允许1分钟误差
                    return False
                continue
            if now is None and v in ('', None):
                continue
            if str(now) != str(v):
                return False
        return True
