"""Observe real public-button requests in isolated browser contexts; never mock traffic."""
import argparse
import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base', default='https://beta.smako.nu')
    parser.add_argument('--case')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, mobile, members, mode in (
            ('clean-balanced', False, False, 'balanced'),
            ('mobile-six-balanced', True, True, 'balanced'),
            ('mobile-six-cheapest', True, True, 'cheapest'),
        ):
            if args.case and name != args.case:
                continue
            context = browser.new_context(viewport={'width': 390 if mobile else 1280, 'height': 844 if mobile else 900})
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error, sink=errors: sink.append(str(error)))
            page.goto(args.base)
            page.locator('#onboarding-cta').click()
            page.locator('#servings').fill('2')
            page.locator('#max-stores').select_option('3')
            page.locator('details.advanced-options summary').click()
            available = page.locator('input[name="membership"]').evaluate_all('(es)=>es.map(e=>({id:e.value,checked:e.checked}))')
            if members:
                for checkbox in page.locator('input[name="membership"]').all():
                    checkbox.check()
            page.locator('#diversity-' + mode).check()
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
            page.on('response', lambda r, sink=responses: sink.append(r) if r.request.method == 'POST' and r.url.endswith('/api/plans') else None)
            page.locator('#submit-button').click()
            page.wait_for_function("!document.querySelector('#error-state').hidden || !document.querySelector('#results').hidden",timeout=610000)
            response = responses[-1] if responses else None
            request = requests[-1] if requests else None
            body = response.json() if response else None
            report = {'case': name, 'started_utc': utc, 'browser': 'Chromium isolated context', 'viewport': page.viewport_size,
                      'available_memberships': available, 'form': fields, 'url': request.url if request else None,
                      'method': request.method if request else None, 'request': request.post_data_json if request else None,
                      'status': response.status if response else None, 'body': body, 'seconds': round(time.monotonic()-started, 3),
                      'headers': {k: v for k, v in (response.headers if response else request.headers if request else {}).items() if k in {'x-request-id','x-error-code','content-type','retry-after'}},
                      'page_errors': errors}
            page.locator('#submit-button:not([disabled])').wait_for(timeout=10000)
            report['visible_text'] = page.locator('body').inner_text()
            report['service_workers'] = page.evaluate('async()=> (await navigator.serviceWorker.getRegistrations()).map(r=>r.active?.scriptURL)')
            page.screenshot(path=str(args.output / (name + '-after.png')), full_page=True)
            if response and response.status == 201:
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
            if response is None:
                break
        browser.close()


if __name__ == '__main__':
    main()
