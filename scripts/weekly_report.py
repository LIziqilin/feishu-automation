# -*- coding: utf-8 -*-
"""
weekly_report.py — V13 周报生成器（周日 20:11 错峰）
聚合：①学习侧三指标（素材处置/来源转化/复习完成） ②目标覆盖矩阵 ③ROI 看板 ④归档候选(180天) ⑤系统健康
用法: python weekly_report.py [--send] [--date 2026-09-13]
"""
import sys, io, argparse
from datetime import date, datetime, timezone, timedelta
import os
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
# 注意：learning_metrics 会包裹 stdout；本模块不再重复包裹
import learning_metrics as lm
import review_engine as eng
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService
import study_planner as sp

CST = timezone(timedelta(hours=8))


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def build_weekly(today):
    c = FeishuClient()
    lines = []
    lines.append('【%s 周报】' % today.isoformat())

    # 1) 学习侧三指标
    try:
        import json as _json
        m = lm.main(json=True) if hasattr(lm, 'main') else None
        # learning_metrics 以模块方式调用较绕，直接内联统计
    except Exception:
        pass
    # 内联三指标
    week_ago = int((datetime.now(CST) - timedelta(days=7)).timestamp() * 1000)
    idx = c.read_records(TABLES['知识索引表'], page_size=500,
                         field_names=['标题', '创建日期', '知识池', '状态'])
    new7 = [r for r in idx if r.get('fields', {}).get('创建日期')
            and int(r.get('fields', {})['创建日期']) >= week_ago]
    disposed = [r for r in new7
                if plain(r.get('fields', {}).get('知识池')) == '活跃池'
                or plain(r.get('fields', {}).get('状态')) in ('已处置', '转卡', '淘汰')]
    dr = len(disposed) * 100 / len(new7) if new7 else 100.0
    cards = c.read_records(TABLES['学习卡片表'], page_size=500,
                           field_names=['卡片问题正面', '来源知识ID', '卡片状态', '科目'])
    total_cards = len(cards)
    linked = [r for r in cards if plain(r.get('fields', {}).get('来源知识ID'))]
    lr = len(linked) * 100 / total_cards if total_cards else 0.0
    flow = c.read_records(TABLES['复习流水表'], page_size=500, field_names=['客户端时间戳'])
    wk_flow = [r for r in flow
               if r.get('fields', {}).get('客户端时间戳')
               and int(r.get('fields', {})['客户端时间戳']) >= week_ago]
    active_n = sum(1 for r in cards if plain(r.get('fields', {}).get('卡片状态')) in ('LEARNING', 'REVIEWING'))
    due_est = max(active_n, 1) * 3
    cr = len(wk_flow) * 100 / due_est if due_est else 0.0
    lines.append('学习三指标：素材处置 %.0f%%(%d/%d) | 来源转化 %.0f%%(%d/%d) | 复习完成 %.0f%%(%d/%d)'
                 % (dr, len(disposed), len(new7), lr, len(linked), total_cards,
                    min(cr, 100), len(wk_flow), due_est))

    # 2) 覆盖矩阵缺口
    dom = ['考证', '认知', '酒店工程', '财商', '沟通']
    card_recs = []
    for r in cards:
        f = r.get('fields', {})
        card_recs.append({'card_id': r['record_id'],
                          '科目': plain(f.get('科目')) or '未分类',
                          '状态': plain(f.get('卡片状态')) or 'NOT_STARTED'})
    mat = sp.coverage_matrix(card_recs, dom)
    gaps = [d for d in dom if mat[d]['gap']]
    lines.append('覆盖缺口：%s' % ('>'.join(gaps) if gaps else '无'))
    for d in dom:
        lines.append('  %s：%d卡/%d掌握%s' % (d, mat[d]['total'], mat[d]['mastered'],
                                           ' ⚠' if mat[d]['gap'] else ''))

    # 3) ROI
    mastered_new = sum(1 for r in cards if plain(r.get('fields', {}).get('卡片状态')) == 'MASTERED')
    maintenance_min = 30  # 双窗口预算
    lines.append('ROI：本周新掌握 %d 卡 / 维护 %d 分钟' % (mastered_new, maintenance_min))

    # 4) 归档候选（180天无反馈，仅LEARNING/REVIEWING）
    svc = ReviewService(c)
    der = svc.derive_and_apply(rebuild_all=True, dry_run=True)
    states = {}
    for rid, snap in der.get('all_states', {}).items():
        states[rid] = snap
    cands = []
    if states:
        cands = eng.archive_candidates(states, today)
    lines.append('归档候选(180天无反馈)：%d 条（人工确认后归档，MASTERED豁免）' % len(cands))

    # 5) 健康
    try:
        import subprocess, json as _json
        p = subprocess.run([sys.executable, r'D:\AI-Tools\feishu\V12方案\v13_wave1\probe30.py', '--once'],
                           capture_output=True, timeout=90)
        out = (p.stdout or b'').decode('utf-8', 'replace')
        line = [l for l in out.splitlines() if l.strip().startswith('{')][-1]
        d = _json.loads(line)
        ok = all(d.get(k) for k in ('hermes_gateway', 'anyllm', 'feishu', 'deepseek'))
        lines.append('系统健康：%s' % ('OK(四路)' if ok else '部分FAIL(%s)' % ','.join(
            k for k, v in d.items() if not v)))
    except Exception:
        lines.append('系统健康：探测失败')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    text = build_weekly(today)
    print(text)
    if a.send:
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
    print('WEEKLY_REPORT_DONE')


if __name__ == '__main__':
    main()
