import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from check_navigation import NavigationParser, check, local_target_issue


class NavigationTests(unittest.TestCase):
    def test_whole_artifact_navigation(self):
        report=check(ROOT)
        self.assertEqual(report['findings'],[])
        self.assertGreaterEqual(report['files'],5)

    def test_no_repository_buttons_or_wrapped_animation(self):
        for name in ('index.html','index_v2.html','demo.html','preview.html'):
            text=(ROOT/name).read_text(encoding='utf-8')
            for label in ('>GitHub</a>','>Anonymous repository</a>','>Code &amp; data</a>'):
                self.assertNotIn(label,text,name)
            self.assertIn('Navigation audit: 2026-09-25',text)
            self.assertNotRegex(text,r'<a\b')
            self.assertNotIn('window.open(',text)
            self.assertIn('assets/live-search-demo.mp4',text)
        readme=(ROOT/'README.md').read_text(encoding='utf-8')
        self.assertNotIn('[![',readme)
        self.assertNotIn('Open the interactive demo',readme)

    def test_navigation_rejects_external_and_encoded_urls(self):
        for value in ('https://example.invalid/','//example.invalid/',
                      'https%3A%2F%2Fexample.invalid/',
                      'https&#58;//example.invalid/','/another-project/',
                      '../outside-artifact','file:/private','javascript:alert(1)'):
            self.assertIsNotNone(local_target_issue(value,ROOT/'index.html',ROOT))

    def test_local_links_resolve(self):
        for value in ('#explorer','README.md','preview.html','data/benchmark_v2.json'):
            self.assertIsNone(local_target_issue(value,ROOT/'index.html',ROOT))

    def test_hidden_redirects(self):
        parser=NavigationParser()
        parser.feed('<base href="/"><meta http-equiv="refresh" content="0;url=elsewhere">')
        self.assertEqual(len(parser.issues),2)

    def test_even_local_hyperlinks_disabled(self):
        parser=NavigationParser()
        parser.feed('<a href="README.md">Readme</a><a href="#case">Case</a>')
        self.assertEqual(len(parser.issues),2)

    def test_media_manifest_matches(self):
        import json,hashlib
        manifest=json.loads((ROOT/'assets/showcase-manifest.json').read_text())
        self.assertEqual(manifest['new_model_calls'],0)
        for name,digest in manifest['outputs'].items():
            self.assertEqual(hashlib.sha256((ROOT/'assets'/name).read_bytes()).hexdigest(),digest)


if __name__=='__main__':unittest.main()
