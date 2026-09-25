"""Require link-free presentation and local media; never print destinations."""
import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from check_anonymity import ROOT, public_paths


class NavigationParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.targets=[]
        self.issues=[]

    def handle_starttag(self, tag, attrs):
        values=dict(attrs)
        if tag in {'a','area'} and 'href' in values:
            self.issues.append('hyperlink navigation is disabled')
        if tag in {'iframe','object','embed','form'}:
            self.issues.append('embedded navigation or form is disabled')
        if tag=='base':self.issues.append('base element overrides local navigation')
        if tag=='meta' and values.get('http-equiv','').lower()=='refresh':
            self.issues.append('automatic meta redirect')
        for field in ('href','src','action','formaction','poster','data'):
            if field in values and values[field]:self.targets.append(values[field])
        for candidate in values.get('srcset','').split(','):
            if candidate.strip():self.targets.append(candidate.strip().split()[0])


def local_target_issue(value, path, root):
    value=html.unescape(value).strip()
    for _ in range(2):value=unquote(value)
    if value.startswith('#') or not value:return None
    try:parts=urlsplit(value)
    except ValueError:return 'invalid navigation target'
    if parts.scheme or parts.netloc:return 'external project navigation'
    if value.startswith('/') or '\\' in value:
        return 'root-relative or ambiguous navigation'
    target=(path.parent/parts.path).resolve()
    if not target.is_relative_to(root.resolve()):return 'navigation escapes artifact'
    if not target.exists():return 'missing local navigation target'
    return None


def check(root=ROOT):
    root=Path(root); findings=[]; pages=0; links=0
    for path in public_paths(root):
        if path.suffix.lower() not in {'.html','.md'}:continue
        pages+=1
        text=path.read_text(encoding='utf-8')
        parser=NavigationParser();parser.feed(text)
        targets=parser.targets
        if path.suffix=='.md':
            if re.search(r'(?<!!)\[[^\]\n]+\]\(',text) or re.search(r'^\s*\[[^\]]+\]:',text,re.M):
                parser.issues.append('Markdown text hyperlink is disabled')
            without_code=re.sub(r'```[\s\S]*?```|`[^`\n]+`','',text)
            if re.search(r'https?://|<https?:',without_code):
                parser.issues.append('autolink outside code is disabled')
            targets += [a or b for a,b in re.findall(r'\]\(\s*(?:<([^>]+)>|([^\s)]+))',text)]
            targets += re.findall(r'^\s*\[[^\]]+\]:\s*<?([^\s>]+)',text,re.M)
            targets += re.findall(r'<((?:https?:)?//[^<>\s]+)>',text)
        issues=parser.issues
        if path.suffix=='.html' and re.search(r'(?:window\.open\s*\(|location(?:\.href)?\s*=|location\.(?:assign|replace)\s*\()',text):
            issues.append('script navigation is disabled')
        for target in targets:
            links+=1
            issue=local_target_issue(target,path,root)
            if issue:issues.append(issue)
        if issues:findings.append({'path':path.relative_to(root).as_posix(),
                                   'issues':sorted(set(issues))})
    return {'status':'FAIL' if findings else 'PASS','files':pages,
            'static_targets':links,'findings':findings,
            'scope':'all HTML and Markdown presentation; runtime in-place controls tested separately'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    report=check(parser.parse_args().root)
    print(json.dumps(report,indent=2));raise SystemExit(report['status']!='PASS')


if __name__=='__main__':main()
