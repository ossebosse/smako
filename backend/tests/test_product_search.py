from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from app.models import Product, Store
from app.models.product import OfferMetadata
from app.models.provenance import SourceProvenance
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverse, PreparedPriceUniverseManager
from app.services.product_search import ProductSearchRequest, search_text
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)
GTIN = "7311043007851"


def product(i="a", store="hemkop", **changes):
    return Product.model_validate(
        {
            "product_id": i,
            "name": "Gevalia kaffe 450 g",
            "brand": "Gevalia",
            "canonical_name": "kaffe",
            "category": "kaffe",
            "chain": store,
            "store_id": store,
            "store_name": store,
            "price": 49.9,
            "package_quantity": 450,
            "package_unit": "g",
            "quantity_confidence": "exact",
            "gtin": GTIN,
            "source_provenance": SourceProvenance(
                source_provider="own",
                source_channel="catalog",
                source_snapshot_id="frozen",
                source_observed_at=NOW,
                store_id=store,
            ),
            **changes,
        }
    )


def prepare(*rows, version="one"):
    key = PriceUniverseKey.create(
        city="Lund",
        postal_codes=["22350"],
        snapshot_ids=["frozen"],
        source_strategy_version=version,
        normalizer_version="v1",
        taxonomy_version="v1",
    )
    universe = PriceUniverseBuilder().build(key, rows, built_at=NOW)
    stores = tuple(
        Store(
            store_id=s,
            name="Coop Online Syd" if s == "coop" else s,
            chain=s,
            city="Lund",
            price_context_type=("online_fulfillment" if s == "coop" else "physical_store"),
            price_semantics="online_price" if s == "coop" else None,
        )
        for s in sorted({r.store_id for r in rows})
    )
    return PreparedPriceUniverse(
        universe=universe,
        stores=stores,
        economic_pool=EconomicIngredientPool(),
        source_name="frozen",
    )


def search(prepared, query="kaffe", now=NOW, **kwargs):
    return prepared.product_search_index.search(
        ProductSearchRequest(query=query, **kwargs), now=now
    )


def offer(**changes):
    return OfferMetadata.model_validate(
        {
            "kind": "campaign",
            "description": "Veckans kaffe",
            "price": 39.9,
            "valid_from": NOW.date(),
            "valid_to": NOW.date(),
            **changes,
        }
    )


@pytest.mark.parametrize(
    "query",
    [
        GTIN,
        "Gevalia kaffe 450 g",
        "GEVALIA KAFFE 450 G",
        "kaffe",
        "kaffet",
        "Gevalia",
        "450g",
        "0,45 kg",
    ],
)
def test_retrieval(query):
    result = search(prepare(product()), query)
    assert result["total"] == 1
    assert result["results"][0]["identity_basis"] == "verified_gtin"


def test_swedish_case_quantity_plural():
    assert search_text("MJÖLKEN") == "mjolk"
    assert search_text("kycklingfiléer") == "kycklingfile"
    p = prepare(product(name="Arla mellanmjölk", package_quantity=1500, package_unit="ml"))
    assert search(p, "mjölk")["total"] == 1
    assert search(p, "mellanmjölk 1,5 l")["total"] == 1


def test_exact_identity_prices_sort_and_online_semantics():
    result = search(prepare(product(), product("b", "coop", price=42.9)), GTIN)
    assert result["semantics"] == "exact_identity"
    row = result["results"][0]
    assert len(row["prices"]) == 2
    assert row["prices"][0]["store_name"] == "Coop Online Syd"
    assert row["prices"][0]["context_type"] == "online_fulfillment"
    assert row["prices"][0]["context_label"] == "Onlinepris"
    assert "inte lagerbesked" in row["prices"][0]["availability_label"]
    assert "Stora Coop" not in str(result)


def test_generic_compound_head_excludes_accessories_and_flavoured_sweets():
    p = prepare(
        product(name="Bryggkaffe"),
        product("b", name="Kaffemått", category="Köksredskap", gtin=None),
    )
    assert search(p)["total"] == 1
    p = prepare(product(name="Mellanmjölk"), product("b", name="Mjölkchoklad", gtin=None))
    assert search(p, "mjölk")["total"] == 1


