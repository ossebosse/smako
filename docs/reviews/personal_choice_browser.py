"""One Chromium E probe against the isolated frozen server, with a real A seed.

Registration credentials and saved capabilities exist only in process memory.
No API or planning result is mocked; the ordinary tab draft restores E controls.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    requests = json.loads(args.protocol.read_text(encoding='utf8'))['requests']
    report = {'scope': 'Chromium UI -> tunneled local HTTP -> ordinary job/save -> visible shopping list and saved GET',
              'status': 'starting', 'exact_E_prepared': False}
    args.output.mkdir(parents=True, exist_ok=False)

    def write():
        (args.output / 'browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')

    write()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        report['browser'] = browser.version
        context = browser.new_context(viewport={'width': 1365, 'height': 1000})
        page = context.new_page()
        try:
            response = context.request.post(args.url + '/api/account/register', data={
                'email': secrets.token_hex(12) + '@example.invalid', 'password': secrets.token_urlsafe(32)})
            assert response.status == 201, response.status
            del response
            started = time.perf_counter()
            response = context.request.post(args.url + '/api/plans', data=requests['A'], headers={'Prefer': 'respond-async'})
            assert response.status == 202, response.status
            status_url = response.json()['status_url']
            while response.status == 202 and time.perf_counter() - started < 300:
                time.sleep(.2)
                response = context.request.get(args.url + status_url)
            report['A_seed_seconds'] = time.perf_counter() - started
            if response.status == 202:
                context.request.delete(args.url + status_url)
                raise TimeoutError('A seed reached the five-minute boundary')
            assert response.status == 201, response.status
            del response
            # Existing tab-local recovery is an ordinary supported UI input.
            # It restores values only; no E plan or certificate has been built.
            page.add_init_script('sessionStorage.setItem("smako.personal.requestDraft", ' + json.dumps(json.dumps(requests['E'])) + ');')
            page.goto(args.url + '/personal#choices')
            expect(page.locator('#check-postcode')).to_be_enabled(timeout=30000)
            page.locator('#customer-postcode').fill('21120')
            page.locator('#check-postcode').click()
            expect(page.locator('#confirm-location')).to_be_enabled(timeout=30000)
            page.locator('#confirm-location').click()
            expect(page.locator('#dinner-count-value')).to_have_value('5')
            expect(page.locator('#dinner-servings-value')).to_have_value('4')
            expect(page.locator('#cuisine-italian')).to_be_checked()
            expect(page.locator('#cuisine-indian')).to_be_checked()
            expect(page.locator('#dinner-min_protein_g-value')).to_have_value('40')
            expect(page.locator('#dinner-chicken-value')).to_have_value('3')
            expect(page.locator('#dinner-vegetarian-value')).to_have_value('2')
            captured = []
            page.on('request', lambda req: captured.append(req.post_data_json) if req.url.endswith('/api/plans') and req.method == 'POST' else None)
            started = time.perf_counter()
            with page.expect_response(lambda r: ('/api/plan-jobs/' in r.url and r.status != 202)
                or (r.url.endswith('/api/plans') and r.request.method == 'POST' and r.status != 202), timeout=300000) as final:
                page.locator('#choice-submit').click()
            response = final.value
            report['click_to_terminal_response_seconds'] = time.perf_counter() - started
            report['http_status'] = response.status
            report['submitted_request'] = captured[-1] if captured else None
            payload = response.json()
            if response.status != 201:
                report.update(status='BLOCKED', error=payload)
                write()
                return
            checks = payload['plan']['personal']['checks']
            assert checks['checkout_audit']['passed']
            report['audit_passed'] = True
            report['paid'] = payload['plan']['optimized_basket']['total']
            report['normalized_request'] = payload['request']
            expect(page.locator('#plan-content')).to_contain_text('middag', timeout=30000)
            page.locator('button[data-open="shopping"]').first.click()
            expect(page.locator('#shopping-content')).not_to_contain_text('Ingen beräknad korg ännu.')
            report['click_to_visible_shopping_seconds'] = time.perf_counter() - started
            reread = context.request.get(args.url + '/api/plans/' + payload['plan_id'])
            assert reread.status == 200
            assert reread.json()['plan'] == payload['plan']
            report['click_through_get_seconds'] = time.perf_counter() - started
            report['shopping_text_sha256'] = hashlib.sha256(page.locator('#shopping-content').inner_text().encode()).hexdigest()
            report['status'] = 'PASS'
            page.screenshot(path=str(args.output / 'shopping.png'), full_page=True)
            write()
        except Exception as error:
            report.update(status='FAILED', exception_type=type(error).__name__, reason=str(error)[:800])
            write()
            raise
        finally:
            browser.close()


if __name__ == '__main__':
    main()
