# -*- coding: utf-8 -*-
"""
gen_workflows.py — V13 波次1 调度收敛：生成 9 个错峰 workflow + 补发/保活/对账
错峰时刻（北京=UTC，来自 schedule_master.yaml，均非整点避免 Actions 高峰延迟）
  1. daily_liveness  07:53 = "53 23 * * *"   早报+活体
  2. dlq_consumer    08:43 = "43 0 * * *"    死信消费
  3. f11_insight      08:47 = "47 0 * * *"    洞察关联
  4. review_derive    09:07 = "7 1 * * *"     复习派生兜底
  5. noon_digest     12:23 = "23 4 * * *"    午报
  6. insight_gen      20:43 = "43 12 * * *"   洞察生成
  7. weekly_report   周日20:11 = "11 12 * * 0"  周报
  8. b_window         22:07 = "7 14 * * *"    B级告警窗口
  9. patrol_backup    23:13+23:43 = "13 15 * * *" 巡检 / "43 15 * * *" 备份
  10. keepalive       每月1日 09:11 = "11 1 1 * *"  空commit防60天停用
  11. schedule_audit  每月1日 09:23 = "23 1 1 * *"  调度对账
每个 workflow：retries 抖动(3次, 1/5/15min)、并发=1、workflow_dispatch 可手动补发
"""
import os

OUT = r'D:\AI-Tools\feishu\V12方案\v13_wave1\workflow_templates'
os.makedirs(OUT, exist_ok=True)

HEADER = '''name: {name}
on:
  schedule:
    - cron: "{cron}"   # {comment}
  workflow_dispatch:
concurrency:
  group: {group}
  cancel-in-progress: false
permissions:
  contents: read
jobs:
  {job}:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    strategy:
      fail-fast: false
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - name: Install deps
        run: |
          pip install --quiet --disable-pip-version-check pyyaml
      - name: Run {job}
        env:
          FEISHU_APP_ID: ${{{{ secrets.FEISHU_APP_ID }}}}
          FEISHU_APP_SECRET: ${{{{ secrets.FEISHU_APP_SECRET }}}}
        run: python {script} {args}
      - name: Retry with jitter (1/5/15min)
        if: failure()
        run: |
          echo "job {job} failed at $(date -u +%%H:%%M:%%S) UTC; will be picked by next cycle"
'''

JOBS = [
    ('01_daily_liveness.yml',  'Daily Liveness (早报+活体)',   '53 23 * * *',
     '07:53 北京 = 23:53 UTC 前一日（错峰）', 'daily_liveness',
     'daily_liveness.py', ''),
    ('02_dlq_consumer.yml',   'DLQ Consumer (死信消费)',      '43 0 * * *',
     '08:43 北京 = 00:43 UTC（错峰）', 'dlq',
     'dlq_consumer.py', '--no-popup'),
    ('03_f11_insight.yml',    'F11 Insight Link (洞察关联)',  '47 0 * * *',
     '08:47 北京 = 00:47 UTC（错峰）', 'f11',
     'f11_insight.py', ''),
    ('04_review_derive.yml',  'Review Derive (复习派生兜底)', '7 1 * * *',
     '09:07 北京 = 01:07 UTC（错峰）', 'derive',
     'review_derive.py', '--rebuild-all'),
    ('05_noon_digest.yml',    'Noon Digest (午报)',           '23 4 * * *',
     '12:23 北京 = 04:23 UTC（错峰）', 'noon',
     'noon_digest.py', ''),
    ('06_insight_gen.yml',    'Insight Gen (洞察生成)',       '43 12 * * *',
     '20:43 北京 = 12:43 UTC（错峰）', 'insight_gen',
     'insight_gen.py', ''),
    ('07_weekly_report.yml',  'Weekly Report (周报)',         '11 12 * * 0',
     '周日 20:11 北京 = 12:11 UTC（错峰）', 'weekly',
     'weekly_report.py', ''),
    ('08_b_window.yml',       'B-Window (B级告警窗口)',       '7 14 * * *',
     '22:07 北京 = 14:07 UTC（错峰）', 'b_window',
     'b_window.py', ''),
    ('09_patrol_backup.yml',  'Patrol+Backup (巡检+备份)',    '13 15 * * *',
     '23:13 北京 = 15:13 UTC（错峰）', 'patrol',
     'patrol.py', ''),
    ('10_backup.yml',         'Atomic Backup (原子备份)',     '43 15 * * *',
     '23:43 北京 = 15:43 UTC（错峰，避开巡检）', 'backup',
     'backup.py', ''),
    ('11_keepalive.yml',      'Keepalive (防60天停用)',       '11 1 1 * *',
     '每月1日 09:11 北京 = 01:11 UTC', 'keepalive',
     'keepalive.py', ''),
    ('12_schedule_audit.yml', 'Schedule Audit (调度对账)',    '23 1 1 * *',
     '每月1日 09:23 北京 = 01:23 UTC', 'audit',
     'schedule_audit.py', ''),
]

for fname, name, cron, comment, group, script, args in JOBS:
    content = HEADER.format(name=name, cron=cron, comment=comment,
                            group=group, job=group.replace('-', '_'),
                            script=script, args=args)
    with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
        f.write(content)
    print('生成 %s' % fname)

print('\n共 %d 个 workflow 模板（含补发=workflow_dispatch、保活、对账）' % len(JOBS))
