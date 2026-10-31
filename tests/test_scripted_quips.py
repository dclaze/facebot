import unittest
from unittest.mock import AsyncMock, Mock

from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.interaction import InteractionState, ProactiveTurn
from server.scene import SceneState
from server.scripted_quips import QuipDirector, load_quips
from server.vision import VisionState
from server.visual_reactions import VisualReaction


class QuipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 0.
        self.scene = SceneState(clock=lambda: self.now)
        self.state = InteractionState(self.scene, clock=lambda: self.now)
        self.director = QuipDirector(load_quips('halloween'), clock=lambda: self.now)

    def observe(self, when, faces=1, age=0):
        self.now = when
        self.scene.update({'visible_faces': faces, 'age_ms': age})

    def test_rotates_candy_and_survives_connection_changes(self):
        self.observe(0)
        first = self.director.take_event(self.state, arrival=True)
        self.assertEqual(first['category'], 'arrival')
        self.observe(29)
        self.assertIsNone(self.director.take_event(self.state, arrival=True))
        self.observe(46)
        first_candy = self.director.take_event(self.state)
        self.assertEqual(first_candy['category'], 'candy')
        # Reconnect creates a fresh state, while the app keeps its director.
        self.state = InteractionState(self.scene, clock=lambda: self.now)
        self.observe(196)
        next_candy = self.director.take_event(self.state)
        self.assertEqual(next_candy['category'], 'candy')
        self.assertNotEqual(next_candy['text'], first_candy['text'])

    def test_stale_absent_muted_busy_and_recent_conversation_are_quiet(self):
        for faces, age in [(0, 0), (1, 751)]:
            self.observe(0, faces, age)
            self.assertIsNone(self.director.take_event(self.state, arrival=True))
        self.observe(0)
        self.now = 1.
        self.assertIsNone(self.director.take_event(self.state, arrival=True))
        for field in ('user_speaking', 'bot_speaking', 'response_pending'):
            self.observe(2)
            setattr(self.state, field, True)
            self.assertIsNone(self.director.take_event(self.state, arrival=True))
            setattr(self.state, field, False)
        self.scene.encounter.silenced = True
        self.assertIsNone(self.director.take_event(self.state, arrival=True))
        self.scene.encounter.silenced = False
        self.state.last_activity = 1.
        self.assertIsNone(self.director.take_event(self.state, arrival=True))

    def test_only_confirmed_current_costume_labels_trigger_specific_lines(self):
        vision = VisionState(clock=lambda: self.now)
        self.observe(0)
        vision.accept(['cape'], 0, 1)
        self.assertIsNone(self.director.take_event(self.state, vision))
        self.observe(.25)
        vision.accept(['cape'], .25, 1)
        event = self.director.take_event(self.state, vision)
        self.assertEqual(event['category'], 'cape')
        self.observe(31)
        self.assertIsNone(self.director.take_event(self.state, vision))
        # Background furniture is deliberately absent from the event quip pack.
        self.assertNotIn('sofa', self.director.pack['groups'])

    async def test_timer_quip_bypasses_llm_and_stale_delivery_drops(self):
        producer = ProactiveTurn(self.state, LLMContext([]), quips=self.director)
        producer.push_frame = AsyncMock()
        for i in range(5):
            self.observe(i * .25)
        await producer.tick()
        event_frame = producer.push_frame.call_args.args[0]
        self.assertEqual(event_frame.scene_event['kind'], 'prepared_quip')
        consumer = VisualReaction(self.state)
        consumer.push_frame = AsyncMock()
        await consumer.process_frame(event_frame, FrameDirection.DOWNSTREAM)
        frames = [call.args[0] for call in consumer.push_frame.call_args_list]
        self.assertEqual(len([f for f in frames if isinstance(f, TTSSpeakFrame)]), 1)
        self.assertFalse(any(isinstance(f, LLMContextFrame) for f in frames))
        consumer.push_frame.reset_mock()
        self.now += 1.
        await consumer.process_frame(event_frame, FrameDirection.DOWNSTREAM)
        consumer.push_frame.assert_not_called()
        self.assertFalse(self.state.response_pending)

    def test_continuous_audience_gets_variety_without_reminder_flood(self):
        emissions = []
        for i in range(2401):
            self.observe(i / 4)
            event = self.director.take_event(self.state)
            if event:
                emissions.append((self.now, event))
        self.assertGreaterEqual(len(emissions), 15)
        self.assertTrue(all(b[0] - a[0] >= 30 for a, b in zip(emissions, emissions[1:])))
        candy = [(t, e) for t, e in emissions if e['category'] == 'candy']
        self.assertLessEqual(len(candy), 4)
        self.assertEqual(len({e['text'] for _, e in candy}), len(candy))
        general = [e['text'] for _, e in emissions if e['category'] == 'general']
        self.assertEqual(len(set(general[:12])), len(general[:12]))

    def test_app_and_catalog_expose_real_quip_pack(self):
        from fastapi.testclient import TestClient
        from server.app import create_app
        from server.catalog import snapshot
        engine = Mock(model_name='test', voice='test', supports_emotion=False)
        client = TestClient(create_app('test-token-' * 4, engine=engine))
        status = client.get('/health').json()['scripted_quips']
        self.assertTrue(status['enabled'])
        self.assertEqual(status['lines'], 66)
        skill = next(s for s in snapshot()['skills'] if s['id'] == 'scripted-quips')
        self.assertTrue(skill['configured'])


if __name__ == '__main__':
    unittest.main()
