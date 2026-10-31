"""A restrained local performance director; no additional inference or prompt tokens."""
import json
from pathlib import Path
import re
import time

from pipecat.frames.frames import (
    LLMTextFrame, LLMFullResponseStartFrame, LLMFullResponseEndFrame,
    TTSSpeakFrame, InterruptionFrame,
)
from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from server.guard import FALLBACK
from server.sound_effects import SoundEffectFrame

ROOT = Path(__file__).resolve().parents[1]/'contexts/sounds'
SERIOUS = re.compile(r"\b(?:help|hurt|scared|afraid|stop|quiet|silence|emergency|allerg\w*|pain|lost|sad|died|dead|death|don't|do not|cannot|can't|sorry)\b",re.I)
JOKE = re.compile(r'\b(?:tell|give) (?:me |us )?(?:a |another )?(?:joke|dad joke)\b|\bmake (?:me|us) laugh\b',re.I)


def load_performance(profile_id, bank):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}',profile_id):
        raise ValueError('Invalid sound profile')
    path=ROOT/(profile_id+'.json')
    if not path.exists():return None
    if path.stat().st_size>16384:raise ValueError('Sound profile too large')
    value=json.loads(path.read_text())
    if set(value)!={'version','cooldown_seconds','minimum_reply_gap','joke_effect','reply_rules'} or value['version']!=1:
        raise ValueError('Invalid sound performance schema')
    if type(value['cooldown_seconds']) not in (int,float) or not 20<=value['cooldown_seconds']<=300:
        raise ValueError('Invalid sound cooldown')
    if type(value['minimum_reply_gap']) is not int or not 2<=value['minimum_reply_gap']<=20:
        raise ValueError('Invalid sound spacing')
    if not isinstance(value['reply_rules'],list) or len(value['reply_rules'])>30:
        raise ValueError('Invalid sound rules')
    for rule in value['reply_rules']:
        if not isinstance(rule,dict) or set(rule)!={'phrases','effect'} or not isinstance(rule['phrases'],list) or not 1<=len(rule['phrases'])<=8:
            raise ValueError('Invalid sound rule')
        if any(not isinstance(p,str) or not 3<=len(p)<=80 for p in rule['phrases']):
            raise ValueError('Invalid sound phrase')
    for effect in [value['joke_effect'],*[r['effect'] for r in value['reply_rules']]]:
        if not isinstance(effect,str) or effect not in bank.effects:
            raise ValueError('Unknown automatic sound')
    return value


class SoundPerformance:
    def __init__(self, bank, state, config=None, clock=time.monotonic, pack_enabled=lambda: True):
        self.bank,self.state,self.config,self.clock=bank,state,config,clock
        self.enabled=config is not None
        self.pack_enabled=pack_enabled
        self.turn=0
        self.replies=0
        self.last_reply=-100
        self.last_at=float('-inf')
        self.last_effect=None
        self.variants={}
        self.blocked=False
        self.joke_requested=False
        self.scheduled=0
        self.started=0
        self.completed=0
        self.direct_started=0

    def observe(self,frame):
        self.turn+=1
        messages=frame.context.get_messages()
        latest=messages[-1] if messages else {}
        text=latest.get('content','') if latest.get('role')=='user' and not getattr(frame,'scene_event',None) else ''
        if not isinstance(text,str):text=''
        self.blocked=bool(SERIOUS.search(text))
        self.joke_requested=bool(JOKE.search(text))

    def interrupted(self):
        self.turn+=1
        self.blocked=True

    def direct(self):
        # A requested effect also prevents an automatic one immediately after it.
        self.blocked=True
        self.last_at=self.clock()
        self.last_reply=self.replies

    def choose(self,speech):
        self.replies+=1
        if (not self.enabled or not self.pack_enabled() or not self.config or self.blocked or not speech
                or speech==FALLBACK or SERIOUS.search(speech)
                or self.state.scene.encounter.silenced or self.state.user_speaking
                or self.clock()-self.last_at<self.config['cooldown_seconds']
                or self.replies-self.last_reply<self.config['minimum_reply_gap']):
            return None
        normalized=' '.join(re.sub(r'[^a-z0-9 ]',' ',speech.casefold()).split())
        effect=next((rule['effect'] for rule in self.config['reply_rules']
                     if any(re.search(r'\b'+re.escape(p)+r'\b',normalized) for p in rule['phrases'])),None)
        effect=effect or (self.config['joke_effect'] if self.joke_requested else None)
        if effect is None:return None
        # Repeated punchlines don't get the same sting on successive eligible turns.
        if effect==self.last_effect and self.clock()-self.last_at<120:return None
        ids=self.bank.effects[effect]
        index=self.variants.get(effect,0)
        self.variants[effect]=(index+1)%len(ids)
        self.last_effect=effect
        self.last_at=self.clock()
        self.last_reply=self.replies
        self.scheduled+=1
        return SoundEffectFrame(sound_id=ids[index],automatic=True,turn=self.turn)

    def report(self):
        return {'enabled':self.enabled,'cooldown_seconds':self.config['cooldown_seconds'] if self.config else None,
                'automatic_scheduled':self.scheduled,'automatic_started':self.started,
                'automatic_completed':self.completed,'direct_started':self.direct_started}


class AutomaticSoundDirector(FrameProcessor):
    """After the reply guard and before TTS; effects queue behind spoken audio."""
    def __init__(self,performance):
        super().__init__()
        self.performance=performance
        self.text=''

    async def process_frame(self,frame,direction):
        await super().process_frame(frame,direction)
        if direction!=FrameDirection.DOWNSTREAM:
            await self.push_frame(frame,direction)
            return
        if isinstance(frame,(LLMFullResponseStartFrame,InterruptionFrame)):
            self.text=''
        if isinstance(frame,InterruptionFrame):self.performance.interrupted()
        if isinstance(frame,LLMTextFrame):self.text=(self.text+frame.text)[:1024]
        speech=None
        if isinstance(frame,TTSSpeakFrame):speech=frame.text
        elif isinstance(frame,LLMFullResponseEndFrame):speech=self.text;self.text=''
        await self.push_frame(frame,direction)
        if speech:
            effect=self.performance.choose(speech)
            if effect:await self.push_frame(effect,direction)
