# -*- coding: utf-8 -*-
"""
gateway_launcher.py — V13 gateway 启动器（波次1·可用性组，Python launcher 替代 VBS/BAT）
方案定稿（自动化专家§3）：
  1) 任务计划「启动时」触发（非登录时），解决远程桌面重启后 gateway 不拉起
  2) 开机等待网络最多 120s（探测外网+本地飞书可达）
  3) 配置 render：从模板渲染 .env（先渲染后启动，对"更新重置配置"免疫）
  4) 幂等：端口已监听则跳过启动（防止看门狗与 launcher 双拉）
用法: python gateway_launcher.py [--wait-network 120] [--render-only] [--launch-only]
"""
import os, sys, io, time, socket, subprocess, json, urllib.request

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', write_through=True)
except Exception:
    pass

HERMES_HOME = r'C:\Users\Administrator\AppData\Local\hermes'
ENV_FILE = os.path.join(HERMES_HOME, '.env')
ENV_TEMPLATE = os.path.join(HERMES_HOME, '.env.template')
HERMES_DIR = r'D:\AI-Tools\hermes-hudui'
HERMES_EXE = os.path.join(HERMES_DIR, '.venv', 'Scripts', 'hermes-hudui.exe')
PORT = int(os.environ.get('HERMES_PORT', '7860'))   # 与 AnythingLLM(3001) 隔离
HEALTH_URL = 'http://127.0.0.1:%d/api/health' % PORT
LOG = r'D:\AI-Tools\shared\logs\gateway_launcher.log'


def log(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    line = '[%s] %s' % (time.strftime('%Y-%m-%d %H:%M:%S'), msg)
    try:
        print(line)
    except Exception:
        pass
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def port_open(port, host='127.0.0.1'):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def network_ready(timeout=120):
    """探测外网 DNS + 飞书开放平台可达，最多等 timeout 秒。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen('https://open.feishu.cn', timeout=5)
            return True
        except Exception:
            time.sleep(5)
    return False


def render_env():
    """配置即代码：模板 .env.template → 渲染 .env（保留现有值，模板变更合并）。"""
    if not os.path.exists(ENV_TEMPLATE):
        log('模板不存在 %s，跳过 render（无操作）' % ENV_TEMPLATE)
        return True
    current = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding='utf-8'):
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                current[k.strip()] = v.strip()
    out = []
    changed = 0
    for line in open(ENV_TEMPLATE, encoding='utf-8'):
        s = line.strip()
        if s and not s.startswith('#') and '=' in s:
            k = s.split('=', 1)[0].strip()
            if k in current:          # 保留现网值（密钥不覆盖）
                out.append('%s=%s' % (k, current[k]))
                continue
            changed += 1              # 模板新增键
        out.append(line.rstrip('\n'))
    if changed:
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')
        log('render 完成：新增模板键 %d 个' % changed)
        return True
    log('render 无变化')
    return True


def launch():
    if port_open(PORT):
        log('端口 %d 已在监听，跳过启动（幂等）' % PORT)
        return True
    if not os.path.exists(HERMES_EXE):
        log('hermes-hudui.exe 不存在: %s' % HERMES_EXE)
        return False
    env = dict(os.environ)
    env['HERMES_HOME'] = HERMES_HOME
    # CREATE_NO_WINDOW=0x08000000；脱离会话，任务计划进程退出后继续存活
    flags = subprocess.CREATE_NO_WINDOW | getattr(subprocess, 'DETACHED_PROCESS', 0)
    proc = subprocess.Popen(
        [HERMES_EXE, '--port', str(PORT)],
        cwd=HERMES_DIR, env=env, creationflags=flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        close_fds=True)
    log('已拉起 gateway pid=%d，等待健康检查' % proc.pid)
    # 等待健康端点（最多 60s）
    for _ in range(60):
        time.sleep(1)
        if port_open(PORT):
            try:
                urllib.request.urlopen(HEALTH_URL, timeout=3)
                log('gateway 健康检查通过')
                return True
            except Exception:
                continue
    log('gateway 60s 内未通过健康检查')
    return False


def main():
    args = sys.argv[1:]
    wait = 120
    if '--wait-network' in args:
        wait = int(args[args.index('--wait-network') + 1])
    if not network_ready(wait):
        log('网络 %ds 内未就绪，仍尝试启动（gateway 自身可重试）' % wait)
    render_env()
    if '--render-only' in args:
        return 0
    ok = launch()
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
