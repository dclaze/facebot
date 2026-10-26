#!/usr/bin/env python3
"""Render a validated interaction script with local speech and the existing face rig."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('laugh_demo',ROOT/'scripts/laughing-contest-demo.py')
rig=importlib.util.module_from_spec(spec);spec.loader.exec_module(rig)


def validate(script, context_keywords=()):
    if not isinstance(script,dict) or set(script)!={'title','summary','trigger','lines','sound_id','rationale'}:
        raise ValueError('Invalid script fields')
    for key,limit in [('title',60),('summary',240),('trigger',300),('rationale',600)]:
        if not isinstance(script[key],str) or not 1<=len(script[key])<=limit:raise ValueError('Invalid '+key)
    if not isinstance(script['lines'],list) or not 2<=len(script['lines'])<=5:raise ValueError('Use 2–5 dialogue turns')
    for line in script['lines']:
        if not isinstance(line,dict) or set(line)!={'actor','text'}:raise ValueError('Invalid dialogue line')
        if line['actor'] not in ('bot','visitor'):raise ValueError('Invalid actor')
        if not isinstance(line['text'],str) or not 1<=len(line['text'].split())<=12 or len(line['text'])>150:
            raise ValueError('Keep each line to 1–12 words')
    consecutive_words=0
    for line in script['lines']:
        consecutive_words=consecutive_words+len(line['text'].split()) if line['actor']=='bot' else 0
        if consecutive_words>12:raise ValueError('A complete bot turn must stay within 12 words')
    spoken=' '.join(x['text'].casefold() for x in script['lines'] if x['actor']=='visitor')
    if context_keywords and not any(word.casefold() in spoken for word in context_keywords):
        raise ValueError('Visitor must explicitly provide the required scene context')
    if not any(x['actor']=='bot' for x in script['lines']):raise ValueError('Missing character dialogue')
    manifest=json.loads((ROOT/'content/sounds/manifest.json').read_text())
    if script['sound_id']!='none' and script['sound_id'] not in {x['id'] for x in manifest['effects']}:
        raise ValueError('Unknown sound')
    return script


def render(script, output):
    validate(script);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'.local/experience-workshop/speech';cache.mkdir(parents=True,exist_ok=True)
    from server.tts import SpeechEngine
    engine=SpeechEngine()
    clips=[];cues=[];cursor=.45;clips.append(rig.np.zeros(round(cursor*rig.SR)))
    try:
        for number,line in enumerate(script['lines']):
            voice='af_heart' if line['actor']=='bot' else 'am_adam'
            key=hashlib.sha256((voice+'|1.05|'+line['text']).encode()).hexdigest()
            wav=cache/(key+'.wav')
            if not wav.exists():
                engine.voice=voice;engine.speed=1.05
                pcm=rig.np.frombuffer(engine.synthesize(line['text']),'<i2').astype(float)/32768
                rig.write_wav(wav,pcm)
            data=rig.read_wav(wav)
            cues.append({'key':'line-'+str(number),'start':cursor,'end':cursor+len(data)/rig.SR,
                         'caption':line['text'],'speaker':'Casper' if line['actor']=='bot' else 'Visitor - simulated'})
            clips.extend([data,rig.np.zeros(round(.5*rig.SR))]);cursor+=len(data)/rig.SR+.5
    finally:engine.executor.shutdown()
    sources=[]
    if script['sound_id']!='none':
        manifest=json.loads((ROOT/'content/sounds/manifest.json').read_text())
        entry=next(x for x in manifest['effects'] if x['id']==script['sound_id'])
        source=ROOT/'content/sounds'/entry['file']
        if hashlib.sha256(source.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Sound changed')
        data=rig.read_wav(source);clips.append(data)
        cues.append({'key':'effect','start':cursor,'end':cursor+len(data)/rig.SR,
                     'caption':'['+entry['effect'].replace('_',' ')+']','speaker':'Sound effect'})
        cursor+=len(data)/rig.SR;sources.append(entry)
    clips.append(rig.np.zeros(round(.8*rig.SR)))
    audio=rig.np.concatenate(clips);rig.write_wav(output/'soundtrack.wav',audio)
    visual_cues=cues+[{'key':'deep-cackle','start':-10,'end':-10,'caption':'','speaker':''}]
    frames=math.ceil(len(audio)/rig.SR*rig.FPS)
    title=script['title'].upper()+' / DRAFT PREVIEW'
    command=[rig.imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
             '-s',f'{rig.W}x{rig.H}','-r',str(rig.FPS),'-i','pipe:0','-i',str(output/'soundtrack.wav'),
             '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
             '-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(output/'demo.mp4')]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for frame in range(frames):
            process.stdin.write(rig.render(frame/rig.FPS,audio,visual_cues,title=title).tobytes())
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('Video encoding failed')
    finally:
        if process.poll() is None:process.kill();process.wait()
    rig.render(1,audio,visual_cues,title=title).save(output/'poster.png')
    subprocess.run([rig.imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(output/'demo.mp4'),
                    '-f','null','-'],check=True)
    receipt={'evidence':'locally rendered rehearsal; simulated visitor; no runtime activation',
             'duration_seconds':len(audio)/rig.SR,'full_decode':True,'timeline':cues,'sound_sources':sources}
    credits='# Preview credits\n\nDialogue is an owner-review draft rendered with local Kokoro. Visitor audio is simulated.\n\n'
    for source in sources:
        credits+='## '+source['id']+'\n\n'+json.dumps(source,indent=2)+'\n\n'
    (output/'CREDITS.md').write_text(credits)
    (output/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (output/'script.json').write_text(json.dumps(script,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('script');p.add_argument('output')
    args=p.parse_args();print(json.dumps(render(json.loads(Path(args.script).read_text()),args.output)))
