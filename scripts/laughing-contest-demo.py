#!/usr/bin/env python3
"""Isolated audiovisual rehearsal: no live server, tablet or microphone."""
import hashlib, json, math, subprocess, sys, wave
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'.local/laughing-contest-tools')]
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy.signal import resample_poly
OUT = ROOT/'.local/laughing-contest'
SR,FPS,W,H = 24000,30,1080,720
PEAK=10**(-9/20)

def read_wav(path):
    with wave.open(str(path),'rb') as f:
        assert (f.getframerate(),f.getnchannels(),f.getsampwidth())==(SR,1,2)
        return np.frombuffer(f.readframes(f.getnframes()),'<i2').astype(float)/32768

def write_wav(path,data):
    data=np.asarray(data,dtype=float).copy()
    data*=min(1,PEAK/max(float(np.max(np.abs(data))),1e-8))
    n=min(240,len(data)//2)
    data[:n]*=np.linspace(0,1,n);data[-n:]*=np.linspace(1,0,n)
    with wave.open(str(path),'wb') as f:
        f.setparams((1,2,SR,0,'NONE','not compressed'))
        f.writeframes((data*32767).astype('<i2').tobytes())

def prepare_audio():
    lines=[('invite','Want to try a laughing contest?','af_heart',1.05),
           ('yes','Yeah!','af_sky',1.1),('first','You go first.','af_heart',1.05),
           ('kid','Ha ha ha! Ha ha!','af_sky',1.15)]
    missing=[r for r in lines if not (OUT/(r[0]+'.wav')).exists()]
    if missing:
        from server.tts import SpeechEngine
        engine=SpeechEngine()
        try:
            for key,text,voice,speed in missing:
                engine.voice,engine.speed=voice,speed
                data=np.frombuffer(engine.synthesize(text),'<i2').astype(float)/32768
                if key in ('yes','kid'):data=resample_poly(data,9,10)
                write_wav(OUT/(key+'.wav'),data)
                print('Prepared '+key,flush=True)
        finally:engine.executor.shutdown()
    # V2 uses a new recorded male performance, not the earlier witch cackle.
    path=ROOT/'content/laughing-contest/sources/ninjashark-evil-laugh.mp3'
    metadata=json.loads((ROOT/'content/laughing-contest/source.json').read_text())
    assert hashlib.sha256(path.read_bytes()).hexdigest()==metadata['sha256']
    decoded=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(path),
                            '-f','s16le','-ac','1','-ar',str(SR),'pipe:1'],
                           capture_output=True,check=True).stdout
    original=np.frombuffer(decoded,'<i2').astype(float)/32768
    write_wav(OUT/'online-source.wav',original)
    sources=[]
    for name,up,down in [('deep-cackle',4,3),('raspy-cackle',6,5)]:
        # -4.98 semitones for the main version; -3.16 for the alternative.
        low=resample_poly(original,up,down)
        from scipy.signal import butter,sosfilt
        low=sosfilt(butter(2,45,'highpass',fs=SR,output='sos'),low)
        body=sosfilt(butter(2,220,'lowpass',fs=SR,output='sos'),low)
        laugh=np.tanh((low+.5*body)*1.35)/1.35
        room=np.zeros(len(laugh)+int(.7*SR));room[:len(laugh)]=laugh
        for delay,gain in [(.14,.16),(.29,.09),(.47,.04),(.64,.02)]:
            i=int(delay*SR);room[i:i+len(laugh)]+=laugh*gain
        # Same digital ceiling as v1: intensity comes from performance/timbre.
        room*=PEAK/max(float(np.max(np.abs(room))),1e-8)
        write_wav(OUT/(name+'.wav'),room)
        sources.append({**metadata,'variant':name,'speed':down/up,
                        'pitch_semitones':12*math.log2(down/up),
                        'processing':'45Hz highpass, bass body, mild saturation, short room echo',
                        'output_sha256':hashlib.sha256((OUT/(name+'.wav')).read_bytes()).hexdigest()})
    return sources

def timeline():
    chunks=[np.zeros(int(.55*SR))];cues=[];cursor=.55
    for key,caption,speaker,gap in [
        ('invite','Want to try a laughing contest?','Casper',.35),
        ('yes','Yeah!','Participant - simulated',.3),
        ('first','You go first.','Casper',.45),
        ('kid','[laughs]','Participant - simulated',.6),
        ('deep-cackle','','Casper',1.2)]:
        data=read_wav(OUT/(key+'.wav'))
        cues.append(dict(key=key,start=cursor,end=cursor+len(data)/SR,caption=caption,speaker=speaker))
        chunks.extend([data,np.zeros(round(gap*SR))]);cursor+=len(data)/SR+gap
    return np.concatenate(chunks),cues

