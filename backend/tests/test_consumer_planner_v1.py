from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.api import plan as plan_api
from app.config import Settings
from app.main import app
from app.models import (
    OfferKind,
    OfferMetadata,
    PlanPriceData,
    PlanRequest,
    PriceContextCoverage,
    SourceProvenance,
    Store,
)
from app.providers.mock import MockPriceProvider
from app.services.beta_observability import pseudonymous_actor
from app.services.diet_policy import recipe_respects_diet
from app.services.meal_plan_optimizer import (
    MealPlanService,
    _consumer_price_context_coverage,
)
from app.services.plan_mutation import (
    product_alternatives,
    replace_product,
    replace_recipe,
    replacement_recipe_candidates,
)
from app.services.plan_store import PlanOwnerMismatchError, PlanReadOnlyError, PlanStore
from app.services.product_lookup import lookup_gtin
from fastapi import HTTPException
from fastapi import Request as FastAPIRequest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.storage import (
    CommunityEvidenceObservationModel,
    PhysicalStoreModel,
    SourceProductModel,
    StoreContextLinkModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)


@pytest.fixture(scope="module")
def vegetarian_plan_and_request():
    settings = Settings(price_provider="mock", meal_plan_strategy="optimized")
    request = PlanRequest(
        postal_code="22350",
        recipes=5,
        servings=4,
        max_stores=2,
        strategy="optimized",
        candidate_recipe_count=20,
        beam_width=5,
        optimization_iterations=0,
        diversity_mode="balanced",
        diet_preference="vegetarian",
        availability_mode="strict",
    )
    plan = asyncio.run(MealPlanService(settings).create_plan(request))
    return settings, request, plan


@pytest.mark.parametrize("meals", range(3, 8))
@pytest.mark.parametrize("servings", range(1, 9))
@pytest.mark.parametrize("max_stores", (1, 2, 3))
def test_consumer_request_matrix_accepts_supported_values(
    meals: int,
    servings: int,
    max_stores: int,
) -> None:
    request = plan_api._consumer_request(
        PlanRequest(recipes=meals, servings=servings, max_stores=max_stores)
    )
    assert request.strategy == "optimized"


def test_consumer_request_accepts_stable_membership_program_ids() -> None:
    request = PlanRequest(memberships=["ICA_STAMMIS", "COOP_MEMBER"])

    assert request.membership_programs == (
        MembershipProgram.COOP_MEMBER,
        MembershipProgram.ICA_STAMMIS,
    )
    assert request.memberships == {"ica": True, "coop": True}
    assert request.use_member_prices is True


def test_consumer_request_keeps_legacy_membership_flags_compatible() -> None:
    request = PlanRequest(memberships={"hemkop": True, "ica": False})

    assert request.membership_programs == (MembershipProgram.HEMKOP_MEMBER,)
    assert request.memberships == {"hemkop": True, "ica": False}


