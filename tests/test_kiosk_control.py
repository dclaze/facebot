import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from pipecat.frames.frames import TranscriptionFrame
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
        processor.push_frame.assert_not_called()
