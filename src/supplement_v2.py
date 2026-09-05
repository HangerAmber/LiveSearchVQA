"""Explicit, bounded supplementation from a private prior-run ledger.

No schedule and no automatic promotion. Every proposed item runs the complete
P0/P1/P2 gates, and outputs remain staging artifacts until independently validated.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source-run',required=True)
    p.add_argument('--mode',choices=['alternative-fact','typography-repair'],required=True)
    p.add_argument('--eligibility-manifest',help='Freeze the exact article IDs from an earlier run manifest')
    p.add_argument('--output',required=True)
    p.add_argument('--run-id')
    p.add_argument('--build-date',default=datetime.now().date().isoformat())
    p.add_argument('--workers',type=int,default=8)
    p.add_argument('--target',type=int,default=200)
    args=p.parse_args()
    if Path(args.output).name!=args.output or args.output=='benchmark_v2.json':
        p.error('Use a staging filename inside data/, not the published benchmark')
    source=(ROOT/'.runs'/args.source_run).resolve()
    if not source.is_relative_to((ROOT/'.runs').resolve()):p.error('Invalid source run')
    os.environ['LSVQA_RUN_ID']=args.run_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+args.mode
    os.environ['LSVQA_BUILD_DATE']=args.build_date
    os.environ.setdefault('LSVQA_ENGLISH_RATIO','1.0')
    from daily import require_credentials
    require_credentials()
    import generate_v2 as gen
    import ark_api,run_audit
    if gen.CERT_SAMPLES!=4:p.error('Supplementation requires the full 3-model-x-4 profile')
    rows=[json.loads(s) for s in (source/'ledger.jsonl').read_text(encoding='utf-8').splitlines()]
    rejected={r['item_id']:r['reason'] for r in rows if r['kind']=='rejection'}
    certified={r['item_id'] for r in rows if r['kind']=='source_snapshot'}
    cache={}
    for row in rows:
        if row['kind']=='api' and row.get('provider')=='ark' and 'You construct ONE' in str(row.get('request',{}).get('input')):
            raw=ark_api._extract_text(row.get('response',{}))
            parsed=ark_api._parse(raw)
            if isinstance(parsed,dict):cache[row['item_id']]={'raw':raw,'proposal':parsed,'record_id':row['record_id']}
    eligible=set(rejected)-certified
    if args.mode=='typography-repair':
        eligible={key for key in eligible if rejected[key]=='drop_exact_evidence_offset'}
    if args.eligibility_manifest:
        frozen=json.loads(Path(args.eligibility_manifest).read_text(encoding='utf-8'))
        eligible &= set(frozen.get('eligible_article_ids',frozen.get('article_ids',[])))
    eligible &= set(cache)
    original_fresh=gen._fresh_articles
    def select(articles):
        output=[]
        for article in original_fresh(articles):
            key=article['id']
            if key not in eligible:continue
            if args.mode=='alternative-fact':
                previous=cache[key]['proposal']
                article['generation_feedback']={k:previous.get(k,'') for k in ('question','answer','evidence')}
                article['generation_feedback']['rejection']=rejected[key]
            output.append(article)
        return output
    gen._fresh_articles=select
    if args.mode=='typography-repair':
        original_call=ark_api.call_image
        def proposal_replay(image_path,prompt,**kwargs):
            key=Path(image_path).stem
            if prompt.startswith('You construct ONE') and key in cache:
                run_audit.append('proposal_replay',source_run=args.source_run,
                    source_api_record_id=cache[key]['record_id'],reason='exact typography repair; all checks rerun')
                return cache[key]['raw']
            return original_call(image_path,prompt,**kwargs)
        ark_api.call_image=proposal_replay
    folder=ROOT/'.runs'/os.environ['LSVQA_RUN_ID']
    folder.mkdir(parents=True,exist_ok=True)
    manifest={'run_id':os.environ['LSVQA_RUN_ID'],'started_at':datetime.now(timezone.utc).isoformat(),
        'source_run':args.source_run,'mode':args.mode,'eligible_article_ids':sorted(eligible),
        'thresholds_changed':False,'code_sha256':{f.name:hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted((ROOT/'src').glob('*.py'))}}
    manifest_path=folder/'run_manifest.json'
    if manifest_path.exists():raise FileExistsError('Choose a new run ID; prior manifests are immutable')
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    size,_,_=gen.build(target=args.target,workers=args.workers,output_name=args.output,resume=True)
    print('Supplement completed:',size,'staging items; no promotion performed.')

if __name__=='__main__':main()
