#!/usr/bin/env python3
import json
import os
import plistlib
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PREFIX = 'com.joycastle.bingo-frenzy-agent-platform'


def plist(role, root, state, home):
    return {
        'Label': f'{PREFIX}.{role}',
        'ProgramArguments': ['/bin/bash', str(root / 'bin/run-service.sh'), role],
        'WorkingDirectory': str(root),
        'EnvironmentVariables': {'HOME': str(home), 'PATH': '/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin'},
        'RunAtLoad': True, 'KeepAlive': True, 'ThrottleInterval': 10,
        'StandardOutPath': str(state / 'logs' / f'{role}.log'),
        'StandardErrorPath': str(state / 'logs' / f'{role}.log'),
    }


def caddy_config(bind, web, server, webhook):
    import ipaddress
    ipaddress.ip_address(bind)
    for port in (web, server, webhook):
        if not 1024 <= int(port) <= 65535: raise ValueError('端口必须在 1024–65535 之间')
    if len({int(web), int(server), int(webhook)}) != 3: raise ValueError('三个监听端口必须不同')
    return f'''{{
    admin off
    auto_https off
}}
:{web} {{
    bind {bind}
    encode gzip
    handle /hooks/* {{
        reverse_proxy 127.0.0.1:{webhook}
    }}
    handle {{
        reverse_proxy 127.0.0.1:{server} {{
            flush_interval -1
        }}
    }}
}}
'''


def reload_agent(domain, label, target):
    subprocess.run(['launchctl', 'bootout', f'{domain}/{label}'], capture_output=True)
    for attempt in range(20):
        result = subprocess.run(['launchctl', 'bootstrap', domain, str(target)], capture_output=True, text=True)
        if result.returncode == 0: return
        # macOS launchd can return EIO while an asynchronous bootout is finishing.
        if result.returncode != 5 or attempt == 19:
            raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)
        time.sleep(0.5)


def main():
    root = Path(os.environ['BFA_ROOT'])
    state = Path(os.environ['STATE_DIR'])
    home = Path.home()
    domain = f'gui/{os.getuid()}'
    action = sys.argv[1]
    agents = home / 'Library/LaunchAgents'
    if action == 'stop':
        for role in ('edge', 'server'):
            subprocess.run(['launchctl', 'bootout', f'{domain}/{PREFIX}.{role}'], capture_output=True)
        return
    if action == 'status':
        for role in ('server', 'edge'):
            p = subprocess.run(['launchctl', 'print', f'{domain}/{PREFIX}.{role}'], capture_output=True, text=True)
            print(role + ': ' + ('已加载' if p.returncode == 0 else '未加载'))
        with urllib.request.urlopen(f"http://127.0.0.1:{os.environ['WEB_PORT']}/api/health", timeout=5) as r:
            print(r.read().decode())
        return
    if action != 'start': raise ValueError('usage: start|stop|status')
    current = Path(os.environ['CURRENT'])
    if not (current / '.omb-verified').is_file(): raise ValueError('请先运行 install.sh 完成构建和隔离验证')
    agents.mkdir(parents=True, exist_ok=True)
    (state / 'logs').mkdir(parents=True, exist_ok=True)
    config = state / 'Caddyfile'
    config.write_text(caddy_config(os.environ['WEB_BIND'], os.environ['WEB_PORT'], os.environ['OMB_PORT'], os.environ['OMB_WEBHOOK_PORT']))
    subprocess.run([str(state / 'runtime/caddy/caddy'), 'validate', '--config', str(config), '--adapter', 'caddyfile'], check=True)
    for role in ('server', 'edge'):
        target = agents / f'{PREFIX}.{role}.plist'
        pending = target.with_suffix('.next')
        pending.write_bytes(plistlib.dumps(plist(role, root, state, home)))
        pending.chmod(0o600)
        os.replace(pending, target)
        reload_agent(domain, f'{PREFIX}.{role}', target)
    error = None
    for _ in range(90):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{os.environ['WEB_PORT']}/api/health", timeout=2) as r:
                data = json.load(r)
            if data.get('app') == 'openmausbot':
                print('就绪：' + os.environ['OMB_PUBLIC_URL'])
                return
        except (OSError, urllib.error.URLError) as e:
            error = e
        time.sleep(1)
    raise RuntimeError(f'服务未就绪，请检查 {state}/logs：{error}')


if __name__ == '__main__': main()
