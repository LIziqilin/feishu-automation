# -*- coding: utf-8 -*-
"""
noon_digest.py — V13 午报生成器（12:23 错峰）
聚合：①今日学习进度（已复习/未复习） ②下午提醒 ③简版健康
用法: python noon_digest.py [--send] [--date 2026-09-09]
"""
import sys, io, argparse
from datetime import date, datetime, timezone, timedelta
sys.path.insert(0, r'D:\AI-Tools\shared')
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    text = build_noon(today)
    print(text)
    if a.send:
        import requests, json as _json
        from feishu_sdk import gen_sign
        cfg_path = r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json'
        try:
            with open(cfg_path, encoding='utf-8') as f:
                cfg = _json.load(f)
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
    print('NOON_DIGEST_DONE')


if __name__ == '__main__':
    main()
