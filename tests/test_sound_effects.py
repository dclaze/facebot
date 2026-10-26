import asyncio
import hashlib
import importlib.util
import json
import unittest
from unittest.mock import AsyncMock

import numpy as np
from pipecat.frames.frames import (
    LLMContextFrame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame,
    InterruptionFrame, EndFrame, TTSSpeakFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from server.interaction import InteractionState
from server.scene import SceneState
from server.protocol import FaceSerializer
from server.sound_effects import CORPUS, SoundBank, SoundEffectFrame, SoundEffectRequest, SoundEffectPlayback


class CorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bank=SoundBank()

    def test_all_clips_are_bounded_distinct_and_click_faded(self):
        self.assertEqual(len(self.bank.effects),20)
        self.assertEqual(len(self.bank.pcm),40)
        self.assertEqual(len({hashlib.sha256(x).digest() for x in self.bank.pcm.values()}),40)
        for pcm in self.bank.pcm.values():
            samples=np.frombuffer(pcm,dtype='<i2').astype(float)/32768
            self.assertLessEqual(np.max(np.abs(samples)),.355)
            self.assertGreater(np.sqrt(np.mean(samples*samples)),.01)
            self.assertEqual(samples[0],0);self.assertEqual(samples[-1],0)
            self.assertLessEqual(len(samples),144000)

    def test_credited_source_processing_reproduces_every_pcm(self):
        spec=importlib.util.spec_from_file_location('sound_builder',CORPUS.parents[1]/'scripts/build-sound-corpus.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        selection=json.loads((CORPUS/'selection.json').read_text())
        self.assertEqual(set(selection['active_effects']),set(selection['recordings']))
        for kind,ids in self.bank.effects.items():
            for i,sound_id in enumerate(ids):self.assertEqual(mod.render(kind,i,selection),self.bank.pcm[sound_id])

    def test_natural_requests_and_all_aliases(self):
        cases={'Boo, make a ghost sound.':'ghost','Can you fart?':'fart','Please play a drumroll':'drumroll',
               'Boo!':'ghost','Bo.':'ghost','Hey Boo':'ghost','Boo please':'ghost',
               'Give me a laser sound effect':'laser','Make a cat sound':'cat','Play a bell':'bell',
               'Can you make a boing noise please?':'boing','Pew pew!':'laser','Make a sound effect':'ghost'}
        for text,effect in cases.items():self.assertEqual(self.bank.match(text),effect,text)
        self.assertEqual(self.bank.match('Hey Casper, play a bell','Casper'),'bell')
        for alias,effect in self.bank.aliases.items():
            self.assertEqual(self.bank.match('play a '+alias+' sound effect'),effect,alias)

    def test_mentions_negations_quotes_and_injections_do_not_play(self):
        for text in ('Do not play a ghost sound','Stop making fart sounds','I heard a cat','What is a ghost?',
                     'She said play a drumroll','"play a ghost sound"','Play thunder and tell me a joke',
                     'play ../../secrets','play https://example.com/a.wav','turn the volume up and fart',
                     'play an air raid siren','make a gun sound','fart '*80,None):
            self.assertIsNone(self.bank.match(text),text)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bank=SoundBank();self.state=InteractionState(SceneState())
        self.marks=[]
        self.router=SoundEffectRequest(self.bank,self.state,mark=self.marks.append)
        self.router.push_frame=AsyncMock()
        self.player=SoundEffectPlayback(self.bank,self.state,mark=self.marks.append)
        self.player.push_frame=AsyncMock()

    def context(self,text='Play a ghost sound'):
        return LLMContextFrame(LLMContext([{'role':'user','content':text}]))

    async def test_request_alternates_and_pcm_uses_native_epoch_wire(self):
        for expected in ('ghost_01','ghost_02','ghost_01'):
            await self.router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
            frame=self.router.push_frame.call_args.args[0]
            self.assertEqual(frame.sound_id,expected)
        await self.player.process_frame(frame,FrameDirection.DOWNSTREAM)
        frames=[c.args[0] for c in self.player.push_frame.call_args_list]
        self.assertIsInstance(frames[1],TTSStartedFrame)
        self.assertIsInstance(frames[-1],TTSStoppedFrame)
        audio=[f for f in frames if isinstance(f,TTSAudioRawFrame)]
        self.assertEqual(b''.join(f.audio for f in audio),self.bank.pcm['ghost_01'])
        serializer=FaceSerializer()
        await serializer.serialize(InterruptionFrame())
        for f in audio:
            packet=await serializer.serialize(f)
            self.assertEqual(int.from_bytes(packet[:8],'big'),1)
            self.assertLessEqual(len(packet),968)
        self.assertIn('prepared_reply',self.marks)

    async def test_mute_and_scene_events_cannot_trigger_sounds(self):
        self.state.scene.encounter.silenced=True
        await self.router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
        self.router.push_frame.assert_not_called()
        await self.player.process_frame(SoundEffectFrame(sound_id='ghost_01'),FrameDirection.DOWNSTREAM)
        self.player.push_frame.assert_not_called()
        self.state.scene.encounter.silenced=False
        frame=self.context();frame.scene_event={'kind':'stable_visual_arrival'}
        await self.router.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertIs(self.router.push_frame.call_args.args[0],frame)

    async def test_catalog_and_withheld_effects_never_fake_playback(self):
        for text in ('What sounds can you make?','Make a burp sound'):
            await self.router.process_frame(self.context(text),FrameDirection.DOWNSTREAM)
            self.assertIsInstance(self.router.push_frame.call_args.args[0],TTSSpeakFrame)
        self.router.push_frame.reset_mock();self.state.scene.encounter.silenced=True
        await self.router.process_frame(self.context('What sounds can you make?'),FrameDirection.DOWNSTREAM)
        self.router.push_frame.assert_not_called()

    async def test_actual_pipeline_cancels_inflight_effect_on_interrupt(self):
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask,PipelineParams
        from pipecat.pipeline.runner import PipelineRunner
        started=asyncio.Event();interrupted=asyncio.Event();received=[]
        class Sink(FrameProcessor):
            async def process_frame(self,frame,direction):
                await super().process_frame(frame,direction)
                if isinstance(frame,TTSAudioRawFrame):
                    received.append(frame);started.set();await asyncio.sleep(.02)
                if isinstance(frame,InterruptionFrame):interrupted.set()
                await self.push_frame(frame,direction)
        router=SoundEffectRequest(self.bank,self.state)
        player=SoundEffectPlayback(self.bank,self.state)
        task=PipelineTask(Pipeline([router,player,Sink()]),params=PipelineParams(),enable_rtvi=False)
        run=asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
        try:
            await task.queue_frame(self.context())
            await asyncio.wait_for(started.wait(),2)
            await task.queue_frame(InterruptionFrame())
            await asyncio.wait_for(interrupted.wait(),2)
            count=len(received)
            await asyncio.sleep(.08)
            self.assertEqual(len(received),count)
            self.assertLess(sum(len(f.audio) for f in received),len(self.bank.pcm['ghost_01']))
            await task.queue_frame(EndFrame());await asyncio.wait_for(run,2)
        finally:
            if not run.done():await task.cancel();await run

    async def test_production_services_and_transport_play_without_inference_and_release_floor(self):
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask,PipelineParams
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.transports.base_output import BaseOutputTransport
        from pipecat.transports.base_transport import TransportParams
        from pipecat.services.ollama.llm import OLLamaLLMService
        from pipecat.frames.frames import BotStartedSpeakingFrame,BotStoppedSpeakingFrame
        from server.guard import ReplyGuard
        from server.tts import LocalTTS
        from server.interaction import VisitorControl
        from server.timing import StageTiming
        packets=[];speaking=[];done=asyncio.Event();codec=FaceSerializer()
        class Engine:
            model_name='synthetic';voice='synthetic'
            async def stream(self,text):
                raise AssertionError('Sound request invoked speech synthesis')
                yield
        class Transport(BaseOutputTransport):
            async def start(self,frame):
                await super().start(frame);await self.set_transport_ready(frame)
            async def write_audio_frame(self,frame):
                packets.append(await codec.serialize(frame));return True
            async def send_message(self,frame):
                await codec.serialize(frame)
        class Sink(FrameProcessor):
            async def process_frame(self,frame,direction):
                await super().process_frame(frame,direction)
                if isinstance(frame,BotStartedSpeakingFrame):speaking.append('started')
                if isinstance(frame,BotStoppedSpeakingFrame):speaking.append('stopped');done.set()
                await self.push_frame(frame,direction)
        llm=OLLamaLLMService(base_url='http://127.0.0.1:1/v1')
        llm._stream_chat_completions=AsyncMock(side_effect=AssertionError('Sound invoked LLM'))
        timing=StageTiming()
        for stage in ('vad_start','vad_stop','stt_done'):timing.mark(stage)
        state=self.state;state.response_pending=True
        task=PipelineTask(Pipeline([VisitorControl(state),SoundEffectRequest(self.bank,state,mark=timing.mark),
            llm,ReplyGuard(),LocalTTS(Engine()),SoundEffectPlayback(self.bank,state,mark=timing.mark),
            Transport(TransportParams(audio_out_enabled=True,audio_out_sample_rate=24000)),Sink()]),
            params=PipelineParams(),enable_rtvi=False)
        run=asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
        try:
            await task.queue_frame(self.context('Play a pop sound'))
            await asyncio.wait_for(done.wait(),5)
            await asyncio.sleep(.02)
            llm._stream_chat_completions.assert_not_called()
            self.assertEqual(speaking,['started','stopped'])
            self.assertFalse(state.bot_speaking);self.assertFalse(state.response_pending)
            pcm=b''.join(p[8:] for p in packets)
            self.assertEqual(pcm[:len(self.bank.pcm['pop_01'])],self.bank.pcm['pop_01'])
            self.assertEqual(timing.report()['completed_samples'],0)
            self.assertEqual(len(timing.report()['prepared_reply_samples']),1)
            # Production websocket disconnect uses cancel, not EndFrame's
            # provider-specific two-second trailing-silence packet.
            await task.cancel();await asyncio.wait_for(run,3)
        finally:
            if not run.done():await task.cancel();await run
