# -*- coding: utf-8 -*-
"""
local_alert.py — A 类故障本地第二通道（飞书消息之外的兜底）
1) 强制落盘 alerts.log（飞书不可用时仍有证据）
2) 非阻塞 Windows 弹窗（best-effort，失败绝不影响主流程）
3) 飞书机器人消息通道（webhook 告警，best-effort）
"""
import os, sys, subprocess, json, urllib.request
from datetime import datetime

LOG_DIR = r'D:\AI-Tools\shared\logs'
LOG_PATH = os.path.join(LOG_DIR, 'alerts.log')
BOT_CONFIG = r'D:\AI-Tools\feishu\local_cron_tasks\feishu_bot_config.json'


def log_alert(level, title, detail=''):
    os.makedirs(LOG_DIR, exist_ok=True)
    line = '[%s] [%s] %s | %s\n' % (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), level, title, str(detail)[:500])
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line)
    return line


def popup(title, message, timeout_sec=15):
    """非阻塞弹窗：独立进程调用 user32.MessageBox，超时自动关闭，不阻塞消费器。"""
    code = (
        "import ctypes,sys;"
        "u=ctypes.windll.user32;"
        "u.MessageBoxTimeoutW(0,sys.argv[2],sys.argv[1],0x30|0x0,0,%d*1000)"
        % timeout_sec)
    try:
        subprocess.Popen([sys.executable, '-c', code, title, str(message)[:400]],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def feishu_msg(title, detail=''):
    """飞书机器人 webhook 发告警（best-effort，失败仅告警不影响主流程）。"""
    try:
        cfg = json.load(open(BOT_CONFIG, encoding='utf-8'))
        webhook = cfg.get('webhook')
        if not webhook:
            return False
        body = json.dumps({'msg_type': 'text',
                           'content': {'text': '【A类告警】%s\n%s' % (title, str(detail)[:400])}},
                          ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(webhook, data=body,
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.loads(r.read())
        return d.get('code') == 0 or d.get('StatusCode') == 0
    except Exception:
        return False


def dual_alert(title, detail='', do_popup=True, notify_feishu=True):
    """A 类双通道：本地落盘 + 弹窗（可选）+ 飞书消息（可选）；返回落盘行。"""
    line = log_alert('A', title, detail)
    if do_popup:
        popup('A类故障-' + title, detail)
    if notify_feishu:
        feishu_msg(title, detail)
    return line
