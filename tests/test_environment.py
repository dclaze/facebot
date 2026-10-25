"""Regression for the dependency failure observed during local speech setup."""
import unittest
class TokenizerTests(unittest.TestCase):
    def test_tokenizer_roundtrip(self):
        import spacy
        tokenizer = spacy.blank('en').tokenizer
        tokenizer.from_bytes(tokenizer.to_bytes())
        self.assertEqual([t.text for t in tokenizer('One piece, darling.')], ['One','piece',',','darling','.'])
