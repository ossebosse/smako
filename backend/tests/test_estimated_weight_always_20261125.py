"""Owner decision 2026-11-25: estimated weight is always allowed; it is no longer a choice."""

from types import SimpleNamespace

from app.api.plan import _production_consumer_request
from app.models import PlanRequest


def test_a_public_request_for_exact_amounts_is_planned_with_estimated_weight():
    settings = SimpleNamespace(app_env="development")
    assert _production_consumer_request(PlanRequest(purchase_planning_mode="exact"), settings).purchase_planning_mode == "estimated"
    assert _production_consumer_request(PlanRequest(), settings).purchase_planning_mode == "estimated"


def test_the_classic_page_has_no_purchase_mode_choice():
    from pathlib import Path

    page = (Path(__file__).resolve().parents[1] / "app/static/index.html").read_text(encoding="utf-8")
    assert 'id="purchase-planning-mode" name="purchase_planning_mode" value="estimated"' in page
    assert "Exakt – bara styrkta mängder" not in page
