"""Bounded, ephemeral audience continuity; never biometric identity or recall.

A generation change asks consumers to forget conversational history. It is a
privacy boundary, not proof somebody left or a particular person arrived.
"""
import time


class EncounterState:
    FRESH_SECONDS = .75
    STABLE_SECONDS = .75
    ABSENCE_SECONDS = 3.
    GREETING_COOLDOWN = 20.

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.generation = 0
        self.silenced = False
        self._received = None
        self._candidate = None
        self._since = 0.
        self._stable = None
        self._active = False
        self._pending = False
        self._last_greeting = float('-inf')

    def observe(self, faces, age_ms):
        now = self.clock()
        if age_ms > self.FRESH_SECONDS * 1000:
            self._received = None
            self._pending = False
            return
        continuous = self._received is not None and now-self._received <= self.FRESH_SECONDS
        if not continuous or faces != self._candidate:
            self._candidate, self._since = faces, now
        self._received = now-age_ms/1000
        threshold = self.ABSENCE_SECONDS if faces == 0 else self.STABLE_SECONDS
        if now-self._since < threshold or faces == self._stable:
            return
        self._stable = faces
        self.generation += 1
        if faces == 0:
            self._active = False
            self._pending = False
            # Silence stays latched; visual uncertainty must not override a stop.
        elif not self._active:
            self._active = True
            self._pending = True
        # Changing group size invalidates memory but does not repeat an intro.

    def engaged(self):
        # Speech already began this encounter: a late greeting would be redundant.
        self._active = True
        self._pending = False

    def take_event(self, *, user_speaking=False, bot_speaking=False):
        now = self.clock()
        if (not self._pending or self.silenced or user_speaking or bot_speaking
                or self._received is None or now-self._received > self.FRESH_SECONDS
                or self._candidate != self._stable or not self._stable
                or now-self._last_greeting < self.GREETING_COOLDOWN):
            return None
        self._pending = False
        self._last_greeting = now
        return {'kind': 'stable_visual_arrival', 'visible_faces': self._stable,
                'generation': self.generation}
