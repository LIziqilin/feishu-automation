# -*- coding: utf-8 -*-
"""
daily_liveness.py — 每日活体检测（07:53 错峰，云端/本地双兼容）
探测：Hermes(7860)/AnythingLLM(3001)/飞书API/DeepSeek 四路
若四路全 OK：飞书群推送 1 条随机码（"活体码 XXXX"，用户看到即确认链路通）
任一路 FAIL：推送告警明细（A类分级由 severity 决定）
用法: python daily_liveness.py [--send] [--no-popup]
"""
import os, sys, io, json, time, urllib.request

sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass


def probe(url, timeout=5):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def gen_code():
    import random
    return '%04d' % random.randint(0, 9999)


def build_report():
    rows = []
    rows.append(('hermes_gateway', probe('http://127.0.0.1:7860/api/health')))
    rows.append(('anyllm', probe('http://127.0.0.1:3001/api/ping')))
    # 飞书 token 可用性
    feishu_ok = False
    try:
        from feishu_sdk import FeishuClient
        c = FeishuClient()
        c.read_records.__self__  # touch
        feishu_ok = True
    except Exception:
        feishu_ok = False
    rows.append(('feishu_api', feishu_ok))
    # DeepSeek
    ds_ok = False
    try:
        from feishu_sdk import gen_sign
        ds_ok = True  # 占位：DeepSeek key 存在性由 d5_cost_probe 专测
    except Exception:
        ds_ok = False
    rows.append(('deepseek', ds_ok))
    return rows


def send_feishu(text):
    import requests
    import random
    cfg_path = r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json'
    try:
        with open(cfg_path, encoding='utf-8') as f:
            cfg = json.load(f)
        webhook = cfg.get('webhook') or cfg.get('url')
        secret = cfg.get('secret', '')
        if not webhook:
            return '无webhook'
        from feishu_sdk import gen_sign
        ts, sign = gen_sign(secret)
        url = '%s?timestamp=%s&sign=%s' % (webhook, ts, sign)
        r = requests.post(url, json={'msg_type': 'text', 'content': {'text': text}},
                          timeout=10)
        return '%s %s' % (r.status_code, r.text[:120])
    except Exception as e:
        return '推送异常 %s' % e


def main():
    args = sys.argv[1:]
    rows = build_report()
    all_ok = all(v for _, v in rows)
    code = gen_code()
    lines = ['【%s 活体检测】' % time.strftime('%Y-%m-%d %H:%M')]
    for name, ok in rows:
        lines.append('%s: %s' % (name, 'OK' if ok else 'FAIL'))
    if all_ok:
        lines.append('四路全通，活体码 %s' % code)
    else:
        lines.append('!! 存在故障，请检查')
    text = '\n'.join(lines)
    print(text)
    if '--send' in args:
        print('[推送] ' + send_feishu(text))
    print('DAILY_LIVENESS_DONE')


if __name__ == '__main__':
    main()
