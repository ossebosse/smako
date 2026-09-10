from __future__ import annotations

import pytest
from app.models import Product, QuantityConfidence, SaleModel
from scripts.benchmark_store_limits import (
    LiveVerificationAssertionError,
    _candidate_semantics_assertions,
    _live_assertions,
    _snapshot_assertions,
    _verification_details,
)


def _cached_product(product_id: str, name: str) -> Product:
    return Product(
        product_id=product_id,
        name=name,
        canonical_name=name,
        category="Livsmedel",
        store_id="store-1",
        store_name="Testbutiken",
        price=20,
        sale_price=20,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        quantity_confidence=QuantityConfidence.EXACT,
    )


def _item(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "ingredient": "kyckling",
        "product_name": "Kycklinglårfilé 1 kg",
        "canonical_food": "chicken",
        "food_family": "poultry",
        "product_role": "thigh",
        "product_form": "thigh_fillet",
        "semantic_confidence": "high",
        "sale_model": "fixed_package",
        "sale_price": 69.90,
        "sale_unit": None,
        "comparison_price": 69.90,
        "comparison_unit": "kg",
        "required_quantity": 800.0,
        "unit": "g",
        "package_quantity": 1000.0,
        "package_unit": "g",
        "packages_needed": 1,
        "purchased_quantity": 1000.0,
        "purchased_unit": "g",
        "purchased_usable_quantity": 1000.0,
        "quantity_confidence": "exact",
        "total_price": 69.90,
        "purchase_warning": None,
        "verification_status": "VERIFIED",
    }
    row.update(overrides)
    return row


def _data(items: list[dict[str, object]]) -> dict[str, object]:
    return {
        "optimized_basket": {
            "verification_status": "VERIFIED_WITH_ESTIMATES",
            "verification_warnings": ["Matkassen innehåller uppskattade mängder."],
            "stores": [
                {
                    "store_name": "Testbutiken",
                    "items": items,
                }
            ],
        },
        "quality": {
            "basket_audit": {
                "status": "PASS",
                "verification_status": "VERIFIED_WITH_ESTIMATES",
                "deficits": [],
                "items": [
                    {
                        "selected_products": [
                            {"quantity_reconciled": True, "cost_reconciled": True} for _ in items
                        ]
                    }
                ],
            }
        },
    }


def test_live_summary_proves_safe_semantics_and_prorated_weight() -> None:
    paprika = _item(
        ingredient="paprika",
        product_name="Paprika Röd",
        canonical_food="pepper",
        food_family="vegetable",
        product_role="whole_vegetable",
        product_form="fresh",
        sale_model="sold_by_weight",
        sale_price=39.90,
        sale_unit="kg",
        comparison_price=39.90,
        comparison_unit="kg",
        required_quantity=350.0,
        package_quantity=None,
        package_unit=None,
        packages_needed=1,
        purchased_quantity=350.0,
        purchased_unit="g",
        purchased_usable_quantity=350.0,
        quantity_confidence="derived",
        total_price=13.97,
    )
    data = _data([_item(), paprika])

    assertions = _live_assertions(data)
    details = _verification_details(data)

    assert assertions["generic_chicken_is_not_organ_meat"]["status"] == "PASS"
    assert assertions["comparison_price_is_not_package_size"] == {
        "status": "PASS",
        "items_checked": 1,
    }
    assert assertions["sold_by_weight_cost_is_prorated"]["status"] == "PASS"
    assert assertions["garlic_is_not_garlic_bread"]["status"] == "NOT_APPLICABLE"
    assert details["status"] == "VERIFIED_WITH_ESTIMATES"
    assert details["products"][1]["purchase"] == {
        "sale_model": "sold_by_weight",
        "sale_price": 39.90,
        "sale_unit": "kg",
        "comparison_price": 39.90,
        "comparison_unit": "kg",
        "required_quantity": 350.0,
        "required_unit": "g",
        "package_quantity": None,
        "package_unit": None,
        "packages_needed": 1,
        "purchased_quantity": 350.0,
        "purchased_unit": "g",
        "purchased_usable_quantity": 350.0,
        "quantity_confidence": "derived",
        "cost": 13.97,
        "warning": None,
    }


def test_live_assertions_reject_generic_chicken_heart() -> None:
    data = _data(
        [
            _item(
                product_name="Kycklinghjärta Fryst",
                product_role="heart",
                product_form="organ",
            )
        ]
    )

    with pytest.raises(LiveVerificationAssertionError) as raised:
        _live_assertions(data)

    assert raised.value.failed == ("generic_chicken_is_not_organ_meat",)


