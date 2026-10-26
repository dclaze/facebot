#!/usr/bin/env python3
"""Package the verified original skit, Fish lead-in and music video for runtime."""
from pathlib import Path
import hashlib
import json
import math
import shutil
import subprocess
import sys
import tempfile
import wave
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'.local/laughing-contest-tools'))
import imageio_ffmpeg
from server.captions import caption_cues
from server.robin_skit import RobinSkit, ROOT as SPOKEN_ROOT


def verified(path,digest):
    path=Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Source checksum mismatch: '+path.name)
    return path


def main():
    lead=json.loads((ROOT/'.local/ghost-comedy/lead-in-ready.json').read_text())
    video=json.loads((ROOT/'.local/ghost-comedy/music-video-ready.json').read_text())
    if not lead.get('ready_for_assembly') or video['status']!='ready':raise ValueError('Sources not ready')
    lead_path=verified(lead['final_path'],lead['sha256'])
    video_path=verified(video['path'],video['sha256'])
    spoken=RobinSkit(SPOKEN_ROOT)
    if not spoken.pcm:raise ValueError('Original spoken package invalid')
    out=ROOT/'.local/skills/robin-williams-performance';out.mkdir(parents=True,exist_ok=True)
    a,rate=sf.read(lead_path,always_2d=True)
    factor=math.gcd(rate,24000)
    lead_pcm=resample_poly(a.mean(axis=1),24000//factor,rate//factor)
    with tempfile.TemporaryDirectory() as td:
        decoded=Path(td)/'song.wav'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(video_path),'-vn','-ar','24000','-ac','1','-c:a','pcm_s16le',str(decoded)],check=True)
        song,sr=sf.read(decoded);assert sr==24000
    target_samples=round(video['duration_seconds']*24000)
    song=np.pad(song,(0,max(0,target_samples-len(song))))[:target_samples]
    song_rms=float(np.sqrt(np.mean(song*song)));song_peak=float(abs(song).max())
    song_gain=min(1.0,.62/max(song_peak,1e-9),.065/max(song_rms,1e-9))
    spoken_pcm=np.frombuffer(spoken.pcm,dtype='<i2').astype(np.float64)/32768
    gap1=np.zeros(round(.16*24000));gap2=np.zeros(round(.25*24000))
    lead_start=len(spoken_pcm)+len(gap1)
    song_start=lead_start+len(lead_pcm)+len(gap2)
    full=np.concatenate([spoken_pcm,gap1,lead_pcm,gap2,song*song_gain])
    if not np.isfinite(full).all() or abs(full).max()>=1 or len(full)>24000*120:raise ValueError('Invalid full audio')
    audio=out/'robin-full-v1.wav';sf.write(audio,full,24000,subtype='PCM_16')
    digest=hashlib.sha256(audio.read_bytes()).hexdigest()
    video_dest=out/(video['sha256']+'.mp4')
    shutil.copyfile(video_path,video_dest)
    captions=list(spoken.captions)
    captions.extend([[a+lead_start,b+lead_start,t] for a,b,t in caption_cues(lead['transcript'],len(lead_pcm))])
    lyrics=json.loads(Path(video['lyrics_timing_path']).read_text())
    for line in lyrics['lines']:
        start,end=round(line['start']*24000),round(line['end']*24000)
        captions.extend([[a+song_start+start,b+song_start+start,t] for a,b,t in caption_cues(line['text'],end-start)])
    (out/'captions.json').write_text(json.dumps({'audio_sha256':digest,'cues':captions},indent=2)+'\n')
    manifest={'version':1,'file':audio.name,'sha256':digest,'description':'Fictional Robin Williams tribute: original skit, Fish transition, then lyric music video',
      'video':{'file':video_dest.name,'sha256':video['sha256'],'start_samples':song_start,'duration_ms':video['duration_ms']},
      'duration_seconds':len(full)/24000,'sources':{'spoken_sha256':spoken.sha256,'lead_in':lead,'video':video},
      'processing':{'gaps_seconds':[.16,.25],'lead_resampling':'scipy resample_poly, mono24kHz','song_audio':'Decoded from delivered MP4; trimmed/padded to declared duration; mono24kHz','song_gain':song_gain,'song_gain_db':20*math.log10(song_gain),'spoken_bytes_preserved':True},
      'timeline':{'spoken_start_samples':0,'lead_start_samples':lead_start,'song_start_samples':song_start,'end_samples':len(full)}}
    temporary=out/'manifest.tmp';temporary.write_text(json.dumps(manifest,indent=2)+'\n');temporary.replace(out/'manifest.json')
    from server.robin_performance import RobinPerformance
    packaged=RobinPerformance(out)
    assert packaged.video and packaged.pcm and packaged.captions
    assert packaged.pcm[:len(spoken.pcm)]==spoken.pcm
    print(json.dumps({'root':str(out),**packaged.report(),'timeline':manifest['timeline'],'song_gain_db':manifest['processing']['song_gain_db']},indent=2))

if __name__=='__main__':main()
