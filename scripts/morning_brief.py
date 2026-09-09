# -*- coding: utf-8 -*-
"""
morning_brief.py — V13 波次2 早报生成器（07:53 错峰活体+学习入口）
聚合：①今日复习队列（每日3张） ②目标覆盖矩阵缺口提示 ③系统健康（探针四路）
输出：早报文本（可接飞书 webhook 推送）
用法: python morning_brief.py [--send] [--date 2026-09-09]
"""
import sys, io, argparse, json
from datetime import date
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
# 注意：daily_plan 会包裹 stdout；本模块直接复用，不再重复包裹
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService
import study_planner as sp
import daily_plan  # 复用队列读取


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def build_brief(today, quota=3):
    c = FeishuClient()
    svc = ReviewService(c)
    svc.derive_and_apply(rebuild_all=True, dry_run=True)
    cards_raw = c.read_records(TABLES['学习卡片表'], page_size=500)
    cards, by_id = [], {}
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
        card = {'card_id': cid, '状态': st, '下次复习日期': f.get('下次复习日期'),
                '前置依赖': dep, '依赖状态': dep_state, '科目': plain(f.get('科目')) or '',
                '标题': plain(f.get('卡片问题正面')) or ''}
        cards.append(card)
        by_id[cid] = card
    plan = sp.daily_plan(cards, today, quota=quota)
    # 覆盖矩阵（按现有科目聚合）
    domains = ['考证', '认知', '酒店工程', '财商', '沟通']
    m = sp.coverage_matrix(cards, domains)
    gaps = [d for d in domains if m[d]['gap']]
    # 系统健康（探针单文件合并）
    health = '—'
    try:
        import subprocess
        p = subprocess.run([sys.executable, r'D:\AI-Tools\feishu\V12方案\v13_wave1\probe30.py', '--once'],
                           capture_output=True, timeout=90)
        out = (p.stdout or b'').decode('utf-8', 'replace')
        try:
            line = [l for l in out.splitlines() if l.strip().startswith('{')][-1]
            d = json.loads(line)
            ok_all = all(d.get(k) for k in ('hermes_gateway', 'anyllm', 'feishu', 'deepseek'))
            health = 'OK(四路)' if ok_all else '部分FAIL(%s)' % ','.join(
                k for k, v in d.items() if not v)
        except Exception:
            health = 'probe解析异常'
    except Exception:
        health = 'probe超时'
    lines = []
    lines.append('【%s 早报 · 学习入口】' % today.isoformat())
    lines.append('今日复习 %d 张：' % plan['total'])
    for cid in plan['due'] + plan['new']:
        lines.append('  · %s' % (by_id[cid]['标题'] or cid))
    if plan['note']:
        lines.append('提示：%s' % plan['note'])
    lines.append('覆盖缺口：%s' % ('>'.join(gaps) if gaps else '无'))
    lines.append('系统健康：%s' % health)
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    text = build_brief(today)
    print(text)
    if a.send:
        # 接飞书 webhook（自定义机器人，加签模式：timestamp+sign；避整点，单条<=20KB）
        import requests, json as _json, time as _time, urllib.parse
        from feishu_sdk import gen_sign
        from feishu_sdk import get_bot_config

        cfg = get_bot_config()
        try:
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
    print('MORNING_BRIEF_DONE')


if __name__ == '__main__':
    main()
