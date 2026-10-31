#!/usr/bin/env python3
"""Install the owner-authorized October 26–31 morning preview workshop."""
import json
import os
from pathlib import Path
import plistlib
import subprocess

ROOT=Path(__file__).resolve().parents[1]
LABEL='org.facebot.experience-workshop'
DEST=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
domain=f'gui/{os.getuid()}'
WORK=ROOT/'.local/experience-workshop'
WORK.mkdir(parents=True,exist_ok=True)
value={'Label':LABEL,
       'ProgramArguments':[str(ROOT/'.venv/bin/python'),str(ROOT/'scripts/experience-workshop.py')],
       'WorkingDirectory':str(ROOT),
       'EnvironmentVariables':{'PATH':str(Path.home()/'.local/bin')+':/usr/bin:/bin:/usr/sbin:/sbin',
                               'PYTHONUNBUFFERED':'1'},
       'StartCalendarInterval':[{'Month':10,'Day':day,'Hour':9,'Minute':0} for day in range(26,32)],
       'ProcessType':'Background','LowPriorityIO':True,'Nice':10,
       'StandardOutPath':str(WORK/'scheduled.log'),'StandardErrorPath':str(WORK/'scheduled-error.log')}
DEST.parent.mkdir(parents=True,exist_ok=True)
existing=subprocess.run(['launchctl','print',domain+'/'+LABEL],capture_output=True)
if existing.returncode==0:
    raise SystemExit('Schedule already loaded; inspect it before changing an existing job')
with DEST.open('wb') as stream:plistlib.dump(value,stream)
DEST.chmod(0o600)
subprocess.run(['plutil','-lint',str(DEST)],check=True,capture_output=True)
subprocess.run(['launchctl','bootstrap',domain,str(DEST)],check=True,capture_output=True)
loaded=subprocess.run(['launchctl','print',domain+'/'+LABEL],check=True,capture_output=True,text=True)
receipt={'enabled':True,'label':LABEL,'path':str(DEST),'time_zone':'America/Los_Angeles',
         'dates':['2026-10-'+str(day) for day in range(26,32)],'local_time':'09:00',
         'deadline':'2026-10-31','mode':'draft_previews_only','loaded':True,
         'stops_model_work_after_deadline':True,'host_must_be_awake':True}
(WORK/'schedule.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
