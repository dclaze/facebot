"""Remove non-spoken presentation cues before a phonemizer can name them."""
import re
import regex
from server.reactions import parse_reply

# Match complete graphemes so skin tones, flags, keycaps and ZWJ families
# disappear together. Digits by themselves remain ordinary spoken text.
EMOJI = regex.compile(r'\p{Extended_Pictographic}|\p{Regional_Indicator}|\p{Emoji_Modifier}|\u20e3')
ACTION = r'(?:grins?|smiles?|winks?|laughs?|chuckles?|giggles?|sighs?|gasps?|pauses?|nods?|shrugs?)'
DIRECTION = re.compile(
    rf'\*{{1,2}}\s*{ACTION}[.!]?\s*\*{{1,2}}|'
    rf'[\[(]\s*{ACTION}[.!]?\s*[\])]', re.I)


def spoken_text(text: str) -> str:
    if text.lstrip().startswith(('{', '[{', '```')):
        try:
            text, _ = parse_reply(text)
        except (ValueError, TypeError, KeyError):
            return ''
    text = ''.join(g for g in regex.findall(r'\X', text) if not EMOJI.search(g))
    text = DIRECTION.sub(' ', text)
    # Strip formatting, preserving emphasized words and useful parentheticals.
    text = text.replace('*', '').replace('`', '')
    text = re.sub('[\u200d\ufe0e\ufe0f]', '', text)
    return re.sub(r'\s+', ' ', text).strip()
