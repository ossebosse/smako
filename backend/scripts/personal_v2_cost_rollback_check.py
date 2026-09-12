"""Read-compatible existing rollback; retain all databases and history."""

import json
from pathlib import Path

from app.main import app
from app.models import PlanRequest, PlanResponse
from fastapi.testclient import TestClient

for case in json.loads(Path('/evidence/predeclared-inputs.json').read_bytes()).values():
    PlanRequest.model_validate(case['request'])
for case in json.loads(Path('/evidence/final.json').read_bytes())['cases'].values():
    if 'plan' in case:
        PlanResponse.model_validate(case['plan'])
assert TestClient(app).post('/api/plans', json={}).status_code == 503
assert TestClient(app).put('/api/personal/pantry', json={}).status_code == 503
result = {'status': 'PASS', 'new_models_readable': True, 'writes_blocked': True,
          'database_restore': False, 'image': 'personal-v2-dinners-20260911c-rollback'}
Path('/evidence/rollback.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
