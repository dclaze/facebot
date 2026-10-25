"""MLX Audio synthesis adapter; Pipecat owns turn cancellation and buffering."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import mlx.core as mx
import numpy as np
from mlx_audio.tts.utils import load_model
from pipecat.frames.frames import TTSAudioRawFrame, OutputTransportMessageFrame
from server.visemes import cues
from pipecat.services.tts_service import TTSService
from pipecat.services.settings import TTSSettings


class SpeechEngine:
    def __init__(self, model='mlx-community/Kokoro-82M-bf16', voice='af_heart'):
        self.model_name = model
        self.voice = voice
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='facebot-tts')
        self.model = None

    def synthesize(self, text, with_cues=False):
        # All model operations run on the same worker, even after an awaiting
        # coroutine is cancelled. Never race a surviving Metal inference call.
        if self.model is None:
            self.model = load_model(self.model_name)
        chunks = []
        mouth_cues = []
        sample_offset = 0
        # The pinned pipeline exposes the same synthesis output plus its timings;
        # no second alignment model or visitor recording is needed.
        pipeline = self.model._get_pipeline('a')
        for result in pipeline(text, voice=self.voice, speed=1.05):
            mx.eval(result.audio)
            if self.model.config.sample_rate != 24000:
                raise ValueError('Expected Kokoro 24 kHz output')
            samples = np.asarray(result.audio).reshape(-1)
            chunks.append((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
            if with_cues and result.pred_dur is not None:
                phonemes = [p for p in result.phonemes if self.model.vocab.get(p) is not None]
                mouth_cues.extend(cues(phonemes, np.asarray(result.pred_dur).tolist(), len(samples), sample_offset))
            sample_offset += len(samples)
        audio = b''.join(chunks)
        return (audio, mouth_cues) if with_cues else audio

    async def render(self, text):
        return await asyncio.get_running_loop().run_in_executor(self.executor, self.synthesize, text)

    async def render_with_cues(self, text):
        return await asyncio.get_running_loop().run_in_executor(self.executor, self.synthesize, text, True)


class LocalTTS(TTSService):
    def __init__(self, engine):
        super().__init__(sample_rate=24000, settings=TTSSettings(model=engine.model_name, voice=engine.voice, language="en"))
        self.engine = engine

    async def run_tts(self, text, context_id):
        audio, mouth_cues = await self.engine.render_with_cues(text)
        yield OutputTransportMessageFrame(message={'type':'visemes', 'cues':mouth_cues})
        # Keep frames small so framework cancellation can flush at 20 ms boundaries.
        for offset in range(0, len(audio), 960):
            yield TTSAudioRawFrame(audio[offset:offset+960], 24000, 1, context_id=context_id)
            await asyncio.sleep(0)
