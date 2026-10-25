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
    def __init__(self, model='mlx-community/Kokoro-82M-bf16', voice='af_heart', speed=1.05):
        if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not .8 <= speed <= 1.3:
            raise ValueError("Speech speed must be between 0.8 and 1.3")
        self.speed = float(speed)
        self.model_name = model
        self.voice = voice
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='facebot-tts')
        self.model = None

    def synthesize_segments(self, text):
        # One worker owns model operations, including generator advancement/close.
        if self.model is None:
            self.model = load_model(self.model_name)
        pipeline = self.model._get_pipeline('a')
        for result in pipeline(text, voice=self.voice, speed=self.speed):
            mx.eval(result.audio)
            if self.model.config.sample_rate != 24000:
                raise ValueError('Expected Kokoro 24 kHz output')
            samples = np.asarray(result.audio).reshape(-1)
            audio = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
            mouth_cues = []
            if result.pred_dur is not None:
                phonemes = [p for p in result.phonemes if self.model.vocab.get(p) is not None]
                mouth_cues = cues(phonemes, np.asarray(result.pred_dur).tolist(), len(samples))
            yield audio, mouth_cues

    def synthesize(self, text, with_cues=False):
        chunks, mouth_cues, sample_offset = [], [], 0
        for audio, segment_cues in self.synthesize_segments(text):
            chunks.append(audio)
            mouth_cues.extend([[start+sample_offset, end+sample_offset, shape]
                               for start, end, shape in segment_cues])
            sample_offset += len(audio)//2
        audio = b''.join(chunks)
        return (audio, mouth_cues) if with_cues else audio

    async def stream(self, text):
        # Backpressure: advance only when the consumer asks for another segment.
        # Kokoro still synthesizes a complete segment internally; this does NOT
        # make a single short sentence into token-level streaming synthesis.
        iterator = self.synthesize_segments(text)
        loop = asyncio.get_running_loop()
        try:
            while True:
                segment = await loop.run_in_executor(self.executor, next, iterator, None)
                if segment is None:
                    break
                yield segment
        finally:
            # If inference outlives cancellation, close queues behind it on the
            # same worker; never run concurrent Metal calls or close on the loop.
            await loop.run_in_executor(self.executor, iterator.close)

    async def render(self, text):
        return await asyncio.get_running_loop().run_in_executor(self.executor, self.synthesize, text)

    async def render_with_cues(self, text):
        return await asyncio.get_running_loop().run_in_executor(self.executor, self.synthesize, text, True)


class LocalTTS(TTSService):
    def __init__(self, engine, timing=None):
        super().__init__(sample_rate=24000, settings=TTSSettings(model=engine.model_name, voice=engine.voice, language="en"))
        self.engine = engine
        self.timing = timing

    async def run_tts(self, text, context_id):
        if self.timing: self.timing.mark("tts_start")
        async for audio, mouth_cues in self.engine.stream(text):
            yield OutputTransportMessageFrame(message={'type':'visemes', 'cues':mouth_cues})
            # Cancellation/transport granularity; not synthesis latency evidence.
            for offset in range(0, len(audio), 960):
                yield TTSAudioRawFrame(audio[offset:offset+960], 24000, 1, context_id=context_id)
                await asyncio.sleep(0)
