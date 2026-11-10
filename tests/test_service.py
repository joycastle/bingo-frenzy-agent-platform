import importlib.util
import plistlib
import subprocess
import unittest
from unittest.mock import patch
from pathlib import Path

spec = importlib.util.spec_from_file_location('bfa_service', Path(__file__).parents[1] / 'bin/service.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class ServiceConfigurationTests(unittest.TestCase):
    def test_shell_metacharacters_cannot_enter_caddy_binding(self):
        for address in ['localhost; touch /tmp/probe', '0.0.0.0\nadmin :2019', 'example.com']:
            with self.subTest(address=address), self.assertRaises(ValueError):
                service.caddy_config(address, 18799, 8799, 8800)

    def test_conflicting_ports_are_refused(self):
        with self.assertRaises(ValueError):
            service.caddy_config('127.0.0.1', 8799, 8799, 8800)

    def test_invalid_port_cannot_enter_proxy_config(self):
        for port in ['18799\n}', 0, 65536]:
            with self.subTest(port=port), self.assertRaises(ValueError):
                service.caddy_config('127.0.0.1', port, 8799, 8800)

    def test_service_paths_with_spaces_stay_single_arguments(self):
        root = Path('/Users/test/Work/Agent Platform')
        rendered = service.plist('server', root, root / 'state', Path('/Users/test'))
        parsed = plistlib.loads(plistlib.dumps(rendered))
        self.assertEqual(parsed['ProgramArguments'], ['/bin/bash', str(root / 'bin/run-service.sh'), 'server'])
        self.assertEqual(parsed['EnvironmentVariables']['HOME'], '/Users/test')

    def test_proxy_preserves_loopback_upstreams_and_streaming(self):
        config = service.caddy_config('0.0.0.0', 18799, 8799, 8800)
        self.assertIn('reverse_proxy 127.0.0.1:8799', config)
        self.assertIn('reverse_proxy 127.0.0.1:8800', config)
        self.assertIn('flush_interval -1', config)
        self.assertNotIn('header_up Host', config)

    def test_reload_recovers_when_previous_job_is_still_exiting(self):
        done = subprocess.CompletedProcess(['launchctl'], 0, '', '')
        pending = subprocess.CompletedProcess(['launchctl'], 5, '', 'Bootstrap failed: 5')
        with patch.object(service.subprocess, 'run', side_effect=[done, pending, done]) as run, patch.object(service.time, 'sleep') as wait:
            service.reload_agent('gui/502', 'test.agent', Path('/tmp/test.plist'))
        self.assertEqual(run.call_args_list[0].args[0], ['launchctl', 'bootout', 'gui/502/test.agent'])
        self.assertEqual(run.call_args_list[-1].args[0], ['launchctl', 'bootstrap', 'gui/502', '/tmp/test.plist'])
        wait.assert_called_once_with(0.5)

    def test_reload_does_not_hide_other_bootstrap_failures(self):
        done = subprocess.CompletedProcess(['launchctl'], 0, '', '')
        failed = subprocess.CompletedProcess(['launchctl'], 1, '', 'Operation not permitted')
        with patch.object(service.subprocess, 'run', side_effect=[done, failed]), patch.object(service.time, 'sleep') as wait:
            with self.assertRaises(subprocess.CalledProcessError) as error:
                service.reload_agent('gui/502', 'test.agent', Path('/tmp/test.plist'))
        self.assertEqual(error.exception.returncode, 1)
        wait.assert_not_called()


if __name__ == '__main__': unittest.main()
