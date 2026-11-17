#!/usr/bin/env python3
import argparse
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
        api('POST',f'/api/bots/{args.bot}/skill-template',{'name':name,'description':'','source':'local-platform:'+name,'text':text,'enabled':True})
        saved=api('GET',f'/api/bots/{args.bot}/skills/{name}')['text']
        if saved!=text:raise RuntimeError('Skill 内容与仓库不一致')
        listing=api('GET',f'/api/bots/{args.bot}/skills')['skills']
        if not any(s['name']==name and s['enabled'] for s in listing):raise RuntimeError('Skill 未启用')
        print(json.dumps({'bot':args.bot,'skill':name,'enabled':True,'sha256':hashlib.sha256(text.encode()).hexdigest()},ensure_ascii=False))


if __name__=='__main__':main()
