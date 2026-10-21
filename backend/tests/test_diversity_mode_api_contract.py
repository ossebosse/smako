from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import app.services.meal_plan_optimizer as meal_plan_module
import pytest
from app.main import app
from app.models import PlanRequest, Product, Store
from app.models.diversity import DiversityMode
from app.providers.mock import MockPriceProvider
from fastapi.testclient import TestClient

_CENT = Decimal("0.01")


pytestmark = pytest.mark.usefixtures("verified_smako_member")

def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


class _CountingMockPriceProvider(MockPriceProvider):
    def __init__(self) -> None:
        super().__init__(use_member_prices=False)
        self.find_store_calls = 0
        self.search_queries: list[str] = []
        self.store_product_calls = 0
        self.offer_calls = 0

    async def find_stores(self, postal_code: str) -> list[Store]:
        self.find_store_calls += 1
        return await super().find_stores(postal_code)

    async def search_products(
        self,
        query: str,
        store_ids: list[str],
    ) -> list[Product]:
        self.search_queries.append(query)
        return await super().search_products(query, store_ids)

    async def get_store_products(self, store_id: str) -> list[Product]:
        self.store_product_calls += 1
        return await super().get_store_products(store_id)

    async def get_offers(self, store_id: str) -> list[Product]:
        self.offer_calls += 1
        return await super().get_offers(store_id)


def _request_payload(*, diversity_mode: str | None = None, debug: bool = False) -> dict:
    payload = {
        "postal_code": "22350",
        "recipes": 5,
        "servings": 4,
        "max_stores": 2,
        "strategy": "optimized",
        "candidate_recipe_count": 20,
        "beam_width": 5,
        "optimization_iterations": 0,
        "debug": debug,
    }
    if diversity_mode is not None:
        payload["diversity_mode"] = diversity_mode
    return payload


def _max_repetition(values: dict[str, int]) -> int:
    return max(values.values(), default=0)


def _assert_mode_quality(mode: str, option: dict) -> None:
    assert option["mode"] == mode
    assert len(option["recipes"]) == 5
    assert option["portions"] == 20
    assert all(recipe["servings"] == 4 for recipe in option["recipes"])
    assert option["price_per_portion"] == float(
        _money(Decimal(str(option["optimized_basket"]["total"])) / Decimal(20))
    )
    assert [row["recipe_name"] for row in option["recipe_costs"]] == [
        recipe["name"] for recipe in option["recipes"]
    ]
    assert _money(
        sum(
            (Decimal(str(row["incremental_ingredient_cost"])) for row in option["recipe_costs"]),
            Decimal(0),
        )
    ) == _money(option["optimized_basket"]["total"])
    assert _money(
        sum(
            (Decimal(str(row["allocated_basket_cost"])) for row in option["recipe_costs"]),
            Decimal(0),
        )
    ) == _money(option["optimized_basket"]["total"])
    assert all(
        _money(row["cost_per_portion"])
        == _money(Decimal(str(row["allocated_basket_cost"])) / Decimal(4))
        for row in option["recipe_costs"]
    )

    quality = option["quality"]
    assert quality["status"] == ("PASS" if option["variation_target_met"] else "FAIL")
    assert quality["basket_audit"]["status"] == "PASS"
    assert quality["basket_audit"]["passed"] is True
    assert quality["basket_audit"]["deficits"] == []
    assert quality["nutrition"]["status"] == "PASS"
    assert len(quality["nutrition"]["recipes"]) == 5
    assert all(row["status"] == "PASS" for row in quality["nutrition"]["recipes"])

    diversity = quality["diversity"]
    assert diversity["status"] == ("PASS" if option["variation_target_met"] else "FAIL")
    if not option["variation_target_met"]:
        assert option["variation_limitations"]
        assert option["optimized_basket"]["total"] <= option["budget_ceiling"]
        return
    assert diversity["mode"] == mode
    assert diversity["repetition"] == option["repetition"]
    assert len(diversity["pairs"]) == 10
    assert all(not pair["is_near_duplicate"] for pair in diversity["pairs"])

    repetition = option["repetition"]
    if mode == "balanced" or mode == "varied":
        assert option["similarity_threshold"] == 0.85
        assert option["max_pairwise_similarity"] < 0.85
        limits = {
            "recipe_families": 2,
            "primary_proteins": 2,
            "primary_carbs": 2,
            "dish_forms": 2,
            "cooking_methods": 2,
        }
    else:
        assert mode == "cheapest"
        assert option["similarity_threshold"] is None
        limits = {}
        # CHEAPEST deliberately allows repetition, but the optimizer's two
        # basic duplicate guards must still produce distinct recipes/profiles.
        assert len({recipe["name"].casefold() for recipe in option["recipes"]}) == 5
        profiles = {
            tuple(
                sorted(
                    (
                        ingredient["canonical_name"],
                        ingredient["unit"],
                        ingredient["quantity"],
                    )
                    for ingredient in recipe["ingredients"]
                )
            )
            for recipe in option["recipes"]
        }
        assert len(profiles) == 5

    for dimension, limit in limits.items():
        assert _max_repetition(repetition[dimension]) <= limit


