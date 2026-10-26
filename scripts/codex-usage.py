#!/usr/bin/env python3
"""Read account quota without inference; aggregate known nested run receipts."""
import datetime
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def quota():
    p = subprocess.Popen(['codex','--no-daemon','app-server','--stdio'], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
    def send(value):
        p.stdin.write((json.dumps(value)+'\n').encode()); p.stdin.flush()
    send({'id':1,'method':'initialize','params':{'clientInfo':{'name':'facebot_budget','version':'1.0'}}})
    s = selectors.DefaultSelector(); s.register(p.stdout,selectors.EVENT_READ)
    end = time.monotonic()+12; buf = b''
    try:
        while time.monotonic()<end:
            if not s.select(max(0,end-time.monotonic())): break
            block=os.read(p.stdout.fileno(),65536)
            if not block: break
            buf+=block
            while b'\n' in buf:
                line,buf=buf.split(b'\n',1); d=json.loads(line)
                if d.get('id')==1:
                    send({'id':2,'method':'account/rateLimits/read','params':{}})
                if d.get('id')==2:
                    return d['result']['rateLimits']['primary']['usedPercent']
        raise RuntimeError('Quota unavailable; do not invent a percentage')
    finally:
        p.terminate();p.wait(timeout=5);s.close()


def main():
    records=[]
    for filename,kind in [('codex-first-probe.json','runtime_probe'),('codex-lean-probe.json','runtime_probe'),
                          ('interaction-triage-events.jsonl','development')]:
        path=ROOT/'.local'/filename
        if not path.exists(): continue
        events=(json.loads(path.read_text())['events'] if path.suffix=='.json'
                else [json.loads(line) for line in path.read_text().splitlines() if line.startswith('{')])
        for e in events:
            if e.get('type')=='turn.completed':
                records.append({'source':filename,'kind':kind,**e['usage']})
    used=quota()
    value={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'remaining_percent':100-used,'shared_used_percent':used,
           'shared_change_percentage_points_since_baseline':used-28,
           'facebot_attributable_percent':None,
           'attribution':'Shared change includes other chats; no per-run percentage is exposed.',
           'calls':len(records),'records':records,
           **{k:sum(r.get(k,0) for r in records) for k in ('input_tokens','cached_input_tokens','output_tokens')}}
    path=ROOT/'.local/codex-usage.json'
    path.write_text(json.dumps(value,indent=2))
    with (ROOT/'.local/codex-usage-history.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
    print(json.dumps({k:v for k,v in value.items() if k!='records'},indent=2))


if __name__=='__main__':main()
