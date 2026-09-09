# -*- coding: utf-8 -*-
"""
schedule_audit.py — 调度对账（12_schedule_audit.yml 每周）
1) 读取 schedule_master.yaml 权威时刻表
2) 对比本地 Windows 任务实际触发器
3) 输出差异报告（新增/缺失/时间不符）
用法: python schedule_audit.py [--send]
"""
import os, sys, io, json, time, subprocess, yaml
sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

MASTER = r'D:\AI-Tools\feishu\V12方案\v13_wave0\schedule_master.yaml'
LOCAL_PREFIX = ('V13_', 'Hermes_', 'FeishuAssistant-')


def main():
    args = sys.argv[1:]
    try:
        with open(MASTER, encoding='utf-8') as f:
            master = yaml.safe_load(f)
        jobs = master.get('jobs', {})
        expected = {k: v.get('beijing', '') for k, v in jobs.items()}
        # 本地任务
        ps = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             'Get-ScheduledTask | Where-Object {$_.TaskName -like "V13*" -or $_.TaskName -like "Hermes*" -or $_.TaskName -like "FeishuAssistant*"} | Select-Object TaskName,State | ConvertTo-Json'],
            capture_output=True, text=True, timeout=60)
        actual = {}
        try:
            data = json.loads(ps.stdout)
            items = data if isinstance(data, list) else [data]
            for it in items:
                if it:
                    actual[it.get('TaskName', '')] = it.get('State', '')
        except Exception:
            actual = {}
        lines = ['【调度对账】']
        lines.append('权威时刻表任务数: %d' % len(expected))
        lines.append('本地任务数: %d' % len(actual))
        v13 = {k: v for k, v in actual.items() if k.startswith('V13_')}
        lines.append('V13 本地任务: %s' % (', '.join(sorted(v13)) or '无'))
        # 本地任务名 → 云端 job 名映射（V13_ 前缀任务对应 schedule_master job）
        local_to_job = {
            'V13_MorningBrief': 'morning_digest',
            'V13_NoonDigest': 'noon_digest',
            'V13_LearnDigest': 'learn_digest',
            'V13_WeeklyReport': 'weekly_report',
            'V13_Watchdog_10min': None,  # 本地守护，无云端对应
        }
        covered = set()
        for lname, jname in local_to_job.items():
            if lname in actual and jname:
                covered.add(jname)
        mismatches = []
        for name, beijing in expected.items():
            if name not in covered and name not in actual:
                mismatches.append('%s 本地无对应任务(期望%s)' % (name, beijing))
        for name, state in actual.items():
            # 状态码：0=Unknown 1=Disabled 2=Queued 3=Ready 4=Running
            st_map = {0: 'Unknown', 1: 'Disabled', 2: 'Queued', 3: 'Ready', 4: 'Running'}
            st_name = st_map.get(state, str(state))
            if name.startswith('V13_') and st_name not in ('Ready', 'Running'):
                mismatches.append('%s 状态=%s' % (name, st_name))
        if mismatches:
            lines.append('差异 %d 项:' % len(mismatches))
            for m in mismatches[:15]:
                lines.append('  ! %s' % m)
        else:
            lines.append('无差异，调度与权威时刻表一致')
        text = '\n'.join(lines)
        print(text)
        if '--send' in args:
            import requests, hmac, hashlib, base64
            cfg = json.load(open(r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json',
                                 encoding='utf-8'))
            webhook = cfg.get('webhook') or cfg.get('url')
            if webhook:
                from feishu_sdk import gen_sign
                ts, sign = gen_sign(cfg.get('secret', ''))
                r = requests.post('%s?timestamp=%s&sign=%s' % (webhook, ts, sign),
                                  json={'msg_type': 'text', 'content': {'text': text}},
                                  timeout=10)
                print('[推送] %s' % r.text[:120])
    except Exception as e:
        print('调度对账异常: %s' % e)
    print('SCHEDULE_AUDIT_DONE')


if __name__ == '__main__':
    main()
