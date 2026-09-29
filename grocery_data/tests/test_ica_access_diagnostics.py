import json
from types import SimpleNamespace

import pytest

from grocery_data.app.connectors.ica.access_diagnostics import (
    BODY_LIMIT,
    AccessDiagnostics,
    project_error_body,
    public_error_markers,
)


def test_error_projection_never_copies_unknown_fields_or_values():
    secret = 'private-customer-cookie-12345'
    body = json.dumps({'code': 'FORBIDDEN', 'message': secret,
                       'error': {'code': secret}, 'customer': secret}).encode()
    result = project_error_body(body)
    assert result['public_error_codes'] == ['FORBIDDEN']
    assert secret not in json.dumps(result)
    assert project_error_body(b'x' * (BODY_LIMIT + 1)) == {
        'body_read': 'over_limit_omitted'}
    assert public_error_markers("Access Denied: You don't have permission to access secret") == [
        'access_denied', 'permission_denied']


@pytest.mark.parametrize('case', ['ok', 'oversize', 'timeout', 'ambiguous', 'unsupported'])
async def test_bounded_passive_body_read(case, monkeypatch):
    monkeypatch.setattr('grocery_data.app.connectors.ica.access_diagnostics.BODY_TIMEOUT', .01)
    diagnostics = AccessDiagnostics()
    diagnostics.enabled = True
    path = '/stores/1088004/api/webproductpagews/v6/product-pages/search'
    url = 'https://handlaprivatkund.ica.se' + path
    diagnostics._request({'requestId': 'ephemeral-never-export',
                          'request': {'url': url, 'method': 'GET',
                                      'headers': {'Cookie': 'never-export'}}})
    diagnostics._data({'requestId': 'ephemeral-never-export',
                       'dataLength': BODY_LIMIT + 1 if case == 'oversize' else 13})
    if case != 'timeout':
        diagnostics._finished({'requestId': 'ephemeral-never-export'})
    if case == 'ambiguous':
        diagnostics._request({'requestId': 'second', 'request': {'url': url, 'method': 'GET'}})
    calls = []

    async def send(method, _params):
        calls.append(method)
        return {'body': 'Access Denied', 'base64Encoded': False}

    async def header_value(name):
        assert name == 'content-type'
        return 'image/png' if case == 'unsupported' else 'text/html; charset=utf8'

    diagnostics.session = SimpleNamespace(send=send)
    response = SimpleNamespace(request=SimpleNamespace(url=url, method='GET'),
                               header_value=header_value)
    result = await diagnostics.error(response)
    assert calls == (['Network.getResponseBody'] if case == 'ok' else [])
    assert 'ephemeral' not in json.dumps(result)
    assert 'never-export' not in json.dumps(result)
    if case == 'ok':
        assert result['public_error_markers'] == ['access_denied']
        assert result['body_read'] == 'bounded'


async def test_resource_buffer_and_decoded_byte_limit_are_set():
    calls = []

    async def send(method, params):
        calls.append((method, params))

    session = SimpleNamespace(on=lambda *_: None, send=send)

    async def new_cdp_session(_):
        return session

    await AccessDiagnostics().start(SimpleNamespace(new_cdp_session=new_cdp_session), None)
    assert calls == [('Network.enable', {'maxTotalBufferSize': 2 * BODY_LIMIT,
                                        'maxResourceBufferSize': BODY_LIMIT,
                                        'maxPostDataSize': 0})]
