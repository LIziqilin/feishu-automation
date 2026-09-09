# -*- coding: utf-8 -*-
"""
probe30.py — V13 本机 30 分钟探针（波次1·发现能力组，方案§4.3）
每 30 分钟探测三路可用性：
  1) Hermes gateway /health
  2) 飞书 tenant_access_token 可达（开放平台连通）
  3) DeepSeek is_available（可选）
任一 A 类失败 → 本地 alerts.log + 飞书告警双通道（local_alert.dual_alert）
全部正常 → 静默（不刷日志，避免噪声）
用法: python probe30.py [--once] [--notify-feishu]
"""
import os, sys, io, time, json, urllib.request

_LOCAL_SHARED = r'D:\AI-Tools\shared'
if os.path.isdir(_LOCAL_SHARED):
    sys.path.insert(0, _LOCAL_SHARED)
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from feishu_sdk import FeishuClient, TABLES
from local_alert import dual_alert

STATE = r'D:\AI-Tools\shared\state\probe30.json'
PROBE_LOG = r'D:\AI-Tools\shared\logs\probe30.log'
GATEWAY_URL = 'http://127.0.0.1:%d/api/health' % int(os.environ.get('HERMES_PORT', '7860'))
ANYLLM_URL = 'http://127.0.0.1:3001/api/ping'   # AnythingLLM 桌面端（区分于 Hermes）


def log(msg):
    os.makedirs(os.path.dirname(PROBE_LOG), exist_ok=True)
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        print(line)
    except Exception:
        pass
    with open(PROBE_LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def probe_gateway():
    try:
        urllib.request.urlopen(GATEWAY_URL, timeout=5)
        return True
    except Exception:
        return False


def probe_anyllm():
    """AnythingLLM 桌面端（3001 /api/ping），单独探测不混淆 Hermes。"""
    try:
        urllib.request.urlopen(ANYLLM_URL, timeout=5)
        return True
    except Exception:
        return False


def probe_feishu():
    try:
        c = FeishuClient()
        tok = c.get_token()
        return bool(tok) and len(tok) > 20
    except Exception:
        return False


def probe_deepseek():
    """DeepSeek key 可用性：读 anythingllm .env，走 /models 探测（401=key无效/未strip引号）。"""
    try:
        env = r'C:\Users\Administrator\AppData\Roaming\anythingllm-desktop\storage\.env'
        key = None
        for line in open(env, encoding='utf-8'):
            if line.startswith('DEEPSEEK_API_KEY='):
                key = line.strip().split('=', 1)[1].strip().strip("'").strip('"')
                break
        if not key:
            return True   # 未配置则不算故障
        req = urllib.request.Request(
            'https://api.deepseek.com/models',
            headers={'Authorization': 'Bearer %s' % key})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


def write_heartbeat(c, ok):
    """心跳收敛：probe30 为唯一本地心跳来源（替代已停用的整点心跳），错峰写。"""
    try:
        c.create_record(TABLES['系统心跳'], {
            '心跳时间': int(time.time() * 1000),
            '来源': 'probe30-本地',
            '状态': '正常' if ok else '异常',
            '备注': '30min探针(错峰)' if ok else '30min探针异常，见logs/alerts.log',
        })
    except Exception:
        pass


def run_once(notify_feishu=True):
    results = {
        'hermes_gateway': probe_gateway(),
        'anyllm': probe_anyllm(),
        'feishu': probe_feishu(),
        'deepseek': probe_deepseek(),
    }
    ok = all(results.values())
    # 心跳写飞书（新来源，错峰；保持心跳表单来源收敛）
    try:
        c = FeishuClient()
        write_heartbeat(c, ok)
    except Exception:
        pass
    # 静默成功：仅当有失败时才落盘告警（每30min一次也控制量）
    if not ok:
        detail = ', '.join('%s=%s' % (k, 'OK' if v else 'FAIL') for k, v in results.items())
        msg = '30min探针异常: %s' % detail
        log(msg)
        dual_alert('probe30', msg, notify_feishu=notify_feishu)
    else:
        log('30min探针 三路正常')
    return results


def main():
    args = sys.argv[1:]
    notify = '--no-notify' not in args
    if '--once' in args:
        r = run_once(notify)
        print(json.dumps(r, ensure_ascii=False))
        return 0
    while True:
        run_once(notify)
        time.sleep(1800)   # 30min


if __name__ == '__main__':
    main()
