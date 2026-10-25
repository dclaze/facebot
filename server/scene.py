"""Ephemeral observations only; never infer a complete headcount from faces."""
import time
from server.encounter import EncounterState


class SceneState:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.encounter = EncounterState(clock)
        self.received_at = None
        self.faces = None
        self.age_ms = 0

    def update(self, event):
        self.encounter.observe(event['visible_faces'], event['age_ms'])
        self.faces = event['visible_faces']
        self.age_ms = event['age_ms']
        self.received_at = self.clock()

    def context(self):
        if self.received_at is None or (self.clock()-self.received_at)*1000+self.age_ms > 750:
            return 'No fresh visual observation is available. Do not claim to see the audience or surroundings.'
        return (f'Fresh local front-camera detector observation: {self.faces} visible faces detected. '
                'This is uncertain and can miss people, not a complete headcount. '
                'Use this observation naturally when relevant; address a group when multiple faces are detected. '
                'Zero detected faces does not prove nobody is there. '
                'No evidence yet identifies the speaker, furniture, seating, clothing, actions or candy counts. '
                'Do not claim to see a couch or any other unsupported detail. Never identify people.')
