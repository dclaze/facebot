import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from pipecat.frames.frames import TranscriptionFrame, OutputTransportMessageFrame, StartFrame, InterruptionFrame
from pipecat.processors.frame_processor import FrameDirection
from server.interaction import InteractionState, VisitorControl
from server.kiosk_control import MuteLatch
from server.scene import SceneState


class MuteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)/'kiosk-control.json'

    def test_disconnected_stop_survives_reinstantiation_until_explicit_resume(self):
        latch = MuteLatch(self.path)
        self.assertFalse(latch.value)
        self.assertTrue(latch.set_muted(True))
        self.assertTrue(MuteLatch(self.path).value)
        reconnected = InteractionState(SceneState())
        reconnected.scene.encounter.silenced = MuteLatch(self.path).value
        self.assertTrue(reconnected.scene.encounter.silenced)
        self.assertFalse(latch.set_muted(False))
        self.assertFalse(MuteLatch(self.path).value)

    def test_corrupt_data_fails_closed_and_explicit_resume_repairs(self):
        for malformed in ['broken', 'null', '[]', '{"version":1,"muted":0}',
                          '{"version":true,"muted":false}', '{"version":1,"muted":false,"extra":1}']:
            self.path.write_text(malformed)
            latch = MuteLatch(self.path)
            self.assertTrue(latch.value)
            self.assertIsNotNone(latch.error)
            self.assertFalse(latch.set_muted(False))
            self.assertIsNone(latch.error)
            self.assertFalse(MuteLatch(self.path).value)

    def test_failed_write_remains_muted_and_non_bool_is_rejected(self):
        latch = MuteLatch(self.path)
        latch.set_muted(True)
        with patch('server.kiosk_control.atomic_json', side_effect=OSError('test storage failure')):
            self.assertTrue(latch.set_muted(False))
            self.assertTrue(latch.value)
            self.assertIsNotNone(latch.error)
        self.assertTrue(MuteLatch(self.path).value)
        for bad in [0, 1, 'false', None]:
            with self.assertRaises(ValueError):
                latch.set_muted(bad)

    async def test_visitor_stop_resume_persists_and_updates_control_epoch(self):
        latch = MuteLatch(self.path)
        state = InteractionState(SceneState())
        processor = VisitorControl(state, on_mute=latch.set_muted)
        processor.push_frame, processor.broadcast_frame = AsyncMock(), AsyncMock()
        await processor.process_frame(TranscriptionFrame('stop laughing', '', ''), FrameDirection.DOWNSTREAM)
        self.assertTrue(state.scene.encounter.silenced)
        self.assertTrue(MuteLatch(self.path).value)
        self.assertEqual(state.control_epoch, 1)
        processor.broadcast_frame.assert_awaited_once()
        await processor.process_frame(TranscriptionFrame('you can talk again', '', ''), FrameDirection.DOWNSTREAM)
        self.assertFalse(state.scene.encounter.silenced)
        self.assertFalse(MuteLatch(self.path).value)

    async def test_failed_resume_callback_cannot_unmute_or_reach_model(self):
        latch = MuteLatch(self.path)
        latch.set_muted(True)
        state = InteractionState(SceneState())
        state.scene.encounter.silenced = True
        processor = VisitorControl(state, on_mute=latch.set_muted)
        processor.push_frame = AsyncMock()
        with patch('server.kiosk_control.atomic_json', side_effect=OSError('test storage failure')):
            await processor.process_frame(TranscriptionFrame('you can talk again', '', ''), FrameDirection.DOWNSTREAM)
        self.assertTrue(state.scene.encounter.silenced)
        messages = [call.args[0] for call in processor.push_frame.call_args_list]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].message, {'type': 'kiosk_state', 'muted': True})


