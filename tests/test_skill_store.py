import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from server.admin import create_admin
from server import skill_store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'packs.json'
        self.patcher = patch.object(skill_store, 'state_path', return_value=self.path)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.assets = patch.object(skill_store, 'availability', return_value=True)
        self.assets.start()
        self.addCleanup(self.assets.stop)
        self.client = TestClient(create_admin('127.0.0.1'), base_url='http://127.0.0.1:8766', client=('127.0.0.1', 123))
        self.headers = {'Origin': 'http://127.0.0.1:8766'}

    def test_save_survives_reload_and_stale_tab_cannot_overwrite(self):
        first = self.client.put('/api/store/quick-jokes', json={'enabled': False, 'revision': 0}, headers=self.headers)
        self.assertEqual(first.status_code, 200)
        self.assertFalse(skill_store.enabled('quick-jokes'))
        self.assertEqual(self.client.get('/api/store').json()['revision'], 1)
        stale = self.client.put('/api/store/quick-jokes', json={'enabled': True, 'revision': 0}, headers=self.headers)
        self.assertEqual(stale.status_code, 409)
        self.assertFalse(skill_store.enabled('quick-jokes'))

    def test_owner_and_origin_required(self):
        payload = {'enabled': False, 'revision': 0}
        self.assertEqual(self.client.put('/api/store/quick-jokes', json=payload).status_code, 403)
        visitor = TestClient(create_admin('127.0.0.1'), base_url='http://127.0.0.1:8766', client=('192.168.1.44', 123))
        self.assertEqual(visitor.get('/api/store').status_code, 403)
        self.assertFalse(self.path.exists())

    def test_invalid_state_and_unknown_paid_capabilities_fail_closed(self):
        for corrupt in ('{broken', '[]', 'null', '"not an object"'):
            self.path.write_text(corrupt)
            self.assertFalse(skill_store.enabled('quick-jokes'))
            self.assertIsNotNone(skill_store.snapshot()['error'])
        self.assertTrue(skill_store.enabled('candy-host'))
        self.assertFalse(skill_store.enabled('untrusted-download'))
        self.assertIsNotNone(skill_store.snapshot()['error'])
        self.assertFalse(skill_store.snapshot()['payments_enabled'])

    def test_missing_asset_and_core_disable_are_rejected(self):
        with patch.object(skill_store, 'availability', return_value=False):
            with self.assertRaises(ValueError):
                skill_store.update('robin-williams', {'enabled': True, 'revision': 0})
        with self.assertRaises(ValueError):
            skill_store.update('candy-host', {'enabled': False, 'revision': 0})
        with self.assertRaises(ValueError):
            skill_store.update('quick-jokes', {'enabled': 'false', 'revision': 0})
        self.assertFalse(self.path.exists())

    def test_future_pack_update_retains_explicit_disabled_preference(self):
        self.path.write_text(json.dumps({'revision': 3, 'packs': {'quick-jokes': {'enabled': False, 'version': 1}}}))
        with patch.dict(skill_store.BY_ID['quick-jokes'], version=2):
            self.assertFalse(skill_store.enabled('quick-jokes'))
            result = skill_store.update('quick-jokes', {'enabled': True, 'revision': 3})
            self.assertEqual(result['revision'], 4)
            self.assertEqual(skill_store.read_state()['packs']['quick-jokes']['version'], 2)


if __name__ == '__main__':
    unittest.main()
