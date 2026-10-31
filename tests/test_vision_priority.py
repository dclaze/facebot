"""Deterministic scheduling and mocked HTTP; no GPU or live camera operations."""
import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from PIL import Image
from pipecat.frames.frames import ErrorFrame
from server.interaction import InteractionState
from server.scene import SceneState
from server.transcription import LocalSTT
from server.vision import ImageLabeler, VisionState
from server.vision_priority import VisionPriority


class PriorityTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = [10.]
        self.state = VisionState(clock=lambda: self.now[0])
        self.gate = VisionPriority(self.state)
        self.voice = InteractionState(SceneState(), clock=lambda: self.now[0])
        self.voice.stt = SimpleNamespace(inference_active=False, last_inference_finished=float('-inf'))

    def test_idle_admits_and_each_voice_phase_defers(self):
        self.assertFalse(self.gate.should_defer(self.voice))
        for field in ('user_speaking', 'bot_speaking', 'response_pending'):
            with self.subTest(field=field):
                setattr(self.voice, field, True)
                self.assertTrue(self.gate.should_defer(self.voice))
                setattr(self.voice, field, False)
                self.assertFalse(self.gate.should_defer(self.voice))
        self.voice.stt.inference_active = True
        self.assertTrue(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.last_defer_reason, 'speech_recognition')
        self.assertEqual(self.state.deferred_frames, 4)

    def test_continuous_voice_cannot_starve_camera(self):
        self.voice.user_speaking = True
        self.assertTrue(self.gate.should_defer(self.voice))
        self.now[0] += self.state.TTL / 2 - .001
        self.assertTrue(self.gate.should_defer(self.voice))
        self.now[0] += .001
        self.assertFalse(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.priority_refreshes, 1)
        self.now[0] += .01
        self.assertTrue(self.gate.should_defer(self.voice))
        self.now[0] += self.state.TTL / 2
        self.assertFalse(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.priority_refreshes, 2)

    def test_existing_observation_deadline_prevents_actual_slow_refresh_gap(self):
        # Native captures at most every 1.5s; measured warm inference is 2.1s.
        # Old 3s deferral would admit at 5.1 and finish 7.2, after the 6s TTL.
        self.now[0] = 2.1
        self.state.accept(['cup'], 0, 2100)
        self.voice.bot_speaking = True
        self.assertTrue(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.observed_at, 0)
        self.now[0] = 3.6
        self.assertFalse(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.priority_refreshes, 1)
        self.now[0] = 5.7
        self.assertTrue(self.state.fresh())
        self.assertTrue(self.state.accept(['cup'], 3.6, 2100))
        self.assertEqual(self.state.report()['age_ms'], 2100)

    def test_already_aged_observation_refreshes_on_first_busy_frame(self):
        self.state.accept(['cup'], 6, 2100)
        self.voice.stt.inference_active = True
        self.assertFalse(self.gate.should_defer(self.voice))
        self.assertEqual(self.state.deferred_frames, 0)
        self.assertEqual(self.state.observed_at, 6)

    def test_budget_tracks_recent_inference_and_reconnect_does_not_reset_deadline(self):
        self.state.accept(['cup'], 8, 2000)
        self.voice.user_speaking = True
        self.assertTrue(self.gate.should_defer(self.voice))
        self.state.inference_ms = 3200
        replacement = InteractionState(SceneState(), clock=lambda: self.now[0])
        replacement.user_speaking = True
        self.assertFalse(self.gate.should_defer(replacement))
        self.assertEqual(self.state.observed_at, 8)

    def test_unexpected_slow_inference_still_expires_and_cannot_fake_freshness(self):
        self.now[0] = 2.1
        self.state.accept(['cup'], 0, 2100)
        self.voice.bot_speaking = True
        self.now[0] = 3.6
        self.assertFalse(self.gate.should_defer(self.voice))
        self.now[0] = 7.3  # In-flight work is slower than the previous estimate.
        self.assertFalse(self.state.fresh())
        self.assertEqual(self.state.report()['age_ms'], 7300)
        self.assertEqual(self.state.report()['labels'], [])
        self.now[0] = 10
        self.assertFalse(self.state.accept(['cup'], 3.6, 6400))
        self.assertEqual(self.state.observed_at, 0)
        self.assertFalse(self.state.fresh())

    def test_quiet_grace_is_300ms_and_disconnect_drops_old_state(self):
        for field_owner, field in ((self.voice, 'last_activity'), (self.voice.stt, 'last_inference_finished')):
            setattr(field_owner, field, self.now[0])
            self.assertTrue(self.gate.should_defer(self.voice))
            self.now[0] += .301
            self.assertFalse(self.gate.should_defer(self.voice))
        self.voice.user_speaking = True
        self.assertTrue(self.gate.should_defer(self.voice))
        self.assertFalse(self.gate.should_defer(None))
        self.assertIsNone(self.gate.deferred_since)
        fresh_voice = InteractionState(SceneState())
        self.assertFalse(self.gate.should_defer(fresh_voice))

    async def test_real_labeler_skips_http_without_refreshing_stale_observation(self):
        self.state.accept(['cup'], 9, 0)
        self.state.accept(['cup'], 10, 0)
        self.now[0] = 11
        self.voice.user_speaking = True
        labeler = ImageLabeler(self.state, should_defer=lambda: self.gate.should_defer(self.voice))
        await labeler.client.aclose()
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={'message': {'content': '{"labels":[],"people":[]}'}})
        labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        try:
            self.assertFalse(await labeler.label(image.getvalue()))
            self.assertEqual(requests, [])
            self.assertEqual(self.state.observed_at, 10)
            self.assertEqual(self.state.frames, 2)
            self.assertEqual(self.state.errors, 0)
            self.now[0] = 17
            self.assertEqual(self.state.report()['age_ms'], 7000)
            self.assertFalse(self.state.report()['fresh'])
            self.assertEqual(self.state.context(), '')
            self.assertEqual(self.state.report()['labels'], [])
            with self.assertRaises(ValueError):
                await labeler.label(image.getvalue(), age_ms=1001)
            self.assertTrue(await labeler.label(image.getvalue()))
            self.assertEqual(len(requests), 1)
            self.assertEqual(self.state.observed_at, 17)
        finally:
            await labeler.close()


