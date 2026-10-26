#!/usr/bin/env python3
"""Apply the owner's v3 ending removal by reusing the accepted performance."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'.local/laughing-contest-tools')]
import imageio_ffmpeg
from server import experiences

def main():
    item=next(x for x in experiences.entries() if x['id']=='laughing-contest')
    if item['version']!=3:raise RuntimeError('This edit applies only to reviewed v3')
    reviewed=experiences.read_reviews()['items']['laughing-contest']
    before=experiences.revision_key(item)
    if reviewed['revision_key']!=before:raise RuntimeError('Review is stale')
    source=experiences.asset_path(item,'video');output=ROOT/'content/experiences/candidates/laughing-contest/v4'
    output.mkdir(parents=True,exist_ok=False)
    ff=imageio_ffmpeg.get_ffmpeg_exe()
    # Cut before the closing speech/caption; preserve the full 5.116s laugh and restored face.
    subprocess.run([ff,'-v','error','-i',str(source),'-filter_complex',
        '[0:v]trim=end=14.466667,setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=0.8[v];[0:a]atrim=end=14.466667,asetpts=PTS-STARTPTS,apad=pad_dur=0.8[a]',
        '-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','160k','-movflags','+faststart',str(output/'demo.mp4')],check=True)
    subprocess.run([ff,'-v','error','-i',str(output/'demo.mp4'),'-f','null','-'],check=True)
    subprocess.run([ff,'-v','error','-ss','14.2','-i',str(output/'demo.mp4'),'-frames:v','1',str(output/'final-frame.png')],check=True)
    for kind,name in [('audio','laugh.wav'),('poster','poster.png')]:shutil.copyfile(experiences.asset_path(item,kind),output/name)
    base=source.parent
    shutil.copyfile(base/'CREDITS.md',output/'CREDITS.md')
    receipt=json.loads((base/'source-receipt.json').read_text())
    receipt.update(version=4,edit='Remove Okay, you win closing speech and caption; hold restored face silently',
                   source_sha256=item['assets']['video']['sha256'],duration_seconds=15.266667,
                   timeline=[x for x in receipt['timeline'] if x['key']!='end'],full_decode=True,
                   owner_feedback=reviewed['note'],evidence='Edited synthetic rehearsal, not runtime activation')
    receipt['movie_sha256']=hashlib.sha256((output/'demo.mp4').read_bytes()).hexdigest()
    experiences.atomic_json(output/'verification.json',receipt)
    if experiences.read_reviews()['items']['laughing-contest']!=reviewed:raise RuntimeError('Feedback changed; candidate not published')
    candidate={**item,'version':4,'review_summary':'Closing line removed; accepted laugh and full-duration eyes preserved.','assets':{}}
    for kind,name in [('video','demo.mp4'),('audio','laugh.wav'),('poster','poster.png')]:
        path=output/name;candidate['assets'][kind]={'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    experiences.atomic_json(output.parent/'manifest.json',candidate)
    experiences.atomic_json(ROOT/'.local/experience-workshop/status.json',{'state':'ready','message':'Laughing contest v4 is ready: closing line removed.','skill_id':'laughing-contest','version':4})
    print(json.dumps({'version':4,'video':str(output/'demo.mp4'),'full_decode':True}))
if __name__=='__main__':main()
