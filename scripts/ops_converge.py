# -*- coding: utf-8 -*-
"""
ops_converge.py — V13 波次1 运维收敛：停双心跳/双注册（任务计划侧）
原则（自动化专家§2/RACI）：本地与云端各保留一条权威链路，其余整点/重复任务停用。
  - 云端 workflow（错峰，权威）：07:53早报活体/08:43死信/09:07派生/12:23午报/20:43洞察/周日20:11周报/23:13巡检/23:43备份
  - 本地保留（权威）：Hermes_Gateway_agent1_business（gateway本体）、gateway_launcher（开机）、
                     Hermes_Gateway_agent6_scheduler（若正在被 Hermes 内部使用则保留）
  - 停用（双注册）：FeishuAssistant-Heartbeat-* ×3（整点心跳）、Hermes_Local_* ×5（整点任务，
                     与云端错峰任务重复）、FeishuAssistant-SystemHealthCheck（与云端巡检重复）
用法: python ops_converge.py [--dry-run] [--disable] [--report]
"""
import subprocess, json, sys, io

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

KEEP = {
    'Hermes_Gateway_agent1_business': 'gateway本体（权威）',
    'Hermes_Gateway_agent6_scheduler': 'Hermes内部调度（若在用）',
    'FeishuAssistant-CostSync': '成本同步（非重复）',
    'FeishuAssistant-DailyBackup': '每日备份（本地兜底）',
    'FeishuAssistant-PreferenceSync': '偏好同步（非重复）',
    'FeishuAssistant-ReviewNotify': '复习提醒（Disabled，保留disabled状态）',
    'Hermes_Model_SelfCheck': '模型自检（非重复）',
    'LocalCloudSync_Hourly': '本地云同步（非重复）',
    'MareBackup': 'Mare备份（非重复）',
}
DISABLE = {
    'FeishuAssistant-Heartbeat-Morning': '双心跳(整点) → 云端07:53活体',
    'FeishuAssistant-Heartbeat-Noon': '双心跳(整点) → 云端12:23午报',
    'FeishuAssistant-Heartbeat-Night': '双心跳(整点) → 云端20:43洞察',
    'FeishuAssistant-SystemHealthCheck': '双注册 → 云端23:13巡检',
    'Hermes_Local_MorningLearning': '双注册(07:00整点) → 云端07:53活体',
    'Hermes_Local_NoonSupervision': '双注册(12:00整点) → 云端12:23午报',
    'Hermes_Local_EveningReview': '双注册(21:00整点) → 云端20:43洞察',
    'Hermes_Local_WeeklyReport': '双注册(周日整点) → 云端周日20:11周报',
    'Hermes_Local_SystemHealthCheck': '双注册(08:00整点) → 云端23:13巡检',
}


def get_tasks():
    out = subprocess.run(['powershell', '-NoProfile', '-Command',
                          'Get-ScheduledTask | Select-Object -ExpandProperty TaskName'],
                         capture_output=True, text=True, timeout=60)
    return [t.strip() for t in out.stdout.splitlines() if t.strip()]


def main():
    dry = '--dry-run' in sys.argv
    disable = '--disable' in sys.argv
    tasks = get_tasks()
    found_keep = {t: KEEP[t] for t in tasks if t in KEEP}
    found_disable = {t: DISABLE[t] for t in tasks if t in DISABLE}
    missing_keep = {t for t in KEEP if t not in tasks}

    print('=== 保留任务（%d 个，权威链路） ===' % len(found_keep))
    for t, why in sorted(found_keep.items()):
        print('  KEEP %-40s %s' % (t, why))
    if missing_keep:
        print('  注意（不存在，无需处理）: %s' % ', '.join(sorted(missing_keep)))

    print('\n=== 待停用任务（%d 个，双注册/整点心跳） ===' % len(found_disable))
    for t, why in sorted(found_disable.items()):
        print('  STOP %-40s %s' % (t, why))

    if disable and not dry:
        for t in found_disable:
            subprocess.run(['powershell', '-NoProfile', '-Command',
                            'Disable-ScheduledTask -TaskName "%s"' % t],
                           capture_output=True, timeout=60)
            print('  [已停用] %s' % t)
        print('\n收敛完成：%d 个任务已停用' % len(found_disable))
    elif dry:
        print('\n[dry-run] 未执行停用；加 --disable 真正停用')


if __name__ == '__main__':
    main()
