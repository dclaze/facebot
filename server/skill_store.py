"""Free, bundled skill packs. No downloaded code, payment or inferred entitlement."""
import json
import threading
from pathlib import Path

from server.experiences import atomic_json
from server.profiles import private_path

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.RLock()
PACKS = (
    dict(id='candy-host', name='The candy host', category='Essential', version=1,
         description='A warm welcome, one-piece reminders, and a graceful goodbye.',
         example='Trick or treat!', reply='Happy Halloween! One piece, please. Enjoy!', required=True),
    dict(id='quick-jokes', name='Dead funny', category='Comedy', version=1,
         description='Tiny jokes with a quick payoff. No long speeches at the candy tray.',
         example='Tell me a joke', reply='I have no body to go with.', required=False),
    dict(id='playful-scares', name='Little boo', category='Play', version=1,
         description='An invited, playful surprise. Friendly enough for the front porch.',
         example='Scare me', reply='Boo! Sorry. Still in ghost training.', required=False),
    dict(id='laugh-challenge', name='Last laugh', category='Game', version=1,
         description='You go first. Then give the ghost a turn for a theatrical cackle.',
         example="Let's have a laughing contest", reply='You laugh first. Say your turn when ready.', required=False),
    dict(id='sound-effects', name='Spooky soundboard', category='Sound', version=1,
         description='Ghosts, drumrolls and comic punctuation from installed local sounds.',
         example='Make a ghost sound', reply=None, required=False),
    dict(id='robin-williams', name='The guest performance', category='Local extra', version=1,
         description='Your separately supplied performance, with synchronized lyrics and video.',
         example='Is Robin Williams there?', reply=None, required=False, local_only=True),
)
BY_ID = {item['id']: item for item in PACKS}


def state_path():
    return private_path('skill-packs.json')


def read_state():
    try:
        value = json.loads(state_path().read_text())
        if (not isinstance(value, dict) or type(value.get('revision')) is not int or value['revision'] < 0
                or not isinstance(value.get('packs'), dict)):
            raise ValueError('Invalid pack state')
        for key, pack in value['packs'].items():
            if key not in BY_ID or not isinstance(pack, dict) or set(pack) != {'enabled', 'version'}:
                raise ValueError('Invalid pack entry')
            if type(pack['enabled']) is not bool or type(pack['version']) is not int or pack['version'] < 1:
                raise ValueError('Invalid pack values')
        return value
    except FileNotFoundError:
        return {'revision': 0, 'packs': {}}


def enabled(pack_id):
    if pack_id not in BY_ID:
        return False
    if BY_ID[pack_id]['required']:
        return True
    try:
        return read_state()['packs'].get(pack_id, {}).get('enabled', True)
    except (OSError, ValueError, TypeError):
        # Corrupt optional preferences must not bypass the owner's disabled pack.
        return False


def availability(pack_id):
    if pack_id == 'sound-effects':
        return (ROOT/'content/sounds/manifest.json').is_file()
    if pack_id == 'robin-williams':
        from server.robin_performance import RobinPerformance
        return bool(RobinPerformance().pcm)
    if pack_id == 'laugh-challenge':
        return (ROOT/'content/kiosk/manifest.json').is_file()
    return True


def snapshot():
    try:
        state, error = read_state(), None
    except (OSError, ValueError, TypeError):
        state, error = {'revision': 0, 'packs': {}}, 'Skill settings need repair. Optional skills are paused.'
    packs = []
    for definition in PACKS:
        saved = state['packs'].get(definition['id'], {})
        present = availability(definition['id'])
        current = saved.get('version', definition['version']) if present else None
        packs.append({**definition, 'available': present,
                      'enabled': present and enabled(definition['id']), 'price': 'Free',
                      'installed_version': current,
                      'update_available': current is not None and current < definition['version']})
    return {'revision': state['revision'], 'packs': packs, 'error': error,
            'payments_enabled': False, 'delivery': 'bundled-local',
            'notice': 'Free packs for this release. Paid upgrades are not available.'}


def update(pack_id, payload):
    if pack_id not in BY_ID:
        raise LookupError('Unknown skill pack')
    if (not isinstance(payload, dict) or set(payload) != {'enabled', 'revision'}
            or type(payload['enabled']) is not bool or type(payload['revision']) is not int):
        raise ValueError('Use enabled and the current revision')
    if BY_ID[pack_id]['required'] and not payload['enabled']:
        raise ValueError('The candy host is included in every kiosk')
    if payload['enabled'] and not availability(pack_id):
        raise ValueError('This pack needs its local assets before activation')
    with LOCK:
        state = read_state()
        if payload['revision'] != state['revision']:
            raise RuntimeError('Skills changed elsewhere. Refresh and try again.')
        state['packs'][pack_id] = {'enabled': payload['enabled'], 'version': BY_ID[pack_id]['version']}
        state['revision'] += 1
        atomic_json(state_path(), state)
    return snapshot()
