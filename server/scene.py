"""Ephemeral observations only; never infer a complete headcount from faces."""
import time
from server.encounter import EncounterState
from server.personal_space import PersonalSpace


class SceneState:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.encounter = EncounterState(clock)
        self.space = PersonalSpace(clock)
        self.received_at = None
        self.faces = None
        self.overflow = False
        self.age_ms = 0

    def update(self, event):
        self.space.observe(event.get('face_fill'), event['visible_faces'], event['age_ms'])
        self.encounter.observe(event['visible_faces'], event['age_ms'])
        self.faces = event['visible_faces']
        self.overflow = event.get('overflow', False)
        self.age_ms = event['age_ms']
        self.received_at = self.clock()

    def context(self):
        if self.received_at is None or (self.clock()-self.received_at)*1000+self.age_ms > 750:
            return 'No fresh visual observation is available. Do not claim to see the audience or surroundings.'
        count = f'at least {self.faces}' if self.overflow else str(self.faces)
        return (f'Fresh local front-camera detector observation: {count} visible faces detected. '
                'This is uncertain and can miss people, not a complete headcount. '
                'Use this observation naturally when relevant; address a group when multiple faces are detected. '
                'Zero detected faces does not prove nobody is there. '
                'Face detection alone does not identify the speaker, objects, clothing, actions or object counts. '
                'Use separately supplied fresh image labels for objects; never invent unsupported details or identify people.')
