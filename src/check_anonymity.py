"""Offline checks of the public review tree; no network or model calls."""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
HAN=re.compile(r'[\u3400-\u9fff]')
URL=re.compile(r'https?://[^\s<>"\x27)\]}]+',re.I)
LOCAL=re.compile(r'[A-Z]:[\\/](?:Users|Documents and Settings)[\\/][^\s"\x27]+',re.I)
SECRET=re.compile(r'sk-[A-Za-z0-9]{24,}|(?:ARK_API_KEY|QWEN_API_KEY)\s*=\s*[\x22\x27]?[A-Za-z0-9_-]{24,}')
TEXT_EXT={'.md','.py','.html','.json','.yml','.yaml','.toml','.txt','.tex','.bib','.sty','.bst','.svg','.js','.cjs','.css'}
EXCLUDED={'.git','.runs','__pycache__','.pytest_cache','node_modules','outputs','tmp'}

def public_paths(root=ROOT):
    root=Path(root)
    if (root/'.git').exists():
        names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
        paths=[root/n for n in names if n]
    else:paths=list(root.rglob('*'))
    return sorted({p for p in paths if p.is_file() and not any(part in EXCLUDED for part in p.relative_to(root).parts)
                   and p.suffix not in {'.zip','.pyc','.log','.tmp'}})

def text_issues(text,private_tokens=()):
    found=[]
    if HAN.search(text):found.append('non-English CJK text')
    if LOCAL.search(text):found.append('local user-directory path')
    if SECRET.search(text):found.append('possible credential')
    if any(t and t.casefold() in text.casefold() for t in private_tokens):found.append('private identifier')
    for match in URL.finditer(text):
        host=(urlsplit(match.group(0)).hostname or '').lower()
        if host in {'github.com','www.github.com','raw.githubusercontent.com','api.github.com','codeload.github.com'} or host.endswith('.github.io'):
            found.append('non-anonymous repository/website URL');break
    return sorted(set(found))

def check(root=ROOT):
    root=Path(root);findings=[];counts={'files':0,'text_files':0,'pdf_files':0}
    tokens=[t.strip() for t in os.environ.get('ANON_IDENTITY_TOKENS','').split(',') if t.strip()]
    if (root/'.git').exists():
        origin=subprocess.run(['git','config','--get','remote.origin.url'],cwd=root,capture_output=True,text=True).stdout.strip()
        match=re.search(r'(?:github\.com[:/])([^/]+)/',origin,re.I)
        if match and len(match.group(1))>=4:tokens.append(match.group(1))
    for path in public_paths(root):
        name=path.relative_to(root).as_posix();counts['files']+=1
        reasons=[]
        if path.name=='.env' or (path.name.startswith('.env.') and path.name!='.env.example'):
            reasons.append('private environment file')
        raw=path.read_bytes()
        if any(t.encode().lower() in raw.lower() for t in tokens):reasons.append('private identifier in file bytes')
        if path.suffix in TEXT_EXT or path.name in {'.gitignore','.env.example'}:
            counts['text_files']+=1
            reasons+=text_issues(raw.decode('utf-8-sig'),tokens)
        if path.suffix=='.pdf':
            counts['pdf_files']+=1
            from pypdf import PdfReader
            reader=PdfReader(path)
            reasons+=text_issues(str(dict(reader.metadata or {})),tokens)
            author=str((reader.metadata or {}).get('/Author','')).strip()
            if author and author.lower() not in {'anonymous','anonymous authors'}:reasons.append('non-anonymous PDF author metadata')
            for page in reader.pages:
                reasons+=text_issues(page.extract_text() or '',tokens)
                for entry in page.get('/Annots',[]):
                    action=entry.get_object().get('/A',{})
                    if action.get('/S') in ('/Launch','/JavaScript'):reasons.append('active PDF action')
                    reasons+=text_issues(str(action.get('/URI','')),tokens)
        if path.suffix.lower() in {'.jpg','.jpeg','.png','.gif'}:
            from PIL import Image
            with Image.open(path) as image:
                metadata=str(image.info)+' '+str(dict(image.getexif()))
            if LOCAL.search(metadata) or any(t.casefold() in metadata.casefold() for t in tokens):
                reasons.append('private identity in image metadata')
        if reasons:findings.append({'path':name,'issues':sorted(set(reasons))})
    return {'status':'PASS' if not findings else 'FAIL',**counts,'findings':findings,
        'scope':'author-identity links, local paths, credentials, CJK text and PDF text/metadata/links; not a guarantee against external identity inference'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args();report=check(args.root)
    print(json.dumps(report,indent=2));raise SystemExit(report['status']!='PASS')

if __name__=='__main__':main()
