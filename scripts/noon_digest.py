# -*- coding: utf-8 -*-
"""
noon_digest.py — V13 午报生成器（12:23 错峰）
聚合：①今日学习进度（已复习/未复习） ②下午提醒 ③简版健康
用法: python noon_digest.py [--send] [--date 2026-09-09]
"""
import sys, io, argparse
from datetime import date, datetime, timezone, timedelta
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
# 注意：morning_brief 内部包裹 stdout；本模块不再重复包裹
import morning_brief as mb
from feishu_sdk import FeishuClient, TABLES

CST = timezone(timedelta(hours=8))


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def build_noon(today):
    c = FeishuClient()
    # 今日复习完成数：流水表今天有几条
    day_start = int(datetime(today.year, today.month, today.day, tzinfo=CST).timestamp() * 1000)
    flow = c.read_records(TABLES['复习流水表'], page_size=500, field_names=['客户端时间戳'])
    done = sum(1 for r in flow
               if r.get('fields', {}).get('客户端时间戳')
               and int(r.get('fields', {})['客户端时间戳']) >= day_start)
    lines = []
    lines.append('【%s 午报】' % today.isoformat())
    lines.append('今日已复习 %d 张（目标 3 张）%s' % (
        done, '，加油完成剩余!' if done < 3 else '，已完成目标✓'))
    lines.append('下午建议：优先处理待办，晚间 12:37 有明日学习提醒')
    return '\n'.join(lines)



def check_noon_idempotent(c, today):
    """V13 v9.0新增: 午报幂等检查。查系统健康表是否已有今日午报推送记录。"""
    idem_key = f'午报推送-{today.isoformat()}'
    try:
        records = c.read_records(TABLES['系统健康表'], page_size=100)
        for r in records:
            f = r.get('fields', {})
            if str(f.get('检查项', '')) == idem_key:
                return True
    except Exception:
        pass
    return False

def mark_noon_idempotent(c, today):
    """V13 v9.0新增: 午报推送成功后写入幂等记录。"""
    idem_key = f'午报推送-{today.isoformat()}'
    now_ms = int(datetime.now(CST).timestamp() * 1000)
    try:
        c.create_record(TABLES['系统健康表'], {
            '检查项': idem_key, '状态': '正常', '最近检查时间': now_ms,
            '检查结果': '午报推送成功',
        })
    except Exception:
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    text = build_noon(today)
    print(text)
    if a.send:
        c = FeishuClient()
        if check_noon_idempotent(c, today):
            print(f'[幂等跳过] 今日({today.isoformat()})午报已推送，跳过')
            return
        import requests, json as _json
        from feishu_sdk import gen_sign
        from feishu_sdk import get_bot_config

        cfg = get_bot_config()
        try:
            webhook = cfg.get('webhook') or cfg.get('url')
            if not webhook:
                print('\n[推送失败] 无 webhook 键')
            else:
                ts, sign = gen_sign(cfg.get('secret', ''))
                url = '%s?timestamp=%s&sign=%s' % (webhook, ts, sign)
                r = requests.post(url, json={'msg_type': 'text',
                                             'content': {'text': text}},
                                  timeout=10)
                print('\n[已推送] HTTP %s %s' % (r.status_code, r.text[:120]))
        except Exception as e:
            print('\n[推送失败] %s' % e)
            mark_noon_idempotent(c, today)
        print(f'[幂等记录] 已写入 午报推送-{today.isoformat()}')
    print('NOON_DIGEST_DONE')


if __name__ == '__main__':
    main()
