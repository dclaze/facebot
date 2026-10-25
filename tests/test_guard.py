import unittest
from server.guard import checked_reply, FALLBACK
class GuardTests(unittest.TestCase):
    def test_family_safe_line_kept(self):
        text='My haunting budget only covers one piece each.'
        self.assertEqual(checked_reply(text),text)
    def test_unsafe_or_oversized_output_replaced(self):
        for text in ['', 'You are stupid.', 'Visit https://example.org', 'word '*40]:
            self.assertEqual(checked_reply(text), FALLBACK)
