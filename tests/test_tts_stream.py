import unittest
from concurrent.futures import ThreadPoolExecutor
from server.tts import SpeechEngine, LocalTTS
from pipecat.frames.frames import TTSAudioRawFrame, OutputTransportMessageFrame


class SegmentStreamTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_segment_is_available_before_second_is_synthesized(self):
        engine = SpeechEngine.__new__(SpeechEngine)
        engine.executor = ThreadPoolExecutor(max_workers=1)
        visited = []
        def segments(text):
            try:
                visited.append('first')
                yield b'\0'*960, [[0,480,'open']]
                visited.append('second')
                yield b'\0'*480, [[0,240,'closed']]
            finally:
                visited.append('closed')
        engine.synthesize_segments = segments
        stream = engine.stream('Synthetic example')
        try:
            audio, cue = await anext(stream)
            self.assertEqual(len(audio), 960)
            self.assertEqual(visited, ['first'])
            await stream.aclose()
        finally:
            engine.executor.shutdown(wait=True)
        self.assertEqual(visited, ['first','closed'])

    async def test_transport_emits_cues_then_pcm_for_each_segment(self):
        class Engine:
            model_name='synthetic'
            voice='synthetic'
            async def stream(self, text):
                yield b'\0'*1440, [[0,720,'open']]
                yield b'\0'*480, [[0,240,'closed']]
        tts = LocalTTS(Engine())
        frames = [f async for f in tts.run_tts('Synthetic example', 'test')]
        self.assertEqual([type(f) for f in frames], [OutputTransportMessageFrame,
            TTSAudioRawFrame, TTSAudioRawFrame, OutputTransportMessageFrame, TTSAudioRawFrame])
        self.assertEqual([len(f.audio) for f in frames if isinstance(f, TTSAudioRawFrame)], [960,480,480])
        self.assertEqual(frames[3].message['cues'][0][0], 0)  # serializer adds playback offset

    async def test_cancel_during_worker_inference_closes_on_same_worker(self):
        import asyncio
        import threading
        engine = SpeechEngine.__new__(SpeechEngine)
        engine.executor = ThreadPoolExecutor(max_workers=1)
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()
        thread_ids = []
        def segments(text):
            try:
                thread_ids.append(threading.get_ident())
                loop.call_soon_threadsafe(entered.set)
                release.wait(timeout=2)
                yield b'\0'*960, []
                self.fail('Cancelled stream requested another inference')
            finally:
                thread_ids.append(threading.get_ident())
        engine.synthesize_segments = segments
        stream = engine.stream('Synthetic cancellation')
        task = asyncio.create_task(anext(stream))
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            task.cancel()
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
        finally:
            release.set()
            engine.executor.shutdown(wait=True)
        self.assertEqual(len(thread_ids), 2)
        self.assertEqual(thread_ids[0], thread_ids[1])
