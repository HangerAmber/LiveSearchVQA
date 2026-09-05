import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from generate_v2 import _recover_verbatim, _recover_answer_span, _short_excerpt

class ProposalRepairs(unittest.TestCase):
    def test_typographic_quotes_keep_actual_source(self):
        source='A report. The firm announced “$5 million” in funding. End.'
        repaired=_recover_verbatim(source,'The firm announced "$5 million" in funding.')
        self.assertEqual(repaired,'The firm announced “$5 million” in funding.')
        self.assertIn(repaired,source)
    def test_nbsp_keeps_offsets(self):
        source='Sales grew by 5\u00a0percent this quarter.'
        self.assertEqual(_recover_verbatim(source,'Sales grew by 5 percent this quarter.'),source)
    def test_equivalent_format_only(self):
        self.assertEqual(_recover_answer_span('The price is US$1,250 today.','USD 1250'),'US$1,250')
        self.assertEqual(_recover_answer_span('Growth was 5 percent.','5.1%'),'5.1%')
    def test_excerpt_is_verbatim_and_short(self):
        source=' '.join(['word']*20+['$5','million']+['context']*20)
        excerpt=_short_excerpt(source,'$5 million')
        self.assertIn(excerpt,source)
        self.assertIn('$5 million',excerpt)
        self.assertLessEqual(len(excerpt.split()),25)

if __name__=='__main__':unittest.main()
