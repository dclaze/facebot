import unittest
from fastapi.testclient import TestClient
from server.admin import create_admin
from server.catalog import snapshot
from server.context_budget import ContextBudget
from server.persona import bounded_context


class CatalogTests(unittest.TestCase):
    def test_installed_catalog_resolves_assets_and_personalities(self):
        catalog=snapshot()
        self.assertEqual(len(catalog['sounds']),20)
        self.assertEqual(catalog['clip_count'],40)
        self.assertEqual({x['id'] for x in catalog['personalities']},{'ghost','host'})
        self.assertTrue(all(x['event_ids'] for x in catalog['personalities']))
        client=TestClient(create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('127.0.0.1',1234))
        self.assertEqual(client.get('/packs').status_code,200)
        self.assertEqual(client.get('/api/catalog').json()['clip_count'],40)
        for sound in catalog['sounds']:
            for clip in sound['clips']:
                result=client.get(clip['url'])
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.content[:4],b'RIFF')
        self.assertEqual(client.get('/api/sounds/unknown').status_code,404)
        stranger=TestClient(create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('192.0.2.7',1234))
        for route in ('/packs','/api/catalog',catalog['sounds'][0]['clips'][0]['url']):
            self.assertEqual(stranger.get(route).status_code,403)

    def test_capabilities_survive_budget_without_full_corpus(self):
        messages=bounded_context([{'role':'user','content':'What can you do?'}])
        result,receipt=ContextBudget().assemble(messages)
        text=' '.join(x['content'] for x in result)
        self.assertIn('Sound capabilities:',text)
        self.assertIn('Play a drumroll',text)
        self.assertNotIn('.wav',text)
        self.assertLessEqual(receipt['budgeted_input_tokens'],1000)
