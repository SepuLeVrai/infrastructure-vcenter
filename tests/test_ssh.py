"""Remote command construction and configuration generation without SSH access."""
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'collector'))
import providers
import configure


class SSHTests(unittest.TestCase):
    def test_host_key_enforcement_and_remote_program(self):
        config = {'host': '192.0.2.31', 'username': 'monitor', 'private_key_file': '/etc/infra-agent/ssh/key', 'mounts': ['/']}
        with patch.object(providers.subprocess, 'run', return_value=NS(returncode=0, stdout='banner\n{"readings": {}, "metadata": {"hostname": "linux-node"}}')) as run:
            readings, metadata = providers.SSHProvider(config).collect()
        args, kwargs = run.call_args
        self.assertIn('StrictHostKeyChecking=yes', args[0])
        self.assertIn('BatchMode=yes', args[0])
        self.assertEqual(args[0][-2:], ['python3', '-'])
        self.assertEqual(metadata['collection_transport'], 'ssh')
        compile(kwargs['input'], '<remote-readonly-program>', 'exec')
        self.assertIn('time.sleep(1)', kwargs['input'])

    def test_invalid_ssh_target_rejected_before_execution(self):
        for host in ['-oProxyCommand=anything', 'host;command', 'https://host']:
            with patch.object(providers.subprocess, 'run') as run, self.assertRaises(ValueError):
                providers.SSHProvider({'host': host, 'username': 'monitor'}).collect()
            run.assert_not_called()

    def test_generator_deduplicates_and_preserves_stable_ids(self):
        args = NS(local=False, linux_hosts='192.0.2.31;node.example.invalid;192.0.2.31', ssh_user='monitor', ssh_key='/key', known_hosts='/known', agent_id='example', mqtt_host='mqtt.example.invalid', mqtt_user='monitor')
        first = configure.generate(args)
        args.linux_hosts = 'node.example.invalid;192.0.2.31'
        second = configure.generate(args)
        self.assertEqual({s['id'] for s in first['sources']}, {s['id'] for s in second['sources']})
        self.assertEqual(len(first['sources']), 2)
        self.assertNotIn('password', first['mqtt'])


if __name__ == '__main__':
    unittest.main()
