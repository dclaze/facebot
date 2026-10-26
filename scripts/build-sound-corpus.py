#!/usr/bin/env python3
"""Rebuild Facebot effects from original synthesis and credited local sources."""
import argparse
import hashlib
import json
from pathlib import Path
import wave
import numpy as np

RATE = 24000
ROOT = Path(__file__).resolve().parents[1]
# Names and exact speech aliases are data, not instructions in the hot LLM prompt.
SOUNDS = {
    'ghost': ('spooky', 'ghost sound|ghost noise|spooky sound|ghostly sound|boo'),
    'ghost_laugh': ('spooky', 'ghost laugh|evil laugh|spooky laugh|witch laugh'),
    'creaky_door': ('spooky', 'creaky door|creaking door|door creak'),
    'chains': ('spooky', 'chains|rattling chains|chain rattle'),
    'magic': ('spooky', 'magic|magic spell|magic sparkle|sparkle'),
    'cauldron': ('spooky', 'cauldron|bubbling cauldron|bubbles|bubbling'),
    'bat': ('creatures', 'bat|bat wings|flapping wings'),
    'monster': ('creatures', 'monster|monster growl|growl'),
    'wolf': ('creatures', 'wolf|wolf howl|howl'),
    'owl': ('creatures', 'owl|owl hoot|hoot'),
    'cat': ('creatures', 'cat|meow|cat meow'),
    'dog': ('creatures', 'dog|bark|dog bark|woof'),
    'frog': ('creatures', 'frog|ribbit|frog croak'),
    'cricket': ('creatures', 'cricket|crickets'),
    'fart': ('comic', 'fart|fart noise|raspberry'),
    'burp': ('comic', 'burp|belch'),
    'boing': ('comic', 'boing|spring|bounce'),
    'slide_whistle': ('comic', 'slide whistle|whistle'),
    'rimshot': ('comic', 'rimshot|rim shot|badum tss|ba dum tss'),
    'sad_trombone': ('comic', 'sad trombone|wah wah|womp womp'),
    'squeak': ('comic', 'squeak|rubber duck|squeaky toy'),
    'pop': ('comic', 'pop|bubble pop'),
    'drumroll': ('percussion', 'drumroll|drum roll'),
    'knock': ('percussion', 'knock|knocking|door knock'),
    'footsteps': ('percussion', 'footsteps|steps'),
    'heartbeat': ('percussion', 'heartbeat|heart beat'),
    'bell': ('percussion', 'bell|ding|chime'),
    'gong': ('percussion', 'gong'),
    'wind': ('weather', 'wind|spooky wind|wind blowing'),
    'rain': ('weather', 'rain|raindrops'),
    'thunder': ('weather', 'thunder|thunder rumble'),
    'splash': ('weather', 'splash|water splash'),
    'whoosh': ('movement', 'whoosh|swoosh'),
    'robot': ('arcade', 'robot|robot beep|beep|bleep'),
    'laser': ('arcade', 'laser|pew pew|zap'),
    'ufo': ('arcade', 'ufo|spaceship|flying saucer'),
    'level_up': ('arcade', 'level up|power up'),
    'coin': ('arcade', 'coin|coin pickup'),
    'victory': ('arcade', 'victory|fanfare|celebration'),
    'ticking': ('percussion', 'ticking|clock|tick tock'),
}


