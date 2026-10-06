"""Isolated real-job process restart or guest-cookie loss; no mock menus.

Start is API-driven. Status and final/error DOM use the ordinary public page.
Cookie restoration stays in test memory and never appears in evidence.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
import uuid
from pathlib import Path

from playwright.async_api import async_playwright, expect


async def main(args):
    args.output.mkdir(parents=True, exist_ok=True)
    request = json.loads(args.request.read_text(encoding='utf8'))
    report = {'scenario': args.scenario, 'page_errors': [], 'statuses': [], 'start_kind': 'ordinary_API_real_planner', 'mocked_completed_menus': False}
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        context = await browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        page = await context.new_page()
        page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
        await context.expose_binding('__unhandled', lambda source, data: report['page_errors'].append('unhandledrejection: '+data))
        await context.add_init_script("window.addEventListener('unhandledrejection',e=>window.__unhandled(String(e.reason?.message||e.reason)).catch(()=>{}));")
        page.on('response', lambda response: report['statuses'].append({'url': response.url, 'status': response.status}) if '/api/plan-jobs/' in response.url else None)
        await page.goto(args.base, wait_until='domcontentloaded')
        await page.wait_for_function("document.documentElement.dataset.frontendInitialized==='true'")
        if await page.locator('#onboarding-dialog').is_visible():
            await page.locator('#onboarding-cta').click()
        accepted = await context.request.post(args.base+'/api/plans', data=request, headers={'Prefer': 'respond-async', 'X-Request-ID': str(uuid.uuid4())}, timeout=30000)
        assert accepted.status == 202
        pending = await accepted.json()
        report['job_url'] = pending['status_url']
        report['request_id'] = pending['request_id']
        await page.evaluate("pending=>SmakoRecipes.storage.set('smako.planJob.public',{url:pending.status_url,requestId:pending.request_id,started_at:Date.now()})", pending)
        await page.reload(wait_until='domcontentloaded')
        for _ in range(100):
            status = await context.request.get(args.base+pending['status_url'])
            body = await status.json()
            assert status.status == 202
            if body['stage'] != 'queued':
                report['before_interruption_stage'] = body['stage']
                break
            await asyncio.sleep(.2)
        else:
            raise AssertionError('Job never began computing')
        original_cookies = await context.cookies()
        if args.scenario == 'restart':
            marker = args.output/'restart-ready.json'
            marker.write_text(json.dumps({'job_url': pending['status_url'], 'request_id': pending['request_id']}), encoding='utf8')
            deadline = time.monotonic()+180
            while not (args.output/'restart-continue.json').exists():
                assert time.monotonic() < deadline
                await asyncio.sleep(.25)
        else:
            await context.clear_cookies()
            report['session_test'] = 'guest cookie removal, not signed-account expiry'
        await expect(page.locator('#error-state')).to_be_visible(timeout=180000)
        report['error_dom'] = await page.locator('#error-state').inner_text()
        assert 'gått ut' in report['error_dom']
        assert await page.evaluate("SmakoRecipes.pendingJob('public')===null")
        assert not report['page_errors']
        await page.screenshot(path=str(args.output/'expired-job.png'))
        if args.scenario == 'cookie-loss':
            await context.add_cookies(original_cookies)
            await page.evaluate("pending=>SmakoRecipes.storage.set('smako.planJob.public',{url:pending.status_url,requestId:pending.request_id,started_at:Date.now()})", pending)
            await page.reload(wait_until='domcontentloaded')
            await expect(page.locator('#results')).to_be_visible(timeout=240000)
            status = await context.request.get(args.base+pending['status_url'])
            assert status.status == 201
            saved = await status.json()
            assert saved['plan']['optimized_basket']['total'] == 741.15
            read = await context.request.get(args.base+'/api/plans/'+saved['plan_id'])
            assert read.status == 200 and (await read.json())['plan'] == saved['plan']
            report['same_job_result_restored_with_original_test_owner'] = True
            (args.output/'saved.json').write_text(json.dumps(saved), encoding='utf8')
        else:
            gone = await context.request.get(args.base+pending['status_url'])
            assert gone.status == 404
            report['unfinished_job_not_claimed_persistent'] = True
        report['outcome'] = 'PASS'
        (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
        print(json.dumps({k: v for k, v in report.items() if k != 'statuses'}))
        await browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:18127')
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--scenario', choices=['restart', 'cookie-loss'], required=True)
    args = parser.parse_args()
    assert args.base.startswith('http://127.0.0.1:')
    try:
        asyncio.run(main(args))
    except Exception as error:  # noqa: BLE001 - preserve FAIL evidence without secret headers
        raw = '\n'.join('[secret header redacted]' if re.search(r'cookie:|authorization:|token:|anonymous-session', line, re.IGNORECASE) else line for line in str(error).splitlines())
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output/'failure.json').write_text(json.dumps({'outcome': 'FAIL', 'category': type(error).__name__, 'raw_error_redacted': raw}, indent=2), encoding='utf8')
        print(json.dumps({'outcome': 'FAIL', 'category': type(error).__name__, 'error': raw}))
        raise SystemExit(1) from None
