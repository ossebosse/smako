"""Observe real public-button requests in isolated browser contexts; never mock traffic."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def select_area(page, base, postal_code):
    """Use the visible municipal selector when postal scope is an internal key."""
    if page.locator('#municipality').count():
        response = page.request.get(base.rstrip('/') + '/api/municipalities')
        assert response.ok
        area = next(row for row in response.json()['municipalities']
                    if row['postal_code'] == postal_code and row['available'])
        page.locator('#municipality').select_option(area['municipality_code'])
        assert page.locator('#postal-code').input_value() == postal_code
    else:
        page.locator('#postal-code').fill(postal_code)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', default='https://beta.smako.nu')
    parser.add_argument('--case')
    parser.add_argument('--postal-code', default='22350')
    parser.add_argument('--store-context', help='Select exactly this published context via its checkbox')
    parser.add_argument('--browser', choices=['chromium', 'webkit'], default='chromium')
    parser.add_argument('--reject-postal-first')
    parser.add_argument('--ignore-https-errors', action='store_true', help='Only for isolated self-signed candidate TLS')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = getattr(pw, args.browser).launch()
        for name, mobile, members, mode in (
            ('clean-balanced', False, False, 'balanced'),
            ('mobile-six-balanced', True, True, 'balanced'),
            ('mobile-six-cheapest', True, True, 'cheapest'),
        ):
            if args.case and name != args.case:
                continue
            context = browser.new_context(viewport={'width': 390 if mobile else 1280, 'height': 844 if mobile else 900},
                                          is_mobile=mobile, has_touch=mobile, ignore_https_errors=args.ignore_https_errors)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error, sink=errors: sink.append(str(error)))
            page.goto(args.base)
            page.locator('#onboarding-cta').click()
            select_area(page, args.base, args.postal_code)
            page.locator('#recipes').select_option('5')
            page.locator('#servings').fill('2')
            page.locator('#max-stores').select_option('3')
            page.locator('details.advanced-options summary').click()
            available = page.locator('input[name="membership"]').evaluate_all('(es)=>es.map(e=>({id:e.value,checked:e.checked}))')
            if members:
                for checkbox in page.locator('input[name="membership"]').all():
                    checkbox.check()
            page.locator('#diversity-' + mode).check()
            rejection = None
            if args.reject_postal_first:
                assert page.locator('#postal-code').is_visible(), (
                    'Postal input rejection is not a user flow in municipality mode'
                )
                page.locator('#postal-code').fill(args.reject_postal_first)
                rejected_at = time.monotonic()
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/plans')) as observed:
                    page.locator('#submit-button').click()
                rejected = observed.value
                page.locator('#error-state:visible').wait_for()
                rejection = {
                    'url': rejected.url, 'method': rejected.request.method,
                    'request': rejected.request.post_data_json, 'status': rejected.status,
                    'body': rejected.json(), 'seconds': round(time.monotonic()-rejected_at, 3),
                    'headers': {k: v for k, v in rejected.headers.items() if k in {'x-request-id', 'x-error-code'}},
                    'message': page.locator('#error-message').inner_text(),
                    'postal_invalid': page.locator('#postal-code').get_attribute('aria-invalid'),
                    'submit_enabled': page.locator('#submit-button').is_enabled(),
                }
                (args.output/(name+'-initial-rejection.json')).write_text(json.dumps(rejection,ensure_ascii=False,indent=2),encoding='utf-8')
                page.screenshot(path=str(args.output/(name+'-initial-rejection.png')),full_page=True)
                assert rejected.status == 422 and rejection['postal_invalid'] == 'true' and rejection['submit_enabled']
                assert rejection['body']['detail'][0]['loc'] == ['body','postal_code']
                assert page.locator('#postal-code').input_value() == args.reject_postal_first
                assert page.locator('#servings').input_value() == '2' and page.locator('#max-stores').input_value() == '3'
                select_area(page, args.base, args.postal_code)
            if args.store_context:
                selected = page.locator('[id="context-' + args.store_context + '"]')
                selected.wait_for(state='visible', timeout=30000)
                for checkbox in page.locator('input[id^="context-"]:checked').all():
                    checkbox.uncheck()
                selected.check()
            fields = page.locator('#plan-form input, #plan-form select').evaluate_all('(es)=>es.map(e=>({name:e.name,id:e.id,type:e.type,value:e.value,checked:e.checked}))')
            page.screenshot(path=str(args.output / (name + '-before.png')), full_page=True)
            started = time.monotonic()
            utc = datetime.now(UTC).isoformat()
            def failed(req, name=name, started=started, utc=utc, page=page):
                if req.method == 'POST' and req.url.endswith('/api/plans'):
                    evidence = {'started_utc': utc, 'url': req.url, 'method': req.method,
                                'request': req.post_data_json, 'failure': req.failure,
                                'seconds': round(time.monotonic()-started,3)}
                    (args.output / (name+'-network-failure.json')).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
                    print(json.dumps(evidence),flush=True)
            page.on('requestfailed', failed)
            responses = []
            requests = []
            page.on('request', lambda r, sink=requests: sink.append(r) if r.method == 'POST' and r.url.endswith('/api/plans') else None)
            page.on('response', lambda r, sink=responses: sink.append(r) if (r.request.method == 'POST' and r.url.endswith('/api/plans')) or '/api/plan-jobs/' in r.url else None)
            page.locator('#submit-button').click()
            page.locator('#error-state:visible, #results:visible').first.wait_for(state='visible',timeout=610000)
            response = responses[-1] if responses else None
            request = requests[-1] if requests else None
            body = response.json() if response else None
            report = {'case': name, 'started_utc': utc, 'browser': args.browser + ' isolated context', 'viewport': page.viewport_size,
                      'mobile_emulation': mobile, 'physical_iphone_test': False,
                      'available_memberships': available, 'form': fields, 'url': request.url if request else None,
                      'method': request.method if request else None, 'request': request.post_data_json if request else None,
                      'request_headers': {k: v for k, v in (request.headers if request else {}).items()
                                          if k in {'accept', 'content-type', 'prefer', 'x-request-id'}},
                      'status': response.status if response else None, 'body': body, 'seconds': round(time.monotonic()-started, 3),
                      'headers': {k: v for k, v in (response.headers if response else request.headers if request else {}).items() if k in {'x-request-id','x-error-code','content-type','retry-after'}},
                      'page_errors': errors}
            report['initial_rejection'] = rejection
            initial = next((r for r in responses if r.request.method == 'POST'), None)
            report['initial_response'] = {'status': initial.status, 'body': initial.json() if initial.status == 202 else None,
                                          'request_id': initial.headers.get('x-request-id')} if initial else None
            report['transport'] = [{'url': r.url, 'method': r.request.method, 'status': r.status,
                                    'request_id': r.headers.get('x-request-id'), 'error_code': r.headers.get('x-error-code'),
                                    'elapsed_ms': r.request.timing['responseEnd']}
                                   for r in responses]
            if response and response.status < 400:
                page.locator('#submit-button:not([disabled])').wait_for(timeout=10000)
            report['submit_enabled_after_response'] = page.locator('#submit-button').is_enabled()
            report['visible_text'] = page.locator('body').inner_text()
            report['service_workers'] = page.evaluate('async()=> (await navigator.serviceWorker.getRegistrations()).map(r=>r.active?.scriptURL)')
            page.screenshot(path=str(args.output / (name + '-after.png')), full_page=True)
            (args.output / (name + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            if response and response.status == 201:
                plan = body['plan']
                basket = plan['optimized_basket']
                recipes = plan['recipes']
                cards = page.locator('#recipes-list details')
                for card in cards.all():
                    if card.get_attribute('open') is None:
                        card.locator('summary').click()
                rows = [item for group in basket['stores'] for item in group['items']]
                report['acceptance'] = {
                    'postal_scope_preserved': body['request']['postal_code'] == args.postal_code,
                    'selected_store_filter': args.store_context is None or (
                        request.post_data_json.get('allowed_store_ids') == [args.store_context]
                        and {store['store_id'] for store in basket['stores']} <= {args.store_context}
                    ),
                    'five_dinners_two_servings': len(recipes) == 5 and all(r['servings'] == 2 for r in recipes),
                    'ten_total_portions': plan['portions'] == 10,
                    'full_recipes': all(r['instructions'] and all(step.strip() for step in r['instructions']) and r['ingredients'] and all(i['quantity'] > 0 and i['unit'] for i in r['ingredients']) for r in recipes),
                    'five_visible_recipe_cards': cards.count() == 5 and page.locator('.instructions-list:visible').count() == 5,
                    'quantities_rendered': all(v.strip() not in {'', '\u2014'} for v in page.locator('.ingredient-amount').all_text_contents()),
                    'shopping_rows_rendered': page.locator('#store-groups tbody tr').count() == len(rows) and bool(rows),
                    'max_three_stores': basket['max_stores'] == 3 and 0 < basket['store_count'] <= 3,
                    'exact_request': body['request']['purchase_planning_mode'] == 'exact' and not body['request'].get('personal'),
                    'memberships_preserved': sorted(body['request']['membership_programs']) == sorted(request.post_data_json['memberships']),
                    'selected_diversity_preserved': plan['diversity_mode'] == mode,
                    'verified_basket': basket['verification_status'] == 'VERIFIED',
                    'total_reconciled': basket['total_reconciled'] and basket['total'] > 0,
                    'basket_audit_passed': plan['quality']['basket_audit']['passed'],
                    'nutrition_quality_passed': plan['quality']['nutrition']['status'] == 'PASS',
                    'quality_label_visible': page.locator('#basket-verification-title').is_visible(),
                }
                report['quality_label'] = page.locator('#basket-verification').inner_text()
                report['recipe_text'] = page.locator('#recipes-list').inner_text()
                report['shopping_text'] = page.locator('#shopping-section').inner_text()
                page.locator('#menu-section').screenshot(path=str(args.output/(name+'-recipes.png')))
                page.locator('#shopping-section').screenshot(path=str(args.output/(name+'-shopping.png')))
                report['plan_sha256'] = hashlib.sha256(json.dumps(body['plan'],sort_keys=True).encode()).hexdigest()
                with page.expect_response(lambda r: r.request.method == 'GET' and '/api/plans/' in r.url, timeout=30000) as readback:
                    page.reload()
                loaded = readback.value.json()
                report['identical_reload'] = loaded['plan'] == body['plan'] and loaded['request'] == body['request']
                page.locator('#results').wait_for(state='visible')
                report['reload_text'] = page.locator('body').inner_text()
            (args.output / (name + '.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({k: report[k] for k in ['case','status','seconds','headers']}), flush=True)
            if response and response.status >= 400:
                print(json.dumps(body,ensure_ascii=False), flush=True)
            context.close()
            if args.store_context:
                assert response is not None and response.status == 201 and not errors, report['status']
                assert report.get('acceptance'), 'Scoped menu did not produce acceptance evidence'
            if report.get('acceptance'):
                assert all(report['acceptance'].values()) and report['identical_reload'], report['acceptance']
            if response is None:
                break
        browser.close()


if __name__ == '__main__':
    main()
