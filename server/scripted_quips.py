"""Prepared Halloween banter; scheduling uses observations, never guesses actions."""
import json
import time
from pathlib import Path

from server.profiles import EXPRESSIONS

ROOT = Path(__file__).resolve().parents[1] / 'contexts' / 'quips'


def load_quips(profile):
    path = ROOT / (profile + '.json')
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if value.get('profile') != profile or set(value) != {'profile', 'groups'}:
        raise ValueError('Invalid quip pack')
    groups = value['groups']
    if not isinstance(groups, dict) or not {'arrival', 'general', 'candy'} <= groups.keys():
        raise ValueError('Missing quip groups')
    for group, lines in groups.items():
        if not isinstance(lines, list) or not 2 <= len(lines) <= 24:
            raise ValueError('A quip group needs 2–24 variations')
        for line in lines:
            if (not isinstance(line, list) or len(line) != 2
                    or not isinstance(line[0], str) or not line[0].strip()
                    or len(line[0]) > 160 or len(line[0].split()) > 24
                    or line[1] not in EXPRESSIONS):
                raise ValueError('Invalid prepared quip')
    return value


class QuipDirector:
    """One per application, so reconnects do not reset rotation or cooldowns.

    Face presence is only an audience cue. Object remarks require the vision
    service's already-confirmed, still-fresh labels. No visitor identity memory.
    """
    GAP = 30.
    CANDY_GAP = 150.
    LABEL_GAP = 180.

    def __init__(self, pack, clock=time.monotonic):
        self.pack, self.clock = pack, clock
        self.indices = {}
        self.last = float('-inf')
        self.last_candy = None
        self.categories = {}
        self.count = 0
        self.audience_since = None
        self.last_observation = None

    def take_event(self, state, vision=None, arrival=False):
        now, scene = self.clock(), state.scene
        fresh = (scene.received_at is not None and scene.faces
                 and (state.clock() - scene.received_at) * 1000 + scene.age_ms <= 750)
        if not fresh:
            self.audience_since = self.last_observation = None
            return None
        if self.last_observation is None or now - self.last_observation > .75:
            self.audience_since = now
        self.last_observation = now
        if (not fresh or scene.encounter.silenced or state.user_speaking
                or state.bot_speaking or state.response_pending
                or now - self.last < self.GAP
                or state.clock() - state.last_activity < 8.
                or state.clock() < state.quiet_until):
            return None
        groups = self.pack['groups']
        # Start the reminder clock only once an audience is actually observed.
        if self.last_candy is None:
            self.last_candy = now - self.CANDY_GAP + 45.
        category = None
        if now - self.last_candy >= self.CANDY_GAP:
            category = 'candy'
        elif arrival:
            category = 'arrival'
        elif vision and vision.fresh():
            labels = [label for label in vision.labels if label in groups
                      and now - self.categories.get(label, float('-inf')) >= self.LABEL_GAP]
            if labels:
                category = min(labels, key=lambda label: self.categories.get(label, float('-inf')))
        if category is None:
            # Allow a settled audience before the first timer-driven remark.
            if now - self.audience_since < 8.:
                return None
            category = 'general'
        lines = groups[category]
        index = self.indices.get(category, 0)
        text, expression = lines[index % len(lines)]
        self.indices[category] = index + 1
        self.last = self.categories[category] = now
        if category == 'candy':
            self.last_candy = now
        self.count += 1
        return {'kind': 'prepared_quip', 'category': category,
                'text': text, 'expression': expression,
                'expires_at': state.clock() + (750 - scene.age_ms) / 1000. - (state.clock() - scene.received_at)}

    def report(self):
        return {'enabled': True, 'profile': self.pack['profile'],
                'lines': sum(len(x) for x in self.pack['groups'].values()),
                'minimum_gap_seconds': self.GAP, 'candy_gap_seconds': self.CANDY_GAP,
                'planned_quips': max(0, self.count)}
