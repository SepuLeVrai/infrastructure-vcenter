"""Endpoint identities, reference scoping and partial failure without hardware."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.dev-deps'))
package = types.ModuleType('vmware_test')
package.__path__ = [str(ROOT / 'custom_components/infra_vcenter')]
sys.modules['vmware_test'] = package
from vmware_test.connection import VMwareConnection, EndpointTypeError
from vmware_test.endpoints import parse_hosts, normalize_vmware_config


def snapshot(identity):
    return {
        'vcenter:x': {'kind': 'vcenter', 'id': identity, 'name': 'ESXi', 'attributes': {'api_type': 'HostAgent'}, 'metrics': {}},
        'host:host-1': {'kind': 'host', 'id': 'host-1', 'name': 'node', 'attributes': {}, 'metrics': {'connection': ('connected', None)}},
        'vm:vm-1': {'kind': 'vm', 'id': 'vm-1', 'name': 'vm', 'attributes': {'host_id': 'host-1', 'datastore_ids': ['ds-1']}, 'metrics': {'power_state': ('poweredOn', None)}},
        'datastore:ds-1': {'kind': 'datastore', 'id': 'ds-1', 'name': 'data', 'attributes': {'host_ids': ['host-1']}, 'metrics': {}},
    }


class FakeClient:
    def __init__(self, config):
        self.host = config['host']
        self.failed = False

    def describe(self):
        return {'identity': self.host, 'api_type': 'HostAgent'}

    def collect(self):
        if self.failed:
            raise TimeoutError()
        return snapshot(self.host)


class EndpointTests(unittest.TestCase):
    def test_semicolon_normalization_and_validation(self):
        self.assertEqual(parse_hosts(' NODE.EXAMPLE.INVALID ; 192.0.2.11;node.example.invalid;;'), ['node.example.invalid', '192.0.2.11'])
        self.assertEqual(parse_hosts('[2001:db8::1]'), ['2001:db8::1'])
        for raw in ['https://node', 'node/path', 'node:443', '-node', 'a..b']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_hosts(raw)
        with self.assertRaises(ValueError):
            normalize_vmware_config({})

    def test_ids_are_scoped_and_original_snapshot_unchanged(self):
        original = snapshot('a')
        first = VMwareConnection.scope(original, 'a')
        second = VMwareConnection.scope(original, 'b')
        self.assertFalse(set(first).intersection(second))
        self.assertEqual(first['vm:esxi:a:vm-1']['attributes']['host_id'], 'esxi:a:host-1')
        self.assertEqual(first['vm:esxi:a:vm-1']['attributes']['datastore_ids'], ['esxi:a:ds-1'])
        self.assertEqual(original['vm:vm-1']['attributes']['host_id'], 'host-1')

    def test_partial_endpoint_failure_and_recovery(self):
        with patch('vmware_test.connection.VCenterClient', FakeClient):
            group = VMwareConnection({'esx_hosts': '192.0.2.11;192.0.2.12'}, group_id='group')
            result = group.collect()
            self.assertEqual(result['vcenter:group']['metrics']['hosts'][0], 2)
            self.assertNotIn('storage_capacity', result['vcenter:group']['metrics'])
            group.endpoints[0][1].failed = True
            result = group.collect()
            self.assertFalse(result['host:esxi:192.0.2.11:host-1']['available'])
            self.assertEqual(result['vcenter:group']['metrics']['hosts_connected'][0], 1)
            self.assertEqual(len(result['vcenter:group']['attributes']['unavailable_endpoints']), 1)
            group.endpoints[0][1].failed = False
            self.assertTrue(group.collect()['host:esxi:192.0.2.11:host-1'].get('available', True))
            for _, client in group.endpoints:
                client.failed = True
            with self.assertRaises(ConnectionError):
                group.collect()

    def test_endpoint_aliases_are_not_counted_twice(self):
        with patch('vmware_test.connection.VCenterClient', FakeClient):
            group = VMwareConnection({'esx_hosts': '192.0.2.11;esx.example.invalid'}, group_id='group')
            group.endpoints[1][1].host = '192.0.2.11'
            result = group.collect()
            self.assertEqual(result['vcenter:group']['metrics']['hosts'][0], 1)


if __name__ == '__main__':
    unittest.main()
