"""One atomic, hot-read source for runtime knobs shared by UI and commands."""
import json
import os
import re
from pathlib import Path
import tempfile
from server.profiles import active, private_path

PATH = Path(__file__).resolve().parents[1] / '.local/runtime-settings.json'
DEFAULTS = dict(active()['character_profile']['defaults'])
PALETTES = {
    'mint': ['#CEFFEE', '#5EEBB8', '#09362F', '#0C312B', '#030F0E'],
    'pumpkin': ['#FFF0D0', '#FFAD49', '#59300F', '#402710', '#160D04'],
    'violet': ['#F0E0FF', '#C697FF', '#392052', '#2D1C40', '#100A18'],
    'ice': ['#E5F7FF', '#72CFFF', '#153D54', '#102D40', '#050F18'],
}


def validate(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULTS) or 'speech_rate' not in value:
        raise ValueError('Invalid runtime settings fields')
    value = {**active()['character_profile']['defaults'], **value}  # Migrate existing speed-only files.
    rate = value['speech_rate']
    if type(rate) not in (int, float) or not .8 <= rate <= 1.3:
        raise ValueError('Speech rate must be between 0.8 and 1.3')
    name = value['character_name']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z -]{0,23}', name.strip()):
        raise ValueError('Character name must be 1–24 letters, spaces or hyphens')
    if not isinstance(value['color_scheme'], str) or value['color_scheme'] not in PALETTES:
        raise ValueError('Choose Mint, Pumpkin, Violet or Ice')
    return {'speech_rate': round(float(rate), 2), 'character_name': name.strip(), 'color_scheme': value['color_scheme']}


def presentation():
    value = read()
    return {**value, 'colors': PALETTES[value['color_scheme']]}


def read(path=None):
    path = private_path("runtime-settings.json") if path is None else path
    try:
        return validate(json.loads(path.read_text()))
    except (OSError, ValueError, TypeError):
        return dict(active()["character_profile"]["defaults"])


def save(value, path=None):
    path = private_path("runtime-settings.json") if path is None else path
    value = validate(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.settings-')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f)
            f.flush(); os.fsync(f.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    return value