def test_text_prefix_never_creates_identity():
    result = search(prepare(product(gtin=None), product("b", "coop", gtin=None)), "Geval")
    assert result["semantics"] == "matching_alternatives"
    assert result["total"] == 2
    assert all(len(r["prices"]) == 1 for r in result["results"])
    assert all(r["identity_basis"] == "context_product" for r in result["results"])


def test_conflicting_packages_even_shared_gtin_do_not_merge():
    result = search(prepare(product(), product("b", "coop", package_quantity=500)), GTIN)
    assert result["total"] == 2
    assert result["semantics"] == "matching_alternatives"


def test_invalid_source_gtin_never_establishes_identity():
    result = search(prepare(product(gtin="7311043007852")), "kaffe")
    assert result["results"][0]["gtin"] is None
    assert result["results"][0]["identity_basis"] == "context_product"


def test_duplicate_listing_not_an_additional_store():
    p = prepare(product(), product("duplicate"))
    assert len(search(p)["results"][0]["prices"]) == 1
    assert search(p, view="multiple")["total"] == 0


def test_coffee_additive_remains_searchable_but_not_a_generic_coffee():
    p = prepare(product(), product("oat", name="Havredryck Till Kaffe", gtin=None))
    assert search(p)["total"] == 1
    assert search(p, "Havredryck Till Kaffe")["total"] == 1


def test_generic_food_respects_existing_non_human_food_classification():
    p = prepare(
        product(
            name="Kycklingfilé",
            canonical_food="non_human_food",
            product_role="non_human_food",
            category="Hundgodis",
        )
    )
    assert search(p, "kycklingfilé")["total"] == 0
    assert search(p, GTIN)["total"] == 1


def test_unit_normalization_and_incompatible_dimensions():
    p = prepare(product(), product("b", "coop", gtin=None, package_unit="ml"))
    rows = search(p)["results"]
    assert {r["prices"][0]["unit"] for r in rows} == {"kg", "l"}
    result = search(p, view="unit", unit="kg")
    assert result["total"] == 1
    assert result["results"][0]["sort_unit_price"] == 110.89


@pytest.mark.parametrize("confidence", ["estimated", "unknown"])
def test_uncertain_quantity_not_normalized(confidence):
    row = search(prepare(product(quantity_confidence=confidence)))["results"][0]
    assert row["prices"][0]["unit_price"] is None


def test_weight_rate_never_called_package_price():
    p = product(sale_model="sold_by_weight", sale_unit="kg")
    row = search(prepare(p))["results"][0]
    assert row["best_price"] is None
    assert row["prices"][0]["price_basis"] == "not_compared"


def test_public_campaign():
    row = search(prepare(product(offers=[offer()])), view="campaigns")["results"][0]
    assert row["best_price"] == 39.9
    assert row["prices"][0]["promotions"][0]["valid_to"] == NOW.date()


def test_member_selected_and_not_selected_and_cache_isolation():
    p = prepare(product(offers=[offer(kind="member", member_program="hemkop", price=29.9)]))
    ordinary = search(p)
    member = search(p, memberships=["HEMKOP_MEMBER"])
    assert ordinary["results"][0]["best_price"] == 49.9
    assert member["results"][0]["best_price"] == 29.9
    assert member["results"][0]["prices"][0]["membership_required"]
    assert not ordinary["results"][0]["prices"][0]["promotions"][0]["eligible"]
    assert search(p) == ordinary


def test_flat_member_price_reuses_contract_projection():
    p = prepare(product(member_price=30))
    assert search(p)["results"][0]["best_price"] == 49.9
    assert search(p, memberships=["HEMKOP_MEMBER"])["results"][0]["best_price"] == 30


def test_multibuy_not_unconditional_package_price():
    p = prepare(product(offers=[offer(kind="multipack", required_packages=2, price=60)]))
    row = search(p)["results"][0]
    assert row["best_price"] == 49.9
    assert row["prices"][0]["promotions"][0]["required_packages"] == 2


def test_expired_flattened_campaign_excluded_and_date_cache_changes():
    p = prepare(product(offers=[offer()], effective_price=39.9))
    assert search(p)["results"][0]["best_price"] == 39.9
    result = search(p, now=NOW + timedelta(days=1))
    assert result["results"][0]["best_price"] == 49.9
    assert not result["results"][0]["has_campaign"]
    assert search(p, now=NOW + timedelta(days=1), view="campaigns")["total"] == 0


