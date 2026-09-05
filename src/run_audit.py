"""Private API ledger. Never serialize credentials or HTTP headers."""
import base64
import hashlib
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

_state = threading.local()
_lock = threading.Lock()
ROOT = Path(__file__).resolve().parents[1]

def begin_item(item_id):
    _state.item_id = item_id
    _state.trials = []
    _state.last_call_id = None

def _safe(value):
    if isinstance(value, dict):
        return {k: _safe(v) for k, v in value.items()
                if k.lower() not in {'authorization', 'api_key', 'headers'}}
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, str) and value.startswith('data:image/') and ';base64,' in value:
        mime, encoded = value.split(';base64,', 1)
        return {'image_sha256': hashlib.sha256(base64.b64decode(encoded)).hexdigest(), 'mime': mime[5:]}
    return value

def append(kind, **fields):
    run_id = os.environ.get('LSVQA_RUN_ID')
    if not run_id:
        return None
    row = dict(record_id=uuid.uuid4().hex, kind=kind,
               at=datetime.now(timezone.utc).isoformat(),
               item_id=getattr(_state, 'item_id', None), **fields)
    target = ROOT / '.runs' / run_id / 'ledger.jsonl'
    with _lock:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('a', encoding='utf-8') as out:
            out.write(json.dumps(_safe(row), ensure_ascii=False) + '\n')
    return row['record_id']

def api(provider, request, response, elapsed):
    _state.last_call_id = append('api', provider=provider, model=request.get('model'),
        request=request, response=response, elapsed_seconds=round(elapsed, 4))

def trial(condition, member, prediction, correct, prompt, temperature):
    record = dict(condition=condition, member=member,
        prediction=prediction, correct=bool(correct), prompt=prompt,
        temperature=temperature, top_p=0.95,
        api_record_id=getattr(_state, 'prediction_call_id', None))
    _state.trials.append(record)
    append('trial', **record)

def mark_prediction():
    _state.prediction_call_id = getattr(_state, 'last_call_id', None)

def trials():
    return list(getattr(_state, 'trials', []))

