import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import AsyncMock
from pipecat.frames.frames import TranscriptionFrame, LLMTextFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection
from server.recording import InteractionRecorder, RecordingTap
from server.protocol import FaceSerializer

class RecordingTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_creates_no_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'private'
            recorder=InteractionRecorder(root)
            recorder.event('test', text='synthetic')
            recorder.mic_audio(bytes(640))
            recorder.close()
            self.assertFalse(root.exists())

    async def test_private_transcript_and_playback_evidence_are_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'private'
            recorder=InteractionRecorder(root, enabled=True)
            for stage,frame in [('input',TranscriptionFrame('Synthetic question?', '', '')),
                                ('reply',LLMTextFrame('Synthetic reply.')),
                                ('reply',TTSSpeakFrame('Prepared reply.'))]:
                tap=RecordingTap(recorder,stage)
                tap.push_frame=AsyncMock()
                await tap.process_frame(frame,FrameDirection.DOWNSTREAM)
                tap.push_frame.assert_awaited_once_with(frame,FrameDirection.DOWNSTREAM)
            recorder.output_audio(960)
            recorder.close()
            rows=[json.loads(line) for p in root.glob('*.jsonl') for line in p.read_text().splitlines()]
            self.assertEqual([r['text'] for r in rows if 'text' in r],['Synthetic question?','Synthetic reply.','Prepared reply.'])
            self.assertEqual(recorder.report()['transcript_events'],3)
            self.assertEqual(root.stat().st_mode & 0o777,0o700)
            self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in root.iterdir()))
            self.assertIn('not audible',next(r for r in rows if r['event']=='audio_sent')['evidence'])

    async def test_bounded_valid_wav_and_invalid_packets_are_not_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            recorder=InteractionRecorder(root,enabled=True,audio=True,chunk_seconds=.02,chunks=2)
            codec=FaceSerializer(recorder=recorder)
            with self.assertRaises(ValueError): await codec.deserialize(b'x')
            self.assertEqual(recorder.audio_bytes,0)
            for _ in range(4): await codec.deserialize(bytes(640))
            recorder.close()
            paths=list(root.glob('*.wav'))
            self.assertEqual(len(paths),2)
            for p in paths:
                with wave.open(str(p),'rb') as source:
                    self.assertEqual(source.getparams()[:3],(1,2,16000))
                    self.assertEqual(source.getnframes(),320)
            self.assertEqual(recorder.audio_bytes,2560)

    async def test_disk_error_does_not_break_frame_forwarding(self):
        with tempfile.TemporaryDirectory() as directory:
            recorder=InteractionRecorder(Path(directory),enabled=True)
            for p in Path(directory).iterdir(): p.unlink()
            Path(directory).rmdir()
            tap=RecordingTap(recorder,'input');tap.push_frame=AsyncMock()
            await tap.process_frame(TranscriptionFrame('Synthetic question','',''),FrameDirection.DOWNSTREAM)
            self.assertEqual(recorder.errors,1)
            tap.push_frame.assert_awaited_once()