class STTInflightTests(unittest.IsolatedAsyncioTestCase):
    def service(self):
        stt = LocalSTT()
        stt.start_processing_metrics = AsyncMock()
        stt.stop_processing_metrics = AsyncMock()
        return stt

    async def consume(self, service):
        return [frame async for frame in service.run_stt(bytes(32000))]

    async def test_inflight_cleanup_on_error(self):
        stt = self.service()
        with patch('server.transcription.transcribe', side_effect=RuntimeError('fixture')):
            frames = await self.consume(stt)
        self.assertIsInstance(frames[0], ErrorFrame)
        self.assertFalse(stt.inference_active)
        self.assertGreater(stt.last_inference_finished, 0)
        stt.stop_processing_metrics.assert_awaited_once()

    async def test_cancelled_turn_stays_busy_until_native_worker_finishes(self):
        stt = self.service()
        started, release = asyncio.Event(), asyncio.Event()
        async def worker(*args, **kwargs):
            started.set()
            await release.wait()
            return {'segments': []}
        with patch('server.transcription.asyncio.to_thread', new=worker):
            turn = asyncio.create_task(self.consume(stt))
            await asyncio.wait_for(started.wait(), 1)
            self.assertTrue(stt.inference_active)
            turn.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await turn
            self.assertTrue(stt.inference_active)
            stt.stop_processing_metrics.assert_awaited_once()
            worker_task = next(iter(stt._inference_tasks))
            release.set()
            await worker_task
            await asyncio.sleep(0)
            self.assertFalse(stt.inference_active)

    async def test_one_completed_worker_cannot_clear_another_workers_busy_flag(self):
        stt = self.service()
        first, second, started = asyncio.Event(), asyncio.Event(), asyncio.Event()
        arrivals = []
        async def worker(*args, **kwargs):
            event = first if not arrivals else second
            arrivals.append(event)
            if len(arrivals) == 2:
                started.set()
            await event.wait()
            return {'segments': []}
        with patch('server.transcription.asyncio.to_thread', new=worker):
            one = asyncio.create_task(self.consume(stt))
            two = asyncio.create_task(self.consume(stt))
            await asyncio.wait_for(started.wait(), 1)
            first.set()
            await one
            self.assertTrue(stt.inference_active)
            second.set()
            await two
            self.assertFalse(stt.inference_active)


class VisionSocketTests(unittest.TestCase):
    def test_deferred_real_websocket_frame_is_acknowledged_without_inference(self):
        from fastapi.testclient import TestClient
        from server.app import create_app
        token = 'synthetic-priority-test-token'
        engine = Mock(model_name='fixture', voice='fixture')
        engine.render = AsyncMock()
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        with patch('server.app.ContextBudget'), \
             patch('server.app.warm_stt_startup', new=AsyncMock(return_value={'ready': True})), \
             patch('server.vision_priority.VisionPriority._reason', return_value='visitor_speaking'), \
             patch('httpx.AsyncClient.post', new=AsyncMock()) as inference:
            with TestClient(create_app(token, engine)) as client:
                with client.websocket_connect('/vision', headers={'Authorization': 'Bearer '+token}) as socket:
                    socket.send_bytes(bytes(4) + image.getvalue())
                    receipt = socket.receive_json()
                    self.assertEqual(receipt['deferred_frames'], 1)
                    self.assertEqual(receipt['frames'], 0)
                    self.assertEqual(receipt['errors'], 0)
                    self.assertFalse(receipt['fresh'])
                    self.assertIsNone(receipt['age_ms'])
                inference.assert_not_awaited()