def test_personal_and_invalid_promotions_rejected():
    with pytest.raises(ValidationError):
        offer(eligibility="user_specific")
    with pytest.raises(ValidationError):
        offer(valid_to=NOW.date() - timedelta(days=1))
    invalid = offer(eligibility="member", member_program="coop")
    row = search(prepare(product(offers=[invalid])))["results"][0]
    assert not row["has_campaign"]
    assert row["best_price"] == 49.9


def test_stale_and_aging_cache_boundaries():
    p = prepare(product())
    assert search(p)["results"][0]["prices"][0]["freshness"] == "FRESH"
    assert (
        search(p, now=NOW + timedelta(hours=36))["results"][0]["prices"][0]["freshness"] == "AGING"
    )
    result = search(p, now=NOW + timedelta(hours=48))
    assert result["total"] == 0
    assert result["excluded_stale_context_count"] == 1


def test_ineligible_context_absent():
    p = prepare(product(), product("b", "coop", price=10))
    p = replace(p, stores=tuple(s for s in p.stores if s.chain != "coop"))
    assert search(p)["results"][0]["best_price"] == 49.9


def test_unknown_context_type_does_not_imply_store_link():
    p = prepare(product())
    p = replace(
        p, stores=tuple(s.model_copy(update={"price_context_type": None}) for s in p.stores)
    )
    assert search(p)["results"][0]["prices"][0]["context_label"] == "Annat prisunderlag"


def test_pagination_and_product_detail():
    p = prepare(*(product(str(i), gtin=None) for i in range(45)))
    first = search(p, limit=20)
    second = search(p, limit=20, offset=20)
    assert first["total"] == 45 and first["next_offset"] == 20
    assert len(second["results"]) == 20 and second["next_offset"] == 40
    assert {r["product_key"] for r in first["results"]}.isdisjoint(
        r["product_key"] for r in second["results"]
    )
    key = first["results"][0]["product_key"]
    assert search(p, product_key=key)["total"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"query": ""},
        {"query": "x" * 121},
        {"query": "* OR ()", "limit": 0},
        {"limit": 41},
        {"offset": -1},
        {"offset": 1001},
        {"postal_code": "22x50"},
        {"memberships": ["other"]},
        {"memberships": ["COOP_MEMBER"] * 7},
        {"query": "7311043007852"},
    ],
)
def test_bounds(changes):
    with pytest.raises(ValidationError):
        ProductSearchRequest.model_validate({"query": "kaffe", **changes})


def test_universe_cache_isolation():
    first = prepare(product(), version="one")
    second = prepare(product(price=20), version="two")
    assert search(first)["results"][0]["best_price"] == 49.9
    assert search(second)["results"][0]["best_price"] == 20
    assert search(first)["price_universe_id"] != search(second)["price_universe_id"]


def test_api_anonymous_area_bounds_no_provider_or_network(monkeypatch):
    from app.api import product_search as api

    manager = PreparedPriceUniverseManager()
    manager.activate(prepare(product()))
    monkeypatch.setattr(api, "GLOBAL_PREPARED_PRICE_UNIVERSES", manager)
    application = FastAPI()
    application.include_router(api.router)

    class Clock:
        @staticmethod
        def now(**kwargs):
            return NOW

    monkeypatch.setattr(api, "datetime", Clock)
    with (
        TestClient(application) as client,
        patch("socket.socket.connect", side_effect=AssertionError("network")),
    ):
        response = client.post("/api/product-search", json={"query": GTIN})
        assert response.status_code == 200
        assert response.json()["exact_gtin"] and response.json()["live_provider_calls"] == 0
        assert response.headers["cache-control"] == "no-store"
        assert (
            client.post(
                "/api/product-search", json={"query": "kaffe", "postal_code": "11111"}
            ).status_code
            == 422
        )
        assert (
            client.post("/api/product-search", json={"query": "kaffe", "view": "unit"}).status_code
            == 422
        )


def coverage(response, chain):
    return next(c for c in response["chain_coverage"] if c["chain"] == chain)


def test_generic_willys_without_gtin_is_ranked_by_price_not_identity_strength():
    p = prepare(product(store="willys", gtin=None, price=20), product(store="coop", price=45))
    with patch("socket.socket.connect", side_effect=AssertionError("provider network")):
        response = search(p, limit=1)
    assert response["results"][0]["prices"][0]["chain"] == "willys"
    assert response["results"][0]["identity_basis"] == "context_product"
    assert coverage(response, "willys")["status"] == "VISIBLE"
    assert coverage(response, "coop")["reason"] == "outside_page"
    assert response["live_provider_calls"] == 0


