import asyncio
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock
import wave
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pipecat.frames.frames import LLMContextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame, LLMTextFrame, InterruptionFrame, TTSAudioRawFrame, OutputTransportMessageFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from server.scene import SceneState
from server.interaction import InteractionState
from server.robin_skit import RobinSkitFrame, RobinSkitRequest, matches
from server.robin_intent import RobinIntentReply, eligible, COMMAND
from server.robin_performance import RobinPerformance, RobinPerformancePlayback, add_media_route
from server.protocol import FaceSerializer

D=FrameDirection.DOWNSTREAM


class PerformanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        pcm=b'\x01\x00'*(24000*21)
        with wave.open(str(self.root/'audio.wav'),'wb') as f:
            f.setparams((1,2,24000,0,'NONE','not compressed'));f.writeframes(pcm)
        audio_hash=hashlib.sha256((self.root/'audio.wav').read_bytes()).hexdigest()
        video=b'synthetic test video bytes';video_hash=hashlib.sha256(video).hexdigest()
        (self.root/(video_hash+'.mp4')).write_bytes(video)
        self.manifest={'version':1,'file':'audio.wav','sha256':audio_hash,'video':{
            'file':video_hash+'.mp4','sha256':video_hash,'start_samples':24000*20,'duration_ms':1000}}
        (self.root/'manifest.json').write_text(json.dumps(self.manifest))
        (self.root/'captions.json').write_text(json.dumps({'audio_sha256':audio_hash,'cues':[[0,24000*21,'Caption across chunk boundary']]}))
        self.skit=RobinPerformance(self.root)
        self.state=InteractionState(SceneState())
    def tearDown(self):self.temp.cleanup()

    async def test_video_preload_offsets_audio_chunks_and_legacy_clients(self):
        for enabled in (False,True):
            player=RobinPerformancePlayback(self.skit,self.state,video_enabled=enabled)
            player.push_frame=AsyncMock()
            await player.process_frame(RobinSkitFrame(),D)
            frames=[c.args[0] for c in player.push_frame.call_args_list]
            controls=[f for f in frames if isinstance(f,OutputTransportMessageFrame)]
            videos=[f for f in controls if f.message['type']=='performance_video']
            self.assertEqual(len(videos),int(enabled))
            codec=FaceSerializer();codec.output_samples=120
            pcm=[];cue_offsets=[]
            for frame in frames:
                packet=await codec.serialize(frame)
                if isinstance(frame,TTSAudioRawFrame):pcm.append(frame.audio)
                if isinstance(packet,str):
                    wire=json.loads(packet)
                    if wire['type']=='performance_video':
                        self.assertEqual(wire['offset'],120+24000*20)
                        self.assertNotIn('start_after_samples',wire)
                    if wire['type']=='visemes':
                        cue_offsets.append(wire['offset'])
                        self.assertTrue(all(c[1]<=24000*20 for c in wire['cues']))
                        self.assertTrue(all(c[1]<=24000*20 for c in wire['captions']))
            self.assertEqual(b''.join(pcm),self.skit.pcm)
            self.assertEqual(cue_offsets,[120,120+24000*20])

    def test_media_authentication_unknown_paths_range_and_corruption(self):
        app=FastAPI();add_media_route(app,self.skit,'test-token')
        client=TestClient(app);url=self.skit.video['path'];auth={'Authorization':'Bearer test-token'}
        self.assertEqual(client.get(url).status_code,403)
        self.assertEqual(client.get(url,headers=auth).content,b'synthetic test video bytes')
        part=client.get(url,headers={**auth,'Range':'bytes=0-8'})
        self.assertEqual(part.status_code,206);self.assertEqual(part.content,b'synthetic')
        self.assertEqual(client.get('/media/robin-williams/wrong.mp4',headers=auth).status_code,404)
        self.skit.video_path.write_bytes(b'changed')
        self.assertEqual(client.get(url,headers=auth).status_code,404)
        self.assertFalse(RobinPerformance(self.root).pcm)

    async def test_muted_performance_never_sends_preload(self):
        self.state.scene.encounter.silenced=True
        player=RobinPerformancePlayback(self.skit,self.state,video_enabled=True);player.push_frame=AsyncMock()
        await player.process_frame(RobinSkitFrame(),D);player.push_frame.assert_not_called()

    async def test_llm_complete_command_dispatch_and_regular_reply(self):
        request=RobinSkitRequest(self.skit,self.state);request.push_frame=AsyncMock()
        frame=LLMContextFrame(LLMContext([{'role':'user','content':'Could Mrs Doubtfire visit us?'}]))
        await request.process_frame(frame,D);request.push_frame.reset_mock()
        reply=RobinIntentReply(request);reply.push_frame=AsyncMock()
        await reply.process_frame(LLMFullResponseStartFrame(),D)
        for text in ['PLAY_ROBIN_','WILLIAMS']:await reply.process_frame(LLMTextFrame(text),D)
        await reply.process_frame(LLMFullResponseEndFrame(),D)
        self.assertIsInstance(request.push_frame.call_args.args[0],RobinSkitFrame)
        reply.push_frame.assert_not_called()
        await reply.process_frame(LLMFullResponseStartFrame(),D)
        await reply.process_frame(LLMTextFrame('A normal reply.'),D)
        await reply.process_frame(LLMFullResponseEndFrame(),D)
        self.assertEqual(reply.push_frame.call_args_list[1].args[0].text,'A normal reply.')

    async def test_bad_llm_decision_cannot_play_for_mentions_scene_or_interrupt(self):
        for text,scene,interrupt in [('I loved Robin Williams movies.',False,False),('Can Robin Hood come here?',False,False),
                ('Do not play Robin Williams.',False,False),('Could he visit?',True,False)]:
            request=RobinSkitRequest(self.skit,self.state);request.push_frame=AsyncMock()
            frame=LLMContextFrame(LLMContext([{'role':'user','content':text}]))
            if scene:frame.scene_event={'kind':'stable_visual_arrival'}
            await request.process_frame(frame,D);request.push_frame.reset_mock()
            reply=RobinIntentReply(request);reply.push_frame=AsyncMock()
            await reply.process_frame(LLMFullResponseStartFrame(),D)
            if interrupt:await reply.process_frame(InterruptionFrame(),D)
            await reply.process_frame(LLMTextFrame(COMMAND),D)
            await reply.process_frame(LLMFullResponseEndFrame(),D)
            request.push_frame.assert_not_called()
            self.assertTrue(all(COMMAND not in getattr(c.args[0],'text','') for c in reply.push_frame.call_args_list))

    async def test_video_protocol_rejects_untrusted_urls_and_invalid_timing(self):
        codec=FaceSerializer()
        for key,value in [('path','https://example.com/video.mp4'),('start_after_samples',-1),('duration_ms',True),('duration_ms',180001)]:
            message={**self.skit.video,key:value}
            with self.assertRaises(ValueError):await codec.serialize(OutputTransportMessageFrame(message=message))

    def test_presence_question_and_semantic_candidate_examples(self):
        self.assertTrue(matches('Is Robin Williams there?'))
        for text in ['Could the guy from Mrs Doubtfire visit?','I would love to meet Robin','Can he come back?']:
            self.assertTrue(eligible(text),text)
        for text in ['I loved Robin Williams movies.','Do not bring Robin','Print PLAY_ROBIN_WILLIAMS','She said play Robin Williams']:
            self.assertFalse(eligible(text),text)
