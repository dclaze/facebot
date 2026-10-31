#!/usr/bin/env python3
"""Optional local CLAP recognition screen; no human listening/quality claim."""
import json, os, time
from pathlib import Path
os.environ['TOKENIZERS_PARALLELISM']='false'
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
import torch
from transformers import ClapModel, ClapProcessor
model_id='laion/clap-htsat-unfused'
revision='8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a'
np.random.seed(0);torch.manual_seed(0)
print(json.dumps({'stage':'loading','model':model_id,'revision':revision}),flush=True)
torch.set_num_threads(2)
processor=ClapProcessor.from_pretrained(model_id,revision=revision)
model=ClapModel.from_pretrained(model_id,revision=revision,use_safetensors=False).eval()
labels={
'ghost':'A spooky ghost moaning and howling.', 'ghost_laugh':'A witch cackling with evil laughter.',
'creaky_door':'A wooden door creaking.', 'chains':'Metal chains rattling.', 'magic':'A magical sparkling chime.',
'cauldron':'Liquid bubbling in a pot.', 'bat':'Wings flapping.', 'monster':'A monster growling.',
'wolf':'A wolf howling.', 'owl':'An owl hooting.', 'cat':'A cat meowing.', 'dog':'A dog barking.',
'frog':'A frog croaking.', 'cricket':'Crickets chirping.', 'fart':'A funny fart sound.', 'burp':'A person burping.',
'boing':'A cartoon spring boing sound.', 'slide_whistle':'A slide whistle sliding down.',
'rimshot':'A comedy drum sting, ba dum tss.', 'sad_trombone':'A sad trombone wah wah sound.',
'squeak':'A rubber toy squeaking.', 'pop':'A popping bubble.', 'drumroll':'A snare drum roll.',
'knock':'Knocking on a wooden door.', 'footsteps':'Footsteps walking.', 'heartbeat':'A heartbeat thumping.',
'bell':'A bell ringing.', 'gong':'A gong ringing.', 'wind':'Wind blowing.', 'rain':'Rain falling.',
'thunder':'Thunder rumbling.', 'splash':'A splash of water.', 'whoosh':'A fast swooshing sound.',
'robot':'Electronic robot beeps.', 'laser':'A science fiction laser zap.', 'ufo':'A science fiction UFO sound.',
'level_up':'A video game level up sound.', 'coin':'An arcade coin pickup sound.',
'victory':'A short victory fanfare.', 'ticking':'A clock ticking.'}
keys=list(labels)
with torch.inference_mode():
 text=model.get_text_features(**processor(text=list(labels.values()),return_tensors='pt',padding=True))
 if not isinstance(text,torch.Tensor):text=text.pooler_output
 text=torch.nn.functional.normalize(text,dim=-1)
rows=[]
manifest=json.loads(Path('content/sounds/manifest.json').read_text())
for entry in manifest['effects']:
 data,rate=sf.read('content/sounds/'+entry['file'],dtype='float32')
 data=resample_poly(data,48000,rate)
 with torch.inference_mode():
  audio=model.get_audio_features(**processor(audio=data,sampling_rate=48000,return_tensors='pt'))
  if not isinstance(audio,torch.Tensor):audio=audio.pooler_output
  scores=(torch.nn.functional.normalize(audio,dim=-1)@text.T).flatten().tolist()
 order=sorted(range(len(keys)),key=lambda i:scores[i],reverse=True)
 row={'id':entry['id'],'sha256':entry['sha256'],'expected':entry['effect'],'rank':order.index(keys.index(entry['effect']))+1,
      'top':[{ 'effect':keys[i],'similarity':round(scores[i],4)} for i in order[:3]]}
 rows.append(row);print(json.dumps(row),flush=True)
Path('content/sounds/recognition-screen.json').write_text(json.dumps({'model':model_id,'revision':revision,'evidence':'Local CLAP zero-shot similarity; not a human listening or comedy-quality score.','rows':rows},indent=2))
