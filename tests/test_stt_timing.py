"""Content-free timing diagnostics with real threads and mocked native inference."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import threading
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pipecat.frames.frames import ErrorFrame
from server.transcription import LocalSTT


class STTTimingTests(unittest.IsolatedAsyncioTestCase):
    def service(self):
        service = LocalSTT(recorder=Mock())
        service.start_processing_metrics = AsyncMock()
        service.stop_processing_metrics = AsyncMock()
        service._handle_transcription = AsyncMock()
        return service

    async def consume(self, service):
        return [frame async for frame in service.run_stt(bytes(640))]

    async def wait_for(self, predicate):
        async with asyncio.timeout(2):
            while not predicate():
                await asyncio.sleep(.001)

    async def test_executor_queue_and_native_call_are_measured_separately(self):
        service = self.service()
        loop = asyncio.get_running_loop()
        executor = ThreadPoolExecutor(max_workers=1)
        loop.set_default_executor(executor)
        occupied, release_queue, entered, release_native = [threading.Event() for _ in range(4)]
        def occupy():
            occupied.set()
            release_queue.wait(2)
        blocker = executor.submit(occupy)
        await self.wait_for(occupied.is_set)
        def native(*args, **kwargs):
            entered.set()
            release_native.wait(2)
            return {'segments': []}
        try:
            with patch('server.transcription.transcribe', side_effect=native):
                turn = asyncio.create_task(self.consume(service))
                await self.wait_for(lambda: service.inference_active)
                await asyncio.sleep(.035)
                release_queue.set()
                await self.wait_for(entered.is_set)
                await asyncio.sleep(.035)
                release_native.set()
                await turn
            receipt = service.report()['timing']['samples'][-1]
            self.assertGreaterEqual(receipt['queue_ms'], 25)
            self.assertGreaterEqual(receipt['transcribe_ms'], 25)
            self.assertAlmostEqual(receipt['total_ms'],sum(receipt[k] for k in ('prepare_ms','queue_ms','transcribe_ms','result_ms')),delta=.02)
            self.assertEqual(receipt['outcome'], 'rejected')
            self.assertIsNone(receipt['cancelled_after_ms'])
            self.assertFalse(service.inference_active)
        finally:
            release_queue.set(); release_native.set()
            blocker.result(timeout=2)
            executor.shutdown(wait=True)

    async def test_cancelled_turn_retains_busy_and_receipt_until_native_finishes(self):
        service = self.service()
        entered, release = threading.Event(), threading.Event()
        def native(*args, **kwargs):
            entered.set(); release.wait(2)
            raise RuntimeError('private native text')
        try:
            with patch('server.transcription.transcribe', side_effect=native):
                turn = asyncio.create_task(self.consume(service))
                await self.wait_for(entered.is_set)
                turn.cancel()
                with self.assertRaises(asyncio.CancelledError):await turn
                self.assertTrue(service.inference_active)
                self.assertEqual(service.report()['timing']['samples'], [])
                await asyncio.sleep(.025)
                release.set()
                await self.wait_for(lambda: not service.inference_active)
            receipt = service.report()['timing']['samples'][-1]
            self.assertEqual(receipt['outcome'], 'cancelled')
            self.assertIsNone(receipt['total_ms'])
            self.assertIsNone(receipt['result_ms'])
            self.assertGreater(receipt['worker_completion_ms'], receipt['cancelled_after_ms'])
            self.assertNotIn('private native text', json.dumps(service.report()))
            service.stop_processing_metrics.assert_awaited_once()
        finally:release.set()

    async def test_cancellation_while_queued_does_not_cancel_the_native_task(self):
        service = self.service()
        executor = ThreadPoolExecutor(max_workers=1)
        asyncio.get_running_loop().set_default_executor(executor)
        occupied, release = threading.Event(), threading.Event()
        def block():
            occupied.set(); release.wait(2)
        blocker = executor.submit(block)
        try:
            await self.wait_for(occupied.is_set)
            with patch('server.transcription.transcribe', return_value={'segments': []}) as native:
                turn = asyncio.create_task(self.consume(service))
                await self.wait_for(lambda: service.inference_active)
                turn.cancel()
                with self.assertRaises(asyncio.CancelledError):await turn
                self.assertTrue(service.inference_active)
                self.assertEqual(service.report()['timing']['samples'], [])
                native.assert_not_called()
                release.set()
                await self.wait_for(lambda: not service.inference_active)
                native.assert_called_once()
            receipt = service.report()['timing']['samples'][-1]
            self.assertEqual(receipt['outcome'],'cancelled')
            self.assertIsNotNone(receipt['queue_ms'])
            self.assertIsNotNone(receipt['transcribe_ms'])
            self.assertIsNone(receipt['total_ms'])
        finally:
            release.set(); blocker.result(timeout=2); executor.shutdown(wait=True)

    async def test_preparation_and_selection_count_in_total_and_samples_are_bounded(self):
        service = self.service()
        async def prepare():await asyncio.sleep(.025)
        service.start_processing_metrics.side_effect = prepare
        def select(result):
            time.sleep(.025)
            return 'PRIVATE TRANSCRIPT', []
        with patch('server.transcription.transcribe', return_value={'segments': []}), \
             patch('server.transcription.select_transcript', side_effect=select):
            await self.consume(service)
        receipt = service.report()['timing']['samples'][-1]
        self.assertGreaterEqual(receipt['prepare_ms'],20)
        self.assertGreaterEqual(receipt['result_ms'],20)
        self.assertEqual(receipt['outcome'],'accepted')
        service.start_processing_metrics.side_effect = None
        with patch('server.transcription.transcribe', return_value={'segments': []}):
            for _ in range(20):await self.consume(service)
        report = service.report()
        self.assertEqual(len(report['timing']['samples']),16)
        self.assertNotIn('PRIVATE TRANSCRIPT',json.dumps(report))
        self.assertNotIn('PRIVATE TRANSCRIPT',str(service.recorder.event.call_args_list))
        report['timing']['samples'][0]['total_ms'] = -1
        self.assertGreaterEqual(service.report()['timing']['samples'][0]['total_ms'],0)
        self.assertEqual(service.report()['counts']['utterances'],21)

    async def test_worker_failure_and_pre_dispatch_failure_keep_unknown_fields_null(self):
        service = self.service()
        with patch('server.transcription.transcribe', side_effect=RuntimeError('private')):
            frames=await self.consume(service)
        self.assertIsInstance(frames[0],ErrorFrame)
        sample=service.report()['timing']['samples'][-1]
        self.assertEqual(sample['outcome'],'error')
        self.assertIsNotNone(sample['transcribe_ms'])
        self.assertIsNotNone(sample['total_ms'])
        # A malformed PCM buffer fails before native dispatch.
        frames=[frame async for frame in service.run_stt(b'\x00')]
        self.assertIsInstance(frames[0],ErrorFrame)
        sample=service.report()['timing']['samples'][-1]
        self.assertIsNone(sample['queue_ms'])
        self.assertIsNone(sample['transcribe_ms'])
        self.assertEqual(sample['outcome'],'error')
        self.assertFalse(service.inference_active)

    async def test_optional_timing_recorder_failure_does_not_drop_transcription(self):
        service = self.service()
        def record(kind, **fields):
            if kind == 'transcription_timing':raise OSError('private path')
        service.recorder.event.side_effect = record
        with patch('server.transcription.transcribe', return_value={'segments': []}):
            self.assertEqual(await self.consume(service), [])
        self.assertEqual(service.report()['counts']['rejected'],1)
        self.assertEqual(service.report()['counts']['timing_record_errors'],1)
        self.assertNotIn('private path',json.dumps(service.report()))


if __name__ == '__main__':unittest.main()
