import unittest
from unittest.mock import AsyncMock, Mock, patch

from pipecat.frames.frames import ErrorFrame, TranscriptionFrame
from server.transcription import LocalSTT, select_transcript, repetition_loop


def result(text, **metrics):
    return {'segments': [{'text': text, 'avg_logprob': -.2,
                          'no_speech_prob': .02, 'compression_ratio': 1., **metrics}]}


class TranscriptTests(unittest.IsolatedAsyncioTestCase):
    def test_recorded_loop_rejected_but_normal_emphasis_and_commands_survive(self):
        self.assertTrue(repetition_loop("I'm gonna go back to the next one. " * 14))
        for text in ('Boo! Boo!', 'Hey YOU, one candy per person, please!',
                     'Please stop talking.', 'Can I have two pieces?', 'Play a drumroll.'):
            self.assertEqual(select_transcript(result(text)), (text, []))

    def test_uncertain_whole_utterance_not_stitched_into_new_meaning(self):
        for metric, value, reason in [('avg_logprob', -1.1, 'low_confidence'),
                                     ('no_speech_prob', .7, 'likely_silence'),
                                     ('compression_ratio', 2.5, 'high_repetition')]:
            bad = result('do not', **{metric: value})['segments'][0]
            mixed = {'segments': [bad, result('play that')['segments'][0]]}
            text, reasons = select_transcript(mixed)
            self.assertEqual(text, '')
            self.assertIn(reason, reasons)

    async def test_service_keeps_raw_pcm_contract_and_records_quality_without_text(self):
        recorder = Mock()
        service = LocalSTT(recorder=recorder)
        self.assertFalse(service.wants_wav_segments)
        service.start_processing_metrics = AsyncMock()
        service.stop_processing_metrics = AsyncMock()
        service._handle_transcription = AsyncMock()
        service._user_id = ''
        with patch('mlx_whisper.transcribe', return_value=result('Can I have one?')) as model:
            frames = [frame async for frame in service.run_stt(bytes(32000))]
        self.assertEqual(len(frames), 1)
        self.assertIsInstance(frames[0], TranscriptionFrame)
        self.assertFalse(model.call_args.kwargs['condition_on_previous_text'])
        self.assertNotIn('text', recorder.event.call_args.kwargs)
        self.assertTrue(recorder.event.call_args.kwargs['accepted'])
        service.stop_processing_metrics.assert_awaited_once()

    async def test_rejected_loop_never_becomes_a_user_turn(self):
        service = LocalSTT()
        service.start_processing_metrics = AsyncMock()
        service.stop_processing_metrics = AsyncMock()
        with patch('mlx_whisper.transcribe', return_value=result('Go back to the next one. ' * 14)):
            frames = [frame async for frame in service.run_stt(bytes(32000))]
        self.assertEqual(frames, [])
        self.assertEqual(service.report()['counts']['rejected'], 1)

    async def test_recognizer_error_closes_metrics_without_inventing_speech(self):
        service = LocalSTT()
        service.start_processing_metrics = AsyncMock()
        service.stop_processing_metrics = AsyncMock()
        with patch('mlx_whisper.transcribe', side_effect=RuntimeError('test')):
            frames = [frame async for frame in service.run_stt(bytes(32000))]
        self.assertEqual(len(frames), 1)
        self.assertIsInstance(frames[0], ErrorFrame)
        service.stop_processing_metrics.assert_awaited_once()
        self.assertEqual(service.report()['counts']['errors'], 1)


if __name__ == '__main__':
    unittest.main()
