import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from answer_equivalence import fast_match

class EqTests(unittest.TestCase):
    def test_exact_quantity(self):
        self.assertTrue(fast_match('$1,250', '$1250'))
        self.assertTrue(fast_match('US$1,250', 'USD 1250'))
        self.assertTrue(fast_match('5.70%', '5.7 percent'))
        self.assertTrue(fast_match('Third', 'third'))

    def test_wrong_number_or_sign(self):
        self.assertFalse(fast_match('96.2', '81.6'))
        self.assertFalse(fast_match('-3', '3'))
        self.assertFalse(fast_match('5.7%', '5.8%'))

    def test_context_requires_judge(self):
        for gold, answer in [('5 percent', '5 percentage points'),
                             ('$1250', 'USD 1250'),
                             ('$5', '5'), ('5 million', '5 billion'),
                             ('Aug. 14, 2026', 'Aug. 14, 2025'),
                             ('Q2 FY2027', 'Q1 FY2027'),
                             ('96.2', 'The answer is 196.2')]:
            self.assertIsNone(fast_match(gold, answer))

    def test_abstention_and_multiple_answers(self):
        self.assertFalse(fast_match('96.2', 'UNKNOWN'))
        self.assertFalse(fast_match('96.2', '96.2 or 81.6'))
        self.assertFalse(fast_match('96.2', ''))

if __name__ == '__main__':
    unittest.main()
