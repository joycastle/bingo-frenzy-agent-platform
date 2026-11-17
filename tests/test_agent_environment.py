import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class AgentEnvironmentTests(unittest.TestCase):
    def launch(self, role, contents=None):
        with tempfile.TemporaryDirectory(prefix='bfa environment ') as tmp:
            root = Path(tmp)
            state = root / 'private state'
            state.mkdir()
            current = root / 'release'
            current.mkdir()
            shutil.copyfile(Path(__file__).parents[1] / 'bin/run-service.sh', root / 'run-service.sh')
            (root / 'common.sh').write_text('set -euo pipefail\n')
            probe = root / 'node'
            probe.write_text('#!/usr/bin/env python3\nimport json,os\nprint(json.dumps({k:v for k,v in os.environ.items() if k.startswith("BFA_FIXTURE_")}))\n')
            probe.chmod(0o700)
            caddy = state / 'runtime/caddy'
            caddy.mkdir(parents=True)
            shutil.copyfile(probe, caddy / 'caddy')
            (caddy / 'caddy').chmod(0o700)
            if contents is not None:
                (state / '.env').write_text(contents)
                (state / '.env').chmod(0o600)
            env = {k:v for k,v in os.environ.items() if not k.startswith('BFA_FIXTURE_')}
            env.update(STATE_DIR=str(state), CURRENT=str(current), TARGET='darwin-arm64', OMB_PORT='8799', OMB_DATA_DIR=str(root/'data'), RUNTIME=str(state/'runtime'), PATH=str(root)+os.pathsep+env['PATH'])
            result = subprocess.run(['bash', str(root/'run-service.sh'), role], env=env, text=True, capture_output=True)
            return result

    def test_server_exports_quoted_values_and_overrides_inherited_values(self):
        with patch.dict(os.environ, {'BFA_FIXTURE_TEXT':'old'}):
            result = self.launch('server', "BFA_FIXTURE_TEXT='a $literal # token with spaces'\nBFA_FIXTURE_JSON='{\"repos\":[\"org/repo\"]}'\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'BFA_FIXTURE_TEXT':'a $literal # token with spaces', 'BFA_FIXTURE_JSON':'{"repos":["org/repo"]}'})

    def test_missing_env_preserves_existing_server_start(self):
        result = self.launch('server')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})

    def test_edge_does_not_load_agent_credentials(self):
        result = self.launch('edge', "BFA_FIXTURE_SECRET='test-only-value'\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})

    def test_env_failure_stops_server_instead_of_starting_with_partial_config(self):
        result = self.launch('server', "BFA_FIXTURE_SECRET='test-only-value'\nfalse\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
