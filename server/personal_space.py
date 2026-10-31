"""Face image occupancy, not metric distance or identity. Hysteresis prevents nagging."""
import time


class PersonalSpace:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.near_since = self.far_since = self.last_seen = None
        self.warned = False
        self.pending = None
        self.last_warning = float('-inf')

    def observe(self, fill, faces, age_ms):
        now = self.clock()
        if faces < 1 or age_ms > 500 or fill is None:
            self.near_since = self.far_since = None
            self.pending = None
            self.last_seen = None
            self.warned = False
            return
        if self.last_seen is None or now-self.last_seen > .75:
            self.near_since = self.far_since = None
            self.pending = None
            self.warned = False
        self.last_seen = now-age_ms/1000
        if fill >= 180:
            self.far_since = None
            if self.pending == 'space_restored': self.pending = None
            if self.near_since is None: self.near_since = now
            if not self.warned and now-self.near_since >= .6 and now-self.last_warning >= 30:
                self.pending = 'too_close'
        elif fill <= 100:
            self.near_since = None
            if self.pending == 'too_close': self.pending = None
            if self.far_since is None: self.far_since = now
            if self.warned and now-self.far_since >= 1.:
                self.pending = 'space_restored'
        else:
            self.near_since = self.far_since = None
            self.pending = None

    def take_event(self):
        if not self.pending or self.last_seen is None or self.clock()-self.last_seen > .75:
            return None
        kind = self.pending
        self.pending = None
        self.warned = kind == 'too_close'
        if self.warned: self.last_warning = self.clock()
        return {'kind': kind}
