"""Immutable CC0 cackle, using the same cancellable PCM envelope as speech."""
import asyncio
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import wave

from pipecat.frames.frames import DataFrame, OutputTransportMessageFrame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

ROOT = Path(__file__).resolve().parents[1] / 'content/kiosk'


@dataclass
class KioskCackleFrame(DataFrame):
    requested_at: float = 0.
    control_epoch: int = 0


def load_cackle():
    manifest = json.loads((ROOT / 'manifest.json').read_text())
    path = ROOT / 'deep-cackle-v2.wav'
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sha256']:
        raise ValueError('Kiosk cackle checksum mismatch')
    with wave.open(str(path)) as wav:
        if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (24000, 1, 2):
            raise ValueError('Kiosk cackle PCM format mismatch')
        if wav.getnframes() != manifest['samples'] or not 240 <= wav.getnframes() <= 24000 * 12:
            raise ValueError('Kiosk cackle duration mismatch')
        return wav.readframes(wav.getnframes())


class KioskPlayback(FrameProcessor):
    def __init__(self, state, mark=None):
        super().__init__()
        self.state, self.mark, self.pcm = state, mark, load_cackle()

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if direction != FrameDirection.DOWNSTREAM or not isinstance(frame, KioskCackleFrame):
            await self.push_frame(frame, direction)
            return
        if (frame.control_epoch != self.state.control_epoch
                or self.state.scene.encounter.silenced or self.state.user_speaking
                or self.state.clock() - frame.requested_at > 2):
            self.state.response_pending = False
            return
        await self.push_frame(OutputTransportMessageFrame(message={
            'type': 'performance_face', 'name': 'wolf_eyes', 'duration_samples': len(self.pcm) // 2}), direction)
        await self.push_frame(OutputTransportMessageFrame(message={'type': 'visemes', 'cues': []}), direction)
        await self.push_frame(TTSStartedFrame(), direction)
        if self.mark:
            self.mark('tts_start')
        for offset in range(0, len(self.pcm), 960):
            if (self.state.scene.encounter.silenced or self.state.user_speaking
                    or frame.control_epoch != self.state.control_epoch):
                break
            audio = TTSAudioRawFrame(self.pcm[offset:offset + 960], 24000, 1)
            audio.sound_effect = True
            await self.push_frame(audio, direction)
            if offset == 0 and self.mark:
                self.mark('first_pcm')
            await asyncio.sleep(0)
        await self.push_frame(TTSStoppedFrame(), direction)
