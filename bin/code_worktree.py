#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


def repositories(raw):
    data = json.loads(raw or '{}')
    if not isinstance(data, dict):
        raise ValueError('GIT_REPOSITORIES_JSON 必须是 alias → {url, branch} 对象')
    for alias, config in data.items():
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', alias) or not isinstance(config, dict):
            raise ValueError('仓库别名或配置无效')
        url = config.get('url', '')
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'github.com' or parsed.query or parsed.fragment
                or not re.fullmatch(r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git', parsed.path)):
            raise ValueError('仓库 URL 须为不含凭据的 https://github.com/owner/repo.git')
        if not isinstance(config.get('branch'), str) or not config['branch']:
            raise ValueError('每个仓库须指定默认 branch')
    return data


class Worktrees:
    def __init__(self, root, registry, runner):
        self.root = Path(root).resolve()
        self.registry = registry
        self.runner = runner
        self.root.mkdir(parents=True, exist_ok=True)

    def git(self, *args):
        result = self.runner(list(args))
        if result.returncode:
            raise RuntimeError('Git 操作失败：' + result.stderr.strip()[-1800:])
        return result.stdout.strip()

    def entries(self):
        index = self.root/'index.json'
        return json.loads(index.read_text()) if index.exists() else []

    def publish(self, entries):
        pending = self.root/'index.next.json'
        pending.write_text(json.dumps(entries, ensure_ascii=False, indent=2)+'\n')
        os.replace(pending, self.root/'index.json')
        lines = ['# 代码工作树', '', '每个仓库、分支固定目录；查询前同步远端并丢弃分析缓存的本地改动。此列表不代表线上部署版本。', '',
                 '| 仓库 | 分支 | 提交 SHA | 工作树路径 | 最近使用（UTC） |', '|---|---|---|---|---|']
        cards = []
        for e in sorted(entries, key=lambda x: (x['repository'], x['branch'], x['createdAt'])):
            cells = [e['repository'], e['branch'], e['sha'], e['path'], e['lastUsedAt']]
            lines.append('| '+' | '.join(c.replace('|', '\\|') for c in cells)+' |')
            repo, branch, sha, path, used = map(html.escape, cells)
            cards.append(f'<tr><td>{repo}</td><td>{branch}</td><td><code>{sha[:12]}</code></td><td><code>{path}</code></td><td>{used}</td></tr>')
        (self.root/'WORKTREES.md').write_text('\n'.join(lines)+'\n')
        (self.root/'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>代码工作树</title><style>body{font:15px/1.6 system-ui,sans-serif;color:#1f2937;background:#f5f7fa;margin:32px}h1{font-size:26px}table{border-collapse:collapse;background:white;width:100%}td,th{padding:12px;text-align:left;border-bottom:1px solid #e5e7eb;vertical-align:top}th{background:#eaf0f7}code{font-size:12px;overflow-wrap:anywhere}p{color:#526174}.scroll{overflow:auto}</style><h1>代码工作树</h1><p>每个仓库、分支固定目录；查询前更新到远端，强推后也重新对齐。分析缓存中的本地改动和临时文件不保留。</p><div class="scroll"><table><thead><tr><th>仓库</th><th>分支</th><th>提交</th><th>工作树目录</th><th>最近使用（UTC）</th></tr></thead><tbody>'''+''.join(cards)+'</tbody></table></div></html>')

    def open(self, alias, branch=None):
        if alias not in self.registry:
            raise ValueError('仓库不在 GIT_REPOSITORIES_JSON 中')
        config = self.registry[alias]
        branch = branch or config['branch']
        if branch.startswith('-') or branch == 'HEAD' or not branch:
            raise ValueError('请使用明确分支名')
        self.git('check-ref-format', 'refs/heads/'+branch)
        mirror = self.root/'mirrors'/f'{alias}.git'
        mirror.parent.mkdir(exist_ok=True)
        if not mirror.exists():
            self.git('init', '--bare', str(mirror))
            self.git('--git-dir='+str(mirror), 'remote', 'add', 'origin', config['url'])
        elif self.git('--git-dir='+str(mirror), 'config', '--get', 'remote.origin.url') != config['url']:
            raise ValueError('缓存远端与配置不符，保留原目录，请管理员核查')
        remote_ref = 'refs/heads/'+branch
        remote = self.git('--git-dir='+str(mirror), 'ls-remote', '--exit-code', 'origin', remote_ref)
        matches = [line.split() for line in remote.splitlines() if line.split()[-1:] == [remote_ref]]
        if len(matches) != 1 or not re.fullmatch(r'[0-9a-f]{40,64}', matches[0][0]):
            raise ValueError('未找到唯一的远端分支，未复用旧版本')
        sha = matches[0][0]
        self.git('--git-dir='+str(mirror), 'fetch', '--depth=1', '--filter=blob:none', '--no-tags', 'origin', sha)
        slug = re.sub(r'[^A-Za-z0-9_.-]', '-', branch)[:70]
        branch_hash = hashlib.sha256(branch.encode()).hexdigest()[:6]
        dirname = urlsplit(config['url']).path.rsplit('/', 1)[1][:-4]+f'@{slug}'
        destination = self.root/'worktrees'/dirname
        destination.parent.mkdir(exist_ok=True)
        entries = self.entries()
        if any(e['path'] == str(destination) and (e['alias'] != alias or e['branch'] != branch) for e in entries):
            destination = destination.with_name(dirname+'-'+branch_hash)
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        existing = next((e for e in entries if e['alias'] == alias and e['branch'] == branch), None)
        if existing:
            if existing['path'] != str(destination) or not destination.is_dir():
                raise ValueError('已记录的工作树缺失或路径不符，请管理员核查')
            if destination.is_symlink():
                raise ValueError('拒绝跟随工作树目录软链')
            common = self.git('-C', str(destination), 'rev-parse', '--git-common-dir')
            if (destination/common).resolve() != mirror.resolve():
                raise ValueError('工作树不属于受管镜像，未修改')
            self.git('-C', str(destination), 'reset', '--hard', sha)
            self.git('-C', str(destination), 'clean', '-fdx')
            existing['sha'] = sha
            existing['lastUsedAt'] = now
            entry = existing
        else:
            if destination.exists() or destination.is_symlink():
                raise ValueError('工作树目录已存在但未登记，未覆盖')
            self.git('--git-dir='+str(mirror), 'worktree', 'add', '--detach', str(destination), sha)
            entry = {'alias':alias, 'repository':urlsplit(config['url']).path.lstrip('/').removesuffix('.git'), 'branch':branch, 'sha':sha,
                     'path':str(destination), 'createdAt':now, 'lastUsedAt':now}
            entries.append(entry)
        self.publish(entries)
        return entry

    def remove(self, alias, branch):
        entries = self.entries()
        entry = next((e for e in entries if e['alias'] == alias and e['branch'] == branch), None)
        if not entry:
            raise ValueError('工作树未登记，未删除')
        destination = Path(entry['path'])
        mirror = self.root/'mirrors'/f'{alias}.git'
        if destination.is_symlink() or destination.parent != self.root/'worktrees':
            raise ValueError('拒绝清理受管目录以外的路径')
        common = self.git('-C', str(destination), 'rev-parse', '--git-common-dir')
        if (destination/common).resolve() != mirror.resolve():
            raise ValueError('工作树不属于受管镜像，未删除')
        self.git('--git-dir='+str(mirror), 'worktree', 'remove', str(destination))
        self.publish([e for e in entries if e is not entry])
        return {'removed':str(destination), 'branch':branch}


def main():
    parser = argparse.ArgumentParser(description='按仓库和分支维护分析工作树；更新时强制对齐远端、丢弃受管缓存的本地改动；不推送')
    sub = parser.add_subparsers(dest='command', required=True)
    open_parser = sub.add_parser('open')
    open_parser.add_argument('alias')
    open_parser.add_argument('--branch')
    remove_parser = sub.add_parser('remove', help='确认无人使用后清理已登记工作树；不强制删除脏工作树')
    remove_parser.add_argument('alias')
    remove_parser.add_argument('--branch', required=True)
    sub.add_parser('list')
    sub.add_parser('repos')
    args = parser.parse_args()
    registry = repositories(os.environ.get('GIT_REPOSITORIES_JSON', ''))
    if args.command == 'repos':
        print(json.dumps(registry, ensure_ascii=False, indent=2)); return
    root = Path(os.environ['STATE_DIR'])/'sources'
    wrapper = os.environ['BFA_GITHUB_COMMAND']
    def run(arguments):
        return subprocess.run(['/bin/bash', wrapper, 'git', '-c', 'core.hooksPath=/dev/null', *arguments], capture_output=True, text=True, timeout=600)
    manager = Worktrees(root, registry, run)
    with (root/'.worktree.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise RuntimeError('另一个工作树操作仍在进行，请稍后重试')
        if args.command == 'open':
            result = manager.open(args.alias, args.branch)
        elif args.command == 'remove':
            result = manager.remove(args.alias, args.branch)
        else:
            result = manager.entries(); manager.publish(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
