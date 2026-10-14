import unittest
from app.core import bm25, chunks, fuse, validate_claims

class CoreTests(unittest.TestCase):
    def test_overlap_and_no_tail_duplication(self):
        text = ' '.join(str(i) for i in range(300))
        result = chunks(text)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].split()[-30:], result[1].split()[:30])
        self.assertEqual(result[-1].split()[-1], '299')
        self.assertEqual(chunks(''), [])
    def test_keyword_ranking(self):
        scores=bm25('equipment approval', ['Employees need equipment approval', 'Annual leave details'])
        self.assertGreater(scores[0], scores[1])
    def test_fusion_rewards_agreement(self):
        self.assertEqual(fuse(['a','b'],['c','b'])[0], 'b')
    def test_citations_reject_unknown_or_fabricated_quotes(self):
        source={'id':'a','text':'Employees may work remotely two days per week.'}
        good={'statement':'Two remote days are permitted.', 'source_id':'a','quote':'work remotely two days per week.'}
        bad_quote={**good,'quote':'work remotely seven days per week.'}
        bad_id={**good,'source_id':'invented'}
        self.assertEqual(validate_claims({'claims':[good,bad_quote,bad_id,None]},[source]),[good])

if __name__=='__main__': unittest.main()
