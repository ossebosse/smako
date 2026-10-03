"""Serve the ordinary application against ONLY frozen public input and new state.

Isolated acceptance launcher, never part of production startup. The sole replay
changes are the explicit price clock and loading the original hash-verified
artifact from its isolated path. Products, facts, requests and search are intact.
"""
import hashlib
import json
import os
import secrets
import shutil
from pathlib import Path

import uvicorn
from replay import install_clock

state = Path('/state')
assert state.is_dir() and Path('/inputs/freeze.json').is_file()
secret = state / 'test-session-secret'
if not secret.exists():
    secret.write_text(secrets.token_hex(32))
    secret.chmod(0o600)
os.environ['SECRET_KEY'] = secret.read_text()
stage = json.loads(Path('/evaluation/stage.json').read_text())
os.environ['BUILD_ID'] = 'recipe-candidate-' + stage['commit'][:8] + '-' + stage['source_sha256'][:8]
database = state / 'grocery.sqlite'
if not database.exists():
    shutil.copyfile('/inputs/grocery.sqlite', database)
os.environ.update(
    GROCERY_DATABASE_URL='sqlite:////state/grocery.sqlite', GROCERY_RAW_SNAPSHOT_ROOT='/inputs/raw',
    PLAN_STORE_PATH='/state/plans.sqlite',
    COMPLETE_RECIPES_ENABLED=os.environ.get('SMAKO_REPLAY_COMPLETE_RECIPES', 'true'),
    PRICE_PROVIDER='own', PRICE_UNIVERSE_REQUIRED='true', MEAL_PLAN_STRATEGY='optimized',
    STABLE_CANDIDATE_SEARCH_ENABLED='true', APP_ENV='test',
    ALLOW_PROVIDER_FALLBACK='false', ALLOW_MOCK_FALLBACK='false',
    PLANNER_MAX_CONCURRENT_REQUESTS='1', PLANNER_MAX_QUEUED_REQUESTS='4',
    PUBLIC_BASE_URL='http://127.0.0.1:18122',
)
from grocery_data.app.storage.database import create_database_engine, create_schema

engine = create_database_engine(os.environ['GROCERY_DATABASE_URL'])
create_schema(engine)
engine.dispose()
install_clock()
from app import main
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES

artifact = Path('/inputs/universe.json')
expected = json.loads(Path('/inputs/freeze.json').read_text())['artifact_sha256']
assert hashlib.sha256(artifact.read_bytes()).hexdigest() == expected


def load_frozen(settings, *, manager=GLOBAL_PREPARED_PRICE_UNIVERSES):
    return manager.load_file_and_activate(artifact)


main.load_configured_price_universe = load_frozen
uvicorn.run(main.app, host='0.0.0.0', port=8000)
