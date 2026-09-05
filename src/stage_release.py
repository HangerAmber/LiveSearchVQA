"""Stage only public release artifacts and images referenced by those artifacts."""
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def stage():
    files=[]
    for pattern in ['index.html','demo.html','data/benchmark_v2.json','data/stats_v2.json',
                    'data/quality_report_v2.json','data/archive_v2/*.json','data/releases/*.json']:
        files.extend(ROOT.glob(pattern))
    json_files=[p for p in files if p.name=='benchmark_v2.json' or p.parent.name=='archive_v2']
    showcase=ROOT/'data/showcase_cases.json'
    if showcase.exists(): json_files.append(showcase)
    for path in json_files:
        payload=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(payload,dict): payload=payload.get('items',payload.get('questions',[]))
        for item in payload:
            photo=(ROOT/'data'/item['image']).resolve()
            if not photo.is_relative_to((ROOT/'data/images').resolve()):
                raise ValueError('Image escaped the public image directory')
            if not photo.exists(): raise FileNotFoundError(photo)
            files.append(photo)
    names=sorted({str(p.relative_to(ROOT)) for p in files if p.exists()})
    for start in range(0,len(names),60):
        subprocess.run(['git','add','--',*names[start:start+60]],cwd=ROOT,check=True)
    print(f'Staged {len(names)} allowlisted public paths; no raw crawls or private ledgers.')

if __name__=='__main__': stage()