def test_willys_hemkop_identical_names_are_separate_alternatives_and_not_gtin_matches():
    p = prepare(product(store="willys", gtin=None), product(store="hemkop", gtin=None))
    response = search(p, query="Gevalia kaffe 450 g")
    assert response["total"] == 2
    assert all(r["comparison_semantics"] == "single_context_product" for r in response["results"])
    assert all(len(r["prices"]) == 1 for r in response["results"])
    exact = search(p, query=GTIN)
    assert exact["total"] == 0
    assert coverage(exact, "willys")["reason"] == "no_exact_identity"


def test_stale_ica_then_genuine_new_snapshot_normal_activation(tmp_path):
    old = product(store="ica").model_copy(
        update={
            "source_provenance": product(store="ica").source_provenance.model_copy(
                update={"source_observed_at": NOW - timedelta(hours=49)}
            )
        }
    )
    manager = PreparedPriceUniverseManager()
    old_path = tmp_path / "old.json"
    manager.write_artifact(prepare(old, product(store="coop")), old_path)
    before = manager.load_file_and_activate(old_path)
    assert coverage(search(before), "ica")["status"] == "STALE"
    assert all(
        price["chain"] != "ica" for row in search(before)["results"] for price in row["prices"]
    )
    # Frozen new-observation fixture, never an altered production observation.
    fresh = prepare(product(store="ica"), product(store="coop"), version="new-snapshot")
    new_path = tmp_path / "new.json"
    manager.write_artifact(fresh, new_path)
    after = manager.load_file_and_activate(new_path)
    assert after.product_search_index is not before.product_search_index
    assert coverage(search(after), "ica")["status"] == "VISIBLE"
    assert search(after)["price_universe_id"] != search(before)["price_universe_id"]
    assert coverage(search(before), "ica")["status"] == "STALE"


def test_coverage_distinguishes_missing_context_query_and_filter():
    p = prepare(product(store="willys", gtin=None))
    assert coverage(search(p), "ica")["reason"] == "no_eligible_price_context"
    assert coverage(search(p, query="pasta"), "willys")["status"] == "NO_MATCH"
    assert coverage(search(p, view="campaigns"), "willys")["reason"] == "filtered_out"
    assert coverage(search(p, view="multiple"), "willys")["reason"] == "filtered_out"


def test_coverage_changes_at_freshness_boundary_and_membership_price_isolated():
    p = prepare(
        product(
            store="willys",
            gtin=None,
            offers=[offer(kind="member", price=29.9, member_program="willys")],
        ),
        product(store="coop"),
    )
    public = search(p)
    member = search(p, memberships=("WILLYS_PLUS",))
    assert coverage(public, "willys")["status"] == "VISIBLE"
    assert coverage(member, "willys")["status"] == "VISIBLE"
    w = next(r for r in member["results"] if r["prices"][0]["chain"] == "willys")
    assert w["best_price"] == 29.9 and w["prices"][0]["membership_required"]
    assert all(r["best_price"] == 49.9 for r in public["results"])
    coop = next(
        price for r in public["results"] for price in r["prices"] if price["chain"] == "coop"
    )
    assert coop["context_type"] == "online_fulfillment"
    assert (
        coop["context_label"] == "Onlinepris" and "inte lagerbesked" in coop["availability_label"]
    )
    assert coverage(search(p, now=NOW + timedelta(hours=48)), "willys")["status"] == "STALE"
    assert coverage(search(p, now=NOW + timedelta(hours=47)), "willys")["status"] == "VISIBLE"


def test_relay_location_is_exposed_without_changing_own_source_or_identity():
    row = product(store="willys", gtin=None)
    source = row.source_provenance.model_copy(update={"collection_location": "LOCAL_RELAY"})
    row = row.model_copy(update={"source_provenance": source})
    response = search(prepare(row))
    result = response["results"][0]
    assert result["identity_basis"] == "context_product"
    assert result["prices"][0]["source_provider"] == "own"
    assert result["prices"][0]["collection_location"] == "LOCAL_RELAY"
    assert response["live_provider_calls"] == 0
