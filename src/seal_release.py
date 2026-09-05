"""Seal an actual validated release; publish counts/hashes, not private raw logs."""
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def seal():
    data=ROOT/'data'
    items=json.loads((data/'benchmark_v2.json').read_text(encoding='utf-8'))
    report=json.loads((data/'quality_report_v2.json').read_text(encoding='utf-8'))
    if report['status']!='PASS' or report['items']!=len(items) or len(items)!=200:
        raise ValueError('Only a validated complete 200-item release may be sealed')
    day=items[0]['build_date']
    run_ids=sorted({i['certification'].get('run_id') for i in items})
    if not all(run_ids): raise ValueError('Missing run identifiers')
    responses=0; errors=0; usage=defaultdict(Counter); rejections=Counter(); ledgers=[]
    for run_id in run_ids:
        ledger=ROOT/'.runs'/run_id/'ledger.jsonl'
        if not ledger.exists(): raise ValueError('Missing private ledger')
        records=[json.loads(s) for s in ledger.read_text(encoding='utf-8').splitlines()]
        trial_ids={r['api_record_id'] for r in records if r['kind']=='trial'}
        for item in items:
            if item['certification']['run_id'] == run_id:
                if any(t['api_record_id'] not in trial_ids for t in item['certification']['trials']):
                    raise ValueError('Public trial missing from private ledger')
        for row in records:
            if row['kind']=='api':
                responses+=1
                for k,v in (row.get('response',{}).get('usage',{}) or {}).items():
                    if isinstance(v,(int,float)): usage[row['provider']][k]+=v
            if row['kind']=='transport_error': errors+=1
            if row['kind']=='rejection': rejections[row.get('reason','unknown')]+=row.get('amount',1)
        ledgers.append({'run_id':run_id,'sha256':sha(ledger),'records':len(records),
                        'access':'private; source copyright and privacy restrictions'})
    manifest={'schema':'livesearchvqa-public-release-20260905','build_date':day,
        'sealed_at':datetime.now(timezone.utc).isoformat(),'items':len(items),
        'benchmark_sha256':sha(data/'benchmark_v2.json'),
        'validation_sha256':sha(data/'quality_report_v2.json'),
        'accepted_ids_sha256':hashlib.sha256('\n'.join(sorted(i['id'] for i in items)).encode()).hexdigest(),
        'api_json_responses_recorded':responses,'transport_errors_recorded':errors,
        'usage_by_provider':dict(usage),'actual_billed_usd':None,
        'billing_note':'Provider invoice unavailable; token counts are not measured dollar cost.',
        'rejection_counters':dict(rejections),'rejection_note':'Auxiliary score counters may overlap.',
        'human_review_status':'not_yet_audited','held_out_evaluation_status':'not_run',
        'private_ledgers':ledgers,
        'code_sha256':{p.name:sha(p) for p in sorted((ROOT/'src').glob('*.py'))}}
    out=data/'releases'/f'{day}.json'; out.parent.mkdir(exist_ok=True)
    if out.exists(): raise FileExistsError('Refusing to overwrite a sealed manifest')
    out.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    print('Sealed public manifest:',out)

if __name__=='__main__': seal()
