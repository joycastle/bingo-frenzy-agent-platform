#!/usr/bin/env python3
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from urllib.parse import urlsplit


def main():
    p = argparse.ArgumentParser(description='将仓库中按 Bot 分组的单文件 Skill 安装到指定本机 MausBot')
    p.add_argument('--url', required=True)
    p.add_argument('--bot', required=True)
    p.add_argument('--directory', required=True, type=Path)
    p.add_argument('--replace', action='store_true', help='备份后替换本平台安装的同名 Skill')
    p.add_argument('--backup-directory', type=Path, default=Path.home()/'.local/share/bingo-frenzy-agent-platform/skill-backups')
    args = p.parse_args()
    url = urlsplit(args.url)
    if url.scheme != 'http' or url.hostname not in ('127.0.0.1','localhost') or url.username or url.password or url.path not in ('','/') or url.query or url.fragment:
        p.error('--url 必须是显式本机 HTTP 服务地址')
    if not re.fullmatch(r'[A-Za-z0-9-]+',args.bot): p.error('Bot ID 无效')
    base = args.url.rstrip('/')
    def api(method,path,body=None):
        request=urllib.request.Request(base+path,method=method,headers={'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
        with urllib.request.urlopen(request,timeout=30) as response:return json.load(response)
    bot=next((b for b in api('GET','/api/bots?messages=0')['bots'] if b['id']==args.bot),None)
    if bot is None or bot.get('busy') or bot.get('waitingForTeammates'):
        p.error('Bot 不存在或仍在运行任务')
    skills=sorted(args.directory.glob('*/SKILL.md'))
    if not skills:p.error('目录里没有 Skill')
    for file in skills:
        extras=[f for f in file.parent.rglob('*') if f.is_file() and f != file and f.relative_to(file.parent).parts[0] != 'agents']
        if extras:p.error('当前单文件安装入口不能忽略支持文件，请使用完整 Skill 包安装')
    for file in skills:
        text=file.read_text();name=file.parent.name
        path=f'/api/bots/{args.bot}/skills/{name}'
        listing=api('GET',f'/api/bots/{args.bot}/skills')['skills']
        existing=next((s for s in listing if s['name']==name),None)
        source='local-platform:'+name
        previous=api('GET',path)['text'] if existing else None
        if existing and previous==text:
            if not existing['enabled']:api('PATCH',path,{'enabled':True})
        else:
            old=None
            if existing:
                if not args.replace:p.error('同名 Skill 已存在；更新请使用 --replace，先备份再替换')
                if existing.get('source')!=source:p.error('同名 Skill 不是本平台安装，未替换')
                backup=args.backup_directory/args.bot/name/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
                backup.mkdir(parents=True,mode=0o700)
                (backup/'SKILL.md').write_text(previous);(backup/'SKILL.md').chmod(0o600)
                (backup/'metadata.json').write_text(json.dumps(existing,ensure_ascii=False,indent=2));(backup/'metadata.json').chmod(0o600)
                old={'name':name,'description':existing.get('description',''),'source':source,'text':previous,'enabled':existing['enabled']}
                api('DELETE',path)
            try:
                api('POST',f'/api/bots/{args.bot}/skill-template',{'name':name,'description':'','source':source,'text':text,'enabled':True})
            except Exception:
                if old:api('POST',f'/api/bots/{args.bot}/skill-template',old)
                raise
        saved=api('GET',path)['text']
        if saved!=text:raise RuntimeError('Skill 内容与仓库不一致')
        listing=api('GET',f'/api/bots/{args.bot}/skills')['skills']
        if not any(s['name']==name and s['enabled'] for s in listing):raise RuntimeError('Skill 未启用')
        print(json.dumps({'bot':args.bot,'skill':name,'enabled':True,'sha256':hashlib.sha256(text.encode()).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()
