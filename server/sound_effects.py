"""Exact on-demand effects, kept outside LLM prompts and speech synthesis."""
from dataclasses import dataclass
import asyncio
import hashlib
import json
from pathlib import Path
import re
import wave

from pipecat.frames.frames import (
    DataFrame, LLMContextFrame, OutputTransportMessageFrame, TTSAudioRawFrame,
    TTSStartedFrame, TTSStoppedFrame, TTSSpeakFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection

CORPUS = Path(__file__).resolve().parents[1]/'content/sounds'


class SoundBank:
    def __init__(self, root=CORPUS):
        self.root = Path(root)
        manifest = json.loads((self.root/'manifest.json').read_text())
        if (manifest['version'],manifest['sample_rate'],manifest['channels'],manifest['sample_width']) != (1,24000,1,2):
            raise ValueError('Unsupported sound corpus format')
        self.aliases, self.effects, self.pcm = {}, {}, {}
        self.unavailable = set(manifest.get('unavailable_aliases',()))
        for entry in manifest['effects']:
            filename = entry['file']
            if Path(filename).name != filename or not filename.endswith('.wav'):
                raise ValueError('Invalid sound filename')
            path = self.root/filename
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError('Sound checksum mismatch')
            with wave.open(str(path),'rb') as f:
                if (f.getframerate(), f.getnchannels(), f.getsampwidth(),f.getcomptype()) != (24000,1,2,'NONE') or not 240 <= f.getnframes() <= 144000:
                    raise ValueError('Invalid sound PCM')
                self.pcm[entry['id']] = f.readframes(f.getnframes())
            self.effects.setdefault(entry['effect'], []).append(entry['id'])
            self.aliases[entry['effect'].replace('_',' ')] = entry['effect']
            for alias in entry['aliases']:
                self.aliases[alias] = entry['effect']

    def target(self, text, name='Boo'):
        if not isinstance(text,str) or len(text)>180:
            return None
        text = ' '.join(re.sub(r'[,!?.]', ' ', text.casefold()).split())
        if re.fullmatch(r'(?:(?:hey|hi) )?(?:boo|bo)(?: please)?',text):
            return 'boo'
        names = '(?:boo|bo)' if name.casefold()=='boo' else re.escape(name.casefold())
        text = re.sub(r'^(?:(?:hey|hi) )?'+names+r' ', '', text)
        text = re.sub(r'^please ', '', text)
        text = re.sub(r' please$', '', text)
        # Whole request only: no substring activation on stories, quotes,
        # negations, stop requests or multiple/conflicting commands.
        request = re.fullmatch(
            r'(?:(?:(?:can|could|would|will) you )?(?:play|make|do|give me|let me hear) |'
            r'(?:(?:can|could|would|will) you ))?'
            r'(?:(?:a|an|the|some) )?(.+?)(?: sound effect| sound| noise)?', text)
        target = request.group(1) if request else ''
        return target

    def match(self,text,name='Boo'):
        target=self.target(text,name)
        if target in ('sound effect','sound effects','funny sound','spooky noise'):
            return 'ghost'
        return self.aliases.get(target)


@dataclass
class SoundEffectFrame(DataFrame):
    sound_id: str = ''
    automatic: bool = False
    turn: int = 0


class SoundEffectRequest(FrameProcessor):
    def __init__(self, bank, state, mark=None, name_provider=lambda:'Boo', performance=None):
        super().__init__()
        self.bank, self.state, self.mark, self.name_provider = bank, state, mark, name_provider
        self.next_variant = {}
        self.performance=performance

    async def process_frame(self, frame, direction):
        await super().process_frame(frame,direction)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame,LLMContextFrame) and self.performance:
            self.performance.observe(frame)
        if direction == FrameDirection.DOWNSTREAM and isinstance(frame,LLMContextFrame) and not getattr(frame,'scene_event',None):
            messages = frame.context.get_messages()
            latest = messages[-1] if messages else {}
            text=latest.get('content') if latest.get('role')=='user' else None
            if isinstance(text,str) and self.performance:
                command=' '.join(re.sub(r'[,!?.]',' ',text.casefold()).split())
                if command in ('no sound effects','stop sound effects','turn off sound effects','turn on sound effects','use sound effects again'):
                    enabled=command in ('turn on sound effects','use sound effects again')
                    self.performance.enabled=enabled and self.performance.config is not None
                    self.performance.direct()
                    if not self.state.scene.encounter.silenced:
                        if self.mark:self.mark('prepared_reply')
                        await self.push_frame(TTSSpeakFrame('Automatic effects on.' if self.performance.enabled else 'Automatic effects off.'),direction)
                    return
            effect = self.bank.match(text,self.name_provider())
            target=self.bank.target(text,self.name_provider())
            catalog=isinstance(text,str) and re.fullmatch(
                r'(?:what|which) (?:sound effects|sounds)(?: can you (?:make|play|do)| do you have)[?.!]*',text.strip(),re.I)
            if catalog or target in self.bank.unavailable:
                if self.performance:self.performance.direct()
                if self.state.scene.encounter.silenced:
                    self.state.response_pending=False
                    return
                if self.mark:self.mark('prepared_reply')
                reply=('Ghosts, cackles, farts, cats, whistles, drums, and arcade sounds.' if catalog
                       else "That sound hasn't made the cut yet.")
                await self.push_frame(TTSSpeakFrame(reply),direction)
                return
            if effect:
                if self.performance:self.performance.direct()
                if self.state.scene.encounter.silenced:
                    self.state.response_pending = False
                    return
                variants = self.bank.effects[effect]
                index = self.next_variant.get(effect,0)
                self.next_variant[effect] = (index+1)%len(variants)
                if self.mark:self.mark('prepared_reply')
                await self.push_frame(SoundEffectFrame(sound_id=variants[index]),direction)
                return
        await self.push_frame(frame,direction)


