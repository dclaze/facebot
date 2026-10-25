import unittest
from server.timing import StageTiming

class TimingTests(unittest.TestCase):
    def test_stage_deltas_and_bounded_content_free_report(self):
        now=[0.]
        timing=StageTiming(clock=lambda:now[0], capacity=2)
        for _ in range(3):
            timing.mark('vad_start')
            for stage, delta in [('vad_stop',1),('stt_done',.1),('llm_start',.05),('llm_first_text',.2),('llm_done',.3),('tts_start',.01),('first_pcm',.1)]:
                now[0]+=delta; timing.mark(stage)
        report=timing.report()
        self.assertEqual(report['completed_samples'],2)
        self.assertAlmostEqual(report['samples'][0]['vad_stop_to_first_pcm_ms'],760)
        self.assertAlmostEqual(report['samples'][0]['tts_first_pcm_ms'],100)
        self.assertIn('not acoustic',report['evidence'])
        with self.assertRaises(ValueError): timing.mark('visitor transcript')

    def test_partial_interrupted_and_proactive_are_not_reply_samples(self):
        now=[0.]
        timing=StageTiming(clock=lambda:now[0])
        timing.mark('first_pcm')
        timing.mark('vad_start'); timing.mark('vad_stop'); timing.mark('llm_start')
        timing.mark('vad_start')  # new utterance replaces incomplete turn
        timing.mark('first_pcm') # stale audio without current LLM request
        self.assertEqual(timing.report()['completed_samples'],0)
        self.assertEqual(timing.report()['incomplete_turns'],1)


class DiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnostics_requires_pairing_authorization(self):
        import httpx
        from server.app import create_app
        token = 'synthetic-test-token-not-a-real-secret'
        app = create_app(token, engine=object())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            self.assertEqual((await client.get('/diagnostics')).status_code, 403)
            response = await client.get('/diagnostics', headers={'Authorization':'Bearer '+token})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['completed_samples'], 0)
            self.assertNotIn(token, response.text)

class StaleTimingTests(unittest.TestCase):
    def test_stale_pcm_before_current_generation_is_not_first_reply_audio(self):
        now=[0.]
        timing=StageTiming(clock=lambda:now[0])
        timing.mark('vad_start'); timing.mark('first_pcm')
        for stage in ('vad_stop','stt_done','llm_start','tts_start','first_pcm'):
            now[0]+=1; timing.mark(stage)
        self.assertEqual(timing.report()['samples'][0]['tts_first_pcm_ms'],1000)

    def test_prepared_repairs_are_excluded_from_generated_summary(self):
        now=[0.]
        timing=StageTiming(clock=lambda:now[0])
        for stage in ('vad_start','vad_stop','stt_done','prepared_reply','tts_start','first_pcm'):
            now[0]+=1;timing.mark(stage)
        report=timing.report()
        self.assertEqual(report['completed_samples'],0)
        self.assertEqual(len(report['prepared_reply_samples']),1)
        self.assertEqual(report['summary'],{})
