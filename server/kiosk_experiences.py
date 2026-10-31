"""Bounded, explicit visitor requests for the candy-tray starter pack.

No LLM, visitor identity, laugh detector or candy-taking inference. Session game
state deliberately does not survive a disconnected visitor connection.
"""
import json
from pathlib import Path
import re

from server.profiles import EXPRESSIONS

PACK = Path(__file__).resolve().parents[1] / 'contexts/kiosk/halloween.json'


def load_pack():
    pack = json.loads(PACK.read_text())
    if pack['version'] != 1 or pack['id'] != 'halloween-candy-tray':
        raise ValueError('Unsupported kiosk pack')
    for lines in pack['replies'].values():
        if not lines:
            raise ValueError('Empty kiosk group')
        for text, expression in lines:
            if not 1 <= len(text.split()) <= 10 or expression not in EXPRESSIONS:
                raise ValueError('Invalid short kiosk reply')
    return pack


def normalize(text, name='Boo'):
    if not isinstance(text, str) or not text.strip() or len(text) > 180:
        return ''
    text = ' '.join(re.sub(r'[,!?.]', ' ', text.casefold()).split())
    text = re.sub(r"^(?:(?:hey|hi) )?" + re.escape(name.casefold()) + r' ', '', text)
    text = re.sub(r'^please | please$', '', text)
    return text


class KioskDirector:
    """Exact phrases only: quotations, negation and noisy fragments fall through."""
    def __init__(self, state, name_provider=lambda: 'Boo', enabled=lambda pack: True):
        self.state, self.name_provider, self.enabled = state, name_provider, enabled
        self.pack = load_pack()
        self.indices = {}
        self.control_epoch = state.control_epoch
        self.game_until = None
        self.game_last = float('-inf')
        self.last_reply = float('-inf')

    def reset(self):
        self.game_until = None

    def reply(self, category):
        lines = self.pack['replies'][category]
        index = self.indices.get(category, 0)
        self.indices[category] = index + 1
        text, expression = lines[index % len(lines)]
        self.last_reply = self.state.clock()
        return {'category': category, 'text': text, 'expression': expression}

    def route(self, text):
        if self.control_epoch != self.state.control_epoch:
            self.reset()
            self.control_epoch = self.state.control_epoch
        if self.state.scene.encounter.silenced:
            self.reset()
            return None
        command = normalize(text, self.name_provider())
        now = self.state.clock()
        expired = self.game_until is not None and now >= self.game_until
        if expired:
            self.reset()
        if command in ('cancel game', 'stop game', 'stop the game', 'end game', 'no thanks'):
            self.reset()
            return {'category': 'game_cancel', 'text': None, 'expression': 'neutral'}
        game_before = self.game_until, self.game_last
        category = None
        if command in ('your turn', "it's your turn", 'you go', 'i am done', "i'm done"):
            category = 'cackle' if self.game_until is not None else 'game_expired'
            self.reset()
        elif command in ('laughing game', 'laughing contest', "let's play a laughing game",
                         'play a laughing game', 'let us play a laughing game',
                         'can we have a laughing contest', "let's have a laughing contest",
                         'let us have a laughing contest', 'can we play a laughing game'):
            if self.game_until is not None:
                category = 'game_wait'
            elif now - self.game_last < 60:
                category = 'game_cooldown'
            else:
                self.game_until = now + 20
                self.game_last = now
                category = 'game_start'
        elif re.fullmatch(r'(?:(?:can|could|would) you )?(?:tell (?:me|us) (?:a|another) (?:joke|dad joke)|make (?:me|us) laugh)', command):
            category = 'joke'
        elif command in ('scare me', 'give me a little scare', 'give me a scare', 'can you scare me'):
            category = 'scare'
        elif command in ('hello', 'hi', 'hey', 'happy halloween', 'trick or treat'):
            category = 'greeting'
        elif command in ('thank you', 'thanks', 'thanks boo'):
            category = 'thanks'
        elif command in ('goodbye', 'bye', 'bye bye', 'see you later'):
            category = 'goodbye'
            self.reset()
        if category:
            pack = ('laugh-challenge' if category.startswith('game_') or category == 'cackle' else
                    'quick-jokes' if category == 'joke' else 'playful-scares' if category == 'scare' else 'candy-host')
            if not self.enabled(pack):
                self.reset()
                return self.reply('fallback')
            # Speech requests already yield to native interruption. This bounds
            # repeated transcripts without queuing stale authored responses.
            if now - self.last_reply < 1.5:
                self.game_until, self.game_last = game_before
                return {'category': 'cooldown', 'text': None, 'expression': 'neutral'}
            if category == 'cackle':
                self.last_reply = now
                return {'category': category, 'text': None, 'expression': 'neutral'}
            return self.reply(category)
        if re.search(r'\b(?:allerg\w*|ingredients?|nuts?|peanuts?|diabet\w*|safe to eat)\b', command):
            self.reset()
            return self.reply('candy_safety')
        if self.game_until is not None:
            return {'category': 'waiting', 'text': None, 'expression': 'neutral'}
        if command in ('who are you', 'what are you', 'are you real', 'are you a real ghost'):
            return self.reply('identity')
        if re.search(r'\b(?:address|phone number|password|where do (?:i|you) live|my name is)\b', command):
            return self.reply('privacy')
        return None


def prepared_texts():
    from server.scripted_quips import load_quips
    lines = [text for group in load_pack()['replies'].values() for text, _ in group]
    lines += [text for group in load_quips('halloween')['groups'].values() for text, _ in group]
    return tuple(dict.fromkeys(lines + ['ONE ONLY, PLEASE!', 'One piece per person, please.']))
