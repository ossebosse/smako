"""Ordinary production HTTP using a new, separate guest verification identity.

No retailer calls or order/purchase actions; secrets/full responses stay private.
"""
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

root = Path('/verification')
source = Path('/source')
phase = sys.argv[1]
base = os.environ['PUBLIC_BASE_URL'].rstrip('/')


def save(name, value):
    p = root / (name + '.json')
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    p.chmod(0o600)


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def audit_plan(plan, request):
    checks = plan['personal']['checks']
    audit = checks['checkout_audit']
    assert audit['passed'] and not audit['deficits'] and audit['totals_reconciled']
    assert not audit['total_reconciliation_errors']
    assert checks['purchase_planning_mode'] == request['purchase_planning_mode']
    limits = {m['meal_type']: m['limits'].get('min_protein_g') for m in request['personal']['meals']}
    for row in checks['nutrition']:
        minimum = limits[row['slot_id'].rsplit('-', 1)[0]]
        if minimum is not None:
            assert row['values']['protein_g'] >= minimum
    return {'checkout': audit['status'], 'totals_reconciled': True,
            'price_status': checks['purchase'], 'allergen_status': checks['allergy'],
            'nutrition': [{k: n[k] for k in ['slot_id', 'status', 'values']} for n in checks['nutrition']]}


