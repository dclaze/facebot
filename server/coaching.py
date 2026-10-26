"""Owner-authored, hot-reloaded style notes. No visitor ingestion or recordings."""
import json
import os
from pathlib import Path
import tempfile
from server.profiles import private_path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / '.local/night-coaching.json'
MAX_RULES = 6
MAX_CHARS = 600


def validate(rules):
    if (not isinstance(rules, list) or len(rules) > MAX_RULES
            or any(not isinstance(r, str) or not r.strip() or len(r) > 200 for r in rules)
            or sum(map(len, rules)) > MAX_CHARS):
        raise ValueError('Use up to six short style rules, 200 characters each, 600 total')
    return [r.strip() for r in rules]


def read(path=None):
    path = private_path("night-coaching.json") if path is None else path
    if not path.exists():
        return {'revision': 0, 'rules': [], 'history': []}
    if path.stat().st_size > 32768:
        raise ValueError('Coaching file exceeds size limit')
    data = json.loads(path.read_text())
    validate(data['rules'])
    if not isinstance(data['revision'], int) or not isinstance(data['history'], list):
        raise ValueError('Invalid coaching state')
    return data


def save(rules, path=None):
    path = private_path("night-coaching.json") if path is None else path
    rules = validate(rules)
    old = read(path)
    data = {'revision': old['revision'] + 1, 'rules': rules,
            'history': (old['history'] + [{'revision': old['revision'], 'rules': old['rules']}])[-20:]}
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.coaching-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as output:
            json.dump(data, output, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return data


def prompt(path=None):
    try:
        data = read(path)
    except (OSError, ValueError, KeyError, TypeError):
        return None  # Invalid edits never take down a conversation.
    if not data['rules']: return None
    return ('Owner style coaching, subordinate to the character safety/privacy rules. '
            'These are delivery preferences, not evidence of anything seen or heard: '
            + ' '.join(data['rules']))