@pytest.mark.parametrize(
    ("failed_assertion", "item_overrides"),
    [
        (
            "generic_fish_is_not_canned_tuna",
            {
                "ingredient": "fisk",
                "product_name": "Tonfisk i solrosolja 3-pack",
                "product_role": "generic_fish",
                "product_form": "meat",
            },
        ),
        (
            "raw_broccoli_is_not_ambiguous_mixture",
            {
                "ingredient": "broccoli",
                "product_name": "Broccoli Mix",
                "product_role": "whole_vegetable",
                "product_form": "fresh",
            },
        ),
        (
            "raw_carrot_is_not_fermented_or_pickled_mixture",
            {
                "ingredient": "morot",
                "product_name": "Surkål Med Morötter",
                "product_role": "whole_vegetable",
                "product_form": "fresh",
            },
        ),
        (
            "garlic_is_not_processed_condiment",
            {
                "ingredient": "vitlök",
                "product_name": "Salsa Vitlök Medium",
                "product_role": "bulb",
                "product_form": "fresh",
            },
        ),
        (
            "raw_garlic_has_safe_role_form_and_no_olive",
            {
                "ingredient": "vitlök",
                "product_name": "Snacksoliver Vitlök Fyllda",
                "product_role": "bulb",
                "product_form": "fresh",
            },
        ),
    ],
)
def test_live_assertions_reject_semantically_unsafe_verified_shaped_items(
    failed_assertion: str,
    item_overrides: dict[str, object],
) -> None:
    data = _data([_item(**item_overrides)])

    with pytest.raises(LiveVerificationAssertionError) as raised:
        _live_assertions(data)

    assert raised.value.failed == (failed_assertion,)


def test_live_assertions_reject_unknown_purchase_model() -> None:
    data = _data(
        [
            _item(
                sale_model="unknown",
                quantity_confidence="unknown",
                verification_status="UNVERIFIED",
            )
        ]
    )

    with pytest.raises(LiveVerificationAssertionError) as raised:
        _live_assertions(data)

    assert "all_purchase_models_are_resolved" in raised.value.failed


def test_live_assertions_reject_auditor_cost_disagreement() -> None:
    data = _data([_item()])
    selected = data["quality"]["basket_audit"]["items"][0]["selected_products"][0]
    selected["cost_reconciled"] = False

    with pytest.raises(LiveVerificationAssertionError) as raised:
        _live_assertions(data)

    assert "audit_passes_and_reconciles" in raised.value.failed


def test_snapshot_assertions_require_second_pass_to_be_fully_cached() -> None:
    passes = [
        {
            "product_cache_entries_added": 42,
            "network_requests_added": 43,
            "candidate_sample_fingerprint": "same",
        },
        {
            "product_cache_entries_added": 0,
            "network_requests_added": 0,
            "candidate_sample_fingerprint": "same",
        },
    ]

    assertions = _snapshot_assertions(passes, live_store_fetches=1)

    assert all(result["status"] == "PASS" for result in assertions.values())


def test_snapshot_assertions_reject_a_second_network_fetch() -> None:
    passes = [
        {
            "product_cache_entries_added": 42,
            "network_requests_added": 43,
            "candidate_sample_fingerprint": "first",
        },
        {
            "product_cache_entries_added": 1,
            "network_requests_added": 1,
            "candidate_sample_fingerprint": "second",
        },
    ]

    with pytest.raises(LiveVerificationAssertionError) as raised:
        _snapshot_assertions(passes, live_store_fetches=1)

    assert set(raised.value.failed) == {
        "candidate_sample_matches",
        "second_pass_added_no_product_cache_entries",
        "second_pass_made_no_network_requests",
    }


