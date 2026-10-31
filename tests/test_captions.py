import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from server.captions import caption_cues, validate_captions
from server.protocol import FaceSerializer
from server.tts import LocalTTS, SpeechSegment
from pipecat.frames.frames import OutputAudioRawFrame, OutputTransportMessageFrame, InterruptionFrame, TTSAudioRawFrame


class CaptionTests(unittest.TestCase):
    def test_engine_uses_exact_synthesized_segment_text(self):
        import mlx.core as mx
        from server.tts import SpeechEngine
        result=SimpleNamespace(audio=mx.zeros((2400,)),pred_dur=None,
                               graphemes='Actual spoken segment.',tokens=[])
        engine=SpeechEngine()
        engine.model=SimpleNamespace(config=SimpleNamespace(sample_rate=24000),
            _get_pipeline=lambda _: lambda text, **kwargs: iter([result]))
        try:
            segment=next(engine.synthesize_segments('Original upstream prompt.'))
            self.assertEqual(segment.captions,[[0,2400,'Actual spoken segment.']])
            audio,mouths=segment
            self.assertEqual((len(audio),mouths),(4800,[]))
        finally:
            engine.executor.shutdown()

    def test_short_pages_preserve_all_words_and_punctuation(self):
        text = "Sycamore Park! Nothing’s changed—except the PRICES! Can’t even possess a house for free!"
        cues = caption_cues(text, 240000)
        self.assertEqual(' '.join(c[2] for c in cues), text)
        self.assertEqual((cues[0][0], cues[-1][1]), (0, 240000))
        self.assertTrue(all(len(c[2]) <= 30 and len(c[2].split()) <= 5 for c in cues))
        self.assertTrue(all(a[1] == b[0] for a, b in zip(cues, cues[1:])))
        validate_captions(cues)

    def test_joke_sentence_boundary_moves_orphan_with_its_timestamp(self):
        text = 'Ghosts love elevators. They lift our spirits.'
        tokens = [SimpleNamespace(text='They', start_ts=1.25),
                  SimpleNamespace(text='lift', start_ts=1.6)]
        cues = caption_cues(text, 96000, tokens)
        self.assertEqual(cues, [[0, 30000, 'Ghosts love elevators.'],
                                [30000, 96000, 'They lift our spirits.']])
        fallback = caption_cues(text, 96000)
        self.assertEqual(fallback[1][0], round(96000 * text.index('They') / len(text)))
        self.assertEqual(' '.join(c[2] for c in fallback), text)

    def test_two_stranded_words_and_quoted_sentence_move_together(self):
        text = 'A ghost waved. They both vanished into thin air.'
        cues = caption_cues(text, 96000)
        self.assertEqual(cues[0][2], 'A ghost waved.')
        self.assertTrue(cues[1][2].startswith('They both vanished'))
        quoted = caption_cues('She said “Boo!” They left in a hurry.', 96000)
        self.assertEqual(quoted[0][2], 'She said “Boo!”')
        for sentence, pages in ((text, cues), ('She said “Boo!” They left in a hurry.', quoted)):
            self.assertEqual(' '.join(c[2] for c in pages), sentence)
            self.assertTrue(all(len(c[2]) <= 30 and len(c[2].split()) <= 5 for c in pages))
            self.assertTrue(all(a[1] == b[0] for a,b in zip(pages,pages[1:])))
            validate_captions(pages)

    def test_short_greetings_abbreviations_and_unpunctuated_text_keep_greedy_fit(self):
        for text in ('Boo! Happy Halloween!', 'Hello! Welcome, little ghosts!'):
            self.assertEqual(caption_cues(text, 24000), [[0, 24000, text]])
        self.assertEqual(caption_cues('Ask Dr. Smith about the spooky elevator', 96000)[0][2],
                         'Ask Dr. Smith about the')
        plain = 'One two three four five six seven eight nine ten eleven twelve'
        cues = caption_cues(plain, 96000)
        self.assertEqual([c[2] for c in cues], ['One two three four five',
                                               'six seven eight nine ten', 'eleven twelve'])
        self.assertEqual(' '.join(c[2] for c in cues), plain)
        validate_captions(cues)

    def test_word_alignment_and_missing_timestamps(self):
        text = 'One two three four five six seven eight nine ten'
        tokens = [SimpleNamespace(text='six', start_ts=1.75)]
        cues = caption_cues(text, 96000, tokens)
        self.assertEqual(cues[1][0], 42000)
        self.assertEqual(cues[1][2], 'six seven eight nine ten')
        validate_captions(caption_cues(text, 96000, [SimpleNamespace(text='six', start_ts=float('nan'))]))

    def test_long_unbroken_word_empty_and_unicode(self):
        text = 'W' * 97
        cues = caption_cues(text, 48000)
        self.assertEqual(''.join(c[2] for c in cues), text)
        self.assertTrue(all(len(c[2]) <= 30 for c in cues))
        self.assertEqual(caption_cues(' \n\t', 48000), [])
        self.assertEqual(caption_cues('hello', 0), [])
        validate_captions(caption_cues('Spooky café — boo! 👻', 24000))

    def test_validation_rejects_unsafe_boundaries_atomically(self):
        for cues in ([[0,0,'hi']], [[-1,2,'hi']], [[0,2880001,'hi']], [[True,2,'hi']],
                     [[0,2,'']], [[0,2,'x'*161]], [[0,2,'a\nb']], [[0,2,'ok'],[1,3,'overlap']]):
            with self.assertRaises(ValueError): validate_captions(cues)
        validate_captions([[0,2880000,'🙂'*160]])

    def test_skit_sidecar_requires_matching_audio_and_bounded_cues(self):
        import hashlib
        import wave
        from server.robin_skit import RobinSkit
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            audio=root/'test.wav'
            with wave.open(str(audio),'wb') as stream:
                stream.setparams((1,2,24000,0,'NONE','not compressed'))
                stream.writeframes(bytes(48000))
            digest=hashlib.sha256(audio.read_bytes()).hexdigest()
            (root/'manifest.json').write_text(json.dumps({'version':1,'file':'test.wav','sha256':digest}))
            sidecar=root/'captions.json'
            sidecar.write_text(json.dumps({'audio_sha256':digest,'cues':[[0,24000,'Hello']]}))
            self.assertEqual(RobinSkit(root).captions,[[0,24000,'Hello']])
            for data in ({'audio_sha256':'stale','cues':[[0,24000,'Wrong']]},
                         {'audio_sha256':digest,'cues':[[0,24001,'Too long']]}):
                sidecar.write_text(json.dumps(data))
                skit=RobinSkit(root)
                self.assertTrue(skit.pcm)
                self.assertEqual(skit.captions,[])


class CaptionTransportTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_spoken_segments_survive_transport_offset_and_interrupt(self):
        class Engine:
            model_name='synthetic'
            voice='synthetic'
            async def stream(self, text):
                yield SpeechSegment(bytes(1440), [[0,720,'open']], [[0,720,'First sentence.']])
                yield SpeechSegment(bytes(480), [], [[0,240,'Next sentence.']])
        tts=LocalTTS(Engine())
        codec=FaceSerializer()
        controls=[]
        async for frame in tts.run_tts('Supplied to the engine', 'caption-test'):
            encoded=await codec.serialize(frame)
            if isinstance(encoded,str): controls.append(json.loads(encoded))
        self.assertEqual([(c['epoch'],c['offset'],c['captions'][0][2]) for c in controls],
                         [(0,0,'First sentence.'),(0,720,'Next sentence.')])
        await codec.serialize(InterruptionFrame())
        encoded=await codec.serialize(OutputTransportMessageFrame(message={
            'type':'visemes','cues':[],'captions':[[0,240,'Fresh']]}))
        self.assertEqual(json.loads(encoded)['offset'],0)
        self.assertEqual(json.loads(encoded)['epoch'],1)
        with self.assertRaises(ValueError):
            await codec.serialize(OutputTransportMessageFrame(message={
                'type':'visemes','cues':[],'captions':[[0,240,'x'*161]]}))
