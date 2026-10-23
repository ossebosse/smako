"""Stable content identities; serialized private inputs never leave the owner.

The full request and effective state are deliberately bound. Qualification reads taste, slot
locks, reservations, pantry allocation, servings, purchased-product evidence,
membership, clock and settings through clean_recipe/basket/_check_nutrition.
Library content is separate so adding a recipe can reuse unchanged records.
Universe/fact replacement invalidates the entire context (including negatives).
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

VERSION = "smako-planner-context-v1"
SETTING_NAMES = (
    "complete_recipes_enabled", "price_provider", "meal_plan_strategy",
    "max_price_age_hours", "price_age_warning_hours", "price_universe_required",
    "price_universe_required_context_ids", "own_sources_only",
    "stable_candidate_search_enabled", "stable_candidate_base_count",
    "stable_candidate_search_limit", "allow_medium_semantic_matches",
    "allow_estimated_quantities", "allow_unknown_quantities", "allow_unknown_sale_model",
    "library_seed_pool_limit", "library_refinement_pool_limit", "library_substitution_pool_limit",
    "library_seed_variant_shortlist", "library_merge_generations",
    "library_substitution_screen_margin", "library_substitution_slot_limit", "library_search_policy",
)


def _json(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Unsupported context value: {type(value).__name__}")


def canonical_bytes(value):
    return json.dumps(value, default=_json, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode()


def content_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def settings_contract(settings):
    return {name: getattr(settings, name, None) for name in SETTING_NAMES}


def fact_source_contract():
    from grocery_data.app.services import axfood_detail_archive
    from grocery_data.app.services.axfood_detail_archive import VERSION as AXFOOD_VERSION

    root = os.getenv("AXFOOD_PRODUCT_DETAIL_ROOT")
    manifest = None
    if root:
        try:
            path = Path(root) / "manifest.json"
            manifest = (hashlib.sha256(path.read_bytes()).hexdigest()
                        if path.stat().st_size <= 16 * 1024 * 1024 else "oversized")
        except OSError:
            manifest = "unavailable"
    return {"axfood_parser": AXFOOD_VERSION, "axfood_manifest": manifest,
            "axfood_parser_sha256": hashlib.sha256(Path(axfood_detail_archive.__file__).read_bytes()).hexdigest()}


def planner_context(planner):
    from app.services.meal_library_content import manifest_entries
    from app.services.meal_prepared_artifacts import method_signature
    from app.services.recipe_week_variation import CLASSIFICATION_VERSION

    request = planner.request.model_dump(mode="json")
    # Revision is an optimistic-concurrency gate checked by the constructor and
    # PlanStore, not a pricing input. Read dependencies in _need_rows/_allocate
    # are exact available items and this plan's consumption/purchase ledger.
    # Unrelated plan writes must not invalidate an unchanged empty pantry view.
    if request.get("personal") is not None:
        request["personal"]["pantry_revision"] = 0
    state = {"available_items": planner.items,
             "plan_ledger": [entry for entry in planner.state.get("ledger", [])
                             if entry["plan_id"] == planner.plan_id],
             "legacy_purchase_lots": planner.state.get("legacy_purchase_lots", {}).get(planner.plan_id, [])}
    return content_digest({
        "version": VERSION, "method": method_signature(),
        "classification": CLASSIFICATION_VERSION,
        "revocations": manifest_entries().get("revocations", {}),
        "request": request, "settings": settings_contract(planner.settings),
        "prices": planner.prepared.universe.universe_id,
        "facts": planner.facts_version, "reference": planner.reference_version,
        "fact_sources": fact_source_contract(),
        "frozen_fact_manifests": getattr(planner.facts, "source_manifests", ()),
        "view": planner.view.cache_identity, "stores": planner.store_ids,
        # Qualification/search read time through request_view and Stockholm's
        # price date. Final response ages use the current clock and are NOT
        # cached. Binding microseconds would prevent equivalent request reuse.
        "pricing_date": planner.pricing_date,
        "memberships": planner.user.cache_identity, "state": state,
        "plan_id": planner.plan_id, "cooked_weights": planner.cooked_weights,
        "nutrition_search_limit": planner.nutrition_search_limit,
        "complete": planner.complete,
    })
