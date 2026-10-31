"""Short, sample-timed captions for native clients. No additional inference."""
import math
import re

RATE = 24000
MAX_SAMPLES = RATE * 120
MAX_TEXT = 160
# Part of prepared-audio cache identity: old PCM keeps its old caption sidecar.
CAPTION_PAGINATION_VERSION = 2


def _sentence_end(word):
    word = word.rstrip('"\'”’)]}')
    if word.endswith(('!', '?', '…')):
        return True
    return (word.endswith('.') and word.count('.') == 1
            and word.casefold() not in {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'st.', 'jr.', 'sr.', 'vs.', 'etc.'}
            and not re.fullmatch(r'[A-Z]\.', word))


def caption_cues(text, samples, tokens=None):
    """Use the synthesized segment's text and available Kokoro word timestamps.

    Prepared recordings without alignment use proportional phrase timing; this
    fallback tracks PCM duration, and is not a word-alignment claim.
    """
    if not isinstance(text, str) or type(samples) is not int or not 0 < samples <= MAX_SAMPLES:
        return []
    text = ' '.join(text.split())
    if not text:
        return []
    pieces = []
    for match in re.finditer(r'\S+', text):
        word = match.group()
        for index in range(0, len(word), 30):
            pieces.append((word[index:index+30], match.start()+index))
    pages, current = [], []
    for piece in pieces:
        word, start = piece
        if current and (len(current) >= 5 or len(' '.join(p[0] for p in current)) + 1 + len(word) > 30):
            split = len(current)
            # Move one or two stranded words to the next page, retaining their
            # original text offsets for token/proportional timing. Do this only
            # on overflow; complete short greetings that fit stay together.
            for boundary in range(len(current)-1, max(1, len(current)-3), -1):
                carry = current[boundary:] + [piece]
                if (_sentence_end(current[boundary-1][0])
                        and len(' '.join(p[0] for p in carry)) <= 30):
                    split = boundary
                    break
            pages.append((' '.join(p[0] for p in current[:split]), current[0][1]))
            current = current[split:]
        current.append(piece)
    if current:
        pages.append((' '.join(p[0] for p in current), current[0][1]))
    if len(pages) > 512 or len(pages) > samples:
        raise ValueError('Caption segment too large')
    # Alignment is optional. Match token spelling against actual segment text;
    # aliases or incomplete timing fall back to bounded proportional timing.
    starts, cursor = {}, 0
    for token in tokens or []:
        spelling = ' '.join(str(getattr(token, 'text', '')).split())
        timestamp = getattr(token, 'start_ts', None)
        if not spelling or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
            continue
        index = text.find(spelling, cursor)
        if index >= 0:
            starts[index] = max(0, min(samples-1, round(timestamp * RATE)))
            cursor = index + len(spelling)
    boundaries = [0]
    for index, (_, start) in enumerate(pages[1:], 1):
        candidate = starts.get(start, round(samples * start / len(text)))
        boundaries.append(max(boundaries[-1]+1, min(samples-(len(pages)-index), candidate)))
    boundaries.append(samples)
    return [[boundaries[i], boundaries[i+1], page] for i, (page, _) in enumerate(pages)]


def validate_captions(cues):
    if not isinstance(cues, list) or len(cues) > 512:
        raise ValueError('Invalid caption cues')
    previous = 0
    for cue in cues:
        if not isinstance(cue, (list, tuple)) or len(cue) != 3:
            raise ValueError('Invalid caption cue')
        start, end, text = cue
        if (type(start) is not int or type(end) is not int or start < previous
                or not start < end <= MAX_SAMPLES or not isinstance(text, str)
                or not text.strip() or len(text) > MAX_TEXT
                or any(ord(character) < 32 for character in text)):
            raise ValueError('Invalid caption cue')
        previous = end
    return cues
