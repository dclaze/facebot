import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class FeedbackWatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'reviews.json'
        self.w=module('feedback_watch','scripts/watch-experience-feedback.py')
    def tearDown(self):self.temp.cleanup()
    def write(self,note='shorter',stamp='one'):
        self.path.write_text(json.dumps({'items':{'laugh':{'status':'changes_requested','note':note,'revision_key':'v3','updated_at':stamp}}}))
    def test_idle_and_duplicate_clicks_do_not_dispatch(self):
        self.write();dispatch=Mock();watch=self.w.Watcher(self.path,dispatch)
        self.assertTrue(watch.tick())
        for _ in range(20):self.assertFalse(watch.tick())
        self.write(stamp='new-click');self.assertFalse(watch.tick())
        dispatch.assert_called_once()
        self.write('different direction');self.assertTrue(watch.tick());self.assertEqual(dispatch.call_count,2)
    def test_feedback_arriving_during_work_is_not_lost(self):
        self.write();dispatch=Mock(side_effect=lambda:self.write('new while working'))
        watch=self.w.Watcher(self.path,dispatch);watch.tick();watch.tick()
        self.assertEqual(dispatch.call_count,2)
    def test_api_save_is_picked_up_without_another_request(self):
        from fastapi.testclient import TestClient
        from server import experiences
        from server.admin import create_admin
        with patch.object(experiences,'review_file',return_value=self.path):
            client=TestClient(create_admin('127.0.0.1'),base_url='http://127.0.0.1:8766',client=('127.0.0.1',1))
            dispatch=Mock();watch=self.w.Watcher(self.path,dispatch);watch.tick();dispatch.reset_mock()
            item=client.get('/api/experiences').json()['experiences'][0]
            payload=dict(action='request_changes',note='Synthetic revision',revision_key=item['revision_key'],review_revision=item['review_revision'])
            result=client.post('/api/experiences/'+item['id']+'/review',json=payload,headers={'Origin':'http://127.0.0.1:8766'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertTrue(watch.tick());dispatch.assert_called_once()
            watch.tick();dispatch.assert_called_once()
    def test_only_feedback_dispatches_worker(self):
        target={'id':'example','priority':0,'revision_key':'x','feedback':'shorter'}
        with patch.object(self.w,'WORK',Path(self.temp.name)),patch.object(self.w.experiences,'report',side_effect=[{'queue':[target]},{'queue':[]}]),patch.object(self.w.subprocess,'run',return_value=Mock(stdout='{"state":"ready"}')) as run:
            self.w.process_feedback();self.assertEqual(run.call_count,1)
            self.assertIn('--feedback-only',run.call_args.args[0])
        with patch.object(self.w,'WORK',Path(self.temp.name)),patch.object(self.w.experiences,'report',return_value={'queue':[{'priority':1}]}),patch.object(self.w.subprocess,'run') as run:
            self.w.process_feedback();run.assert_not_called()
    def test_completed_or_failed_requests_are_not_regenerated(self):
        worker=module('worker','scripts/experience-workshop.py');target={'id':'a','feedback':'shorter'}
        for state in ('failed','complete'):
            self.assertEqual(worker.eligible([target],{worker.job_key(target):{'state':state}}),[])
