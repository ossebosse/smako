from __future__ import annotations

import json
from pathlib import Path

from app.main import app
from fastapi.testclient import TestClient

STATIC = Path(__file__).parents[1] / "app" / "static"


def test_manifest_describes_root_scoped_standalone_consumer_app() -> None:
    manifest = json.loads((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))

    assert manifest["id"] == "/"
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["lang"] == "sv-SE"
    assert {icon["purpose"] for icon in manifest["icons"]} == {"any", "maskable"}
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/static/icons/")
        assert (STATIC / "icons" / Path(icon["src"]).name).is_file()


def test_service_worker_only_caches_static_shell_and_never_api_or_posts() -> None:
    worker = (STATIC / "service-worker.js").read_text(encoding="utf-8")

    assert 'const SHELL_CACHE = "billigaste-veckomenyn-shell-v11"' in worker
    assert 'request.method !== "GET"' in worker
    assert 'url.pathname.startsWith("/api/")' in worker
    assert 'request.mode === "navigate"' in worker
    assert "networkFirstShell(request)" in worker
    assert 'fetch(request, { cache: "no-cache" })' in worker
    assert 'caches.match("/static/offline.html")' in worker
    assert "cached || fetch(request)" not in worker
    assert "await cache.put(request, response.clone())" in worker
    shell_block = worker.split("const SHELL_ASSETS", maxsplit=1)[1].split(");", maxsplit=1)[0]
    assert '"/api/' not in shell_block
    assert '"/"' not in shell_block
    assert "plans" not in shell_block
    assert "prices" not in shell_block


def test_root_worker_route_is_not_cached_and_allows_root_scope() -> None:
    client = TestClient(app)

    manifest = client.get("/manifest.webmanifest")
    worker = client.get("/service-worker.js")

    assert manifest.status_code == 200
    assert manifest.headers["content-type"].startswith("application/manifest+json")
    assert worker.status_code == 200
    assert worker.headers["content-type"].startswith("application/javascript")
    assert worker.headers["service-worker-allowed"] == "/"
    assert "no-store" in worker.headers["cache-control"]


def test_consumer_shell_registers_pwa_with_safe_area_support() -> None:
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    script = (STATIC / "app.js").read_text(encoding="utf-8")
    styles = (STATIC / "styles.css").read_text(encoding="utf-8")

    assert "viewport-fit=cover" in page
    assert 'rel="manifest" href="/manifest.webmanifest"' in page
    assert 'rel="icon" href="/static/icons/app-icon.svg"' in page
    assert 'navigator.serviceWorker.register("/service-worker.js", { scope: "/" })' in script
    assert '"serviceWorker" in navigator && window.isSecureContext' in script
    assert "env(safe-area-inset-top" in styles
    assert "env(safe-area-inset-right" in styles
    assert "env(safe-area-inset-bottom" in styles
    assert "env(safe-area-inset-left" in styles
