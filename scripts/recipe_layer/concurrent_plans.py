"""Three isolated owners using normal asynchronous HTTP planning; no fixtures injected."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright


async def main(args):
    assert urlsplit(args.base).hostname in {'localhost', '127.0.0.1'}
    args.output.mkdir(parents=True, exist_ok=False)
    request = json.loads(args.request.read_text(encoding='utf-8'))
    async with async_playwright() as pw:
        contexts = [await pw.request.new_context(base_url=args.base) for _ in range(3)]
        for context in contexts:
            response = await context.get('/api/personal/state')
            assert response.ok
        async def run(index):
            context = contexts[index]
            started = time.perf_counter()
            response = await context.post('/api/plans', data=request, headers={'Prefer': 'respond-async'})
            assert response.status == 202, await response.text()
            url = (await response.json())['status_url']
            duplicate = await context.post('/api/plans', data=request, headers={'Prefer': 'respond-async'})
            assert duplicate.status == 202 and (await duplicate.json())['status_url'] == url
            foreign_job = await contexts[(index + 1) % 3].get(url)
            assert foreign_job.status in {403, 404}
            polls = []
            while time.perf_counter() - started < args.timeout:
                before = time.perf_counter()
                response = await context.get(url, timeout=30000)
                elapsed = time.perf_counter() - before
                body = await response.json()
                polls.append({'wall_seconds': elapsed, 'status': response.status,
                              'stage': body.get('stage'), 'since_submit': time.perf_counter() - started})
                if response.status != 202:
                    assert response.status == 201, body
                    break
                await asyncio.sleep(2)
            else:
                raise AssertionError('Job did not finish')
            generation_seconds = time.perf_counter() - started
            envelope = body.get('saved', body)
            foreign = await contexts[(index + 1) % 3].get('/api/plans/' + envelope['plan_id'])
            assert foreign.status in {403, 404}
            fetched = time.perf_counter()
            reread = await context.get('/api/plans/' + envelope['plan_id'])
            fetch_seconds = time.perf_counter() - fetched
            assert reread.ok and (await reread.json())['plan'] == envelope['plan']
            (args.output / f'owner-{index + 1}-plan.json').write_text(json.dumps(envelope, ensure_ascii=False, indent=2), encoding='utf-8')
            result = {'owner': index + 1, 'generation_including_queue_seconds': generation_seconds,
                      'completed_fetch_seconds': fetch_seconds, 'polls': polls,
                      'duplicate_started_same_job': True, 'foreign_job': foreign_job.status,
                      'foreign_plan': foreign.status, 'total': envelope['plan']['optimized_basket']['total']}
            (args.output / f'owner-{index + 1}-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            return result
        results = await asyncio.gather(*(run(index) for index in range(3)))
        (args.output / 'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps([{k: v for k, v in row.items() if k != 'polls'} for row in results]))
        for context in contexts:
            await context.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True)
    parser.add_argument('--request', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--timeout', type=int, default=1200)
    asyncio.run(main(parser.parse_args()))
