import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import settings, coaching, admin

class SettingsTests(unittest.TestCase):
    def test_migration_validation_and_persistence(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'settings.json'
            p.write_text('{"speech_rate":1.12}')
            self.assertEqual(settings.read(p),dict(settings.DEFAULTS,speech_rate=1.12))
            value={'speech_rate':1.23,'character_name':'Lady Boo','color_scheme':'pumpkin'}
            settings.save(value,p)
            self.assertEqual(settings.read(p),value)
            self.assertEqual(p.stat().st_mode & 0o777,0o600)
        for bad in ({'speech_rate':True},{'speech_rate':float('nan')}, {'speech_rate':1.31},
                    dict(settings.DEFAULTS,character_name='<script>'),dict(settings.DEFAULTS,color_scheme='unknown')):
            with self.assertRaises(ValueError): settings.validate(bad)

    def test_admin_save_conflict_origin_and_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'settings.json'; coach=Path(folder)/'coaching.json'
            read_settings=settings.read; save_settings=settings.save
            read_coaching=coaching.read; save_coaching=coaching.save
            with patch.object(settings,'read',lambda:read_settings(runtime)), \
                 patch.object(settings,'save',lambda v:save_settings(v,runtime)), \
                 patch.object(coaching,'read',lambda path=coach:read_coaching(path)), \
                 patch.object(coaching,'save',lambda v:save_coaching(v,coach)):
                client=TestClient(admin.create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('127.0.0.1',1234))
                initial=client.get('/api/settings').json()
                payload={k:initial[k] for k in (*settings.DEFAULTS,'rules','etag')}
                payload.update(character_name='Casper',color_scheme='violet',speech_rate=1.09)
                self.assertEqual(client.put('/api/settings',json=payload).status_code,403)
                headers={'Origin':'http://127.0.0.1:8766'}
                result=client.put('/api/settings',json=payload,headers=headers)
                self.assertEqual(result.status_code,200,result.text)
                self.assertEqual(result.json()['character_name'],'Casper')
                self.assertEqual(read_settings(runtime)['color_scheme'],'violet')
                self.assertEqual(client.put('/api/settings',json=payload,headers=headers).status_code,409)
                payload['etag']=result.json()['etag'];payload['rules']=['x'*201]
                self.assertEqual(client.put('/api/settings',json=payload,headers=headers).status_code,400)
                self.assertEqual(read_settings(runtime)['speech_rate'],1.09)
                self.assertEqual(client.put('/api/settings',json=None,headers=headers).status_code,400)
                self.assertEqual(client.get('/api/settings',headers={'Host':'evil.example:8766'}).status_code,403)
                self.assertEqual(client.get('/').headers['cache-control'],'no-store')
                payload['rules']=['Synthetic owner coaching']
                payload['speech_rate']=1.25
                with patch.object(coaching,'save',side_effect=OSError('synthetic disk failure')):
                    failure=client.put('/api/settings',json=payload,headers=headers)
                self.assertEqual(failure.status_code,503)
                self.assertEqual(read_settings(runtime)['speech_rate'],1.09)


    def test_shared_settings_survive_new_service_and_reset(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime=Path(folder)/'settings.json'; coach=Path(folder)/'coaching.json'
            read_settings=settings.read; save_settings=settings.save
            read_coaching=coaching.read; save_coaching=coaching.save
            with patch.object(settings,'read',lambda:read_settings(runtime)), \
                 patch.object(settings,'save',lambda v:save_settings(v,runtime)), \
                 patch.object(coaching,'read',lambda path=coach:read_coaching(path)), \
                 patch.object(coaching,'save',lambda v:save_coaching(v,coach)):
                def browser():
                    return TestClient(admin.create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('127.0.0.1',1234))
                first=browser(); initial=first.get('/api/settings').json()
                headers={'Origin':'http://127.0.0.1:8766'}
                edited=dict(character_name='Casper',color_scheme='ice',speech_rate=.8,rules=['Synthetic owner direction'])
                saved=first.put('/api/settings',json={**edited,'etag':initial['etag']},headers=headers)
                self.assertEqual(saved.status_code,200,saved.text)
                # A fresh service/browser reads the disk values, without browser storage.
                second=browser(); reloaded=second.get('/api/settings')
                self.assertEqual(reloaded.headers['cache-control'],'no-store')
                for key,value in edited.items(): self.assertEqual(reloaded.json()[key],value)
                defaults=reloaded.json()['defaults']
                reset=second.put('/api/settings',json={**defaults,'etag':reloaded.json()['etag']},headers=headers)
                self.assertEqual(reset.status_code,200,reset.text)
                for client in (first,browser()):
                    current=client.get('/api/settings').json()
                    for key,value in defaults.items(): self.assertEqual(current[key],value)
                self.assertEqual(read_settings(runtime),{k:defaults[k] for k in settings.DEFAULTS})
                self.assertEqual(read_coaching(coach)['rules'],[])

    def test_remote_clients_are_rejected(self):
        client=TestClient(admin.create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('192.0.2.7',1234))
        self.assertEqual(client.get('/api/settings').status_code,403)

    def test_explicit_laptop_can_load_and_save_but_other_devices_cannot(self):
        app=admin.create_admin('192.168.4.32',allowed_clients=['192.168.4.27'])
        laptop=TestClient(app,base_url='http://192.168.4.32:8766',client=('192.168.4.27',1234))
        stranger=TestClient(app,base_url='http://192.168.4.32:8766',client=('192.168.4.28',1234))
        value=dict(settings.DEFAULTS)
        with patch.object(settings,'read',return_value=value), patch.object(settings,'save') as save, \
             patch.object(coaching,'read',return_value={'rules':[],'revision':0}):
            self.assertEqual(laptop.get('/').status_code,200)
            response=laptop.get('/api/settings')
            self.assertEqual(response.status_code,200)
            payload={k:response.json()[k] for k in (*settings.DEFAULTS,'rules','etag')}
            headers={'Origin':'http://192.168.4.32:8766'}
            self.assertEqual(laptop.put('/api/settings',json=payload,headers=headers).status_code,200)
            save.assert_called_once_with(value)
            self.assertEqual(laptop.put('/api/settings',json=payload,headers={'Origin':'http://evil.example'}).status_code,403)
            self.assertEqual(laptop.get('/',headers={'Host':'evil.example:8766'}).status_code,403)
            for route in ('/','/api/settings','/api/status'):
                self.assertEqual(stranger.get(route).status_code,403)
                self.assertEqual(stranger.get(route,headers={'X-Forwarded-For':'192.168.4.27'}).status_code,403)
            self.assertEqual(stranger.put('/api/settings',json=payload,headers=headers).status_code,403)

    def test_owner_address_must_be_explicit_and_private(self):
        for address in ('0.0.0.0','::','224.0.0.1','8.8.8.8','192.168.4.0/24','*'):
            with self.assertRaises(ValueError): admin.create_admin(allowed_clients=[address])

    def test_runtime_endpoint_requires_pairing_and_has_no_secrets(self):
        from unittest.mock import Mock, AsyncMock
        from server.app import create_app
        engine=Mock();engine.render=AsyncMock()
        token='synthetic-token-for-test-only'
        with patch('server.app.ContextBudget'), patch.object(settings,'read',return_value=dict(settings.DEFAULTS,character_name='Casper')):
            with TestClient(create_app(token,engine)) as client:
                self.assertEqual(client.get('/runtime-settings').status_code,403)
                response=client.get('/runtime-settings',headers={'Authorization':'Bearer '+token})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['character_name'],'Casper')
                self.assertEqual(response.json()['colors'],settings.PALETTES['mint'])
                self.assertNotIn(token,response.text)
                self.assertEqual(response.headers['cache-control'],'no-store')

    def test_speech_rate_is_read_at_each_utterance(self):
        from unittest.mock import Mock
        from server.tts import SpeechEngine
        engine=SpeechEngine(live_settings=True)
        engine.model=Mock();pipeline=Mock(return_value=[])
        engine.model._get_pipeline.return_value=pipeline
        try:
            with patch('server.tts.read_settings',side_effect=[dict(settings.DEFAULTS,speech_rate=.9),dict(settings.DEFAULTS,speech_rate=1.23)]):
                list(engine.synthesize_segments('Synthetic first.'))
                list(engine.synthesize_segments('Synthetic second.'))
            self.assertEqual([call.kwargs['speed'] for call in pipeline.call_args_list],[.9,1.23])
            self.assertIsNone(engine.last_synthesized_rate)  # No generated audio yet.
            import mlx.core as mx
            from types import SimpleNamespace
            engine.model.config.sample_rate=24000
            pipeline.return_value=[SimpleNamespace(audio=mx.zeros((240,)),pred_dur=None)]
            with patch('server.tts.read_settings',return_value=dict(settings.DEFAULTS,speech_rate=1.21)):
                result=list(engine.synthesize_segments('Synthetic speech.'))
            self.assertEqual(len(result[0][0]),480)
            self.assertEqual(engine.last_synthesized_rate,1.21)
        finally:
            engine.executor.shutdown(wait=True)
