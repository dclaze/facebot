"""Local Qwen3 CustomVoice, with typed emotion instructions and true PCM chunks.

No voice cloning, remote inference, or arbitrary model-authored instructions.
Unlike Kokoro this backend does not supply phoneme/word alignment. Mouth motion
uses PCM energy, and captions display the current short utterance while speaking.
"""
import numpy as np
import mlx.core as mx
from mlx_audio.tts.utils import load_model
from huggingface_hub import snapshot_download
from server.tts import SpeechEngine, SpeechSegment
from server.spoken_text import spoken_text
from server.settings import read as read_settings
from server.voice_emotion import delivery_instruction, clean_delivery_text

MODEL = 'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-4bit'
REVISION = 'f35faf19b0cc2160865af64ecf0f22f83d335135'


def energy_cues(samples):
    result = []
    for start in range(0, len(samples), 960):
        end = min(len(samples), start + 960)
        rms = float(np.sqrt(np.mean(np.square(samples[start:end]))))
        shape = 'open' if rms > .055 else 'narrow' if rms > .012 else 'rest'
        if result and result[-1][2] == shape:
            result[-1][1] = end
        else:
            result.append([start, end, shape])
    return result


class ExpressiveSpeechEngine(SpeechEngine):
    supports_emotion = True

    def __init__(self, voice='Aiden', speed=1.18, live_settings=False):
        if voice not in ('Ryan', 'Aiden'):
            raise ValueError('Expressive English voice must be Ryan or Aiden')
        super().__init__(model=MODEL, voice=voice, speed=speed, live_settings=live_settings)
        self.last_delivery = None

    def synthesize_segments(self, text, emotion='neutral'):
        text = clean_delivery_text(spoken_text(text))
        if not text:
            return
        if len(text) > 240:
            raise ValueError('Expressive speech exceeds utterance limit')
        if self.model is None:
            # Installation downloads weights explicitly; live speech never
            # resolves a moving model revision or uses a cloud fallback.
            path = snapshot_download(MODEL, revision=REVISION, local_files_only=True)
            self.model = load_model(path)
        if self.live_settings:
            self.speed = read_settings()['speech_rate']
        instruction = delivery_instruction(emotion, self.speed)
        # This is a requested delivery pace, not exact time stretching. Keep
        # the legacy exact-rate readback null instead of claiming that it is.
        self.last_synthesized_rate = None
        self.last_delivery = emotion if emotion in ('neutral', 'skeptical', 'pleased', 'surprised', 'scared') else 'neutral'
        generated = self.model.generate_custom_voice(
            text=text, speaker=self.voice, language='English', instruct=instruction,
            stream=True, streaming_interval=.32, max_tokens=180, temperature=.7)
        total = 0
        pending = []
        started = False
        try:
            for result in generated:
                if result.sample_rate != 24000:
                    raise ValueError('Expected Qwen 24 kHz output')
                mx.eval(result.audio)
                samples = np.asarray(result.audio, dtype=np.float32).reshape(-1)
                if not len(samples):
                    continue
                if not np.isfinite(samples).all():
                    raise ValueError('Nonfinite synthesized audio')
                total += len(samples)
                if total > 24000 * 15:
                    raise ValueError('Expressive utterance exceeded duration limit')
                pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes()
                segment = SpeechSegment(pcm, energy_cues(samples), [[0, len(samples), text[:160]]])
                if started:
                    yield segment
                else:
                    # A bounded two-chunk cushion absorbs small scheduling gaps.
                    # It does not conceal measured longer GPU stalls or buffer
                    # the whole utterance; initial PCM latency includes this cost.
                    pending.append(segment)
                    if total >= 15360:
                        started = True
                        yield from pending
                        pending.clear()
            yield from pending
        finally:
            generated.close()
            # An interrupted stream skips the upstream generator's normal tail.
            # Reset only on this model's single inference worker.
            self.model.speech_tokenizer.decoder.reset_streaming_state()
