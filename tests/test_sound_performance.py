import asyncio
import unittest
from unittest.mock import AsyncMock
from pipecat.frames.frames import (
    LLMContextFrame, LLMTextFrame, LLMFullResponseEndFrame, LLMFullResponseStartFrame,
    TTSSpeakFrame, TTSAudioRawFrame, TTSStoppedFrame, InterruptionFrame, EndFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from server.scene import SceneState
from server.interaction import InteractionState
from server.sound_effects import SoundBank, SoundEffectFrame, SoundEffectRequest, SoundEffectPlayback
from server.sound_performance import SoundPerformance, AutomaticSoundDirector, load_performance
from server.guard import FALLBACK


def context(text):
    return LLMContextFrame(LLMContext([{'role':'user','content':text}]))


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.bank=SoundBank();self.state=InteractionState(SceneState());self.now=0
        self.performance=SoundPerformance(self.bank,self.state,load_performance('halloween',self.bank),clock=lambda:self.now)

    def test_matching_reaction_and_joke_without_prompt_or_inference(self):
        self.performance.observe(context('Nice hat'))
        frame=self.performance.choose('Nice witch hat. Finally, qualified management.')
        self.assertEqual(frame.sound_id,'ghost_laugh_01');self.assertTrue(frame.automatic)
        self.now=31
        self.performance.choose('Hello.');self.performance.choose('Yes.')
        self.performance.observe(context('Tell me a joke'))
        self.assertTrue(self.performance.choose('Mummies listen to wrap music.').sound_id.startswith('rimshot'))

    def test_cooldown_gap_and_repeat_limits(self):
        p=self.performance;p.observe(context('Tell me a joke'))
        self.assertIsNotNone(p.choose('Ghosts cheer by booing.'))
        for _ in range(6):self.assertIsNone(p.choose('My good side costs extra.'))
        self.now=31
        self.assertIsNotNone(p.choose('My good side costs extra.'))
        self.now=62
        self.assertIsNone(p.choose('Nice witch hat.'))
        self.assertIsNone(p.choose('Nice witch hat.'))
        self.assertIsNotNone(p.choose('Nice witch hat.'))
        self.now=93
        for _ in range(4):self.assertIsNone(p.choose('Nice witch hat.'))
        self.now=183
        self.assertEqual(p.choose('Nice witch hat.').sound_id,'ghost_laugh_02')

    def test_silence_distress_speech_and_fallback_have_no_embellishment(self):
        p=self.performance
        for request,reply in [('I am scared','Nice witch hat.'),('Help me','My good side costs extra.'),
                              ('Tell me a joke',FALLBACK),('Tell me a joke',"Sorry, I can't help."),
                              ('What time is it?','It is six o clock.')]:
            p.observe(context(request));self.assertIsNone(p.choose(reply))
        p.observe(context('Tell me a joke'));self.state.user_speaking=True
        self.assertIsNone(p.choose('Mummies listen to wrap music.'))
        self.state.user_speaking=False;self.state.scene.encounter.silenced=True
        self.assertIsNone(p.choose('Mummies listen to wrap music.'))

    def test_other_event_profiles_do_not_inherit_halloween_effects(self):
        self.assertIsNone(load_performance('neutral',self.bank))
        p=SoundPerformance(self.bank,self.state)
        p.observe(context('Tell me a joke'));self.assertIsNone(p.choose('Nice witch hat.'))


class PerformancePipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bank=SoundBank();self.state=InteractionState(SceneState())
        self.performance=SoundPerformance(self.bank,self.state,load_performance('halloween',self.bank))

    async def test_direct_request_has_no_automatic_double_sound(self):
        p=SoundEffectRequest(self.bank,self.state,performance=self.performance);p.push_frame=AsyncMock()
        await p.process_frame(context('Bo.'),FrameDirection.DOWNSTREAM)
        self.assertIsInstance(p.push_frame.call_args.args[0],SoundEffectFrame)
        self.assertFalse(p.push_frame.call_args.args[0].automatic)
        self.assertIsNone(self.performance.choose('Nice witch hat.'))
        await p.process_frame(context('Stop sound effects'),FrameDirection.DOWNSTREAM)
        self.assertFalse(self.performance.enabled)
        self.assertIsInstance(p.push_frame.call_args.args[0],TTSSpeakFrame)

    async def test_cancelled_or_stale_auto_effect_never_reaches_pcm(self):
        self.performance.observe(context('Tell me a joke'))
        frame=self.performance.choose('Ghosts cheer by booing.')
        player=SoundEffectPlayback(self.bank,self.state,performance=self.performance);player.push_frame=AsyncMock()
        self.performance.interrupted()
        await player.process_frame(frame,FrameDirection.DOWNSTREAM)
        player.push_frame.assert_not_called()
        self.assertEqual(self.performance.started,0)

    async def test_generated_reply_effect_follows_end_and_interrupt_discards_partial_reply(self):
        d=AutomaticSoundDirector(self.performance);d.push_frame=AsyncMock()
        d._start_interruption=AsyncMock()
        self.performance.observe(context('Tell me a joke'))
        for frame in (LLMFullResponseStartFrame(),LLMTextFrame('Mummies listen to wrap music.'),LLMFullResponseEndFrame()):
            await d.process_frame(frame,FrameDirection.DOWNSTREAM)
        frames=[c.args[0] for c in d.push_frame.call_args_list]
        self.assertIsInstance(frames[-2],LLMFullResponseEndFrame)
        self.assertIsInstance(frames[-1],SoundEffectFrame)
        d.push_frame.reset_mock()
        for frame in (LLMFullResponseStartFrame(),LLMTextFrame('Nice witch hat.'),InterruptionFrame(),LLMFullResponseEndFrame()):
            await d.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertFalse(any(isinstance(c.args[0],SoundEffectFrame) for c in d.push_frame.call_args_list))

    async def test_real_tts_queue_finishes_speech_before_automatic_effect(self):
        await self.check_tts_queue([TTSSpeakFrame('Nice witch hat. Finally, qualified management.')])

    async def test_generated_tts_queue_finishes_speech_before_automatic_effect(self):
        await self.check_tts_queue([LLMFullResponseStartFrame(),
            LLMTextFrame('Nice witch hat. Finally, qualified management.'),LLMFullResponseEndFrame()])

    async def check_tts_queue(self,frames):
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask,PipelineParams
        from pipecat.pipeline.runner import PipelineRunner
        from server.tts import LocalTTS
        done=asyncio.Event();audio=[];stops=[];synthesized=[]
        speech_pcm=(b'\x01\x02'*480)*2
        class Engine:
            model_name='synthetic';voice='synthetic'
            async def stream(self,text):
                synthesized.append(text)
                yield speech_pcm,[]
        class Sink(FrameProcessor):
            async def process_frame(self,frame,direction):
                await super().process_frame(frame,direction)
                if isinstance(frame,TTSAudioRawFrame):audio.append((getattr(frame,'sound_effect',False),frame.audio))
                if isinstance(frame,TTSStoppedFrame):
                    stops.append(frame)
                    if len(stops)==2:done.set()
                await self.push_frame(frame,direction)
        self.performance.observe(context('Nice hat'))
        task=PipelineTask(Pipeline([AutomaticSoundDirector(self.performance),LocalTTS(Engine()),
            SoundEffectPlayback(self.bank,self.state,performance=self.performance),Sink()]),
            params=PipelineParams(),enable_rtvi=False)
        run=asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
        try:
            for frame in frames:await task.queue_frame(frame)
            await asyncio.wait_for(done.wait(),3)
            first_effect=next(i for i,(effect,_) in enumerate(audio) if effect)
            self.assertTrue(synthesized)
            self.assertEqual(b''.join(pcm for _,pcm in audio[:first_effect]),speech_pcm*len(synthesized))
            self.assertTrue(all(effect for effect,_ in audio[first_effect:]))
            self.assertEqual(b''.join(pcm for _,pcm in audio[first_effect:]),self.bank.pcm['ghost_laugh_01'])
            self.assertEqual(self.performance.completed,1)
            await task.cancel();await asyncio.wait_for(run,3)
        finally:
            if not run.done():await task.cancel();await run
