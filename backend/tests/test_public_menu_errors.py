"""Error contracts only. These injected failures are not public acceptance tests."""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest
from app.api import plan as api
from app.config import Settings
from app.main import app
from app.services.personal_policy import PolicyConflict
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright


@pytest.mark.parametrize('route', ['/api/plan', '/api/plans'])
def test_internal_value_error_is_not_a_form_error(monkeypatch, route):
    monkeypatch.setattr(api, 'get_settings', lambda: Settings(price_provider='mock'))

    async def fail(*args):
        raise ValueError('private configuration detail')

    monkeypatch.setattr(api, '_run_admitted_plan', fail)
    response = TestClient(app).post(route, json={'recipes': 5, 'servings': 2, 'max_stores': 3})
    assert response.status_code == 500
    assert response.headers['x-error-code'] == 'planner_internal_error'
    assert response.headers['x-request-id']
    assert 'private configuration' not in response.text


def test_policy_data_block_keeps_its_distinct_code(monkeypatch):
    monkeypatch.setattr(api, 'get_settings', lambda: Settings(price_provider='mock'))

    async def fail(*args):
        raise PolicyConflict('Källunderlag saknas', code='DATA_BLOCKED')

    monkeypatch.setattr(api, '_run_admitted_plan', fail)
    response = TestClient(app).post('/api/plans', json={'max_stores': 3})
    assert response.status_code == 422
    assert response.json()['code'] == 'DATA_BLOCKED'


def test_consumer_store_limit_points_to_the_actual_form_field():
    from app.models import PlanRequest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        api._consumer_request(PlanRequest(max_stores=4))
    assert caught.value.status_code == 422
    assert caught.value.detail[0]['loc'] == ['body', 'max_stores']


@pytest.mark.parametrize('route', ['/api/plan', '/api/plans'])
@pytest.mark.parametrize('state,expected_status,code', [
    ('unsupported_postal', 422, 'form_validation_error'),
    ('absent', 503, 'price_universe_unavailable'),
    ('stale', 503, 'price_universe_unusable'),
    ('missing_required', 503, 'price_universe_unusable'),
])
def test_offline_preflight_distinguishes_area_from_data_failure(
    monkeypatch, route, state, expected_status, code,
):
    settings = Settings(price_provider='auto', price_universe_required=True,
                        price_universe_required_context_ids=('required',))
    prepared = SimpleNamespace(
        universe=SimpleNamespace(key=SimpleNamespace(postal_codes=('22350',))),
        status=lambda **_: SimpleNamespace(status='stale' if state == 'stale' else 'fresh'),
        _context_partition=lambda **_: (set() if state == 'missing_required' else {'required'}, (), {}),
    )
    monkeypatch.setattr(api, 'get_settings', lambda: settings)
    monkeypatch.setattr(api, 'GLOBAL_PREPARED_PRICE_UNIVERSES', SimpleNamespace(
        get_for_request=lambda *_: None if state in {'absent', 'unsupported_postal'} else prepared,
        get_active=lambda *_: None if state == 'absent' else prepared,
    ))

    async def must_not_run(*_):
        pytest.fail('Preflight rejection must not start planning or live collection')

    monkeypatch.setattr(api, '_run_admitted_plan', must_not_run)
    response = TestClient(app).post(route, json={
        'postal_code': '22222' if state == 'unsupported_postal' else '22350',
        'recipes': 5, 'servings': 2, 'max_stores': 3,
    })
    assert response.status_code == expected_status
    assert response.headers['x-error-code'] == code
    assert response.headers['x-request-id']
    if state == 'unsupported_postal':
        assert response.json()['detail'][0]['loc'] == ['body', 'postal_code']
        assert '22350' in response.json()['detail'][0]['msg']


@pytest.mark.asyncio
async def test_optional_unlimited_comparison_cannot_enumerate_33_context_power_set():
    from app.models.basket import OptimizedBasket
    from app.services.meal_plan_optimizer import MealPlanService

    service = MealPlanService(Settings(price_provider='mock'))
    calls = []

    def optimize(*args, max_stores):
        calls.append(max_stores)
        assert max_stores is not None, 'Would allocate 2**33-1 optional store combinations'
        return OptimizedBasket(total=0, stores=[], max_stores=max_stores)

    service.basket_optimizer.optimize = optimize
    plan = SimpleNamespace(ingredients=[], candidates_by_name={})
    scenarios = await service._build_scenarios(plan, [object()] * 33)
    assert calls == [1, 2, 3]
    assert scenarios[-1].basket is None
    assert scenarios[-1].error


