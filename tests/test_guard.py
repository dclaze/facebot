import unittest
from server.guard import checked_reply, FALLBACK, LENGTH_FALLBACK
class GuardTests(unittest.TestCase):
    def test_family_safe_line_kept(self):
        text='My haunting budget only covers one piece each.'
        self.assertEqual(checked_reply(text),text)
    def test_unsafe_or_oversized_output_replaced(self):
        for text in ['', 'You are stupid.', 'Visit https://example.org']:
            self.assertEqual(checked_reply(text), FALLBACK)

    def test_complete_safe_answer_is_not_a_safety_refusal(self):
        text = 'Ask the host about ingredients before choosing candy, because I cannot verify what is inside each wrapper.'
        self.assertEqual(checked_reply(text), text)
        self.assertEqual(checked_reply('word '*33), LENGTH_FALLBACK)

    def test_emoji_and_stage_directions_are_not_spoken(self):
        self.assertEqual(checked_reply('One piece. 😁✨'), 'One piece.')
        self.assertEqual(checked_reply('*grins* One piece. (Winks.)'), 'One piece.')
        self.assertEqual(checked_reply('One piece per person. 👨‍👩‍👧‍👦'), 'One piece per person.')
        self.assertEqual(checked_reply('Only *one* piece. Allergies? Ask the host (check the wrapper).'),
                         'Only one piece. Allergies? Ask the host (check the wrapper).')
        self.assertEqual(checked_reply('😀'), FALLBACK)
