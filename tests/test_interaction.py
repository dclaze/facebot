import unittest
from unittest.mock import AsyncMock
from pipecat.frames.frames import TranscriptionFrame, UserStartedSpeakingFrame, BotStoppedSpeakingFrame, LLMContextFrame, LLMFullResponseEndFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.scene import SceneState
from server.interaction import InteractionState, VisitorControl, ProactiveTurn


class InteractionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 0.
        self.scene = SceneState(clock=lambda: self.now)
        self.state = InteractionState(self.scene, clock=lambda: self.now)
        self.context = LLMContext([])
        self.proactive = ProactiveTurn(self.state, self.context)
        self.proactive.push_frame = AsyncMock()
        self.control = VisitorControl(self.state)
        self.control.push_frame = AsyncMock()
        self.control.broadcast_frame = AsyncMock()

    def arrival(self):
        for i in range(5):
            self.now = i*.25
            self.scene.update({'visible_faces':1,'age_ms':0})

    async def test_arrival_produces_labeled_context_not_user_text(self):
        self.arrival()
        await self.proactive.tick()
        frame = self.proactive.push_frame.call_args.args[0]
        self.assertIsInstance(frame, LLMContextFrame)
        self.assertEqual(frame.scene_event['kind'], 'stable_visual_arrival')
        self.assertEqual(self.context.get_messages(), [])
        await self.proactive.tick()
        self.assertEqual(self.proactive.push_frame.call_count, 1)

    async def test_speech_cancels_pending_greeting(self):
        self.arrival()
        await self.control.process_frame(UserStartedSpeakingFrame(), FrameDirection.UPSTREAM)
        await self.proactive.tick()
        self.proactive.push_frame.assert_not_called()
        self.state.user_speaking = False
        self.now += .25
        self.scene.update({'visible_faces':1,'age_ms':0})
        await self.proactive.tick()
        self.proactive.push_frame.assert_not_called()

    async def test_stop_interrupts_and_blocks_context_until_explicit_resume(self):
        self.arrival()
        await self.control.process_frame(TranscriptionFrame('Please stop talking.', '', ''), FrameDirection.DOWNSTREAM)
        self.assertTrue(self.scene.encounter.silenced)
        self.control.broadcast_frame.assert_awaited_once()
        self.assertEqual(self.control.push_frame.call_args.args[0].message,
                         {'type': 'kiosk_state', 'muted': True})
        await self.proactive.process_frame(LLMContextFrame(self.context), FrameDirection.DOWNSTREAM)
        self.proactive.push_frame.assert_not_called()
        await self.control.process_frame(TranscriptionFrame('You can talk again.', '', ''), FrameDirection.DOWNSTREAM)
        self.assertFalse(self.scene.encounter.silenced)

    async def test_bot_busy_prevents_initiation(self):
        self.arrival()
        self.state.response_pending = True
        await self.proactive.tick()
        self.proactive.push_frame.assert_not_called()
        await self.control.process_frame(BotStoppedSpeakingFrame(), FrameDirection.UPSTREAM)
        await self.proactive.tick()
        self.proactive.push_frame.assert_not_called()  # quiet gap after playback

    async def test_silence_guard_does_not_speak_fallback(self):
        from server.guard import ReplyGuard
        guard = ReplyGuard(is_silenced=lambda: True)
        guard.push_frame = AsyncMock()
        await guard.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)
        self.assertEqual(guard.push_frame.call_count, 1)
        self.assertIsInstance(guard.push_frame.call_args.args[0], LLMFullResponseEndFrame)

    async def test_event_integration_uses_system_event_and_drops_prior_visitor(self):
        from server.app import FrameTrace
        trace = FrameTrace(name='before_llm', scene=self.scene)
        trace.push_frame = AsyncMock()
        self.context.add_message({'role':'user', 'content':'My name is Maya.'})
        self.arrival()
        await self.proactive.tick()
        frame = self.proactive.push_frame.call_args.args[0]
        await trace.process_frame(frame, FrameDirection.DOWNSTREAM)
        messages = self.context.get_messages()
        self.assertFalse(any(m['role']=='user' for m in messages))
        self.assertIn('EVENT: stable_visual_arrival', messages[-1]['content'])
        self.assertEqual(messages[-1]['role'], 'system')
        self.context.add_message({'role':'user', 'content':'Hello ghost'})
        await trace.process_frame(LLMContextFrame(self.context), FrameDirection.DOWNSTREAM)
        self.assertNotIn('EVENT: stable_visual_arrival', str(self.context.get_messages()))

    async def test_real_pipeline_starts_event_timer_and_cleans_it_up(self):
        import asyncio
        from pipecat.frames.frames import EndFrame
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask, PipelineParams
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.processors.frame_processor import FrameProcessor
        self.arrival()
        ready = asyncio.Event()
        class Sink(FrameProcessor):
            async def process_frame(self, frame, direction):
                await super().process_frame(frame, direction)
                if getattr(frame, 'scene_event', None):
                    ready.set()
                await self.push_frame(frame, direction)
        processor = ProactiveTurn(self.state, self.context)
        task = PipelineTask(Pipeline([processor, Sink()]), params=PipelineParams(), enable_rtvi=False)
        run = asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)
            await task.queue_frame(EndFrame())
            await asyncio.wait_for(run, timeout=2)
            self.assertIsNone(processor._ticker)
        finally:
            if not run.done():
                await task.cancel()
                await run
