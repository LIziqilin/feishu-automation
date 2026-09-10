# -*- coding: utf-8 -*-
"""
morning_brief.py — V13 早报生成器（07:53 错峰，云端兜底+幂等防双份）
聚合：①今日复习队列 ②今日到期任务 ③目标覆盖矩阵缺口 ④系统健康
幂等：推送前查系统健康表"早报推送-YYYY-MM-DD"记录，已存在则跳过
用法: python morning_brief.py [--send] [--date 2026-09-11]
V13 v9.0修复: 增加幂等机制(日期+任务名)，防止本地+云端双份推送
"""
import sys, io, argparse, json
from datetime import date, datetime, timezone, timedelta
import os
CST = timezone(timedelta(hours=8))
_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
from feishu_sdk import FeishuClient, TABLES
from review_io import ReviewService
import study_planner as sp
import daily_plan


def plain(v):
    if isinstance(v, list) and v:
        return v[0].get('text') if isinstance(v[0], dict) else v[0]
    return v


def parse_deadline(deadline):
    """解析飞书API返回的截止日期字段，支持毫秒时间戳(数字)和字符串。"""
    if deadline is None:
        return None
    if isinstance(deadline, (int, float)):
        if deadline > 1e12:
            return datetime.fromtimestamp(deadline / 1000, tz=CST)
        elif deadline > 1e9:
            return datetime.fromtimestamp(deadline, tz=CST)
    if isinstance(deadline, str):
        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d']:
            try:
                return datetime.strptime(deadline[:19], fmt).replace(tzinfo=CST)
            except ValueError:
                continue
        try:
            ts = float(deadline)
            if ts > 1e12:
                return datetime.fromtimestamp(ts / 1000, tz=CST)
        except ValueError:
            pass
    return None


def get_due_tasks(c, today):
    """查询今日到期任务。"""
    due_tasks = []
    try:
        tasks = c.read_records(TABLES['任务总表'], page_size=200)
        today_str = today.isoformat()
        for task in tasks:
            f = task.get('fields', {})
            status = str(f.get('状态', ''))
            if status in ('已完成', '已取消', '完成'):
                continue
            deadline = f.get('截止日期', f.get('计划完成时间', None))
            dt = parse_deadline(deadline)
            if dt and dt.strftime('%Y-%m-%d') == today_str:
                title = str(f.get('任务名称', f.get('标题', '无标题')))[:30]
                priority = str(f.get('优先级', f.get('重要程度', '')))
                due_tasks.append({'title': title, 'deadline': dt.strftime('%H:%M'), 'priority': priority})
    except Exception as e:
        print(f'[到期任务查询异常] {e}', file=sys.stderr)
    return due_tasks


def check_idempotent(c, today):
    """V13 v9.0新增: 幂等检查。查系统健康表是否已有今日早报推送记录。
    幂等键 = "早报推送-YYYY-MM-DD"。已存在则返回True(跳过)，不存在返回False(继续推送)。
    """
    idem_key = f'早报推送-{today.isoformat()}'
    try:
        records = c.read_records(TABLES['系统健康表'], page_size=100)
        for r in records:
            f = r.get('fields', {})
            check_item = str(f.get('检查项', ''))
            if check_item == idem_key:
                return True  # 今日已推送，跳过
    except Exception as e:
        print(f'[幂等检查异常] {e}', file=sys.stderr)
    return False


def mark_idempotent(c, today):
    """V13 v9.0新增: 推送成功后写入幂等记录。"""
    idem_key = f'早报推送-{today.isoformat()}'
    now_ms = int(datetime.now(CST).timestamp() * 1000)
    try:
        c.create_record(TABLES['系统健康表'], {
            '检查项': idem_key,
            '状态': '正常',
            '最近检查时间': now_ms,
            '检查结果': '早报推送成功',
        })
        return True
    except Exception as e:
        print(f'[幂等记录写入异常] {e}', file=sys.stderr)
        return False


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
    domains = ['考证', '认知', '酒店工程', '财商', '沟通']
    m = sp.coverage_matrix(cards, domains)
    gaps = [d for d in domains if m[d]['gap']]
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
            health = 'OK(四路)' if ok_all else '部分FAIL(%s)' % ','.join(k for k, v in d.items() if not v)
        except Exception:
            health = 'probe解析异常'
    except Exception:
        health = 'probe超时'
    due_tasks = get_due_tasks(c, today)
    lines = []
    lines.append('【%s 早报 · 学习入口】' % today.isoformat())
    lines.append('今日复习 %d 张：' % plan['total'])
    for cid in plan['due'] + plan['new']:
        lines.append('  · %s' % (by_id[cid]['标题'] or cid))
    if plan['note']:
        lines.append('提示：%s' % plan['note'])
    if due_tasks:
        lines.append('今日到期 %d 个任务：' % len(due_tasks))
        for t in due_tasks[:5]:
            prio = '[%s] ' % t['priority'] if t['priority'] else ''
            lines.append('  ⏰ %s%s (截止%s)' % (prio, t['title'], t['deadline']))
        if len(due_tasks) > 5:
            lines.append('  ...还有%d个' % (len(due_tasks) - 5))
    else:
        lines.append('今日到期任务：无')
    lines.append('覆盖缺口：%s' % ('>'.join(gaps) if gaps else '无'))
    lines.append('系统健康：%s' % health)
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=None)
    ap.add_argument('--send', action='store_true')
    a = ap.parse_args()
    today = date.fromisoformat(a.date) if a.date else date.today()
    
    # V13 v9.0新增: 幂等检查（仅在--send模式下）
    if a.send:
        c = FeishuClient()
        if check_idempotent(c, today):
            print(f'[幂等跳过] 今日({today.isoformat()})早报已推送，跳过')
            print('MORNING_BRIEF_DONE')
            return
    
    text = build_brief(today)
    print(text)
    if a.send:
        import requests
        from feishu_sdk import gen_sign, get_bot_config
        cfg = get_bot_config()
        try:
            webhook = cfg.get('webhook') or cfg.get('url')
            if not webhook:
                print('\n[推送失败] feishu_bot_config.json 无 webhook 键')
            else:
                ts, sign = gen_sign(cfg.get('secret', ''))
                url = '%s?timestamp=%s&sign=%s' % (webhook, ts, sign)
                r = requests.post(url, json={'msg_type': 'text', 'content': {'text': text}}, timeout=10)
                print('\n[已推送] HTTP %s %s' % (r.status_code, r.text[:120]))
                # V13 v9.0新增: 推送成功后写入幂等记录
                if r.status_code == 200:
                    c = FeishuClient()
                    mark_idempotent(c, today)
                    print(f'[幂等记录] 已写入 早报推送-{today.isoformat()}')
        except Exception as e:
            print('\n[推送失败] %s' % e)
    print('MORNING_BRIEF_DONE')


if __name__ == '__main__':
    main()
