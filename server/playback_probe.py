"""Content-free host dispatch → native playback-head acknowledgement timings.

Includes return network transit. Excludes speech recognition and acoustic output.
These measurements must never be presented as visitor-end-to-audible latency.
"""
from collections import deque
import math
import statistics
import time
import uuid

SCENARIOS = {'welcome': 'Trick or treat!', 'candy': 'How many pieces can I take?',
             'joke': 'Tell me a joke', 'scare': 'Scare me',
             'laugh-invite': "Let's have a laughing contest", 'laugh-turn': 'Your turn',
             'sound': 'Make a ghost sound', 'robin': 'Is Robin Williams there?',
             'goodbye': 'Goodbye'}


class PlaybackProbes:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.pending = None
        self.results = deque(maxlen=200)

    def expire(self):
        if self.pending and self.clock() - self.pending['started'] > 15:
            self.results.append({'id': self.pending['id'], 'scenario': self.pending['scenario'], 'status': 'timeout'})
            self.pending = None

    def begin(self, scenario):
        self.expire()
        if scenario not in SCENARIOS:
            raise ValueError('Unknown rehearsal scenario')
        if self.pending:
            raise RuntimeError('A playback probe is pending')
        self.pending = {'id': str(uuid.uuid4()), 'scenario': scenario,
                        'started': self.clock(), 'epoch': None, 'offset': None}
        return self.pending['id']

    def sent(self, identifier, epoch, offset):
        if self.pending and self.pending['id'] == identifier:
            self.pending.update(epoch=epoch, offset=offset)

    def receive(self, event):
        self.expire()
        pending = self.pending
        if (not pending or pending['epoch'] is None or event['id'] != pending['id']
                or event['epoch'] != pending['epoch'] or event['sample'] <= pending['offset']):
            return
        self.results.append({'id': pending['id'], 'scenario': pending['scenario'], 'status': 'played',
                             'dispatch_to_native_ack_ms': round((self.clock() - pending['started']) * 1000, 2)})
        self.pending = None

    def cancel(self):
        if self.pending:
            self.results.append({'id': self.pending['id'], 'scenario': self.pending['scenario'], 'status': 'cancelled'})
            self.pending = None

    def report(self):
        self.expire()
        values = sorted(x['dispatch_to_native_ack_ms'] for x in self.results if x['status'] == 'played')
        return {'evidence': 'host dispatch to native AudioTrack head acknowledgement; includes return Wi-Fi; excludes VAD, STT and acoustic output',
                'samples': list(self.results), 'pending': self.pending['id'] if self.pending else None,
                'summary': {'n': len(values), 'p50_ms': statistics.median(values),
                            'p95_ms': values[math.ceil(len(values)*.95)-1]} if values else None}
