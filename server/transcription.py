"""Local speech recognition with bounded quality receipts and loop rejection."""
import asyncio
import re
import time
from collections import Counter
from datetime import datetime, timezone

import numpy as np
from pipecat.frames.frames import ErrorFrame, TranscriptionFrame
from pipecat.services.whisper.stt import WhisperSTTServiceMLX


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
        super().__init__(**kwargs)
        self.recorder = recorder
        self.counts = Counter()

    async def run_stt(self, audio):
        started = time.monotonic()
        await self.start_processing_metrics()
        try:
            import mlx_whisper
            pcm = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.
            result = await asyncio.to_thread(
                mlx_whisper.transcribe, pcm,
                path_or_hf_repo=self._settings.model,
                temperature=0., language='en', condition_on_previous_text=False,
            )
            text, reasons = select_transcript(result)
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
        except Exception as error:
            self.counts['errors'] += 1
            yield ErrorFrame(error=f'Local transcription failed: {type(error).__name__}')
        finally:
            await self.stop_processing_metrics()

    def report(self):
        return {'model': self._settings.model, 'counts': dict(self.counts),
                'confidence_is_accuracy': False, 'vad_stop_seconds': .45}
