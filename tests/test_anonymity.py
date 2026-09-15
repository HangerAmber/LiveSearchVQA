import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from check_anonymity import text_issues

class AnonymityTests(unittest.TestCase):
    def test_owner_host_rejected(self):
        url='https://'+'example-user.github.io/project/'
        self.assertIn('non-anonymous repository/website URL',text_issues(url))
    def test_repository_link_rejected(self):
        url='https://'+'github.com/'+'example-user/project'
        self.assertTrue(text_issues(url))
    def test_encoded_and_protocol_relative_links_rejected(self):
        from urllib.parse import quote
        url='https://'+'github.com/'+'example-user/project'
        for value in (url.replace('https:',''),quote(url,safe=''),
                      url.replace('/',r'\/'),url.replace('/',r'\u002f'),
                      url.replace(':','&#58;'),url.replace('.com/','.com./')):
            self.assertIn('non-anonymous repository/website URL',text_issues(value))
    def test_anonymous_and_news_sources_allowed(self):
        self.assertEqual(text_issues('https://anonymous.4open.science/r/review/README.md https://www.nasa.gov/'),[])
    def test_non_english_text_rejected(self):
        self.assertIn('non-English CJK text',text_issues(chr(0x4e2d)))
    def test_local_path_rejected(self):
        value='C:'+chr(92)+'Users'+chr(92)+'example-user'+chr(92)+'notes.txt'
        self.assertIn('local user-directory path',text_issues(value))
    def test_review_projection(self):
        manifest=json.loads((ROOT/'data/releases/anonymous-review-export.json').read_text())
        for snapshot in manifest['snapshots']:
            raw=(ROOT/snapshot['path']).read_bytes();items=json.loads(raw)
            self.assertEqual(len(items),snapshot['review_items'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(),snapshot['review_sha256'])
            self.assertTrue(all(i['source_language']=='en' for i in items))
    def test_preview_content_unchanged(self):
        report=json.loads((ROOT/'data/releases/2026-09-05-ledger-linkage.json').read_text())
        raw=(ROOT/'data/previews/2026-09-05.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),report['preview_sha256'])
    def test_all_html_entry_points(self):
        for name in ('index.html','index_v2.html','demo.html','preview.html'):
            text=(ROOT/name).read_text(encoding='utf-8')
            self.assertEqual(text_issues(text),[],name)
            self.assertIn('name="referrer" content="no-referrer"',text)
            self.assertIn('<html lang="en">',text)

if __name__=='__main__':unittest.main()
