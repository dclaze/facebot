"""MLX Audio synthesis adapter; Pipecat owns turn cancellation and buffering."""
import asyncio
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import mlx.core as mx
import numpy as np
from mlx_audio.tts.utils import load_model
from pipecat.frames.frames import TTSAudioRawFrame, OutputTransportMessageFrame, InterruptionFrame, TTSStoppedFrame
from server.visemes import cues
from server.prepared_audio import PreparedAudioCache
from server.captions import caption_cues
from server.spoken_text import spoken_text
from server.settings import read as read_settings
from server.worker_progress import WorkerProgress
from pipecat.services.tts_service import TTSService
from pipecat.services.settings import TTSSettings


@dataclass
class SpeechSegment:
    audio: bytes
    mouth_cues: list
    captions: list

    def __iter__(self):
        # Preserve existing offline render callers that unpack audio and visemes.
        yield self.audio
        yield self.mouth_cues

    def __len__(self):
        return 2

    def __getitem__(self, index):
        return (self.audio, self.mouth_cues)[index]


class SpeechEngine:
    def __init__(self, model='mlx-community/Kokoro-82M-bf16', voice='af_heart', speed=1.05, live_settings=False):
        if not isinstance(speed, (int, float)) or isinstance(speed, bool) or not .8 <= speed <= 1.3:
            raise ValueError("Speech speed must be between 0.8 and 1.3")
        self.speed = float(speed)
        self.last_synthesized_rate = None
        self.live_settings = live_settings
        self.model_name = model
        self.voice = voice
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='facebot-tts')
        self.model = None
        self.prepared_cache = PreparedAudioCache(model)

    @property
    def worker_progress(self):
        # Initialized on the event-loop thread before any tracked submission.
        if not hasattr(self, '_worker_progress'):
            self._worker_progress = WorkerProgress()
        return self._worker_progress

    async def _run_worker(self, function, *args):
        progress = self.worker_progress
        progress.waiting(1)
        try:
            return await asyncio.get_running_loop().run_in_executor(
                self.executor, progress.run, function, *args)
        finally:
            progress.waiting(-1)

    def synthesize_segments(self, text):
        text = spoken_text(text)
        if not text:
            return
        # Capture voice/rate for the complete utterance and cache identity.
        if self.live_settings:
            self.speed = read_settings()['speech_rate']
        voice, speed = self.voice, self.speed
        cached = self.prepared_cache.get(text, voice, speed)
        if cached is not None:
            self.last_synthesized_rate = speed
            for audio, mouth_cues, captions in cached:
                yield SpeechSegment(audio, mouth_cues, captions)
            return
        # One worker owns model operations, including generator advancement/close.
        if self.model is None:
            self.model = load_model(self.model_name)
        pipeline = self.model._get_pipeline('a')
        complete_segments = []
        for result in pipeline(text, voice=voice, speed=speed):
            mx.eval(result.audio)
            if self.model.config.sample_rate != 24000:
                raise ValueError('Expected Kokoro 24 kHz output')
            samples = np.asarray(result.audio).reshape(-1)
            audio = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
            mouth_cues = []
            if result.pred_dur is not None:
                phonemes = [p for p in result.phonemes if self.model.vocab.get(p) is not None]
                mouth_cues = cues(phonemes, np.asarray(result.pred_dur).tolist(), len(samples))
            self.last_synthesized_rate = speed
            segment = SpeechSegment(audio, mouth_cues, caption_cues(getattr(result, 'graphemes', text), len(samples), getattr(result, 'tokens', None)))
            complete_segments.append(segment)
            yield segment
        # Only a fully exhausted synthesis is reusable after cancellation.
        self.prepared_cache.put(text, voice, speed, complete_segments)

    def synthesize(self, text, with_cues=False):
        chunks, mouth_cues, sample_offset = [], [], 0
        for audio, segment_cues in self.synthesize_segments(text):
            self.worker_progress.advanced()
            chunks.append(audio)
            mouth_cues.extend([[start+sample_offset, end+sample_offset, shape]
                               for start, end, shape in segment_cues])
            sample_offset += len(audio)//2
        audio = b''.join(chunks)
        return (audio, mouth_cues) if with_cues else audio

    async def stream(self, text, *, emotion=None):
        # Backpressure: advance only when the consumer asks for another segment.
        # Kokoro still synthesizes a complete segment internally; this does NOT
        # make a single short sentence into token-level streaming synthesis.
        iterator = (self.synthesize_segments(text) if emotion is None else
                    self.synthesize_segments(text, emotion=emotion))
        try:
            while True:
                segment = await self._run_worker(next, iterator, None)
                if segment is None:
                    break
                yield segment
        finally:
            # If inference outlives cancellation, close queues behind it on the
            # same worker; never run concurrent Metal calls or close on the loop.
            # Do not hold Pipecat's interruption path waiting for that inference.
            # Submit directly so task cancellation cannot cancel the queued close.
            cleanup = self.executor.submit(self.worker_progress.run, iterator.close)
            task = asyncio.current_task()
            if not task or not task.cancelling():
                await asyncio.shield(asyncio.wrap_future(cleanup))

    async def render(self, text):
        return await self._run_worker(self.synthesize, text)

    async def render_with_cues(self, text):
        return await self._run_worker(self.synthesize, text, True)


class LocalTTS(TTSService):
    def __init__(self, engine, timing=None):
        super().__init__(sample_rate=24000, push_start_frame=True, push_stop_frames=True,
                         settings=TTSSettings(model=engine.model_name, voice=engine.voice, language="en"))
        self.engine = engine
        self.timing = timing
        self.expression = 'neutral'

    async def process_frame(self, frame, direction):
        from server.reactions import validate_expression
        if isinstance(frame, OutputTransportMessageFrame) and validate_expression(frame.message):
            self.expression = frame.message['name']
        elif isinstance(frame, (InterruptionFrame, TTSStoppedFrame)):
            self.expression = 'neutral'
        await super().process_frame(frame, direction)

    async def run_tts(self, text, context_id):
        if self.timing: self.timing.mark("tts_start")
        expression, self.expression = self.expression, 'neutral'
        stream = (self.engine.stream(text, emotion=expression)
                  if getattr(self.engine, 'supports_emotion', False) else self.engine.stream(text))
        async for segment in stream:
            audio, mouth_cues = segment
            yield OutputTransportMessageFrame(message={'type':'visemes', 'cues':mouth_cues,
                                                       'captions':getattr(segment, 'captions', [])})
            # Cancellation/transport granularity; not synthesis latency evidence.
            for offset in range(0, len(audio), 960):
                yield TTSAudioRawFrame(audio[offset:offset+960], 24000, 1, context_id=context_id)
                await asyncio.sleep(0)
