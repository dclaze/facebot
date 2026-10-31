"""Prepared fictional tribute playback, independent of language generation."""
import asyncio
from dataclasses import dataclass
import hashlib
import json
import math
import struct
from pathlib import Path
from server.captions import validate_captions
import re
import time
import wave

from pipecat.frames.frames import (
    DataFrame, LLMContextFrame, OutputTransportMessageFrame, TTSAudioRawFrame,
    TTSStartedFrame, TTSStoppedFrame, TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

ROOT = Path(__file__).resolve().parents[1] / '.local/skills/robin-williams'


def matches(text, name='Boo'):
    if not isinstance(text, str) or len(text) > 180:
        return False
    text = ' '.join(re.sub(r'[,!?.]', ' ', text.casefold()).split())
    names = '(?:boo|bo)' if name.casefold() == 'boo' else re.escape(name.casefold())
    text = re.sub(r'^(?:(?:hey|hi) )?' + names + r' ', '', text)
    text = re.sub(r'^please | please$', '', text)
    person = r'robin williams(?:\'s)?'
    # Complete requests only: incidental stories, negations, quoted requests,
    # unrelated Robins and compound commands remain ordinary conversation.
    return bool(re.fullmatch(
        r'(?:' + person + r'|is ' + person + r' (?:there|here|around|available)|'
        r'(?:tell (?:me|us) about|what about|how about|who (?:is|was)|'
        r'do you know|did you know|do you remember|are you|'
        r'what do you know about|can you tell (?:me|us) about) ' + person + r'|'
        r'(?:(?:can|could|would|will) you )?(?:play|do|perform|replay|show (?:me|us)) '
        r'(?:the |a )?' + person + r'(?: (?:skit|bit|tribute|performance))?'
        r')', text))


class RobinSkit:
    """Local checksum-bound PCM; an absent package never prevents startup."""
    def __init__(self, root=ROOT):
        self.pcm = b''
        self.sha256 = None
        self.cues = []
        self.captions = []
        try:
            root = Path(root)
            manifest = json.loads((root / 'manifest.json').read_text())
            filename = manifest['file']
            if Path(filename).name != filename or not filename.endswith('.wav'):
                raise ValueError('Invalid skit filename')
            path = root / filename
            if path.stat().st_size > 48000 * 120 + 4096:
                raise ValueError('Skit too large')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if manifest['version'] != 1 or digest != manifest['sha256']:
                raise ValueError('Skit checksum mismatch')
            with wave.open(str(path), 'rb') as source:
                if (source.getframerate(), source.getnchannels(), source.getsampwidth(),
                        source.getcomptype()) != (24000, 1, 2, 'NONE'):
                    raise ValueError('Invalid skit PCM format')
                frames = source.getnframes()
                if not 24000 <= frames <= 24000 * 120:
                    raise ValueError('Invalid skit duration')
                pcm = source.readframes(frames)
                if len(pcm) != frames * 2:
                    raise ValueError('Truncated skit')
            self.pcm, self.sha256 = pcm, digest
            # Optional transcript sidecar is bound to these exact audio bytes.
            # Older packages remain playable when caption metadata is absent.
            try:
                caption_path = root / 'captions.json'
                if caption_path.stat().st_size > 32768:
                    raise ValueError('Caption sidecar too large')
                caption_data = json.loads(caption_path.read_text())
                if caption_data['audio_sha256'] != digest:
                    raise ValueError('Caption audio mismatch')
                captions = validate_captions(caption_data['cues'])
                if captions and captions[-1][1] > frames:
                    raise ValueError('Captions exceed audio')
                self.captions = captions
            except (OSError, ValueError, KeyError, TypeError):
                pass
            # Audio-envelope animation, not inferred phonemes. Sample positions
            # are consumed against the native playback clock, including pauses.
            for offset in range(0, len(pcm), 1920):
                block = pcm[offset:offset+1920]
                samples = struct.unpack('<' + 'h' * (len(block)//2), block)
                rms = math.sqrt(sum(x*x for x in samples)/len(samples))/32768
                mouth = 'open' if rms > .055 else 'narrow' if rms > .012 else 'rest'
                start, end = offset//2, (offset+len(block))//2
                if self.cues and self.cues[-1][2] == mouth:
                    self.cues[-1][1] = end
                else:
                    self.cues.append([start, end, mouth])
        except (OSError, ValueError, KeyError, TypeError, wave.Error, EOFError):
            pass

    def report(self):
        return {'available': bool(self.pcm), 'duration_seconds': len(self.pcm) / 48000,
                'sha256': self.sha256, 'routing_version': 1}


@dataclass
class RobinSkitFrame(DataFrame):
    pass


class RobinSkitRequest(FrameProcessor):
    def __init__(self, skit, state, mark=None, name_provider=lambda: 'Boo',
                 performance=None, clock=time.monotonic, enabled=lambda: True):
        super().__init__()
        self.skit, self.state, self.mark = skit, state, mark
        self.name_provider, self.performance, self.clock = name_provider, performance, clock
        self.last_request = float('-inf')
        self.intent_frame = None
        self.enabled = enabled

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame, LLMContextFrame):
            self.intent_frame = frame
        if (direction == FrameDirection.DOWNSTREAM and isinstance(frame, LLMContextFrame)
                and not getattr(frame, 'scene_event', None)):
            messages = frame.context.get_messages()
            latest = messages[-1] if messages else {}
            text = latest.get('content') if latest.get('role') == 'user' else None
            self.intent_frame = frame
            if matches(text, self.name_provider()):
                await self.dispatch(frame, direction)
                return
        await self.push_frame(frame, direction)


    async def dispatch(self, frame, direction):
        if self.performance:
            self.performance.observe(frame)
            self.performance.direct()
        if self.state.scene.encounter.silenced or self.state.user_speaking:
            self.state.response_pending = False
            return
        if not self.enabled():
            if self.mark:
                self.mark('prepared_reply')
            await self.push_frame(TTSSpeakFrame('That performance is resting tonight.'), direction)
            return
        # Ignore duplicate final transcripts; another request can replay.
        now = self.clock()
        if now - self.last_request < 3:
            self.state.response_pending = False
            return
        self.last_request = now
        if self.mark:
            self.mark('prepared_reply')
        if self.skit.pcm:
            await self.push_frame(RobinSkitFrame(), direction)
        else:
            await self.push_frame(TTSSpeakFrame("The Robin Williams skit isn't available yet."), direction)
        return

class RobinSkitPlayback(FrameProcessor):
    """After TTS: ordinary paced transport, cancellation and native epoch flush."""
    def __init__(self, skit, state, mark=None):
        super().__init__()
        self.skit, self.state, self.mark = skit, state, mark

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, RobinSkitFrame) and direction == FrameDirection.DOWNSTREAM:
            if self.state.scene.encounter.silenced or not self.skit.pcm:
                self.state.response_pending = False
                return
            # Envelope cues follow the existing native audio playback clock.
            await self.push_frame(OutputTransportMessageFrame(message={'type': 'visemes', 'cues': self.skit.cues, 'captions': self.skit.captions}), direction)
            await self.push_frame(TTSStartedFrame(), direction)
            if self.mark:
                self.mark('tts_start')
            for offset in range(0, len(self.skit.pcm), 960):
                if self.state.scene.encounter.silenced:
                    break
                audio = TTSAudioRawFrame(self.skit.pcm[offset:offset+960], 24000, 1)
                audio.sound_effect = True  # Prepared media, excluded from synthesis metrics.
                await self.push_frame(audio, direction)
                if offset == 0 and self.mark:
                    self.mark('first_pcm')
                await asyncio.sleep(0)
            await self.push_frame(TTSStoppedFrame(), direction)
            return
        await self.push_frame(frame, direction)