def test_browser_error_classes_retain_choices_and_identify_actual_field():
    static = Path(__file__).resolve().parents[1] / 'app/static'
    case = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send(self, status, body, content_type='application/json', headers=None):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body if isinstance(body, bytes) else json.dumps(body).encode())

        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/ready':
                return self.send(case.get('ready_status', 200), {'status': case.get('ready_body', 'ready')})
            if path.startswith('/api/plan-jobs/'):
                case['polled'] = True
                return self.send(503, {}, headers={'X-Error-Code': 'price_universe_unusable', 'X-Request-ID': 'poll-error-12345'})
            file = static / ('index.html' if path == '/' else path.removeprefix('/static/'))
            if file.is_file():
                return self.send(200, file.read_bytes(), mimetypes.guess_type(file)[0] or 'text/plain')
            self.send(200, {})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or '{}')
            if self.path == '/api/plans':
                case['request'] = body
                headers = {'X-Request-ID': self.headers['X-Request-ID'], **case.get('headers', {})}
                return self.send(case['status'], case['body'], headers=headers)
            self.send(202, {})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 390, 'height': 844})
            page.goto(f'http://127.0.0.1:{server.server_port}')
            page.locator('#onboarding-cta').click()
            page.locator('#servings').fill('2')
            page.locator('#max-stores').select_option('3')
            cases = [
                (202, {'status': 'pending', 'status_url': '/api/plan-jobs/' + 'a' * 32}, {}, 'verifieringskraven'),
                (503, {'detail': 'private service details'}, {}, 'tillfälligt otillgänglig'),
                (422, {'detail': [{'loc': ['body', 'postal_code'], 'msg': 'Prisområde saknas'}]}, {}, 'Postnummer'),
                (422, {'detail': [{'loc': ['body', 'max_stores'], 'msg': 'Värdet är ogiltigt'}]}, {}, 'Max antal inköpsställen'),
                (422, {'detail': 'underlag', 'code': 'DATA_BLOCKED'}, {}, 'inte kan verifieras'),
                (422, {'detail': 'saknas'}, {'X-Error-Code': 'plan_infeasible'}, 'Ingen komplett meny'),
                (500, {'detail': 'private configuration detail'}, {}, 'serverfel'),
                (504, {}, {}, 'inte i tid'),
                (503, {}, {'X-Error-Code': 'price_universe_unavailable'}, 'Prisunderlaget'),
                (503, {}, {'X-Error-Code': 'price_universe_unusable'}, 'verifieringskraven'),
                (503, {}, {'X-Error-Code': 'saved_plan_owner_session_unavailable'}, 'session'),
                (429, {}, {'Retry-After': '12'}, '12 sekunder'),
                (403, {}, {}, 'session saknar åtkomst'),
            ]
            for status, body, headers, expected in cases:
                case.update(status=status, body=body, headers=headers)
                page.locator('#submit-button').click()
                page.locator('#error-state').wait_for(state='visible')
                text = page.locator('#error-message').inner_text()
                assert expected in text
                assert 'Fel-ID: ' in text
                assert 'Kontrollera dina val' not in text
                assert 'private configuration' not in text
                assert 'private service' not in text
                assert 'uppdaterar priserna' not in text
                if status == 202:
                    assert case['polled'] and 'poll-error-12345' in text
                assert page.locator('#submit-button').is_enabled()
                assert case['request']['max_stores'] == 3
                assert case['request']['servings'] == 2
                assert case['request']['purchase_planning_mode'] == 'exact'
                assert page.locator('#max-stores').input_value() == '3'
                assert page.locator('#servings').input_value() == '2'
                invalid = page.locator('#max-stores').get_attribute('aria-invalid')
                assert (invalid == 'true') == (isinstance(body.get('detail'), list) and body['detail'][0]['loc'][1] == 'max_stores')
                invalid_postal = page.locator('#postal-code').get_attribute('aria-invalid')
                assert (invalid_postal == 'true') == (isinstance(body.get('detail'), list) and body['detail'][0]['loc'][1] == 'postal_code')
            # A real data outage still disables planning. The existing status
            # retry can recover without losing the selected form values.
            case.update(status=503, body={}, headers={'X-Error-Code': 'price_universe_unusable'},
                        ready_status=503, ready_body='not_ready')
            page.locator('#submit-button').click()
            page.locator('#error-state').wait_for(state='visible')
            assert not page.locator('#submit-button').is_enabled()
            assert 'uppdaterar priserna' not in page.locator('body').inner_text()
            case.update(ready_status=200, ready_body='ready')
            page.locator('#service-retry-button').click()
            page.locator('#submit-button:not([disabled])').wait_for()
            assert page.locator('#max-stores').input_value() == '3'
            assert page.locator('#servings').input_value() == '2'
            browser.close()
    finally:
        server.shutdown()
