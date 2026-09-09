# -*- coding: utf-8 -*-
"""
keepalive.py — Actions 保活（每月1日 09:11 错峰）
GitHub Actions 默认分支 60 天无 commit 会自动停用全部 workflow。
本脚本输出占位并提示（云端由 workflow 内 git commit 实现空提交保活）。
本地版：仅记录保活日志 + 推送提醒。
用法: python keepalive.py [--send]
"""
import os, sys, io, json, time
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

LOG = r'D:\AI-Tools\shared\logs\keepalive.log'


def main():
    args = sys.argv[1:]
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = '[%s] keepalive ping' % time.strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    print(line)
    if '--send' in args:
        try:
            import requests, hmac, hashlib, base64
            cfg = json.load(open(r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json',
                                 encoding='utf-8'))
            webhook = cfg.get('webhook') or cfg.get('url')
            if webhook:
                from feishu_sdk import gen_sign
                ts, sign = gen_sign(cfg.get('secret', ''))
                r = requests.post('%s?timestamp=%s&sign=%s' % (webhook, ts, sign),
                                  json={'msg_type': 'text', 'content': {'text': line}},
                                  timeout=10)
                print('[推送] %s' % r.text[:120])
        except Exception as e:
            print('[推送失败] %s' % e)
    print('KEEPALIVE_DONE')


if __name__ == '__main__':
    main()
