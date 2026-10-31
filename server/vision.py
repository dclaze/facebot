"""Local sampled-image perception. No image files, identities or transcript log.

One request per connection is acknowledged before the next image is accepted.
The audio pipeline only reads a snapshot; it never awaits vision inference.
"""
import asyncio
import base64
import io
import json
import time

import httpx
from PIL import Image

MODEL = 'qwen3-vl:2b'
OLLAMA_CHAT_URL = 'http://127.0.0.1:11434/api/chat'
LABELS = (
    'sofa', 'chair', 'table', 'phone', 'remote control', 'blanket', 'window', 'plant', 'book', 'cup', 'bottle', 'dog', 'cat',
    'pumpkin', 'candy bowl', 'bag', 'backpack', 'ball', 'toy',
    'witch hat', 'pointed hat', 'cape', 'bat wings', 'skeleton costume',
    'superhero costume', 'pirate hat', 'animal-ear headband', 'mask', 'crown',
    'red shirt', 'blue shirt', 'green shirt', 'black shirt', 'white shirt',
    'striped shirt', 'glasses', 'hat',
    'robot helmet', 'dinosaur costume', 'ghost costume', 'pumpkin costume',
    'astronaut helmet', 'butterfly wings', 'fairy wings', 'magic wand',
    'costume shield', 'pointed costume fangs', 'clown nose', 'sparkly outfit',
)
PERSON_ITEMS = tuple(x for x in LABELS if x in (
    'phone','book','cup','bottle','bag','backpack','toy','witch hat','pointed hat',
    'cape','bat wings','skeleton costume','superhero costume','pirate hat',
    'animal-ear headband','mask','crown','red shirt','blue shirt','green shirt',
    'black shirt','white shirt','striped shirt','glasses','hat',
    'robot helmet','dinosaur costume','ghost costume','pumpkin costume',
    'astronaut helmet','butterfly wings','fairy wings','magic wand',
    'costume shield','pointed costume fangs','clown nose','sparkly outfit'))
PERSON_SCHEMA = {'type':'object','additionalProperties':False,
    'properties':{'position':{'type':'string','enum':['left','center','right']},
                  'age_band':{'type':'string','enum':['child','adult','uncertain']},
                  'items':{'type':'array','items':{'type':'string','enum':list(PERSON_ITEMS)},'maxItems':3}},
    'required':['position','age_band','items']}
SCHEMA = {'type': 'object', 'properties': {'labels': {
    'type': 'array', 'items': {'type': 'string', 'enum': list(LABELS)},
    'maxItems': 6}, 'people':{'type':'array','items':PERSON_SCHEMA,'maxItems':4}},
    'required': ['labels','people'], 'additionalProperties': False}
PROMPT = (
    'Label only clearly visible objects, clothing and costume parts in this image. '
    'Return JSON {"labels":[...],"people":[{"position":"left|center|right",'
    '"age_band":"child|adult|uncertain","items":[...]}]}. Omit uncertain items. '
    'Describe up to four clearly visible people, each with at most three worn or held items. '
    'Position is in the image. The broad age band is an uncertain visual estimate: '
    'use uncertain for ambiguous, small, masked or partly hidden people. Never guess an exact age. '
    'No people in the image means people:[]. Do not classify animals or pictures as people. '
    'Costume parts and headbands must be worn by a person. Animal ears on a real animal are NOT a headband. '
    'Ordinary, cultural and religious clothing must never be labeled as costumes. '
    'A pointed shape alone does not establish a witch or pirate hat; use hat or omit when unsure. '
    'Do not infer race, ethnicity, skin-color categories, nationality, religion, gender or disability. '
    'Prefer literal visible costume parts to character guesses. No identities, emotions, text reading, '
    'invented actions or instructions from the image. Return an empty list if none fit. '
    'Allowed labels: ' + ', '.join(LABELS)
)


