# -*- coding: utf-8 -*-
"""
learn_digest.py — V13 波次2 晚间学习提醒（12:37 错峰）
明日复习队列预览 + 覆盖矩阵缺口 → 输出文本（可接 webhook）
用法: python learn_digest.py [--send] [--date 2026-09-10]
"""
import sys, argparse
from datetime import date, timedelta
sys.path.insert(0, r'D:\AI-Tools\shared')
import morning_brief as mb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--send', action='store_true')
    ap.add_argument('--date', default=None)
    a = ap.parse_args()
    base = date.fromisoformat(a.date) if a.date else date.today()
    tomorrow = base + timedelta(days=1)
    brief = mb.build_brief(tomorrow, quota=3)
    lines = brief.splitlines()
    # 只取队列部分，去掉健康（晚间无需探测）
    body = ['【%s 晚间 · 明日学习】' % tomorrow.isoformat()]
    for l in lines[1:]:
        if l.startswith('系统健康'):
            continue
        body.append(l)
    text = '\n'.join(body)
    print(text)
    if a.send:
        import requests, json as _json, urllib.parse
        from feishu_sdk import gen_sign
        cfg_path = r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json'
        try:
            with open(cfg_path, encoding='utf-8') as f:
                cfg = _json.load(f)
            webhook = cfg.get('webhook') or cfg.get('url')
            if not webhook:
                print('\n[推送失败] feishu_bot_config.json 无 webhook 键')
            else:
                ts, sign = gen_sign(cfg.get('secret', ''))
                # gen_sign 已做 quote_plus；sign 参数直接拼（勿二次编码）
                url = '%s?timestamp=%s&sign=%s' % (webhook, ts, sign)
                r = requests.post(url, json={'msg_type': 'text',
                                             'content': {'text': text}},
                                  timeout=10)
                print('\n[已推送] HTTP %s %s' % (r.status_code, r.text[:120]))
        except Exception as e:
            print('\n[推送失败] %s' % e)
    print('LEARN_DIGEST_DONE')


if __name__ == '__main__':
    main()
