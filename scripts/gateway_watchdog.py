# -*- coding: utf-8 -*-
"""
gateway_watchdog.py — V13 gateway 看门狗（波次2 升级：双服务守护）
方案定稿（自动化专家§3 + 波次2 实测教训）：每 10min 探测 Hermes(7860) + AnythingLLM(3001)，
  各自失败按 1/5/15min 退避拉起（间隔递增），连续 3 次失败停拉并 A 类告警。
  恢复成功则重置失败计数。实测发现 AnythingLLM 也会掉，必须纳入守护。
用法: python gateway_watchdog.py [--loop] [--once] [--reset]
"""
import os, sys, io, time, json, subprocess, urllib.request

sys.path.insert(0, r'D:\AI-Tools\shared')
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass
from local_alert import log_alert

STATE = r'D:\AI-Tools\shared\state\gateway_watchdog.json'
LOG = r'D:\AI-Tools\shared\logs\gateway_watchdog.log'

SERVICES = {
    'hermes': {
        'url': 'http://127.0.0.1:7860/api/health',
        'exe': r'D:\AI-Tools\hermes-hudui\.venv\Scripts\hermes-hudui.exe',
        'cwd': r'D:\AI-Tools\hermes-hudui',
        'env_home': 'C:\\Users\\Administrator\\AppData\\Local\\hermes',
        'port': '7860',
    },
    'anyllm': {
        'url': 'http://127.0.0.1:3001/api/ping',
        'exe': r'C:\Users\Administrator\AppData\Local\Programs\AnythingLLM\AnythingLLM.exe',
        'cwd': r'C:\Users\Administrator\AppData\Local\Programs\AnythingLLM',
        'env_home': None,
        'port': None,
    },
}
BACKOFF = (1, 5, 15)          # 分钟：第1/2/3次失败的等待
MAX_FAIL = 3


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        print(line)
    except Exception:
        pass
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def health_ok(cfg):
    try:
        urllib.request.urlopen(cfg['url'], timeout=5)
        return True
    except Exception:
        return False


def load_state():
    try:
        with open(STATE, encoding='utf-8') as f:
            st = json.load(f)
        if 'services' not in st:
            st['services'] = {}
        return st
    except Exception:
        return {'services': {k: {'fail_streak': 0, 'paused': False} for k in SERVICES}}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def relaunch(name, cfg):
    """拉起服务；返回是否成功。"""
    try:
        if name == 'hermes':
            env = dict(os.environ)
            env['HERMES_HOME'] = cfg['env_home']
            flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, 'DETACHED_PROCESS', 0)
            subprocess.Popen([cfg['exe'], '--port', cfg['port']],
                             cwd=cfg['cwd'], env=env, creationflags=flags,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True)
        else:
            # 桌面应用：用 ShellExecute 方式启动
            subprocess.Popen(['cmd', '/c', 'start', '', cfg['exe']],
                             cwd=cfg['cwd'], close_fds=True)
    except Exception as e:
        log('%s 拉起异常: %s' % (name, e))
        return False
    for _ in range(30):        # 等 30s
        time.sleep(1)
        if health_ok(cfg):
            return True
    return False


def tick(st):
    # 兼容旧版状态结构（顶层 fail_streak → services.hermes.fail_streak）
    if 'services' not in st:
        st['services'] = {}
        st['services']['hermes'] = {'fail_streak': st.get('fail_streak', 0),
                                    'paused': st.get('paused', False)}
        st['services']['anyllm'] = {'fail_streak': 0, 'paused': False}
    for name, cfg in SERVICES.items():
        sv = st['services'].setdefault(name, {'fail_streak': 0, 'paused': False})
        if sv.get('paused'):
            log('%s 已熔断暂停，跳过本轮' % name)
            continue
        if health_ok(cfg):
            if sv['fail_streak']:
                log('%s 已恢复，重置失败计数' % name)
            sv['fail_streak'] = 0
            continue
        sv['fail_streak'] += 1
        n = sv['fail_streak']
        log('%s 探测失败 #%d（%s 不可达）' % (name, n, cfg['url']))
        if n > MAX_FAIL:
            sv['paused'] = True
            log_alert('A', 'gateway_watchdog',
                      '%s 连续 %d 次拉起失败，已熔断暂停；需人工检查 %s'
                      % (name, n - 1, cfg['exe']))
            log('%s 连续失败达上限，熔断暂停（A类告警已发）' % name)
            continue
        wait_min = BACKOFF[min(n - 1, len(BACKOFF) - 1)]
        log('%s 按 %dmin 退避后拉起（第 %d 次）' % (name, wait_min, n))
        time.sleep(min(wait_min, 2) * 60)   # 测试可注入小值；生产按分钟
        if relaunch(name, cfg):
            log('%s 第 %d 次拉起成功' % (name, n))
            sv['fail_streak'] = 0
        else:
            log('%s 第 %d 次拉起仍未健康' % (name, n))
    save_state(st)
    return st


def main():
    args = sys.argv[1:]
    st = load_state()
    if '--reset' in args:
        st = {'services': {k: {'fail_streak': 0, 'paused': False} for k in SERVICES}}
        save_state(st)
        print('看门狗状态已重置')
        return 0
    if '--once' in args:
        tick(st)
        return 0
    while True:
        st = tick(st)
        time.sleep(600)   # 每 10min


if __name__ == '__main__':
    main()
