#!/usr/bin/env python3
"""Cheap feedback watcher: no model calls or catalog scans while feedback is unchanged."""
from datetime import datetime
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from server import experiences
from zoneinfo import ZoneInfo
WORK=ROOT/'.local/experience-workshop'
DEADLINE='2026-10-31'

def fingerprint(path):
    try:
        data=json.loads(path.read_text())['items']
        # Repeated clicks with identical direction are one request.
        return json.dumps({key:{k:v.get(k) for k in ('status','note','revision_key')}
                           for key,v in data.items()},sort_keys=True)
    except FileNotFoundError:return '{}'

class Watcher:
    def __init__(self,path,process):
        self.path=path;self.process=process;self.stamp=None;self.seen=None
    def tick(self):
        try:s=self.path.stat();stamp=(s.st_mtime_ns,s.st_size)
        except FileNotFoundError:stamp=(0,0)
        if stamp==self.stamp:return False
        current=fingerprint(self.path)
        self.stamp=stamp
        if current==self.seen:return False
        self.process()
        self.seen=current
        return True

def process_feedback():
    spec=importlib.util.spec_from_file_location('workshop',ROOT/'scripts/experience-workshop.py')
    worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    # Drain only actionable owner feedback, never generate unrelated missing previews.
    while True:
        attempts_path=WORK/'attempts.json'
        attempts=json.loads(attempts_path.read_text()) if attempts_path.exists() else {}
        queue=[x for x in experiences.report()['queue'] if x['priority']==0]
        if not worker.eligible(queue,attempts):return
        result=subprocess.run([sys.executable,str(ROOT/'scripts/experience-workshop.py'),'--feedback-only'],
                              cwd=ROOT,capture_output=True,text=True,timeout=600)
        try:outcome=json.loads(result.stdout)
        except ValueError:raise RuntimeError('Revision worker exited without a valid result: '+result.stderr[-300:])
        print(json.dumps(outcome),flush=True)
        if outcome.get('state')=='busy':
            time.sleep(5);continue
        if outcome.get('state') not in ('ready','needs_author','needs_attention'):return

def main():
    WORK.mkdir(parents=True,exist_ok=True)
    with (WORK/'feedback-watch.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        watcher=Watcher(experiences.review_file(),process_feedback)
        while datetime.now(ZoneInfo('America/Los_Angeles')).date().isoformat()<=DEADLINE:
            try:watcher.tick()
            except Exception as exc:
                experiences.atomic_json(WORK/'status.json',{'state':'needs_attention',
                    'message':'Feedback is saved; immediate processing needs attention.',
                    'detail':str(exc)[:400],'updated_at':datetime.now().astimezone().isoformat()})
                # Do not spin on an unchanged failing request.
                watcher.seen=fingerprint(watcher.path)
                print(str(exc),flush=True)
            time.sleep(2)

if __name__=='__main__':main()
