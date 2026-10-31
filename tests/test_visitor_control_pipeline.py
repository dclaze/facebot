"""Real Pipecat queue regression; synthetic transcripts are not STT/device evidence."""
import asyncio
from pathlib import Path
import tempfile
import unittest

from pipecat.frames.frames import DataFrame, InterruptionFrame, OutputTransportMessageFrame, TranscriptionFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from server.interaction import InteractionState, VisitorControl
from server.kiosk_control import MuteLatch
from server.scene import SceneState


class VisitorControlPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_stop_negative_and_resume_keep_real_processing_queues_alive(self):
        """Exercise real broadcast/push/queue tasks, including repeated interruption."""
        cues = asyncio.Queue()
        markers = asyncio.Queue()
        forwarded = []
        downstream = []
        upstream_interruptions = []

        class Upstream(FrameProcessor):
            async def process_frame(self, frame, direction):
                await super().process_frame(frame, direction)
                if direction == FrameDirection.UPSTREAM and isinstance(frame, InterruptionFrame):
                    upstream_interruptions.append(frame)
                await self.push_frame(frame, direction)

        class Sink(FrameProcessor):
            async def process_frame(self, frame, direction):
                await super().process_frame(frame, direction)
                if direction == FrameDirection.DOWNSTREAM:
                    if isinstance(frame, OutputTransportMessageFrame):
                        downstream.append(frame.message)
                        await cues.put(frame.message)
                    elif isinstance(frame, InterruptionFrame):
                        downstream.append('interruption')
                    elif isinstance(frame, TranscriptionFrame):
                        forwarded.append(frame.text)
                    elif type(frame) is DataFrame:
                        await markers.put(frame)
                await self.push_frame(frame, direction)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'control.json'
            latch = MuteLatch(path)
            state = InteractionState(SceneState())
            processor = VisitorControl(state, on_mute=latch.set_muted)
            task = PipelineTask(Pipeline([Upstream(), processor, Sink()]),
                                params=PipelineParams(), enable_rtvi=False)
            run = asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
            try:
                self.assertEqual(await asyncio.wait_for(cues.get(), 2),
                                 {'type': 'kiosk_state', 'muted': False})
                for cycle in range(3):
                    await task.queue_frame(TranscriptionFrame('Please be quiet.', '', ''))
                    self.assertEqual(await asyncio.wait_for(cues.get(), 1),
                                     {'type': 'kiosk_state', 'muted': True})
                    self.assertTrue(state.scene.encounter.silenced)
                    self.assertTrue(MuteLatch(path).value)
                    self.assertEqual(downstream[-2:], ['interruption', {'type': 'kiosk_state', 'muted': True}])

                    await task.queue_frame(TranscriptionFrame("You can't talk again.", '', ''))
                    marker = DataFrame()
                    await task.queue_frame(marker)
                    self.assertIs(await asyncio.wait_for(markers.get(), 1), marker)
                    self.assertTrue(state.scene.encounter.silenced)
                    self.assertTrue(MuteLatch(path).value)
                    self.assertTrue(cues.empty())

                    await task.queue_frame(TranscriptionFrame('Talk again.', '', ''))
                    self.assertEqual(await asyncio.wait_for(cues.get(), 1),
                                     {'type': 'kiosk_state', 'muted': False})
                    marker = DataFrame()
                    await task.queue_frame(marker)
                    self.assertIs(await asyncio.wait_for(markers.get(), 1), marker)
                    self.assertFalse(state.scene.encounter.silenced)
                    self.assertFalse(MuteLatch(path).value)
                    self.assertEqual(forwarded, ['Talk again.'] * (cycle + 1))
                    self.assertEqual(state.control_epoch, cycle + 1)
                    self.assertEqual(len(upstream_interruptions), cycle + 1)
            finally:
                await task.cancel()
                await asyncio.wait_for(run, 3)


if __name__ == '__main__':
    unittest.main()
