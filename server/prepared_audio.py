"""Local authored-only speech cache; generated visitor dialogue is never stored."""
import base64
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path

from server.kiosk_experiences import prepared_texts
from server.spoken_text import spoken_text
from server.captions import validate_captions


@lru_cache(maxsize=1)
def authored_texts():
    return frozenset(spoken_text(text) for text in prepared_texts())


class PreparedAudioCache:
    def __init__(self, model, root=None):
        self.model = model
        self.root = Path(root or os.getenv('FACEBOT_PREPARED_CACHE',
            str(Path(__file__).resolve().parents[1] / '.local/prepared-audio')))
        self.hits = self.misses = 0

    def key(self, text, voice, speed):
        return hashlib.sha256(json.dumps([1, self.model, voice, float(speed), text],
                                         separators=(',', ':')).encode()).hexdigest()

    def get(self, text, voice, speed):
        if text not in authored_texts():
            return None
        key = self.key(text, voice, speed)
        path = self.root / (key + '.json')
        try:
            if path.stat().st_size > 2_000_000:
                raise ValueError('Oversized prepared audio')
            value = json.loads(path.read_text())
            if value['key'] != key or value['version'] != 1:
                raise ValueError('Prepared audio identity mismatch')
            result = []
            total = 0
            for row in value['segments']:
                audio = base64.b64decode(row['pcm'], validate=True)
                total += len(audio)
                if (len(audio) % 2 or not audio or total > 24_000 * 2 * 20
                        or hashlib.sha256(audio).hexdigest() != row['sha256']
                        or not isinstance(row['mouth_cues'], list) or len(row['mouth_cues']) > 1024
                        or not isinstance(row['captions'], list)):
                    raise ValueError('Invalid prepared audio')
                samples = len(audio) // 2
                previous = 0
                for cue in row['mouth_cues']:
                    if (not isinstance(cue, list) or len(cue) != 3
                            or type(cue[0]) is not int or type(cue[1]) is not int
                            or not previous <= cue[0] < cue[1] <= samples
                            or cue[2] not in ('rest', 'closed', 'teeth', 'tongue', 'pucker', 'round', 'open', 'wide', 'narrow')):
                        raise ValueError('Invalid cached viseme')
                    previous = cue[1]
                validate_captions(row['captions'])
                if any(cue[1] > samples for cue in row['captions']):
                    raise ValueError('Caption exceeds prepared segment')
                result.append((audio, row['mouth_cues'], row['captions']))
            if not result:
                raise ValueError('Empty prepared audio')
            self.hits += 1
            return result
        except (OSError, ValueError, KeyError, TypeError):
            self.misses += 1
            return None

    def put(self, text, voice, speed, segments):
        if text not in authored_texts():
            return
        rows = []
        for segment in segments:
            rows.append({'pcm': base64.b64encode(segment.audio).decode('ascii'),
                         'sha256': hashlib.sha256(segment.audio).hexdigest(),
                         'mouth_cues': segment.mouth_cues, 'captions': segment.captions})
        if not rows or sum(len(s.audio) for s in segments) > 24_000 * 2 * 20:
            return
        key = self.key(text, voice, speed)
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / (key + '.json')
            # Bounded disk footprint across voice/rate revisions. Cache misses
            # remain ordinary synthesis, so eviction cannot change behavior.
            files = list(self.root.glob('*.json'))
            if len(files) >= 256 and not path.exists():
                min(files, key=lambda p: p.stat().st_mtime).unlink()
            temporary = self.root / (key + '.tmp')
            temporary.write_text(json.dumps({'version': 1, 'key': key, 'segments': rows}, separators=(',', ':')))
            temporary.replace(path)
        except OSError:
            pass  # Cache storage failure must not suppress speech.
