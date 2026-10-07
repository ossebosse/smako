"""Three real button flows against isolated frozen replay; optional status reset.

No completed response is mocked. Injection aborts one client status connection.
Never log cookies, session capabilities or exception tracebacks with headers.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Error as BrowserError
from playwright.async_api import async_playwright, expect


def core(saved):
    return hashlib.sha256(json.dumps({'request': saved['request'], 'plan': saved['plan']}, sort_keys=True).encode()).hexdigest()


async def main(args):
    request = json.loads(args.request.read_text(encoding='utf8'))
    args.output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        contexts = [await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                                              service_workers='block' if args.interrupt else 'allow') for _ in range(3)]
        rows = []
        prepared = 0
        all_prepared, first_accepted = asyncio.Event(), asyncio.Event()

        async def owner(index):
            nonlocal prepared
            context = contexts[index]
            page = await context.new_page()
            click_finished = asyncio.Event()
            row = {'owner_label': index+1, 'injected': [], 'page_errors': [], 'server_errors': [], 'network_failures': [], 'responses': [], 'posts': 0, 'lifecycle': []}
            rows.append(row)
            await context.expose_binding('__cTrace', lambda source, data: row['lifecycle'].append({**data, 'observed_utc': datetime.now(UTC).isoformat()}))
            await context.expose_binding('__cUnhandled', lambda source, data: row['page_errors'].append('unhandledrejection: '+data))
            await context.add_init_script("window.__doc=crypto.randomUUID();window.addEventListener('smako:plan-transport',e=>window.__cTrace({...e.detail,document_id:window.__doc}).catch(()=>{}));")
            await context.add_init_script("window.addEventListener('unhandledrejection',e=>window.__cUnhandled(String(e.reason?.message||e.reason)).catch(()=>{}));")
            page.on('pageerror', lambda e: row['page_errors'].append(str(e)))
            page.on('requestfailed', lambda req: row['network_failures'].append({'path': urlsplit(req.url).path, 'failure': req.failure,
                'request_id': req.headers.get('x-request-id'), 'observed_utc': datetime.now(UTC).isoformat()}))

            async def response(r):
                path = urlsplit(r.url).path
                if r.status >= 500:
                    row['server_errors'].append({'path': path, 'status': r.status,
                        'request_id': r.headers.get('x-request-id'), 'at_utc': datetime.now(UTC).isoformat()})
                if path == '/api/plans' and r.request.method == 'POST' or path.startswith('/api/plan-jobs/'):
                    try:
                        body = await r.json()
                    except BrowserError:
                        row['responses'].append({'path': path, 'status': r.status, 'body_unavailable': True})
                        return
                    row['responses'].append({'path': path, 'status': r.status, 'stage': body.get('stage'), 'request_id': r.headers.get('x-request-id'), 'response_ms': r.request.timing.get('responseEnd'), 'at_utc': datetime.now(UTC).isoformat()})
                    if r.request.method == 'POST':
                        row['posts'] += 1
                        row['job_url'] = body['status_url']
                        if index == 0:first_accepted.set()
                    if r.status == 201:
                        row['saved'] = body
                    if index > 0 and r.status == 202 and body.get('stage') == 'queued' and not row.get('queued_dom'):
                        await expect(page.locator('#loading-message')).to_contain_text('väntar', timeout=10000)
                        row['queued_dom'] = await page.locator('#loading-message').inner_text()
                    if args.interrupt and index > 0 and r.status == 202 and body.get('stage') == 'queued' and path.startswith('/api/plan-jobs/') and not row.get('queued_reload'):
                        row['queued_reload'] = True
                        row['queued_reload_requested_utc'] = datetime.now(UTC).isoformat()
                        # A response callback can run before Playwright's
                        # dblclick action has returned. Do not navigate out
                        # from under that action and make it retry against the
                        # correctly disabled button in the replacement page.
                        await click_finished.wait()
                        row['queued_reload_started_utc'] = datetime.now(UTC).isoformat()
                        await page.reload(wait_until='domcontentloaded')

            page.on('response', response)
            if args.interrupt and index == 0:
                async def reset(route):
                    if not row['injected']:
                        row['injected'].append({'path': urlsplit(route.request.url).path, 'request_id': route.request.headers.get('x-request-id'), 'kind': 'connectionreset', 'at_utc': datetime.now(UTC).isoformat()})
                        await route.abort('connectionreset')
                    else:
                        await route.continue_()
                await context.route('**/api/plan-jobs/*', reset)
            await page.goto(args.base, wait_until='domcontentloaded')
            if await page.locator('#onboarding-dialog').is_visible():
                await page.locator('#onboarding-cta').click()
            await page.locator('#postal-code').fill(request['postal_code'])
            await page.locator('#recipes').select_option(str(request['recipes']))
            await page.locator('#servings').fill(str(request['servings']))
            await page.locator('#max-stores').select_option(str(request['max_stores']))
            await page.locator('#purchase-planning-mode').select_option(request['purchase_planning_mode'])
            await page.locator('#diversity-balanced').check()
            await page.locator('details.advanced-options > summary').click()
            for membership in request['membership_programs']:
                await page.locator(f'input[name="membership"][value="{membership}"]').check()
            await expect(page.locator('#recipe-style')).to_be_visible(timeout=30000)
            await page.locator('#recipe-style').select_option('complete')
            for cuisine in request['recipe_preferences']['cuisines']:
                await page.locator('#cuisine-'+cuisine).check()
            await page.locator('#recipe-ingredient-preset').select_option('custom')
            await page.locator('#recipe-min-ingredients').fill('10')
            await page.locator('#recipe-max-ingredients').fill('15')
            await page.locator('#recipe-min-protein').fill('30')
            await page.locator('#recipe-allow-fish').check()
            await page.locator('#recipe-nutrition-estimates').check()
            for store in request['allowed_store_ids']:
                await page.locator(f'#recipe-price-contexts input[value="{store}"]').check()
            prepared += 1
            if prepared == 3:all_prepared.set()
            await all_prepared.wait()
            # Admit the interrupted owner first, then start the two other real
            # button flows while it computes. Queue/reload coverage is deliberate.
            if index > 0:await first_accepted.wait()
            clicked = time.monotonic()
            row['click_started_utc'] = datetime.now(UTC).isoformat()
            await page.locator('#submit-button').dblclick()
            row['click_finished_utc'] = datetime.now(UTC).isoformat()
            click_finished.set()
            await expect(page.locator('#results')).to_be_visible(timeout=420000)
            row['click_to_result_seconds'] = time.monotonic()-clicked
            assert row['posts'] == 1 and not row['page_errors'] and not row['server_errors']
            saved = row['saved']
            assert saved['plan']['optimized_basket']['total'] == 741.15
            read = await context.request.get(args.base+'/api/plans/'+saved['plan_id'], timeout=30000)
            assert read.status == 200 and core(await read.json()) == core(saved)
            row['complete_result_hash'] = core(saved)
            row['recipe_cards'] = await page.locator('#recipes-list .recipe-card').count()
            assert row['recipe_cards'] == 5
            await page.screenshot(path=str(args.output/f'owner-{index+1}.png'), full_page=True)
            (args.output/f'owner-{index+1}-saved.json').write_text(json.dumps(saved, ensure_ascii=False), encoding='utf8')
            row['plan_id'] = saved['plan_id']
            del row['saved']
            return row

        try:
            await asyncio.gather(*(owner(i) for i in range(3)))
        finally:
            # Preserve observed job references and event ordering on failure;
            # the rows contain no authentication headers or session cookies.
            (args.output/'observed-owners.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
        rows.sort(key=lambda r: r['owner_label'])
        if args.interrupt:
            assert len(rows[0]['injected']) == 1
            assert all(row.get('queued_reload') for row in rows[1:])
        for index, row in enumerate(rows):
            other = contexts[(index+1)%3]
            denied = await other.request.get(args.base+row['job_url'])
            row['foreign_job_status'] = denied.status
            denied = await other.request.get(args.base+'/api/plans/'+row['plan_id'])
            row['foreign_plan_status'] = denied.status
            assert row['foreign_job_status'] == 404 and row['foreign_plan_status'] == 403
        result = {'outcome': 'PASS', 'controlled_interruption': args.interrupt, 'owners': rows}
        (args.output/'summary.json').write_text(json.dumps(result, indent=2), encoding='utf8')
        print(json.dumps([{k: v for k, v in r.items() if k not in {'responses', 'network_failures', 'lifecycle'}} for r in rows]))
        await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:18127')
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--interrupt', action='store_true')
    args = parser.parse_args()
    assert urlsplit(args.base).hostname in {'localhost', '127.0.0.1'}
    try:
        asyncio.run(main(args))
    except Exception as error:  # noqa: BLE001 - preserve FAIL evidence without secret headers
        # Playwright API transport tracebacks can include Cookie headers.
        raw = '\n'.join('[secret header redacted]' if re.search(r'cookie:|authorization:|token:|anonymous-session', line, re.IGNORECASE) else line for line in str(error).splitlines())
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'failure.json').write_text(json.dumps({'outcome': 'FAIL', 'category': type(error).__name__, 'raw_error_redacted': raw}, indent=2), encoding='utf8')
        print(json.dumps({'outcome': 'FAIL', 'category': type(error).__name__, 'error': raw}))
        raise SystemExit(1) from None
