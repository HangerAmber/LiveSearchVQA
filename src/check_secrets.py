"""Scan the staged tree without printing matching credential values."""
import os
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS=[re.compile(rb'sk-[A-Za-z0-9]{24,}'),
          re.compile(rb'(?:ARK_API_KEY|QWEN_API_KEY|DASHSCOPE_API_KEY)\s*=\s*[\"\']?[A-Za-z0-9_-]{24,}')]

def main():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    problems=[]
    secrets=[os.environ.get(k,'').encode() for k in ('ARK_API_KEY','QWEN_API_KEY','DASHSCOPE_API_KEY')]
    secrets=[s for s in secrets if len(s)>12]
    for name in filter(None,names):
        if name=='.env' or (name.startswith('.env.') and name!='.env.example') or name.startswith('.runs/'):
            problems.append((name,'private path')); continue
        if Path(name).suffix.lower() in {'.jpg','.jpeg','.png','.gif','.pdf','.pptx','.zip','.woff','.woff2'}:
            continue
        result=subprocess.run(['git','show',':'+name],cwd=ROOT,capture_output=True)
        if result.returncode: continue
        content=result.stdout
        if any(p.search(content) for p in PATTERNS) or any(s in content for s in secrets):
            problems.append((name,'possible credential'))
    for name,reason in problems: print(reason+': '+name)
    print(f'Staged-tree credential check: {len(problems)} findings')
    raise SystemExit(bool(problems))

if __name__=='__main__': main()
