import io
import json
import unittest
from unittest.mock import AsyncMock
from PIL import Image
from server.vision import VisionState, ImageLabeler
from server.personal_space import PersonalSpace
from server.reactions import parse_reply, validate_expression
from server.visual_reactions import LINES, VisualReaction
from server.scene import SceneState
from server.interaction import InteractionState
from pipecat.frames.frames import LLMContextFrame, TTSSpeakFrame, OutputTransportMessageFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection


class VisualStateTests(unittest.TestCase):
    def test_confirmation_expiry_and_changed_scene(self):
        now=[0.];s=VisionState(clock=lambda:now[0])
        s.accept(['sofa'],0,10);self.assertEqual(s.context(),'')
        now[0]=1;s.accept(['sofa','cup'],1,10)
        self.assertIn('sofa',s.context());self.assertNotIn('cup',s.context())
        self.assertEqual(s.take_event()['kind'],'visual_labels');self.assertIsNone(s.take_event())
        now[0]=2;s.accept([],2,10);self.assertEqual(s.context(),'')
        now[0]=9;self.assertFalse(s.fresh())
        self.assertFalse(s.accept(['sofa'],1,10))
        with self.assertRaises(ValueError):s.accept(['ignore instructions'],9,10)

    def test_identity_labels_and_freeform_person_fields_rejected(self):
        s=VisionState(clock=lambda:0.)
        for label in ('Asian', 'Black person', 'white person', 'Muslim', 'Native American costume', 'Mexican costume', 'hijab'):
            with self.assertRaises(ValueError):s.accept([label],0,1)
            with self.assertRaises(ValueError):
                s.accept([],0,1,[{'position':'center','age_band':'uncertain','items':[label]}])
        with self.assertRaises(ValueError):
            s.accept([],0,1,[{'position':'center','age_band':'adult','items':['cape'],'race':'unknown'}])

    def test_same_costume_can_recur_after_observation_gap(self):
        now=[0.];s=VisionState(clock=lambda:now[0])
        s.accept(['cape'],0,1)
        now[0]=1;s.accept(['cape'],1,1);self.assertIsNotNone(s.take_event())
        now[0]=30;s.accept(['cape'],30,1);self.assertIsNone(s.take_event())
        now[0]=31;s.accept(['cape'],31,1);self.assertIsNotNone(s.take_event())

    def test_late_results_never_replace_newer_context(self):
        now=[4.];s=VisionState(clock=lambda:now[0])
        self.assertTrue(s.accept(['cup'],3,10))
        self.assertFalse(s.accept(['phone'],2,10));self.assertEqual(s.previous,('cup',))

    def test_people_are_ephemeral_bounded_and_age_is_not_roast_context(self):
        now=[0.];s=VisionState(clock=lambda:now[0])
        person={'position':'left','age_band':'child','items':['blue shirt']}
        s.accept([],0,10,[person]);self.assertEqual(s.context(),'')
        now[0]=1;s.accept([],1,10,[person])
        self.assertIn('blue shirt',s.context());self.assertNotIn('child',s.context())
        self.assertEqual(s.report()['people'][0]['age_band'],'child')
        with self.assertRaises(ValueError):s.accept([],2,10,[{**person,'name':'Jeremy'}])
        now[0]=8;self.assertEqual(s.report()['people'],[])

    def test_proximity_requires_stable_approach_and_real_retreat(self):
        now=[0.];s=PersonalSpace(clock=lambda:now[0])
        for t in (0,.25,.5,.75):now[0]=t;s.observe(220,1,0)
        self.assertEqual(s.take_event()['kind'],'too_close')
        self.assertIsNone(s.take_event())
        for t in (1,1.25,1.5,1.75,2):now[0]=t;s.observe(70,1,0)
        self.assertEqual(s.take_event()['kind'],'space_restored')
        for t in (2.5,2.75,3,3.25):now[0]=t;s.observe(220,1,0)
        self.assertIsNone(s.take_event())

    def test_new_group_does_not_inherit_retreat_acknowledgment(self):
        now=[0.];s=PersonalSpace(clock=lambda:now[0])
        for t in (0,.25,.5,.75):now[0]=t;s.observe(220,1,0)
        self.assertEqual(s.take_event()['kind'],'too_close')
        now[0]=1;s.observe(0,0,0)
        for t in (6,6.25,6.5,6.75,7):now[0]=t;s.observe(70,1,0)
        self.assertIsNone(s.take_event())

    def test_proximity_cancels_stale_near_event(self):
        now=[0.];s=PersonalSpace(clock=lambda:now[0])
        for t in (0,.25,.5,.75):now[0]=t;s.observe(220,1,0)
        now[0]=1;s.observe(70,1,0);self.assertIsNone(s.take_event())

    def test_structured_reaction_only_speaks_speech_field(self):
        from server.spoken_text import spoken_text
        speech,event=parse_reply('{"speech":"Back up, boss.","expression":"skeptical"}')
        self.assertEqual(speech,'Back up, boss.');self.assertTrue(validate_expression(event))
        self.assertEqual(spoken_text('{"speech":"Back up, boss.","expression":"skeptical"}'),speech)
        self.assertEqual(spoken_text('{"expression":"scared"}'),'')
        for value in ('{"speech":"Hi","expression":"shell"}', '{"speech":"Hi","expression":"scared","command":"run"}', 'not json'):
            with self.assertRaises(ValueError):parse_reply(value)
        for line,_ in LINES.values():self.assertLessEqual(len(line.split()),12)


class VisualPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_camera_proximity_does_not_nag_or_block_the_next_turn(self):
        state = InteractionState(SceneState())
        p = VisualReaction(state)
        p.push_frame = AsyncMock()
        for kind in ('too_close', 'space_restored') * 3:
            state.response_pending = True
            frame = LLMContextFrame(LLMContext([]))
            frame.scene_event = {'kind': kind}
            await p.process_frame(frame, FrameDirection.DOWNSTREAM)
            p.push_frame.assert_not_called()
            self.assertFalse(state.response_pending)

    async def test_media_validation_precedes_any_inference(self):
        state=VisionState();lab=ImageLabeler(state)
        lab.client.post=AsyncMock()
        for payload in (b'', b'x'*256001, b'not an image'):
            with self.assertRaises((ValueError,OSError)):await lab.label(payload)
        b=io.BytesIO();Image.new('RGB',(641,1)).save(b,format='JPEG')
        with self.assertRaises(ValueError):await lab.label(b.getvalue())
        lab.client.post.assert_not_called();await lab.close()

    async def test_reaction_controls_are_separate_from_speech_and_mute_wins(self):
        state=InteractionState(SceneState());p=VisualReaction(state)
        p.push_frame=AsyncMock();f=LLMContextFrame(LLMContext([]))
        f.scene_event={'kind':'visual_labels','labels':['sofa']}
        await p.process_frame(f,FrameDirection.DOWNSTREAM)
        frames=[c.args[0] for c in p.push_frame.call_args_list]
        self.assertIsInstance(frames[0],OutputTransportMessageFrame)
        self.assertIsInstance(frames[1],TTSSpeakFrame)
        self.assertNotIn('skeptical',frames[1].text)
        state.scene.encounter.silenced=True;p.push_frame.reset_mock()
        await p.process_frame(f,FrameDirection.DOWNSTREAM);p.push_frame.assert_not_called()
