"""Isolated worker execution and recovery policy; no model or live service calls."""
import asyncio
import importlib.util
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from server.tts import SpeechEngine
from server.worker_progress import WorkerProgress, recovery_report
spec = importlib.util.spec_from_file_location('worker_kiosk', Path(__file__).resolve().parents[1] / 'scripts/kiosk-service.py')
kiosk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kiosk)


class WorkerExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_call_blocks_new_demand_while_http_remains_ready(self):
        from server.app import create_app
        engine = SpeechEngine()
        entered = asyncio.Event()
        release = threading.Event()
        loop = asyncio.get_running_loop()
        def segments(text):
            loop.call_soon_threadsafe(entered.set)
            release.wait(3)
            yield b'\0' * 960, []
        engine.synthesize_segments = segments
        first = engine.stream('synthetic first')
        task = asyncio.create_task(anext(first))
        second_task = None
        try:
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await asyncio.wait_for(task, .1)
            cancelled = engine.worker_progress.snapshot()
            self.assertEqual((cancelled['running_job'], cancelled['waiting']), (1, 0))
            second = engine.stream('synthetic second')
            second_task = asyncio.create_task(anext(second))
            await asyncio.sleep(.02)
            self.assertFalse(second_task.done())
            with patch('server.app.ContextBudget'), patch('server.app.ImageLabeler'), \
                 patch('server.app.MuteLatch', return_value=SimpleNamespace(value=False)):
                app = create_app('synthetic-worker-recovery-token', engine)
                health = next(r.endpoint for r in app.routes if r.path == '/health')
                self.assertEqual((await health())['status'], 'ready')
                recovery = next(r.endpoint for r in app.routes if r.path == '/recovery')
                from fastapi import HTTPException
                with self.assertRaises(HTTPException) as denied:
                    await recovery('Bearer wrong')
                self.assertEqual(denied.exception.status_code, 403)
                self.assertFalse((await recovery('Bearer synthetic-worker-recovery-token'))['eligible'])
                from starlette.websockets import WebSocketState
                cells = dict(zip(recovery.__code__.co_freevars, recovery.__closure__))
                state = SimpleNamespace(scene=SimpleNamespace(encounter=SimpleNamespace(silenced=False)))
                socket = SimpleNamespace(client_state=WebSocketState.CONNECTED,
                                         application_state=WebSocketState.CONNECTED)
                cells['current_interaction'].cell_contents = state
                cells['current_voice_socket'].cell_contents = socket
                self.assertTrue((await recovery('Bearer synthetic-worker-recovery-token'))['eligible'])
                socket.client_state = WebSocketState.DISCONNECTED
                self.assertFalse((await recovery('Bearer synthetic-worker-recovery-token'))['eligible'])
                socket.client_state = WebSocketState.CONNECTED
                socket.application_state = WebSocketState.DISCONNECTED
                self.assertFalse((await recovery('Bearer synthetic-worker-recovery-token'))['eligible'])
                socket.application_state = WebSocketState.CONNECTED
                cells['mute'].cell_contents.value = True
                self.assertFalse((await recovery('Bearer synthetic-worker-recovery-token'))['eligible'])
            # Old native execution remains visible after its awaiting task was
            # cancelled; a different waiter is now blocked behind it.
            report = engine.worker_progress.snapshot()
            self.assertEqual(report['running_job'], 1)
            self.assertEqual(report['waiting'], 1)
            self.assertGreater(report['progress_age_s'], 0)
        finally:
            if second_task:
                second_task.cancel()
                await asyncio.gather(second_task, return_exceptions=True)
            release.set()
            engine.executor.shutdown(wait=True)

    async def test_queued_work_without_tracked_execution_is_not_a_running_job(self):
        engine = SpeechEngine()
        release = threading.Event()
        entered = threading.Event()
        def unrelated_work():
            entered.set()
            release.wait(3)
        engine.executor.submit(unrelated_work)
        self.assertTrue(await asyncio.to_thread(entered.wait, 1))
        engine.synthesize_segments = lambda text: ((b'\0' * 960, []) for _ in range(1))
        stream = engine.stream('synthetic queued work')
        task = asyncio.create_task(anext(stream))
        try:
            await asyncio.sleep(.02)
            report = engine.worker_progress.snapshot()
            self.assertEqual(report['waiting'], 1)
            self.assertIsNone(report['running_job'])
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            release.set()
            engine.executor.shutdown(wait=True)

    async def test_cancelled_without_new_demand_and_backpressure_are_idle(self):
        engine = SpeechEngine()
        engine.synthesize_segments = lambda text: ((b'\0' * 960, []) for _ in range(2))
        stream = engine.stream('synthetic buffered output')
        try:
            await anext(stream)
            report = engine.worker_progress.snapshot()
            self.assertEqual(report['waiting'], 0)
            self.assertIsNone(report['running_job'])
        finally:
            await stream.aclose()
            engine.executor.shutdown(wait=True)


