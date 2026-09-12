"""HTTPS acceptance using isolated synthetic guests; never persist cookies or identities."""

import json
from copy import deepcopy
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from backend.scripts.personal_v2_cost_audit import OUTPUT, inputs, save

BASE = 'https://beta.smako.nu'


def main():
    _, cases = inputs()
    out = {'transport': 'HTTPS API', 'cases': {}}
    for key, case in cases.items():
        opener = build_opener(HTTPCookieProcessor(CookieJar()))
        def call(path, data=None, method=None, opener=opener):
            req = Request(BASE + path, data=json.dumps(data).encode() if data is not None else None,
                          method=method, headers={'Origin': BASE, 'Content-Type': 'application/json'})
            try:
                with opener.open(req, timeout=180) as response:
                    return response.status, json.load(response)
            except HTTPError as error:
                return error.code, json.load(error)
        status, state = call('/api/personal/state')
        assert status == 200
        if key == 'pantry':
            status, _ = call('/api/personal/pantry', {'revision': state['revision'], 'items': case['stock']}, 'PUT')
            assert status == 200
            _, state = call('/api/personal/state')
        request = deepcopy(case['request'])
        request['personal']['pantry_revision'] = state['revision']
        status, response = call('/api/plans', request)
        if key == 'no_fish':
            assert status == 422
            row = {'status': 'DATA_BLOCKED', 'response': response}
        else:
            assert status == 201, (key, status, response)
            plan = response['plan']
            assert plan['data']['live_chain_requests'] == 0
            row = {'status': 'PASS', 'plan': plan}
            assert plan['optimized_basket']['total'] == {
                'original': 677.43, 'same_menu': 677.43, 'cheapest': 563.96,
                'pantry': 688.73, 'strict': 30.38,
            }[key]
            if key == 'strict':
                assert all(n['status'] == 'VERIFIED' for n in plan['personal']['checks']['nutrition'])
            else:
                assert len(plan['recipes']) == 5
                for n in plan['personal']['checks']['nutrition']:
                    assert n['values']['protein_g'] >= 20 and n['values']['kcal'] <= 800
            # Retained response can be reloaded without rewriting a revision.
            _, restored = call('/api/plans/' + response['plan_id'])
            assert restored['plan']['recipes'] == plan['recipes']
            row['saved_reload'] = True
        _, after = call('/api/personal/state')
        assert [(i['id'], i['quantity']) for i in state['items']] == [(i['id'], i['quantity']) for i in after['items']]
        row['stock_unchanged'] = True
        out['cases'][key] = row
        save(OUTPUT / 'https.json', out)
        print(json.dumps({'case': key, 'status': row['status'], 'http': status,
                          'cost': row.get('plan', {}).get('optimized_basket', {}).get('total')}), flush=True)


if __name__ == '__main__':
    main()
