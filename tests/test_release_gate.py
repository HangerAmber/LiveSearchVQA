"""Synthetic unit fixtures only: these records must never be released as data."""
import contextlib
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import validate_v2

class ReleaseGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.data=Path(self.tmp.name)
        (self.data/'images').mkdir()
        Image.new('RGB',(300,200),'navy').save(self.data/'images/fixture.jpg')
        now=datetime.now(timezone.utc)
        evidence='The project raised $5 million in funding.'
        question='How much funding did the pictured project report raising in its newly announced round?'
        panel=['fixture-A','fixture-B','fixture-C']
        cert={'profile':'3-model-x-4','panel':panel,'run_id':'UNIT-TEST-ONLY',
              'grader_version':'unit-fixture','closed_book':{},'oracle':{},'trials':[]}
        for condition in ('closed_book','oracle'):
            for member in panel:
                prediction='UNKNOWN' if condition=='closed_book' else '$5 million'
                cert[condition][member]=[prediction]*4
                for sample in range(4):
                    cert['trials'].append({'condition':condition,'member':member,
                        'prediction':prediction,'correct':condition=='oracle',
                        'prompt':question if condition=='closed_book' else evidence+' '+question,
                        'temperature':0.7 if condition=='closed_book' else 0.2,'top_p':0.95,
                        'api_record_id':f'UNIT-TEST-{condition}-{member}-{sample}'})
        self.item={'id':'UNIT-TEST-ONLY','article_id':'fixture','image':'images/fixture.jpg',
            'question':question,'answer':'$5 million','answer_type':'numeric',
            'evidence':evidence,'category':'business','source':'unit-fixture','source_language':'en',
            'article_url':'https://example.invalid/fixture','article_title':'Unit test fixture',
            'pub_date':(now-timedelta(hours=1)).isoformat(),'build_date':now.date().isoformat(),
            'build_timestamp':now.isoformat(),'source_sha256':hashlib.sha256(evidence.encode()).hexdigest(),
            'evidence_offsets':[0,len(evidence)],'item_version':'unit-fixture','event_id':'unit-fixture',
            'human_review_status':'not_yet_audited','visual_anchor_type':'object',
            'freshness_relation':'new_announcement','certification':cert,
            'image_match_audit':{**{k:4 for k in ('image_article_match','question_image_grounding',
                'event_specificity','search_necessity','fresh_fact_centrality','question_clarity')},
                'explicit_event_question':True,'image_only_answerable':False,'visual_claim_supported':True},
            'referent_grounding_audit':{'image_resolves_omitted_subject':True,
                'omitted_subject_is_answer_target':True,'omitted_subject':'fixture project',
                'profile':'qwen-plus-all-2','samples':[{'fixture':True},{'fixture':True}]}}
        (self.data/'articles.json').write_text(json.dumps([{'id':'fixture','text':evidence}]),encoding='utf-8')

    def tearDown(self):self.tmp.cleanup()

    def check(self,item):
        (self.data/'candidate.json').write_text(json.dumps([item]),encoding='utf-8')
        with patch.object(validate_v2,'DATA_DIR',str(self.data)),contextlib.redirect_stdout(io.StringIO()):
            try:validate_v2.validate('candidate.json',target=1)
            except SystemExit:pass
        return json.loads((self.data/'quality_report_v2.next.json').read_text())['problems']

    def test_complete_record(self):self.assertEqual(self.check(self.item),[])
    def test_p1_correct_answer_rejected(self):
        self.item['certification']['trials'][0]['correct']=True
        self.assertTrue(any('verdict' in p for p in self.check(self.item)))
    def test_p2_wrong_answer_rejected(self):
        self.item['certification']['trials'][-1]['correct']=False
        self.assertTrue(any('verdict' in p for p in self.check(self.item)))
    def test_debug_profile_not_publishable(self):
        self.item['certification']['profile']='3-model-x-1'
        self.assertTrue(any('exactly' in p for p in self.check(self.item)))
    def test_future_article_rejected(self):
        self.item['pub_date']=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()
        self.assertTrue(any('age' in p for p in self.check(self.item)))
    def test_source_tampering_rejected(self):
        self.item['source_sha256']='wrong'
        self.assertTrue(any('hash mismatch' in p for p in self.check(self.item)))
    def test_excerpt_tampering_rejected(self):
        self.item['evidence_offsets']=[1,10]
        self.assertTrue(any('offsets' in p for p in self.check(self.item)))

if __name__=='__main__':unittest.main()