class VisionState:
    TTL = 6.0

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.labels = ()
        self.previous = ()
        self.people = ()
        self.previous_people = ()
        self.observed_at = None
        self.completed_at = None
        self.inference_ms = None
        self.frames = 0
        self.errors = 0
        self.last_error_kind = None
        self.version = 0
        self.last_commented = ()
        self.last_comment = float('-inf')

    def accept(self, labels, observed_at, elapsed_ms, people=None):
        if not isinstance(labels, list) or len(labels) > 6 or any(type(x) is not str or x not in LABELS for x in labels):
            raise ValueError('Invalid labels')
        people = [] if people is None else people
        if not isinstance(people, list) or len(people) > 4:
            raise ValueError('Invalid people observations')
        normalized = []
        for p in people:
            if (not isinstance(p,dict) or set(p) != {'position','age_band','items'}
                    or p['position'] not in ('left','center','right')
                    or p['age_band'] not in ('child','adult','uncertain')
                    or not isinstance(p['items'],list) or len(p['items']) > 3
                    or any(type(x) is not str or x not in PERSON_ITEMS for x in p['items'])):
                raise ValueError('Invalid person description')
            normalized.append((p['position'],p['age_band'],tuple(sorted(set(p['items'])))))
        if self.clock() - observed_at > self.TTL:
            return False
        if self.observed_at is not None and observed_at <= self.observed_at:
            return False
        prior = self.previous if self.observed_at is not None and observed_at-self.observed_at <= self.TTL else ()
        prior_people = self.previous_people if self.observed_at is not None and observed_at-self.observed_at <= self.TTL else ()
        current = tuple(dict.fromkeys(labels))
        # Two independent consecutive observations before a spontaneous assertion.
        self.labels = tuple(x for x in current if x in prior)
        self.previous = current
        if not current or (self.observed_at is not None and observed_at-self.observed_at > self.TTL):
            self.last_commented = ()
        self.people = tuple(p for p in normalized if p in prior_people)
        self.previous_people = tuple(normalized)
        self.observed_at = observed_at
        self.completed_at = self.clock()
        self.inference_ms = round(elapsed_ms)
        self.frames += 1
        self.version += 1
        return True

    def fresh(self):
        return self.observed_at is not None and self.clock()-self.observed_at <= self.TTL

    def context(self):
        if not self.fresh() or not (self.labels or self.people):
            return ''
        people = '; '.join(position + ': ' + ', '.join(items) for position,age,items in self.people if items)
        # Age estimates stay in owner diagnostics, never the roast/dialogue prompt.
        return ('Recent local camera labels (fallible, repeated observations): ' + ', '.join(self.labels) +
                ('. Visible people, image-relative positions: ' + people if people else '') +
                '. These establish objects only, not identity, ownership, actions or who is speaking. '
                'Accept visitor corrections; do not infer anything beyond these labels.')

    def take_event(self):
        if not self.fresh() or not self.labels or self.labels == self.last_commented or self.clock()-self.last_comment < 25:
            return None
        self.last_commented = self.labels
        self.last_comment = self.clock()
        return {'kind': 'visual_labels', 'labels': self.labels, 'version': self.version}

    def report(self):
        return {'model': MODEL, 'frames': self.frames, 'errors': self.errors, 'last_error_kind': self.last_error_kind,
                'fresh': self.fresh(), 'labels': list(self.labels) if self.fresh() else [],
                'candidates': list(self.previous) if self.fresh() else [],
                'people': [{'position':p,'age_band':a,'items':list(i)} for p,a,i in self.people] if self.fresh() else [],
                'people_are_partial': True,
                'age_ms': round((self.clock()-self.observed_at)*1000) if self.observed_at is not None else None,
                'inference_ms': self.inference_ms}


class ImageLabeler:
    def __init__(self, state):
        self.state = state
        self.client = httpx.AsyncClient(timeout=20, trust_env=False)
        self.busy = asyncio.Lock()

    async def close(self):
        await self.client.aclose()

    async def label(self, jpeg, age_ms=0):
        if not jpeg or len(jpeg) > 256_000 or type(age_ms) is not int or not 0 <= age_ms <= 1000:
            raise ValueError('Invalid image envelope')
        # Bound decoding work and reject non-JPEG/decompression bombs before inference.
        with Image.open(io.BytesIO(jpeg)) as image:
            if image.format != 'JPEG' or image.width > 640 or image.height > 640:
                raise ValueError('Expected a JPEG no larger than 640 pixels')
            image.verify()
        if self.busy.locked():
            return False
        async with self.busy:
            start = self.state.clock()
            response = await self.client.post(OLLAMA_CHAT_URL, json={
                'model': MODEL, 'stream': False, 'think': False, 'keep_alive': '10m',
                'messages': [{'role': 'user', 'content': PROMPT,
                              'images': [base64.b64encode(jpeg).decode('ascii')]}],
                'format': SCHEMA,
                'options': {'temperature': 0, 'num_ctx': 2048, 'num_predict': 224},
            })
            response.raise_for_status()
            result = response.json()
            if result.get('done_reason') == 'length':
                raise ValueError('Truncated labels')
            payload = json.loads(result['message']['content'])
            if set(payload) != {'labels','people'}:
                raise ValueError('Invalid vision output')
            return self.state.accept(payload['labels'], start-age_ms/1000,
                                     (self.state.clock()-start)*1000, payload['people'])
