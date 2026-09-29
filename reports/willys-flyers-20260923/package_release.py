"""Freeze the reviewed delta and derive store outcomes from retained evidence."""
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

R = Path(__file__).resolve().parent
REPO = R.parents[1]


def read(p):
    return json.loads(p.read_bytes())


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    original = read(R / 'initial-state.json')
    changed = [name for name, h in original.items() if not (REPO / name).exists() or digest(REPO / name) != h]
    intended = {
        'backend/app/services/basket_calculator.py',
        'backend/app/services/personal_source_facts.py',
        'backend/app/services/production_price_universe_build.py',
        'grocery_data/__main__.py', 'grocery_data/app/api/catalog.py',
        'grocery_data/app/services/offer_rows.py', 'deploy/scripts/run_daily_refresh.py',
    }
    assert set(changed) == intended, changed
    new = [
        'grocery_data/app/connectors/willys/flyer_inventory.py',
        'grocery_data/app/connectors/willys/flyer_client.py',
        'grocery_data/app/connectors/willys/flyer_offers.py',
        'grocery_data/app/connectors/willys/fixtures/flyer_review_20260923.json',
        'grocery_data/app/services/willys_flyer_job.py',
        'grocery_data/scripts/collect_willys_flyers.py',
        'backend/app/providers/willys_flyers.py',
        'grocery_data/tests/test_willys_flyers.py',
        'backend/tests/test_willys_flyer_wiring.py',
        'backend/tests/test_willys_flyer_purchase.py',
        'backend/tests/fixtures/willys-flyers-20260923.json',
        'docs/willys_flyers.md',
    ]
    files = {}
    for name in sorted([*changed, *new]):
        target = R / 'package-code' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / name, target)
        files[name] = {'sha256': digest(target), 'before_sha256': original.get(name)}
    save(R / 'PACKAGE.json', {
        'created_at': datetime.now(UTC).isoformat(), 'production_activation': False,
        'changed_existing_files': changed, 'unchanged_start_files': len(original)-len(changed),
        'files': files, 'preservation': 'All other files hashed at task start remain byte-identical. Prior source reports/release packages were only read.',
    })
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
    from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
    rows, runtimes = [], []
    for code, city in [('1281', 'Lund'), ('1280', 'Malmö')]:
        root = R / f'runtime-final-{code}'
        accept = read(root / 'ACCEPTANCE.json')
        assert accept['status'] == 'PASS'
        runtime = read(root / 'result-recovery.json')
        purchases = read(root / 'purchases.json')
        assert purchases['audits'] == (3 if code == '1281' else 18)
        artifact = PreparedUniverseArtifactStore(root/'price-universes').resolve_active_artifact(city, verify_hash=True)
        prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact.read_bytes()).restore()
        prices = [p for p in prepared.universe.products if p.chain == 'willys' and p.source_provenance.source_channel == 'offers']
        counts = Counter(p.source_provenance.provider_store_id for p in prices)
        schedules = {s['store_id']: s for s in runtime['source_plan']['stores']}
        live = read(R / f'final-live-{code}/collection/coverage.json')
        for store in live['stores']:
            q = store['qualification']
            reasons = Counter(f['error_message'] for f in q['retained_parser_quarantine'])
            reasons.update(d['blockers'][0] for d in q['decisions'] if d['blockers'])
            assert sum(reasons.values()) == store['quarantine_count']
            examples = []
            for p in prices:
                if p.source_provenance.provider_store_id != store['store_id'] or p.name not in {'Pågenlimpan', 'Kycklingbröstfilé Sverige', 'Pizzadeg'}:
                    continue
                examples.append({'name': p.name, 'brand': p.brand, 'package_quantity': p.package_quantity,
                    'package_unit': p.package_unit, 'ordinary_price': p.price,
                    'offers': [o.model_dump(mode='json') for o in p.offers],
                    'official_url': store['source_url']})
            assert len(examples) == 3
            rows.append({
                'municipality_code': code, 'municipality': city, 'municipality_status': store['municipality_status'],
                'store_id': store['store_id'], 'store': store['name'], 'official_source': store['source_url'],
                'source_format': store['source_format'], 'pages': 12 if store['store_id'] == '2352' else 4,
                'price_channel': store['price_channel'], 'coverage': store['coverage'],
                'retrieved_text_advertisements': q['advertisements'], 'retrieved_expanded_records': store['retrieved_products'],
                'own': store['own'], 'price_universe_current': counts[store['store_id']],
                'quarantine': store['quarantine_count'], 'quarantine_primary_reasons': dict(reasons),
                'expired_since_collection': store['own'] - counts[store['store_id']],
                'observed_at': store['observed_at'], 'snapshot_id': store['snapshot_id'],
                'next_fetch_at': schedules[store['store_id']]['next_fetch_at'],
                'price_hard_stop_at': schedules[store['store_id']]['price_hard_stop_at'],
                'checkout_audits': 3, 'nutrition': 'no exact approved declaration identity; strict recipe nutrition rejected',
                'examples': examples,
            })
        runtimes.append({'code': code, 'live_price_requests': live['external_price_requests'],
            'acceptance': accept, 'baseline_chain_counts': runtime['all_chain_counts'],
            'ordinary_runner_status': runtime['runner']['status'], 'purchase_date': purchases['purchase_date']})
    tests = {}
    for name in ['regression.xml', 'final-tests.xml', 'contract-regression.xml', 'facts-regression.xml']:
        for t in ET.parse(R/name).getroot().iter('testcase'):
            tests[t.attrib['classname']+'::'+t.attrib['name']] = {
                'result': 'failed' if t.find('failure') is not None or t.find('error') is not None else 'passed',
                'evidence': name,
            }
    assert all(t['result'] == 'passed' for t in tests.values())
    save(R/'RESULT.json', {'created_at': datetime.now(UTC).isoformat(), 'stores': rows, 'runtime': runtimes,
        'test_cases_latest': tests, 'unique_test_count': len(tests),
        'historical_test_gap': 'test_reviewed_lidl_nutrition.py: missing historical adapter/fixtures; not counted as passed',
        'production_activation': False})
    print(json.dumps({'stores':len(rows), 'own':sum(r['own'] for r in rows),
        'price_universe':sum(r['price_universe_current'] for r in rows), 'unique_tests':len(tests)}))


if __name__ == '__main__':
    main()
