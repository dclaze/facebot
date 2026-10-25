import importlib.util
import unittest
from unittest.mock import patch
import io
import json

spec = importlib.util.spec_from_file_location('benchmark', 'scripts/benchmark_ollama.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class BenchmarkTests(unittest.TestCase):
    def test_percentile_small_sample_and_empty(self):
        self.assertIsNone(b.percentile([], .95))
        self.assertEqual(b.percentile([3, 1, 2], .95), 3)

    def test_truncated_stream_is_failure(self):
        with patch.object(b.urllib.request, 'urlopen', return_value=io.BytesIO(b'')):
            with self.assertRaisesRegex(RuntimeError, 'without completion'):
                b.measure('http://localhost', 'test', 'synthetic')

    def test_thinking_does_not_count_as_content(self):
        events = [{'message': {'thinking': 'hidden'}},
                  {'message': {'content': 'Boo!'}}, {'done': True, 'eval_count': 2}]
        stream = io.BytesIO(b'\n'.join(json.dumps(x).encode() for x in events))
        with patch.object(b.urllib.request, 'urlopen', return_value=stream):
            result = b.measure('http://localhost', 'test', 'synthetic')
        self.assertIsNotNone(result['first_token_ms'])
        self.assertEqual(result['first_token_ms'], result['first_sentence_ms'])

if __name__ == '__main__':
    unittest.main()