class SoundEffectPlayback(FrameProcessor):
    """After TTS: standard speech-audio envelopes keep floor and flush semantics.

    Pipecat serializes DataFrames and cancels this processor's current frame on
    interruption. The existing native epoch protocol flushes queued PCM.
    """
    def __init__(self, bank, state, mark=None, performance=None):
        super().__init__()
        self.bank, self.state, self.mark = bank, state, mark
        self.performance=performance

    async def process_frame(self, frame, direction):
        await super().process_frame(frame,direction)
        if isinstance(frame,SoundEffectFrame) and direction == FrameDirection.DOWNSTREAM:
            if frame.automatic and (not self.performance or not self.performance.enabled
                    or frame.turn!=self.performance.turn or self.state.user_speaking):
                return
            if self.state.scene.encounter.silenced:
                self.state.response_pending = False
                return
            pcm = self.bank.pcm[frame.sound_id]
            if self.performance:
                if frame.automatic:self.performance.started+=1
                else:self.performance.direct_started+=1
            # Empty cues leave sound effects free of invented speech visemes.
            await self.push_frame(OutputTransportMessageFrame(message={'type':'visemes','cues':[]}),direction)
            await self.push_frame(TTSStartedFrame(),direction)
            if self.mark and not frame.automatic:self.mark('tts_start')
            complete=True
            for offset in range(0,len(pcm),960):
                if self.state.scene.encounter.silenced or (frame.automatic and
                        (self.state.user_speaking or frame.turn!=self.performance.turn or not self.performance.enabled)):
                    complete=False
                    break
                audio=TTSAudioRawFrame(pcm[offset:offset+960],24000,1)
                audio.sound_effect=True
                await self.push_frame(audio,direction)
                if offset==0 and self.mark and not frame.automatic:self.mark('first_pcm')
                await asyncio.sleep(0)
            await self.push_frame(TTSStoppedFrame(),direction)
            if self.performance and frame.automatic and complete:self.performance.completed+=1
            return
        await self.push_frame(frame,direction)
