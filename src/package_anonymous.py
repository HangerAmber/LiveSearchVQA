"""Build a history-free anonymous review ZIP; no API calls or source mutation."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path
from check_anonymity import ROOT,check,public_paths

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('anonymous-review.zip'))
    args=parser.parse_args();report=check()
    if report['status']!='PASS':raise RuntimeError('Anonymity check failed; run check_anonymity.py for details')
    referenced=set()
    for pattern in ['data/benchmark_v2.json','data/archive_v2/*.json','data/previews/*.json','data/showcase_cases.json']:
        for p in ROOT.glob(pattern):
            items=json.loads(p.read_text(encoding='utf-8'))
            if isinstance(items,dict):items=items.get('items',items.get('questions',[]))
            for item in items:
                photo=(ROOT/'data'/item['image']).resolve()
                if not photo.is_relative_to((ROOT/'data/images').resolve()) or not photo.is_file():
                    raise ValueError('Missing or unsafe referenced image')
                referenced.add(photo)
    paths=[p for p in public_paths() if 'data/images/' not in p.relative_to(ROOT).as_posix() or p.resolve() in referenced]
    output=args.output.resolve()
    if output.exists():raise FileExistsError('Choose a new archive name; existing archives are not overwritten')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in paths:
            name=p.relative_to(ROOT).as_posix()
            if name.startswith('.github/') or name in {'data/articles.json','data/image_hashes.json'}:continue
            info=zipfile.ZipInfo('LiveSearchVQA-anonymous/'+name,date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=0o100644<<16
            archive.writestr(info,p.read_bytes())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        count=len(archive.namelist())
        assert not any('/.git/' in n or '/.runs/' in n or n.endswith('/.env') for n in archive.namelist())
    print(json.dumps({'archive':output.name,'files':count,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
        'history_included':False,'credentials_included':False,'anonymity_check':report['status']},indent=2))

if __name__=='__main__':main()
