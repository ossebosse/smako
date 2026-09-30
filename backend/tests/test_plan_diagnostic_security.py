from __future__ import annotations

import json

import pytest
from app.api import plan as plan_api
from app.config import Settings
from app.errors import PriceProviderError
from app.main import app
from app.models import PlanRequest
from app.providers.federated import SourceResolutionDiagnostics
from app.providers.mock import MockPriceProvider
from app.services.meal_plan_optimizer import MealPlanService
from fastapi.testclient import TestClient

from grocery_data.app.domain import Chain
from grocery_data.app.domain.source_strategy import (
    SourceChannel,
    SourceProvider,
    SourceRole,
)


class _DiagnosticMockProvider(MockPriceProvider):
    @property
    def diagnostics(self) -> tuple[SourceResolutionDiagnostics, ...]:
        return (
            SourceResolutionDiagnostics(
                chain=Chain.WILLYS,
                context_id="context:willys:test",
                requested_provider=SourceProvider.OWN,
                selected_provider=SourceProvider.OWN,
                selected_channel=SourceChannel.CATALOG,
                selected_role=SourceRole.BASKET,
                selected_snapshot_id="snapshot:test",
                fallback_available=False,
                fallback_used=False,
                basket_eligible=True,
                reason=(
                    "GET https://provider.invalid/catalog?api_key=TOPSECRET "
                    "Cookie=session-secret failed"
                ),
                considered_stores=2,
                accepted_stores=1,
                products_considered={"own": 12},
                products_returned=10,
                provider_errors=(
                    "Bearer token-value from https://provider.invalid?token=TOPSECRET",
                ),
            ),
        )


def _request(*, debug: bool) -> PlanRequest:
    return PlanRequest(
        recipes=3,
        servings=4,
        max_stores=2,
        strategy="legacy",
        optimization_iterations=0,
        debug=debug,
    )


@pytest.mark.asyncio
async def test_normal_plan_response_never_exposes_source_diagnostics() -> None:
    service = MealPlanService(Settings(price_provider="mock", meal_plan_strategy="legacy"))
    response = await service._build_with_provider(
        _request(debug=False),
        _DiagnosticMockProvider(),
    )

    assert response.source_diagnostics == []
    assert response.debug_info is None
    rendered = response.model_dump_json()
    assert "TOPSECRET" not in rendered
    assert "provider.invalid" not in rendered
    assert "session-secret" not in rendered


@pytest.mark.asyncio
async def test_debug_diagnostics_are_closed_typed_counters_not_exception_text() -> None:
    service = MealPlanService(Settings(price_provider="mock", meal_plan_strategy="legacy"))
    response = await service._build_with_provider(
        _request(debug=True),
        _DiagnosticMockProvider(),
    )

    assert response.source_diagnostics == [
        {
            "chain": "willys",
            "context_id": "context:willys:test",
            "requested_provider": "own",
            "selected_provider": "own",
            "selected_channel": "catalog",
            "selected_role": "basket",
            "selected_snapshot_id": "snapshot:test",
            "fallback_available": False,
            "fallback_used": False,
            "basket_eligible": True,
            "considered_stores": 2,
            "accepted_stores": 1,
            "rejected_stores": 0,
            "stale_stores": 0,
            "products_returned": 10,
            "rows_rejected": 0,
            "stale_rows": 0,
            "products_considered": {"own": 12},
            "provider_error_count": 1,
            "resolution_status": "selected",
        }
    ]
    rendered = json.dumps(response.source_diagnostics)
    assert "reason" not in response.source_diagnostics[0]
    assert "provider_errors" not in response.source_diagnostics[0]
    for secret in ("TOPSECRET", "session-secret", "token-value", "https://", "Cookie"):
        assert secret not in rendered


def test_arbitrary_artifact_diagnostic_keys_are_not_projected() -> None:
    safe = MealPlanService._safe_source_diagnostics(
        [
            {
                "chain": "hemkop",
                "context_id": "https://host/?token=secret",
                "basket_eligible": False,
                "provider_errors": ["https://host/?key=secret"],
                "raw_url": "https://host/?cookie=secret",
                "headers": {"Authorization": "Bearer secret"},
                "reason": "api_key=secret",
                "products_considered": {"own": 1, "https://leak": 99},
            }
        ]
    )
    assert safe == [
        {
            "chain": "hemkop",
            "context_id": None,
            "basket_eligible": False,
            "products_considered": {"own": 1},
            "provider_error_count": 1,
            "resolution_status": "no_eligible_source",
        }
    ]


def test_provider_api_error_does_not_echo_exception_or_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingService:
        async def create_plan(self, _request):
            raise PriceProviderError(
                "GET https://provider.invalid?api_key=TOPSECRET Cookie=session-secret"
            )

    monkeypatch.setattr(plan_api, "_service", lambda _request: FailingService())
    monkeypatch.setenv("PRICE_UNIVERSE_REQUIRED", "false")
    response = TestClient(app).post(
        "/api/plan",
        json={"recipes": 3, "servings": 4, "max_stores": 2},
    )
    assert response.status_code == 502
    assert response.json() == {"detail": "price provider unavailable"}
    assert "TOPSECRET" not in response.text
    assert "provider.invalid" not in response.text