def test_saved_plan_preserves_stable_membership_programs(
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, _request, plan = vegetarian_plan_and_request
    request = PlanRequest(memberships=["HEMKOP_MEMBER", "LIDL_PLUS"])

    saved = PlanStore(tmp_path / "membership-plans.sqlite3").create(request, plan)
    loaded = PlanStore(tmp_path / "membership-plans.sqlite3").get(saved.plan_id)

    assert loaded.request.membership_programs == (
        MembershipProgram.HEMKOP_MEMBER,
        MembershipProgram.LIDL_PLUS,
    )
    assert loaded.request.memberships == {"hemkop": True, "lidl": True}


def test_saved_plan_roundtrip_preserves_selected_member_contract_provenance(
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, _request, plan = vegetarian_plan_and_request
    first_group = plan.optimized_basket.stores[0]
    first_item = first_group.items[0]
    program = MembershipProgram.COOP_MEMBER
    member_item = first_item.model_copy(
        update={
            "chain": "coop",
            "price_contract_id": "contract:saved-plan-member",
            "eligibility": PromotionEligibility.MEMBER,
            "price_mechanism": PromotionMechanism.SALE_PRICE,
            "membership_program": program,
        }
    )
    member_group = first_group.model_copy(
        update={"items": [member_item, *first_group.items[1:]]}
    )
    member_basket = plan.optimized_basket.model_copy(
        update={"stores": [member_group, *plan.optimized_basket.stores[1:]]}
    )
    member_plan = plan.model_copy(
        update={
            "optimized_basket": member_basket,
            "membership_programs_used": (program,),
        }
    )
    request = PlanRequest(memberships=[program.value])

    saved = PlanStore(tmp_path / "member-provenance.sqlite3").create(
        request,
        member_plan,
    )
    loaded = PlanStore(tmp_path / "member-provenance.sqlite3").get(saved.plan_id)
    loaded_item = loaded.plan.optimized_basket.stores[0].items[0]

    assert loaded.request.membership_programs == (program,)
    assert loaded.plan.membership_programs_used == (program,)
    assert loaded_item.price_contract_id == "contract:saved-plan-member"
    assert loaded_item.eligibility is PromotionEligibility.MEMBER
    assert loaded_item.membership_program is program


def test_saved_plan_roundtrip_preserves_pricing_time_context_and_snapshot_lineage(
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    priced_at = datetime(2026, 9, 2, 8, 30, tzinfo=UTC)
    price_data = PlanPriceData(
        price_universe_id="price-universe:lineage",
        built_at=datetime(2026, 9, 2, 8, 0, tzinfo=UTC),
        pricing_timestamp=priced_at,
        snapshot_ids=("snapshot:universe",),
        status="fresh",
        compared_price_contexts=(
            PriceContextCoverage(
                context_id="own:coop:730400",
                display_name="Coop Online Syd",
                chain="coop",
                price_context_type="online_fulfillment",
                price_semantics="online_price",
                price_scope_label="Coop onlinepris",
                snapshot_ids=("snapshot:coop:730400",),
                status="compared",
            ),
        ),
    )
    saved = PlanStore(tmp_path / "lineage.sqlite3").create(
        request,
        plan.model_copy(update={"data": price_data}),
    )
    loaded = PlanStore(tmp_path / "lineage.sqlite3").get(saved.plan_id)

    assert loaded.price_universe_id == "price-universe:lineage"
    assert loaded.plan.data is not None
    assert loaded.plan.data.pricing_timestamp == priced_at
    assert loaded.plan.data.compared_price_contexts[0].context_id == "own:coop:730400"
    assert loaded.plan.data.compared_price_contexts[0].snapshot_ids == (
        "snapshot:coop:730400",
    )


@pytest.mark.parametrize(
    ("field", "value"),
    (("recipes", 2), ("servings", 9), ("max_stores", 4)),
)
def test_consumer_request_rejects_values_outside_primary_ux(
    field: str,
    value: int,
) -> None:
    with pytest.raises(HTTPException) as error:
        plan_api._consumer_request(PlanRequest(**{field: value}))
    assert error.value.status_code == 422


def test_production_plan_api_rejects_expensive_internal_search_options_before_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    class MustNotRunService:
        async def create_plan(self, _request):
            nonlocal called
            called = True
            raise AssertionError("an over-budget request must not start planning")

    settings = Settings(
        app_env="production",
        app_version="0.1.0-beta.1",
        build_id="beta-test-build",
        public_base_url="https://beta.example.test",
        secret_key="s" * 40,
        beta_admin_token="a" * 40,
        price_provider="mock",
    )
    monkeypatch.setattr(plan_api, "get_settings", lambda: settings)
    monkeypatch.setattr(plan_api, "_service", lambda: MustNotRunService())

    client = TestClient(app)
    response = client.post(
        "/api/plan?debug=true",
        json={
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "candidate_recipe_count": 300,
            "candidate_search_limit": 300,
            "beam_width": 100,
            "optimization_iterations": 2,
        },
    )

    assert response.status_code == 422
    assert response.headers["X-Error-Code"] == "consumer_request_budget_exceeded"
    assert called is False


def test_plan_routes_can_reuse_process_lifetime_plan_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "process-lifetime-plans.sqlite3"
    store = PlanStore(path)
    settings = Settings(price_provider="mock", plan_store_path=path)
    request = FastAPIRequest(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/plans/example",
            "headers": [],
            "app": SimpleNamespace(state=SimpleNamespace(plan_store=store)),
        }
    )
    monkeypatch.setattr(plan_api, "get_settings", lambda: settings)

    assert plan_api._store(request) is store


def test_selected_plan_obeys_requested_diet_and_store_limit(
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    assert len(plan.recipes) == 5
    assert all(recipe.instructions for recipe in plan.recipes)
    assert all(recipe.servings == 4 for recipe in plan.recipes)
    assert all(
        recipe_respects_diet(recipe, preference=request.diet_preference)
        for recipe in plan.recipes
    )
    assert plan.optimized_basket.store_count <= 2
    assert plan.portions == 20
    assert any("Strikt sortiment är rådgivande" in warning for warning in plan.warnings)


def test_vegan_guard_rejects_all_animal_canonicals() -> None:
    from app.models import Recipe, RecipeIngredient

    animal_names = (
        "kyckling",
        "kycklinglever",
        "fisk",
        "tonfisk",
        "ägg",
        "mjölk",
        "smör",
        "yoghurt",
        "fetaost",
        "halloumi",
    )
    for name in animal_names:
        recipe = Recipe(
            name=f"Test {name}",
            servings=4,
            ingredients=[RecipeIngredient(name=name, quantity=100, unit="g")],
            instructions=["Tillaga."],
        )
        assert not recipe_respects_diet(recipe, preference="vegan")


def test_vegetarian_guard_uses_semantic_food_family_for_active_canonicals() -> None:
    from app.models import Recipe, RecipeIngredient

    for name in ("tonfisk", "kycklinglever", "kycklinghjärta"):
        recipe = Recipe(
            name=f"Test {name}",
            servings=4,
            ingredients=[RecipeIngredient(name=name, quantity=100, unit="g")],
            instructions=["Tillaga."],
        )
        assert not recipe_respects_diet(recipe, preference="vegetarian")


def test_plan_store_is_append_only_and_metrics_are_privacy_safe(
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    store = PlanStore(tmp_path / "plans.sqlite3")
    owner_actor_hash = "a" * 64
    created = store.create(request, plan, owner_actor_hash=owner_actor_hash)
    revised = store.append(
        plan_id=created.plan_id,
        request=request,
        response=plan,
        operation="product_replaced",
        expected_parent=1,
        owner_actor_hash=owner_actor_hash,
    )

    assert store.get(created.plan_id, revision=1).operation == "created"
    assert store.get(created.plan_id).revision == revised.revision == 2
    assert revised.parent_revision == 1
    with pytest.raises(PlanOwnerMismatchError):
        store.append(
            plan_id=created.plan_id,
            request=request,
            response=plan,
            operation="product_replaced",
            expected_parent=2,
            owner_actor_hash="b" * 64,
        )
    assert store.get(created.plan_id).revision == 2
    metrics = store.aggregate_metrics()
    assert metrics == [
        {
            "diversity_mode": "balanced",
            "diet_preference": "vegetarian",
            "max_stores": 2,
            "meal_count": 5,
            "servings": 4,
            "plans_generated": 1,
        }
    ]
    assert created.plan_id not in str(metrics)


def test_plan_metrics_api_exposes_only_aggregate_dimensions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    path = tmp_path / "metrics.sqlite3"
    created = PlanStore(path).create(request, plan)
    monkeypatch.setenv("PLAN_STORE_PATH", str(path))

    response = TestClient(app).get("/api/metrics/plans")

    assert response.status_code == 200
    body = response.json()
    assert body["dimensions"][0]["plans_generated"] == 1
    assert created.plan_id not in response.text


def test_saved_plan_api_persists_without_repricing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, _request, plan = vegetarian_plan_and_request

    class FakeService:
        async def create_plan(self, _request):
            return plan

    monkeypatch.setattr(plan_api, "_service", lambda: FakeService())
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("PLAN_STORE_PATH", str(tmp_path / "api-plans.sqlite3"))
    client = TestClient(app)
    response = client.post(
        "/api/plans",
        json={
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "diet_preference": "vegetarian",
            "diversity_mode": "balanced",
            "memberships": ["COOP_MEMBER"],
        },
    )
    assert response.status_code == 201, response.text
    saved = response.json()
    loaded = client.get(f"/api/plans/{saved['plan_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["plan"] == saved["plan"]
    assert loaded.json()["revision"] == 1
    assert loaded.json()["request"]["membership_programs"] == ["COOP_MEMBER"]
    assert loaded.json()["request"]["memberships"] == {"coop": True}


def test_saved_plan_reads_and_mutations_require_creating_anonymous_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, _request, plan = vegetarian_plan_and_request
    path = tmp_path / "owned-api-plans.sqlite3"
    secret_key = "test-saved-plan-owner-key-0000000000000001"
    creator_session = "creator-session-00000001"
    other_session = "other-session-0000000002"
    mutation_calls: list[str] = []

    class FakeService:
        async def create_plan(self, _request):
            return plan

    def fake_replace_product(current_plan, _request, **_kwargs):
        mutation_calls.append("product")
        return current_plan

    async def fake_replace_recipe(current_plan, _request, **_kwargs):
        mutation_calls.append("recipe")
        return current_plan

    monkeypatch.setattr(plan_api, "_service", lambda: FakeService())
    monkeypatch.setattr(plan_api, "replace_product", fake_replace_product)
    monkeypatch.setattr(plan_api, "replace_recipe", fake_replace_recipe)
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("PLAN_STORE_PATH", str(path))
    monkeypatch.setenv("SECRET_KEY", secret_key)
    monkeypatch.setenv("PLANNER_RATE_LIMIT_REQUESTS", "1000")
    monkeypatch.setenv("PLANNER_NETWORK_RATE_LIMIT_REQUESTS", "1001")
    client = TestClient(app)
    created = client.post(
        "/api/plans",
        json={
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "diet_preference": "vegetarian",
        },
        headers={"X-Anonymous-Session-ID": creator_session},
    )

    assert created.status_code == 201, created.text
    plan_id = created.json()["plan_id"]
    assert "owner_actor_hash" not in created.text

    wrong_read = client.get(
        f"/api/plans/{plan_id}",
        headers={"X-Anonymous-Session-ID": other_session},
    )
    assert wrong_read.status_code == 403
    assert wrong_read.headers["X-Error-Code"] == "saved_plan_owner_required"

    owned_read = client.get(
        f"/api/plans/{plan_id}",
        headers={"X-Anonymous-Session-ID": creator_session},
    )
    assert owned_read.status_code == 200

    wrong_product = client.post(
        f"/api/plans/{plan_id}/replace-product",
        json={"product_id": "original", "replacement_product_id": "replacement"},
        headers={"X-Anonymous-Session-ID": other_session},
    )
    wrong_recipe = client.post(
        f"/api/plans/{plan_id}/replace-recipe",
        json={"recipe_index": 0},
        headers={"X-Anonymous-Session-ID": other_session},
    )
    assert wrong_product.status_code == 403
    assert wrong_product.headers["X-Error-Code"] == "saved_plan_owner_required"
    assert wrong_recipe.status_code == 403
    assert wrong_recipe.headers["X-Error-Code"] == "saved_plan_owner_required"
    assert mutation_calls == []
    assert PlanStore(path).get(plan_id).revision == 1

    replaced_product = client.post(
        f"/api/plans/{plan_id}/replace-product",
        json={"product_id": "original", "replacement_product_id": "replacement"},
        headers={"X-Anonymous-Session-ID": creator_session},
    )
    replaced_recipe = client.post(
        f"/api/plans/{plan_id}/replace-recipe",
        json={"recipe_index": 0},
        headers={"X-Anonymous-Session-ID": creator_session},
    )
    assert replaced_product.status_code == 200, replaced_product.text
    assert replaced_product.json()["revision"] == 2
    assert replaced_recipe.status_code == 200, replaced_recipe.text
    assert replaced_recipe.json()["revision"] == 3
    assert mutation_calls == ["product", "recipe"]

    expected_owner = pseudonymous_actor(creator_session, Settings.from_env())
    assert expected_owner is not None
    with sqlite3.connect(path) as connection:
        persisted_owners = [
            row[0]
            for row in connection.execute(
                """
                SELECT owner_actor_hash
                FROM consumer_plan_revisions
                WHERE plan_id = ?
                ORDER BY revision
                """,
                (plan_id,),
            ).fetchall()
        ]
        database_dump = "\n".join(connection.iterdump())
    assert persisted_owners == [expected_owner, expected_owner, expected_owner]
    assert len(expected_owner) == 64
    assert creator_session not in database_dump


def test_legacy_saved_plan_migration_keeps_ownerless_plan_read_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    path = tmp_path / "legacy-ownerless-plans.sqlite3"
    saved = PlanStore(path).create(request, plan)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "ALTER TABLE consumer_plan_revisions DROP COLUMN owner_actor_hash"
        )

    migrated = PlanStore(path)
    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(consumer_plan_revisions)"
            ).fetchall()
        }
        migrated_owner = connection.execute(
            """
            SELECT owner_actor_hash
            FROM consumer_plan_revisions
            WHERE plan_id = ?
            """,
            (saved.plan_id,),
        ).fetchone()[0]
    assert "owner_actor_hash" in columns
    assert migrated_owner is None
    assert migrated.get(saved.plan_id).revision == 1
    with pytest.raises(PlanReadOnlyError):
        migrated.get_owned(saved.plan_id, owner_actor_hash="b" * 64)

    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("PLAN_STORE_PATH", str(path))
    monkeypatch.setenv("SECRET_KEY", "test-legacy-owner-key-000000000000000001")
    monkeypatch.setenv("PLANNER_RATE_LIMIT_REQUESTS", "1000")
    monkeypatch.setenv("PLANNER_NETWORK_RATE_LIMIT_REQUESTS", "1001")
    client = TestClient(app)
    headers = {"X-Anonymous-Session-ID": "legacy-reader-session-0001"}
    forbidden_read = client.get(f"/api/plans/{saved.plan_id}", headers=headers)
    forbidden_write = client.post(
        f"/api/plans/{saved.plan_id}/replace-product",
        json={"product_id": "original", "replacement_product_id": "replacement"},
        headers=headers,
    )

    assert forbidden_read.status_code == 403
    assert forbidden_read.headers["X-Error-Code"] == "saved_plan_owner_unavailable"
    assert forbidden_write.status_code == 403
    assert forbidden_write.headers["X-Error-Code"] == "saved_plan_read_only"
    assert PlanStore(path).get(saved.plan_id).revision == 1


def test_consumer_plan_store_never_persists_internal_diagnostics(
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    tainted = plan.model_copy(
        update={
            "source_diagnostics": [{"raw_url": "https://user:secret@example.test"}],
            "debug_info": {"api_key": "must-not-be-persisted", "rows": [1, 2, 3]},
        }
    )
    path = tmp_path / "sanitized-plan.sqlite3"

    saved = PlanStore(path).create(request, tainted)
    loaded = PlanStore(path).get(saved.plan_id)

    assert loaded.plan.source_diagnostics == []
    assert loaded.plan.debug_info is None
    with sqlite3.connect(path) as connection:
        serialized = connection.execute(
            "SELECT response_json FROM consumer_plan_revisions WHERE plan_id = ?",
            (saved.plan_id,),
        ).fetchone()[0]
    assert "must-not-be-persisted" not in serialized
    assert "user:secret" not in serialized


def test_saved_plan_freshness_exposes_actionable_version_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    saved = PlanStore(tmp_path / "freshness.sqlite3").create(request, plan).model_copy(
        update={"price_universe_id": "price-universe:old"}
    )
    prepared = SimpleNamespace(
        universe=SimpleNamespace(universe_id="price-universe:new"),
        status=lambda **_kwargs: SimpleNamespace(status="fresh"),
    )
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: prepared,
    )
    monkeypatch.setattr(plan_api, "get_settings", lambda: Settings(price_provider="mock"))

    annotated = plan_api._annotate_freshness(saved)

    assert annotated.prices_changed_since_creation is True
    assert annotated.price_version_status == "newer_available"
    assert annotated.active_price_freshness == "fresh"
    assert annotated.recalculation_available is True
    assert annotated.plan == saved.plan


def test_saved_plan_detects_same_universe_context_that_became_stale(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    saved = PlanStore(tmp_path / "coverage-freshness.sqlite3").create(
        request, plan
    ).model_copy(update={"price_universe_id": "price-universe:same"})
    used_context_ids = {
        group.store_id for group in saved.plan.optimized_basket.stores
    }
    stale_context_id = min(used_context_ids)
    prepared = SimpleNamespace(
        universe=SimpleNamespace(universe_id=saved.price_universe_id),
        status=lambda **_kwargs: SimpleNamespace(status="degraded"),
        request_view=lambda **_kwargs: SimpleNamespace(
            usable_context_ids=tuple(sorted(used_context_ids - {stale_context_id}))
        ),
    )
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: prepared,
    )
    monkeypatch.setattr(plan_api, "get_settings", lambda: Settings(price_provider="mock"))

    annotated = plan_api._annotate_freshness(saved)

    assert annotated.prices_changed_since_creation is False
    assert annotated.price_contexts_changed_since_creation is True
    assert annotated.unavailable_saved_context_ids == (stale_context_id,)
    assert annotated.price_version_status == "coverage_changed"
    assert annotated.active_price_freshness == "degraded"
    assert annotated.recalculation_available is True
    assert annotated.plan.optimized_basket == saved.plan.optimized_basket


def test_consumer_price_context_coverage_separates_compared_and_stale_lineage() -> None:
    observed_at = datetime(2026, 9, 1, 3, 17, tzinfo=UTC)
    compared_store = Store(
        store_id="own:coop:730400",
        name="Coop Online Syd",
        chain="coop",
        city="Lund",
        price_context_type="online_fulfillment",
        price_semantics="online_price",
        price_label="Coop onlinepris",
        source_provenance=SourceProvenance(
            source_provider="coop_own",
            source_channel="full_catalog",
            source_snapshot_id="snapshot:coop:fresh",
            source_observed_at=observed_at,
        ),
    )
    stale_store = Store(
        store_id="own:willys:old",
        name="Willys Lund",
        chain="willys",
        city="Lund",
        source_provenance=SourceProvenance(
            source_provider="willys_own",
            source_channel="full_catalog",
            source_snapshot_id="snapshot:willys:old",
            source_observed_at=observed_at,
        ),
    )
    prepared = SimpleNamespace(
        stores=(compared_store, stale_store),
        universe=SimpleNamespace(products=()),
    )

    compared, unavailable = _consumer_price_context_coverage(
        prepared,
        usable_context_ids=(compared_store.store_id,),
        excluded_stale_context_ids=(stale_store.store_id,),
    )

    assert [(row.display_name, row.status) for row in compared] == [
        ("Coop Online Syd", "compared")
    ]
    assert compared[0].price_scope_label == "Coop onlinepris"
    assert compared[0].snapshot_ids == ("snapshot:coop:fresh",)
    assert [(row.display_name, row.status) for row in unavailable] == [
        ("Willys Lund", "excluded_stale")
    ]
    assert unavailable[0].snapshot_ids == ("snapshot:willys:old",)


def test_saved_plan_endpoint_rejects_nonlocal_price_source(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, _request, plan = vegetarian_plan_and_request
    unsafe = plan.model_copy(update={"data_source": "primat"})

    class FakeService:
        async def create_plan(self, _request):
            return unsafe

    monkeypatch.setattr(plan_api, "_service", lambda: FakeService())
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("PLAN_STORE_PATH", str(tmp_path / "unsafe.sqlite3"))
    response = TestClient(app).post(
        "/api/plans",
        json={"recipes": 5, "servings": 4, "max_stores": 2},
    )
    assert response.status_code == 503


def test_offline_preflight_fails_before_service_or_provider_can_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    called = False

    class MustNotRunService:
        async def create_plan(self, _request):
            nonlocal called
            called = True
            raise AssertionError("planning must not start without a local universe")

    monkeypatch.setattr(plan_api, "_service", lambda: MustNotRunService())
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setenv("PRICE_PROVIDER", "auto")
    monkeypatch.setenv("PLAN_STORE_PATH", str(tmp_path / "never-created.sqlite3"))
    response = TestClient(app).post(
        "/api/plans",
        json={"recipes": 5, "servings": 4, "max_stores": 2},
    )
    assert response.status_code == 503
    assert called is False
    assert not (tmp_path / "never-created.sqlite3").exists()


def test_product_and_recipe_replacements_reprice_only_saved_candidates(
    vegetarian_plan_and_request,
) -> None:
    settings, request, plan = vegetarian_plan_and_request
    selected = next(
        item
        for group in plan.optimized_basket.stores
        for item in group.items
        if product_alternatives(plan, item.product_id)
    )
    alternative = product_alternatives(plan, selected.product_id)[0]
    product_changed = replace_product(
        plan,
        request,
        product_id=selected.product_id,
        replacement_product_id=alternative.product_id,
    )
    assert any(
        item.product_id == alternative.product_id
        for group in product_changed.optimized_basket.stores
        for item in group.items
    )
    assert product_changed.optimized_basket.store_count <= request.max_stores
    assert [row.recipe_name for row in product_changed.recipe_costs] == [
        recipe.name for recipe in product_changed.recipes
    ]
    assert round(sum(row.allocated_basket_cost for row in product_changed.recipe_costs), 2) == round(
        product_changed.optimized_basket.total,
        2,
    )
    assert all(row.incremental_ingredient_cost is None for row in product_changed.recipe_costs)

    candidates = replacement_recipe_candidates(plan)
    assert candidates
    recipe_changed = asyncio.run(
        replace_recipe(
            plan,
            request,
            recipe_index=0,
            replacement_recipe_name=None,
            settings=settings,
        )
    )
    assert recipe_changed.recipes[0].name != plan.recipes[0].name
    assert recipe_changed.quality is not None
    assert recipe_changed.quality.status == "PASS"
    assert recipe_changed.optimized_basket.store_count <= request.max_stores
    assert [row.recipe_name for row in recipe_changed.recipe_costs] == [
        recipe.name for recipe in recipe_changed.recipes
    ]
    assert round(sum(row.allocated_basket_cost for row in recipe_changed.recipe_costs), 2) == round(
        recipe_changed.optimized_basket.total,
        2,
    )


def test_exact_gtin_lookup_is_local_and_does_not_invent_physical_store_id() -> None:
    product = MockPriceProvider()._products[0].model_copy(
        update={"gtin": "7391737003437"}
    )
    prepared = SimpleNamespace(
        universe=SimpleNamespace(
            universe_id="price-universe:test",
            products_for_gtin=lambda gtin: (product,) if gtin == "7391737003437" else (),
        )
    )
    result = lookup_gtin(prepared, "7391737003437")
    assert result.found
    assert result.product is not None
    assert result.prices[0].physical_store_id is None
    assert result.live_provider_calls == 0


def test_exact_gtin_lookup_keeps_public_and_generic_member_prices_distinct() -> None:
    product = MockPriceProvider()._products[0].model_copy(
        update={
            "gtin": "7391737003437",
            "chain": "coop",
            "price": 32.95,
            "effective_price": 29.95,
            "member_price": 24.95,
            "offers": [
                OfferMetadata(
                    kind=OfferKind.CAMPAIGN,
                    description="Publik kampanj",
                    price=29.95,
                ),
                OfferMetadata(
                    kind=OfferKind.MEMBER,
                    description="Coop medlemspris",
                    price=24.95,
                    member_program="Coop medlem",
                ),
            ],
        }
    )
    prepared = SimpleNamespace(
        universe=SimpleNamespace(
            universe_id="price-universe:test",
            products_for_gtin=lambda gtin: (product,) if gtin == "7391737003437" else (),
        )
    )

    result = lookup_gtin(prepared, "7391737003437")

    price = result.prices[0]
    assert price.regular_price == 32.95
    assert price.current_public_price == 29.95
    assert price.member_price == 24.95
    assert price.membership_program is MembershipProgram.COOP_MEMBER


def test_exact_gtin_lookup_does_not_expose_an_excluded_stale_context() -> None:
    product = MockPriceProvider()._products[0].model_copy(
        update={"gtin": "7391737003437", "store_id": "context:coop:stale"}
    )
    prepared = SimpleNamespace(
        universe=SimpleNamespace(
            universe_id="price-universe:test",
            products_for_gtin=lambda gtin: (product,) if gtin == "7391737003437" else (),
        )
    )

    result = lookup_gtin(
        prepared,
        "7391737003437",
        allowed_context_ids={"context:willys:fresh"},
    )

    assert result.found is False
    assert result.prices == []


def test_plan_product_report_binds_server_provenance_and_is_advisory_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    vegetarian_plan_and_request,
) -> None:
    _settings, request, plan = vegetarian_plan_and_request
    owner_session = "consumer-report-session"
    monkeypatch.setenv("SECRET_KEY", "test-report-owner-key-000000000000000001")
    owner_actor_hash = pseudonymous_actor(owner_session, Settings.from_env())
    assert owner_actor_hash is not None
    first_group = plan.optimized_basket.stores[0]
    first_item = first_group.items[0].model_copy(
        update={
            "gtin": "7391737003437",
            "chain": "hemkop",
            "source_provenance": SourceProvenance(
                source_provider="hemkop_own",
                source_channel="full_catalog",
                source_snapshot_id="snapshot:server-authoritative",
                source_observed_at=datetime(2026, 8, 31, 10, 0, tzinfo=UTC),
                chain="hemkop",
                store_id=first_group.store_id,
                store_name=first_group.store_name,
            ),
        }
    )
    group = first_group.model_copy(update={"items": [first_item, *first_group.items[1:]]})
    basket = plan.optimized_basket.model_copy(
        update={"stores": [group, *plan.optimized_basket.stores[1:]]}
    )
    plan = plan.model_copy(update={"optimized_basket": basket})
    plan_path = tmp_path / "report-plan.sqlite3"
    saved = PlanStore(plan_path).create(
        request,
        plan,
        owner_actor_hash=owner_actor_hash,
    )

    evidence_path = tmp_path / "community.sqlite3"
    engine = create_database_engine(f"sqlite+pysqlite:///{evidence_path.as_posix()}")
    create_schema(engine)
    factory = create_session_factory(engine)
    physical_store_id = "physical:hemkop:4123"
    now = datetime.now(tz=UTC)
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id=physical_store_id,
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                city="Lund",
                official_source="fixture",
                discovered_at=now,
                last_seen_at=now,
            )
        )
        session.add(
            StoreContextLinkModel(
                physical_store_id=physical_store_id,
                grocery_context_id=first_item.store_id,
                source_provider="hemkop_own",
                source_channel="full_catalog",
                grocery_context_name=first_group.store_name,
                relation_type="exact",
                confidence="high",
                linked_at=now,
                last_verified_at=now,
            )
        )
        session.commit()

    monkeypatch.setenv("PLAN_STORE_PATH", str(plan_path))
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("community reporting must not read or mutate PriceUniverse")
        ),
    )
    previous_factory = app.state.community_session_factory
    previous_settings = app.state.community_evidence_settings
    app.state.community_session_factory = factory
    app.state.community_evidence_settings = GroceryDataSettings(
        database_url=f"sqlite+pysqlite:///{evidence_path.as_posix()}",
        raw_snapshot_root=tmp_path / "raw",
        user_agent="consumer-api-test",
    )
    with sqlite3.connect(plan_path) as connection:
        before_plan_json = connection.execute(
            "SELECT response_json FROM consumer_plan_revisions WHERE plan_id = ?",
            (saved.plan_id,),
        ).fetchone()[0]
    client = TestClient(app)
    base_payload = {
        "evidence_type": "PRICE_DIFFERENCE",
        "evidence_source": "SHELF_PRICE",
        "anonymous_session_id": owner_session,
        "observed_at": now.isoformat(),
        "physical_store_id": physical_store_id,
        "shelf_price": "32.00",
        "price_unit": "kr/st",
    }
    report_url = (
        f"/api/plans/{saved.plan_id}/products/{first_item.product_id}/report"
    )
    try:
        forged = client.post(
            report_url,
            json={
                **base_payload,
                "source_product_id": "forged-product",
                "price_snapshot_id": "snapshot:forged",
                "digital_price": "0.01",
                "grocery_context_id": "context:forged",
            },
            headers={
                "Idempotency-Key": "report-forged-0001",
                "X-Anonymous-Session-ID": owner_session,
            },
        )
        assert forged.status_code == 422

        response = client.post(
            report_url,
            json=base_payload,
            headers={
                "Idempotency-Key": "report-valid-000001",
                "X-Anonymous-Session-ID": owner_session,
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["plan_id"] == saved.plan_id
        assert body["source_product_id"] == first_item.product_id
        assert body["gtin"] == "7391737003437"
        assert body["grocery_context_id"] == first_item.store_id
        assert body["price_snapshot_id"] == "snapshot:server-authoritative"
        assert float(body["digital_price"]) == first_item.unit_price
        assert body["physical_store_id"] == physical_store_id
        assert body["store_identity_verified"] is True
    finally:
        app.state.community_session_factory = previous_factory
        app.state.community_evidence_settings = previous_settings
        engine.dispose()

    with sqlite3.connect(plan_path) as connection:
        after_plan_json = connection.execute(
            "SELECT response_json FROM consumer_plan_revisions WHERE plan_id = ?",
            (saved.plan_id,),
        ).fetchone()[0]
    assert after_plan_json == before_plan_json
    with factory() as session:
        assert session.scalar(select(func.count(CommunityEvidenceObservationModel.id))) == 1
        assert session.scalar(select(func.count(SourceProductModel.id))) == 0
