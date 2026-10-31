"""No daemon or model inference: exercise runtime HTTP schema and setup retries."""
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
import tempfile
from unittest.mock import AsyncMock, patch

import httpx
from PIL import Image
from server.vision import ImageLabeler, VisionState, MODEL, SCHEMA, OLLAMA_CHAT_URL, vision_url

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

    async def test_override_is_used_by_runtime_request(self):
        endpoint = 'http://127.0.0.1:11435/api/chat'
        with patch.dict(os.environ, {'FACEBOT_VISION_URL': endpoint}):
            labeler = ImageLabeler(VisionState())
        await labeler.client.aclose()
        seen = []
        def handle(request):
            seen.append(str(request.url))
            return httpx.Response(200, json={'message': {'content': '{"labels":[],"people":[]}', 'thinking': ''}})
        labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        try:
            self.assertTrue(await labeler.label(image.getvalue()))
            self.assertEqual(seen, [endpoint])
        finally:
            await labeler.close()

    async def test_thinking_or_empty_or_truncated_replies_never_accept_frames(self):
        good = '{"labels":[],"people":[]}'
        fixtures = [
            {'message': {'content': good, 'thinking': 'reasoning despite think:false'}},
            {'message': {'content': good, 'thinking': None}},
            {'message': {'content': '', 'thinking': 'reasoning'}},
            {'message': {'content': '   '}},
            {'message': {'content': good}, 'done_reason': 'length'},
        ]
        image = io.BytesIO()
        Image.new('RGB', (64, 64)).save(image, format='JPEG')
        for reply in fixtures:
            with self.subTest(reply=reply):
                labeler = ImageLabeler(VisionState())
                await labeler.client.aclose()
                labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=reply)))
                try:
                    with self.assertRaises(ValueError):
                        await labeler.label(image.getvalue())
                    self.assertEqual(labeler.state.frames, 0)
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


class EndpointValidationTests(unittest.TestCase):
    def test_default_and_literal_loopback_only(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(vision_url(), OLLAMA_CHAT_URL)
        for endpoint in ('http://127.0.0.1:11435/api/chat', 'http://[::1]:11435/api/chat'):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {'FACEBOT_VISION_URL': endpoint}):
                self.assertEqual(vision_url(), endpoint)

    def test_rejects_network_targets_and_url_features(self):
        endpoints = [
            '', 'http://localhost:11434/api/chat', 'http://192.168.1.2:11434/api/chat',
            'http://0.0.0.0:11434/api/chat', 'http://127.0.0.1.evil:11434/api/chat',
            'http://user@127.0.0.1:11434/api/chat', 'https://127.0.0.1:11434/api/chat',
            'http://127.0.0.1/api/chat', 'http://127.0.0.1:0/api/chat',
            'http://127.0.0.1:65536/api/chat', 'http://127.0.0.1:11434/api/chat?x=1',
            'http://127.0.0.1:11434/api/chat#x', 'http://127.0.0.1:11434/api/generate',
            'http://127.0.0.1:11434/api/chat\n',
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {'FACEBOT_VISION_URL': endpoint}):
                with self.assertRaises(ValueError):
                    vision_url()


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

    async def test_setup_receipt_reports_selected_loopback_endpoint(self):
        endpoint = 'http://127.0.0.1:11435/api/chat'
        with patch.dict(os.environ, {'FACEBOT_VISION_URL': endpoint}):
            receipt, _ = await self.smoke([True])
        self.assertEqual(receipt['endpoint'], endpoint)
        self.assertTrue(receipt['requires_nonempty_content_without_thinking'])

    async def test_real_labeler_rejects_thinking_in_setup_smoke(self):
        labeler = ImageLabeler(VisionState())
        await labeler.client.aclose()
        labeler.client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request:
            httpx.Response(200, json={'message': {
                'content': '{"labels":[],"people":[]}', 'thinking': 'unexpected reasoning'}})))
        with patch('server.vision.ImageLabeler', return_value=labeler):
            receipt = await setup.vision_smoke()
        self.assertEqual(receipt['status'], 'failed')
        self.assertEqual(len(receipt['attempts']), 2)
        self.assertEqual(labeler.state.frames, 0)
        self.assertTrue(labeler.client.is_closed)

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
    def test_public_pull_and_runtime_require_instruction_tag(self):
        self.assertEqual(MODEL, 'qwen3-vl:2b-instruct')
        self.assertIn(MODEL, setup.MODELS)

    def test_failed_vision_warmup_writes_receipt_and_stops_setup(self):
        with tempfile.TemporaryDirectory() as root:
            receipt = {'status': 'failed', 'attempts': [{'status': 'error'}]}
            with patch.object(setup, 'vision_smoke', new=AsyncMock(return_value=receipt)):
                with self.assertRaisesRegex(RuntimeError, 'Vision setup failed'):
                    setup.warm_models(Path(root))
            saved = json.loads((Path(root)/'.local/setup/vision-smoke.json').read_text())
            self.assertEqual(saved, receipt)
