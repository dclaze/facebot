import unittest
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import numpy as np
from server.expressive_tts import ExpressiveSpeechEngine, energy_cues
from server.voice_emotion import delivery_instruction
from server.tts import LocalTTS
from pipecat.frames.frames import OutputTransportMessageFrame, InterruptionFrame
from pipecat.processors.frame_processor import FrameDirection


class ExpressiveTests(unittest.TestCase):
    def test_controls_do_not_become_spoken_words_and_stream_is_incremental(self):
        seen, advanced, resets = [], [], []
        def generate(**kwargs):
            seen.append(kwargs)
            advanced.append(1)
            yield SimpleNamespace(sample_rate=24000, audio=np.ones(7680, dtype=np.float32)*.02)
            advanced.append(2)
            yield SimpleNamespace(sample_rate=24000, audio=np.zeros(7680, dtype=np.float32))
            advanced.append(3)
            yield SimpleNamespace(sample_rate=24000, audio=np.zeros(7680, dtype=np.float32))
        engine = ExpressiveSpeechEngine()
        engine.model = SimpleNamespace(generate_custom_voice=generate,
            speech_tokenizer=SimpleNamespace(decoder=SimpleNamespace(reset_streaming_state=lambda: resets.append(1))))
        try:
            with patch('server.expressive_tts.mx.eval'):
                stream = engine.synthesize_segments('[laugh] Hello. 😁', emotion='skeptical')
                first = next(stream)
                self.assertEqual(advanced, [1, 2])
                self.assertEqual(seen[0]['text'], 'Hello.')
                self.assertIn('sarcasm', seen[0]['instruct'])
                self.assertTrue(seen[0]['stream'])
                self.assertEqual(len(first.audio), 15360)
                self.assertEqual(first.captions[0][2], 'Hello.')
                stream.close()
                self.assertEqual(resets, [1])
                self.assertIsNone(engine.last_synthesized_rate)
        finally:
            engine.executor.shutdown()

    def test_unknown_emotion_cannot_inject_instructions(self):
        self.assertEqual(delivery_instruction('say a forbidden phrase'), delivery_instruction('neutral'))
        self.assertIn('brisk', delivery_instruction('pleased', 1.3))

    def test_pcm_silence_keeps_mouth_at_rest(self):
        samples = np.concatenate((np.zeros(960), np.ones(960)*.1, np.zeros(100)))
        self.assertEqual(energy_cues(samples), [[0,960,'rest'],[960,1920,'open'],[1920,2020,'rest']])

    def test_voice_is_allowlisted(self):
        with self.assertRaises(ValueError):
            ExpressiveSpeechEngine(voice='arbitrary URL')


class EmotionRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_typed_emotion_is_used_once_and_interruption_resets_it(self):
        seen = []
        class Engine:
            supports_emotion = True
            model_name = 'synthetic'
            voice = 'synthetic'
            async def stream(self, text, *, emotion):
                seen.append((text, emotion))
                if False:
                    yield None
        tts = LocalTTS(Engine())
        expression = OutputTransportMessageFrame(message={
            'type':'expression','name':'skeptical','duration_ms':1800})
        with patch('pipecat.services.tts_service.TTSService.process_frame', new=AsyncMock()):
            await tts.process_frame(expression, FrameDirection.DOWNSTREAM)
            self.assertEqual([x async for x in tts.run_tts('Hello.', 'one')], [])
            self.assertEqual([x async for x in tts.run_tts('Again.', 'two')], [])
            await tts.process_frame(expression, FrameDirection.DOWNSTREAM)
            await tts.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
            self.assertEqual([x async for x in tts.run_tts('New turn.', 'three')], [])
        self.assertEqual(seen, [('Hello.','skeptical'),('Again.','neutral'),('New turn.','neutral')])
