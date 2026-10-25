#!/usr/bin/env python3
"""Restart only the local Facebot server; leave native face/camera apps running.

Uses ignored local pairing/PID files. Does not run ADB, reinstall an app, change
permissions or record visitor media. Voice pauses until the app reconnects.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',default='qwen2.5:1.5b')
    parser.add_argument('--speech-rate',type=float,default=1.12)
    args=parser.parse_args()
    if not .8<=args.speech_rate<=1.3: parser.error('Speech rate must be0.8–1.3')
    if args.model not in ('qwen2.5:1.5b','qwen3.5:9b','qwen3:1.7b'):
        parser.error('Model must be supported by server configuration')
    root=Path(__file__).resolve().parents[1]
    local=root/'.local'
    pid_file=local/'live-server.pid'
    token=(local/'pairing-token').read_text().strip()
    if len(token)<24: raise RuntimeError('Valid private pairing token required')
    pid=int(pid_file.read_text())
    command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
    if '-m server.app' not in command: raise RuntimeError('PID does not identify Facebot server; no process stopped')
    os.kill(pid,signal.SIGTERM)
    for _ in range(80):
        try:os.kill(pid,0)
        except ProcessLookupError:break
        time.sleep(.1)
    else:raise RuntimeError('Previous server remains live; not starting a duplicate')
    env=os.environ.copy()
    env.update(FACEBOT_TOKEN=token,FACEBOT_LLM=args.model,FACEBOT_SPEECH_RATE=str(args.speech_rate))
    with (local/'live-server.log').open('ab') as log:
        process=subprocess.Popen([str(root/'.venv/bin/python'),'-m','server.app'],cwd=root,
            env=env,stdout=log,stderr=log,start_new_session=True)
    pid_file.write_text(str(process.pid))
    for _ in range(90):
        if process.poll() is not None:raise RuntimeError('Updated server exited; native face was not closed')
        try:
            with urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=1) as response:
                if json.load(response).get('status')=='ready':
                    print('Server ready. Native apps were left running; verify voice reconnection.')
                    return
        except (OSError,ValueError):pass
        time.sleep(.5)
    raise RuntimeError('Readiness observation timed out; inspect the saved PID before retrying')

if __name__=='__main__':main()
