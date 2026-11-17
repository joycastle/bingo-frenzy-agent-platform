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
def fixture_server():
    writes=[]
    saved={}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,body):
            self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(body).encode())
        def do_GET(self):
            if self.path.startswith('/api/bots?'):
                return self.respond(200,{'bots':[{'id':'target','busy':False},{'id':'other','busy':False}]})
            if self.path=='/api/bots/target/skills':
                return self.respond(200,{'skills':[{'name':k,'enabled':v['enabled']} for k,v in saved.items()]})
            name=self.path.rsplit('/',1)[-1]
            if self.path.startswith('/api/bots/target/skills/') and name in saved:
                return self.respond(200,{'text':saved[name]['text']})
            self.respond(404,{'error':'not found'})
        def do_POST(self):
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if self.path!='/api/bots/target/skill-template' or not {'name','description','source','text','enabled'}<=payload.keys():
                return self.respond(400,{'error':'invalid request'})
            writes.append((self.path,payload));saved[payload['name']]=payload
            self.respond(201,{'installed':{'name':payload['name']}})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield f'http://127.0.0.1:{server.server_port}',writes
    finally:server.shutdown();server.server_close();thread.join()


class InstallBotSkillsTests(unittest.TestCase):
    def run_install(self,url,directory):
        return subprocess.run([sys.executable,str(Path(__file__).parents[1]/'bin/install-bot-skills.py'),'--url',url,'--bot','target','--directory',str(directory)],capture_output=True,text=True)

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


if __name__=='__main__':unittest.main()