def synthesize(kind, variant):
    rng = np.random.default_rng(4100 + list(SOUNDS).index(kind)*17 + variant)
    pitch = (1., 1.09)[variant]
    out = np.zeros(int(2.4*RATE))

    def tone(start, duration, f0, f1=None, gain=1., harmonics=1, wobble=0., noise=0.):
        t = np.arange(int(duration*RATE))/RATE
        freq = np.linspace(f0, f0 if f1 is None else f1, len(t))*pitch
        freq *= 1 + wobble*np.sin(2*np.pi*6*t)
        phase = 2*np.pi*np.cumsum(freq)/RATE
        s = sum(np.sin(phase*h)/(h*h) for h in range(1, harmonics+1))
        s += noise*rng.uniform(-1, 1, len(t))
        env = np.minimum(t/.012, 1)*np.minimum((duration-t)/.055, 1)
        add(start, s*env*gain)

    def add(start, s):
        i = round(start*RATE)
        n = min(len(s), len(out)-i)
        out[i:i+n] += s[:n]

    def noise(start, duration, gain=1., smooth=1, decay=2.):
        n = int(duration*RATE)
        s = rng.normal(size=n)
        if smooth > 1:
            s = np.convolve(s, np.ones(smooth)/smooth, mode='same')*np.sqrt(smooth)
        t = np.arange(n)/RATE
        add(start, s*gain*np.minimum(t/.008, 1)*np.minimum((duration-t)/.05, 1)*np.exp(-decay*t/duration))

    if kind == 'ghost':
        tone(0, 1.75, 330, 155, wobble=.1, harmonics=3)
        tone(.12, 1.5, 665, 305, gain=.24, wobble=.12)
    elif kind == 'ghost_laugh':
        for i in range(6): tone(i*.24, .19, 330-i*23, 190-i*13, harmonics=5, wobble=.2)
    elif kind == 'creaky_door':
        for i in range(18): tone(i*.08, .12, 110+i*13, 150+i*9, gain=.6, harmonics=7, noise=.16)
    elif kind == 'chains':
        for i in range(12):
            noise(i*.11, .09, gain=.2)
            for f in (1700, 2310, 3320): tone(i*.11, .1, f+rng.uniform(-200, 200), gain=.15)
    elif kind in ('magic', 'level_up', 'victory'):
        notes = {'magic':[784,1047,1319,1568,2093,2637], 'level_up':[262,330,392,523,659,784], 'victory':[392,392,392,523,659,784]}[kind]
        for i,f in enumerate(notes): tone(i*.13, .32 if kind=='magic' else .24, f, gain=.7, harmonics=2)
    elif kind == 'cauldron':
        for i in range(18): tone(i*.095, .09, rng.uniform(180,400), rng.uniform(500,1000), gain=.65)
    elif kind == 'bat':
        for i in range(10): noise(i*.12, .10, smooth=18)
    elif kind == 'monster': tone(0, 1.2, 95, 58, harmonics=8, wobble=.23, noise=.2)
    elif kind == 'wolf':
        tone(0,.4,220,480,harmonics=3); tone(.38,.95,480,430,harmonics=3,wobble=.025); tone(1.3,.35,430,180,harmonics=3)
    elif kind == 'owl':
        for start,duration in ((0,.22),(.3,.38),(.92,.4)): tone(start,duration,410,350,harmonics=2)
    elif kind == 'cat':
        tone(0,.2,500,820,harmonics=4);tone(.18,.5,820,350,harmonics=4,wobble=.04)
    elif kind == 'dog':
        for start in (0,.4): tone(start,.19,220,105,harmonics=8,noise=.5)
    elif kind == 'frog':
        for start in (0,.45,.9): tone(start,.22,190,95,harmonics=5,wobble=.5)
    elif kind == 'cricket':
        for i in range(12): tone(i*.11,.055,3900,4300,gain=.5)
    elif kind in ('fart','burp'):
        tone(0,.85 if kind=='fart' else .6,85 if kind=='fart' else 145,45,harmonics=9,wobble=.6,noise=.16)
    elif kind == 'boing': tone(0,.85,410,70,harmonics=3,wobble=.45)
    elif kind == 'slide_whistle':
        tone(0,.65,400,1800);tone(.65,.3,1800,300)
    elif kind in ('rimshot','drumroll'):
        hits = [0,.19] if kind=='rimshot' else np.linspace(0,1.1,22)
        for s in hits: noise(s,.12,.45,decay=5);tone(s,.1,180,80,gain=.4)
        noise(.42 if kind=='rimshot' else 1.2,.7,.35,decay=5)
    elif kind == 'sad_trombone':
        for i,f in enumerate((294,277,262,196)): tone(i*.32,.4,f,f*.94,harmonics=5,wobble=.02)
    elif kind == 'squeak':
        tone(0,.18,1200,2100,harmonics=2);tone(.18,.22,2100,850,harmonics=2)
    elif kind == 'pop': tone(0,.09,750,80,noise=.1)
    elif kind in ('knock','footsteps','heartbeat','ticking'):
        hits={'knock':[0,.24,.48],'footsteps':[0,.4,.8,1.2],'heartbeat':[0,.18,.8,.98],'ticking':[0,.4,.8,1.2]}[kind]
        for i,s in enumerate(hits):
            f={'knock':260,'footsteps':100,'heartbeat':65,'ticking':1700 if i%2 else 2200}[kind]
            tone(s,.10,f,f*.65,harmonics=3)
            if kind!='heartbeat':noise(s,.07,.2,smooth=5,decay=5)
    elif kind in ('bell','gong'):
        for j,ratio in enumerate((1,2.01,2.71,3.93,5.4)):
            f=(700 if kind=='bell' else 110)*ratio
            t=np.arange(int(1.7*RATE))/RATE
            add(0,np.sin(2*np.pi*f*pitch*t)*np.exp(-t*(2+j))*.6/(j+1)*np.minimum(t/.008,1))
    elif kind in ('wind','rain','thunder','splash','whoosh'):
        smooth={'wind':70,'rain':2,'thunder':170,'splash':8,'whoosh':35}[kind]
        duration={'wind':1.8,'rain':1.8,'thunder':1.9,'splash':.65,'whoosh':.8}[kind]
        noise(0,duration,smooth=smooth,decay=.2 if kind in ('wind','rain','whoosh') else 3.)
        if kind=='rain':
            for i in range(26):tone(i*.065,.025,rng.uniform(800,2300),gain=.12)
        if kind=='thunder':tone(0,1.5,55,28,gain=.6,noise=.15)
    elif kind == 'robot':
        for i,f in enumerate((440,880,550,1100,660)):tone(i*.16,.11,f,harmonics=4)
    elif kind == 'laser':
        for start in (0,.35,.7):tone(start,.28,2400,100,harmonics=2)
    elif kind == 'ufo':
        tone(0,1.5,450,1200,wobble=.3);tone(0,1.5,460,1250,gain=.4,wobble=.23)
    elif kind == 'coin':
        tone(0,.12,988,harmonics=2);tone(.12,.5,1319,harmonics=2)
    else: raise ValueError(kind)
    # Trim tail, remove DC, normalize to -9 dBFS peak; fade both boundaries.
    nonzero=np.flatnonzero(np.abs(out)>1e-6)
    out=out[:nonzero[-1]+1]
    out-=out.mean()
    fade=min(240,len(out)//4)
    out[:fade]*=np.linspace(0,1,fade);out[-fade:]*=np.linspace(1,0,fade)
    out*=10**(-9/20)/max(np.max(np.abs(out)),1e-9)
    return (out*32767).astype('<i2').tobytes()


def write_wav(path, pcm):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(RATE);f.writeframes(pcm)


def recorded_pcm(source):
    import soundfile as sf
    from scipy.signal import resample_poly, butter, sosfilt
    path=ROOT/'content/sounds/sources'/source['file']
    if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
        raise ValueError('Source recording checksum mismatch')
    samples,rate=sf.read(path,always_2d=True,dtype='float64')
    start=round(source['start_seconds']*rate)
    end=round(source['end_seconds']*rate) if source['end_seconds'] else len(samples)
    samples=samples[start:end].mean(axis=1)
    # Speed variants intentionally alter pitch as documented in selection.json.
    samples=resample_poly(samples,RATE,round(rate*source['speed']))
    samples=sosfilt(butter(2,45,fs=RATE,btype='highpass',output='sos'),samples)
    active=np.flatnonzero(np.abs(samples)>max(.00001,np.max(np.abs(samples))*.002))
    if not len(active):raise ValueError('Silent source')
    samples=samples[max(0,active[0]-120):min(len(samples),active[-1]+1201)]
    if len(samples)>RATE*6:raise ValueError('Choose a source excerpt under six seconds')
    attack=min(48,len(samples)//4);release=min(1200,len(samples)//4)
    samples[:attack]*=np.linspace(0,1,attack)
    samples[-release:]*=np.linspace(1,0,release)
    # Approximate level matching, with peak headroom; never hard-clip sources.
    gain=min(.10/max(np.sqrt(np.mean(samples*samples)),1e-9),
             10**(-9/20)/max(np.max(np.abs(samples)),1e-9))
    return (samples*gain*32767).astype('<i2').tobytes()


def render(kind,variant,selection):
    sources=selection['recordings'].get(kind)
    if not sources:raise ValueError('Active effects require downloaded, credited sources')
    return recorded_pcm(sources[variant])


def build(destination):
    destination.mkdir(parents=True,exist_ok=True)
    entries=[]
    preview=[]
    selection=json.loads((ROOT/'content/sounds/selection.json').read_text())
    for kind,(category,aliases) in SOUNDS.items():
        if kind not in selection['active_effects']:continue
        for variant in range(2):
            pcm=render(kind,variant,selection)
            filename=f'{kind}_{variant+1:02d}.wav'
            path=destination/filename;write_wav(path,pcm)
            source=selection['recordings'].get(kind,[None,None])[variant]
            entries.append(dict(id=f'{kind}_{variant+1:02d}',effect=kind,category=category,
                aliases=aliases.split('|'),file=filename,duration_ms=round(len(pcm)/48),
                license=source['license'] if source else 'MIT',
                provenance=source or {'method':'original procedural synthesis'},
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
            if variant==0:preview.extend((pcm,bytes(RATE)))
    manifest=dict(version=1,sample_rate=RATE,channels=1,sample_width=2,
        license='Per-entry '+ ' / '.join(sorted({e['license'] for e in entries}))+'; see CREDITS.md',
        provenance='Downloaded creator recordings and designed sound effects; exact credits and transformations in selection.json.',
        peak_dbfs=-9,effects=entries,
        unavailable_aliases=sorted({alias for k,(_,aliases) in SOUNDS.items()
                                    if k not in selection['active_effects']
                                    for alias in [k.replace('_',' '),*aliases.split('|')]}))
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    write_wav(destination/'sampler.wav',b''.join(preview))
    showcase=[]
    for kind in ('ghost_laugh','creaky_door','fart','slide_whistle','boing','rimshot','sad_trombone','laser'):
        showcase.extend((render(kind,0,selection),bytes(RATE)))
    write_wav(destination/'showcase.wav',b''.join(showcase))
    print(json.dumps({'effects':len(selection['active_effects']),'clips':len(entries),'destination':str(destination)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'content/sounds')
    build(parser.parse_args().output)
