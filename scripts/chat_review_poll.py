# -*- coding: utf-8 -*-
"""
chat_review_poll.py — V13 波次2 群内文字指令复习闭环（P0 并行底座）
轮询群消息 → 解析"会/不会/模糊 N" → 映射今日队列 → 写流水 → 回执消息
- 增量游标 state/chat_poll_cursor.json（记录已处理消息create_time）
- 跳过应用自身消息（防死循环）
- event_id 幂等（重复轮询不重复写）
用法: python chat_review_poll.py [--chat oc_xxx] [--dry-run] [--once]
"""
import sys, io, os, json, argparse, time
from datetime import datetime, timezone, timedelta
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
import urllib.request
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService
import chat_command as cc
import study_planner as sp

CST = timezone(timedelta(hours=8))
STATE_FILE = r'D:\AI-Tools\shared\state\chat_poll_cursor.json'
DEFAULT_CHAT = 'oc_1fe154e172ab04622b7ffa810ac172bc'  # 个人总控群


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def load_cursor():
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            return json.load(f).get('last_ts', 0)
    except Exception:
        return 0


def save_cursor(ts):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({'last_ts': ts, 'updated': datetime.now(CST).isoformat()},
                  f, ensure_ascii=False, indent=2)


def fetch_messages(c, chat, cursor, limit=50):
    """拉群消息（游标之后），返回消息列表（按时间升序）。"""
    tok = c.get_token()
    url = ('https://open.feishu.cn/open-apis/im/v1/messages'
           '?container_id_type=chat&container_id=%s&page_size=%d'
           '&sort_type=ByCreateTimeAsc' % (chat, limit))
    if cursor:
        url += '&start_time=%d' % (cursor + 1)
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
    d = json.loads(urllib.request.urlopen(req, timeout=15).read())
    if d.get('code') != 0:
        print('拉消息失败 code=%s msg=%s' % (d.get('code'), d.get('msg')))
        return []
    return d.get('data', {}).get('items', []) or []


def send_text(c, chat, text):
    tok = c.get_token()
    url = 'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id'
    body = json.dumps({'receive_id': chat, 'msg_type': 'text',
                       'content': json.dumps({'text': text})}).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={'Authorization': 'Bearer ' + tok,
                                          'Content-Type': 'application/json'})
    d = json.loads(urllib.request.urlopen(req, timeout=10).read())
    return d.get('code') == 0


def build_queue(c, today):
    """复用 daily_plan 逻辑取今日队列。"""
    svc = ReviewService(c)
    svc.derive_and_apply(rebuild_all=True, dry_run=True)
    cards_raw = c.read_records(TABLES['学习卡片表'], page_size=500)
    cards = []
    for r in cards_raw:
        f = r.get('fields', {})
        cid = r['record_id']
        st = plain(f.get('卡片状态')) or 'NOT_STARTED'
        dep = plain(f.get('前置依赖'))
        dep_state = None
        if dep and dep.startswith('rec'):
            try:
                dep_state = plain(c.get_record(TABLES['学习卡片表'], dep)['fields'].get('卡片状态')) or 'NOT_STARTED'
            except Exception:
                dep_state = None
        cards.append({'card_id': cid, '状态': st, '下次复习日期': f.get('下次复习日期'),
                      '前置依赖': dep, '依赖状态': dep_state,
                      '标题': plain(f.get('卡片问题正面')) or ''})
    return sp.daily_plan(cards, today), {c2['card_id']: c2 for c2 in cards}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chat', default=DEFAULT_CHAT)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--date', default=None)
    a = ap.parse_args()
    from datetime import date
    today = date.fromisoformat(a.date) if a.date else date.today()
    c = FeishuClient()
    svc = ReviewService(c)

    cursor = load_cursor()
    msgs = fetch_messages(c, a.chat, cursor)
    if not msgs:
        print('无新消息（游标=%d）' % cursor)
        if a.once:
            return 0
    plan, by_id = build_queue(c, today)
    processed = 0
    max_ts = cursor
    for m in msgs:
        ts = int(m.get('create_time') or 0)
        max_ts = max(max_ts, ts)
        if cc.is_app_message(m):
            continue
        text = cc.extract_text(m)
        parsed = cc.parse_command(text)
        if not parsed:
            continue
        result, target = parsed
        card_id = cc.map_to_cards(plan, target)
        if not card_id:
            send_text(c, a.chat, '⚠ 指令无法匹配今日队列卡片（会/不会/模糊 + 序号1~%d）' % plan['total'])
            continue
        title = (by_id.get(card_id) or {}).get('标题') or card_id
        if a.dry_run:
            print('[dry-run] 卡=%s 结果=%s' % (title, result))
            processed += 1
            continue
        # 写流水（幂等：record_answer 有 event_id 去重）
        try:
            dt = datetime.fromtimestamp(ts / 1000, CST)
            rec, dup = svc.record_answer(card_id, result, source='群指令',
                                         client_dt=dt, card_title=title)
            if dup:
                print('[幂等跳过] %s' % title)
                continue
            svc.derive_and_apply(rebuild_all=True)  # 即时派生
            processed += 1
            send_text(c, a.chat, '✓ [%s] 已记录"%s" → %s' % (today.isoformat(), title, result))
            print('已处理: %s -> %s' % (title, result))
        except Exception as e:
            print('写流水失败 %s: %s' % (title, e))
    save_cursor(max_ts)
    print('本轮处理 %d 条指令，游标推进至 %d' % (processed, max_ts))
    print('CHAT_POLL_DONE')


if __name__ == '__main__':
    main()
