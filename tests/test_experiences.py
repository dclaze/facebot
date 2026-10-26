import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import experiences
from server.admin import create_admin


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'reviews.json'
        self.patcher=patch.object(experiences,'review_file',return_value=self.path);self.patcher.start()
        self.client=TestClient(create_admin('127.0.0.1',allowed_clients=['192.168.4.27']),
            base_url='http://127.0.0.1:8766',client=('192.168.4.27',1234))
        self.headers={'Origin':'http://127.0.0.1:8766'}
    def tearDown(self):
        self.patcher.stop();self.temp.cleanup()
    def item(self,id='laughing-contest'):
        return next(x for x in self.client.get('/api/experiences').json()['experiences'] if x['id']==id)
    def payload(self,item,action='request_changes',note='Hold the eyes until the laugh finishes.'):
        return dict(action=action,note=note,revision_key=item['revision_key'],review_revision=item['review_revision'])

    def test_packaged_video_range_and_owner_access(self):
        item=self.item()
        self.assertTrue(item['preview_available'])
        self.assertFalse(item['configured'])
        response=self.client.get(item['media']['video'],headers={'Range':'bytes=0-1023'})
        self.assertEqual(response.status_code,206)
        self.assertEqual(len(response.content),1024)
        self.assertEqual(response.headers['content-type'],'video/mp4')
        stranger=TestClient(create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('192.168.4.28',1234))
        for route in ('/api/experiences',item['media']['video']):
            self.assertEqual(stranger.get(route).status_code,403)
        self.assertEqual(self.client.get('/api/experiences/unknown/media/video').status_code,404)
        self.assertEqual(self.client.get('/api/experiences/laughing-contest/media/contract').status_code,404)

    def test_feedback_persists_and_rejects_lost_updates(self):
        item=self.item();payload=self.payload(item)
        self.assertEqual(self.client.post('/api/experiences/laughing-contest/review',json=payload).status_code,403)
        saved=self.client.post('/api/experiences/laughing-contest/review',json=payload,headers=self.headers)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.item()['review']['note'],payload['note'])
        self.assertEqual(experiences.report()['queue'][0]['id'],'laughing-contest')
        self.assertEqual(self.client.post('/api/experiences/laughing-contest/review',json=payload,headers=self.headers).status_code,409)
        fresh=TestClient(create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('127.0.0.1',1234))
        self.assertEqual(next(x for x in fresh.get('/api/experiences').json()['experiences'] if x['id']=='laughing-contest')['review']['note'],payload['note'])

    def test_approval_is_bound_to_preview_content_and_never_activates(self):
        item=self.item();payload=self.payload(item,'approve_preview','Good.')
        saved=self.client.post('/api/experiences/laughing-contest/review',json=payload,headers=self.headers)
        self.assertEqual(saved.status_code,200,saved.text)
        self.assertEqual(self.item()['review']['status'],'approved')
        self.assertFalse(self.item()['configured'])
        changed=copy.deepcopy(experiences.entries())
        next(x for x in changed if x['id']=='laughing-contest')['version']+=1
        with patch.object(experiences,'entries',return_value=changed):
            revised=self.item()
            self.assertEqual(revised['review'],{})
            self.assertEqual(revised['previous_feedback'],'Good.')
            self.assertFalse(revised['configured'])

    def test_missing_or_tampered_preview_cannot_be_approved(self):
        changed=copy.deepcopy(experiences.entries())
        target=next(x for x in changed if x['id']=='laughing-contest')
        target['assets']['video']['sha256']='0'*64
        with patch.object(experiences,'entries',return_value=changed):
            item=self.item()
            self.assertFalse(item['preview_available'])
            result=self.client.post('/api/experiences/laughing-contest/review',
                json=self.payload(item,'approve_preview',''),headers=self.headers)
            self.assertEqual(result.status_code,400)
        target['assets']['video']['path']='.local/pairing-token'
        self.assertIsNone(experiences.asset_path(target,'video'))

    def test_validation_and_profile_isolation(self):
        item=self.item()
        for action,note in [('request_changes',''),('deploy','ship it'),('request_changes','x'*2001)]:
            result=self.client.post('/api/experiences/laughing-contest/review',
                json=self.payload(item,action,note),headers=self.headers)
            self.assertEqual(result.status_code,400)
        with patch.object(experiences,'active',return_value={'id':'neutral'}):
            self.assertEqual(experiences.snapshot(),[])
            with self.assertRaises(LookupError):experiences.review('laughing-contest',self.payload(item))


class PreviewGroundingTests(unittest.TestCase):
    def renderer(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('preview_renderer',Path(__file__).resolve().parents[1]/'scripts/render-experience.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module
    def test_rejects_ungrounded_dog_and_split_overlong_turn(self):
        root=Path(__file__).resolve().parents[1]
        renderer=self.renderer()
        historical=json.loads((root/'tests/fixtures/experience-dog-invalid.json').read_text())
        with self.assertRaises(ValueError):renderer.validate(historical,['dog'])
        no_context=copy.deepcopy(historical)
        no_context['lines']=no_context['lines'][:2]
        with self.assertRaisesRegex(ValueError,'scene context'):renderer.validate(no_context,['dog'])
        fixed=copy.deepcopy(historical)
        fixed['lines']=[{'actor':'visitor','text':'Hi! I brought my dog.'},
                        {'actor':'bot','text':'A dog! Bring bags. I haunt; you handle cleanup.'}]
        self.assertEqual(renderer.validate(fixed,['dog']),fixed)


class WorkshopGuardTests(unittest.TestCase):
    def worker(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('workshop',Path(__file__).resolve().parents[1]/'scripts/experience-workshop.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        return module

    def test_reserve_and_unknown_quota_stop_before_model(self):
        import sys
        worker=self.worker()
        for remaining in (7,5):
            with tempfile.TemporaryDirectory() as folder, patch.object(worker,'WORK',Path(folder)), \
                 patch.object(worker,'remaining_quota',return_value=remaining), \
                 patch.object(worker.experiences,'report',return_value={'queue':[]}), \
                 patch.object(worker.urllib.request,'urlopen') as request, \
                 patch.object(sys,'argv',['workshop']):
                self.assertEqual(worker.main()['state'],'paused')
                request.assert_not_called()
        with tempfile.TemporaryDirectory() as folder, patch.object(worker,'WORK',Path(folder)), \
             patch.object(worker,'remaining_quota',side_effect=RuntimeError('unavailable')), \
             patch.object(worker.experiences,'report',return_value={'queue':[]}), \
             patch.object(worker.urllib.request,'urlopen') as request, \
             patch.object(sys,'argv',['workshop']):
            self.assertEqual(worker.main()['state'],'paused')
            request.assert_not_called()

    def test_deadline_stops_before_quota_or_model(self):
        import sys
        worker=self.worker()
        with tempfile.TemporaryDirectory() as folder, patch.object(worker,'WORK',Path(folder)), \
             patch.object(worker,'DEADLINE','2020-01-01'), \
             patch.object(worker,'remaining_quota') as quota, \
             patch.object(worker.experiences,'report',return_value={'queue':[]}), \
             patch.object(sys,'argv',['workshop']):
            self.assertEqual(worker.main()['state'],'sunset')
            quota.assert_not_called()

    def test_failed_input_waits_for_a_change(self):
        worker=self.worker()
        original={'id':'example','revision_key':'one','feedback':'shorter'}
        attempts={worker.job_key(original):{'state':'failed'}}
        self.assertEqual(worker.eligible([original],attempts),[])
        changed={**original,'feedback':'shorter, and remove the sound'}
        self.assertEqual(worker.eligible([changed],attempts),[changed])
