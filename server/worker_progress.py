"""Content-free execution evidence for the single native speech worker.

An asyncio cancellation cannot stop native inference. Track execution separately
from its waiters so a cancelled call blocking a later request stays visible.
"""
import threading
import time


class WorkerProgress:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._sequence = 0
        self._running = None
        self._progress = 0
        self._updated = 0
        self._waiting = 0
        self._demand = 0

    def waiting(self, delta):
        with self._lock:
            if self._waiting == 0 and delta > 0:
                self._demand += 1
            self._waiting += delta

    def run(self, function, *args):
        with self._lock:
            self._sequence += 1
            self._running = self._sequence
            self._updated = self._clock()
        try:
            return function(*args)
        finally:
            with self._lock:
                self._running = None

    def advanced(self):
        # Whole-utterance render calls can produce many segments on one job.
        with self._lock:
            if self._running is not None:
                self._progress += 1
                self._updated = self._clock()

    def snapshot(self):
        with self._lock:
            return {'running_job': self._running, 'progress': self._progress,
                    'progress_age_s': max(0., self._clock() - self._updated) if self._running is not None else None,
                    'waiting': self._waiting, 'demand': self._demand}


def recovery_report(engine, interaction, muted, *, connected=False):
    """No session or owner Quiet means no automatic TTS recovery demand."""
    return {'version': 1,
            'eligible': connected is True and interaction is not None and not muted and not interaction.scene.encounter.silenced,
            'tts_worker': engine.worker_progress.snapshot()}
