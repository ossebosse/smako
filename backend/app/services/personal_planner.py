"""Composition of the existing generator, search and package price engine.

Personal data stays in this request and the owned PlanStore, never shared caches.
All relevant candidates and the final basket pass the same hard constraints.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from itertools import combinations
from zoneinfo import ZoneInfo

from app.errors import IncompleteBasketError
from app.models import (
    DiversityMode,
    NormalizedIngredient,
    OptimizedBasket,
    OptimizedStoreGroup,
    PlanPriceData,
    PlanResponse,
    ProductCandidate,
)
from app.models.personal import MealSlot, PersonalResult, TasteProfile
from app.models.recipe import Recipe
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import money
from app.services.basket_optimizer import BasketOptimizer, BasketVerificationPolicy
from app.services.diet_policy import recipe_respects_diet
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.inter_plan_distance import compare_plans, required_changes
from app.services.meal_plan_optimizer import MealPlanService, _consumer_price_context_coverage
from app.services.personal_nutrition import calculation_basis, requested_nutrients
from app.services.personal_policy import (
    PolicyConflict,
    check_product,
    distribution_ok,
    interpretation,
    is_nonfood,
    merged_profile,
    preference_score,
    properties_match,
    protein_category,
)
from app.services.personal_store import available_items, consumed_demands, demand_key
from app.services.product_search import ProductSearchRequest
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_candidate_validator import recipe_id
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext

POLICY_VERSION = "personal-policy-v2-7"


# Exact recipe value, including preparation and unrounded ingredient quantities.
# Recipe's nested lists are mutable, so object ID/name alone is not a safe key.
def _recipe_value(recipe):
    if recipe is None:
        return None
    return (recipe.name, recipe.servings, tuple(recipe.ingredients), tuple(recipe.instructions))


def personal_policy_request(request, dinner_count):
    result = request.model_copy(update={"recipes": dinner_count})
    # Personal forms use the named preset. Serialized absent optional overrides
    # become null on reload; null must not silently disable that preset on edits.
    # Explicit numeric overrides survive. The legacy non-personal API is untouched.
    for key in (
        "max_same_cooking_method_meals",
        "max_same_dish_form_meals",
        "max_pairwise_culinary_similarity",
    ):
        if getattr(result, key) is None:
            result.model_fields_set.discard(key)
    return result


class PersonalPlanner:
    def __init__(
        self,
        request,
        settings,
        prepared,
        state,
        *,
        plan_id=None,
        facts=None,
        cooked_weights=None,
        now=None,
    ):
        self.request, self.settings, self.prepared, self.state = request, settings, prepared, state
        if request.diet_preference in {"vegetarian", "vegan"}:
            raise PolicyConflict(
                "Personlig planering har kostval per måltidstyp. Det äldre globala kostkravet kan inte ignoreras: ange det i måltidsvalen och ta bort det globala fältet innan du bekräftar."
            )
        self.spec = request.personal.model_copy(deep=True)
        self.spec.profile = merged_profile(
            self.spec.profile, TasteProfile(exclusions=request.avoid_ingredients)
        )
        self.plan_id = plan_id
        from app.services.personal_source_facts import load_retained_facts

        needs_facts = (
            self.spec.organic_percent
            or self.spec.organic_animals
            or self.spec.profile.allergies
            or self.spec.profile.exclusions
            or any(
                m.count
                and (
                    m.organic_animals
                    or m.limits.active
                    or m.profile.allergies
                    or m.profile.exclusions
                )
                for m in self.spec.meals
            )
        )
        self.facts = (
            load_retained_facts(prepared) if facts is None and needs_facts else facts
        ) or {}
        from app.services.personal_source_facts import facts_version

        self.facts_version = getattr(self.facts, "version", None) or facts_version(self.facts)
        self.reference_version = None
        if self.spec.allow_nutrition_estimates:
            from app.services.nutrition_reference import reference_data

            self.reference_version = reference_data()["content_version"]
        self.cooked_weights = cooked_weights or {}
        self.now = now or datetime.now(UTC)
        self.pricing_date = self.now.astimezone(ZoneInfo("Europe/Stockholm")).date()
        self.service = MealPlanService(settings)
        self.optimizer = BasketOptimizer(
            verification_policy=BasketVerificationPolicy.strict_live(
                allow_estimated_quantities=False, allow_medium_semantic=False
            )
        )
        self.auditor = BasketAuditor(pantry_items=frozenset())
        self.user = UserPricingContext.from_chain_flags(
            request.memberships
            or {
                k: request.use_member_prices
                for k in ("ica", "coop", "willys", "hemkop", "citygross", "lidl")
            }
        )
        self.view = prepared.request_view(
            now=self.now, stale_age_hours=settings.max_price_age_hours
        )
        self.store_ids = {s.store_id for s in self.view.stores}
        self.index = prepared.product_search_index
        self.product_keys = {i: k for k, positions in self.index.groups.items() for i in positions}
        self.by_identity = {
            (p.store_id, p.product_id): i for i, p in enumerate(prepared.universe.products)
        }
        self.items = available_items(state, plan_id=plan_id)
        self.meals = {m.meal_type: m for m in self.spec.meals}
        self.lookup_cache = {}
        # Only this planner owns these immutable-by-convention facts and this
        # request's estimate policy. Nothing survives into another request or
        # account. Bound the cache even for unusually large edit inputs.
        self.nutrition_cache = {}
        self.slot_nutrition_cache = {}
        self.queries = {}
        from app.services.planning_diagnostics import PlanningDiagnostics

        self.diagnostics = PlanningDiagnostics()
        if self.spec.pantry_revision != state["revision"]:
            raise PolicyConflict(
                "Skafferiet har ändrats. Läs om och beräkna igen.", code="REVISION_CONFLICT"
            )

    def source_facts(self, product):
        facts = self.facts.get((product.store_id, product.product_id))
        provenance = product.source_provenance
        if (
            facts
            and facts.source
            and facts.source_product_id == product.product_id
            and (provenance and facts.source_snapshot_id == provenance.source_snapshot_id)
        ):
            return facts
        return None

    def nutrition_evidence(self, product, name, unit, requested, recipe):
        key = (
            product.store_id,
            product.product_id,
            name,
            unit,
            frozenset(requested),
            _recipe_value(recipe),
            self.spec.allow_nutrition_estimates,
        )
        if key not in self.nutrition_cache:
            result = self._nutrition_evidence(product, name, unit, requested, recipe)
            if len(self.nutrition_cache) >= 16384:
                self.nutrition_cache.clear()
            self.nutrition_cache[key] = result
        return self.nutrition_cache[key]

    def _nutrition_evidence(self, product, name, unit, requested, recipe):
        fact = self.source_facts(product)
        qualified = bool(
            fact
            and fact.nutrition_unit == unit
            and fact.nutrition_basis
            and fact.nutrition_preparation == "as_sold"
            and requested <= fact.nutrition.keys()
            and all(math.isfinite(fact.nutrition[k]) and fact.nutrition[k] >= 0 for k in requested)
        )
        if not self.spec.allow_nutrition_estimates:
            return fact if qualified else None
        from app.services.nutrition_reference import product_reference, reference_evidence
        from app.services.personal_nutrition import (
            is_couscous_preparation,
            is_reference_preparation,
            reference_method,
        )

        cooked = bool(recipe and is_reference_preparation(recipe))
        assembly = bool(recipe and is_couscous_preparation(recipe))
        if cooked and "strimlad" in product.name.casefold():
            from app.services.personal_nutrition import reference_instructions

            if recipe.instructions == reference_instructions("plate"):
                return None  # The existing plate explicitly serves a whole fillet.
        from app.services.reviewed_warm_meals import evidence as warm_evidence
        from app.services.reviewed_warm_meals import preparation

        warm = bool(preparation(recipe))
        if (
            warm
            and preparation(recipe) == "lentil_pasta_cheese"
            and canonicalize_ingredient_name(name) == "ost"
        ):
            import re

            from app.services.product_semantics import evaluate_product_semantics

            semantic = evaluate_product_semantics("ost", product)
            if (
                qualified
                and semantic.compatible
                and semantic.product_role
                in {"standard_cheese", "hard_cheese", "cheddar", "gouda", "parmesan"}
                and re.search(
                    r"hårdost|hushållsost|cheddar|gouda|präst|herrgård|grevé|parmesan|grana",
                    product.name.casefold(),
                )
            ):
                return fact  # Cold grated topping: declaration needs no cooking transform.
            return None
        if qualified and not cooked and not assembly and not warm:
            return fact
        if unit != "g" or (
            fact
            and (
                fact.conflicts
                or (
                    fact.nutrition
                    and (fact.nutrition_unit != unit or fact.nutrition_preparation != "as_sold")
                )
            )
        ):
            return None
        identity = product_reference(product, name, fact)
        if identity is None:
            return None
        if (cooked or assembly or warm) and fact and fact.nutrition and not qualified:
            return None  # Do not overwrite an incomplete declaration with easier generic values.
        if warm:
            return warm_evidence(identity, recipe, fact if qualified else None)
        if assembly:
            from app.services.nutrition_reference import assembly_evidence

            return assembly_evidence(identity, fact if qualified else None)
        return reference_evidence(
            identity,
            cooked=cooked,
            declaration=fact if qualified else None,
            method=reference_method(recipe, name) if recipe else "boil",
        )

    def resolve(
        self,
        name,
        quantity,
        unit,
        *,
        product_key=None,
        properties=(),
        profile=None,
        organic_animals=False,
        food=True,
    ):
        cache_key = (
            name,
            unit,
            product_key,
            tuple(properties),
            profile.model_dump_json(),
            organic_animals,
            food,
        )
        if cache_key in self.lookup_cache:
            return self.lookup_cache[cache_key]
        canonical = canonicalize_ingredient_name(name)
        requirement = NormalizedIngredient(
            canonical_name=canonical, required_quantity=quantity, unit=unit
        )
        if product_key:
            positions = self.index.groups.get(product_key, ())
        else:
            positions = set()
            # Reuse the semantic index first, and the existing product search for
            # goods outside the dinner taxonomy (including liver pâté/napkins).
            for candidate in self.view.economic_pool.candidates_by_name.get(canonical, ()):
                position = self.by_identity.get((candidate.store_id, candidate.product_id))
                if position is not None:
                    positions.add(position)
            if self.facts:
                # Reuse the wider frozen semantic index before any cheap-pool
                # pruning. Search text alone misses e.g. compound bread names.
                for candidate in self.view.economic_pool.matched_candidates_by_name.get(
                    canonical, ()
                ):
                    position = self.by_identity.get((candidate.store_id, candidate.product_id))
                    if position is not None:
                        positions.add(position)
                for entry in self.prepared.universe.indexes.canonical:
                    if entry.key == canonical:
                        positions.update(entry.product_indexes)
            if not positions or properties or self.facts:
                key = name
                if key not in self.queries:
                    matches, _, _ = self.index.retrieve(ProductSearchRequest(query=name))
                    self.queries[key] = {i for k in matches for i in self.index.groups[k]}
                positions |= self.queries[key]
        candidates = []
        conflicts = []
        for i in sorted(positions):
            product = self.prepared.universe.products[i]
            if product.store_id not in self.store_ids or product.usable_unit != unit:
                continue
            if not properties_match(product, properties):
                continue
            if not food and not is_nonfood(product.name):
                conflicts.append(
                    PolicyConflict(f"{product.name} kan inte klassas som icke-livsmedel.")
                )
                continue
            if product.product_role == "non_human_food":
                continue
            from app.services.reviewed_cold_meals import plain_quark

            reviewed_quark = canonical == "kvarg" and plain_quark(
                product, self.source_facts(product)
            )
            if canonical == "kvarg" and not product_key and not reviewed_quark:
                continue
            if (
                self.facts
                and product.semantic_confidence not in {"high", "exact"}
                and not reviewed_quark
                and not product_key
            ):
                continue
            try:
                check_product(
                    product, profile, self.source_facts(product), organic_animals=organic_animals
                )
            except PolicyConflict as exc:
                if exc.stage is None:
                    exc.stage = "policy_taste"
                conflicts.append(exc)
                continue
            if reviewed_quark and not product_key:
                candidate = ProductCandidate.from_product(product, 1).model_copy(
                    update={
                        "semantic_confidence": "high",
                        "semantic_evidence": [
                            "reviewed plain quark name/form and retained dairy ingredients"
                        ],
                        "canonical_food": "kvarg",
                        "food_family": "dairy",
                        "product_role": "quark",
                    }
                )
            elif product_key:
                # Explicit exact identity is the match evidence; no fuzzy alias.
                candidate = ProductCandidate.from_product(product, 1).model_copy(
                    update={
                        "semantic_confidence": "exact",
                        "semantic_evidence": ["user-confirmed exact product identity"],
                    }
                )
            else:
                matched = self.service.matcher.match(
                    requirement, [product], store_ids=list(self.store_ids)
                )
                if matched:
                    candidate = matched[0]
                elif properties or canonical not in self.view.economic_pool.candidates_by_name:
                    # For out-of-taxonomy generic goods all query terms must be
                    # present; the user confirms the resulting query properties.
                    from app.services.product_search import search_text

                    tokens = set(search_text(name).split())
                    if not tokens <= set(search_text(product.name).split()):
                        continue
                    candidate = ProductCandidate.from_product(product, 1).model_copy(
                        update={
                            "semantic_confidence": "high",
                            "semantic_evidence": ["confirmed generic query and properties"],
                        }
                    )
                else:
                    continue
            candidate = price_candidate_for_context(candidate, self.user, on_date=self.pricing_date)
            candidates.append((i, candidate))
        if not candidates:
            if conflicts:
                raise conflicts[0]
            raise PolicyConflict(
                f"Ingen verifierad köpbar vara för {name}, {unit}. Kontrollera mängden, egenskaperna eller exakt produkt.",
                code="DATA_BLOCKED",
            )
        self.lookup_cache[cache_key] = candidates
        return candidates

    def clean_recipe(self, recipe, meal):
        # Never trust a caller/LLM supplied canonical identity over the visible ingredient.
        recipe = Recipe.model_validate(
            {
                **recipe.model_dump(),
                "ingredients": [
                    {**i.model_dump(), "canonical_name": canonicalize_ingredient_name(i.name)}
                    for i in recipe.ingredients
                ],
            }
        )
        profile = merged_profile(self.spec.profile, meal.profile)
        if not recipe_respects_diet(
            recipe,
            preference=meal.diet,
            avoid_ingredients=profile.exclusions
            + profile.allergies
            + self.request.avoid_ingredients,
        ):
            raise PolicyConflict(
                f"{recipe.name} strider mot kostval eller hård uteslutning.", stage="policy_taste"
            )
        for ingredient in self.service.normalizer.normalize_and_aggregate([recipe]):
            self.resolve(
                ingredient.canonical_name,
                ingredient.required_quantity,
                ingredient.unit,
                profile=profile,
                organic_animals=self.spec.organic_animals or meal.organic_animals,
            )
        return recipe

    def _need_rows(self, slots):
        rows = []
        for slot in slots:
            if slot.recipe is None:
                continue
            meal = self.meals[slot.meal_type]
            recipe = self.clean_recipe(slot.recipe, meal)
            profile = merged_profile(self.spec.profile, meal.profile)
            for ingredient in self.service.normalizer.normalize_and_aggregate([recipe]):
                rows.append(
                    {
                        "name": ingredient.canonical_name,
                        "quantity": ingredient.required_quantity,
                        "unit": ingredient.unit,
                        "source": slot.id,
                        "food": True,
                        "use_pantry": True,
                        "product_key": None,
                        "properties": [],
                        "profile": profile,
                        "organic_animals": self.spec.organic_animals or meal.organic_animals,
                    }
                )
        for extra in self.spec.extras:
            expected = interpretation(extra.query)
            if any(p not in extra.properties for p in expected):
                raise PolicyConflict(
                    f"Bekräfta och behåll egenskapen {', '.join(expected)} för {extra.query}."
                )
            rows.append(
                {
                    "name": extra.query,
                    "quantity": extra.quantity,
                    "unit": extra.unit,
                    "source": extra.id,
                    "food": not is_nonfood(extra.query),
                    "use_pantry": extra.use_pantry,
                    "product_key": extra.product_key,
                    "properties": extra.properties,
                    "profile": self.spec.profile,
                    "organic_animals": self.spec.organic_animals,
                }
            )
            if not extra.food and not is_nonfood(extra.query):
                raise PolicyConflict(f"{extra.query} kan inte undantas från matinköpets krav.")
        consumed = defaultdict(float)
        for booked in consumed_demands(self.state, self.plan_id):
            consumed[booked["demand_key"]] += booked["quantity"]
        for row in rows:
            row["demand_key"] = demand_key(row)
            row["original_quantity"] = row["quantity"]
            row["quantity"] = max(0, row["quantity"] - consumed[row["demand_key"]])
        return rows

    def _allocate(self, row, resolved, available):
        remaining = row["quantity"]
        allocations = []
        keys = {self.product_keys[i] for i, _ in resolved}
        purchased_ids = {
            r.get("item_id")
            for e in self.state.get("ledger", [])
            if e["plan_id"] == self.plan_id and e["action"] == "purchase"
            for r in e["rows"]
        }
        purchased_ids.update(self.state.get("legacy_purchase_lots", {}).get(self.plan_id, []))
        for item in self.items:
            if not row["use_pantry"] and item["id"] not in purchased_ids:
                continue
            if item["unusable"] or item["unit"] != row["unit"] or available[item["id"]] <= 0:
                continue
            if item["product_key"]:
                if item["product_key"] not in keys:
                    continue
            else:
                if row["product_key"] or row["properties"]:
                    continue
                if canonicalize_ingredient_name(item["name"]) != canonicalize_ingredient_name(
                    row["name"]
                ):
                    continue
                if row["profile"].allergies or row["profile"].exclusions:
                    # A generic pantry entry has no complete source declaration.
                    continue
            # Exact pantry lots use the same qualified facts as purchases. A
            # generic lot has no declared nutrition and cannot borrow a label.
            if (
                row.get("nutrients")
                and not item["product_key"]
                and (not self.spec.allow_nutrition_estimates or not item.get("nutrition_reference"))
            ):
                raise PolicyConflict(
                    f"{item['name']}: skafferivarans exakta produkt och näringsdeklaration saknas. För generiskt underlag krävs uppskattningsläge och bekräftat livsmedel/beredningsstatus i Skafferi.",
                    code="DATA_BLOCKED",
                )
            if row["organic_animals"] and not item["product_key"]:
                raise PolicyConflict(
                    f"{item['name']}: skafferivarans animaliska innehåll/ekostatus saknar produktunderlag.",
                    code="DATA_BLOCKED",
                )
            used = min(remaining, available[item["id"]])
            allocations.append(
                {
                    "item_id": item["id"],
                    "quantity": used,
                    "unit": item["unit"],
                    "name": item["name"],
                    "source": row["source"],
                    "demand_key": row["demand_key"],
                    "product_key": item["product_key"],
                    "nutrition_reference": item.get("nutrition_reference"),
                }
            )
            remaining -= used
            available[item["id"]] -= used
            if remaining < 1e-8:
                return 0, allocations
        return remaining, allocations

    def basket(self, slots, *, final=True):
        available = {i["id"]: i["available"] for i in self.items}
        rows = self._need_rows(slots)
        allocations, groups = [], []
        missing_nutrition = set()
        nutrition_needs = set()
        # Constrained explicit rows first: a compatible recipe can share their
        # packages, but two different exact variants never become interchangeable.
        rows.sort(key=lambda r: (not bool(r["product_key"]), not bool(r["properties"])))
        for row in rows:
            if row["quantity"] <= 0:
                continue
            resolved = self.resolve(
                row["name"],
                row["quantity"],
                row["unit"],
                product_key=row["product_key"],
                properties=row["properties"],
                profile=row["profile"],
                organic_animals=row["organic_animals"],
                food=row["food"],
            )
            meal = next((self.meals[s.meal_type] for s in slots if s.id == row["source"]), None)
            requested = requested_nutrients(meal.limits) if meal else set()
            recipe = next((s.recipe for s in slots if s.id == row["source"]), None)
            row["nutrients"] = sorted(requested)
            if requested:
                nutrition_needs.add(row["name"])
                verified = [
                    (i, c)
                    for i, c in resolved
                    if (
                        fact := self.nutrition_evidence(
                            self.prepared.universe.products[i],
                            row["name"],
                            row["unit"],
                            requested,
                            recipe,
                        )
                    )
                    and fact.nutrition_unit == row["unit"]
                    and fact.nutrition_basis
                    and fact.nutrition_preparation == "as_sold"
                    and requested <= fact.nutrition.keys()
                    and all(
                        math.isfinite(fact.nutrition[k]) and fact.nutrition[k] >= 0
                        for k in requested
                    )
                ]
                if not verified:
                    missing_nutrition.add(row["name"])
                    self.diagnostics.missing_needs[(row["source"], row["name"])] = {
                        "slot_id": row["source"],
                        "meal_type": meal.meal_type,
                        "recipe": recipe.name,
                        "ingredient": row["name"],
                        "quantity": row["quantity"],
                        "unit": row["unit"],
                        "requested_nutrients": sorted(requested),
                        "reason_code": "NUTRITION_EVIDENCE_UNQUALIFIED",
                        "reason": "Kvalificerad deklaration eller tillåten referens med rätt enhet/beredning saknas.",
                    }
                else:
                    resolved = verified
            quantity, allocation = self._allocate(row, resolved, available)
            allocations.extend(allocation)
            if quantity <= 0:
                continue
            identities = {i for i, _ in resolved}
            group = next(
                (
                    g
                    for g in groups
                    if g["unit"] == row["unit"]
                    and g["food"] == row["food"]
                    and g["positions"] & identities
                ),
                None,
            )
            if group:
                group["quantity"] += quantity
                group["positions"] &= identities
                group["sources"].append(row["source"])
                group["demand_keys"].append(row["demand_key"])
            else:
                groups.append(
                    {
                        "name": row["name"],
                        "quantity": quantity,
                        "unit": row["unit"],
                        "food": row["food"],
                        "sources": [row["source"]],
                        "demand_keys": [row["demand_key"]],
                        "positions": identities,
                        "candidates": dict(resolved),
                    }
                )
        if missing_nutrition:
            raise PolicyConflict(
                f"{recipe.name if recipe else 'Korgen'}: näringsunderlag med rätt enhet saknas för {', '.join(sorted(missing_nutrition))} ({len(missing_nutrition)} av {len(nutrition_needs)} ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde.",
                code="DATA_BLOCKED",
                stage="product_qualification",
            )
        ingredients, candidate_map = [], {}
        for n, group in enumerate(groups):
            key = f"{group['name']} [{n + 1}]"
            group["key"] = key
            for row in rows:
                if row["demand_key"] in group["demand_keys"]:
                    row["purchase_key"] = key
            candidates = [group["candidates"][i] for i in group["positions"]]
            lock = self.spec.product_locks.get(key)
            if lock:
                candidates = [
                    c
                    for c in candidates
                    if self.product_keys[self.by_identity[(c.store_id, c.product_id)]] == lock
                ]
                if not candidates:
                    raise PolicyConflict(f"Låst produkt saknas för {group['name']}.")
            candidate_map[key] = candidates
            ingredients.append(
                NormalizedIngredient(
                    canonical_name=key,
                    required_quantity=group["quantity"],
                    unit=group["unit"],
                    source_recipes=group["sources"],
                )
            )
        with self.optimizer.quote_cache():
            try:
                basket = self.optimizer.optimize(
                    ingredients, candidate_map, self.view.stores, max_stores=self.request.max_stores
                )
            except IncompleteBasketError as exc:
                stores = sorted({c.store_id for cs in candidate_map.values() for c in cs})
                covers = any(
                    all(any(c.store_id in subset for c in cs) for cs in candidate_map.values())
                    for n in range(1, min(len(stores), self.request.max_stores) + 1)
                    for subset in combinations(stores, n)
                )
                raise PolicyConflict(
                    str(exc), stage="price_basket" if covers else "store_cap"
                ) from exc
            ordinary_total = basket.total
            if self.spec.surplus_mode == "allow_larger":
                basket = self._larger_packages(basket, ingredients, candidate_map)
            if self.spec.organic_percent:
                try:
                    basket = self._ecological_basket(ingredients, candidate_map, groups, basket)
                except PolicyConflict as exc:
                    exc.stage = "organic"
                    if final:
                        raise
                    # A later meal can still raise the global cost share. Do not
                    # declare a partial menu infeasible, but price qualified
                    # alternatives before beam pruning whenever available.
            if any(self.meals[s.meal_type].limits.active for s in slots if s.recipe):
                basket = self._qualified_nutrition_basket(
                    slots,
                    basket,
                    ingredients,
                    candidate_map,
                    groups,
                    rows,
                    allocations,
                    final=final,
                )
        audit = self.auditor.audit(
            ingredients,
            basket,
            user_pricing_context=self.user,
            strategic_extras_allowed=self.spec.surplus_mode == "allow_larger",
        )
        if not audit.passed:
            raise PolicyConflict("Korgens mängder/prisvillkor kunde inte verifieras.")
        for group in groups:
            item = next(
                i for store in basket.stores for i in store.items if i.ingredient == group["key"]
            )
            group["selected_product_key"] = self.product_keys[
                self.by_identity[(item.store_id, item.product_id)]
            ]
            product = self.prepared.universe.products[
                self.by_identity[(item.store_id, item.product_id)]
            ]
            group["unused_source_offers"] = [
                offer.model_dump(mode="json")
                for offer in product.offers
                if (
                    (
                        offer.price_contract_id is not None
                        and item.price_contract_id is not None
                        and offer.price_contract_id != item.price_contract_id
                        and (
                            item.applied_offer is None
                            or offer.price_contract_id != item.applied_offer.price_contract_id
                        )
                    )
                    or (item.price_mechanism == "regular" and item.applied_offer is None)
                )
            ]
        for group in groups:
            item = next(
                i for store in basket.stores for i in store.items if i.ingredient == group["key"]
            )
            if item.group_applications:
                product = self.prepared.universe.products[
                    self.by_identity[(item.store_id, item.product_id)]
                ]
                group["unused_source_offers"] = [
                    offer.model_dump(mode="json")
                    for offer in product.offers
                    if item.applied_offer is None or offer != item.applied_offer
                ]
        checks = self._check_final(slots, basket, groups, rows, allocations) if final else {}
        return {
            "basket": basket,
            "ingredients": ingredients,
            "groups": groups,
            "allocations": allocations,
            "remaining_demands": [
                {k: v for k, v in r.items() if k not in {"profile", "organic_animals", "nutrients"}}
                for r in rows
            ],
            "available_surplus": [
                {
                    "item_id": i["id"],
                    "name": i["name"],
                    "quantity": available[i["id"]],
                    "unit": i["unit"],
                }
                for i in self.items
                if available[i["id"]] > 1e-8
            ],
            "checks": checks,
            "audit": audit,
            "larger_purchase_cost": max(0, float(money(basket.total - ordinary_total)))
            if self.spec.surplus_mode == "allow_larger"
            else 0,
        }

    def _larger_packages(self, basket, ingredients, candidates):
        """Opt-in strategic multibuy, quoted by the original package calculator.

        At most 10% extra spend per line, and at least 10% lower package price.
        Actual needs remain unchanged; the extra purchased quantity is surplus.
        """
        from app.services.basket_calculator import BasketCalculator

        calculator = BasketCalculator()
        groups = []
        for store in basket.stores:
            rows = []
            for current in store.items:
                selected = next(
                    c
                    for c in candidates[current.ingredient]
                    if c.store_id == current.store_id and c.product_id == current.product_id
                )
                choices = []
                for offer in selected.offers:
                    if (
                        selected.sale_model != "fixed_package"
                        or not selected.usable_quantity
                        or offer.required_packages <= current.packages_needed
                    ):
                        continue
                    requirement = next(
                        i for i in ingredients if i.canonical_name == current.ingredient
                    )
                    increased = requirement.model_copy(
                        update={
                            "required_quantity": offer.required_packages * selected.usable_quantity
                        }
                    )
                    extra = calculator.calculate_item(increased, selected)
                    if (
                        extra.total_price <= current.total_price * 1.1
                        and extra.total_price / extra.packages_needed
                        <= current.total_price / current.packages_needed * 0.9
                    ):
                        choices.append(
                            extra.model_copy(
                                update={
                                    "required_quantity": current.required_quantity,
                                    "strategic_extra_quantity": increased.required_quantity
                                    - current.required_quantity,
                                    "waste_quantity": extra.purchased_usable_quantity
                                    - current.required_quantity,
                                    "purchase_warning": f"Valt större köp: {extra.packages_needed - current.packages_needed} extra förpackningar, {extra.total_price - current.total_price:.2f} kr i merkostnad.",
                                }
                            )
                        )
                rows.append(min(choices, key=lambda i: i.total_price) if choices else current)
            groups.append(
                OptimizedStoreGroup(
                    store_id=store.store_id,
                    store_name=store.store_name,
                    items=rows,
                    subtotal=float(money(sum(i.total_price for i in rows))),
                )
            )
        return OptimizedBasket(
            stores=groups,
            total=float(money(sum(g.subtotal for g in groups))),
            max_stores=basket.max_stores,
            savings_vs_single_store=None,
        )

    def _eco_percent(self, basket, groups):
        food = {g["key"]: g["food"] for g in groups}
        denominator = Decimal(0)
        organic = Decimal(0)
        for group in basket.stores:
            for item in group.items:
                if not food[item.ingredient]:
                    continue
                denominator += money(item.total_price)
                p = self.prepared.universe.products[
                    self.by_identity[(item.store_id, item.product_id)]
                ]
                facts = self.source_facts(p)
                if facts and facts.organic is True:
                    organic += money(item.total_price)
        return float(organic * 100 / denominator) if denominator else None

    def _eco_evidence(self, basket, groups):
        food = {g["key"] for g in groups if g["food"]}
        lines = []
        for store in basket.stores:
            for item in store.items:
                if item.ingredient not in food:
                    continue
                fact = self.source_facts(
                    self.prepared.universe.products[
                        self.by_identity[(item.store_id, item.product_id)]
                    ]
                )
                lines.append(
                    {
                        "product_id": item.product_id,
                        "name": item.product_name,
                        "cost": item.total_price,
                        "organic": fact.organic if fact else None,
                        "sources": list(fact.field_sources.get("organic", ())) if fact else [],
                    }
                )
        return {
            "status": "NO_NEW_FOOD_PURCHASES" if not lines else "CALCULATED",
            "requested_percent": self.spec.organic_percent,
            "lines": lines,
            "food_cost": float(sum((money(r["cost"]) for r in lines), Decimal(0))),
            "organic_food_cost": float(
                sum((money(r["cost"]) for r in lines if r["organic"] is True), Decimal(0))
            ),
        }

    def _qualified_nutrition_basket(
        self, slots, baseline, ingredients, candidates, groups, rows, allocations, *, final
    ):
        """Bounded product search, repriced by the existing whole-basket engine.

        Run before meal beam pruning too: a cheap nutritionally unsuitable meal
        must not crowd out complete alternatives. Final validation repeats it.
        """
        try:
            self._check_final(slots, baseline, groups, rows, allocations)
            return baseline
        except PolicyConflict as initial:
            if initial.code == "DATA_BLOCKED":
                raise  # All candidates already require the selected data fields.
            conflict = initial
        import heapq

        keys = [
            k
            for k in candidates
            if any(r.get("purchase_key") == k and r.get("nutrients") for r in rows)
        ]
        choices = []
        extrema = defaultdict(list)
        requested = set().union(
            *(requested_nutrients(self.meals[s.meal_type].limits) for s in slots)
        )
        if not requested:
            raise conflict
        for key in keys:
            current = next(
                i for store in baseline.stores for i in store.items if i.ingredient == key
            )
            ordered = sorted(
                candidates[key],
                key=lambda c: (
                    c.product_id != current.product_id or c.store_id != current.store_id,
                    c.effective_price,
                    c.product_id,
                ),
            )
            # Retain nutritional extrema before the bounded combination search,
            # plus cheapest and verified organic alternatives. Unknown is absent.
            important = ordered[:1]
            for nutrient in sorted(requested):

                def effective_value(candidate, key=key, nutrient=nutrient):
                    product = self.prepared.universe.products[
                        self.by_identity[(candidate.store_id, candidate.product_id)]
                    ]
                    values = []
                    for need in rows:
                        if need.get("purchase_key") != key or nutrient not in need.get(
                            "nutrients", []
                        ):
                            continue
                        recipe = next(s.recipe for s in slots if s.id == need["source"])
                        evidence = self.nutrition_evidence(
                            product, need["name"], need["unit"], {nutrient}, recipe
                        )
                        if evidence and nutrient in evidence.nutrition:
                            values.append(evidence.nutrition[nutrient])
                    return min(values) if values else None

                values = {(c.store_id, c.product_id): effective_value(c) for c in ordered}
                known = [c for c in ordered if values[(c.store_id, c.product_id)] is not None]
                if known:
                    known.sort(key=lambda c: values[(c.store_id, c.product_id)])
                    important.extend([known[0], known[-1]])
                    extrema[(nutrient, "min")].append(known[0])
                    extrema[(nutrient, "max")].append(known[-1])
                else:
                    extrema[(nutrient, "min")].append(ordered[0])
                    extrema[(nutrient, "max")].append(ordered[0])
            important.extend(ordered)
            unique = list({(c.store_id, c.product_id): c for c in reversed(important)}.values())[
                ::-1
            ]
            equivalent = {}
            for candidate in unique:
                product = self.prepared.universe.products[
                    self.by_identity[(candidate.store_id, candidate.product_id)]
                ]
                fact = self.source_facts(product)
                signature = [fact.organic if fact else None]
                for need in rows:
                    if need.get("purchase_key") != key or not need.get("nutrients"):
                        continue
                    recipe = next(s.recipe for s in slots if s.id == need["source"])
                    evidence = self.nutrition_evidence(
                        product, need["name"], need["unit"], set(need["nutrients"]), recipe
                    )
                    signature.append(tuple((n, evidence.nutrition[n]) for n in need["nutrients"]))
                equivalent.setdefault(tuple(signature), []).append(candidate)
            # The bounded search is over distinct nutritional choices. Keep ALL
            # exact products, package sizes and stores within each choice for the
            # existing pricing engine; equal macros do not mean equal products.
            choices.append(list(equivalent.values()))
        searched = 0
        best = None
        # Explore nearby alternatives across ALL relevant ingredients first.
        # A large final dimension (or unrelated extras) cannot consume the whole
        # search budget before an earlier ingredient gets its second candidate.
        origin = (0,) * len(keys)
        queue, seen = [(0, origin)], {origin}
        # Joint extrema must actually be tried: the nearby-product budget can
        # otherwise end before changing several shared ingredients together.
        for combination in extrema.values():
            indices = tuple(
                next(
                    i
                    for i, group in enumerate(choices[n])
                    if any(
                        (c.store_id, c.product_id) == (selected.store_id, selected.product_id)
                        for c in group
                    )
                )
                for n, selected in enumerate(combination)
            )
            if indices not in seen:
                seen.add(indices)
                heapq.heappush(queue, (0, indices))
        while queue and searched < 256:
            _, indices = heapq.heappop(queue)
            for dimension, index in enumerate(indices):
                if index + 1 < len(choices[dimension]):
                    neighbor = tuple(
                        index + 1 if n == dimension else v for n, v in enumerate(indices)
                    )
                    if neighbor not in seen:
                        seen.add(neighbor)
                        heapq.heappush(queue, (sum(neighbor), neighbor))
            combination = [choices[n][i] for n, i in enumerate(indices)]
            searched += 1
            narrowed = {**candidates, **dict(zip(keys, combination, strict=True))}
            try:
                selected = {i.ingredient: i for store in baseline.stores for i in store.items}
                selected.update(
                    {key: group[0] for key, group in zip(keys, combination, strict=True)}
                )
                # Same nutrition calculator, before pricing. Every product in a
                # class has the same requested per-recipe values; no provisional
                # prices or package surplus enter this qualification.
                self._check_nutrition(slots, selected, rows, allocations)
                option = self.optimizer.optimize(
                    ingredients, narrowed, self.view.stores, max_stores=self.request.max_stores
                )
                if (
                    final
                    and self.spec.organic_percent
                    and (self._eco_percent(option, groups) or 0) + 1e-8 < self.spec.organic_percent
                ):
                    continue
                self._check_final(slots, option, groups, rows, allocations)
                if best is None or option.total < best.total:
                    best = option
            except (PolicyConflict, IncompleteBasketError):
                continue
        if best is None:
            raise PolicyConflict(
                f"Ingen komplett kombination hittades i näringssökningen ({min(searched, 256)} kombinationer). Exempel på beräknat näringsavslag: {conflict} Kraven är oförändrade; sökningen bevisar inte omöjlighet.",
                code="NUTRITION_TARGET_NOT_MET",
                stage="nutrition",
            )
        return best

    def _ecological_basket(self, ingredients, candidates, groups, baseline):
        percent = self._eco_percent(baseline, groups)
        if percent is None and any(g["food"] for g in groups):
            raise PolicyConflict(
                "Matinköpets nettokostnad är noll. Den valda ekologiska kostnadsandelen kan därför inte beräknas. Ändra kravet uttryckligen i Mina val eller välj andra varor.",
                code="DATA_BLOCKED",
            )
        if percent is None or percent + 1e-8 >= self.spec.organic_percent:
            return baseline
        organic_candidates = {}
        for name, values in candidates.items():
            organic_candidates[name] = [
                c
                for c in values
                if (
                    (
                        facts := self.source_facts(
                            self.prepared.universe.products[
                                self.by_identity[(c.store_id, c.product_id)]
                            ]
                        )
                    )
                    and facts.organic is True
                )
            ]
        eligible = [g["key"] for g in groups if g["food"] and organic_candidates[g["key"]]]
        if not eligible:
            raise PolicyConflict(
                f"Ingen av {sum(g['food'] for g in groups)} matinköpsrader har ett verifierat ekologiskt alternativ i sökningen. Vald kostnadsandel kan inte verifieras. Ändra kravet uttryckligen i Mina val, välj andra varor eller gå tillbaka.",
                code="DATA_BLOCKED",
            )
        winners = []
        searched = 0
        # Bounded search over ecological candidate restrictions, always repriced
        # by the original whole-basket optimizer. Exhaustion is explicitly reported.
        subsets = [tuple(eligible)]
        for size in range(1, len(eligible)):
            for subset in combinations(eligible, size):
                subsets.append(subset)
                if len(subsets) >= 256:
                    break
            if len(subsets) >= 256:
                break
        for subset in subsets:
            narrowed = {
                k: organic_candidates[k] if k in subset else v for k, v in candidates.items()
            }
            try:
                option = self.optimizer.optimize(
                    ingredients, narrowed, self.view.stores, max_stores=self.request.max_stores
                )
                searched += 1
                if (self._eco_percent(option, groups) or 0) + 1e-8 >= self.spec.organic_percent:
                    winners.append(option)
            except IncompleteBasketError:
                continue
        if not winners:
            raise PolicyConflict(
                f"Ingen kombination hittades med minst {self.spec.organic_percent:g} % verifierat eko inom butikstaket ({searched} kontrollerade kombinationer). Kravet är oförändrat."
            )
        return min(winners, key=lambda b: b.total)

    def _check_final(self, slots, basket, groups, rows, allocations):
        ingredient_checks = []
        purchased = {i.ingredient: i for s in basket.stores for i in s.items}
        for need in rows:
            profile = need["profile"]
            if not (profile.exclusions or profile.allergies):
                continue
            positions = set()
            item = purchased.get(need.get("purchase_key"))
            if item:
                positions.add(self.by_identity[(item.store_id, item.product_id)])
            for allocation in allocations:
                if allocation["demand_key"] == need["demand_key"]:
                    positions.update(self.index.groups.get(allocation.get("product_key"), ()))
            for position in sorted(positions):
                p = self.prepared.universe.products[position]
                fact = self.source_facts(p)
                check_product(p, profile, fact, organic_animals=need["organic_animals"])
                ingredient_checks.append(
                    {
                        "source": need["source"],
                        "ingredient": need["name"],
                        "product_id": p.product_id,
                        "store_id": p.store_id,
                        "name": p.name,
                        "exclusions": profile.exclusions,
                        "status": "CHECKED_INGREDIENT_CHOICE",
                        "ingredients": list(fact.ingredients) if fact else [],
                        "evidence_kind": fact.ingredient_evidence_kind if fact else None,
                        "field_sources": list(fact.field_sources.get("ingredients", ()))
                        if fact
                        else [],
                        "allergy_status": "REQUESTED_SEPARATELY"
                        if profile.allergies
                        else "NOT_REQUESTED",
                    }
                )
        nutrition = self._check_nutrition(slots, purchased, rows, allocations)
        has_allergies = bool(
            self.spec.profile.allergies
            or any(m.count and m.profile.allergies for m in self.spec.meals)
        )
        return {
            "purchase": "VERIFIED",
            "allergy": "VERIFIED" if has_allergies else "NOT_REQUESTED",
            "ingredient_exclusions": ingredient_checks,
            "nutrition": nutrition,
            "facts_version": self.facts_version,
            "nutrition_reference_version": self.reference_version,
            "organic_cost_percent": self._eco_percent(basket, groups),
            "organic_evidence": self._eco_evidence(basket, groups),
            "organic_animals": "VERIFIED"
            if self.spec.organic_animals
            or any(m.count and m.organic_animals for m in self.spec.meals)
            else "NOT_REQUESTED",
            "organic_definition": "Minst X % av matinköpets varukostnad ska vara verifierat ekologisk.",
            "distribution": [
                {"meal_type": s.meal_type, "slot_id": s.id, "protein": protein_category(s.recipe)}
                for s in slots
                if s.recipe
            ],
        }

    def _check_nutrition(self, slots, selected_products, rows, allocations):
        """Reuse the same per-portion calculation, never an approximate price.

        The selected package contributes nutrition only for the exact edible
        demand, after stock allocation. Neither package surplus nor the other
        slots' purchases can change that sum. Pricing/stock allocation remain
        joint and run before this function. No float rounding is used in keys.
        """
        results = []
        for slot in slots:
            if not slot.recipe:
                continue
            needs = [r for r in rows if r["source"] == slot.id]
            limits = self.meals[slot.meal_type].limits
            demand_values = []
            for need in needs:
                selected = selected_products.get(need.get("purchase_key"))
                pantry = tuple(
                    (a["name"], a["quantity"], a.get("product_key"), a.get("nutrition_reference"))
                    for a in allocations
                    if a["demand_key"] == need["demand_key"]
                )
                demand_values.append(
                    (
                        need["name"],
                        need["unit"],
                        need["quantity"],
                        need["original_quantity"],
                        (selected.store_id, selected.product_id) if selected else None,
                        pantry,
                    )
                )
            weight = (
                self.cooked_weights.get(recipe_id(slot.recipe))
                if limits.min_weight_g is not None or limits.max_weight_g is not None
                else None
            )
            key = (
                _recipe_value(slot.recipe),
                slot.meal_type,
                limits.model_dump_json(),
                self.spec.allow_nutrition_estimates,
                tuple(demand_values),
                json.dumps(weight, sort_keys=True) if weight else None,
            )
            cached = self.slot_nutrition_cache.get(key)
            if cached is None:
                try:
                    value = self._check_nutrition_uncached(
                        [slot], selected_products, needs, allocations
                    )[0]
                    cached = (value, None)
                except PolicyConflict as exc:
                    # Store values, not exceptions retaining whole search stacks.
                    cached = (None, (str(exc), exc.code, exc.stage))
                if len(self.slot_nutrition_cache) >= 2048:
                    self.slot_nutrition_cache.clear()
                self.slot_nutrition_cache[key] = cached
            value, error = cached
            if error:
                raise PolicyConflict(error[0], code=error[1], stage=error[2])
            # Slot identity is output context, not part of the food calculation.
            results.append({**value, "slot_id": slot.id})
        return results

    def _check_nutrition_uncached(self, slots, selected_products, rows, allocations):
        nutrition = []
        for slot in slots:
            if not slot.recipe:
                continue
            meal = self.meals[slot.meal_type]
            limits = meal.limits
            row = {"slot_id": slot.id, "status": "NOT_REQUESTED", "values": {}, "sources": []}
            if limits.active:
                totals = defaultdict(float)
                requested = requested_nutrients(limits)
                if requested:
                    row["calculation_basis"] = calculation_basis(
                        slot.recipe, allow_estimates=self.spec.allow_nutrition_estimates
                    )
                    for need in (r for r in rows if r["source"] == slot.id):
                        contributions = []
                        pantry = [a for a in allocations if a["demand_key"] == need["demand_key"]]
                        for allocation in pantry:
                            if (
                                not allocation.get("product_key")
                                and self.spec.allow_nutrition_estimates
                            ):
                                from app.services.nutrition_reference import (
                                    assembly_evidence,
                                    reference_evidence,
                                    validate_pantry_reference,
                                )
                                from app.services.personal_nutrition import (
                                    is_couscous_preparation,
                                    is_reference_preparation,
                                    reference_method,
                                )

                                identity = validate_pantry_reference(
                                    allocation["name"],
                                    need["unit"],
                                    allocation.get("nutrition_reference"),
                                )
                                evidence = reference_evidence(
                                    identity,
                                    cooked=is_reference_preparation(slot.recipe),
                                    method=reference_method(slot.recipe, need["name"]),
                                )
                                if is_couscous_preparation(slot.recipe):
                                    evidence = assembly_evidence(identity)
                                from app.services.reviewed_warm_meals import (
                                    evidence as warm_evidence,
                                )
                                from app.services.reviewed_warm_meals import (
                                    preparation,
                                )

                                if preparation(slot.recipe):
                                    evidence = warm_evidence(identity, slot.recipe)
                                contributions.append((allocation["quantity"], evidence, "pantry"))
                                continue
                            positions = self.index.groups.get(allocation.get("product_key"), ())
                            evidence = [
                                self.nutrition_evidence(
                                    self.prepared.universe.products[i],
                                    need["name"],
                                    need["unit"],
                                    requested,
                                    slot.recipe,
                                )
                                for i in positions
                            ]
                            evidence = [
                                f
                                for f in evidence
                                if f
                                and f.nutrition_unit == need["unit"]
                                and f.nutrition_basis
                                and f.nutrition_preparation == "as_sold"
                                and requested <= f.nutrition.keys()
                            ]
                            values = {
                                tuple((k, f.nutrition[k]) for k in sorted(requested))
                                for f in evidence
                            }
                            if len(values) != 1:
                                raise PolicyConflict(
                                    f"{need['name']}: skafferiets exakta näringsunderlag saknas eller är motstridigt.",
                                    code="DATA_BLOCKED",
                                )
                            contributions.append((allocation["quantity"], evidence[0], "pantry"))
                        quantity = need["quantity"] - sum(a["quantity"] for a in pantry)
                        if need["original_quantity"] > need["quantity"] + 1e-8:
                            raise PolicyConflict(
                                f"{need['name']}: redan förbrukade ingrediensers näringsgrund måste verifieras från den historiska revisionen.",
                                code="DATA_BLOCKED",
                            )
                        if quantity > 1e-8:
                            selected = selected_products.get(need.get("purchase_key"))
                            fact = (
                                self.nutrition_evidence(
                                    self.prepared.universe.products[
                                        self.by_identity[(selected.store_id, selected.product_id)]
                                    ],
                                    need["name"],
                                    need["unit"],
                                    requested,
                                    slot.recipe,
                                )
                                if selected
                                else None
                            )
                            contributions.append((quantity, fact, "purchase"))
                        for quantity, fact, origin in contributions:
                            if (
                                not fact
                                or fact.nutrition_unit != need["unit"]
                                or not fact.nutrition_basis
                                or fact.nutrition_preparation != "as_sold"
                                or not requested <= fact.nutrition.keys()
                            ):
                                raise PolicyConflict(
                                    f"{need['name']}: valda näringsvärden med rätt enhet och grund saknas.",
                                    code="DATA_BLOCKED",
                                )
                            if any(
                                not math.isfinite(fact.nutrition[k]) or fact.nutrition[k] < 0
                                for k in requested
                            ):
                                raise PolicyConflict(
                                    f"{need['name']}: konfliktfyllda näringsvärden.",
                                    code="DATA_BLOCKED",
                                )
                            for k in requested:
                                totals[k] += (
                                    fact.nutrition[k] * quantity / 100 / slot.recipe.servings
                                )
                            row["sources"].append(
                                {
                                    "source": fact.source,
                                    "product_id": fact.source_product_id,
                                    "unit": fact.nutrition_unit,
                                    "basis": fact.nutrition_basis,
                                    "quantity": quantity,
                                    "used_edible_quantity": quantity,
                                    "cooked_quantity_g": None,
                                    "origin": origin,
                                    "ingredient": need["name"],
                                    "evidence_kind": getattr(
                                        fact, "evidence_kind", "qualified_product_declaration"
                                    ),
                                    "field_sources": {
                                        k: list(v)
                                        for k, v in fact.field_sources.items()
                                        if k.startswith("nutrition.")
                                    },
                                }
                            )
                if limits.min_weight_g is not None or limits.max_weight_g is not None:
                    weight = self.cooked_weights.get(recipe_id(slot.recipe))
                    if (
                        not weight
                        or not weight.get("source")
                        or weight.get("servings") != slot.recipe.servings
                        or not isinstance(weight.get("total_g"), (int, float))
                        or not math.isfinite(weight["total_g"])
                        or weight["total_g"] <= 0
                    ):
                        raise PolicyConflict(
                            f"{slot.recipe.name}: verifierat tillagningsutbyte/ätbar tillagad vikt saknas.",
                            code="DATA_BLOCKED",
                            stage="preparation",
                        )
                    totals["weight_g"] = weight["total_g"] / slot.recipe.servings
                    row["sources"].append(weight)
                for key, value in limits.model_dump().items():
                    if value is None:
                        continue
                    metric = key.removeprefix("min_").removeprefix("max_")
                    if (key.startswith("min_") and totals[metric] < value) or (
                        key.startswith("max_") and totals[metric] > value
                    ):
                        raise PolicyConflict(
                            f"{slot.recipe.name}: {metric} {totals[metric]:.12g} per portion bryter mot {key} {value:g}.",
                            code="NUTRITION_TARGET_NOT_MET",
                            stage="nutrition",
                        )
                estimated = any(
                    s.get("evidence_kind") not in {None, "qualified_product_declaration"}
                    for s in row["sources"]
                )
                row.update(status="ESTIMATED" if estimated else "VERIFIED", values=dict(totals))
            nutrition.append(row)
        return nutrition

    def _candidates(self, meal):
        generator = self.service.candidate_generator or DeterministicRecipeCandidateGenerator()
        candidates = generator.generate_for_meal_type(
            self.view.economic_pool, meal.meal_type, count=80, servings=meal.servings
        )
        if (
            self.spec.allow_nutrition_estimates
            and meal.meal_type == "dinner"
            and requested_nutrients(meal.limits)
        ):
            candidates.extend(
                DeterministicRecipeCandidateGenerator().generate_reference_candidates(
                    servings=meal.servings
                )
            )
        valid = []
        local_conflicts = []
        self.diagnostics.pools.append({"meal_type": meal.meal_type, "raw": len(candidates)})
        for recipe in candidates:
            stage = "policy_taste"
            try:
                profile = merged_profile(self.spec.profile, meal.profile)
                if not recipe_respects_diet(
                    recipe,
                    preference=meal.diet,
                    avoid_ingredients=profile.exclusions + profile.allergies,
                ):
                    raise PolicyConflict("Strider mot kostval eller hård uteslutning.")
                stage = "preparation"
                if self.spec.allow_nutrition_estimates and requested_nutrients(meal.limits):
                    calculation_basis(recipe, allow_estimates=True)
                stage = "product_qualification"
                recipe = self.clean_recipe(recipe, meal)
                # Existing dinner safeguards remain approximate structural checks.
                quality = (
                    self.service._nutrition_for(self.request).validate_recipes([recipe])
                    if meal.meal_type == "dinner"
                    else None
                )
                if quality and not quality.is_valid:
                    from dataclasses import asdict

                    self.diagnostics.reject(
                        "nutrition",
                        recipe,
                        f"Befintlig strukturell måltidskontroll (inte ditt valda proteinmål): {asdict(quality.results[0])}",
                    )
                    continue
                if meal.limits.active:
                    # Qualify every meal type before menu branching. Previously
                    # only depth-one dinners were independently checked; failed
                    # breakfasts/snacks could remain hidden behind dinner search.
                    self.basket(
                        [
                            MealSlot(
                                id=f"{meal.meal_type}-1",
                                day=1,
                                meal_type=meal.meal_type,
                                recipe=recipe,
                            )
                        ],
                        final=False,
                    )
                    self.diagnostics.singleton_passed += 1
                valid.append(recipe)
            except (PolicyConflict, ValueError) as exc:
                self.diagnostics.reject(getattr(exc, "stage", None) or stage, recipe, str(exc))
                if len(local_conflicts) < 10:
                    local_conflicts.append(exc)
        if not valid:
            if local_conflicts:
                raise local_conflicts[0]
            raise PolicyConflict(f"Inga användbara recept för {meal.meal_type} med dina val.")
        return valid

    def create(self, *, replace_slot=None, balanced_reference=None):
        try:
            result = self._create(replace_slot=replace_slot, balanced_reference=balanced_reference)
            result.personal.checks["planning_diagnostics"] = self.diagnostics.snapshot()
            return result
        except (ValueError, IncompleteBasketError) as exc:
            message = str(exc)
            code = getattr(exc, "code", "SEARCH_BLOCKED")
            if isinstance(exc, IncompleteBasketError):
                message = "Sökningen hittade ingen komplett meny med dina krav. Se blockeringsfördelningen. Inga krav har sänkts."
            elif self.diagnostics.pools:
                message = (
                    "Ingen komplett kombination hittades. Flera kandidater har prövats; exemplet nedan förklarar inte hela veckoplanen. "
                    + message
                )
            if not self.spec.allow_nutrition_estimates and any(
                m.count and requested_nutrients(m.limits) for m in self.spec.meals
            ):
                self._estimate_alternatives()
            raise PolicyConflict(
                message,
                code=code,
                conflicts=getattr(exc, "conflicts", None),
                diagnostics=self.diagnostics.snapshot(),
            ) from exc

    def _estimate_alternatives(self):
        """Read-only eligibility probe; never changes the submitted opt-in."""
        alternative = self.request.model_copy(deep=True)
        alternative.personal.allow_nutrition_estimates = True
        probe = PersonalPlanner(
            alternative,
            self.settings,
            self.prepared,
            self.state,
            plan_id=self.plan_id,
            facts=self.facts,
            cooked_weights=self.cooked_weights,
            now=self.now,
        )
        generator = DeterministicRecipeCandidateGenerator()
        for meal in probe.spec.meals:
            if not meal.count or not requested_nutrients(meal.limits):
                continue
            recipes = (
                generator.generate_reference_candidates(servings=meal.servings)
                if meal.meal_type == "dinner"
                else generator.generate_for_meal_type(
                    probe.view.economic_pool, meal.meal_type, servings=meal.servings
                )
            )
            for recipe in recipes:
                try:
                    result = probe.basket(
                        [
                            MealSlot(
                                id=f"{meal.meal_type}-1",
                                day=1,
                                meal_type=meal.meal_type,
                                recipe=recipe,
                            )
                        ]
                    )
                except (ValueError, IncompleteBasketError):
                    continue
                if result["checks"]["nutrition"][0]["status"] == "ESTIMATED":
                    self.diagnostics.estimate_alternatives.append(
                        {
                            "meal_type": meal.meal_type,
                            "recipe": recipe.name,
                            "values": result["checks"]["nutrition"][0]["values"],
                            "scope": "one_meal_only",
                        }
                    )
                    break

    def _create(self, *, replace_slot=None, balanced_reference=None):
        slots = self.spec.slots
        if slots is None:
            slots = [
                MealSlot(id=f"{meal.meal_type}-{day}", day=day, meal_type=meal.meal_type)
                for meal in self.spec.meals
                for day in range(1, meal.count + 1)
            ]
        generating = self.spec.slots is None
        # Keep Varierad conditioned on a real Balanserad menu, as in the existing
        # planner. Its ceiling covers breakfasts, snacks and extras as well.
        if generating and self.request.diversity_mode == "varied" and balanced_reference is None:
            balanced_request = self.request.model_copy(
                update={"diversity_mode": DiversityMode.BALANCED}
            )
            balanced_reference = PersonalPlanner(
                balanced_request,
                self.settings,
                self.prepared,
                self.state,
                plan_id=self.plan_id,
                facts=self.facts,
                cooked_weights=self.cooked_weights,
                now=self.now,
            ).create()
        pools, options = {}, []
        for slot in slots:
            if generating or slot.id == replace_slot:
                if slot.meal_type not in pools:
                    pools[slot.meal_type] = self._candidates(self.meals[slot.meal_type])
                choices = [
                    r
                    for r in pools[slot.meal_type]
                    if not slot.recipe or recipe_id(r) != recipe_id(slot.recipe)
                ]
                options.append([slot.model_copy(update={"recipe": r}) for r in choices])
            else:
                options.append([slot])
        dinner_pool = list(
            {
                recipe_id(s.recipe): s.recipe
                for group in options
                for s in group
                if s.meal_type == "dinner" and s.recipe
            }.values()
        )
        dinner_count = sum(
            1
            for s in slots
            if s.meal_type == "dinner" and (generating or s.recipe or s.id == replace_slot)
        )
        policy_request = personal_policy_request(self.request, dinner_count)
        policy = self.service._diversity_policy_for(policy_request, self.request.diversity_mode)
        if dinner_count < 2:
            policy = policy.model_copy(update={"min_cooking_methods": 0})
        constraints = self.service._culinary_constraints(dinner_pool, policy)
        ceiling = None
        if balanced_reference is not None and dinner_count:
            references = [
                s.recipe
                for s in balanced_reference.personal.slots
                if s.meal_type == "dinner" and s.recipe
            ]
            comparison = compare_plans(references, dinner_pool)
            novel = frozenset(
                r["recipe"] for r in comparison["dinners"] if r["structurally_changed"]
            )
            constraints = replace(
                constraints,
                min_reference_changes=required_changes(dinner_count),
                reference_distinct_recipes=novel,
            )
            ceiling = float(
                money(
                    balanced_reference.optimized_basket.total
                    * (1 + self.request.varied_budget_percent / 100)
                )
            )
        draft = any(not group[0].recipe for group in options if len(group) == 1)

        def accepts(chosen, *, final):
            if not distribution_ok(chosen, self.spec.meals, partial=not final or draft):
                self.diagnostics.branch(len(chosen), "policy_taste")
                return False
            dinners = [s.recipe for s in chosen if s.meal_type == "dinner" and s.recipe]
            if len({recipe_id(r) for r in dinners}) != len(dinners):
                self.diagnostics.branch(len(chosen), "variation")
                return False
            # Repeated breakfasts/snacks are permitted. Dinner variation follows
            # the existing actual ingredient/preparation constraints.
            accepted = self.service.menu_optimizer.accepts_recipes(dinners, constraints)
            if not accepted:
                self.diagnostics.branch(len(chosen), "variation")
            return accepted

        def score(chosen, result):
            tastes = preference_score([s.recipe for s in chosen if s.recipe], self.spec.profile)
            tastes += sum(
                preference_score([s.recipe], self.meals[s.meal_type].profile)
                for s in chosen
                if s.recipe
            )
            return (
                result["basket"].total + tastes * 2,
                result["basket"].total,
                tuple(s.recipe.name if s.recipe else "" for s in chosen),
            )

        def evaluate(chosen, *, final):
            try:
                result = self.basket(chosen, final=final)
            except (ValueError, IncompleteBasketError) as exc:
                stage = getattr(exc, "stage", None) or (
                    "product_qualification"
                    if getattr(exc, "code", None) == "DATA_BLOCKED"
                    else "price_basket"
                )
                self.diagnostics.branch(len(chosen), stage)
                if (
                    len(chosen) == 1
                    and generating
                    and chosen[0].recipe
                    and not self.meals[chosen[0].meal_type].limits.active
                ):
                    self.diagnostics.reject(stage, chosen[0].recipe, str(exc))
                raise
            if (
                len(chosen) == 1
                and generating
                and not self.meals[chosen[0].meal_type].limits.active
            ):
                self.diagnostics.singleton_passed += 1
            if final and ceiling is not None and result["basket"].total > ceiling:
                raise PolicyConflict(
                    f"Varierad överskrider vald kostnadsgräns {ceiling:.2f} kr för hela korgen. Balanserad kostar {balanced_reference.optimized_basket.total:.2f} kr."
                )
            return result

        chosen, result = self.service.menu_optimizer.optimize_slots(
            options,
            evaluate=evaluate,
            accepts=accepts,
            score=score,
            beam_width=8,
            search_trace=self.diagnostics.search,
        )
        # Recheck every final constraint even if the cache supplied a beam result.
        result = self.basket(chosen, final=True)
        if not accepts(chosen, final=True):
            raise PolicyConflict("Slutlig fördelning eller variation kunde inte verifieras.")
        recipes = [s.recipe for s in chosen if s.recipe]
        basket = result["basket"]
        comparisons = []
        for cap in range(1, self.request.max_stores):
            alternative_request = self.request.model_copy(update={"max_stores": cap})
            try:
                alternative = PersonalPlanner(
                    alternative_request,
                    self.settings,
                    self.prepared,
                    self.state,
                    plan_id=self.plan_id,
                    facts=self.facts,
                    cooked_weights=self.cooked_weights,
                    now=self.now,
                ).basket(chosen)
                comparisons.append(
                    {
                        "max_stores": cap,
                        "status": "FEASIBLE",
                        "total": alternative["basket"].total,
                        "stores": [
                            {"name": s.store_name, "total": s.subtotal}
                            for s in alternative["basket"].stores
                        ],
                    }
                )
            except (PolicyConflict, IncompleteBasketError) as exc:
                comparisons.append({"max_stores": cap, "status": "CONFLICT", "message": str(exc)})
        result["checks"]["same_menu_comparisons"] = comparisons
        payload = {
            "policy": POLICY_VERSION,
            "request": self.request.model_dump(mode="json"),
            "pantry_revision": self.state["revision"],
            "facts_policy_version": self.facts_version,
            "nutrition_reference_version": self.reference_version,
            "cooked_weight_evidence": self.cooked_weights,
            "state": self.state,
            "recipes": [r.model_dump() for r in recipes],
            "prices": self.prepared.universe.universe_id,
            "freshness": self.view.cache_identity,
            "pricing_date": self.pricing_date.isoformat(),
            "memberships": self.user.cache_identity,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        needs = [
            {k: v for k, v in g.items() if k not in {"positions", "candidates"}}
            for g in result["groups"]
        ]
        surplus = [
            {
                "name": next(g["name"] for g in needs if g["key"] == i.ingredient),
                "product_name": i.product_name,
                "product_key": next(
                    g["selected_product_key"] for g in needs if g["key"] == i.ingredient
                ),
                "quantity": i.waste_quantity,
                "unit": i.unit,
            }
            for g in basket.stores
            for i in g.items
            if i.waste_quantity > 0
        ]
        portions = sum(r.servings for r in recipes)
        status = self.prepared.status(
            now=self.now,
            warning_age_hours=self.settings.price_age_warning_hours,
            stale_age_hours=self.settings.max_price_age_hours,
        )
        compared, excluded = _consumer_price_context_coverage(
            self.prepared,
            usable_context_ids=self.view.usable_context_ids,
            excluded_stale_context_ids=self.view.excluded_stale_context_ids,
        )
        return PlanResponse(
            location="Lund",
            postal_code=self.request.postal_code,
            strategy="optimized",
            diversity_mode=self.request.diversity_mode,
            recipes=recipes,
            ingredients=result["ingredients"],
            optimized_basket=basket,
            single_store_options=[],
            portions=portions,
            price_per_portion=float(money(basket.total / portions)) if portions else 0,
            membership_programs_used=self.user.memberships,
            data_source="price-universe-offline",
            data=PlanPriceData(
                **status.model_dump(exclude={"hours_until_oldest_usable_stale"}),
                pricing_timestamp=datetime.now(UTC),
                compared_price_contexts=compared,
                excluded_price_contexts=excluded,
            ),
            recipe_source="deterministic-candidates+personal-planning",
            warnings=[
                "Köpkostnaden avser hela förpackningar. Näring, allergener och eko är separata kontroller.",
                "Kontosynk kräver verifierad inloggning. Gästläget är privat för denna webbläsarsession.",
                "Kampanjgrupper används bara när källa och deltagande produktidentiteter är uttryckliga.",
            ],
            personal=PersonalResult(
                slots=chosen,
                pantry_revision=self.state["revision"],
                allocations=result["allocations"],
                future_surplus=surplus,
                needs=needs,
                checks=result["checks"],
                larger_purchase_cost=result["larger_purchase_cost"],
                cache_identity=digest,
                empty_slots=sum(s.recipe is None for s in chosen),
                remaining_demands=result["remaining_demands"],
                consumed_demands=consumed_demands(self.state, self.plan_id),
                available_surplus=result["available_surplus"],
            ),
        )

    def surplus_suggestions(self, plan):
        """Read-only previews: hypothetical future surplus never enters real stock."""
        from copy import deepcopy

        from app.models.personal import MealSettings, PantryItem

        surplus = plan.personal.future_surplus
        if not surplus:
            return []
        virtual = {
            "id": "future-preview",
            "revision": 0,
            "profile": None,
            "items": [
                PantryItem(
                    name=s["name"],
                    quantity=s["quantity"],
                    unit=s["unit"],
                    product_key=s["product_key"],
                ).model_dump()
                for s in surplus
            ],
            "reservations": {},
            "events": {},
        }
        meal = deepcopy(self.meals.get("dinner") or MealSettings(count=1, servings=1))
        meal.count = 1
        meal.distribution = {}
        spec = self.spec.model_copy(
            update={
                "pantry_revision": 0,
                "extras": [],
                "slots": None,
                "meals": [meal],
                "product_locks": {},
            }
        )
        request = self.request.model_copy(
            update={"personal": spec, "diversity_mode": DiversityMode.CHEAPEST, "recipes": 1}
        )
        preview = PersonalPlanner(
            request,
            self.settings,
            self.prepared,
            virtual,
            facts=self.facts,
            cooked_weights=self.cooked_weights,
            now=self.now,
        )
        candidates = preview._candidates(meal)
        found = []
        for recipe in candidates:
            slot = MealSlot(id="future-dinner", day=1, meal_type="dinner", recipe=recipe)
            try:
                result = preview.basket([slot])
                if not result["allocations"]:
                    continue
                found.append(
                    {
                        "recipe": recipe,
                        "new_cost": result["basket"].total,
                        "additional_purchases": result["basket"],
                        "uses_future_surplus": result["allocations"],
                        "status": "PREVIEW_ONLY",
                        "message": "Beräknade framtida rester. Inget lager eller korg ändras förrän receptet väljs. Hållbarhet är okänd.",
                    }
                )
            except (ValueError, IncompleteBasketError):
                continue
        return sorted(found, key=lambda r: r["new_cost"])[:3]
