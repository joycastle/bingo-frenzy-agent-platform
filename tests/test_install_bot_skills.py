from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Thread
import unittest


@contextmanager
def fixture_server(initial=None, reject_new=False):
    writes=[]
    saved=dict(initial or {})
    initial_texts={v['text'] for v in saved.values()}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,body):
            self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())
        def do_GET(self):
            if self.path.startswith('/api/bots?'):
                return self.respond(200,{'bots':[{'id':'target','busy':False},{'id':'other','busy':False}]})
            if self.path=='/api/bots/target/skills':
                return self.respond(200,{'skills':[{'name':k,'enabled':v['enabled'],'source':v['source']} for k,v in saved.items()]})
            name=self.path.rsplit('/',1)[-1]
            if self.path.startswith('/api/bots/target/skills/') and name in saved:
                return self.respond(200,{'text':saved[name]['text']})
            self.respond(404,{'error':'not found'})
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path!='/api/bots/target/skill-template' or not {'name','description','source','text','enabled'}<=payload.keys():
                return self.respond(400,{'error':'invalid request'})
            if payload['name'] in saved:return self.respond(422,{'error':'already imported'})
            if reject_new and payload['text'] not in initial_texts:return self.respond(500,{'error':'fixture import failure'})
            writes.append((self.path,payload));saved[payload['name']]=payload
            self.respond(201,{'installed':{'name':payload['name']}})
        def do_DELETE(self):
            name=self.path.rsplit('/',1)[-1]
            if self.path.startswith('/api/bots/target/skills/') and name in saved:
                writes.append((self.path,{'deleted':True}));del saved[name]
                return self.respond(200,{'ok':True})
            self.respond(404,{'error':'not found'})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',writes
    finally:server.shutdown();server.server_close();thread.join()


class InstallBotSkillsTests(unittest.TestCase):
    def run_install(self,url,directory,*extra):
        return subprocess.run([sys.executable,str(Path(__file__).parents[1]/'bin/install-bot-skills.py'),'--url',url,'--bot','target','--directory',str(directory),*extra],capture_output=True,text=True)

    def test_installs_exact_skill_contents_to_only_selected_bot(self):
        with tempfile.TemporaryDirectory() as tmp, fixture_server() as (url,writes):
            folder=Path(tmp)/'example';folder.mkdir()
            text='---\nname: example\ndescription: Example reader\n---\nRead project references.\n'
            (folder/'SKILL.md').write_text(text)
            result=self.run_install(url,Path(tmp))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(writes),1)
            self.assertEqual(writes[0][0],'/api/bots/target/skill-template')
            self.assertEqual(writes[0][1]['text'],text)
            self.assertTrue(writes[0][1]['enabled'])
            self.assertTrue(json.loads(result.stdout)['enabled'])

    def test_external_target_is_refused_before_any_request(self):
        result=self.run_install('https://example.invalid',Path('/unused'))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('本机',result.stderr)

    def test_supporting_files_are_not_silently_left_out(self):
        with tempfile.TemporaryDirectory() as tmp, fixture_server() as (url,writes):
            folder=Path(tmp)/'example';(folder/'references').mkdir(parents=True)
            (folder/'SKILL.md').write_text('---\nname: example\ndescription: Example\n---\n')
            (folder/'references/details.md').write_text('required resource')
            result=self.run_install(url,Path(tmp))
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(writes,[])

    def test_identical_skill_is_not_deleted_and_imported_again(self):
        old={'name':'example','source':'local-platform:example','text':'old content','enabled':True}
        with tempfile.TemporaryDirectory() as tmp,fixture_server({'example':old}) as (url,writes):
            folder=Path(tmp)/'example';folder.mkdir();(folder/'SKILL.md').write_text(old['text'])
            result=self.run_install(url,Path(tmp))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(writes,[])

    def test_explicit_replace_backs_up_old_contents_before_update(self):
        old={'name':'example','source':'local-platform:example','text':'old content','enabled':True}
        with tempfile.TemporaryDirectory() as tmp,fixture_server({'example':old}) as (url,writes):
            folder=Path(tmp)/'skills/example';folder.mkdir(parents=True);(folder/'SKILL.md').write_text('new content')
            backup=Path(tmp)/'backups'
            result=self.run_install(url,folder.parent,'--replace','--backup-directory',str(backup))
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(writes[0][1],{'deleted':True})
            self.assertEqual(writes[1][1]['text'],'new content')
            files=list(backup.rglob('SKILL.md'));self.assertEqual(len(files),1)
            self.assertEqual(files[0].read_text(),'old content')

    def test_failed_replacement_restores_old_skill(self):
        old={'name':'example','source':'local-platform:example','text':'old content','enabled':False}
        with tempfile.TemporaryDirectory() as tmp,fixture_server({'example':old},reject_new=True) as (url,writes):
            folder=Path(tmp)/'skills/example';folder.mkdir(parents=True);(folder/'SKILL.md').write_text('new content')
            result=self.run_install(url,folder.parent,'--replace','--backup-directory',str(Path(tmp)/'backups'))
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(writes[-1][1]['text'],'old content')
            self.assertFalse(writes[-1][1]['enabled'])

    def test_other_skill_source_is_not_replaced(self):
        old={'name':'example','source':'someone-else','text':'old content','enabled':True}
        with tempfile.TemporaryDirectory() as tmp,fixture_server({'example':old}) as (url,writes):
            folder=Path(tmp)/'example';folder.mkdir();(folder/'SKILL.md').write_text('new content')
            result=self.run_install(url,Path(tmp),'--replace')
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(writes,[])


if __name__=='__main__':unittest.main()
