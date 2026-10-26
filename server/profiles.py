"""Validated, process-start profiles. Content is operator-authored, never visitor input."""
from functools import lru_cache
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / 'contexts'
PRIVATE_ROOT = ROOT.parent / '.local'
IDENTIFIER = re.compile(r'[a-z][a-z0-9_-]{0,39}')
EXPRESSIONS = {'neutral', 'skeptical', 'surprised', 'scared', 'pleased'}


def _identifier(value):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError('Invalid profile identifier')
    return value


def _text(value, limit):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid profile text')


def _read(kind, name):
    _identifier(name)
    try:
        path = ROOT / kind / (name + '.json')
        if path.stat().st_size > 32768:
            raise ValueError('Profile exceeds size limit')
        value = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Cannot load selected profile') from error
    if not isinstance(value, dict) or value.get('id') != name:
        raise ValueError('Profile id mismatch')
    return value


def load(name):
    event = _read('events', name)
    if set(event) != {'id','character','instructions','facts','arrival','arrival_instruction','visual_reactions'}:
        raise ValueError('Invalid event fields')
    character = _read('characters', event['character'])
    if set(character) != {'id','defaults','instructions','voice'}:
        raise ValueError('Invalid character fields')
    if not isinstance(character['voice'], str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', character['voice']):
        raise ValueError('Invalid local voice identifier')
    _text(character['instructions'], 2000)
    # The character name is the only supported interpolation.
    template = character['instructions'].replace('{name}', '')
    if '{' in template or '}' in template:
        raise ValueError('Unsupported character placeholder')
    defaults = character['defaults']
    if not isinstance(defaults, dict) or set(defaults) != {'character_name','color_scheme','speech_rate'}:
        raise ValueError('Invalid character defaults')
    if not isinstance(defaults['character_name'], str) or not re.fullmatch(r'[A-Za-z][A-Za-z -]{0,23}', defaults['character_name']):
        raise ValueError('Invalid character name')
    if defaults['color_scheme'] not in ('mint','pumpkin','violet','ice') or type(defaults['speech_rate']) not in (int,float) or not .8 <= defaults['speech_rate'] <= 1.3:
        raise ValueError('Invalid character presentation')
    _text(event['instructions'], 1200)
    _text(event['arrival_instruction'], 300)
    facts = event['facts']
    if not isinstance(facts, list) or len(facts) > 40:
        raise ValueError('Invalid profile facts')
    for fact in facts:
        if not isinstance(fact, dict) or set(fact) != {'keywords','text'}:
            raise ValueError('Invalid fact fields')
        _text(fact['text'], 500)
        if not isinstance(fact['keywords'], list) or not 1 <= len(fact['keywords']) <= 12:
            raise ValueError('Invalid fact keywords')
        for keyword in fact['keywords']: _text(keyword, 80)
    reactions = event['visual_reactions']
    if not isinstance(reactions, dict) or len(reactions) > 60:
        raise ValueError('Invalid visual reactions')
    for label in reactions: _text(label, 80)
    for reaction in [event['arrival'], *reactions.values()]:
        if not isinstance(reaction, list) or len(reaction) != 2:
            raise ValueError('Invalid prepared reaction')
        _text(reaction[0], 160)
        if len(reaction[0].split()) > 12 or not isinstance(reaction[1], str) or reaction[1] not in EXPRESSIONS:
            raise ValueError('Invalid prepared speech or expression')
    return {**event, 'character_profile': character}


@lru_cache(maxsize=1)
def active():
    """Pin selection and file contents for the process lifetime; restart to switch."""
    return load(os.environ.get('FACEBOT_PROFILE', 'halloween'))


def private_path(filename):
    # Legacy paths belong exclusively to the original event. Never use them as
    # fallbacks for a second use case or inherit its recording consent.
    name = active()['id']
    directory = PRIVATE_ROOT if name == 'halloween' else PRIVATE_ROOT / 'profiles' / name
    return directory / filename
