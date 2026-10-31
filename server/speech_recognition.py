"""Shared local recognition model and synthetic process warmup."""
import asyncio
import time

import numpy as np

STT_MODEL = 'mlx-community/whisper-small.en-mlx'
STT_WARMUP_TIMEOUT_SECONDS = 60


def transcribe(pcm, *, model=STT_MODEL):
    import mlx_whisper
    return mlx_whisper.transcribe(
        pcm, path_or_hf_repo=model, temperature=0., language='en',
        condition_on_previous_text=False,
    )


def warm_stt():
    """Load and exercise this process's recognizer without visitor audio.

    Successful silence decoding establishes model execution, not recognition
    accuracy or acoustic latency. Its transcript is neither used nor retained.
    """
    started = time.monotonic()
    result = transcribe(np.zeros(16000, dtype=np.float32))
    if not isinstance(result, dict) or not isinstance(result.get('segments'), list):
        raise ValueError('Speech recognition warmup returned an invalid result')
    return {'model': STT_MODEL, 'ready': True,
            'warmup_ms': round((time.monotonic() - started) * 1000),
            'evidence': 'synthetic silence; not microphone accuracy or acoustic latency'}


async def warm_stt_startup():
    # MLX runs in-process so the loaded model remains cached for live turns.
    # A timeout prevents readiness; Python cannot cancel the native worker.
    return await asyncio.wait_for(asyncio.to_thread(warm_stt),
                                  timeout=STT_WARMUP_TIMEOUT_SECONDS)
