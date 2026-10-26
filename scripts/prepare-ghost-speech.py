#!/usr/bin/env python3
"""Build original eye textures and one local TTS/viseme demonstration."""
import importlib.util,json,sys,wave,hashlib
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'content/animations/ghost-speech';OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('realistic',ROOT/'scripts/render-ghost-eyes-realistic.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
g=r.RealisticGhost(eyes_only=True)
atlas=Image.new('RGB',(1440,2160))
for i in range(16):
    frame=Image.new('RGB',(720,1080))
    openness=.94*(1-.97*i/15)
    for side in [-1,1]:
        eye=g.eye(0,side,openness*(.98 if side>0 else 1),(0,0),.37,0)
        frame.paste(eye,(48 if side<0 else 362,342+(2 if side>0 else 0)))
    frame=frame.resize((360,540),Image.Resampling.LANCZOS)
    atlas.paste(frame,((i%4)*360,(i//4)*540))
atlas.save(OUT/'eyes-atlas.png')
text='Maybe we should open the spooky door. Five warm waffles for my friendly ghost.'
if not (OUT/'voice-sample.json').exists():
    from server.tts import SpeechEngine
    engine=SpeechEngine(voice='af_heart',speed=1.05,live_settings=False)
    try:audio,cues=engine.synthesize(text,with_cues=True)
    finally:engine.executor.shutdown()
    with wave.open(str(OUT/'voice-sample.wav'),'wb') as w:
        w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(audio)
    sample={'text':text,'sampleRate':24000,'sampleCount':len(audio)//2,'voice':'af_heart','source':'Local Kokoro synthesis with predicted phoneme durations; not forced alignment','cues':cues,'sha256':hashlib.sha256((OUT/'voice-sample.wav').read_bytes()).hexdigest()}
    (OUT/'voice-sample.json').write_text(json.dumps(sample,indent=2)+'\n')
else:sample=json.loads((OUT/'voice-sample.json').read_text())
(OUT/'voice-sample.js').write_text('window.GHOST_SAMPLE = '+json.dumps(sample)+';\n')
print(json.dumps({'duration':sample['sampleCount']/sample['sampleRate'],'shapes':sorted(set(c[2] for c in sample['cues'])),'cueCount':len(sample['cues']),'atlas':[1440,2160]}),flush=True)
