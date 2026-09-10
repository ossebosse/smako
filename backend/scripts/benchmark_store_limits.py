"""Compare optimized one- and two-store plans on one Primat snapshot.

Run this file from the repository root. The script deliberately creates one
``PrimatPriceProvider`` instance, freezes the first resolved store list and
retains the provider's product-search cache between both menu searches. That
keeps the comparison inside Primat's small free-tier request budget while the
two plans are costed against exactly the same fetched product rows.

Credentials are read only through ``Settings.from_env()``. They are never
accepted as command-line arguments, copied into the result or included in an
error message.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


_ALLOWED_BASKET_STATUSES = {"VERIFIED", "VERIFIED_WITH_ESTIMATES"}
_ALLOWED_SEMANTIC_CONFIDENCES = {"exact", "high"}

_CANDIDATE_TARGETS: dict[str, dict[str, object]] = {
    "generic_chicken": {
        "ingredient": "kyckling",
        "observation_markers": ("kyckling", "chicken"),
    },
    "explicit_chicken_heart": {
        "ingredient": "kycklinghjärta",
        "observation_markers": ("kycklinghjärta", "kyckling hjärta", "chicken heart"),
    },
    "garlic": {
        "ingredient": "vitlök",
        "observation_markers": ("vitlök", "garlic"),
    },
    "rice": {
        "ingredient": "ris",
        "observation_markers": ("ris", "rice"),
    },
    "cheese": {
        "ingredient": "ost",
        "observation_markers": (
            "ost",
            "cheese",
            "halloumi",
            "cheddar",
            "gouda",
            "mozzarella",
            "parmesan",
        ),
    },
}

_CANDIDATE_TRAPS: dict[str, dict[str, object]] = {
    "generic_chicken_rejects_organ_meat": {
        "target": "generic_chicken",
        "required_markers": ("kyckling", "chicken"),
        "trap_markers": (
            "hjärta",
            "hjarta",
            "heart",
            "lever",
            "liver",
            "mage",
            "gizzard",
            "fötter",
            "fotter",
            "feet",
            "skinn",
            "skin",
            "buljong",
            "broth",
        ),
        "expected": "rejected",
    },
    "explicit_chicken_heart_accepts_heart": {
        "target": "explicit_chicken_heart",
        "required_markers": ("kyckling", "chicken"),
        "trap_markers": ("hjärta", "hjarta", "heart"),
        "expected": "accepted",
    },
    "garlic_rejects_bread_salsa_and_olives": {
        "target": "garlic",
        "required_markers": ("vitlök", "garlic"),
        "trap_markers": (
            "baguette",
            "baguetter",
            "bröd",
            "brod",
            "bread",
            "salsa",
            "oliv",
            "olive",
        ),
        "expected": "rejected",
    },
    "rice_rejects_pudding_rice": {
        "target": "rice",
        "required_markers": (),
        "trap_markers": (
            "grötris",
            "grot ris",
            "risgryn",
            "ris gryn",
            "risgröt",
            "ris grot",
            "rice pudding",
            "pudding rice",
        ),
        "expected": "rejected",
    },
    "cheese_rejects_grilling_sauce_and_snacks": {
        "target": "cheese",
        "required_markers": (),
        "trap_markers": (
            "grillost",
            "grill ost",
            "halloumi",
            "ostsås",
            "ost sås",
            "cheese sauce",
            "ostbågar",
            "ostchips",
            "cheese snack",
        ),
        "expected": "rejected",
    },
    "garlic_rejects_other_primary_products": {
        "target": "garlic",
        "required_markers": ("vitlök", "garlic"),
        "trap_markers": (
            "krossade tomater",
            "tomater krossade",
            "tomatkross",
            "bratwurst",
            "cambozola",
            "gnocchi",
            "labneh",
            "risotto",
            "salami",
            "färskost",
            "farskost",
            "majonnäs",
            "majonnas",
            "mayonnaise",
            "vitlöksolja",
            "vitloksolja",
            "garlic oil",
        ),
        "expected": "rejected",
    },
    "generic_chicken_rejects_prepared_primary_products": {
        "target": "generic_chicken",
        "required_markers": ("kyckling", "chicken"),
        "trap_markers": (
            "barnmat",
            "baby food",
            "babyfood",
            "couscous",
            "cup noodles",
            "koppnudlar",
            "snabbnudlar",
            "noodles",
            "bouillon",
            "teriyaki",
            "salami",
            "hotdog",
            "hot dog",
            "bacon",
            "gyros",
            "pinnar",
            "sticks",
            "fingers",
        ),
        "expected": "rejected",
    },
    "cheese_rejects_snack_and_dairy_primary_products": {
        "target": "cheese",
        "required_markers": ("ost", "cheese", "cheddar", "parmesan"),
        "trap_markers": ("majskakor", "riskakor", "crème fraiche", "creme fraiche"),
        "expected": "rejected",
    },
    "rice_rejects_couscous_primary_products": {
        "target": "rice",
        "required_markers": ("ris", "rice"),
        "trap_markers": ("couscous",),
        "expected": "rejected",
    },
    "rice_rejects_oat_and_barley_rice": {
        "target": "rice",
        "required_markers": ("ris", "rice"),
        "trap_markers": ("havreris", "havre ris", "oat rice", "kornris", "korn ris", "barley rice"),
        "expected": "rejected",
    },
    "cheese_rejects_whey_and_brown_cheese": {
        "target": "cheese",
        "required_markers": ("ost", "cheese"),
        "trap_markers": ("mesost", "brunost", "whey cheese", "brown cheese"),
        "expected": "rejected",
    },
}


class LiveVerificationAssertionError(RuntimeError):
    """A sanitized correctness failure which is safe to include in CLI output."""

    def __init__(self, failed: list[str]) -> None:
        self.failed = tuple(sorted(failed))
        super().__init__(", ".join(self.failed))


def _items(data: dict[str, Any]) -> list[dict[str, Any]]:
    basket = data.get("optimized_basket") or {}
    return [item for store in basket.get("stores", []) for item in store.get("items", [])]


def _assertion(
    *,
    checked: int,
    passed: bool,
) -> dict[str, int | str]:
    return {
        "status": "NOT_APPLICABLE" if checked == 0 else ("PASS" if passed else "FAIL"),
        "items_checked": checked,
    }


def _safe_product_name(product: Any) -> str:
    """Return a bounded public product name, never raw catalogue metadata."""

    value = getattr(product, "name", getattr(product, "product_name", ""))
    return " ".join(str(value).split())[:160]


def _bounded_names(products: Iterable[Any], *, limit: int = 30) -> tuple[list[str], int]:
    names = sorted(
        {_safe_product_name(product) for product in products if _safe_product_name(product)}
    )
    return names[:limit], max(0, len(names) - limit)


def _has_marker(name_text: str, markers: Iterable[object]) -> bool:
    from app.services.ingredient_normalizer import _search_text

    return any(_search_text(str(marker)) in name_text for marker in markers)


def _cached_products(
    cache: Mapping[object, Iterable[Any]],
) -> list[Any]:
    """Flatten the existing provider cache without triggering catalogue I/O."""

    unique: dict[tuple[str, str], Any] = {}
    for cached_rows in cache.values():
        for product in cached_rows:
            key = (
                str(getattr(product, "store_id", "")),
                str(getattr(product, "product_id", "")),
            )
            unique[key] = product
    return sorted(
        unique.values(),
        key=lambda product: (
            _safe_product_name(product).casefold(),
            str(getattr(product, "store_id", "")),
            str(getattr(product, "product_id", "")),
        ),
    )


def _candidate_semantics_assertions(
    cache: Mapping[object, Iterable[Any]],
) -> dict[str, Any]:
    """Audit semantic traps across product rows already fetched for the snapshot.

    This function receives only the in-memory cache and has no provider
    reference, so it cannot make a Primat request. Missing trap examples are
    reported as ``NOT_OBSERVED`` rather than being mistaken for proof.
    """

    from app.models import NormalizedIngredient
    from app.services.ingredient_normalizer import _search_text
    from app.services.product_matcher import ProductMatcher

    products = _cached_products(cache)
    matcher = ProductMatcher()
    evaluations: dict[str, dict[tuple[str, str], Any]] = {}
    product_by_key = {
        (
            str(getattr(product, "store_id", "")),
            str(getattr(product, "product_id", "")),
        ): product
        for product in products
    }
    canonical_candidates: dict[str, dict[str, Any]] = {}

    for target_name, spec in _CANDIDATE_TARGETS.items():
        ingredient = NormalizedIngredient(
            canonical_name=str(spec["ingredient"]),
            required_quantity=100,
            unit="g",
        )
        target_evaluations = {
            key: matcher.evaluate_semantics(ingredient, product)
            for key, product in product_by_key.items()
        }
        evaluations[target_name] = target_evaluations
        markers = tuple(spec["observation_markers"])
        observed = [
            product
            for key, product in product_by_key.items()
            if _has_marker(_search_text(_safe_product_name(product)), markers)
            or (
                target_evaluations[key].canonical_food is not None
                and target_evaluations[key].compatible
            )
        ]
        accepted = [
            product
            for product in observed
            if (
                target_evaluations[
                    (
                        str(getattr(product, "store_id", "")),
                        str(getattr(product, "product_id", "")),
                    )
                ].compatible
                and target_evaluations[
                    (
                        str(getattr(product, "store_id", "")),
                        str(getattr(product, "product_id", "")),
                    )
                ].confidence.value
                in _ALLOWED_SEMANTIC_CONFIDENCES
            )
        ]
        rejected = [product for product in observed if product not in accepted]
        observed_names, observed_omitted = _bounded_names(observed)
        accepted_names, accepted_omitted = _bounded_names(accepted)
        rejected_names, rejected_omitted = _bounded_names(rejected)
        canonical_candidates[target_name] = {
            "ingredient": spec["ingredient"],
            "status": "OBSERVED" if observed else "NOT_OBSERVED",
            "relevant_products_observed": len(observed),
            "relevant_product_names": observed_names,
            "relevant_names_omitted": observed_omitted,
            "accepted_safe_count": len(accepted),
            "accepted_safe_names": accepted_names,
            "accepted_names_omitted": accepted_omitted,
            "rejected_relevant_count": len(rejected),
            "rejected_relevant_names": rejected_names,
            "rejected_names_omitted": rejected_omitted,
        }

    trap_assertions: dict[str, dict[str, Any]] = {}
    for assertion_name, spec in _CANDIDATE_TRAPS.items():
        target_name = str(spec["target"])
        required_markers = tuple(spec["required_markers"])
        trap_markers = tuple(spec["trap_markers"])
        observed = []
        for key, product in product_by_key.items():
            name_text = _search_text(_safe_product_name(product))
            if required_markers and not _has_marker(name_text, required_markers):
                continue
            if _has_marker(name_text, trap_markers):
                observed.append((key, product))

        accepted = [
            product
            for key, product in observed
            if evaluations[target_name][key].compatible
            and evaluations[target_name][key].confidence.value in _ALLOWED_SEMANTIC_CONFIDENCES
        ]
        explicitly_rejected = [
            product
            for key, product in observed
            if not evaluations[target_name][key].compatible
            and evaluations[target_name][key].confidence.value == "rejected"
        ]
        expected = str(spec["expected"])
        passed = (
            len(accepted) == len(observed)
            if expected == "accepted"
            else len(explicitly_rejected) == len(observed)
        )
        observed_names, observed_omitted = _bounded_names(product for _, product in observed)
        accepted_names, accepted_omitted = _bounded_names(accepted)
        rejected_names, rejected_omitted = _bounded_names(explicitly_rejected)
        trap_assertions[assertion_name] = {
            "status": "NOT_OBSERVED" if not observed else ("PASS" if passed else "FAIL"),
            "expected": expected,
            "trap_products_observed": len(observed),
            "trap_product_names": observed_names,
            "trap_names_omitted": observed_omitted,
            "accepted_count": len(accepted),
            "accepted_names": accepted_names,
            "accepted_names_omitted": accepted_omitted,
            "rejected_count": len(explicitly_rejected),
            "rejected_names": rejected_names,
            "rejected_names_omitted": rejected_omitted,
        }

    failed = [name for name, assertion in trap_assertions.items() if assertion["status"] == "FAIL"]
    if failed:
        raise LiveVerificationAssertionError(failed)
    return {
        "source": "existing_product_search_cache",
        "network_requests_added": 0,
        "cache_entries_inspected": len(cache),
        "unique_products_inspected": len(products),
        "canonical_candidates": canonical_candidates,
        "trap_assertions": trap_assertions,
    }


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _verification_details(data: dict[str, Any]) -> dict[str, Any]:
    """Return only sanitized product semantics and purchase facts."""

    basket = data.get("optimized_basket") or {}
    audit = (data.get("quality") or {}).get("basket_audit") or {}
    products: list[dict[str, Any]] = []
    for store in basket.get("stores", []):
        for item in store.get("items", []):
            products.append(
                {
                    "ingredient": item.get("ingredient"),
                    "product": item.get("product_name"),
                    "store": store.get("store_name"),
                    "semantic": {
                        "canonical_food": item.get("canonical_food"),
                        "food_family": item.get("food_family"),
                        "role": item.get("product_role"),
                        "form": item.get("product_form"),
                        "confidence": item.get("semantic_confidence"),
                    },
                    "purchase": {
                        "sale_model": item.get("sale_model"),
                        "sale_price": item.get("sale_price"),
                        "sale_unit": item.get("sale_unit"),
                        "comparison_price": item.get("comparison_price"),
                        "comparison_unit": item.get("comparison_unit"),
                        "required_quantity": item.get("required_quantity"),
                        "required_unit": item.get("unit"),
                        "package_quantity": item.get("package_quantity"),
                        "package_unit": item.get("package_unit"),
                        "packages_needed": item.get("packages_needed"),
                        "purchased_quantity": item.get("purchased_quantity"),
                        "purchased_unit": item.get("purchased_unit"),
                        "purchased_usable_quantity": item.get("purchased_usable_quantity"),
                        "quantity_confidence": item.get("quantity_confidence"),
                        "cost": item.get("total_price"),
                        "warning": item.get("purchase_warning"),
                    },
                    "verification_status": item.get("verification_status"),
                }
            )
    return {
        "status": basket.get("verification_status"),
        "warnings": basket.get("verification_warnings", []),
        "audit_status": audit.get("status"),
        "audit_verification_status": audit.get("verification_status"),
        "audit_deficits": len(audit.get("deficits", [])),
        "products": products,
    }


def _live_assertions(data: dict[str, Any]) -> dict[str, dict[str, int | str]]:
    """Validate the live result without exposing source payloads or credentials."""

    basket = data.get("optimized_basket") or {}
    audit = (data.get("quality") or {}).get("basket_audit") or {}
    items = _items(data)
    selected = [
        product for row in audit.get("items", []) for product in row.get("selected_products", [])
    ]
    checks: dict[str, dict[str, int | str]] = {}
    checks["basket_is_verified"] = _assertion(
        checked=1,
        passed=basket.get("verification_status") in _ALLOWED_BASKET_STATUSES,
    )
    checks["audit_passes_and_reconciles"] = _assertion(
        checked=max(1, len(selected)),
        passed=(
            audit.get("status") == "PASS"
            and audit.get("verification_status") in _ALLOWED_BASKET_STATUSES
            and not audit.get("deficits")
            and bool(selected)
            and all(
                product.get("quantity_reconciled") is True
                and product.get("cost_reconciled") is True
                for product in selected
            )
        ),
    )
    checks["all_products_are_semantically_safe"] = _assertion(
        checked=len(items),
        passed=bool(items)
        and all(item.get("semantic_confidence") in _ALLOWED_SEMANTIC_CONFIDENCES for item in items),
    )
    checks["all_purchase_models_are_resolved"] = _assertion(
        checked=len(items),
        passed=bool(items)
        and all(
            item.get("sale_model") != "unknown" and item.get("quantity_confidence") != "unknown"
            for item in items
        ),
    )

    trap_specs = {
        "generic_chicken_is_not_organ_meat": (
            "kyckling",
            {"heart", "liver", "gizzard", "feet", "skin_only", "broth", "processed_ready_meal"},
            {"organ", "liquid", "prepared"},
            (
                "kycklinghjärta",
                "kycklinglever",
                "kycklingmage",
                "kycklingfötter",
                "kycklingskinn",
                "kycklingbuljong",
            ),
        ),
        "garlic_is_not_garlic_bread": (
            "vitlök",
            {"bread", "sauce", "seasoning", "spread", "processed_ready_meal"},
            {"prepared", "processed"},
            ("baguette", "baguetter", "vitlöksbröd"),
        ),
        "garlic_is_not_processed_condiment": (
            "vitlök",
            {"condiment", "sauce"},
            {"condiment", "sauce"},
            ("salsa", "chutney", "relish", "ketchup", "senap"),
        ),
        "rice_is_not_pudding_rice": (
            "ris",
            {"pudding_rice", "rice_noodle", "rice_flour", "rice_drink", "snack"},
            {"prepared", "processed"},
            ("grötris", "risgryn", "risgröt"),
        ),
        "cheese_is_not_grilling_or_processed_cheese": (
            "ost",
            {
                "grilling_cheese",
                "cheese_sauce",
                "cheese_flavoured_snack",
                "processed_ready_meal",
            },
            {"grilling", "processed", "prepared"},
            ("grillost", "halloumi", "ostsås", "ostbågar"),
        ),
        "generic_fish_is_not_canned_tuna": (
            "fisk",
            {"canned_tuna", "preserved_fish", "preserved_in_oil"},
            {"canned", "preserved_in_oil"},
            ("tonfisk i", "tuna in", "solrosolja", "olivolja"),
        ),
        "raw_broccoli_is_not_ambiguous_mixture": (
            "broccoli",
            {"ambiguous_mixture", "vegetable_mixture"},
            {"mixture"},
            ("broccoli mix", "broccoliblandning"),
        ),
        "raw_carrot_is_not_fermented_or_pickled_mixture": (
            "morot",
            {"fermented_vegetable_mixture", "pickled_vegetable_mixture"},
            {"fermented", "pickled"},
            ("surkål", "surkal", "sauerkraut", "inlagd", "picklad"),
        ),
    }
    for label, (ingredient, excluded_roles, excluded_forms, excluded_names) in trap_specs.items():
        relevant = [item for item in items if item.get("ingredient") == ingredient]
        checks[label] = _assertion(
            checked=len(relevant),
            passed=all(
                item.get("product_role") not in excluded_roles
                and item.get("product_form") not in excluded_forms
                and not any(
                    marker in str(item.get("product_name", "")).casefold()
                    for marker in excluded_names
                )
                for item in relevant
            ),
        )

    garlic_items = [item for item in items if item.get("ingredient") == "vitlök"]
    checks["raw_garlic_has_safe_role_form_and_no_olive"] = _assertion(
        checked=len(garlic_items),
        passed=all(
            item.get("product_role") in {"bulb", "clove"}
            and item.get("product_form") == "fresh"
            and "oliv" not in str(item.get("product_name", "")).casefold()
            for item in garlic_items
        ),
    )

    weight_items = [item for item in items if item.get("sale_model") == "sold_by_weight"]
    checks["kg_rate_is_not_a_one_kg_package"] = _assertion(
        checked=len(weight_items),
        passed=all(
            item.get("package_quantity") is None and item.get("package_unit") is None
            for item in weight_items
        ),
    )
    comparison_weight_items = [
        item
        for item in weight_items
        if item.get("comparison_price") is not None and item.get("comparison_unit") == "kg"
    ]
    checks["comparison_price_is_not_package_size"] = _assertion(
        checked=len(comparison_weight_items),
        passed=all(item.get("package_quantity") is None for item in comparison_weight_items),
    )
    prorated_weight_items = [
        item
        for item in weight_items
        if item.get("unit") == "g"
        and item.get("sale_unit") == "kg"
        and item.get("sale_price") is not None
        and item.get("required_quantity") is not None
        and item.get("total_price") is not None
    ]
    checks["sold_by_weight_cost_is_prorated"] = _assertion(
        checked=len(prorated_weight_items),
        passed=all(
            _money(
                Decimal(str(item["required_quantity"]))
                * Decimal(str(item["sale_price"]))
                / Decimal(1000)
            )
            == Decimal(str(item["total_price"])).quantize(Decimal("0.01"))
            for item in prorated_weight_items
        ),
    )
    fixed_items = [item for item in items if item.get("sale_model") == "fixed_package"]
    checks["fixed_packages_have_explicit_quantity"] = _assertion(
        checked=len(fixed_items),
        passed=all(
            item.get("package_quantity") is not None and item.get("package_unit") is not None
            for item in fixed_items
        ),
    )

    failed = [name for name, result in checks.items() if result["status"] == "FAIL"]
    if failed:
        raise LiveVerificationAssertionError(failed)
    return checks


def _candidate_sample_fingerprint(data: dict[str, Any]) -> str:
    debug = data.get("debug_info") or {}
    candidate_evidence = {
        "candidate_sample": debug.get("candidate_sample", []),
        "candidate_batches": debug.get("candidate_batches", {}),
        "candidate_family_coverage": {
            family: {
                "generated": counts.get("generated"),
                "valid": counts.get("valid"),
            }
            for family, counts in (debug.get("candidate_family_coverage", {}) or {}).items()
        },
    }
    encoded = json.dumps(
        candidate_evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_assertions(
    passes: list[dict[str, Any]],
    *,
    live_store_fetches: int,
) -> dict[str, dict[str, int | str]]:
    """Prove that pass two reused pass one's stores, products and candidates."""

    checks = {
        "one_underlying_store_fetch": _assertion(
            checked=1,
            passed=live_store_fetches == 1,
        ),
        "second_pass_added_no_product_cache_entries": _assertion(
            checked=1,
            passed=(len(passes) == 2 and passes[1]["product_cache_entries_added"] == 0),
        ),
        "second_pass_made_no_network_requests": _assertion(
            checked=1,
            passed=(len(passes) == 2 and passes[1]["network_requests_added"] == 0),
        ),
        "candidate_sample_matches": _assertion(
            checked=1,
            passed=(
                len(passes) == 2
                and passes[0]["candidate_sample_fingerprint"]
                == passes[1]["candidate_sample_fingerprint"]
            ),
        ),
    }
    failed = [name for name, result in checks.items() if result["status"] == "FAIL"]
    if failed:
        raise LiveVerificationAssertionError(failed)
    return checks


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Jämför optimized max_stores=1 och 2 på samma Primat-snapshot.")
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--candidate-count", type=int, default=80)
    parser.add_argument("--beam-width", type=int, default=30)
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    # Imports happen after the local backend path is installed. Importing
    # config loads .env, but this benchmark never mutates os.environ.
    from app.config import Settings
    from app.models import DiversityMode, PlanRequest, Store
    from app.providers.primat import PrimatPriceProvider
    from app.services.meal_plan_optimizer import MealPlanService
    from scripts.benchmark_plan import _summary

    class SnapshotPrimatPriceProvider(PrimatPriceProvider):
        """One live provider with a stable store list and observable call counts."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self._store_snapshot: tuple[Store, ...] | None = None
            self._snapshot_postal_code: str | None = None
            self.request_counts: Counter[str] = Counter()
            self.live_store_fetches = 0

        async def _request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            # Only fixed endpoint paths are retained; request headers,
            # parameters and credentials can therefore never enter output.
            self.request_counts[path] += 1
            return await super()._request(method, path, params=params, json=json)

        async def find_stores(self, postal_code: str) -> list[Store]:
            digits = "".join(character for character in postal_code if character.isdigit())
            if self._store_snapshot is None:
                self.live_store_fetches += 1
                stores = await super().find_stores(digits)
                self._store_snapshot = tuple(stores)
                self._snapshot_postal_code = digits
            elif digits != self._snapshot_postal_code:
                raise ValueError("A snapshot benchmark can only use one postal code")
            return list(self._store_snapshot)

        @property
        def product_search_cache_entries(self) -> int:
            return len(self._product_search_cache)

        @property
        def product_search_cache_snapshot(
            self,
        ) -> dict[tuple[str, tuple[str, ...]], tuple[Any, ...]]:
            """Expose immutable cached rows for local, network-free assertions."""

            return {key: tuple(rows) for key, rows in self._product_search_cache.items()}

    loaded = Settings.from_env()
    settings = replace(
        loaded,
        price_provider="primat",
        meal_plan_strategy="optimized",
        # Keep this comparison deterministic and avoid any extra external API
        # calls. The production OpenAI integration remains untouched.
        openai_api_key=None,
        allow_mock_fallback=False,
    )
    if not settings.primat_api_key:
        raise RuntimeError("PRIMAT_API_KEY is required")

    provider = SnapshotPrimatPriceProvider(
        api_key=settings.primat_api_key,
        base_url=settings.primat_base_url,
        use_member_prices=False,
    )
    service = MealPlanService(settings)
    results: dict[str, Any] = {}
    snapshot_passes: list[dict[str, Any]] = []
    candidate_semantics: dict[str, Any] = {}
    try:
        for max_stores in (1, 2):
            cache_entries_before = provider.product_search_cache_entries
            requests_before = provider.request_counts.copy()
            request = PlanRequest(
                postal_code=args.postal_code,
                recipes=args.recipes,
                servings=args.servings,
                max_stores=max_stores,
                use_member_prices=False,
                optimization_iterations=0,
                strategy="optimized",
                candidate_recipe_count=args.candidate_count,
                beam_width=args.beam_width,
                diversity_mode=DiversityMode.BALANCED,
                max_same_carbohydrate_meals=3,
                debug=True,
            )
            started = perf_counter()
            response = await service._build_optimized_with_provider(request, provider)
            wall_seconds = perf_counter() - started
            if response.data_source != "primat":
                raise RuntimeError("The live benchmark did not return Primat data")
            data = response.model_dump(mode="json")
            assertions = _live_assertions(data)
            summary = _summary(data, wall_seconds)
            # The row-level purchase evidence below supersedes the older,
            # package-centric basket/debug summaries. Keeping only store
            # subtotals here makes the one-shot JSON small enough to inspect
            # without losing any correctness evidence.
            basket_summary = summary.get("basket") or {}
            basket_summary["stores"] = [
                {
                    "store": store.get("store"),
                    "subtotal": store.get("subtotal"),
                }
                for store in basket_summary.get("stores", [])
            ]
            summary.pop("surplus", None)
            summary.pop("debug", None)
            summary["verification"] = _verification_details(data)
            summary["assertions"] = assertions
            results[f"max_stores_{max_stores}"] = summary

            requests_after = provider.request_counts.copy()
            request_delta = requests_after - requests_before
            snapshot_passes.append(
                {
                    "max_stores": max_stores,
                    "product_cache_entries_before": cache_entries_before,
                    "product_cache_entries_after": (provider.product_search_cache_entries),
                    "product_cache_entries_added": (
                        provider.product_search_cache_entries - cache_entries_before
                    ),
                    "network_requests_added": sum(request_delta.values()),
                    "network_requests_added_by_endpoint": dict(sorted(request_delta.items())),
                    "candidate_sample_fingerprint": (_candidate_sample_fingerprint(data)),
                }
            )
        candidate_request_count_before = sum(provider.request_counts.values())
        candidate_semantics = _candidate_semantics_assertions(
            provider.product_search_cache_snapshot
        )
        candidate_request_count_after = sum(provider.request_counts.values())
        candidate_semantics["network_requests_added"] = (
            candidate_request_count_after - candidate_request_count_before
        )
        if candidate_semantics["network_requests_added"] != 0:
            raise LiveVerificationAssertionError(["candidate_semantics_made_network_requests"])
    finally:
        await provider.aclose()

    snapshot_assertions = _snapshot_assertions(
        snapshot_passes,
        live_store_fetches=provider.live_store_fetches,
    )

    one_total = Decimal(str(results["max_stores_1"]["basket"]["total"]))
    two_total = Decimal(str(results["max_stores_2"]["basket"]["total"]))
    return {
        "benchmark": {
            "postal_code": PlanRequest.normalize_postal_code(args.postal_code),
            "recipes": args.recipes,
            "servings": args.servings,
            "candidate_count": args.candidate_count,
            "beam_width": args.beam_width,
            "diversity_mode": "balanced",
            "max_same_carbohydrate_meals": 3,
            "member_prices": False,
            "openai_enabled": False,
            "mock_fallback": False,
        },
        "snapshot": {
            "shared_primat_provider": True,
            "frozen_store_list": True,
            "underlying_store_fetches": provider.live_store_fetches,
            "product_search_cache_entries": provider.product_search_cache_entries,
            "network_requests_by_endpoint": dict(sorted(provider.request_counts.items())),
            "network_requests_total": sum(provider.request_counts.values()),
            "passes": snapshot_passes,
            "assertions": snapshot_assertions,
            "candidate_semantics": candidate_semantics,
        },
        "results": results,
        "comparison": {
            "max_two_stores_savings_vs_one_store": float(
                max(Decimal(0), (one_total - two_total).quantize(Decimal("0.01")))
            )
        },
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    started = perf_counter()
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - never emit credential-bearing details
        error_type = type(exc).__name__
        if error_type == "PriceProviderRateLimitError":
            message = (
                "Primat-jämförelsen stoppades av Primats anrops- eller radbudget. "
                "Vänta tills budgeten återställts och försök igen."
            )
        elif error_type == "PriceProviderAuthenticationError":
            message = "Primat avvisade den konfigurerade servernyckeln."
        elif isinstance(exc, LiveVerificationAssertionError):
            message = "Live-korrekthetskontrollen misslyckades: " + ", ".join(exc.failed)
        else:
            message = (
                f"Primat-jämförelsen misslyckades ({error_type}). Kontrollera .env och försök igen."
            )
        print(
            json.dumps(
                {
                    "error": message,
                    "runtime_seconds": round(perf_counter() - started, 4),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    result["total_wall_seconds"] = round(perf_counter() - started, 4)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
