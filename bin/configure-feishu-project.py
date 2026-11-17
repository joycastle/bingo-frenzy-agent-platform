#!/usr/bin/env python3
"""停服后安装不含密钥的单 Bot MCP 配置；默认关闭，连接验证后再启用。"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import time


def configure(data, platform, bot, port, wait_stop=0):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', bot):
        raise ValueError('Bot ID 无效')
    deadline = time.monotonic()+wait_stop
    while True:
        with socket.socket() as probe:
            probe.settimeout(1)
            if probe.connect_ex(('127.0.0.1', port)) != 0:
                break
        if time.monotonic() >= deadline:
            raise ValueError('请先确认没有运行中的任务并停止 MausBot 服务')
        time.sleep(.2)
    if not (data/'bots'/bot).is_dir():
        raise ValueError('目标 Bot 目录不存在')
    file = data/'config.json'
    original = file.read_bytes()
    config = json.loads(original)
    entry = json.loads((platform/'bots/code-reader/mcp/feishu-project.json').read_text())['mcpServers']['feishu-project']
    entry['bot'] = bot
    entry['args'] = [str(platform/'bin/feishu-project-mcp')]
    current = config.get('mcpServers', {}).get('feishu-project')
    if current is not None:
        if {**current, 'enabled': False} != entry:
            raise ValueError('同名 MCP 配置不同，未覆盖，请先核对')
        return False
    backup = data/'backups'/('feishu-project-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'))
    backup.mkdir(parents=True, mode=0o700)
    (backup/'config.json').write_bytes(original)
    (backup/'config.json').chmod(0o600)
    config.setdefault('mcpServers', {})['feishu-project'] = entry
    pending = file.with_name('config.feishu-project.next.json')
    with pending.open('x', encoding='utf8') as out:
        pending.chmod(0o600)
        out.write(json.dumps(config, ensure_ascii=False, indent=2)+'\n')
    os.replace(pending, file)
    return True


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bot', required=True)
    p.add_argument('--data-dir', type=Path, default=Path.home()/'.openmausbot')
    p.add_argument('--port', type=int, default=8799)
    p.add_argument('--wait-stop', type=int, choices=range(0,61), default=0, metavar='秒', help='等待异步停服，最多 60 秒')
    args = p.parse_args()
    try:
        changed = configure(args.data_dir.resolve(), Path(__file__).resolve().parents[1], args.bot, args.port, args.wait_stop)
        print('MCP 已配置但保持关闭，请启动后测试再启用。' if changed else '同名配置一致，保留现有启用状态。')
    except (OSError, ValueError) as e:
        p.exit(1, str(e)+'\n')
