import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import importlib.util
import socket


class FeishuProjectMcpTests(unittest.TestCase):
    def test_offline_configuration_preserves_keys_and_other_servers_and_is_idempotent(self):
        platform = Path(__file__).parents[1]
        spec = importlib.util.spec_from_file_location('configure_feishu', platform/'bin/configure-feishu-project.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as port:
            data = Path(tmp);(data/'bots/target').mkdir(parents=True)
            config = {'fixtureSecret':'keep-private','mcpServers':{'other':{'enabled':True}}}
            file = data/'config.json';file.write_text(json.dumps(config))
            original = file.read_bytes()
            port.bind(('127.0.0.1',0));number=port.getsockname()[1]
            self.assertTrue(module.configure(data,platform,'target',number))
            saved = json.loads(file.read_text())
            self.assertEqual(saved['fixtureSecret'],'keep-private')
            self.assertEqual(saved['mcpServers']['other'],config['mcpServers']['other'])
            self.assertEqual(saved['mcpServers']['feishu-project']['bot'],'target')
            self.assertFalse(saved['mcpServers']['feishu-project']['enabled'])
            self.assertEqual(next((data/'backups').glob('*/config.json')).read_bytes(),original)
            self.assertFalse(module.configure(data,platform,'target',number))
            port.listen()
            with self.assertRaisesRegex(ValueError,'停止'):
                module.configure(data,platform,'target',number)

    def run_wrapper(self, contents, wrapper='feishu-project-mcp', args=()):
        with tempfile.TemporaryDirectory(prefix='bf project mcp ') as tmp:
            root = Path(tmp)
            shutil.copyfile(Path(__file__).parents[1]/'bin'/wrapper, root/'wrapper')
            (root/'common.sh').write_text('set -euo pipefail\nFEISHU_PROJECT_MCP_VERSION=0.0.1\nFEISHU_PROJECT_CLI_VERSION=1.0.28\n')
            if contents is not None:
                (root/'.env').write_text(contents)
            probe = root/'npx'
            probe.write_text('#!/usr/bin/env python3\nimport json,os,sys\nkeys=("MEEGLE_HOST","MEEGLE_USER_ACCESS_TOKEN","MEEGLE_ACCESS_TOKEN_HEADER","MEEGLE_TELEMETRY","MEEGLE_NO_UPDATE_CHECK")\nresult={"args":sys.argv[1:],"token":os.environ.get("MCP_USER_TOKEN")}\nif "@lark-project/meegle@1.0.28" in sys.argv: result["cli_env"]={k:os.environ.get(k) for k in keys}\nprint(json.dumps(result))\n')
            probe.chmod(0o700)
            env = dict(os.environ, STATE_DIR=tmp, PATH=tmp+os.pathsep+os.environ['PATH'], MCP_USER_TOKEN='inherited-not-selected', MEEGLE_USER_ACCESS_TOKEN='inherited-not-selected', MEEGLE_HOST='other.example', MEEGLE_ACCESS_TOKEN_HEADER='Authorization', MEEGLE_TELEMETRY='enabled')
            return subprocess.run(['bash',str(root/'wrapper'),*args],env=env,capture_output=True,text=True)

    def test_namespaced_private_token_maps_to_official_variable_and_pinned_command(self):
        result = self.run_wrapper("FEISHU_PROJECT_MCP_USER_TOKEN='fixture $ value'\n")
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout),{'args':['-y','@lark-project/mcp@0.0.1','--domain','https://project.feishu.cn'],'token':'fixture $ value'})
        self.assertEqual(result.stderr,'')

    def test_missing_or_empty_config_does_not_fall_back_to_inherited_token(self):
        for wrapper in ['feishu-project-mcp','feishu-project-cli']:
            for contents in [None,'',"FEISHU_PROJECT_MCP_USER_TOKEN=''\n"]:
                with self.subTest(wrapper=wrapper,contents=contents):
                    result = self.run_wrapper(contents,wrapper)
                    self.assertNotEqual(result.returncode,0)
                    self.assertEqual(result.stdout,'')
                    self.assertNotIn('inherited-not-selected',result.stderr)

    def test_cli_reuses_private_token_with_correct_header_and_forwards_arguments(self):
        args=['workitem','get','--name','two words $ literal','--envelope']
        result=self.run_wrapper("FEISHU_PROJECT_MCP_USER_TOKEN='fixture $ value'\n",'feishu-project-cli',args)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=json.loads(result.stdout)
        self.assertEqual(actual['args'],['-y','@lark-project/meegle@1.0.28',*args])
        self.assertEqual(actual['cli_env'],{
            'MEEGLE_HOST':'project.feishu.cn',
            'MEEGLE_USER_ACCESS_TOKEN':'fixture $ value',
            'MEEGLE_ACCESS_TOKEN_HEADER':'X-Mcp-Token',
            'MEEGLE_TELEMETRY':'disabled',
            'MEEGLE_NO_UPDATE_CHECK':'1',
        })
        self.assertEqual(result.stderr,'')

if __name__ == '__main__':
    unittest.main()
