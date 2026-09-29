"""Public iPaper text/PDF transport discovered from the official flyer viewer."""
import base64
import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx

from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy, bounded_request
from grocery_data.app.domain import RawBatch, RawFetch, TransportMetrics


class FlyerClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=60, follow_redirects=False)
        self.limiter = AsyncRateLimiter(1)
        self.pdfs = {}
        self.requests = 0
        self.stopped_status = None

    async def aclose(self):
        await self.client.aclose()

    async def request(self, method, url, **kwargs):
        if self.stopped_status is not None:
            raise ValueError(f'public flyer batch stopped after HTTP {self.stopped_status}; not retried')
        def count(_):
            self.requests += 1
        response = await bounded_request(self.client, self.limiter, RetryPolicy(attempts=1),
            method, url, on_attempt=count, retry_rate_limits=False, **kwargs)
        if response.status_code == 302 and url.endswith('/GetPDF.ashx'):
            destination = response.headers.get('location', '')
            target = urlsplit(destination)
            if target.scheme != 'https' or target.netloc != 'cdn.ipaper.io' or not target.path.endswith('/Download.pdf'):
                raise ValueError('unverified public PDF redirect')
            response = await bounded_request(self.client, self.limiter, RetryPolicy(attempts=1),
                'GET', destination, on_attempt=count, retry_rate_limits=False)
        if response.status_code != 200:
            if response.status_code in (401, 403, 429):
                self.stopped_status = response.status_code
            raise ValueError(f'public flyer transport stopped: HTTP {response.status_code}')
        return response

    async def fetch(self, store):
        url = store.source_fields['flyer_url'].rstrip('/') + '/'
        if (urlsplit(url).netloc != 'reklamblad.willys.se'
                or url != f'https://reklamblad.willys.se/willys/{store.external_id}/'):
            raise ValueError('unverified official flyer URL')
        before = self.requests
        response = await self.request('GET', url)
        settings, _ = json.JSONDecoder().raw_decode(response.text.split('window.staticSettings =', 1)[1])
        if settings['paperCompleteUrl'] != url or (settings.get('gatedContent') or {}).get('isEnabled'):
            raise ValueError('flyer identity or public access unverified')
        # Closed capture: never save scripts, cookies, transient asset signatures
        # or account identifiers from the viewer HTML.
        safe = {k: settings[k] for k in ('paperId', 'name', 'pages', 'pageTexts', 'paperCompleteUrl', 'enrichments')}
        safe['publication_url'] = settings['aws']['url']
        safe['download_enabled'] = settings['modules']['hasDownloadPdf']
        if not safe['download_enabled'] or not safe['pageTexts']:
            raise ValueError('document_text_or_public_download_unavailable')
        listing = RawFetch(chain='willys', store_external_id=store.external_id, kind='flyer_listing',
            method='GET', url=url, fetched_at=datetime.now(UTC), http_status=200,
            content_type='application/json; profile=sanitized-public-viewer',
            payload=json.dumps(safe, ensure_ascii=False).encode(), connector_version='willys-flyer-v1')
        key = safe['publication_url']
        if key not in self.pdfs:
            pdf_url = url + 'GetPDF.ashx'
            pdf = await self.request('POST', pdf_url, data={'pageNumbers': ''})
            if not pdf.content.startswith(b'%PDF'):
                raise ValueError('public_download_not_pdf')
            self.pdfs[key] = RawFetch(chain='willys', kind='flyer_pdf', method='POST', url=pdf_url,
                fetched_at=datetime.now(UTC), http_status=200, content_type='application/json; profile=pdf-evidence',
                payload=json.dumps({'sha256': hashlib.sha256(pdf.content).hexdigest(),
                    'pdf_base64': base64.b64encode(pdf.content).decode()}).encode(), connector_version='willys-flyer-v1')
        # Shared PDF only after this store's own current page has confirmed the
        # identical publication. Original PDF observation remains unchanged.
        return RawBatch(chain='willys', documents=(listing, self.pdfs[key]),
                        transport=TransportMetrics(request_count=self.requests-before))
