import unittest
from unittest.mock import AsyncMock
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.interaction import InteractionState
from server.scene import SceneState
from server.visual_reactions import VisualReaction, REMARK_COOLDOWN_SECONDS


class RepetitionTests(unittest.IsolatedAsyncioTestCase):
    async def test_flicker_reconnect_and_alternative_object(self):
        now, recent = [0.], {}
        state = InteractionState(SceneState())

        async def emit(labels):
            # New processor simulates a reconnect, without forgetting the joke.
            processor = VisualReaction(state, clock=lambda: now[0], recent=recent)
            processor.push_frame = AsyncMock()
            frame = LLMContextFrame(LLMContext([]))
            frame.scene_event = {'kind': 'visual_labels', 'labels': labels}
            state.response_pending = True
            await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
            return [call.args[0].text for call in processor.push_frame.call_args_list
                    if isinstance(call.args[0], TTSSpeakFrame)]

        self.assertEqual(len(await emit(['sofa'])), 1)
        now[0] = 31
        self.assertEqual(await emit(['sofa']), [])
        self.assertFalse(state.response_pending)
        alternative = await emit(['sofa', 'cup'])
        self.assertEqual(len(alternative), 1)
        self.assertIn('cup', alternative[0])
        now[0] = REMARK_COOLDOWN_SECONDS
        self.assertEqual(len(await emit(['sofa'])), 1)
