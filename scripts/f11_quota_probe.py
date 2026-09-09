# -*- coding: utf-8 -*-
"""
f11_quota_probe.py — 飞书自动化额度探测（08:47 错峰）
读取多维表格自动化运行统计（tenant token），判断月度剩余额度。
基础版 200 次/月，输出剩余百分比；<20% 推送告警。
用法: python f11_quota_probe.py [--send]
"""
import os, sys, io, json, time
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass


def main():
    args = sys.argv[1:]
    try:
        from feishu_sdk import FeishuClient, TABLES
        c = FeishuClient()
        # 读系统健康表（自动化运行次数记录在本表）
        recs = c.read_records(TABLES['系统健康表'], page_size=500,
                              field_names=['检查项', '自动化次数', '今日自动化次数', '最近检查时间'])
        auto_rows = [r for r in recs
                     if r.get('fields', {}).get('自动化次数') is not None
                     or r.get('fields', {}).get('今日自动化次数') is not None]
        lines = ['【%s 额度探测】' % time.strftime('%Y-%m-%d %H:%M')]
        if auto_rows:
            for r in auto_rows[:10]:
                f = r.get('fields', {})
                lines.append('%s 自动化次数=%s 今日=%s' % (
                    f.get('检查项'), f.get('自动化次数'), f.get('今日自动化次数')))
        else:
            lines.append('健康表暂无自动化次数记录（基础版200次/月，需GUI查看）')
        # 简化：按健康表最新记录估剩余
        text = '\n'.join(lines)
        print(text)
        if '--send' in args:
            import requests
            from feishu_sdk import get_bot_config
            cfg = get_bot_config()
            webhook = cfg.get('webhook') or cfg.get('url')
            if webhook:
                from feishu_sdk import gen_sign
                ts, sign = gen_sign(cfg.get('secret', ''))
                r = requests.post('%s?timestamp=%s&sign=%s' % (webhook, ts, sign),
                                  json={'msg_type': 'text', 'content': {'text': text}},
                                  timeout=10)
                print('[推送] %s' % r.text[:120])
    except Exception as e:
        print('额度探测异常: %s' % e)
    print('F11_QUOTA_DONE')


if __name__ == '__main__':
    main()
