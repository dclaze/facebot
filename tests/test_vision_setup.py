"""No daemon or model inference: exercise runtime HTTP schema and setup retries."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image
from server.vision import ImageLabeler, VisionState, MODEL, SCHEMA, OLLAMA_CHAT_URL

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup_kiosk_vision_test', ROOT/'scripts/setup-kiosk.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class VisionEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_runtime_uses_standard_local_ollama_and_validates_schema(self):
        seen = []
        def handle(request):
            seen.append(request)
            self.assertEqual(str(request.url), 'http://127.0.0.1:11434/api/chat')
            body = json.loads(request.content)
            self.assertEqual(body['model'], MODEL)
            self.assertEqual(body['format'], SCHEMA)
            self.assertFalse(body['stream'])
            return httpx.Response(200, json={'message': {'content': json.dumps({'labels': [], 'people': []})}})
        state = VisionState()
        labeler = ImageLabeler(state)
        await labeler.client.aclose()
        labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        try:
            self.assertTrue(await labeler.label(image.getvalue()))
            self.assertEqual(state.frames, 1)
            self.assertEqual(len(seen), 1)
        finally:
            await labeler.close()

    async def test_malformed_model_reply_is_not_runtime_success(self):
        labeler = ImageLabeler(VisionState())
        await labeler.client.aclose()
        labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={'message': {'content': '{"labels":["invented-command"],"people":[]}'}})))
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        try:
            with self.assertRaises(ValueError):
                await labeler.label(image.getvalue())
            self.assertEqual(labeler.state.frames, 0)
        finally:
            await labeler.close()


class VisionSetupTests(unittest.IsolatedAsyncioTestCase):
    async def smoke(self, results):
        labeler = AsyncMock()
        labeler.label.side_effect = results
        with patch('server.vision.ImageLabeler', return_value=labeler):
            receipt = await setup.vision_smoke()
        labeler.close.assert_awaited_once()
        # Setup uses an in-memory synthetic JPEG accepted by the runtime envelope.
        for call in labeler.label.call_args_list:
            with Image.open(io.BytesIO(call.args[0])) as image:
                self.assertEqual((image.format, image.size), ('JPEG', (64, 64)))
        return receipt, labeler.label.await_count

    async def test_cold_stale_then_timely_reply_retries_once(self):
        receipt, count = await self.smoke([False, True])
        self.assertEqual(count, 2)
        self.assertEqual(receipt['status'], 'ready')
        self.assertEqual([row['status'] for row in receipt['attempts']], ['stale', 'accepted'])
        self.assertEqual(receipt['endpoint'], OLLAMA_CHAT_URL)
        self.assertFalse(receipt['visual_recognition_quality_tested'])
        self.assertFalse(receipt['microphone_or_camera_used'])

    async def test_ready_first_attempt_does_not_repeat_inference(self):
        receipt, count = await self.smoke([True])
        self.assertEqual(count, 1)
        self.assertEqual(receipt['status'], 'ready')

    async def test_missing_endpoint_is_failed_not_offline_ready(self):
        receipt, count = await self.smoke([httpx.ConnectError('fixture'), httpx.ConnectError('fixture')])
        self.assertEqual(count, 2)
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(receipt['attempts'][0]['error_type'], 'ConnectError')

    async def test_two_stale_replies_do_not_bypass_live_frame_ttl(self):
        receipt, count = await self.smoke([False, False])
        self.assertEqual(count, 2)
        self.assertEqual(receipt['status'], 'failed')


class SetupGateTests(unittest.TestCase):
    def test_public_pull_and_runtime_model_match_verified_compatible_tag(self):
        self.assertEqual(MODEL, 'qwen3-vl:2b')
        self.assertIn(MODEL, setup.MODELS)

    def test_failed_vision_warmup_writes_receipt_and_stops_setup(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = {'status': 'failed', 'attempts': [{'status': 'error'}]}
            with patch.object(setup, 'vision_smoke', new=AsyncMock(return_value=receipt)):
                with self.assertRaisesRegex(RuntimeError, 'Vision setup failed'):
                    setup.warm_models(Path(root))
            saved = json.loads((Path(root)/'.local/setup/vision-smoke.json').read_text())
            self.assertEqual(saved, receipt)
