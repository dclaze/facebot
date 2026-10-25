#!/usr/bin/env python3
"""Synthetic local generated PCM benchmark; excludes mic, endpointing and speaker."""
import argparse
import json
import time
import urllib.request
import mlx.core as mx
from mlx_audio.tts.utils import load_model
from benchmark_ollama import SYSTEM, PROMPTS, percentile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', default='qwen3.5:9b')
    p.add_argument('--tts', default='mlx-community/Kokoro-82M-bf16')
    p.add_argument('--samples', type=int, default=5)
    args = p.parse_args()
    start = time.monotonic()
    tts = load_model(args.tts)
    print(json.dumps({'tts_load_ms': (time.monotonic()-start)*1000}), flush=True)
    rows = []
    for i in range(args.samples + 1):
        start = time.monotonic()
        body = {'model':args.model, 'stream':True, 'think':False,
                'messages':[{'role':'system','content':SYSTEM},
                            {'role':'user','content':PROMPTS[i % len(PROMPTS)]}],
                'options':{'num_predict':48,'num_ctx':2048,'temperature':.7}}
        req = urllib.request.Request('http://127.0.0.1:11434/api/chat',
                    data=json.dumps(body).encode(), headers={'Content-Type':'application/json'})
        text = ''
        with urllib.request.urlopen(req, timeout=90) as response:
            for line in response:
                event = json.loads(line)
                if event.get('error'): raise RuntimeError(event['error'])
                text += event.get('message',{}).get('content','')
                if any(c in text for c in '.!?') or event.get('done'): break
        if not text.strip(): raise RuntimeError('Empty reply')
        llm_ms = (time.monotonic()-start)*1000
        first = None
        samples = 0
        for result in tts.generate(text=text, voice='af_heart', speed=1.05, lang_code='a'):
            mx.eval(result.audio)
            if first is None: first = (time.monotonic()-start)*1000
            samples += result.audio.size
        if not samples: raise RuntimeError('Empty generated audio')
        row={'phase':'initial' if i==0 else 'warm','llm_sentence_ms':llm_ms,
             'first_pcm_ms':first,'complete_pcm_ms':(time.monotonic()-start)*1000,
             'audio_samples':samples}
        rows.append(row)
        print(json.dumps(row),flush=True)
    summary={'evidence':'synthetic text to generated PCM; NOT physical spoken latency',
             'model':args.model,'tts':args.tts,'warm_samples':args.samples}
    for key in ('llm_sentence_ms','first_pcm_ms','complete_pcm_ms'):
        values=[r[key] for r in rows[1:]]
        summary[key]={'p50':percentile(values,.5),'p95':percentile(values,.95)}
    print(json.dumps(summary),flush=True)

if __name__=='__main__': main()
