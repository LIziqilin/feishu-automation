# -*- coding: utf-8 -*-
"""
cold_restore.py — V13 波次2 冷归档恢复配额（降权不删向量）
规则（方案§7/§11.5）：冷归档默认 hidden 降权（零费用可逆）；恢复<=5条/月；恢复前费用预估
用法:
  python cold_restore.py --check          # 查当前冷归档条数+本月已恢复配额
  python cold_restore.py --restore recX   # 恢复1条（预估+写回，默认dry-run需--apply）
  python cold_restore.py --restore recX --apply
配额状态存 state/cold_restore.json（按月滚动）
"""
import sys, io, os, json, argparse
from datetime import datetime, timezone, timedelta
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES

CST = timezone(timedelta(hours=8))
STATE = r'D:\AI-Tools\shared\state\cold_restore.json'
MONTH_LIMIT = 5


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def load_state():
    try:
        with open(STATE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'month': '', 'restored': []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def current_month():
    return datetime.now(CST).strftime('%Y-%m')


def estimate_cost(title_len, tokens_per_char=1.5):
    """费用预估：重新 embedding 的成本模型（DeepSeek/ALLM 按 token 计）。
    仅为估算，标注口径。"""
    est_tokens = int(title_len * tokens_per_char)
    # 每千 token 约 ¥0.0001（embedding 类）——按量后付费实测值口径
    est_cost = est_tokens / 1000 * 0.0001
    return est_tokens, round(est_cost, 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--restore', default=None)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    c = FeishuClient()
    st = load_state()
    month = current_month()
    if st.get('month') != month:
        st = {'month': month, 'restored': []}

    if a.check:
        idx = c.read_records(TABLES['知识索引表'], page_size=500,
                             field_names=['标题', '知识池', '科目'])
        cold = [r for r in idx if plain(r.get('fields', {}).get('知识池')) == '冷归档']
        print('=== 冷归档状态 %s ===' % month)
        print('冷归档条数: %d' % len(cold))
        print('本月已恢复: %d / 配额 %d' % (len(st['restored']), MONTH_LIMIT))
        for r in cold[:10]:
            print('  %s %s' % (r['record_id'],
                               str(plain(r.get('fields', {}).get('标题')))[:24]))
        if len(cold) > 10:
            print('  …共 %d 条' % len(cold))
        print('COLD_CHECK_DONE')
        return 0

    if a.restore:
        card = c.get_record(TABLES['知识索引表'], a.restore)
        f = card['fields']
        pool = plain(f.get('知识池'))
        title = str(plain(f.get('标题')) or a.restore)
        if pool != '冷归档':
            print('该记录不在冷归档（当前=%s），无需恢复' % pool)
            return 1
        if len(st['restored']) >= MONTH_LIMIT:
            print('本月恢复配额已用尽（%d/%d），下月再试' % (len(st['restored']), MONTH_LIMIT))
            return 2
        tokens, cost = estimate_cost(len(title))
        print('=== 恢复预览 ===')
        print('条目: %s' % title)
        print('预估重新embedding: ~%d tokens, 约 ¥%f（按量后付费估算口径，非账单）'
              % (tokens, cost))
        print('恢复后: 冷归档 → 温存池（参与低优先级检索）')
        if not a.apply:
            print('[dry-run] 加 --apply 执行')
            return 0
        c.update_record(TABLES['知识索引表'], a.restore, {'知识池': '温存池'})
        st['restored'].append({'id': a.restore, 'at': datetime.now(CST).isoformat(),
                               'title': title[:30]})
        save_state(st)
        print('已恢复 %s → 温存池（本月 %d/%d）' % (title[:30], len(st['restored']), MONTH_LIMIT))
        print('COLD_RESTORE_DONE')
        return 0


if __name__ == '__main__':
    main()
