import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from pipecat.frames.frames import (
    LLMContextFrame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame,
    InterruptionFrame, EndFrame, TTSSpeakFrame, BotStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from server.interaction import InteractionState, VisitorControl
from server.scene import SceneState
from server.protocol import FaceSerializer
from server.robin_skit import RobinSkit, RobinSkitFrame, RobinSkitRequest, RobinSkitPlayback, matches


class RequestTests(unittest.TestCase):
    def test_questions_and_commands(self):
        for text in ('Robin Williams?', 'Who was Robin Williams?', 'Tell me about Robin Williams.',
                     'Do you know Robin Williams?', 'Are you Robin Williams?',
                     'What do you know about Robin Williams?', 'Boo, play the Robin Williams skit!',
                     'Could you play Robin Williams please?', "Play Robin Williams's tribute"):
            self.assertTrue(matches(text), text)
        self.assertTrue(matches('Hey Casper, tell me about Robin Williams', 'Casper'))

    def test_not_every_mention_is_a_request(self):
        for text in ('Do not play Robin Williams', "Don't tell me about Robin Williams",
                     'Stop Robin Williams', 'I like Robin Williams', 'Who is Robin Hood?',
                     'She said play Robin Williams', '"Play Robin Williams"',
                     'Play Robin Williams and a bell', 'play ../../Robin Williams', None):
            self.assertFalse(matches(text), text)

    def test_media_integrity_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertFalse(RobinSkit(root).pcm)
            (root/'manifest.json').write_text(json.dumps({'version':1,'file':'../other.wav','sha256':'bad'}))
            self.assertFalse(RobinSkit(root).pcm)
            (root/'clip.wav').write_bytes(b'tampered')
            (root/'manifest.json').write_text(json.dumps({'version':1,'file':'clip.wav','sha256':'bad'}))
            self.assertFalse(RobinSkit(root).pcm)


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.skit = RobinSkit()
        if not self.skit.pcm:
            self.skipTest('Private owner skit is not installed on this checkout')
        self.state = InteractionState(SceneState())

    def context(self, text='Tell me about Robin Williams'):
        return LLMContextFrame(LLMContext([{'role':'user','content':text}]))

    async def test_router_mute_scene_duplicates_and_missing_media(self):
        clock=[0.0]
        router=RobinSkitRequest(self.skit,self.state,clock=lambda:clock[0])
        router.push_frame=AsyncMock()
        await router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
        self.assertIsInstance(router.push_frame.call_args.args[0],RobinSkitFrame)
        router.push_frame.reset_mock()
        await router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
        router.push_frame.assert_not_called()
        clock[0]=4
        self.state.scene.encounter.silenced=True
        await router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
        router.push_frame.assert_not_called()
        self.state.scene.encounter.silenced=False
        frame=self.context();frame.scene_event={'kind':'stable_visual_arrival'}
        await router.process_frame(frame,FrameDirection.DOWNSTREAM)
        self.assertIs(router.push_frame.call_args.args[0],frame)
        with tempfile.TemporaryDirectory() as directory:
            router=RobinSkitRequest(RobinSkit(directory),self.state)
            router.push_frame=AsyncMock()
            await router.process_frame(self.context(),FrameDirection.DOWNSTREAM)
            self.assertIsInstance(router.push_frame.call_args.args[0],TTSSpeakFrame)

    async def test_exact_audio_and_envelopes(self):
        player=RobinSkitPlayback(self.skit,self.state);player.push_frame=AsyncMock()
        await player.process_frame(RobinSkitFrame(),FrameDirection.DOWNSTREAM)
        frames=[c.args[0] for c in player.push_frame.call_args_list]
        self.assertEqual(frames[0].message,{'type':'visemes','cues':self.skit.cues, 'captions':self.skit.captions})
        self.assertGreater(len(self.skit.cues),10)
        self.assertLessEqual(len(self.skit.cues),1024)
        self.assertEqual(self.skit.cues[0][0],0)
        self.assertEqual(self.skit.cues[-1][1],len(self.skit.pcm)//2)
        self.assertEqual(self.skit.cues[-1][2],'rest')
        self.assertTrue(all(a[1]==b[0] for a,b in zip(self.skit.cues,self.skit.cues[1:])))
        self.assertIsInstance(frames[1],TTSStartedFrame)
        self.assertIsInstance(frames[-1],TTSStoppedFrame)
        audio=[f for f in frames if isinstance(f,TTSAudioRawFrame)]
        self.assertEqual(b''.join(f.audio for f in audio),self.skit.pcm)
        self.assertTrue(all(f.sound_effect and len(f.audio)<=960 for f in audio))
        player.push_frame.reset_mock();self.state.scene.encounter.silenced=True
        await player.process_frame(RobinSkitFrame(),FrameDirection.DOWNSTREAM)
        player.push_frame.assert_not_called()

    async def run_transport(self, interrupt=False):
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.task import PipelineTask, PipelineParams
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.transports.websocket.fastapi import FastAPIWebsocketOutputTransport, FastAPIWebsocketParams
        from pipecat.services.ollama.llm import OLLamaLLMService
        from server.tts import LocalTTS
        from server.guard import ReplyGuard
        from server.sound_effects import SoundBank, SoundEffectRequest, SoundEffectPlayback
        from server.sound_performance import SoundPerformance, AutomaticSoundDirector, load_performance
        packets=[];done=asyncio.Event();started=asyncio.Event();flushed=asyncio.Event()
        codec=FaceSerializer()
        class Engine:
            model_name='synthetic';voice='synthetic'
            async def stream(self,text):
                raise AssertionError('Skit invoked speech synthesis')
                yield
        class Client:
            is_closing=False
            is_connected=True
            async def setup(self,setup):pass
            async def disconnect(self):pass
            async def send(self,payload):
                if isinstance(payload,bytes):
                    packets.append(payload);started.set()
                elif json.loads(payload).get('type')=='interrupt':
                    flushed.set()
        transport=FastAPIWebsocketOutputTransport(AsyncMock(),Client(),
            FastAPIWebsocketParams(audio_out_enabled=True,audio_out_sample_rate=24000,serializer=codec))
        class Sink(FrameProcessor):
            async def process_frame(self,frame,direction):
                await super().process_frame(frame,direction)
                if isinstance(frame,BotStoppedSpeakingFrame):done.set()
                await self.push_frame(frame,direction)
        llm=OLLamaLLMService(base_url='http://127.0.0.1:1/v1')
        llm._stream_chat_completions=AsyncMock(side_effect=AssertionError('Skit invoked LLM'))
        bank=SoundBank();performance=SoundPerformance(bank,self.state,load_performance('halloween',bank))
        self.state.response_pending=True
        task=PipelineTask(Pipeline([VisitorControl(self.state),
            RobinSkitRequest(self.skit,self.state,performance=performance),
            SoundEffectRequest(bank,self.state,performance=performance),llm,ReplyGuard(),
            AutomaticSoundDirector(performance),LocalTTS(Engine()),
            RobinSkitPlayback(self.skit,self.state),SoundEffectPlayback(bank,self.state,performance=performance),
            transport,Sink()]),
            params=PipelineParams(),enable_rtvi=False)
        run=asyncio.create_task(PipelineRunner(handle_sigint=False).run(task))
        try:
            await task.queue_frame(self.context())
            if interrupt:
                await asyncio.wait_for(started.wait(),5)
                await task.queue_frame(InterruptionFrame())
                await asyncio.wait_for(flushed.wait(),5)
                count=len(packets);await asyncio.sleep(.2)
                self.assertEqual(len(packets),count)
                self.assertEqual(codec.epoch,1)
                self.assertLess(sum(len(p)-8 for p in packets),len(self.skit.pcm))
            else:
                await asyncio.wait_for(done.wait(),len(self.skit.pcm)/48000+6)
                await asyncio.sleep(.05)  # allow the upstream stop notification to reach VisitorControl
                pcm=b''.join(p[8:] for p in packets)
                self.assertEqual(pcm[:len(self.skit.pcm)],self.skit.pcm)
                self.assertFalse(any(pcm[len(self.skit.pcm):]))  # transport tail padding only
                self.assertFalse(self.state.bot_speaking)
                self.assertFalse(self.state.response_pending)
                self.assertEqual(performance.scheduled,0)
            llm._stream_chat_completions.assert_not_called()
            await task.cancel();await asyncio.wait_for(run,5)
        finally:
            if not run.done():await task.cancel();await run

    async def test_production_pipeline_full_recording_no_inference(self):
        await self.run_transport()

    async def test_production_transport_flush_on_interruption(self):
        await self.run_transport(interrupt=True)
