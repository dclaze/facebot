import unittest
from server.encounter import EncounterState


class EncounterTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.
        self.state = EncounterState(clock=lambda: self.now)

    def observe(self, faces, advance=0, age_ms=0):
        self.now += advance
        self.state.observe(faces, age_ms)

    def test_stable_arrival_emits_once_and_never_fabricates_dialogue(self):
        self.observe(1)
        self.assertIsNone(self.state.take_event())
        for _ in range(4): self.observe(1, .25)
        event = self.state.take_event()
        self.assertEqual(event['kind'], 'stable_visual_arrival')
        self.assertEqual(event['visible_faces'], 1)
        self.assertNotIn('user', event)
        self.assertIsNone(self.state.take_event())
        for _ in range(200): self.observe(1, .25)
        self.assertIsNone(self.state.take_event())

    def test_speech_silence_and_staleness_suppress_initiation(self):
        self.observe(2)
        for _ in range(4): self.observe(2, .25)
        self.assertIsNone(self.state.take_event(user_speaking=True))
        self.assertIsNone(self.state.take_event(bot_speaking=True))
        self.state.silenced = True
        self.assertIsNone(self.state.take_event())
        self.state.silenced = False
        self.now += 1
        self.assertIsNone(self.state.take_event())

    def test_dropout_does_not_create_new_encounter_but_sustained_absence_does(self):
        self.observe(1)
        self.observe(1, .25)
        generation = self.state.generation
        self.observe(0, .25)
        self.observe(1, .25)
        self.assertEqual(self.state.generation, generation)
        self.observe(0, .25)
        for _ in range(12): self.observe(0, .25)
        self.assertGreater(self.state.generation, generation)
        self.assertIsNone(self.state.take_event())

    def test_stable_group_change_forgets_history_without_reintroducing(self):
        self.observe(1)
        for _ in range(4): self.observe(1, .25)
        self.state.take_event()
        generation = self.state.generation
        self.observe(2, .25)
        for _ in range(4): self.observe(2, .25)
        self.assertGreater(self.state.generation, generation)
        self.assertIsNone(self.state.take_event())

    def test_stale_stream_cannot_accumulate_stability(self):
        self.observe(1)
        self.observe(1, 10)
        self.assertIsNone(self.state.take_event())
        self.observe(1, 1, age_ms=1000)
        self.assertIsNone(self.state.take_event())
