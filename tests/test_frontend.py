"""Resource migration preserves IDs and never edits dashboard/card YAML."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
package = ModuleType('frontend_test')
package.__path__ = [str(ROOT / 'custom_components/infra_vcenter')]
sys.modules['frontend_test'] = package
http = ModuleType('homeassistant.components.http')
http.StaticPathConfig = lambda url, path, cache: NS(url=url, path=path, cache=cache)
lovelace_const = ModuleType('homeassistant.components.lovelace.const')
lovelace_const.LOVELACE_DATA = 'lovelace'
with patch.dict(sys.modules, {'homeassistant.components.http': http,
                             'homeassistant.components.lovelace.const': lovelace_const}):
    spec = importlib.util.spec_from_file_location('frontend_test.frontend', ROOT / 'custom_components/infra_vcenter/frontend.py')
    frontend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frontend)


class Resources:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.changes = []

    async def async_get_info(self):
        self.loaded = True

    def async_items(self):
        assert self.loaded
        return self.rows

    async def async_update_item(self, ident, data):
        self.changes.append((ident, data))
        row = next(row for row in self.rows if row['id'] == ident)
        row.update(url=data['url'], type=data['res_type'])

    async def async_create_item(self, data):
        self.changes.append(('new', data))
        self.rows.append({'id': 'new', 'url': data['url'], 'type': data['res_type']})


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_preserves_ids_and_unrelated_resources(self):
        unrelated = {'id': 'other', 'url': '/local/other-card.js?v=2', 'type': 'module'}
        resources = Resources([{'id': 'existing', 'url': frontend.LEGACY_PATH + '?v=0.3.1', 'type': 'module'}, unrelated])
        await frontend.async_sync_resources(resources)
        self.assertEqual(resources.rows[0]['id'], 'existing')
        self.assertEqual(resources.rows[0]['url'], frontend.CARD_URL)
        self.assertEqual(resources.rows[1], unrelated)
        await frontend.async_sync_resources(resources)
        self.assertEqual(len(resources.changes), 1, 'reloading must not add another resource')

    async def test_new_install_and_external_url(self):
        external = {'id': 'external', 'url': 'https://example.invalid' + frontend.LEGACY_PATH, 'type': 'module'}
        resources = Resources([external])
        await frontend.async_sync_resources(resources)
        self.assertEqual(resources.rows[0], external)
        self.assertEqual(resources.rows[1]['url'], frontend.CARD_URL)

    async def test_legacy_duplicates_converge_to_one_module_url(self):
        resources = Resources([{'id': 'one', 'url': frontend.LEGACY_PATH, 'type': 'module'},
                               {'id': 'two', 'url': frontend.CARD_PATH + '?v=old', 'type': 'module'}])
        await frontend.async_sync_resources(resources)
        self.assertEqual({r['id'] for r in resources.rows}, {'one', 'two'})
        self.assertEqual({r['url'] for r in resources.rows}, {frontend.CARD_URL})

    async def test_yaml_resources_and_dashboard_configuration_are_untouched(self):
        calls = []
        async def register(paths):
            calls.extend(paths)
        resources = Resources([{'id': 'yaml', 'url': frontend.LEGACY_PATH}])
        dashboard = {'cards': [{'type': 'custom:infra-vcenter-overview', 'source_links': [{'source': 'example:bmc', 'target': 'vc:host:h1'}]}]}
        original = deepcopy(dashboard)
        hass = NS(http=NS(async_register_static_paths=register), data={'lovelace': NS(resource_mode='yaml', resources=resources, dashboards=dashboard)})
        with self.assertLogs(frontend._LOGGER, level='WARNING'):
            await frontend.async_setup_frontend(hass)
        self.assertEqual(resources.changes, [])
        self.assertEqual(dashboard, original)
        self.assertEqual(calls[0].url, frontend.CARD_PATH)
        self.assertTrue(Path(calls[0].path).is_file())