def render(t,audio,cues,title='LAUGHING CONTEST  /  SILENT ENDING V4'):
    S=2;im=Image.new('RGB',(W*S,H*S),'black');d=ImageDraw.Draw(im)
    cream,gold,deep='#fff0c7','#ffb058','#7a3c15'
    def ellipse(box,fill):d.ellipse(tuple(v*S for v in box),fill=fill)
    def polygon(points,fill):d.polygon([(x*S,y*S) for x,y in points],fill=fill)
    def curve(points,fill,width):
        a,b,c=[np.array(p) for p in points]
        pts=[tuple(((1-u)**2*a+2*(1-u)*u*b+u*u*c)*S) for u in np.linspace(0,1,50)]
        d.line(pts,fill=fill,width=round(width*S),joint='curve')
    cue=next((c for c in cues if c['start']<=t<c['end']),None)
    scary=next(c for c in cues if c['key']=='deep-cackle');dt=t-scary['start']
    eyes_only=0<=dt<scary['end']-scary['start'];blackout=-.18<=dt<0
    sample=audio[max(0,int(t*SR)):int((t+.025)*SR)]
    energy=min(1,float(np.sqrt(np.mean(sample**2)))*14) if len(sample) else 0
    speaking=cue and cue['speaker']=='Casper'
    if eyes_only:
        for x,lean in [(65,50),(210,-40),(890,30),(1015,-50)]:
            polygon([(x-14,H),(x+7,80),(x+lean,0),(x+25,0),(x+31,H)],'#0b100c')
            curve([(x+10,320),(x+lean,230),(x-90,170)],'#0b100c',9)
        for center,sign in [(395,1),(685,-1)]:
            polygon([(center-80,292-12*sign),(center-35,298),(center+70,320+12*sign),
                     (center+32,353),(center-25,348)],'#ffa62c')
            ellipse((center-8,302,center+9,350),'#180c00')
            ellipse((center-25,311,center-16,319),'#fff0b6')
        im=Image.blend(im.filter(ImageFilter.GaussianBlur(15*S)),im,.78)
        d=ImageDraw.Draw(im)
    elif not blackout:
        bob=math.sin(t*1.6)*3
        for cx,cy in [(313,278),(767,264)]:
            cy+=bob;blink=.12 if t%5.3<.11 else 1
            if cue and cue['key']=='kid':blink=.72
            ellipse((cx-190,cy-69*blink,cx+190,cy+74*blink),deep)
            ellipse((cx-172,cy-57*blink,cx+172,cy+57*blink),cream)
            dx=9*math.sin(t*.7)
            ellipse((cx-65+dx,cy-45*blink,cx+65+dx,cy+45*blink),gold)
            ellipse((cx-36+dx,cy-39*blink,cx+36+dx,cy+39*blink),'#191007')
            ellipse((cx-25+dx,cy-30*blink,cx-8+dx,cy-16*blink),'white')
        curve([(130,201+bob),(270,170+bob),(463,202+bob)],gold,15)
        curve([(616,190+bob),(810,141+bob),(950,178+bob)],cream,17)
        ellipse((524,331+bob,556,348+bob),gold)
        aperture=(8+energy*78) if speaking else 3;y=414+bob
        curve([(360,y),(540,y+38),(720,y-12)],gold,5)
        if aperture>10:
            pts=[(360+360*u,y+12*math.sin(math.pi*u)-12*u) for u in np.linspace(0,1,50)]
            pts += [(360+360*u,y+(aperture+18)*math.sin(math.pi*u)-12*u) for u in np.linspace(1,0,50)]
            polygon(pts,deep)
            d.line([(x*S,yy*S) for x,yy in pts+[pts[0]]],fill=gold,width=5*S,joint='curve')
            curve([(396,y+12),(540,y+35),(684,y+2)],cream,9)
        curve([(205,393+bob),(225,378+bob),(270,381+bob)],gold,6)
        curve([(820,368+bob),(864,350+bob),(886,373+bob)],cream,6)
    def text(value,y,size,fill):
        font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',size*S)
        d.text((W*S/2,y*S),value,font=font,fill=fill,anchor='mm')
    text(title,35,15,'#9a8c77')
    if not blackout and not eyes_only:text('CASPER',535,21,gold)
    if cue and cue['caption']:
        text(cue['caption'],603,29,cream);text(cue['speaker'],645,15,'#ad9c84')
    elif cue and cue['key']=='deep-cackle':text('[theatrical cackle]',625,18,'#ad9c84')
    text('LOCAL REHEARSAL / SIMULATED PARTICIPANT / NOT LIVE ON TABLET',696,12,'#6f665a')
    return im.resize((W,H),Image.Resampling.LANCZOS)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    sources=prepare_audio();audio,cues=timeline();write_wav(OUT/'soundtrack.wav',audio)
    movie=OUT/'laughing-contest-demo.mp4'
    command=[imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-f','rawvideo','-pix_fmt','rgb24',
             '-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-i',str(OUT/'soundtrack.wav'),
             '-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p',
             '-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',str(movie)]
    process=subprocess.Popen(command,stdin=subprocess.PIPE)
    frames=math.ceil(len(audio)/SR*FPS)
    try:
        for frame in range(frames):process.stdin.write(render(frame/FPS,audio,cues).tobytes())
        process.stdin.close()
        if process.wait()!=0:raise RuntimeError('Encoder failed')
    finally:
        if process.poll() is None:process.kill();process.wait()
    scary=next(c for c in cues if c['key']=='deep-cackle')
    for name,t in [('friendly',1),('wolf-eyes',scary['start']+.6),('recovery',scary['end']+.6)]:
        render(t,audio,cues).save(OUT/(name+'.png'))
    receipt=dict(kind='Local audiovisual rehearsal; simulated participant; no device connection',
                 approval='pending',fps=FPS,frames=frames,duration_seconds=len(audio)/SR,
                 audio_peak_dbfs=20*math.log10(float(np.max(np.abs(read_wav(OUT/'soundtrack.wav'))))),
                 blackout_seconds=.18,blackout_before_laugh=True,
                 wolf_eyes_seconds=scary['end']-scary['start'],timeline=cues,sources=sources,
                 movie_sha256=hashlib.sha256(movie.read_bytes()).hexdigest())
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(movie=str(movie),duration_seconds=receipt['duration_seconds'],
                         audio_peak_dbfs=receipt['audio_peak_dbfs'])),flush=True)
if __name__=='__main__':main()