def evidence():
    return {'version': 1, 'eligible': True, 'tts_worker':
            dict(running_job=1, progress=0, progress_age_s=1000., waiting=1, demand=1)}


class RecoveryPolicyTests(unittest.TestCase):
    def test_same_execution_without_progress_and_continuous_demand_expires(self):
        watch, report = kiosk.StalledWorker(90), evidence()
        self.assertFalse(watch.observe(report, 0))
        self.assertFalse(watch.observe(report, 89.99))
        self.assertTrue(watch.observe(report, 90))
        # Reset even when a poll missed the idle gap before new demand.
        report['tts_worker']['demand'] += 1
        self.assertFalse(watch.observe(report, 91))
        self.assertFalse(watch.observe(report, 180))
        self.assertTrue(watch.observe(report, 181))

    def test_progressing_long_output_and_new_executions_reset_deadline(self):
        for field in ('progress', 'running_job'):
            with self.subTest(field=field):
                watch, report = kiosk.StalledWorker(90), evidence()
                for now in range(0, 600, 60):
                    report['tts_worker'][field] += 1
                    self.assertFalse(watch.observe(report, now))
                    self.assertFalse(watch.observe(report, now + 59))

    def test_idle_cancelled_queued_and_missing_evidence_never_expire(self):
        examples = [None, {}, {'version': 1, 'eligible': False, 'tts_worker': evidence()['tts_worker']}]
        for field, value in [('waiting', 0), ('running_job', None), ('progress_age_s', 0),
                             ('progress_age_s', float('nan')), ('progress_age_s', float('inf')),
                             ('running_job', True), ('waiting', True), ('demand', 0)]:
            report = evidence()
            report['tts_worker'][field] = value
            examples.append(report)
        for report in examples:
            with self.subTest(report=report):
                watch = kiosk.StalledWorker(90)
                self.assertFalse(watch.observe(report, 0))
                self.assertFalse(watch.observe(report, 1000))

    def test_quiet_and_disconnect_reset_previously_observed_stall(self):
        engine = SimpleNamespace(worker_progress=SimpleNamespace(snapshot=lambda: evidence()['tts_worker']))
        interaction = SimpleNamespace(scene=SimpleNamespace(encounter=SimpleNamespace(silenced=False)))
        self.assertTrue(recovery_report(engine, interaction, False, connected=True)['eligible'])
        # Disconnect cleanup may still retain the old interaction/task.
        self.assertFalse(recovery_report(engine, interaction, False, connected=False)['eligible'])
        for state, muted in ((None, False), (interaction, True)):
            watch = kiosk.StalledWorker(90)
            self.assertFalse(watch.observe(evidence(), 0))
            self.assertFalse(watch.observe(recovery_report(engine, state, muted, connected=True), 100))
            self.assertIsNone(watch.key)
            self.assertFalse(watch.observe(evidence(), 101))
        interaction.scene.encounter.silenced = True
        self.assertFalse(recovery_report(engine, interaction, False, connected=True)['eligible'])

    def test_deadline_validation_includes_saved_configs(self):
        self.assertEqual(kiosk.tts_stall_timeout(), 90)
        for value in (None, True, 0, 29.9, 601, float('nan'), float('inf'), '90'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                kiosk.Supervisor({'tts_stall_timeout': value}, Path('/unused'))
        for value in (30, 90, 600):
            self.assertEqual(kiosk.tts_stall_timeout(value), value)


class RenderProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_whole_render_marks_progress_between_segments(self):
        engine = SpeechEngine()
        clock = [0.]
        engine._worker_progress = WorkerProgress(clock=lambda: clock[0])
        seen = []
        def segments(text):
            for _ in range(5):
                clock[0] += 40
                yield b'\0' * 960, []
                seen.append(engine.worker_progress.snapshot())
        engine.synthesize_segments = segments
        try:
            await engine.render('synthetic progressing render')
            self.assertEqual([s['progress'] for s in seen], [1, 2, 3, 4, 5])
            self.assertTrue(all(s['running_job'] == 1 and s['progress_age_s'] == 0 for s in seen))
            self.assertIsNone(engine.worker_progress.snapshot()['running_job'])
        finally:
            engine.executor.shutdown(wait=True)


if __name__ == '__main__':
    unittest.main()
