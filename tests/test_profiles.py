import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from server import profiles, coaching, settings
from server.persona import bounded_context, instructions, relevant_facts


class ProfilesTests(unittest.TestCase):
    def tearDown(self):
        profiles.active.cache_clear()

    def select(self, name):
        profiles.active.cache_clear()
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, FACEBOT_PROFILE=name).start()

    def test_neutral_prompt_and_facts_do_not_inherit_event(self):
        self.select('neutral')
        with patch('server.persona.coaching_prompt', return_value=None):
            text = ' '.join(m['content'] for m in bounded_context([]))
        for word in ('ghost', 'halloween', 'candy', 'mill valley', 'boss', 'bud'):
            self.assertNotIn(word, text.lower())
        self.assertIsNone(relevant_facts('Tell me about the Dipsea railway'))
        self.assertIn('Honor requests for silence', text)
        self.assertIn('Never invent identities', text)
        self.assertIn('Do not address visitors by personal names', text)
        self.assertEqual(settings.read()['character_name'], 'Host')
        self.assertEqual(profiles.active()['visual_reactions'], {})

    def test_halloween_preserves_character_and_name_preference(self):
        self.select('halloween')
        text = instructions('Boo')
        self.assertIn('child-safe ghost', text)
        self.assertIn('Halloween in Mill Valley', text)
        self.assertIn('Do not address visitors by personal names', text)
        self.assertIn('ONE PIECE', text)
        self.assertIn('November 19, 1905', relevant_facts('Tell me about the Dipsea'))
        self.assertNotIn('Back up', str(profiles.active()['visual_reactions']))

    def test_selection_is_fixed_until_restart(self):
        self.select('neutral')
        self.assertEqual(profiles.active()['id'], 'neutral')
        os.environ['FACEBOT_PROFILE'] = 'halloween'
        self.assertEqual(profiles.active()['id'], 'neutral')

    def test_invalid_selection_fails_instead_of_loading_another_event(self):
        for name in ('../halloween', '/tmp/profile', 'missing', ''):
            profiles.active.cache_clear()
            with patch.dict(os.environ, FACEBOT_PROFILE=name):
                with self.assertRaises(ValueError): profiles.active()

    def test_new_event_is_data_only_and_bad_profile_is_rejected(self):
        import shutil
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(profiles.ROOT, root/'contexts')
            with patch.object(profiles, 'ROOT', root/'contexts'):
                value = json.loads((profiles.ROOT/'events/neutral.json').read_text())
                value['id'] = 'exhibit'
                value['instructions'] = 'Welcome visitors to the science exhibit.'
                path = profiles.ROOT/'events/exhibit.json'
                path.write_text(json.dumps(value))
                self.assertIn('science exhibit', profiles.load('exhibit')['instructions'])
                value['arrival'] = ['A greeting', 'execute-shell']
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError): profiles.load('exhibit')

    def test_private_state_isolated_and_legacy_halloween_preserved(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(profiles, 'PRIVATE_ROOT', Path(folder)):
            self.select('halloween')
            coaching.save(['Candy station coaching.'])
            settings.save(dict(settings.DEFAULTS, character_name='Boo'))
            self.assertEqual(profiles.private_path('night-coaching.json'), Path(folder)/'night-coaching.json')
            (Path(folder)/'recording-config.json').write_text('{"enabled":true,"audio":true}')
            profiles.active.cache_clear()
            os.environ['FACEBOT_PROFILE'] = 'neutral'
            self.assertEqual(coaching.read()['rules'], [])
            self.assertEqual(settings.read()['character_name'], 'Host')
            from server.recording import InteractionRecorder
            recorder = InteractionRecorder.configured()
            self.assertFalse(recorder.enabled)
            self.assertEqual(recorder.root, Path(folder)/'profiles/neutral/interactions')
            coaching.save(['Welcome to the exhibit.'])
            profiles.active.cache_clear()
            os.environ['FACEBOT_PROFILE'] = 'halloween'
            self.assertEqual(coaching.read()['rules'], ['Candy station coaching.'])


class ProfilePipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_neutral_arrival_and_visual_labels_never_use_ghost_lines(self):
        from server.visual_reactions import VisualReaction
        from server.scene import SceneState
        from server.interaction import InteractionState
        from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame
        from pipecat.processors.aggregators.llm_context import LLMContext
        from pipecat.processors.frame_processor import FrameDirection
        profiles.active.cache_clear()
        try:
            with patch.dict(os.environ, FACEBOT_PROFILE='neutral'):
                state = InteractionState(SceneState())
                processor = VisualReaction(state)
                processor.push_frame = AsyncMock()
                for kind, labels in [('stable_visual_arrival', []), ('visual_labels', ['sofa','pumpkin']), ('too_close', [])]:
                    frame = LLMContextFrame(LLMContext([]))
                    frame.scene_event = {'kind': kind, 'labels': labels}
                    state.response_pending = True
                    await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
                spoken = [c.args[0].text for c in processor.push_frame.call_args_list if isinstance(c.args[0], TTSSpeakFrame)]
                self.assertEqual(spoken, ['Hello. Welcome.'])
                self.assertFalse(state.response_pending)
                state.scene.encounter.silenced = True
                processor.push_frame.reset_mock()
                frame.scene_event = {'kind':'stable_visual_arrival'}
                await processor.process_frame(frame, FrameDirection.DOWNSTREAM)
                processor.push_frame.assert_not_called()
        finally:
            profiles.active.cache_clear()
