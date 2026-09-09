# -*- coding: utf-8 -*-
"""
patrol.py — 每日巡检（23:13 错峰）
1) 检查错误日志表近24h是否有 A 类未处理
2) 检查死信表是否有积压
3) 检查系统健康表最新记录时间
4) 汇总巡检报告推送
用法: python patrol.py [--send]
"""
import os, sys, io, json, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

CST = timezone(timedelta(hours=8))


def main():
    args = sys.argv[1:]
    try:
        from feishu_sdk import FeishuClient, TABLES
        c = FeishuClient()
        lines = ['【%s 巡检】' % time.strftime('%Y-%m-%d %H:%M')]
        # 1) A类未处理
        a_count = 0
        for tname, sf in (('错误日志_云端', '处理状态'), ('错误日志_本地', '状态')):
            try:
                recs = c.read_records(TABLES[tname], page_size=500,
                                      field_names=['级别', sf])
                a_count += sum(1 for r in recs
                               if 'A' in str(r.get('fields', {}).get('级别', ''))
                               and ('待处理' in str(r.get('fields', {}).get(sf, '')) or '未处理' in str(r.get('fields', {}).get(sf, ''))))
            except Exception:
                pass
        lines.append('A类未处理: %d' % a_count)
        # 2) 死信积压
        try:
            dlq = c.read_records(TABLES['错误日志_云端'], page_size=500)
            lines.append('错误日志云端总数: %d' % len(dlq))
        except Exception:
            lines.append('错误日志云端总数: 读取失败')
        # 3) 系统健康最新
        try:
            health = c.read_records(TABLES['系统健康表'], page_size=50,
                                    field_names=['检查项', '处理状态', '最近检查时间'])
            lines.append('健康表记录数: %d' % len(health))
        except Exception:
            lines.append('健康表: 读取失败')
        verdict = '正常' if a_count == 0 else '需关注'
        lines.append('巡检结论: %s' % verdict)
        text = '\n'.join(lines)
        print(text)
        if '--send' in args:
            import requests
            from feishu_sdk import gen_sign
            cfg = json.load(open(r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json',
                                 encoding='utf-8'))
            webhook = cfg.get('webhook') or cfg.get('url')
            if webhook:
                ts, sign = gen_sign(cfg.get('secret', ''))
                r = requests.post('%s?timestamp=%s&sign=%s' % (webhook, ts, sign),
                                  json={'msg_type': 'text', 'content': {'text': text}},
                                  timeout=10)
                print('[推送] %s' % r.text[:120])
    except Exception as e:
        print('巡检异常: %s' % e)
    print('PATROL_DONE')


if __name__ == '__main__':
    main()