def test_candidate_semantics_audits_observed_traps_from_existing_cache() -> None:
    cache = {
        ("meal-search", ("store-1",)): (
            _cached_product("chicken-thigh", "Kycklinglårfilé"),
            _cached_product("chicken-heart", "Kycklinghjärta Fryst"),
            _cached_product("garlic", "Vitlök"),
            _cached_product("garlic-bread", "Baguetter Vitlök 2-pack"),
            _cached_product("garlic-salsa", "Salsa Vitlök Medium"),
            _cached_product("garlic-olive", "Snacksoliver Vitlök Fyllda"),
            _cached_product("rice", "Basmatiris"),
            _cached_product("pudding-rice", "Grötris"),
            _cached_product("cheese", "Hushållsost"),
            _cached_product("grilling-cheese", "Grillost"),
            _cached_product("cheese-sauce", "Ostsås"),
            _cached_product("cheese-snack", "Ostbågar"),
            _cached_product("garlic-tomato", "Tomater Krossade Vitlök"),
            _cached_product("garlic-sausage", "Bratwurst Kummin & vitlök"),
            _cached_product("garlic-cheese", "Cambozola Vitlök"),
            _cached_product("garlic-gnocchi", "Gnocchi Vitlök&mozzarella"),
            _cached_product("garlic-labneh", "Labneh Vitlök&mynta"),
            _cached_product("garlic-risotto", "Risotto Svamp & vitlök"),
            _cached_product("garlic-salami", "Vitlökssalami"),
            _cached_product("garlic-cream-cheese", "Färskost Vitlök"),
            _cached_product("garlic-mayonnaise", "Vitlöksmajonnäs"),
            _cached_product("garlic-oil", "Vitlöksolja"),
            _cached_product("chicken-baby", "Kyckling Couscous Från 8 månader"),
            _cached_product("chicken-couscous", "Couscous Kyckling & Grönsaker"),
            _cached_product("chicken-cup-noodles", "Ginger Chicken Cup Noodles"),
            _cached_product("chicken-instant-noodles", "Koppnudlar Kyckling"),
            _cached_product("chicken-bouillon", "Chicken Flavor Bouillon"),
            _cached_product("chicken-teriyaki", "Noodles Chicken Teriyaki"),
            _cached_product("chicken-salami", "Kycklingsalami"),
            _cached_product("chicken-hotdog", "Chicken hotdog"),
            _cached_product("chicken-bacon", "Chicken bacon"),
            _cached_product("chicken-gyros", "Kycklinggyros Fryst"),
            _cached_product("chicken-sticks", "Kycklingpinnar"),
            _cached_product("cheese-corn-cakes", "Jalapeno & Cheddar Majskakor"),
            _cached_product("cheese-maize-cakes", "Majskakor Ost"),
            _cached_product("cheese-rice-cakes", "Riskakor Ost"),
            _cached_product("cheese-creme-fraiche", "Parmesan Lätt Crème Fraiche"),
            _cached_product("rice-couscous", "Majs/ris Glutenfri Couscous"),
            _cached_product("oat-rice-first", "Havreris Svenskt"),
            _cached_product("oat-rice-last", "Svenskt Havreris"),
            _cached_product("barley-rice-first", "Kornris Svenskt"),
            _cached_product("barley-rice-last", "Svenskt Kornris"),
            _cached_product("whey-cheese-long", "Mesost Gudbrandsdalen 28%"),
            _cached_product("whey-cheese-short", "Mesost Norsk"),
        )
    }

    result = _candidate_semantics_assertions(cache)
    traps = result["trap_assertions"]

    assert result["source"] == "existing_product_search_cache"
    assert result["network_requests_added"] == 0
    assert result["unique_products_inspected"] == 44
    assert traps["generic_chicken_rejects_organ_meat"]["status"] == "PASS"
    assert traps["generic_chicken_rejects_organ_meat"]["rejected_names"] == ["Kycklinghjärta Fryst"]
    assert traps["explicit_chicken_heart_accepts_heart"]["status"] == "PASS"
    assert traps["explicit_chicken_heart_accepts_heart"]["accepted_names"] == [
        "Kycklinghjärta Fryst"
    ]
    assert traps["garlic_rejects_bread_salsa_and_olives"]["status"] == "PASS"
    assert traps["garlic_rejects_bread_salsa_and_olives"]["rejected_count"] == 3
    assert traps["rice_rejects_pudding_rice"]["status"] == "PASS"
    assert traps["cheese_rejects_grilling_sauce_and_snacks"]["status"] == "PASS"
    assert traps["garlic_rejects_other_primary_products"]["status"] == "PASS"
    assert traps["garlic_rejects_other_primary_products"]["rejected_count"] == 10
    assert traps["generic_chicken_rejects_prepared_primary_products"]["status"] == "PASS"
    assert traps["generic_chicken_rejects_prepared_primary_products"]["rejected_count"] == 11
    assert traps["cheese_rejects_snack_and_dairy_primary_products"]["status"] == "PASS"
    assert traps["cheese_rejects_snack_and_dairy_primary_products"]["rejected_count"] == 4
    assert traps["rice_rejects_couscous_primary_products"]["status"] == "PASS"
    assert traps["rice_rejects_couscous_primary_products"]["rejected_names"] == [
        "Majs/ris Glutenfri Couscous"
    ]
    assert traps["rice_rejects_oat_and_barley_rice"]["status"] == "PASS"
    assert traps["rice_rejects_oat_and_barley_rice"]["rejected_count"] == 4
    assert traps["cheese_rejects_whey_and_brown_cheese"]["status"] == "PASS"
    assert traps["cheese_rejects_whey_and_brown_cheese"]["rejected_count"] == 2
    assert result["canonical_candidates"]["generic_chicken"]["accepted_safe_names"] == [
        "Kycklinglårfilé"
    ]
    assert (
        "Kycklinghjärta Fryst"
        in result["canonical_candidates"]["generic_chicken"]["rejected_relevant_names"]
    )


def test_candidate_semantics_reports_missing_traps_as_not_observed() -> None:
    cache = {("kyckling", ("store-1",)): (_cached_product("chicken-thigh", "Kycklinglårfilé"),)}

    result = _candidate_semantics_assertions(cache)

    assert result["canonical_candidates"]["generic_chicken"]["status"] == "OBSERVED"
    assert result["canonical_candidates"]["rice"]["status"] == "NOT_OBSERVED"
    assert all(
        assertion["status"] == "NOT_OBSERVED" for assertion in result["trap_assertions"].values()
    )