def _assert_selected_projection(plan: dict, mode: str) -> None:
    selected = plan["plans"][mode]
    assert plan["diversity_mode"] == mode
    assert plan["recipes"] == selected["recipes"]
    assert plan["recipe_costs"] == selected["recipe_costs"]
    assert plan["ingredients"] == selected["ingredients"]
    assert plan["optimized_basket"] == selected["optimized_basket"]
    assert plan["quality"] == selected["quality"]
    assert plan["surplus"] == selected["surplus"]
    assert plan["portions"] == selected["portions"] == 20
    assert plan["price_per_portion"] == selected["price_per_portion"]


def test_default_balanced_response_prices_all_modes_from_one_provider_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("STABLE_CANDIDATE_SEARCH_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = _CountingMockPriceProvider()

    def provider_factory(*_args, **_kwargs) -> _CountingMockPriceProvider:
        return provider

    monkeypatch.setattr(meal_plan_module, "create_price_provider", provider_factory)
    response = TestClient(app).post(
        "/api/plan",
        json=_request_payload(debug=True),
    )

    assert response.status_code == 200, response.text
    plan = response.json()
    assert PlanRequest().diversity_mode is DiversityMode.BALANCED
    assert plan["diversity_mode"] == "balanced"
    assert set(plan["plans"]) == {"cheapest", "balanced", "varied"}
    assert plan["diversity_plan_errors"] == {}
    assert plan["optimization"]["candidate_recipes_generated"] == 20
    assert plan["optimization"]["candidate_recipes_valid"] >= 5
    assert set(plan["optimization"]["diversity_plan_states"]) == set(plan["plans"])

    for mode, option in plan["plans"].items():
        _assert_mode_quality(mode, option)

    cheapest_total = _money(plan["plans"]["cheapest"]["optimized_basket"]["total"])
    assert cheapest_total <= _money(
        plan["plans"]["balanced"]["optimized_basket"]["total"]
    )
    assert cheapest_total <= _money(
        plan["plans"]["varied"]["optimized_basket"]["total"]
    )
    for option in plan["plans"].values():
        total = _money(option["optimized_basket"]["total"])
        premium = _money(total - cheapest_total)
        assert _money(option["premium_vs_cheapest"]) == premium
        assert _money(option["premium_per_portion"]) == _money(
            premium / Decimal(20)
        )

    _assert_selected_projection(plan, "balanced")

    # The three policy searches consume one shared, immutable local quote
    # snapshot. A mode must never cause another provider/catalog fetch.
    assert provider.find_store_calls == 1
    assert len(provider.search_queries) == plan["debug_info"]["economic_pool"][
        "search_queries_executed"
    ]
    assert provider.store_product_calls == 0
    assert provider.offer_calls == 0
    snapshot_ids = {product.product_id for product in provider._products}
    selected_ids = {
        item["product_id"]
        for option in plan["plans"].values()
        for store in option["optimized_basket"]["stores"]
        for item in store["items"]
    }
    assert selected_ids <= snapshot_ids


def test_api_store_cap_relaxation_is_monotone_for_all_returned_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("STABLE_CANDIDATE_SEARCH_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = _CountingMockPriceProvider()
    monkeypatch.setattr(
        meal_plan_module,
        "create_price_provider",
        lambda *_args, **_kwargs: provider,
    )
    client = TestClient(app)

    plans: dict[int, dict] = {}
    for cap in (1, 2, 3):
        payload = _request_payload()
        payload["max_stores"] = cap
        response = client.post("/api/plan", json=payload)
        assert response.status_code == 200, response.text
        plans[cap] = response.json()

    for mode in ("cheapest", "balanced", "varied"):
        totals = [
            _money(plans[cap]["plans"][mode]["optimized_basket"]["total"])
            for cap in (1, 2, 3)
        ]
        assert totals[1] <= totals[0]
        assert totals[2] <= totals[1]
        for cap in (1, 2, 3):
            basket = plans[cap]["plans"][mode]["optimized_basket"]
            assert basket["max_stores"] == cap
            assert basket["store_count"] <= cap


@pytest.mark.parametrize("mode", ["cheapest", "varied"])
def test_request_selects_requested_diversity_plan(
    mode: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post(
        "/api/plan",
        json=_request_payload(diversity_mode=mode),
    )

    assert response.status_code == 200, response.text
    plan = response.json()
    assert set(plan["plans"]) == {"cheapest", "balanced", "varied"}
    _assert_mode_quality(mode, plan["plans"][mode])
    _assert_selected_projection(plan, mode)


def test_explicit_legacy_schema_defaults_preserve_named_plan_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)
    base = _request_payload()
    explicit_defaults = {
        **base,
        "max_same_primary_ingredient_meals": 2,
        "max_same_recipe_family": 2,
        "max_same_carbohydrate_meals": 3,
        "max_pairwise_recipe_similarity": 0.70,
    }

    omitted_response = client.post("/api/plan", json=base)
    explicit_response = client.post("/api/plan", json=explicit_defaults)

    assert omitted_response.status_code == 200, omitted_response.text
    assert explicit_response.status_code == 200, explicit_response.text
    omitted = omitted_response.json()
    explicit = explicit_response.json()
    for mode, threshold in {
        "cheapest": None,
        "balanced": 0.85,
        "varied": 0.85,
    }.items():
        assert explicit["plans"][mode] == omitted["plans"][mode]
        assert explicit["plans"][mode]["similarity_threshold"] == threshold