cookies = json.loads((root / 'cookies.json').read_bytes()) if (root / 'cookies.json').exists() else {}
report = {'phase': phase, 'started_utc': datetime.now(UTC).isoformat(), 'cases': []}
with httpx.Client(base_url=base, timeout=900, cookies=cookies, headers={'Origin': base}) as client:
    ready = client.get('/ready')
    assert ready.status_code == 200, ('ready', ready.status_code)
    status = client.get('/api/price-universe/status').json()
    report['serving'] = {k: status.get(k) for k in ['universe_id', 'raw_product_count', 'freshness']}
    if phase == 'profiles':
        assert not cookies, 'Never reuse another identity for initial acceptance'
        inputs = json.loads((source / 'http-results.json').read_bytes())['cases']
        assert {x['case'] for x in inputs} == {'original-exact', 'original-estimated', 'plus-exact', 'plus-estimated'}
        created = []
        for row in inputs:
            request = row['request']
            assert request['max_stores'] == 2
            request['personal']['pantry_revision'] = client.get('/api/personal/state').json()['revision']
            started = time.monotonic()
            response = client.post('/api/plans', json=request)
            save('last-response', {'case': row['case'], 'http': response.status_code, 'body': response.json()})
            assert response.status_code == 201, (row['case'], response.status_code)
            value = response.json()
            basket = value['plan']['optimized_basket']
            assert basket['store_count'] <= 2
            retrieved = client.get('/api/plans/' + value['plan_id'])
            assert retrieved.status_code == 200 and retrieved.json()['plan'] == value['plan']
            created.append({'case': row['case'], 'saved': value, 'request': request})
            personal = value['plan']['personal']
            report['cases'].append({'case': row['case'], 'http': 201, 'seconds': round(time.monotonic()-started, 2),
                                    'total': basket['total'], 'store_count': basket['store_count'],
                                    'verification_status': basket.get('verification_status'),
                                    'plan_sha256': sha(value['plan']), 'request_sha256': sha(request),
                                    'checks': personal.get('checks'), 'plan_id': value['plan_id'],
                                    'identical_get': True})
            save('created', created)
            save('cookies', dict(client.cookies))
            save('profiles', report)
            print(json.dumps({'case': row['case'], 'http': 201, 'total': basket['total'], 'stores': basket['store_count']}), flush=True)
            time.sleep(9)
    elif phase == 'audit-profiles':
        created = json.loads((root / 'created.json').read_bytes())
        originals = {x['case']: x['request'] for x in json.loads((source / 'http-results.json').read_bytes())['cases']}
        for item in created:
            if item['case'] not in originals:
                continue
            original = originals[item['case']]
            original['personal']['pantry_revision'] = item['request']['personal']['pantry_revision']
            assert item['request'] == original, 'Profile constraints changed'
            meals = item['request']['personal']['meals']
            assert sum(m['count'] for m in meals) == 15
            assert sum(m['count'] * m['servings'] for m in meals) == 20
            report['cases'].append({'case': item['case'], **audit_plan(item['saved']['plan'], item['request'])})
    elif phase == 'representative':
        from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

        created = json.loads((root / 'created.json').read_bytes())
        inputs = json.loads((source / 'representative-bdc9-results.json').read_bytes())['cases']
        manifest = json.loads(Path('/prices/active/city-lund.json').read_bytes())
        prepared = PreparedPriceUniverseArtifact.model_validate_json((Path('/prices') / manifest['artifact_file']).read_bytes()).restore()
        products = [p.model_dump(mode='json') for p in prepared.universe.products]
        keys = {(prepared.universe.products[i].store_id, prepared.universe.products[i].product_id): key
                for key, indices in prepared.product_search_index.groups.items() for i in indices}
        if (root / 'representative.json').exists():
            report['cases'] = json.loads((root / 'representative.json').read_bytes())['cases']
        for row in inputs:
            if row['case'] in {c['case'] for c in report['cases']}:
                continue
            request = row['request']
            extra = request['personal']['extras'][0]
            matches = [p for p in products if p['store_id'] in request['allowed_store_ids']
                       and p['name'] == extra['query'] and p.get('purchase_terms')]
            assert matches, ('current representative missing', row['case'])
            if extra['kind'] == 'campaign':
                matches = [p for p in matches if p['purchase_terms']['variant_selection'] == 'required'
                           and p['purchase_terms']['complete_group_size'] == 2]
            if row['case'] == 'ica-whole-three-pack':
                matches = [p for p in matches if p['purchase_terms']['complete_group_size'] == 3]
            assert len(matches) == 1, ('ambiguous representative', row['case'], len(matches))
            product = matches[0]
            # Resolve identity through the immutable runtime's actual index,
            # including verified GTIN/package evidence and current context IDs.
            extra['product_key'] = keys[(product['store_id'], product['product_id'])]
            request['personal']['pantry_revision'] = client.get('/api/personal/state').json()['revision']
            response = client.post('/api/plans', json=request)
            save('representative-last-response', {'case': row['case'], 'http': response.status_code, 'body': response.json()})
            if row['case'] == 'ica-approx-laxsida-blocked-control':
                assert request['purchase_planning_mode'] == 'exact'
                assert response.status_code == 422 and response.json().get('detail')
                report['cases'].append({'case': row['case'], 'http': 422, 'controlled_exact_refusal': True})
                save(phase, report)
                time.sleep(9)
                continue
            assert response.status_code == 201, (row['case'], response.status_code)
            value = response.json()
            assert client.get('/api/plans/' + value['plan_id']).json()['plan'] == value['plan']
            created.append({'case': row['case'], 'request': request, 'saved': value})
            save('created', created)
            report['cases'].append({'case': row['case'], 'total': value['plan']['optimized_basket']['total'],
                                    'purchase_terms': product['purchase_terms'],
                                    'source_provenance': product['source_provenance'],
                                    **audit_plan(value['plan'], request)})
            save(phase, report)
            print(json.dumps({'case': row['case'], 'http': 201}), flush=True)
            time.sleep(9)
    elif phase == 'recalculate':
        created = json.loads((root / 'created.json').read_bytes())
        item = created[0]['saved']
        request = {'action': 'recalculate', 'revision': item['revision'],
                   'pantry_revision': client.get('/api/personal/state').json()['revision']}
        response = client.post('/api/personal/plans/' + item['plan_id'] + '/change', json=request)
        save('recalculate-response', {'http': response.status_code, 'body': response.json()})
        assert response.status_code == 200, ('recalculate', response.status_code)
        value = response.json()['saved']
        assert value['plan_id'] == item['plan_id'] and value['revision'] > item['revision']
        assert value['plan']['optimized_basket']['store_count'] <= 2
        report['audit'] = audit_plan(value['plan'], created[0]['request'])
        assert client.get('/api/plans/' + item['plan_id'], params={'revision': item['revision']}).json()['plan'] == item['plan']
        assert client.get('/api/plans/' + item['plan_id']).json()['plan'] == value['plan']
        report.update(http=200, previous_revision=item['revision'], new_revision=value['revision'],
                      old_revision_preserved=True, identical_new_get=True, new_plan_sha256=sha(value['plan']))
        created.append({'case': 'explicit-recalculation', 'saved': value})
        save('created', created)
    elif phase == 'campaign-guard':
        created = json.loads((root / 'created.json').read_bytes())
        item = next(x for x in created if x['case'] == 'hemkop-open-pizza')
        basket = item['saved']['plan']['optimized_basket']
        assert basket['verification_status'] == 'UNVERIFIED'
        rows = [i for s in basket['stores'] for i in s['items']]
        assert rows and all(i['conditional_variant_choice'] for i in rows)
        request = item['request']
        request['personal']['extras'][0]['kind'] = 'exact'
        request['personal']['pantry_revision'] = client.get('/api/personal/state').json()['revision']
        refused = client.post('/api/plans', json=request)
        save('campaign-exact-response', {'http': refused.status_code, 'body': refused.json()})
        assert refused.status_code == 422 and refused.json()['code'] == 'DATA_BLOCKED'
        report.update(open_choice_unverified=True, exact_ingredient_refused=422)
    elif phase == 'read-after-restart':
        created = json.loads((root / 'created.json').read_bytes())
        for item in created:
            saved = item['saved']
            r = client.get('/api/plans/' + saved['plan_id'], params={'revision': saved['revision']})
            assert r.status_code == 200 and r.json()['plan'] == saved['plan']
            assert saved['plan']['build_id'] == '08c137475d9ca96a6ef7673245a639c8c5c9e922'
            report['cases'].append({'case': item['case'], 'identical_plan': True, 'plan_sha256': sha(saved['plan'])})
        with httpx.Client(base_url=base, timeout=30) as stranger:
            denied = stranger.get('/api/plans/' + created[0]['saved']['plan_id'])
            assert denied.status_code == 403
            report['wrong_owner_status'] = 403
    else:
        raise ValueError(phase)
    save('cookies', dict(client.cookies))
report['finished_utc'] = datetime.now(UTC).isoformat()
save(phase, report)
print(json.dumps({'phase': phase, 'status': 'PASS', 'cases': len(report['cases'])}), flush=True)
