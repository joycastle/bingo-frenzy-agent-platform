#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def verify(source, logs):
    logs.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OMB_', 'OPENAI_', 'ANTHROPIC_'))}
    fixture_log = logs / f'fixture-{int(time.time())}.log'
    cli = ['node', '--experimental-strip-types', 'scripts/control-omb.ts']
    records = []
    with fixture_log.open('w+') as out:
        fixture = subprocess.Popen(cli + ['launch'], cwd=source, env=env, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            handle = None
            for _ in range(120):
                try:
                    text = fixture_log.read_text()
                    start = text.find('{')
                    if start >= 0: handle, _ = json.JSONDecoder().raw_decode(text[start:])
                except (ValueError, json.JSONDecodeError): pass
                if handle and handle.get('ok'): break
                if fixture.poll() is not None: raise RuntimeError(f'隔离环境退出：{fixture_log}')
                time.sleep(0.5)
            if not handle or not handle.get('ok'): raise RuntimeError(f'隔离环境未启动：{fixture_log}')
            def call(*args):
                p = subprocess.run(cli + list(args) + ['--url', handle['url'], '--json'], cwd=source, env=env, text=True, capture_output=True, timeout=60)
                if p.returncode: raise RuntimeError(p.stdout + p.stderr)
                value = json.loads(p.stdout)
                records.append({'command': list(args), 'result': value})
                return value
            assert call('doctor')['ok']
            bot = call('new-bot', '--name', 'Deployment fixture')['bot']['id']
            call('send', '--bot', bot, '--text', 'hello')
            assert call('wait', '--bot', bot, '--timeout', '40')['status'] == 'settled'
            messages = call('messages', '--bot', bot, '--limit', '8')['messages']
            assert any(m.get('role') == 'bot' and m.get('text') == 'hello from fake claude' for m in messages)
            print('PASS: isolated create → send → settled → expected reply')
        finally:
            fixture.send_signal(signal.SIGINT)
            try: fixture.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(fixture.pid, signal.SIGTERM)
                fixture.wait(timeout=10)
            (logs / 'verification.json').write_text(json.dumps({'fixture': str(fixture_log), 'records': records}, ensure_ascii=False, indent=2))


if __name__ == '__main__': verify(Path(sys.argv[1]), Path(sys.argv[2]))
