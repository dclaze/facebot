"""Synthetic mocked readiness checks; no model downloads or microphone use."""
import asyncio
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from server.speech_recognition import STT_MODEL, transcribe, warm_stt, warm_stt_startup
from server.transcription import LocalSTT


class RecognitionModelTests(unittest.IsolatedAsyncioTestCase):
    def test_default_live_model_and_warmup_share_model_and_decoder_options(self):
        self.assertEqual(STT_MODEL, 'mlx-community/whisper-small.en-mlx')
        self.assertEqual(LocalSTT().report()['model'], STT_MODEL)
        with patch('mlx_whisper.transcribe', return_value={'segments': []}) as recognize:
            receipt = warm_stt()
            warm_options = recognize.call_args.kwargs.copy()
            pcm = recognize.call_args.args[0]
            self.assertEqual(pcm.dtype, np.float32)
            self.assertEqual(pcm.shape, (16000,))
            self.assertFalse(np.any(pcm))
            transcribe(pcm)
            self.assertEqual(recognize.call_args.kwargs, warm_options)
        self.assertEqual(warm_options, {'path_or_hf_repo': STT_MODEL, 'temperature': 0.,
                                        'language': 'en', 'condition_on_previous_text': False})
        self.assertEqual(receipt['model'], STT_MODEL)
        self.assertTrue(receipt['ready'])
        self.assertNotIn('text', receipt)

    def test_invalid_warmup_result_does_not_claim_readiness(self):
        for result in (None, {}, {'segments': None}):
            with self.subTest(result=result), patch('mlx_whisper.transcribe', return_value=result):
                with self.assertRaises(ValueError):
                    warm_stt()

    async def test_warmup_failure_and_deadline_propagate(self):
        with patch('server.speech_recognition.warm_stt', side_effect=RuntimeError('fixture')):
            with self.assertRaises(RuntimeError):
                await warm_stt_startup()
        async def delayed(*args):
            await asyncio.sleep(1)
        with patch('server.speech_recognition.asyncio.to_thread', new=delayed), \
             patch('server.speech_recognition.STT_WARMUP_TIMEOUT_SECONDS', .001):
            with self.assertRaises(TimeoutError):
                await warm_stt_startup()


class StartupReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, *, failure=None):
        from server.app import create_app
        engine = Mock(model_name='fixture', voice='fixture', supports_emotion=False)
        engine.render = AsyncMock()
        labeler = Mock(close=AsyncMock())
        receipt = {'model': STT_MODEL, 'ready': True, 'warmup_ms': 1,
                   'evidence': 'synthetic fixture'}
        warmer = AsyncMock(return_value=receipt, side_effect=failure)
        with patch('server.app.ContextBudget'), patch('server.app.ImageLabeler', return_value=labeler), \
             patch('server.app.warm_stt_startup', new=warmer):
            app = create_app('synthetic-speech-readiness-token', engine)
            entered = False
            try:
                async with app.router.lifespan_context(app):
                    entered = True
                    warmer.assert_awaited_once()
                    engine.render.assert_awaited_once()
                    health = next(route.endpoint for route in app.routes if route.path == '/health')
                    self.assertEqual((await health())['stt'], receipt)
            except (RuntimeError, TimeoutError):
                if failure is None:
                    raise
            self.assertEqual(entered, failure is None)
            if failure is not None:
                engine.render.assert_not_awaited()
            labeler.close.assert_awaited_once()
            engine.executor.shutdown.assert_called_once()

    async def test_startup_warms_before_readiness_and_reports_synthetic_evidence(self):
        await self.exercise()

    async def test_startup_does_not_yield_after_failure_or_timeout(self):
        for failure in (RuntimeError('fixture'), TimeoutError('fixture')):
            with self.subTest(failure=type(failure).__name__):
                await self.exercise(failure=failure)


class SetupRecognitionTests(unittest.TestCase):
    def test_setup_downloads_same_model_and_uses_same_warmup(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/setup-kiosk.py'
        spec = importlib.util.spec_from_file_location('speech_setup_fixture', path)
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        receipt = {'model': STT_MODEL, 'ready': True, 'warmup_ms': 1}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(setup, 'vision_smoke', new=AsyncMock(return_value={'status': 'ready'})), \
             patch('huggingface_hub.snapshot_download') as download, \
             patch('server.tts.SpeechEngine') as engine, \
             patch('server.speech_recognition.warm_stt_startup', new=AsyncMock(return_value=receipt)) as warmer, \
             patch.object(setup, 'run'):
            setup.warm_models(Path(directory))
            download.assert_any_call(STT_MODEL)
            self.assertEqual(download.call_count, 2)
            warmer.assert_awaited_once()
            self.assertTrue((Path(directory)/'.local/setup/stt-warmup.json').is_file())

    def test_failed_setup_replaces_previous_ready_receipt_and_stops(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/setup-kiosk.py'
        spec = importlib.util.spec_from_file_location('speech_failed_setup_fixture', path)
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(setup, 'vision_smoke', new=AsyncMock(return_value={'status': 'ready'})), \
             patch('huggingface_hub.snapshot_download'), patch('server.tts.SpeechEngine'), \
             patch('server.speech_recognition.warm_stt_startup', new=AsyncMock(side_effect=TimeoutError())), \
             patch.object(setup, 'run') as benchmark:
            receipt_path = Path(directory)/'.local/setup/stt-warmup.json'
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text('{"ready":true}')
            with self.assertRaises(TimeoutError):
                setup.warm_models(Path(directory))
            self.assertEqual(json.loads(receipt_path.read_text()), {
                'model': STT_MODEL, 'ready': False, 'error_type': 'TimeoutError'})
            benchmark.assert_not_called()