class StateCueTests(unittest.IsolatedAsyncioTestCase):
    async def setup_processor(self, processor):
        from pipecat.clocks.system_clock import SystemClock
        from pipecat.utils.asyncio.task_manager import TaskManager
        from pipecat.processors.frame_processor import FrameProcessorSetup
        await processor.setup(FrameProcessorSetup(clock=SystemClock(), task_manager=TaskManager(), pipeline_worker=None))

    async def test_reconnect_replays_persisted_mute_after_start(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/'state.json'
            MuteLatch(path).set_muted(True)
            state = InteractionState(SceneState())
            state.scene.encounter.silenced = MuteLatch(path).value
            processor = VisitorControl(state)
            processor.push_frame = AsyncMock()
            await self.setup_processor(processor)
            start = StartFrame()
            await processor.process_frame(start, FrameDirection.DOWNSTREAM)
            frames = [call.args[0] for call in processor.push_frame.call_args_list]
            self.assertIs(frames[0], start)
            self.assertEqual(frames[1].message, {'type': 'kiosk_state', 'muted': True})
            await processor.cleanup()

    async def test_stop_interrupt_is_before_muted_cue_and_resume_false_cue(self):
        state = InteractionState(SceneState())
        processor = VisitorControl(state)
        order = []
        async def broadcast(kind):
            order.append(kind)
        async def push(frame, direction):
            order.append(frame)
        processor.broadcast_frame = broadcast
        processor.push_frame = push
        await processor.process_frame(TranscriptionFrame('stop', '', ''), FrameDirection.DOWNSTREAM)
        self.assertIs(order[0], InterruptionFrame)
        self.assertEqual(order[1].message, {'type': 'kiosk_state', 'muted': True})
        order.clear()
        await processor.process_frame(TranscriptionFrame('you can talk again', '', ''), FrameDirection.DOWNSTREAM)
        self.assertEqual(order[0].message, {'type': 'kiosk_state', 'muted': False})
        self.assertIsInstance(order[1], TranscriptionFrame)

    async def test_upstream_start_does_not_duplicate_native_state(self):
        processor = VisitorControl(InteractionState(SceneState()))
        processor.push_frame = AsyncMock()
        await self.setup_processor(processor)
        start = StartFrame()
        await processor.process_frame(start, FrameDirection.UPSTREAM)
        processor.push_frame.assert_awaited_once_with(start, FrameDirection.UPSTREAM)
        await processor.cleanup()


class OwnerStateCueTests(unittest.TestCase):
    def test_authenticated_stop_and_resume_queue_order_and_failed_resume(self):
        from fastapi.testclient import TestClient
        from types import SimpleNamespace
        from unittest.mock import Mock
        from server.app import create_app
        with tempfile.TemporaryDirectory() as root:
            latch = MuteLatch(Path(root)/'state.json')
            with patch('server.app.ContextBudget'), patch('server.app.MuteLatch', return_value=latch):
                app = create_app('synthetic-kiosk-state-token-0001', Mock())
            stop = next(route.endpoint for route in app.routes if route.path == '/owner/stop')
            cells = dict(zip(stop.__code__.co_freevars, stop.__closure__))
            state = InteractionState(SceneState())
            task = SimpleNamespace(queue_frame=AsyncMock())
            cells['current_interaction'].cell_contents = state
            cells['current_task'].cell_contents = task
            client = TestClient(app)
            headers = {'Authorization': 'Bearer synthetic-kiosk-state-token-0001'}
            self.assertEqual(client.post('/owner/stop').status_code, 403)
            self.assertEqual(client.post('/owner/stop', headers=headers).status_code, 200)
            frames = [call.args[0] for call in task.queue_frame.call_args_list]
            self.assertIsInstance(frames[0], InterruptionFrame)
            self.assertEqual(frames[1].message, {'type': 'kiosk_state', 'muted': True})
            self.assertTrue(MuteLatch(latch.path).value)
            task.queue_frame.reset_mock()
            self.assertEqual(client.post('/owner/resume', headers=headers).status_code, 200)
            self.assertEqual(task.queue_frame.call_args.args[0].message, {'type': 'kiosk_state', 'muted': False})
            with patch('server.kiosk_control.atomic_json', side_effect=OSError('storage failure')):
                self.assertEqual(client.post('/owner/resume', headers=headers).status_code, 503)
            self.assertEqual(task.queue_frame.call_args.args[0].message, {'type': 'kiosk_state', 'muted': True})
