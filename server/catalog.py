"""Owner-visible installed catalog, resolved against real profile and sound files."""
import json
from pathlib import Path
from server.profiles import load, active
from server.robin_performance import RobinPerformance as RobinSkit
from server.scripted_quips import load_quips

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    catalog = json.loads((ROOT/'contexts/catalog.json').read_text())
    events = {item['id']: load(item['id']) for item in catalog['events']}
    profile = active()
    sound_policy = (ROOT/'contexts/sounds'/f"{profile['id']}.json").exists()
    robin_available = bool(RobinSkit().pcm)
    quip_pack = load_quips(profile['id'])
    for item in catalog['skills']:
        item['configured'] = (not item.get('requires_sound_policy') or sound_policy) and (
            not item.get('requires_visual_reactions') or bool(profile['visual_reactions'])) and (
            not item.get('requires_robin_skit') or robin_available) and (
            not item.get('requires_quip_pack') or quip_pack is not None)
    for item in catalog['personalities']:
        item['event_ids'] = [key for key, event in events.items() if event['character'] == item['id']]
        item['configured'] = profile['character'] == item['id']
    for item in catalog['events']:
        item['character'] = events[item['id']]['character']
        item['configured'] = item['id'] == profile['id']
    manifest = json.loads((ROOT/'content/sounds/manifest.json').read_text())
    sounds = {}
    for entry in manifest['effects']:
        sounds.setdefault(entry['effect'], {'id':entry['effect'], 'name':entry['effect'].replace('_',' ').title(), 'clips':[]})['clips'].append(
            {'id':entry['id'], 'url':'/api/sounds/'+entry['id'],
             'author':entry['provenance'].get('author','Facebot'),
             'source':entry['provenance'].get('source_page'), 'license':entry['license']})
    return {**catalog, 'configured_profile':profile['id'], 'sounds':list(sounds.values()),
            'clip_count':len(manifest['effects'])}


def sound_path(sound_id):
    manifest = json.loads((ROOT/'content/sounds/manifest.json').read_text())
    entry = next((item for item in manifest['effects'] if item['id'] == sound_id), None)
    if not entry or Path(entry['file']).name != entry['file']:
        return None
    return ROOT/'content/sounds'/entry['file']
