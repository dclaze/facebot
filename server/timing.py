"""Bounded in-memory stage durations only. Never accepts speech text or media."""
from collections import deque
import math
import time

class StageTiming:
    STAGES = frozenset(('vad_start','vad_stop','stt_done','llm_start','llm_first_text','llm_done','tts_start','first_pcm'))
    PAIRS = {'vad_stop_to_first_pcm_ms':('vad_stop','first_pcm'),
             'stt_after_vad_stop_ms':('vad_stop','stt_done'),
             'turn_routing_ms':('stt_done','llm_start'),
             'llm_first_text_ms':('llm_start','llm_first_text'),
             'llm_complete_ms':('llm_start','llm_done'),
             'tts_first_pcm_ms':('tts_start','first_pcm')}
    def __init__(self, clock=time.monotonic, capacity=64):
        self.clock=clock
        self.samples=deque(maxlen=capacity)
        self.active={}
        self.complete=False
        self.incomplete=0
    def mark(self, stage):
        if stage not in self.STAGES: raise ValueError('Unknown timing stage')
        now=self.clock()
        if stage=='vad_start':
            if self.active and not self.complete: self.incomplete+=1
            self.active={'vad_start':now}; self.complete=False
            return
        if not self.active or self.complete: return
        if stage=="first_pcm" and not all(k in self.active for k in ("vad_stop","stt_done","llm_start","tts_start")):
            return
        self.active.setdefault(stage,now)
        if stage=='first_pcm' and all(k in self.active for k in ('vad_stop','stt_done','llm_start','tts_start')):
            self.samples.append({name:round((self.active[end]-self.active[start])*1000,2)
                for name,(start,end) in self.PAIRS.items() if start in self.active and end in self.active})
            self.complete=True
    def report(self):
        summary={}
        for key in self.PAIRS:
            values=sorted(s[key] for s in self.samples if key in s)
            if values:
                n=len(values)
                median=values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
                summary[key]={'n':n,'median':median,'p95':values[math.ceil(n*.95)-1]}
        return {'evidence':'server frame-stage timing; not acoustic; VAD stop includes endpoint detection delay',
                'completed_samples':len(self.samples),'incomplete_turns':self.incomplete,
                'summary':summary,'samples':list(self.samples)}
