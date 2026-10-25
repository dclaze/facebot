import unittest
from server.visemes import cues, shape


class VisemeTests(unittest.TestCase):
    def test_distinct_articulations_and_silence(self):
        self.assertEqual([shape(p) for p in 'mafuil '],
                         ['closed','open','teeth','pucker','wide','tongue','rest'])

    def test_sample_timeline_bounds_and_merge(self):
        result = cues('mma', [4,2,2,3,4], 6000, offset=1200)
        self.assertEqual(result, [[1800,4200,'closed'],[4200,6000,'open']])
        result = cues('ma', [3,10,10,1], 1000)
        self.assertEqual(result, [[0,1000,'closed']])
        with self.assertRaises(ValueError): cues('ma',[1,2],1000)
