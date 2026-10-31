"""Versioned interaction previews and owner review records; never runtime activation."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from datetime import datetime, timezone
from server.profiles import active, private_path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT/'contexts/experiences.json'
LOCK = threading.RLock()
MIME = {'mp4':'video/mp4','wav':'audio/wav','png':'image/png'}
SLUG = re.compile(r'^[a-z][a-z0-9-]{0,63}$')


def atomic_json(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='.draft-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def entries():
    data=json.loads(CATALOG.read_text())
    if data.get('version')!=1:raise ValueError('Unknown experience catalog')
    items=list(data['experiences'])
    # Generated candidates are separate manifests; no unattended core-file edits.
    for path in sorted((ROOT/'content/experiences/candidates').glob('*/manifest.json')):
        candidate=json.loads(path.read_text())
        previous=next((x for x in items if x['id']==candidate['id']),None)
        if path.parent.name!=candidate['id']:raise ValueError('Candidate folder mismatch')
        if previous:
            if candidate['version']<=previous['version']:raise ValueError('Candidate version must advance')
            candidate={**previous,**candidate}
            items.remove(previous)
        items.append(candidate)
    seen=set()
    for item in items:
        if not SLUG.fullmatch(item['id']) or item['id'] in seen:raise ValueError('Duplicate/invalid experience id')
        if type(item['version']) is not int or item['version']<1:raise ValueError('Invalid version')
        if item['availability'] not in ('draft','preview'):raise ValueError('Drafts cannot activate runtime')
        seen.add(item['id'])
    return items


def asset_path(item, kind):
    asset=item.get('assets',{}).get(kind)
    if not asset:return None
    path=(ROOT/asset['path']).resolve()
    allowed=(ROOT/'content/experiences').resolve()
    if not path.is_relative_to(allowed) or path.suffix.lstrip('.') not in MIME:return None
    if not path.is_file():return None
    if hashlib.sha256(path.read_bytes()).hexdigest()!=asset['sha256']:return None
    return path


def revision_key(item):
    # Full manifest digest binds approval to content, assets and version.
    return hashlib.sha256(json.dumps(item,sort_keys=True).encode()).hexdigest()


def review_file():
    return private_path('experience-reviews.json')


def read_reviews():
    try:return json.loads(review_file().read_text())
    except FileNotFoundError:return {'revision':0,'items':{},'history':[]}


def snapshot():
    reviews=read_reviews()
    result=[]
    for item in entries():
        if active()['id'] not in item.get('event_ids',[]):continue
        key=revision_key(item)
        review=reviews['items'].get(item['id'],{})
        current=review if review.get('revision_key')==key else {}
        assets={kind:'/api/experiences/'+item['id']+'/media/'+kind+'?revision='+key
                for kind in item.get('assets',{}) if asset_path(item,kind)}
        result.append({k:v for k,v in item.items() if k not in ('assets','contract','recipe')} |
                      {'kind':'experience','configured':False,'revision_key':key,
                       'media':assets,'preview_available':'video' in assets,
                       'review':current,'previous_feedback':review.get('note','') if not current else '',
                       'review_revision':reviews['revision']})
    return result


def review(skill_id, payload):
    if not isinstance(payload,dict) or set(payload)!={'action','note','revision_key','review_revision'}:
        raise ValueError('Invalid review fields')
    if payload['action'] not in ('request_changes','approve_preview'):raise ValueError('Unknown review action')
    if not isinstance(payload['note'],str) or len(payload['note'])>2000:raise ValueError('Feedback must be at most 2000 characters')
    note=payload['note'].strip()
    if payload['action']=='request_changes' and not note:raise ValueError('Describe the change you want')
    if type(payload['review_revision']) is not int:raise ValueError('Invalid review revision')
    with LOCK:
        item=next((x for x in entries() if x['id']==skill_id and active()['id'] in x.get('event_ids',[])),None)
        if item is None:raise LookupError('Unknown experience')
        state=read_reviews()
        if payload['revision_key']!=revision_key(item) or payload['review_revision']!=state['revision']:
            raise RuntimeError('This preview or feedback changed. Reload before reviewing.')
        if payload['action']=='approve_preview' and not asset_path(item,'video'):
            raise ValueError('A playable preview is required before approval')
        saved={'status':'approved' if payload['action']=='approve_preview' else 'changes_requested',
               'note':note,'version':item['version'],'revision_key':revision_key(item),
               'updated_at':datetime.now(timezone.utc).isoformat()}
        state['items'][skill_id]=saved
        state['revision']+=1
        state['history'].append({'id':skill_id,**saved})
        atomic_json(review_file(),state)
        return saved


def report():
    items=snapshot()
    queue=[]
    for item in items:
        if item['review'].get('status')=='approved':continue
        if item['review'].get('status')=='changes_requested':
            priority,reason=0,'Owner requested changes'
        elif not item['preview_available']:
            priority,reason=1,'Needs a playable preview'
        else:continue
        queue.append({'id':item['id'],'name':item['name'],'version':item['version'],
                      'revision_key':item['revision_key'],'priority':priority,'reason':reason,
                      'feedback':item['review'].get('note','')})
    queue.sort(key=lambda x:(x['priority'],x['id']))
    status_path=ROOT/'.local/experience-workshop/status.json'
    try:automation=json.loads(status_path.read_text())
    except FileNotFoundError:automation={'state':'not_started'}
    schedule_path=ROOT/'.local/experience-workshop/schedule.json'
    try:schedule=json.loads(schedule_path.read_text())
    except FileNotFoundError:schedule={'enabled':False}
    return {'schedule':schedule,'deadline':'2026-10-31','mode':'drafts_and_previews_only','queue':queue,
            'ready_for_review':sum(x['preview_available'] and x['review'].get('status')!='approved' for x in items),
            'approved_previews':sum(x['review'].get('status')=='approved' for x in items),
            'automation':automation}
