"""The two trial interfaces are served, chosen on /admin, and send /personal's requests."""
import re
from pathlib import Path

import pytest
from app.main import app
from fastapi.testclient import TestClient

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


@pytest.mark.parametrize("name", ["a", "b"])
def test_trial_interface_page_loads_only_same_origin_files(name):
    response = TestClient(app).get(f"/ui/{name}")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-cache"
    html = response.text
    files = re.findall(r'(?:src|href)="(/static/[^"?]+)', html)
    assert f"/static/next/{name}.js" in files and "/static/next/core.js" in files
    for path in files:
        assert (STATIC / path.removeprefix("/static/")).is_file(), path
    # The site's content policy allows no inline script and no other origins.
    assert not re.search(r"<script(?![^>]*\bsrc=)", html) and "http://" not in html and "https://" not in html


def test_unknown_trial_interface_is_not_found():
    assert TestClient(app).get("/ui/c").status_code == 404


def test_admin_offers_the_interfaces_and_personal_reads_the_choice():
    admin = (STATIC / "admin.html").read_text(encoding="utf-8")
    assert [*re.findall(r'data-interface="([a-z]+)"', admin)] == ["standard", "a", "b"]
    script = (STATIC / "admin.js").read_text(encoding="utf-8")
    choice = (STATIC / "next" / "choice.js").read_text(encoding="utf-8")
    assert '"smako.ui"' in script and '"smako.ui"' in choice
    personal = (STATIC / "personal.html").read_text(encoding="utf-8")
    # Read before anything else is drawn, so the ordinary page never flashes.
    assert personal.index("/static/next/choice.js") < personal.index("/static/styles.css")


def test_trial_interfaces_send_the_requests_personal_sends():
    core = (STATIC / "next" / "core.js").read_text(encoding="utf-8")
    for needed in ('purchase_planning_mode: "estimated"', 'membership_price_policy: "all_advertised"', "allowed_store_ids", "pantry_revision",
                   '"/api/personal/shopping-list"', '"/api/plans"', "respond-async", 'store_cap: "all_selected"'):
        assert needed in core, needed
