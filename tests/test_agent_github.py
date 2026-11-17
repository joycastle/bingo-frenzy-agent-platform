import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class AgentGithubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bfa github ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.state = self.root/'state'
        self.state.mkdir()
        shutil.copyfile(Path(__file__).parents[1]/'bin/agent-github', self.root/'agent-github')
        (self.root/'common.sh').write_text('set -euo pipefail\n')
        gh = self.root/'gh'
        gh.write_text('''#!/usr/bin/env python3
import json,os,sys
if sys.argv[1:] == ['auth','git-credential','get']:
    request=dict(line.rstrip('\\n').split('=',1) for line in sys.stdin if '=' in line)
    if request.get('host')=='github.com' and request.get('protocol')=='https':
        print('username=x-access-token\\npassword='+os.environ['GH_TOKEN'])
else:
    print(json.dumps({'args':sys.argv[1:],'token':os.environ.get('GH_TOKEN')}))
''')
        gh.chmod(0o700)
        self.env = {k:v for k,v in os.environ.items() if k not in ('GH_TOKEN','GITHUB_TOKEN','GIT_TOKEN') and not k.startswith('GIT_CONFIG_')}
        self.env.update(STATE_DIR=str(self.state), HOME=str(self.root), PATH=str(self.root)+os.pathsep+os.environ['PATH'], GIT_CONFIG_NOSYSTEM='1')

    def run_helper(self, *args, contents="GIT_TOKEN='fixture-token'\n", input=None):
        (self.state/'.env').write_text(contents)
        return subprocess.run(['bash',str(self.root/'agent-github'),*args],env=self.env,input=input,text=True,capture_output=True)

    def test_gh_uses_git_token_without_changing_arguments(self):
        r=self.run_helper('gh','api','repos/org/repo')
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout),{'args':['api','repos/org/repo'],'token':'fixture-token'})

    def test_explicit_gh_token_wins(self):
        r=self.run_helper('gh','api','user',contents="GH_TOKEN='gh-fixture'\nGIT_TOKEN='git-fixture'\n")
        self.assertEqual(json.loads(r.stdout)['token'],'gh-fixture')

    def test_git_uses_helper_with_empty_gh_token_and_ignores_global_credentials(self):
        (self.root/'.gitconfig').write_text('[credential]\n\thelper = !echo password=wrong; echo username=wrong\n')
        r=self.run_helper('git','credential','fill',input='protocol=https\nhost=github.com\n\n',contents="GH_TOKEN=''\nGIT_TOKEN='fixture-token'\n")
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('password=fixture-token',r.stdout)
        self.assertNotIn('wrong',r.stdout)
        self.assertNotIn('fixture-token',r.stderr)

    def test_other_hosts_do_not_receive_github_credential(self):
        r=self.run_helper('git','credential','fill',input='protocol=https\nhost=example.invalid\n\n')
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn('fixture-token',r.stdout+r.stderr)

    def test_empty_token_fails_without_falling_back_to_account_login(self):
        r=self.run_helper('gh','api','user',contents="GH_TOKEN=''\nGIT_TOKEN=''\n")
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(r.stdout,'')

    def test_each_command_reads_current_file(self):
        first=self.run_helper('gh','api','user')
        second=self.run_helper('gh','api','user',contents="GIT_TOKEN='rotated-fixture'\n")
        self.assertEqual(json.loads(first.stdout)['token'],'fixture-token')
        self.assertEqual(json.loads(second.stdout)['token'],'rotated-fixture')


if __name__ == '__main__':
    unittest.main()
