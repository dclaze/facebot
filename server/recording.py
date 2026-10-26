"""Opt-in, private local interaction receipts and bounded microphone history."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import uuid
import wave
from server.profiles import private_path
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

ROOT = Path(__file__).resolve().parents[1] / '.local'

class InteractionRecorder:
    def __init__(self, root=None, *, enabled=False, audio=False, chunk_seconds=60, chunks=10):
        self.root = Path(root) if root else private_path('interactions')
        self.enabled, self.audio_enabled = enabled, enabled and audio
        self.chunk_bytes, self.chunks = int(chunk_seconds * 32000), chunks
        self.session = uuid.uuid4().hex
        self.errors = 0
        self._wav = None
        self._bytes = 0
        self.audio_bytes = 0
        self.text_events = 0
        self._last_output = 0.
        if enabled:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.root.chmod(0o700)
            self._prune()
            self.event('session_started', microphone_audio=self.audio_enabled)

    @classmethod
    def configured(cls):
        try:
            config = json.loads(private_path('recording-config.json').read_text())
        except (OSError, ValueError):
            config = {}
        return cls(enabled=config.get('enabled') is True, audio=config.get('audio') is True)

    def _prune(self):
        now = time.time()
        for pattern, limit, age in [('mic-*.wav', self.chunks, 600), ('events-*.jsonl', 5, 86400)]:
            files = sorted(self.root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            for i, path in enumerate(files):
                if i >= limit or now-path.stat().st_mtime > age:
                    path.unlink(missing_ok=True)

    def event(self, kind, **fields):
        if not self.enabled: return
        try:
            self._prune()
            paths = sorted(self.root.glob('events-*.jsonl'))
            path = paths[-1] if paths and paths[-1].stat().st_size < 10_000_000 else self.root / f'events-{time.time_ns()}.jsonl'
            value = dict(at=datetime.now(timezone.utc).isoformat(), session=self.session, event=kind, **fields)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            with os.fdopen(fd, 'a') as output:
                output.write(json.dumps(value, ensure_ascii=False) + '\n')
            self._prune()
        except OSError:
            self.errors += 1  # Recording failure must not stop conversation.

    def mic_audio(self, pcm):
        if not self.audio_enabled: return
        try:
            while pcm:
                if self._wav is None:
                    path = self.root / f'mic-{time.time_ns()}.wav'
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    self._audio_file = os.fdopen(fd, 'wb')
                    self._wav = wave.open(self._audio_file, 'wb')
                    self._wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                    self._bytes = 0
                    self.event('microphone_chunk', file=path.name, sample_rate=16000, channels=1)
                piece, pcm = pcm[:self.chunk_bytes-self._bytes], pcm[self.chunk_bytes-self._bytes:]
                self._wav.writeframesraw(piece)
                self._bytes += len(piece)
                self.audio_bytes += len(piece)
                if self._bytes == self.chunk_bytes:
                    self._close_audio()
                    self._prune()
        except OSError:
            self.errors += 1
            self.audio_enabled = False

    def _close_audio(self):
        if self._wav:
            self._wav.close()
            self._audio_file.close()
            self._wav = None

    def output_audio(self, size):
        now = time.monotonic()
        if now-self._last_output >= 1:
            self.event('audio_sent', packet_bytes=size, evidence='server transport; not audible playback')
            self._last_output = now

    def close(self):
        self._close_audio()
        self.event('session_closed')

    def report(self):
        return dict(enabled=self.enabled, microphone_audio=self.audio_enabled,
                    microphone_bytes=self.audio_bytes, transcript_events=self.text_events,
                    write_errors=self.errors, audio_retention_seconds=600, transcript_retention_hours=24)


class RecordingTap(FrameProcessor):
    def __init__(self, recorder, stage):
        super().__init__()
        self.recorder, self.stage = recorder, stage

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM:
            kind = type(frame).__name__
            if self.stage == 'input' and kind == 'TranscriptionFrame':
                self.recorder.event('recognized_question', text=frame.text[:8192], source='speech_recognizer; may be inaccurate')
                self.recorder.text_events += 1
            elif self.stage == 'reply' and kind in ('LLMTextFrame', 'TTSSpeakFrame'):
                self.recorder.event('reply_for_synthesis', text=frame.text[:8192], evidence='planned speech; playback not confirmed')
                self.recorder.text_events += 1
            elif (self.stage == 'input' and kind in ('VADUserStartedSpeakingFrame', 'VADUserStoppedSpeakingFrame')) or (self.stage == 'reply' and kind in ('InterruptionFrame', 'LLMFullResponseStartFrame', 'LLMFullResponseEndFrame')):
                self.recorder.event(kind)
        await self.push_frame(frame, direction)
