"""Local speech recognition with bounded quality receipts and loop rejection."""
import asyncio
import re
import time
from collections import Counter, deque
from datetime import datetime, timezone

import numpy as np
from pipecat.frames.frames import ErrorFrame, TranscriptionFrame
from pipecat.services.whisper.stt import WhisperSTTServiceMLX
from server.speech_recognition import STT_MODEL, transcribe


def _timed_transcribe(pcm, *, model, timing):
    # Only this worker writes these two timestamps; readers use them after the
    # shielded task completes. Neither PCM nor model output enters the receipt.
    timing['entered'] = time.monotonic()
    try:
        return transcribe(pcm, model=model)
    finally:
        timing['finished'] = time.monotonic()


def repetition_loop(text):
    words = re.findall(r"[\w']+", text.casefold())
    if len(words) < 12:
        return False
    # Reject long repeated phrases, not ordinary emphasis such as "boo, boo!".
    for width in range(1, min(12, len(words) // 3) + 1):
        for start in range(len(words) - width * 3 + 1):
            phrase = words[start:start + width]
            end = start + width
            while words[end:end + width] == phrase:
                end += width
            if end - start >= max(width * 3, len(words) * .6):
                return True
    return False


def select_transcript(result):
    """Reject an unreliable whole utterance instead of stitching missing words.

    These are recognizer diagnostics, not a calibrated accuracy score or proof
    that accepted words were addressed to the bot.
    """
    segments = result.get('segments') or []
    text = ' '.join(str(s.get('text', '')).strip() for s in segments).strip()
    reasons = set()
    if not text:
        reasons.add('empty')
    for segment in segments:
        if segment.get('no_speech_prob', 0.) >= .6:
            reasons.add('likely_silence')
        if segment.get('avg_logprob', 0.) < -1.:
            reasons.add('low_confidence')
        if segment.get('compression_ratio', 0.) > 2.4:
            reasons.add('high_repetition')
    if len(text) > 1500:
        reasons.add('oversized')
    elif repetition_loop(text):
        reasons.add('repeated_phrase')
    return ('' if reasons else text), sorted(reasons)


class LocalSTT(WhisperSTTServiceMLX):
    def __init__(self, *, recorder=None, **kwargs):
        if "settings" not in kwargs and "model" not in kwargs:
            kwargs["settings"] = self.Settings(model=STT_MODEL)
        super().__init__(**kwargs)
        self.recorder = recorder
        self.counts = Counter()
        self._inference_tasks = set()
        self._timing_samples = deque(maxlen=16)
        self.last_inference_finished = float('-inf')

    @property
    def inference_active(self):
        return bool(self._inference_tasks)

    def _inference_finished(self, task, timing):
        self._inference_tasks.discard(task)
        self.last_inference_finished = time.monotonic()
        # A cancelled turn can leave native inference running. Consume its
        # failure without logging text; an active await still gets the error.
        if not task.cancelled():
            task.exception()
        if timing['cancelled'] is not None:
            self._record_timing(timing)

    def _record_timing(self, timing):
        if timing['recorded']:
            return
        timing['recorded'] = True
        def duration(start, end):
            a, b = timing.get(start), timing.get(end)
            return None if a is None or b is None else round(max(0., b-a)*1000, 3)
        receipt = {
            'outcome': timing['outcome'],
            'prepare_ms': duration('started', 'submitted'),
            # Includes event-loop dispatch into asyncio.to_thread, not just
            # time waiting in the default executor's internal queue.
            'queue_ms': duration('submitted', 'entered'),
            'transcribe_ms': duration('entered', 'finished'),
            'result_ms': duration('finished', 'ended'),
            'total_ms': duration('started', 'ended'),
            'cancelled_after_ms': duration('started', 'cancelled'),
            'worker_completion_ms': duration('started', 'finished'),
        }
        self._timing_samples.append(receipt)
        if self.recorder:
            try:
                self.recorder.event('transcription_timing', **receipt)
            except Exception:
                # Optional instrumentation must not break transcription or
                # raise from a native-worker completion callback.
                self.counts['timing_record_errors'] += 1

    async def run_stt(self, audio):
        started = time.monotonic()
        timing = dict(started=started, submitted=None, entered=None, finished=None,
                      ended=None, cancelled=None, outcome='error', recorded=False)
        inference = None
        await self.start_processing_metrics()
        try:
            pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.
            timing['submitted'] = time.monotonic()
            inference = asyncio.create_task(asyncio.to_thread(
                _timed_transcribe, pcm, model=self._settings.model, timing=timing,
            ))
            self._inference_tasks.add(inference)
            inference.add_done_callback(lambda task: self._inference_finished(task, timing))
            # Cancelling a visitor turn cannot cancel the native worker. Keep
            # its task alive and marked busy until it really finishes.
            result = await asyncio.shield(inference)
            text, reasons = select_transcript(result)
            timing['ended'] = time.monotonic()
            timing['outcome'] = 'accepted' if text else 'rejected'
            self._record_timing(timing)
            self.counts['utterances'] += 1
            self.counts['accepted' if text else 'rejected'] += 1
            self.counts.update(reasons)
            if self.recorder:
                segments = result.get('segments') or []
                self.recorder.event('transcription_quality', accepted=bool(text), reasons=reasons,
                    audio_seconds=round(len(pcm) / 16000., 3),
                    inference_ms=round((time.monotonic() - started) * 1000),
                    rms=round(float(np.sqrt(np.mean(pcm * pcm))), 5) if len(pcm) else 0.,
                    clipping_fraction=round(float(np.mean(np.abs(pcm) >= .999)), 5) if len(pcm) else 0.,
                    min_avg_logprob=min((s.get('avg_logprob', 0.) for s in segments), default=None),
                    max_no_speech_prob=max((s.get('no_speech_prob', 0.) for s in segments), default=None),
                    max_compression_ratio=max((s.get('compression_ratio', 0.) for s in segments), default=None))
            if text:
                await self._handle_transcription(text, True, self._settings.language)
                yield TranscriptionFrame(text, self._user_id,
                    datetime.now(timezone.utc).isoformat(), self._settings.language)
        except asyncio.CancelledError:
            if not timing['recorded']:
                timing['cancelled'] = time.monotonic()
                timing['outcome'] = 'cancelled'
                # A running native worker remains busy and publishes once it
                # actually finishes. Cancellation has no completed total.
                if inference is None or inference.done():
                    self._record_timing(timing)
            raise
        except Exception as error:
            if not timing['recorded']:
                timing['ended'] = time.monotonic()
                self._record_timing(timing)
            self.counts['errors'] += 1
            yield ErrorFrame(error=f'Local transcription failed: {type(error).__name__}')
        finally:
            await self.stop_processing_metrics()

    def report(self):
        return {'model': self._settings.model, 'counts': dict(self.counts),
                'confidence_is_accuracy': False, 'vad_stop_seconds': .45,
                'inference_active': self.inference_active,
                'timing': {
                    'capacity': self._timing_samples.maxlen,
                    'evidence': 'host elapsed timing, not GPU or acoustic latency; queue includes async dispatch; total ends after result selection',
                    'samples': [dict(sample) for sample in self._timing_samples],
                }}
