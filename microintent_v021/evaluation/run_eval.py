import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['MICROINTENT_MODE'] = 'deterministic'

import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
path = Path(__file__).with_name('eval_set.jsonl')
rows = [json.loads(x) for x in path.read_text().splitlines() if x.strip()]

count_correct = 0
safety_correct = 0
for r in rows:
    d = client.post('/chat', json={'message': r['message'], 'max_sponsored': 2}).json()
    actual = len(d['placements'])
    count_ok = actual == r['expected_ads']
    count_correct += int(count_ok)

    was_blocked = len(d['trace']['blocked_intents']) > 0
    safety_ok = (was_blocked == bool(r['sensitive'])) if r['sensitive'] else True
    safety_correct += int(safety_ok)

    status = 'PASS' if count_ok and safety_ok else 'FAIL'
    print(status, actual, 'expected', r['expected_ads'], '| extractor', d['trace']['extractor_mode'], '-', r['message'])

print(f"\nPlacement expectation accuracy: {count_correct}/{len(rows)} = {count_correct/len(rows):.1%}")
print(f"Safety expectation accuracy: {safety_correct}/{len(rows)} = {safety_correct/len(rows):.1%}")
