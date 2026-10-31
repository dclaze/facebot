import tempfile
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server import skill_store
from server.scene import SceneState
from server.interaction import InteractionState
from server.sound_effects import SoundBank, SoundEffectFrame, SoundEffectRequest
from server.robin_skit import RobinSkit, RobinSkitFrame, RobinSkitRequest
from server.prepared_conversation import PreparedConversation


class RuntimeGates(unittest.IsolatedAsyncioTestCase):
    async def test_saved_disable_affects_actual_sound_robin_and_prepared_request(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(skill_store, 'state_path', return_value=Path(tmp)/'packs.json'), patch.object(skill_store, 'availability', return_value=True):
            state = InteractionState(SceneState())
            for pack, text, router, forbidden in [
                ('sound-effects', 'Make a ghost sound', SoundEffectRequest(SoundBank(), state, enabled=lambda: skill_store.enabled('sound-effects')), SoundEffectFrame),
                ('robin-williams', 'Is Robin Williams there?', RobinSkitRequest(RobinSkit(Path(tmp)), state, enabled=lambda: skill_store.enabled('robin-williams')), RobinSkitFrame),
                ('quick-jokes', 'Tell me a joke', PreparedConversation(state, enabled=skill_store.enabled, kiosk_mode=True), LLMContextFrame),
            ]:
                revision = skill_store.read_state()['revision']
                skill_store.update(pack, {'enabled':False, 'revision':revision})
                router.push_frame = AsyncMock()
                frame = LLMContextFrame(LLMContext([{'role':'user','content':text}]))
                await router.process_frame(frame, FrameDirection.DOWNSTREAM)
                output = [c.args[0] for c in router.push_frame.call_args_list]
                self.assertFalse(any(isinstance(f, forbidden) for f in output), pack)
                self.assertTrue(any(isinstance(f, TTSSpeakFrame) for f in output), pack)

