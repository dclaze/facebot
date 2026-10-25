"""MLX Audio synthesis adapter; Pipecat owns turn cancellation and buffering."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import mlx.core as mx
import numpy as np
from mlx_audio.tts.utils import load_model
from pipecat.frames.frames import TTSAudioRawFrame
from pipecat.services.tts_service import TTSService
from pipecat.services.settings import TTSSettings


class SpeechEngine:
    def __init__(self, model='mlx-community/Kokoro-82M-bf16', voice='af_heart'):
        self.model_name = model
        self.voice = voice
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='facebot-tts')
        self.model = None

    def synthesize(self, text):
        # All model operations run on the same worker, even after an awaiting
        # coroutine is cancelled. Never race a surviving Metal inference call.
        if self.model is None:
            self.model = load_model(self.model_name)
        chunks = []
        for result in self.model.generate(text=text, voice=self.voice, speed=1.05, lang_code='a'):
            mx.eval(result.audio)
            if result.sample_rate != 24000:
                raise ValueError('Expected Kokoro 24 kHz output')
            samples = np.asarray(result.audio)
            chunks.append((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
        return b''.join(chunks)

    async def render(self, text):
        return await asyncio.get_running_loop().run_in_executor(self.executor, self.synthesize, text)


class LocalTTS(TTSService):
    def __init__(self, engine):
        super().__init__(sample_rate=24000, settings=TTSSettings(model=engine.model_name, voice=engine.voice, language="en"))
        self.engine = engine

    async def run_tts(self, text, context_id):
        audio = await self.engine.render(text)
        # Keep frames small so framework cancellation can flush at 20 ms boundaries.
        for offset in range(0, len(audio), 960):
            yield TTSAudioRawFrame(audio[offset:offset+960], 24000, 1, context_id=context_id)
            await asyncio.sleep(0)
