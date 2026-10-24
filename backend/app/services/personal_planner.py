"""Composition of the existing generator, search and package price engine.

Personal data stays in this request and the owned PlanStore, never shared caches.
All relevant candidates and the final basket pass the same hard constraints.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, OrderedDict, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from functools import wraps
from itertools import combinations
from time import perf_counter
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
from app.services.basket_optimizer import (
    BasketOptimizer,
    BasketVerificationPolicy,
    QuoteSelectionRejected,
)
from app.services.diet_policy import recipe_respects_diet
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.inter_plan_distance import compare_plans, required_changes
from app.services.meal_plan_optimizer import MealPlanService, _consumer_price_context_coverage
from app.services.performance_trace import performance_span
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
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_computation_cache import (
    RecipeComputationCache,
    recipe_value,
    remember_bounded,
)
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext

POLICY_VERSION = "personal-policy-v2-10-joint-week-refinement"


def timed_stage(name):
    def decorate(function):
        @wraps(function)
        def measured(self, *args, **kwargs):
            started = perf_counter()
            try:
                with performance_span("personal_" + name):
                    return function(self, *args, **kwargs)
            finally:
                self.timings[name] += perf_counter() - started
        return measured
    return decorate


# Exact recipe value, including preparation and unrounded ingredient quantities.
# Recipe's nested lists are mutable, so object ID/name alone is not a safe key.
def _recipe_value(recipe):
    return recipe_value(recipe)


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



_AUDIT_FAILURE = "Korgens mängder/prisvillkor kunde inte verifieras."

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
        nutrition_search_limit=256,
        include_content_pack=True,
        library_generation=None,
        artifacts=None,
        previous_menus=(),
    ):
        if not 1 <= nutrition_search_limit <= 65536:
            raise ValueError("Invalid diagnostic nutrition search limit")
        self.nutrition_search_limit = nutrition_search_limit
        self.include_content_pack = include_content_pack
        self.library_generation = library_generation
        self.artifacts = artifacts
        self.previous_menus = tuple(previous_menus)[:8]
        self._qualification_views = {}
        self._supplement_qualified = False
        self._expanded_cohort_qualified = False
        self._library_search_handled = False
        from app.services.meal_library_content import identity, manifest_entries
        from app.services.recipe_library import current_recipes
        self._generation = library_generation or len(manifest_entries()["current"])
        self._prior_recipe_ids = ({identity(r) for r in current_recipes(self._generation-1)}
                                 if self._generation > 2 else None)
        self.timings = defaultdict(float)
        from app.services.complete_recipes import enabled, prepare_request
        request = prepare_request(request, settings, pantry_revision=state["revision"])
        self.complete = enabled(request)
        self.request, self.settings, self.prepared, self.state = request, settings, prepared, state
        if request.diet_preference in {"vegetarian", "vegan"} and not self.complete:
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
            self.complete
            or self.spec.organic_percent
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
        facts_started = perf_counter()
        from app.services.plan_jobs import report_stage
        report_stage("product_facts")
        with performance_span("personal_product_facts"):
            self.facts = (
                load_retained_facts(prepared) if facts is None and needs_facts else facts
            ) or {}
        self.timings["product_facts"] += perf_counter() - facts_started
        from app.services.personal_source_facts import facts_version

        self.facts_version = (facts_version(self.facts)
            if getattr(settings, "library_search_policy", "legacy") == "smako-verified-reference-v1"
            else getattr(self.facts, "version", None) or facts_version(self.facts))
        self.reference_version = None
        if self.spec.allow_nutrition_estimates:
            from app.services.nutrition_reference import reference_data

            self.reference_version = reference_data()["content_version"]
        self.cooked_weights = cooked_weights or {}
        self.now = now or datetime.now(UTC)
        self.pricing_date = self.now.astimezone(ZoneInfo("Europe/Stockholm")).date()
        self.service = MealPlanService(settings)
        self.optimizer = BasketOptimizer(
            memoize_store_subsets=True,
            verification_policy=BasketVerificationPolicy.strict_live(
                allow_estimated_quantities=request.purchase_planning_mode == "estimated", allow_medium_semantic=False
            )
        )
        self.auditor = BasketAuditor(pantry_items=frozenset())
        self.user = UserPricingContext.from_chain_flags(
            request.pricing_memberships
            or {
                k: request.use_member_prices
                for k in ("ica", "coop", "willys", "hemkop", "citygross", "lidl")
            }
        )
        self.view = prepared.request_view(
            now=self.now, stale_age_hours=settings.max_price_age_hours
        )
        self.store_ids = {s.store_id for s in self.view.stores}
        if request.allowed_store_ids:
            missing = set(request.allowed_store_ids) - self.store_ids
            if missing:
                raise PolicyConflict("Valda priskontexter saknas eller är för gamla: " + ", ".join(sorted(missing)),
                                     code="DATA_BLOCKED", stage="store_cap")
            self.store_ids &= set(request.allowed_store_ids)
        self.index = prepared.product_search_index
        self.product_keys = {i: k for k, positions in self.index.groups.items() for i in positions}
        self.by_identity = {
            (p.store_id, p.product_id): i for i, p in enumerate(prepared.universe.products)
        }
        self.items = available_items(state, plan_id=plan_id) if self.spec.use_pantry else []
        self.meals = {m.meal_type: m for m in self.spec.meals}
        # Exact declarations may identify food classes absent from a brand's
        # short retail name. Keep this projection request-local; never change
        # the shared product identity, price or source scope.
        from app.services.meal_prepared_artifacts import declaration_index
        self.declared_classes = {}
        self.declared_positions = defaultdict(set)
        self.declared_classes = declaration_index(prepared.universe,self.facts,self.source_facts)
        for i, food_class in self.declared_classes.items():
            self.declared_positions[food_class].add(i)
        self.lookup_cache = {}
        self.lookup_failures = OrderedDict()
        # Only this planner owns these immutable-by-convention facts and this
        # request's estimate policy. Nothing survives into another request or
        # account. Bound the cache even for unusually large edit inputs.
        self.nutrition_cache = OrderedDict()
        self.candidate_sequences = OrderedDict()
        self.ecological_results = OrderedDict()
        self.variant_search_evidence = OrderedDict()
        self.normalized_recipe_rows = OrderedDict()
        self.qualified_nutrition_candidates = OrderedDict()
        self.slot_nutrition_cache = OrderedDict()
        self.clean_recipe_cache = OrderedDict()
        self.recipe_computations = RecipeComputationCache()
        self.queries = {}
        from app.services.planning_diagnostics import PlanningDiagnostics

        self.diagnostics = PlanningDiagnostics()
        from app.services.product_planning_trace import ProductPlanningTrace
        self.product_trace = ProductPlanningTrace(prepared)
        for i, food_class in self.declared_classes.items():
            product = prepared.universe.products[i]
            if row := self.product_trace.products.get((product.store_id, product.product_id)):
                row["indexes"]["declaration"] = [food_class]
        self.diagnostics.product_trace = self.product_trace
        self._resolution_trace = {}
        # Request-constant serialisations/merges used in cache keys, computed
        # once per object instead of per basket row (objects kept alive so an
        # id() is never reused). Values are identical to recomputing them.
        self._json_memo = {}
        self._merged_profile_memo = {}
        self._need_row_templates = OrderedDict()

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

    def _model_json(self, model):
        entry = self._json_memo.get(id(model))
        if entry is None or entry[0] is not model:
            entry = self._json_memo[id(model)] = (model, model.model_dump_json())
        return entry[1]

    def _merged_profile(self, meal):
        entry = self._merged_profile_memo.get(id(meal))
        if entry is None or entry[0] is not meal:
            entry = self._merged_profile_memo[id(meal)] = (meal, merged_profile(self.spec.profile, meal.profile))
        return entry[1]

    def nutrition_evidence(self, product, name, unit, requested, recipe):
        if recipe is not None and recipe.preparation is not None:
            from app.services.recipe_preparation import input_evidence_identity

            # This cache belongs only to this planner's coherent product/fact
            # snapshot and user policy. Reuse source-per-100 evidence across
            # independently validated recipes, never their portion checks,
            # identities, quantities, recipe basis or final basket audit.
            if not self.spec.allow_nutrition_estimates or not requested <= {"protein_g", "fat_g", "carbs_g", "kcal"}:
                return None
            identity = input_evidence_identity(recipe, name, self.recipe_computations)
            if identity is None:
                return None
            recipe_key = ("prepared_input", identity)
        else:
            # Legacy evidence methods can depend on the entire recipe.
            recipe_key = ("legacy", self.recipe_computations.key(recipe))
        key = (
            product.store_id,
            product.product_id,
            name,
            unit,
            frozenset(requested),
            recipe_key,
            self.spec.allow_nutrition_estimates,
            self.request.purchase_planning_mode,
        )
        if key not in self.nutrition_cache:
            result = self._nutrition_evidence(product, name, unit, requested, recipe)
            if len(self.nutrition_cache) >= 32768:
                self.nutrition_cache.popitem(last=False)
            self.nutrition_cache[key] = result
        else:
            self.nutrition_cache.move_to_end(key)
        return self.nutrition_cache[key]

    def _nutrition_evidence(self, product, name, unit, requested, recipe):
        if product.purchase_terms and product.purchase_terms.identity_scope == "campaign_group":
            return None
        fact = self.source_facts(product)
        from app.services.official_product_facts import project_usable_quantity
        product = project_usable_quantity(product, fact, allow_estimates=self.request.purchase_planning_mode == 'estimated', required_unit=unit)
        if fact and fact.source == 'verified_exact_catalog_declaration':
            from app.services.offer_catalog_facts import matches_product

            if not matches_product(product, fact):
                return None
        if fact and fact.source == 'verified_official_product_declaration':
            from app.services.official_product_facts import declaration_matches_product

            if not declaration_matches_product(product, fact):
                return None
        if fact and fact.source == "reviewed_product_declaration":
            from app.services.reviewed_product_nutrition import declaration_matches_product

            if not declaration_matches_product(product, fact):
                return None  # Missing/changed review is not a generic declaration.
        if fact and fact.source == "verified_lidl_supplier_declaration":
            from app.services.lidl_product_facts import declaration_matches_product
            if not declaration_matches_product(product, fact):
                return None
        from app.services.official_product_facts import facts_for_quantity_unit
        fact = facts_for_quantity_unit(product, fact, unit)
        qualified = bool(
            fact
            and not fact.conflicts
            and fact.nutrition_unit == unit
            and fact.nutrition_basis
            and fact.nutrition_preparation == "as_sold"
            and requested <= fact.nutrition.keys()
            and all(math.isfinite(fact.nutrition[k]) and fact.nutrition[k] >= 0 for k in requested)
        )
        if recipe is not None and recipe.preparation is not None:
            from app.services.recipe_preparation import input_evidence
            if not self.spec.allow_nutrition_estimates or not requested <= {"protein_g", "fat_g", "carbs_g", "kcal"}:
                return None
            return input_evidence(recipe, product, name, unit, qualified, fact,
                                  recipe_cache=self.recipe_computations)
        from app.services.reviewed_product_nutrition import is_reviewed_raw_thigh

        if is_reviewed_raw_thigh(fact):
            from app.services.reviewed_warm_meals import thigh_declaration_evidence

            # Declaration is raw input, not cooked food. Even a complete raw
            # declaration cannot qualify a breast recipe or unknown preparation.
            if (not qualified or not self.spec.allow_nutrition_estimates or unit != "g"
                    or canonicalize_ingredient_name(name) != "kyckling"):
                return None
            return thigh_declaration_evidence(recipe, fact)
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

    def resolve_choices(self, name, quantity, unit, *, alternatives=(), **kwargs):
        """Union of explicitly allowed identities, priced by the ordinary basket.

        All alternatives cover the SAME minimum amount and unit. Each identity
        independently passes existing source, purchase and personal-policy gates.
        No cheapest-per-row choice is made here; store/campaign choice remains global.
        """
        if not alternatives:
            return self.resolve(name, quantity, unit, **kwargs)
        candidates, failures = {}, []
        for key in alternatives:
            try:
                for position, candidate in self.resolve(name, quantity, unit, **{**kwargs, "product_key": key}):
                    candidates[position] = candidate
            except PolicyConflict as exc:
                failures.append(exc)
        if not candidates:
            raise PolicyConflict(
                f"{name}: inget av dina produktalternativ kan täcka behovet. "
                + " · ".join(dict.fromkeys(str(exc) for exc in failures)),
                code="DATA_BLOCKED", stage="product_qualification",
            )
        return sorted(candidates.items())

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
        campaign_choice=False,
        purchase_units=False,
        recipe=None,
    ):
        cache_key = (
            name,
            unit,
            product_key,
            tuple(properties),
            self._model_json(profile),
            organic_animals,
            food,
            campaign_choice,
            purchase_units,
            self.recipe_computations.forms_for(recipe, canonicalize_ingredient_name(name))
            if self.complete and recipe and recipe.preparation else None,
        )
        scope = None
        if cache_key not in self.lookup_cache and cache_key not in self.lookup_failures:
            # Same scope and key: the identical result an earlier request computed.
            # The scope is read from the planner's current attributes.
            from app.services.planner_shared_cache import SHARED_RESOLUTION, planner_scope
            scope = planner_scope(self)
            shared = SHARED_RESOLUTION.get(scope, cache_key) if scope is not None else None
            if shared is not None:
                kind, value, observed = shared
                if kind == "failure":
                    if len(self.lookup_failures) >= 1024:
                        expired, _ = self.lookup_failures.popitem(last=False)
                        self._resolution_trace.pop(expired, None)
                    self.lookup_failures[cache_key] = value
                else:
                    self.lookup_cache[cache_key] = value
                self._resolution_trace[cache_key] = observed
        if cache_key in self.lookup_cache or cache_key in self.lookup_failures:
            for i, stage, outcome, reason in self._resolution_trace.get(cache_key, ()):
                self.product_trace.event(self.prepared.universe.products[i], recipe, name, stage, outcome, reason)
            if cache_key in self.lookup_failures:
                # Request-owned: facts, source snapshot, date, memberships and
                # pantry are fixed for this planner. Nothing persists to a new
                # request or crosses owners. Recreate errors; callers annotate
                # stage/diagnostics and must not mutate a cached exception.
                message, code, conflicts, stage = self.lookup_failures[cache_key]
                self.lookup_failures.move_to_end(cache_key)
                raise PolicyConflict(message, code=code, conflicts=list(conflicts), stage=stage)
            return self.lookup_cache[cache_key]
        observed = []

        def note(i, stage, outcome, reason):
            product = self.prepared.universe.products[i]
            if (product.store_id, product.product_id) in self.product_trace.products:
                observed.append((i, stage, outcome, reason))
                self.product_trace.event(product, recipe, name, stage, outcome, reason)

        canonical = canonicalize_ingredient_name(name)
        requirement = NormalizedIngredient(
            canonical_name=canonical, required_quantity=quantity, unit=unit
        )
        if product_key:
            positions = self.index.groups.get(product_key, ())
        else:
            positions = set(self.declared_positions.get(canonical, ()))
            # Reuse the semantic index first, and the existing product search for
            # goods outside the dinner taxonomy (including liver pâté/napkins).
            for candidate in self.view.economic_pool.candidates_by_name.get(canonical, ()):
                position = self.by_identity.get((candidate.store_id, candidate.product_id))
                if position is not None:
                    positions.add(position)
            if self.facts or self.request.purchase_planning_mode == "estimated":
                # Price candidates must not depend on whether nutrition was
                # requested. Weight offers are deliberately absent from the
                # cheap exact pool, but remain in the wider semantic index.
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
            if not positions or properties or self.facts or self.request.purchase_planning_mode == "estimated":
                key = name
                if key not in self.queries:
                    from app.services.meal_prepared_artifacts import ingredient_search_positions
                    self.queries[key] = ingredient_search_positions(
                        self.prepared, name, complete=self.complete)
                positions |= self.queries[key]
        candidates = []
        conflicts = []
        weight_consent_missing = False
        for i in sorted(positions):
            product = self.prepared.universe.products[i]
            if purchase_units:
                if recipe is not None or not product_key or unit != 'st':
                    raise PolicyConflict('Köpförpackningar får endast användas för uttryckligt valda extravaror.')
                from app.services.purchase_quantity_resolver import project_sales_unit
                try:
                    product = project_sales_unit(product)
                except ValueError:
                    continue
            from app.services.official_product_facts import project_usable_quantity
            product = product if purchase_units else project_usable_quantity(product, self.source_facts(product), allow_estimates=self.request.purchase_planning_mode == 'estimated', required_unit=unit)
            if self.complete and recipe is not None:
                from app.services.complete_recipes import (
                    product_form_compatible,
                    project_retained_frozen_form,
                )
                product = project_retained_frozen_form(product, self.source_facts(product))
                if not product_form_compatible(recipe, name, product, self.source_facts(product)):
                    note(i, "recipe_match", "stopped", "authored ingredient input form is incompatible with product")
                    continue
            note(i, "candidate_index", "passed", "retrieved by existing index/search for this ingredient")
            if product.store_id not in self.store_ids:
                note(i, "store_freshness", "stopped", "store/context excluded by request view or explicit allowed stores")
                continue
            weight_terms = product.purchase_terms and product.purchase_terms.usage == 'estimated'
            if product.usable_unit != unit and not (weight_terms and unit == 'g') and not (campaign_choice and unit == 'st'):
                note(i, "quantity_unit", "stopped", f"usable unit {product.usable_unit!r} does not support required {unit}")
                continue
            if campaign_choice and (not product.purchase_terms or product.purchase_terms.usage != 'variant_selection_required'):
                continue
            if campaign_choice and (profile.allergies or profile.exclusions or organic_animals):
                conflicts.append(PolicyConflict('Kampanjens öppna varianter kan inte styrka allergi-, uteslutnings- eller ekokrav.', code='DATA_BLOCKED'))
                continue
            if not properties_match(product, properties):
                note(i, "variant_properties", "stopped", "requested product properties not established")
                continue
            if not food and not is_nonfood(product.name):
                conflicts.append(
                    PolicyConflict(f"{product.name} kan inte klassas som icke-livsmedel.")
                )
                continue
            if product.product_role == "non_human_food":
                note(i, "recipe_match", "stopped", "non-human food")
                continue
            from app.services.reviewed_cold_meals import plain_quark

            reviewed_quark = canonical == "kvarg" and plain_quark(
                product, self.source_facts(product)
            )
            from app.services.recipe_ingredient_references import reviewed_reference

            reviewed_apple = canonical == 'äpple' and reviewed_reference(
                product, canonical, self.source_facts(product)) == 588
            if canonical == "kvarg" and not product_key and not reviewed_quark:
                note(i, "recipe_match", "stopped", "plain quark identity/composition not established")
                continue
            try:
                check_product(
                    product, profile, self.source_facts(product), organic_animals=organic_animals
                )
            except PolicyConflict as exc:
                if exc.stage is None:
                    exc.stage = "policy_taste"
                conflicts.append(exc)
                note(i, "policy", "stopped", str(exc))
                continue
            if (reviewed_quark or reviewed_apple) and not product_key:
                candidate = ProductCandidate.from_product(product, 1).model_copy(
                    update={
                        "semantic_confidence": "high",
                        "semantic_evidence": [
                            "reviewed plain quark name/form and retained dairy ingredients"
                            if reviewed_quark else "reviewed complete fresh apple label and produce category"
                        ],
                        "canonical_food": "kvarg" if reviewed_quark else "apple",
                        "food_family": "dairy" if reviewed_quark else "fruit",
                        "product_role": "quark" if reviewed_quark else "whole_fruit",
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
                semantic_product = product
                if self.declared_classes.get(i) == canonical:
                    from app.services.declaration_semantics import project_declared_class
                    semantic_product = project_declared_class(product, self.declared_classes[i])
                matched = self.service.matcher.match(
                    requirement, [semantic_product], store_ids=list(self.store_ids)
                )
                if matched:
                    candidate = matched[0]
                    if semantic_product is not product:
                        candidate = candidate.model_copy(update={"semantic_evidence": [*candidate.semantic_evidence,
                                "exact variant-bound supplier food classification: " + self.declared_classes[i]]})
                elif properties or canonical not in self.view.economic_pool.candidates_by_name:
                    # For out-of-taxonomy generic goods all query terms must be
                    # present; the user confirms the resulting query properties.
                    from app.services.product_search import search_text
                    from app.services.product_semantics import (
                        evaluate_product_semantics,
                        has_semantic_rule,
                    )

                    # Index absence is not permission to undo a shared food-
                    # identity rejection. Lexical fallback may still support
                    # out-of-taxonomy goods or a separately qualified purchase
                    # form, but cannot turn pickles/crackers into raw food.
                    if has_semantic_rule(canonical) and not evaluate_product_semantics(canonical, semantic_product).compatible:
                        note(i, "recipe_match", "stopped", "shared identity/form rejection cannot be overridden by lexical fallback")
                        continue

                    # A stale source classification must not pre-empt the shared
                    # semantic matcher. Lexical fallback, however, cannot promote
                    # a low-confidence product into a meal ingredient.
                    if self.facts and product.semantic_confidence not in {"high", "exact"}:
                        note(i, "recipe_match", "stopped", "shared semantic matcher rejected; source confidence cannot support lexical fallback")
                        continue
                    tokens = set(search_text(name).split())
                    if not tokens <= set(search_text(product.name).split()):
                        note(i, "recipe_match", "stopped", "neither semantic match nor complete requested query")
                        continue
                    candidate = ProductCandidate.from_product(product, 1).model_copy(
                        update={
                            "semantic_confidence": "high",
                            "semantic_evidence": ["confirmed generic query and properties"],
                        }
                    )
                else:
                    note(i, "recipe_match", "stopped", "matcher rejected ingredient/product role or form")
                    continue
            note(i, "recipe_match", "passed", "existing matcher or explicit identity passed")
            try:
                candidate = price_candidate_for_context(candidate, self.user, on_date=self.pricing_date,
                    planning_mode=self.request.purchase_planning_mode, allow_campaign_choice=campaign_choice)
            except ValueError as exc:
                from app.services.user_pricing import EstimatedPurchaseRequired
                weight_consent_missing |= isinstance(exc, EstimatedPurchaseRequired)
                note(i, "price_contract", "stopped", str(exc))
                if product.price is not None and product.sale_model not in {'sold_by_weight', 'variable_weight_package'}:
                    raise
                # A weight-dependent option is unavailable in exact mode; it
                # must not discard other exact candidates for the ingredient.
                # An optional offer with no eligible contract on the purchase
                # day supplies no price. Other verified products still qualify.
                continue
            note(i, "price_contract", "passed", "request membership, date, source scope and purchase mode accepted")
            candidates.append((i, candidate))
        self._resolution_trace[cache_key] = observed
        if not candidates:
            failure = conflicts[0] if conflicts else PolicyConflict(
                (f"{name} finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande."
                 if weight_consent_missing else
                 f"Ingen verifierad köpbar vara för {name}, {unit}. Kontrollera mängden, egenskaperna eller exakt produkt."),
                code="DATA_BLOCKED",
            )
            if failure.diagnostics is None:
                if len(self.lookup_failures) >= 1024:
                    expired, _ = self.lookup_failures.popitem(last=False)
                    self._resolution_trace.pop(expired, None)
                self.lookup_failures[cache_key] = (str(failure), failure.code,
                    tuple(failure.conflicts), failure.stage)
                self._share_resolution(scope, cache_key, "failure", self.lookup_failures[cache_key], observed)
            raise failure
        self.lookup_cache[cache_key] = candidates
        self._share_resolution(scope, cache_key, "candidates", candidates, observed)
        return candidates

    @staticmethod
    def _share_resolution(scope, cache_key, kind, value, observed):
        if scope is not None:
            from app.services.planner_shared_cache import SHARED_RESOLUTION
            SHARED_RESOLUTION.put(scope, cache_key, (kind, value, tuple(observed)))

    def clean_recipe(self, recipe, meal):
        # Request-local only. Source facts, stock and store view do not change
        # during this planner. Full recipe content includes preparation version,
        # units and quantities; meal policy and pricing opt-ins remain distinct.
        cache_key = (self.recipe_computations.key(recipe), self._model_json(meal),
                     self._model_json(self.spec.profile), self.spec.organic_animals,
                     tuple(self.request.avoid_ingredients), self.request.purchase_planning_mode,
                     self.user.cache_identity,
                     self._model_json(self.request.recipe_preferences) if self.request.recipe_preferences else None)
        if cache_key in self.clean_recipe_cache:
            self.clean_recipe_cache.move_to_end(cache_key)
            return self.clean_recipe_cache[cache_key]
        if self.complete and (meal.meal_type == "dinner" or meal.recipe_choices is not None):
            from app.services.recipe_library import matches_meal
            if not matches_meal(recipe, meal, self.request.recipe_preferences):
                raise PolicyConflict("Receptet uppfyller inte val av matkök, ingrediensantal, tid eller anpassning. Välj ett kvalificerat alternativ.", code="RECIPE_CHOICES_CONFLICT")
        if (self.complete and recipe.design is not None
                and all(i.canonical_name == canonicalize_ingredient_name(i.name) for i in recipe.ingredients)):
            from app.services.recipe_library import share_issued_recipe_parts

            # Compare every value with the validated issued registry before
            # sharing its frozen ingredients/design. Dumping and parsing this
            # exact tree again cannot add evidence. Mutable recipe lists and
            # preparation forms are still copied by the registry helper.
            recipe = share_issued_recipe_parts(recipe)
        else:
            # Unregistered inputs still derive their canonical identities from
            # visible ingredients and pass through ordinary model validation.
            recipe = Recipe.model_validate(
                {
                    **recipe.model_dump(),
                    "ingredients": [
                        {**i.model_dump(), "canonical_name": canonicalize_ingredient_name(i.name)}
                        for i in recipe.ingredients
                    ],
                }
            )
            if self.complete:
                from app.services.recipe_library import share_issued_recipe_parts

                recipe = share_issued_recipe_parts(recipe)
        profile = self._merged_profile(meal)
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
                recipe=recipe,
            )
        remember_bounded(self.clean_recipe_cache, cache_key, recipe, 512)
        return recipe

    def _recipe_id(self, recipe):
        return self.recipe_computations.get(recipe, recipe_id)

    def _protein_category(self, recipe):
        return self.recipe_computations.get(recipe, protein_category)

    def _need_rows(self, slots):
        rows = []
        for slot in slots:
            if slot.recipe is None:
                continue
            meal = self.meals[slot.meal_type]
            recipe = self.clean_recipe(slot.recipe, meal)
            # The rows of one cleaned recipe in one slot are identical in every
            # basket. Build them (and their demand keys) once; each basket gets
            # fresh shallow copies, since it adds per-basket fields to its rows.
            template_key = (slot.id, id(meal), self.recipe_computations.key(recipe))
            template = self._need_row_templates.get(template_key)
            if template is None or template[0] is not meal:
                profile = self._merged_profile(meal)
                normalized_key = (self.service.normalizer, self.recipe_computations.key(recipe))
                if normalized_key not in self.normalized_recipe_rows:
                    sources = {}
                    for source in recipe.ingredients:
                        sources.setdefault(canonicalize_ingredient_name(source.name), source)
                    normalized = self.service.normalizer.normalize_and_aggregate([recipe])
                    remember_bounded(self.normalized_recipe_rows, normalized_key, tuple(
                        (ingredient, sources.get(ingredient.canonical_name)) for ingredient in normalized), 512)
                else:
                    self.normalized_recipe_rows.move_to_end(normalized_key)
                built = []
                for ingredient, source_ingredient in self.normalized_recipe_rows[normalized_key]:
                    row = {
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
                        **({"input_form": source_ingredient.form,
                            "product_requirements": list(getattr(source_ingredient, "product_requirements", None) or ())}
                           if self.complete and source_ingredient is not None else {}),
                    }
                    row["demand_key"] = demand_key(row)
                    built.append(row)
                template = (meal, tuple(built))
                remember_bounded(self._need_row_templates, template_key, template, 4096)
            else:
                self._need_row_templates.move_to_end(template_key)
            rows.extend({**row, "properties": list(row["properties"]),
                         **({"product_requirements": list(row["product_requirements"])}
                            if "product_requirements" in row else {})}
                        for row in template[1])
        for extra in self.spec.extras:
            # An either/or row's title is a display label. Its individual exact
            # identities may legitimately differ (e.g. fat percentage). Explicit
            # shared properties still bind every candidate in resolve_choices.
            expected = [] if extra.kind == "one_of" else interpretation(extra.query)
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
                    "alternatives": extra.alternatives,
                    "campaign_choice": extra.kind == "campaign",
                    "purchase_units": extra.purchase_units,
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
            if "demand_key" not in row:  # recipe rows carry it from their template
                row["demand_key"] = demand_key(row)
            row["original_quantity"] = row["quantity"]
            row["quantity"] = max(0, row["quantity"] - consumed[row["demand_key"]])
        return rows

    def _allocate(self, row, resolved, available):
        remaining = row["quantity"]
        allocations = []
        if row.get("purchase_units"):
            return remaining, allocations
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
                if self.complete and row.get("input_form"):
                    from app.services.complete_recipes import pantry_form_compatible
                    if not pantry_form_compatible(item, row):
                        continue
                if row["product_key"] or row.get("alternatives") or row["properties"]:
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

    def basket(self, slots, *, final=True, _retained=None):
        # A narrower search incumbent is a concrete purchase, not merely a
        # recipe seed. Requalify its exact products and private allocation while
        # retaining its package/offer checkout; never send it through a new
        # product search that could lose the already validated lower amount.
        retained_items = ({i.ingredient: i for s in _retained.optimized_basket.stores for i in s.items}
                          if _retained is not None else {})
        retained_needs = ({d: need for need in _retained.personal.needs for d in need["demand_keys"]}
                          if _retained is not None else {})
        available = {i["id"]: i["available"] for i in self.items}
        recipes_by_slot = {slot.id: slot.recipe for slot in slots}
        meals_by_slot = {slot.id: self.meals[slot.meal_type] for slot in slots}
        rows = self._need_rows(slots)
        allocations, groups = [], []
        missing_nutrition = set()
        nutrition_needs = set()
        # Constrained explicit rows first: a compatible recipe can share their
        # packages, but two different exact variants never become interchangeable.
        rows.sort(key=lambda r: (not bool(r["product_key"] or r.get("alternatives")), not bool(r["properties"])))
        for row in rows:
            if row["quantity"] <= 0:
                continue
            recipe = recipes_by_slot.get(row["source"])
            resolved = self.resolve_choices(
                row["name"],
                row["quantity"],
                row["unit"],
                product_key=row["product_key"],
                alternatives=row.get("alternatives", ()),
                properties=row["properties"],
                profile=row["profile"],
                organic_animals=row["organic_animals"],
                food=row["food"],
                campaign_choice=row.get("campaign_choice", False),
                purchase_units=row.get("purchase_units", False),
                recipe=recipe,
            )
            meal = meals_by_slot.get(row["source"])
            requested = requested_nutrients(meal.limits) if meal else set()
            row["nutrients"] = sorted(requested)
            if requested:
                nutrition_needs.add(row["name"])
                qualification_key = (id(resolved), self.recipe_computations.key(recipe), row["name"],
                                     row["unit"], frozenset(requested))
                cached_qualification = self.qualified_nutrition_candidates.get(qualification_key)
                if cached_qualification is not None and cached_qualification[0] is resolved:
                    self.qualified_nutrition_candidates.move_to_end(qualification_key)
                    verified = cached_qualification[1]
                else:
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
                    remember_bounded(self.qualified_nutrition_candidates, qualification_key,
                                     (resolved, verified), 4096)
                verified_ids = {i for i, _ in verified}
                for i, _ in resolved:
                    product = self.prepared.universe.products[i]
                    if (product.store_id, product.product_id) not in self.product_trace.products:
                        continue
                    fact = self.source_facts(product)
                    self.product_trace.event(product, recipe, row["name"], "nutrition",
                        "passed" if i in verified_ids else "stopped",
                        "applicable declaration/reference for used recipe amount" if i in verified_ids else
                        "no qualified nutrition for requested unit/preparation/fields",
                        required_unit=row["unit"], requested_fields=sorted(requested),
                        declaration_source=fact.source if fact else None,
                        declaration_unit=fact.nutrition_unit if fact else None,
                        available_fields=sorted(fact.nutrition) if fact else [],
                        conflicts=list(fact.conflicts) if fact else [])
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
            if _retained is None:
                quantity, allocation = self._allocate(row, resolved, available)
            else:
                expected = [a for a in _retained.personal.allocations if a["demand_key"] == row["demand_key"]]
                allocation_budget = {key: 0 for key in available}
                for allocation in expected:
                    key, amount = allocation["item_id"], allocation["quantity"]
                    if key not in available or amount > available[key] + 1e-8:
                        raise PolicyConflict("Tidigare skafferifördelning är inte längre tillgänglig.")
                    allocation_budget[key] += amount
                quantity, allocation = self._allocate(row, resolved, allocation_budget)
                if allocation != expected:
                    raise PolicyConflict("Tidigare skafferifördelning uppfyller inte målbegäran.")
                for used in allocation:
                    available[used["item_id"]] -= used["quantity"]
            allocations.extend(allocation)
            if quantity <= 0:
                continue
            if _retained is not None:
                previous = retained_needs.get(row["demand_key"])
                item = retained_items.get(previous["key"]) if previous else None
                resolved = [(i, c) for i, c in resolved if item is not None
                            and (c.store_id, c.product_id) == (item.store_id, item.product_id)
                            and c.source_provenance == item.source_provenance]
                if not resolved or item.purchase_date != self.pricing_date:
                    raise PolicyConflict("Tidigare produkt och prisunderlag uppfyller inte målbegäran.")
            identities = {i for i, _ in resolved}
            group = next(
                (
                    g
                    for g in groups
                    if g["unit"] == row["unit"]
                    and g.get("purchase_units", False) == row.get("purchase_units", False)
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
                        **({"purchase_units": True} if row.get("purchase_units") else {}),
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
            if _retained is not None:
                original = retained_needs[group["demand_keys"][0]]
                if set(original["demand_keys"]) != set(group["demand_keys"]):
                    raise PolicyConflict("Tidigare gemensamma ingrediensbehov kunde inte återskapas.")
                key = original["key"]
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
            # These frozen, request-owned candidates are never edited. Retain
            # the exact ordered objects so the shared engine's immutable quote
            # set cache can reuse identical subproblems across weekly baskets.
            # Holding the tuple prevents ID reuse; nothing crosses requests.
            sequence_key = tuple(id(candidate) for candidate in candidates)
            if sequence_key not in self.candidate_sequences:
                remember_bounded(self.candidate_sequences, sequence_key, tuple(candidates), 4096)
            else:
                self.candidate_sequences.move_to_end(sequence_key)
            candidate_map[key] = self.candidate_sequences[sequence_key]
            group_rows = [row for row in rows if row["demand_key"] in group["demand_keys"]]
            for c in candidates:
                if (c.store_id, c.product_id) not in self.product_trace.products:
                    continue
                product = self.prepared.universe.products[self.by_identity[(c.store_id, c.product_id)]]
                for row in group_rows:
                    recipe = recipes_by_slot.get(row["source"])
                    self.product_trace.event(product, recipe, row["name"], "basket_candidates", "passed",
                        "qualified candidate passed to whole-basket optimizer")
            ingredients.append(
                NormalizedIngredient(
                    canonical_name=key,
                    required_quantity=group["quantity"],
                    unit=group["unit"],
                    source_recipes=group["sources"],
                )
            )
        # Rule out an impossible singleton before any whole-basket search.
        # Full menus usually pass their initial basket; build their nutrient
        # search model lazily only when that verified baseline fails.
        nutrition_bounds = None
        if len(slots) == 1:
            nutrition_bounds = self._nutrition_search_bounds(slots, candidate_map, rows, allocations)
            self._reject_nutrition_bounds(slots, nutrition_bounds)
        with self.optimizer.quote_cache(reuse_existing=True):
            try:
                package_started = perf_counter()
                with performance_span("personal_package_calculation"):
                    if _retained is None:
                        basket = self.optimizer.optimize(
                            ingredients, candidate_map, self.view.stores, max_stores=self.request.max_stores
                        )
                    else:
                        basket = _retained.optimized_basket.model_copy(deep=True, update={"max_stores": self.request.max_stores})
                        if basket.store_count > self.request.max_stores:
                            raise PolicyConflict("Tidigare inköp överskrider målbegärans butikstak.")
                self.timings["package_calculation"] += perf_counter() - package_started
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
            if _retained is not None and self._eco_percent(basket, groups) + 1e-8 < self.spec.organic_percent:
                raise PolicyConflict("Tidigare inköp uppfyller inte målbegärans ekokrav.")
            if _retained is None and self.spec.surplus_mode == "allow_larger":
                basket = self._larger_packages(basket, ingredients, candidate_map)
            if _retained is None and self.spec.organic_percent:
                try:
                    basket = self._ecological_basket(ingredients, candidate_map, groups, basket)
                except PolicyConflict as exc:
                    exc.stage = "organic"
                    if final:
                        raise
                    # A later meal can still raise the global cost share. Do not
                    # declare a partial menu infeasible, but price qualified
                    # alternatives before beam pruning whenever available.
            if _retained is None and any(self.meals[s.meal_type].limits.active for s in slots if s.recipe):
                basket = self._qualified_nutrition_basket(
                    slots,
                    basket,
                    ingredients,
                    candidate_map,
                    groups,
                    rows,
                    allocations,
                    final=final,
                    nutrition_bounds=nutrition_bounds,
                )
        # Every complete menu (final=True) and every retained incumbent is
        # audited exactly as before. Partial beam prefixes (final=False) are
        # intermediate search states: their result is never returned, saved or
        # shown, and the chosen menu is recomputed with final=True before
        # acceptance. Skipping their audit therefore keeps the gate on every
        # deliverable basket while removing about two thirds of audit calls.
        audit = None
        if (final and not getattr(self, "_defer_search_audit", False)) or _retained is not None:
            audit_started = perf_counter()
            with performance_span("personal_audit"):
                audit = self.auditor.audit(
                    ingredients,
                    basket,
                    user_pricing_context=self.user,
                    strategic_extras_allowed=self.spec.surplus_mode == "allow_larger",
                )
            self.timings["audit"] += perf_counter() - audit_started
            if not audit.passed:
                raise PolicyConflict(_AUDIT_FAILURE)
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
            "trace_inputs": (candidate_map, rows),
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

    def _trace_final_alternatives(self, slots, result):
        """Compare bounded real alternatives, without changing the chosen plan.

        A non-selected item alone is never labelled expensive. These are
        explicitly final-menu counterfactuals, not claims of exhaustive search.
        Every comparison uses whole checkout, store cap, nutrition and audit.
        """
        from app.services.basket_optimizer import _VERIFICATION_RANK
        from app.services.product_planning_trace import recipe_identity

        candidates, rows = result["trace_inputs"]
        baseline = result["basket"]
        selected = {(i.store_id, i.product_id) for s in baseline.stores for i in s.items}
        alternatives = [(key, c) for key, cs in candidates.items() for c in cs
                        if (c.store_id, c.product_id) in self.product_trace.products
                        and (c.store_id, c.product_id) not in selected]
        alternatives.sort(key=lambda item: (
            not bool(item[1].purchase_terms and item[1].purchase_terms.usage == "estimated"),
            item[0], item[1].store_id, item[1].product_id))
        for key, candidate in alternatives[:24]:
            record = {
                "kind": "bounded_final_menu_counterfactual", "ingredient": key,
                "product_id": candidate.product_id, "store_id": candidate.store_id,
                "recipes": [recipe_identity(s.recipe) for s in slots if s.recipe],
                "baseline_total": baseline.total,
                "baseline_status": baseline.verification_status,
                "baseline_stores": [s.store_id for s in baseline.stores],
            }
            try:
                option = self.optimizer.optimize(result["ingredients"], {**candidates, key: [candidate]},
                    self.view.stores, max_stores=self.request.max_stores, calculate_savings=False)
                restricted = {**candidates, key: [candidate]}
                if any(self.meals[s.meal_type].limits.active for s in slots if s.recipe):
                    option = self._qualified_nutrition_basket(
                        slots, option, result["ingredients"], restricted, result["groups"], rows,
                        result["allocations"], final=True)
                self._check_final(slots, option, result["groups"], rows, result["allocations"])
                audit = self.auditor.audit(result["ingredients"], option, user_pricing_context=self.user,
                    strategic_extras_allowed=self.spec.surplus_mode == "allow_larger")
                if not audit.passed:
                    raise PolicyConflict("Counterfactual checkout audit failed", stage="checkout_audit")
                base_rank = _VERIFICATION_RANK[baseline.verification_status]
                option_rank = _VERIFICATION_RANK[option.verification_status]
                verdict = ("quality_priority" if option_rank > base_rank else
                           "higher_whole_basket_cost" if option.total > baseline.total + .005 else
                           "equal_whole_basket_cost" if abs(option.total-baseline.total) <= .005 else
                           "lower_cost_alternative_not_selected")
                record.update(outcome=verdict, alternative_total=option.total,
                    alternative_status=option.verification_status,
                    alternative_stores=[s.store_id for s in option.stores],
                    audit_passed=True,
                    checkout=[i.model_dump(mode="json") for s in option.stores for i in s.items
                              if (i.store_id, i.product_id) == (candidate.store_id, candidate.product_id)])
            except (PolicyConflict, IncompleteBasketError, ValueError) as exc:
                record.update(outcome="blocked_counterfactual", stage=getattr(exc, "stage", None), reason=str(exc))
            self.product_trace.comparisons.append(record)
        if len(alternatives) > 24:
            self.product_trace.comparisons.append({"kind": "comparison_limit", "not_compared": len(alternatives)-24})

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

    def _nutrition_search_bounds(self, slots, candidates, rows, allocations):
        from app.services.nutrition_search_bounds import build_nutrition_bounds

        def evidence(candidate, need, slot, requested):
            product = self.prepared.universe.products[
                self.by_identity[(candidate.store_id, candidate.product_id)]
            ]
            return self.nutrition_evidence(product, need["name"], need["unit"], requested, slot.recipe)

        return build_nutrition_bounds(
            slots, rows, candidates, allocations,
            meal_limits=lambda slot: self.meals[slot.meal_type].limits, evidence=evidence,
        )

    def _reject_nutrition_bounds(self, slots, bounds):
        if bounds is None or not (violations := bounds.violations()):
            return
        from app.services.product_planning_trace import recipe_identity

        if len(self.diagnostics.nutrition_searches) < 2048:
            self.diagnostics.nutrition_searches.append({
                "recipes": [recipe_identity(s.recipe) for s in slots if s.recipe],
                "limit": self.nutrition_search_limit, "evaluated": 0,
                "remaining_frontier": 0, "budget_exhausted": False,
                "numeric_passed": 0, "nutrition_rejections": 0,
                "purchase_or_other_rejections": 0, "qualifying_basket_found": False,
                "best_total": None, "proven_bounds": violations,
                "candidate_counts": {k: len(v) for k, v in bounds.contributions.items()},
                "scope": "qualified current candidate domains, independent optimistic nutrient bounds; not all foods or a purchasable basket",
            })
        else:
            self.diagnostics.omitted_nutrition_searches += 1
        first = violations[0]
        raise PolicyConflict(
            f"{first['recipe']}: {first['nutrient']} ligger inom "
            f"[{first['lower']:.12g}, {first['upper']:.12g}] per portion även med "
            f"oberoende optimistiska val ur det kvalificerade kandidatunderlaget; "
            f"{first['direction']} {first['limit']:g} kan inte nås inom detta underlag. "
            "Detta är en beräknad gräns, inte ett uppnått köp eller en slutsats om andra produkter.",
            code="NUTRITION_TARGET_NOT_MET", stage="nutrition_bound",
        )

    def _qualified_nutrition_basket(
        self, slots, baseline, ingredients, candidates, groups, rows, allocations, *, final,
        nutrition_bounds=None,
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
        if nutrition_bounds is None:
            nutrition_bounds = self._nutrition_search_bounds(slots, candidates, rows, allocations)
            self._reject_nutrition_bounds(slots, nutrition_bounds)
        import heapq

        keys = [
            k
            for k in candidates
            if any(r.get("purchase_key") == k and r.get("nutrients") for r in rows)
        ]
        choices = []
        extrema = defaultdict(list)
        nutrient_values = {}
        requested = set().union(
            *(requested_nutrients(self.meals[s.meal_type].limits) for s in slots)
        )
        if not requested:
            raise conflict
        recipe_by_slot = {s.id: s.recipe for s in slots}
        for key in keys:
            key_needs = [r for r in rows if r.get("purchase_key") == key and r.get("nutrients")]
            qualified_values = {}
            for candidate in candidates[key]:
                product = self.prepared.universe.products[
                    self.by_identity[(candidate.store_id, candidate.product_id)]
                ]
                qualified_values[(candidate.store_id, candidate.product_id)] = [
                    self.nutrition_evidence(product, need["name"], need["unit"],
                                            set(need["nutrients"]), recipe_by_slot[need["source"]])
                    for need in key_needs
                ]
            current = next(
                i for store in baseline.stores for i in store.items if i.ingredient == key
            )
            # Rank alternatives by the actual checkout for the week's pooled
            # requirement. Unit price and one-package price can both rank a
            # small requirement incorrectly after whole-package rounding.
            requirement = next(i for i in ingredients if i.canonical_name == key)
            checkout_totals = {
                (q.store_id, q.product_id): q.total_price
                for q in self.optimizer._candidate_quotes(requirement, candidates[key])
            }
            ordered = sorted(
                candidates[key],
                key=lambda c: (
                    c.product_id != current.product_id or c.store_id != current.store_id,
                    checkout_totals.get((c.store_id, c.product_id), Decimal("Infinity")),
                    c.product_id,
                ),
            )
            # Retain nutritional extrema before the bounded combination search,
            # plus cheapest and verified organic alternatives. Unknown is absent.
            important = ordered[:1]
            for nutrient in sorted(requested):

                def effective_value(candidate, nutrient=nutrient, qualified_values=qualified_values, key_needs=key_needs):
                    evidence_rows = qualified_values[(candidate.store_id, candidate.product_id)]
                    values = [e.nutrition[nutrient]
                              for need, e in zip(key_needs, evidence_rows, strict=True)
                              if nutrient in need["nutrients"] and e and nutrient in e.nutrition]
                    return min(values) if values else None

                values = {(c.store_id, c.product_id): effective_value(c) for c in ordered}
                nutrient_values[(key, nutrient)] = values
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
                evidence_rows = qualified_values[(candidate.store_id, candidate.product_id)]
                for need, evidence in zip(key_needs, evidence_rows, strict=True):
                    signature.append(tuple((n, evidence.nutrition[n]) for n in need["nutrients"]))
                equivalent.setdefault(tuple(signature), []).append(candidate)
            # The bounded search is over distinct nutritional choices. Keep ALL
            # exact products, package sizes and stores within each choice for the
            # existing pricing engine; equal macros do not mean equal products.
            choices.append(list(equivalent.values()))
        # Global extrema may require more shops than this request permits. A
        # bounded walk near the cheapest products can then miss an otherwise
        # valid menu even though each ingredient has a suitable alternative.
        # Seed the SAME search with extrema within feasible store subsets. All
        # exact package/offer costs and hard constraints are still checked by
        # the existing basket optimizer; the 256-evaluation budget is unchanged.
        store_ids = sorted({c.store_id for key in keys for c in candidates[key]})
        subset_count = 0
        for size in range(1, min(self.request.max_stores, len(store_ids)) + 1):
            for stores in combinations(store_ids, size):
                subset_count += 1
                if subset_count > 64:
                    break
                restricted = [[c for c in candidates[key] if c.store_id in stores] for key in keys]
                if not all(restricted):
                    continue
                for nutrient in sorted(requested):
                    for direction in ("min", "max"):
                        selected = []
                        for key, rows_for_key in zip(keys, restricted, strict=True):
                            values = nutrient_values[(key, nutrient)]
                            known = [c for c in rows_for_key if values[(c.store_id, c.product_id)] is not None]
                            if not known:
                                break
                            selector = min if direction == "min" else max
                            selected.append(selector(known, key=lambda c: values[(c.store_id, c.product_id)]))
                        if len(selected) == len(keys):
                            extrema[(nutrient, direction, stores)] = selected
            if subset_count > 64:
                break
        searched = 0
        best = None
        rejected_nutrition = rejected_purchase = passed_nutrition = 0
        bound_pruned = 0
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
        violates_bounds = nutrition_bounds.compile_choices(keys, choices) if nutrition_bounds else None
        # Exact-safe cost pruning: a combination whose optimistic checkout
        # (authoritative line quotes, no store cap) is not below the best exact
        # basket cannot replace it (only a strictly lower total wins). The
        # visited combinations, budget and nutrition checks are unchanged; only
        # the pricing of hopeless combinations is skipped. Disabled with
        # coupled multi-line offers, like the ecological bound.
        allowed_ids = [s.store_id for s in self.view.stores]
        line_bounds = self.optimizer.restriction_cost_bounds(
            ingredients, candidates, candidates, allowed_store_ids=allowed_ids)
        requirement_by_key = {i.canonical_name: i for i in ingredients}
        class_bounds = {}

        def class_bound(dimension, index):
            if (dimension, index) not in class_bounds:
                key = keys[dimension]
                relaxed = self.optimizer.optimistic_relaxed_key(
                    [requirement_by_key[key]], {key: choices[dimension][index]}, allowed_store_ids=allowed_ids)
                class_bounds[(dimension, index)] = relaxed[1] if relaxed else None
            return class_bounds[(dimension, index)]

        key_set = set(keys)
        fixed_bound = (None if line_bounds is None or any(k not in line_bounds for k in keys) else
                       sum((pair[0] for k, pair in line_bounds.items() if k not in key_set), Decimal(0)))

        def optimistic_total(indices):
            if fixed_bound is None:
                return None
            total = fixed_bound
            for dimension, index in enumerate(indices):
                bound = class_bound(dimension, index)
                if bound is None:
                    return None
                total += bound
            return total

        cost_pruned = 0
        while queue and searched < self.nutrition_search_limit:
            _, indices = heapq.heappop(queue)
            for dimension, index in enumerate(indices):
                if index + 1 < len(choices[dimension]):
                    neighbor = indices[:dimension] + (index + 1,) + indices[dimension + 1:]
                    if neighbor not in seen:
                        seen.add(neighbor)
                        heapq.heappush(queue, (sum(neighbor), neighbor))
            combination = [choices[n][i] for n, i in enumerate(indices)]
            searched += 1
            narrowed = {**candidates, **dict(zip(keys, combination, strict=True))}
            if violates_bounds is not None and violates_bounds(indices):
                # All products within each class have equal requested values.
                # This only rejects; survivors still use the original calculator.
                bound_pruned += 1
                rejected_nutrition += 1
                continue
            try:
                selected = {i.ingredient: i for store in baseline.stores for i in store.items}
                selected.update(
                    {key: group[0] for key, group in zip(keys, combination, strict=True)}
                )
                # Same nutrition calculator, before pricing. Every product in a
                # class has the same requested per-recipe values; no provisional
                # prices or package surplus enter this qualification.
                self._check_nutrition(slots, selected, rows, allocations)
                passed_nutrition += 1
                if best is not None:
                    lower = optimistic_total(indices)
                    if lower is not None and lower >= money(best.total):
                        cost_pruned += 1
                        continue
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
            except (PolicyConflict, IncompleteBasketError) as exc:
                if isinstance(exc, PolicyConflict) and exc.code == "NUTRITION_TARGET_NOT_MET":
                    rejected_nutrition += 1
                else:
                    rejected_purchase += 1
                continue
        if len(self.diagnostics.nutrition_searches) < 2048:
            from app.services.product_planning_trace import recipe_identity
            self.diagnostics.nutrition_searches.append({
                "recipes": [recipe_identity(s.recipe) for s in slots if s.recipe],
                "limit": self.nutrition_search_limit, "evaluated": searched,
                "remaining_frontier": len(queue), "budget_exhausted": bool(queue),
                "class_counts": [len(c) for c in choices],
                "numeric_passed": passed_nutrition, "nutrition_rejections": rejected_nutrition,
                "linear_bound_rejections": bound_pruned, "cost_bound_skips": cost_pruned,
                "purchase_or_other_rejections": rejected_purchase,
                "qualifying_basket_found": best is not None,
                "best_total": best.total if best else None,
                "scope": "retained nutrition classes and price candidates; not global optimality"})
        else:
            self.diagnostics.omitted_nutrition_searches += 1
        if best is None:
            raise PolicyConflict(
                f"Ingen komplett kombination hittades i näringssökningen ({searched} kombinationer; {'sökbudget nådd' if queue else 'prövade näringsklasser uttömda'}). Exempel på beräknat näringsavslag: {conflict} Kraven är oförändrade; sökningen bevisar inte omöjlighet.",
                code="NUTRITION_TARGET_NOT_MET",
                stage="nutrition",
            )
        return best

    @timed_stage("ecological_search")
    def _ecological_basket(self, ingredients, candidates, groups, baseline):
        from app.services.basket_calculator import BasketCalculator
        from app.services.performance_trace import increment_performance_counter

        percent = self._eco_percent(baseline, groups)
        if percent is None and any(g["food"] for g in groups):
            raise PolicyConflict(
                "Matinköpets nettokostnad är noll. Den valda ekologiska kostnadsandelen kan därför inte beräknas. Ändra kravet uttryckligen i Mina val eller välj andra varor.",
                code="DATA_BLOCKED",
            )
        if percent is None or percent + 1e-8 >= self.spec.organic_percent:
            return baseline
        # Cache only within this planner, after pantry allocation and product
        # qualification. Snapshot mutable offers and organic declarations on
        # every call; identity alone cannot approve a hit. Ordered rows retain
        # the bounded search's original first-tie/subset behaviour.
        cache_key = None
        if type(self.optimizer) is BasketOptimizer and type(self.optimizer.calculator) is BasketCalculator:
            cache_key = (
                self.spec.organic_percent, self.request.max_stores, self.optimizer.verification_policy,
                tuple((s.store_id, s.name) for s in self.view.stores),
                tuple((i.canonical_name, i.required_quantity, i.unit) for i in ingredients),
                tuple((g["key"], g["food"]) for g in groups),
                tuple((name, tuple((c.model_dump_json(),
                    bool((f := self.source_facts(self.prepared.universe.products[
                        self.by_identity[(c.store_id, c.product_id)]])) and f.organic is True))
                    for c in values)) for name, values in candidates.items()),
            )
            if cache_key in self.ecological_results:
                self.ecological_results.move_to_end(cache_key)
                increment_performance_counter("ecological_result_cache_hits")
                return self.ecological_results[cache_key].model_copy(deep=True)
        organic_candidates = {}
        for name, values in candidates.items():
            organic = tuple(
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
            )
            # The same immutable qualified subset recurs in up to 256 baskets
            # and many meal combinations. Reuse the optimizer's existing exact
            # quote/vector cache, with no pruning or reduced search budget.
            sequence_key = tuple(id(candidate) for candidate in organic)
            if sequence_key not in self.candidate_sequences:
                remember_bounded(self.candidate_sequences, sequence_key, organic, 4096)
            else:
                self.candidate_sequences.move_to_end(sequence_key)
            organic_candidates[name] = self.candidate_sequences[sequence_key]
        eligible = [g["key"] for g in groups if g["food"] and organic_candidates[g["key"]]]
        if not eligible:
            raise PolicyConflict(
                f"Ingen av {sum(g['food'] for g in groups)} matinköpsrader har ett verifierat ekologiskt alternativ i sökningen. Vald kostnadsandel kan inte verifieras. Ändra kravet uttryckligen i Mina val, välj andra varor eller gå tillbaka.",
                code="DATA_BLOCKED",
            )
        best = None
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
        bounds = self.optimizer.restriction_cost_bounds(
            ingredients, candidates, organic_candidates,
            allowed_store_ids=(s.store_id for s in self.view.stores),
        )
        base_bound = sum((pair[0] for pair in bounds.values()), Decimal(0)) if bounds is not None else None
        food_keys = {g["key"] for g in groups if g["food"]}
        organic_ids = {(c.store_id, c.product_id) for values in organic_candidates.values() for c in values}

        def accepts_quotes(quotes):
            food = [q for q in quotes if q.ingredient in food_keys]
            total = sum((money(q.total_price) for q in food), Decimal(0))
            organic = sum((money(q.total_price) for q in food
                           if (q.store_id, q.product_id) in organic_ids), Decimal(0))
            return bool(total) and float(organic * 100 / total) + 1e-8 >= self.spec.organic_percent

        # The result is the cheapest qualifying basket; ties go to the subset
        # that comes first in the original order. With cost bounds, subsets
        # are visited cheapest-bound first so that the bound prunes early;
        # comparing (total, original index) keeps exactly the same winner.
        order = list(enumerate(subsets))
        lower_of = {}
        if bounds is not None:
            for index, subset in order:
                lower_of[index] = base_bound + sum((bounds[k][1] - bounds[k][0] for k in subset), Decimal(0))
            order.sort(key=lambda row: (lower_of[row[0]], row[0]))
        best_index = None

        def cannot_win(cost, index):
            best_total = money(best.total)
            return cost > best_total or (cost == best_total and index > best_index)

        for index, subset in order:
            increment_performance_counter("ecological_subsets_evaluated")
            # An optimistic cost that cannot beat (or tie earlier than) the
            # best exact basket proves this subset cannot replace it. All line
            # quotes include package rounding and eligible single-line offers.
            if best is not None and bounds is not None and cannot_win(lower_of[index], index):
                increment_performance_counter("ecological_subsets_pruned_cost")
                continue
            narrowed = {
                k: organic_candidates[k] if k in subset else v for k, v in candidates.items()
            }
            try:
                if best is not None and bounds is not None:
                    # The week search already exposes checkout-identical
                    # leading keys for nested store caps. Reuse that path to
                    # avoid materializing losing BasketItems and savings, while
                    # keeping every store, quote, verification rank and offer.
                    keys = self.optimizer.same_depth_nested_store_limited_keys(
                        ingredients, narrowed, self.view.stores,
                        max_stores=self.request.max_stores)
                    if not keys or keys[-1] is None or cannot_win(keys[-1][1], index):
                        increment_performance_counter("ecological_subsets_pruned_exact_cost")
                        continue
                option = self.optimizer.optimize(
                    ingredients, narrowed, self.view.stores, max_stores=self.request.max_stores,
                    **({"_accept_quote_selection": accepts_quotes} if bounds is not None else {}),
                )
                searched += 1
                if ((self._eco_percent(option, groups) or 0) + 1e-8 >= self.spec.organic_percent
                        and (best is None or (option.total, index) < (best.total, best_index))):
                    best, best_index = option, index
            except QuoteSelectionRejected:
                searched += 1
                increment_performance_counter("ecological_subsets_pruned_share")
            except IncompleteBasketError:
                continue
        if best is None:
            raise PolicyConflict(
                f"Ingen kombination hittades med minst {self.spec.organic_percent:g} % verifierat eko inom butikstaket ({searched} kontrollerade kombinationer). Kravet är oförändrat."
            )
        if cache_key is not None:
            remember_bounded(self.ecological_results, cache_key, best.model_copy(deep=True), 32)
        return best

    def _check_final(self, slots, basket, groups, rows, allocations):
        # Recheck explicit whole-week constraints independently of search pruning
        # (also applies to user edits and persisted/reloaded slots).
        from app.services.recipe_library import matches_meal
        for category, meal in self.meals.items():
            recipes = [s.recipe for s in slots if s.meal_type == category and s.recipe]
            if meal.recipe_choices is not None and any(
                    not r.design or not matches_meal(r, meal, self.request.recipe_preferences)
                    for r in recipes):
                raise PolicyConflict("Ett recept strider mot måltidstypens val.", code="RECIPE_CHOICES_CONFLICT")
            counts = Counter(r.design.base_id if r.design else self._recipe_id(r) for r in recipes)
            if meal.max_same_base_meals is not None and any(
                    n > meal.max_same_base_meals for n in counts.values()):
                raise PolicyConflict("Veckan överstiger upprepningsgränsen för måltidstypen.", code="RECIPE_CHOICES_CONFLICT")
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
            "purchase": basket.verification_status.value,
            "purchase_planning_mode": self.request.purchase_planning_mode,
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
                {"meal_type": s.meal_type, "slot_id": s.id, "protein": self._protein_category(s.recipe)}
                for s in slots
                if s.recipe
            ],
        }

    @timed_stage("nutrition")
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
                self.cooked_weights.get(self._recipe_id(slot.recipe))
                if limits.min_weight_g is not None or limits.max_weight_g is not None
                else None
            )
            key = (
                self.recipe_computations.key(slot.recipe),
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
                remember_bounded(self.slot_nutrition_cache, key, cached, 2048)
            else:
                self.slot_nutrition_cache.move_to_end(key)
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
                                if slot.recipe.preparation is not None:
                                    from app.services.recipe_preparation import pantry_evidence
                                    evidence = pantry_evidence(slot.recipe, need["name"], identity)
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
                    weight = self.cooked_weights.get(self._recipe_id(slot.recipe))
                    if weight is None and self.spec.allow_nutrition_estimates:
                        from app.services.recipe_portion_weight import estimate_portion_weight

                        selected_by_name = {}
                        for need in (r for r in rows if r['source'] == slot.id):
                            product = selected_products.get(need.get('purchase_key'))
                            # A mixed pantry/purchase food cannot borrow the
                            # purchase's yield identity for the entire input.
                            if product and not any(a['demand_key'] == need['demand_key'] for a in allocations):
                                product = self.prepared.universe.products[
                                    self.by_identity[(product.store_id, product.product_id)]]
                                selected_by_name[canonicalize_ingredient_name(need['name'])] = (product, self.source_facts(product))
                        weight = estimate_portion_weight(slot.recipe, selected_by_name)
                    if (
                        not weight
                        or not weight.get("source")
                        or weight.get("servings") != slot.recipe.servings
                        or not isinstance(weight.get("total_g"), (int, float))
                        or not math.isfinite(weight["total_g"])
                        or weight["total_g"] <= 0
                    ):
                        raise PolicyConflict(
                            f"{slot.recipe.name}: underlag för tillagad portionsvikt och tillagningsutbyte saknas. Vattenupptag och avdunstning kan inte beräknas för detta recept; råvaruvikt används inte som färdig vikt.",
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

    @timed_stage("candidate_generation_and_qualification")
    def _candidates(self, meal, *, qualified_results=None, fixed_slots=()):
        from app.services.plan_jobs import report_stage
        report_stage("candidate_qualification")
        with performance_span("personal_candidate_generation"):
            if self.complete and (meal.meal_type == "dinner" or meal.recipe_choices is not None):
                from app.services.recipe_library import meal_candidates
                candidates = meal_candidates(meal,self.request.recipe_preferences,
                                             include_supplement=self.include_content_pack, generation=self.library_generation)
            else:
                generator = self.service.candidate_generator or DeterministicRecipeCandidateGenerator()
                candidates = generator.generate_for_meal_type(
                    self.view.economic_pool, meal.meal_type, count=80, servings=meal.servings
                )
        if (
            not self.complete
            and
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
        if self.complete and meal.meal_type == "dinner" and self.spec.slots is None:
            from app.services.complete_recipes import validate_content_capacity
            validate_content_capacity(self.request.recipe_preferences, meal,
                                      merged_profile(self.spec.profile, meal.profile), candidates)
        # Every qualified variant keeps its evidence for this request. The seed
        # cap and variant shortlist keep ALL recipes without evidence, so an
        # evicted entry (formerly a fixed 2,048 bound) silently enlarged the
        # seed beam once a library qualified more variants than that.
        evidence_limit = max(2048, len(self.variant_search_evidence) + len(candidates))
        from app.services.personal_policy import remaining_category_capacity
        capacity = remaining_category_capacity(meal, fixed_slots, classify=self._protein_category)
        from app.services.planner_context import content_digest, planner_context
        reuse = (self.complete and getattr(self, "artifacts", None) is not None
                 and getattr(self.settings, "library_search_policy", "legacy") == "smako-verified-reference-v1")
        view_key = (content_digest([planner_context(self), meal, fixed_slots]) if reuse else None)
        stored = self.artifacts.load("qualification", view_key) if reuse else None
        stored_rows = stored.get("rows", {}) if isinstance(stored, dict) else {}
        if not isinstance(stored_rows, dict):
            stored_rows = {}
        qualified_rows = {}
        qualification_hits = 0
        for recipe in candidates:
            issued_key = content_digest(recipe) if reuse else None
            cached = stored_rows.get(issued_key)
            # The recipe registry supplies exact canonical, scaled values. A
            # noncanonical input cannot bypass clean_recipe using a cache hit.
            if (not isinstance(cached, dict) or cached.get("status") not in {"passed", "rejected"}
                    or any(i.canonical_name != canonicalize_ingredient_name(i.name) for i in recipe.ingredients)):
                cached = None
            self.product_trace.recipe(recipe)
            stage = "policy_taste"
            try:
                if cached is not None and cached["status"] == "rejected":
                    if (isinstance(cached.get("reason"), str) and isinstance(cached.get("code"), str)
                            and isinstance(cached.get("stage"), str)):
                        qualification_hits += 1
                        raise PolicyConflict(cached["reason"], code=cached["code"], stage=cached["stage"])
                    cached = None
                if meal.distribution and capacity[self._protein_category(recipe)] <= 0:
                    raise PolicyConflict("Kategorin ryms inte i din valda måltidsfördelning.", stage="policy_taste")
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
                if cached is None:
                    recipe = self.clean_recipe(recipe, meal)
                # Sealed authored designs have their own ingredient, portion,
                # method and timeline validation in clean_recipe. Their actual
                # product nutrition is qualified by basket below. The legacy
                # coarse taxonomy estimator lacks these new foods and cannot
                # veto source-qualified meals merely for incomplete coverage.
                quality = (
                    self.service._nutrition_for(self.request).validate_recipes([recipe])
                    if meal.meal_type == "dinner" and not self.complete
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
                if cached is not None:
                    from app.services.stable_candidate_pool import VariantSearchEvidence
                    try:
                        evidence = cached.get("evidence")
                        if recipe.design:
                            evidence = VariantSearchEvidence(evidence["paid"],
                                tuple((k, v) for k, v in evidence["nutrients"]),
                                frozenset(tuple(k) for k in evidence["packages"]))
                            remember_bounded(self.variant_search_evidence,
                                (meal.meal_type, self._recipe_id(recipe)), evidence, evidence_limit)
                        self.diagnostics.singleton_passed += 1
                        qualification_hits += 1
                    except (KeyError, TypeError, ValueError):
                        cached = None
                        recipe = self.clean_recipe(recipe, meal)
                if cached is None and (meal.limits.active or self.complete):
                    # Qualify every meal type before menu branching. Previously
                    # only depth-one dinners were independently checked; failed
                    # breakfasts/snacks could remain hidden behind dinner search.
                    qualified = self.basket(
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
                    if qualified_results is not None:
                        key = ((f"{meal.meal_type}-1", self._recipe_id(recipe)),)
                        remember_bounded(qualified_results, key, qualified, 256)
                    if recipe.design:
                        from app.services.stable_candidate_pool import VariantSearchEvidence
                        items = [i for s in qualified["basket"].stores for i in s.items]
                        nutrition = self._check_nutrition(
                            [MealSlot(id=f"{meal.meal_type}-1", day=1, meal_type=meal.meal_type, recipe=recipe)],
                            {i.ingredient: i for i in items}, qualified["trace_inputs"][1], qualified["allocations"])
                        remember_bounded(self.variant_search_evidence,
                            (meal.meal_type, self._recipe_id(recipe)),
                            VariantSearchEvidence(qualified["basket"].total,
                                tuple(sorted(nutrition[0]["values"].items())),
                                frozenset((i.store_id, i.product_id) for i in items)), evidence_limit)
                    self.diagnostics.singleton_passed += 1
                valid.append(recipe)
                if reuse:
                    from dataclasses import asdict
                    evidence = self.variant_search_evidence.get((meal.meal_type, self._recipe_id(recipe)))
                    qualified_rows[issued_key] = {"status": "passed",
                        "evidence": asdict(evidence) if evidence is not None else None}
                if recipe.design and recipe.design.content_source:
                    self._supplement_qualified = True
                    from app.services.meal_library_content import identity
                    if self._prior_recipe_ids is not None and identity(recipe) not in self._prior_recipe_ids:
                        self._expanded_cohort_qualified = True
            except (PolicyConflict, ValueError) as exc:
                if reuse:
                    qualified_rows[issued_key] = {"status": "rejected", "reason": str(exc),
                        "stage": getattr(exc, "stage", None) or stage,
                        "code": getattr(exc, "code", "CONFLICT")}
                self.product_trace.recipe(recipe, getattr(exc, "stage", None) or stage, str(exc))
                self.diagnostics.reject(getattr(exc, "stage", None) or stage, recipe, str(exc))
                if len(local_conflicts) < 10:
                    local_conflicts.append(exc)
        if reuse:
            # Only the completed meal view is atomically published. Retain
            # unchanged earlier rows so append-only recipes qualify once.
            if self.artifacts.save("qualification", view_key,
                    {"rows": {**stored_rows, **qualified_rows}, "qualified": len(valid)}):
                self._qualification_views[meal.meal_type] = view_key
            self.diagnostics.pools[-1]["qualification_cache_hits"] = qualification_hits
            self.diagnostics.pools[-1]["qualified"] = len(valid)
            from app.services.recipe_library import prepared_recipe_lookup
            prepared_recipe_lookup(meal.servings)
        if not valid:
            if self.complete:
                if not candidates:
                    raise PolicyConflict("Inget grundrecept uppfyller kombinationen av matkök, tid och ingrediensantal. Prova längre tillagningstid, ett bredare ingrediensintervall eller fler matkök. Dina krav har inte ändrats.", code="RECIPE_CHOICES_UNFULFILLED", stage="policy_taste")
                first = local_conflicts[0] if local_conflicts else None
                code = getattr(first, "code", "RECIPE_QUALIFICATION_BLOCKED")
                reason = str(first) if first else "Recepten stoppades av måltidskontrollen. Se den första orsaken per recept i underlaget."
                if code == "DATA_BLOCKED":
                    suggestion = "Ett eller flera val kan inte kontrolleras med det tillgängliga underlaget. Se orsakerna per recept. Saknade närings-, allergen- eller viktuppgifter behöver kompletteras; ett lägre proteinmål löser inte sådana dataluckor."
                elif code == "NUTRITION_TARGET_NOT_MET":
                    suggestion = "Pröva godkända receptvariationer eller ändra näringsmålet uttryckligen."
                else:
                    suggestion = "Kontrollera vilka kostval eller uteslutningar som anges i orsakerna, eller välj ett annat matkök."
                raise PolicyConflict(reason + " " + suggestion + " Dina krav har inte ändrats.", code=code, stage=getattr(first, "stage", None))
            if local_conflicts:
                raise local_conflicts[0]
            raise PolicyConflict(f"Inga användbara recept för {meal.meal_type} med dina val.")
        return valid

    def create(self, *, replace_slot=None, balanced_reference=None, _compare_scopes=True):
        started = perf_counter()
        self._release_idle_memory()
        incumbents = []
        incumbent_scopes = {}
        if (self.complete and _compare_scopes and self.request.diversity_mode == "cheapest"
                and self.spec.slots is None and replace_slot is None):
            scopes = [(cap, self.request.purchase_planning_mode) for cap in range(1, self.request.max_stores)]
            if self.request.purchase_planning_mode == "estimated":
                scopes.extend((cap, "exact") for cap in range(1, self.request.max_stores + 1))
            for cap, purchase_mode in scopes:
                comparison_request = self.request.model_copy(update={"max_stores": cap, "purchase_planning_mode": purchase_mode})
                try:
                    candidate = PersonalPlanner(comparison_request, self.settings, self.prepared, self.state,
                        plan_id=self.plan_id, facts=self.facts, cooked_weights=self.cooked_weights, now=self.now,
                        nutrition_search_limit=self.nutrition_search_limit,
                        include_content_pack=self.include_content_pack, library_generation=self.library_generation,
                        artifacts=self.artifacts, previous_menus=self.previous_menus).create(_compare_scopes=False)
                except (ValueError, IncompleteBasketError):
                    continue
                incumbents.append(candidate)
                incumbent_scopes[id(candidate)] = {"max_stores": cap, "purchase_planning_mode": purchase_mode}
        def release_search_intermediates():
            # These are pure request-local memoized calculations. A finished
            # result owns its basket/checks; no search cache is an approval.
            for name in ("lookup_cache", "lookup_failures", "_resolution_trace",
                         "nutrition_cache", "candidate_sequences", "ecological_results", "variant_search_evidence", "normalized_recipe_rows",
                         "qualified_nutrition_candidates", "slot_nutrition_cache", "clean_recipe_cache"):
                getattr(self,name).clear()
            self.recipe_computations = RecipeComputationCache()
            import gc
            gc.collect()
        def retain_library_comparison():
            # A larger candidate pool can reorder bounded search. Re-run the
            # exact earlier pool through this same planner, same data/clock,
            # private state and budget. Never load another owner's saved plan.
            # If no added recipe qualifies, the old ordered pool is identical
            # and repeating its full search would have no benefit.
            if (self._library_search_handled
                    or not self.complete or not self.include_content_pack or not self._supplement_qualified
                    or not _compare_scopes
                    or self.spec.slots is not None or replace_slot is not None):
                return
            generation = self._generation
            if generation > 2 and not self._expanded_cohort_qualified:
                return
            if generation <= 2 and self.request.diversity_mode != "cheapest":
                return
            release_search_intermediates()
            try:
                candidate = PersonalPlanner(self.request, self.settings, self.prepared, self.state,
                    plan_id=self.plan_id, facts=self.facts, cooked_weights=self.cooked_weights, now=self.now,
                    nutrition_search_limit=self.nutrition_search_limit,
                    include_content_pack=generation > 2,
                    library_generation=generation-1 if generation > 2 else None, artifacts=self.artifacts,
                    previous_menus=self.previous_menus).create()
            except (ValueError, IncompleteBasketError):
                return
            incumbents.append(candidate)
            incumbent_scopes[id(candidate)] = {"max_stores": self.request.max_stores,
                "purchase_planning_mode": self.request.purchase_planning_mode, "library": "before_content_pack"}
        try:
            with self.optimizer.quote_cache():
                result = self._create(replace_slot=replace_slot, balanced_reference=balanced_reference)
            retain_library_comparison()
            if incumbents:
                winner = min([result, *incumbents], key=lambda p: self._week_purchase_key(p.optimized_basket))
                if winner is not result:
                    result = self._retain_scope_incumbent(winner, incumbent_scopes[id(winner)])
                result.personal.checks.setdefault("scope_comparison", {}).update({
                    "retained_valid_incumbents": len(incumbents),
                    "comparison_totals": [p.optimized_basket.total for p in incumbents],
                    "meaning": "Giltiga lösningar med färre butiker, exakt köp och tidigare recepturval jämförs när sökområdet utökas.",
                })
            return self._finalize_result(result, started)
        except (ValueError, IncompleteBasketError) as exc:
            if not any(scope.get("library") == "before_content_pack" for scope in incumbent_scopes.values()):
                retain_library_comparison()
            if incumbents:
                winner = min(incumbents, key=lambda p: self._week_purchase_key(p.optimized_basket))
                result = self._retain_scope_incumbent(winner, incumbent_scopes[id(winner)], error=exc)
                result.personal.checks["scope_comparison"].update({
                    "retained_valid_incumbents": len(incumbents),
                    "expanded_search_completed_without_better_solution": True,
                    "comparison_totals": [p.optimized_basket.total for p in incumbents],
                })
                return self._finalize_result(result, started)
            message = str(exc)
            code = getattr(exc, "code", "SEARCH_BLOCKED")
            if isinstance(exc, IncompleteBasketError):
                if code == "SEARCH_INCOMPLETE":
                    message = "Sökningen är ofullständig. Ingen slutkontrollerad meny kunde färdigställas. Dina krav har inte ändrats."
                    self.diagnostics.search.append({"depth": 0, "attempt": 1, "library_phase": "incomplete",
                        "beam_pruned": 0, "status": code, "search_report": getattr(exc, "search_report", None)})
                else:
                    message = "Sökningen hittade ingen komplett meny med dina krav. Se blockeringsfördelningen. Inga krav har sänkts."
            elif self.diagnostics.pools and not (self.complete and code == "RECIPE_CHOICES_CONFLICT"):
                message = (
                    "Ingen komplett kombination hittades. Flera kandidater har prövats; exemplet nedan förklarar inte hela veckoplanen. "
                    + message
                )
            hint = self._campaign_only_scope_hint()
            if hint:
                message = f"{message} {hint}"
            if not self.complete and not self.spec.allow_nutrition_estimates and any(
                m.count and requested_nutrients(m.limits) for m in self.spec.meals
            ):
                self._estimate_alternatives()
            raise PolicyConflict(
                message,
                code=code,
                conflicts=getattr(exc, "conflicts", None),
                diagnostics=self.diagnostics.snapshot(),
            ) from exc

    def _campaign_only_scope_hint(self):
        """Explain a failed plan whose every usable store is offers-only.

        Text only: no requirement, store scope or price rule changes. Unknown
        coverage is never treated as offers-only, and nothing is suggested when
        the area has no store with a complete catalogue.
        """
        selected = [s for s in self.view.stores if s.store_id in self.store_ids]
        if not selected or any(s.coverage != "offers_only" for s in selected):
            return None
        complete = sorted({s.name for s in self.view.stores
                           if s.store_id not in self.store_ids
                           and s.coverage in {"full_catalog", "full_online_catalog"}})
        text = ("De valda butikerna har bara kampanjpriser i Smakos underlag, så varor "
                "som inte är på kampanj kan inte prissättas där.")
        if complete:
            text += " Lägg till minst en butik med fullt sortiment, till exempel " + ", ".join(complete[:3]) + "."
        return text

    def _predicted_substitution(self, chosen, incumbent, index):
        """Sort key: predicted week total of a one-slot substitution (unknown last)."""
        predicted = self._substitution_prediction(chosen, incumbent, index)
        return (predicted is None, predicted if predicted is not None else Decimal(0))

    def _substitution_prediction(self, chosen, incumbent, index):
        old, new = incumbent[0][index], chosen[index]
        if not old.recipe or not new.recipe:
            return None
        old_evidence = self.variant_search_evidence.get((old.meal_type, self._recipe_id(old.recipe)))
        new_evidence = self.variant_search_evidence.get((new.meal_type, self._recipe_id(new.recipe)))
        if old_evidence is None or new_evidence is None:
            return None
        total = Decimal(str(incumbent[1]["basket"].total))
        return total - Decimal(str(old_evidence.paid)) + Decimal(str(new_evidence.paid))

    def _screen_substitution(self, chosen, incumbent, index, margin):
        """Keep a one-slot substitution unless its predicted week is far dearer.

        Prediction: incumbent total - qualified single-recipe purchase of the
        replaced recipe + that of the new one. Shared packages make the real
        week cheaper or dearer; ``margin`` is the measured tolerance. Unknown
        evidence keeps the proposal. Heuristic, like the pool caps.
        """
        predicted = self._substitution_prediction(chosen, incumbent, index)
        if predicted is None:
            return True
        total = Decimal(str(incumbent[1]["basket"].total))
        return predicted <= total * (1 + Decimal(str(margin)))

    def _select_library_options(self, groups, *, limit, shortlist_variants):
        """Per meal type: optional variant shortlist (four per base), then the cap.

        ``limit`` 0 and ``shortlist_variants`` False keep the whole qualified
        pool; the full-library reference (matrix ``--uncapped``) uses both.
        """
        from app.services.stable_candidate_pool import (
            category_seed_cap,
            library_seed_cap,
            library_variant_shortlist,
        )
        selected, by_meal = [], {}
        for group in groups:
            if not group:  # e.g. a generation that adds no recipe of this meal type
                selected.append([])
                continue
            meal_type = group[0].meal_type
            if meal_type not in by_meal:
                recipes = [s.recipe for s in group if s.recipe]
                evidence = {self._recipe_id(r): self.variant_search_evidence[(meal_type, self._recipe_id(r))]
                            for r in recipes if (meal_type, self._recipe_id(r)) in self.variant_search_evidence}
                kept = library_variant_shortlist(recipes, evidence) if shortlist_variants else recipes
                if limit:
                    meal = self.meals[meal_type]
                    if meal.distribution:
                        from app.services.personal_policy import remaining_category_capacity
                        kept = category_seed_cap(
                            kept, evidence, capacity=remaining_category_capacity(meal),
                            classify=self._protein_category, limit=limit)
                    else:
                        kept = library_seed_cap(kept, evidence, limit=limit)
                by_meal[meal_type] = {self._recipe_id(r) for r in kept}
            selected.append([s for s in group if not s.recipe or self._recipe_id(s.recipe) in by_meal[meal_type]])
        return selected

    def _week_purchase_key(self, basket):
        from app.services.week_refinement import surplus_key
        return (money(basket.total), surplus_key(basket) if self.spec.surplus_mode == "minimize" else ())

    @timed_stage("memory_reclamation")
    def _release_idle_memory(self, *, recent=False):
        from app.services.planner_memory import release_idle_memory

        return release_idle_memory(generation=1 if recent else 2)

    def _culinary_snapshot(self, *menus):
        from app.services.menu_optimizer import LazyPairwiseSimilarities

        profiles = getattr(self, "_qualified_culinary_view", None)
        names = {s.recipe.name.casefold().strip() for menu in menus for s in menu
                 if s.recipe and s.meal_type == "dinner"}
        return profiles.profile_rows(names) if isinstance(profiles, LazyPairwiseSimilarities) else None

    def _menu_candidate_inputs(self, context):
        from app.services.planner_context import content_digest

        saved = (self.artifacts.recent_menu_records(context, include_certificates=False)
                 if self.artifacts is not None else ())
        records = [*self.previous_menus, *saved]
        # Re-saving the same identities does not require another preparation.
        # The owner/erasure epoch is enforced by the existing artifact reader.
        return records, content_digest({"menu_inputs_v1": sorted({content_digest(r) for r in records})})

    def _search_verified_reference(self, options, search_kwargs, *, _ignore_cache=False):
        from app.services.basket_calculator import BasketCalculator
        from app.services.library_publications import (
            index_slots,
            load_certificate,
            publications,
            restore_slots,
            save_certificate,
        )
        from app.services.library_search_cohorts import merged_library_cohorts, per_package_cohorts
        from app.services.meal_library_content import identity
        from app.services.menu_optimizer import LibraryPrefixCheckpoint
        from app.services.planner_context import content_digest, planner_context
        from app.services.recipe_library import current_recipe_generations, current_recipes
        from app.services.reference_library import reference_cohorts, reference_manifest
        from app.services.verified_menu_search import (
            IMPROVEMENT_EVALUATIONS,
            IMPROVEMENT_PROPOSALS,
            IMPROVEMENT_SAFETY_SECONDS,
            SearchBudget,
            verified_search,
        )

        first = 1 if self.request.diversity_mode == "cheapest" else min(2, self._generation)
        current = current_recipes(self.library_generation)
        reference = reference_cohorts(options, current, first_generation=first)
        context = planner_context(self)
        evaluate, accepts = search_kwargs["evaluate"], search_kwargs["accepts"]
        reference_winner, predecessor, incumbent = None, None, None
        slot_index = index_slots(options)
        chain = publications(self.library_generation)
        # Non-append-only content is explicitly experimental, with no invented
        # predecessor certificate. Still retain any valid pinned reference.
        nodes = chain or ({"generation": self._generation, "count": len(current)},)
        reports, loaded, replayed, chain_complete = [], 0, 0, True
        generations = current_recipe_generations(self.library_generation)
        records, candidate_inputs = self._menu_candidate_inputs(context)
        records.extend(self.artifacts.recent_menu_records(context) if self.artifacts is not None else ())
        prior_records = list({content_digest(record): record for record in records}.values())
        # Stateful/injected calculation paths keep independent call behavior.
        legacy_prefix = (LibraryPrefixCheckpoint()
            if type(self) is PersonalPlanner and type(self.service) is MealPlanService
            and type(getattr(self, "optimizer", None)) is BasketOptimizer
            and type(self.optimizer.calculator) is BasketCalculator
            and getattr(self.basket, "__func__", None) is PersonalPlanner.basket else None)

        def audit(chosen):
            self._defer_search_audit = False
            try:
                return evaluate(chosen, final=True)
            finally:
                self._defer_search_audit = True

        def independent_kwargs():
            kwargs = dict(search_kwargs)
            kwargs["initial_evaluations"] = OrderedDict(search_kwargs.get("initial_evaluations") or {})
            for key in ("completed_prefix_indexes", "cohort_prefix_sizes", "checkpoint_probe_indexes",
                        "unordered_small_pool_limit"):
                kwargs.pop(key, None)
            return kwargs

        for node in nodes:
            cached = (load_certificate(self.artifacts, context, node, options, predecessor, slot_index)
                      if chain and not _ignore_cache else None)
            if cached is not None:
                winner_slots, reference_slots, certificate = cached
                loaded += 1
                predecessor = certificate["sha256"]
                # Later misses must use this predecessor, not skip straight to
                # the largest library's trajectory. Materialize only as needed.
                incumbent = winner_slots, None
                reference_winner = reference_slots, None
                continue
            if incumbent is not None and incumbent[1] is None:
                try:
                    incumbent = incumbent[0], evaluate(incumbent[0], final=False)
                except (ValueError, IncompleteBasketError):
                    incumbent = None
                    chain_complete = False
            if reference_winner is not None and reference_winner[1] is None:
                try:
                    reference_winner = reference_winner[0], evaluate(reference_winner[0], final=False)
                except (ValueError, IncompleteBasketError):
                    reference_winner = None
                    chain_complete = False
            prefix = current_recipes(node["generation"])
            allowed = {identity(r) for r in prefix}
            prefix_options = [[s for s in group if not s.recipe or not s.recipe.design
                               or identity(s.recipe) in allowed] for group in options]
            improvements, completed, prefixes, probes = merged_library_cohorts(
                prefix_options, prefix, current_recipe_generations(node["generation"]), first_generation=first)
            # A cold context prepares ordered publications in this admitted
            # plan job. Each node has fixed limits; a prepared hit replays none.
            budget = SearchBudget(IMPROVEMENT_EVALUATIONS, IMPROVEMENT_PROPOSALS,
                                  seconds=IMPROVEMENT_SAFETY_SECONDS)
            previous = [] if incumbent is None else [incumbent]
            for record in prior_records:
                slots = restore_slots(record, prefix_options, slot_index)
                if slots is not None:
                    try:
                        previous.append((slots, evaluate(slots, final=False)))
                    except (ValueError, IncompleteBasketError):
                        pass  # Changed facts/locks are requalified, never hidden.

            # The pinned base alone cannot dominate legacy on the full library.
            # Prepare that independent trajectory once per publication/context;
            # only its completed candidate enters the normal current checkout.
            legacy_started, trace_start = perf_counter(), len(self.diagnostics.search)
            legacy_report = {"status": "search_miss"}
            try:
                legacy = self.service.menu_optimizer.optimize_library_slots(
                    per_package_cohorts(prefix_options, generations,
                        first_generation=first, last_generation=node["generation"]),
                    _prefix_checkpoint=legacy_prefix, _prefix_context=(context, self._defer_search_audit),
                    **independent_kwargs())
                previous.append(legacy)
                legacy_report = {"status": "proposal_completed", "proposed_paid": str(money(legacy[1]["basket"].total))}
            except (ValueError, IncompleteBasketError) as exc:
                legacy_report.update(code=getattr(exc, "code", None), stage=getattr(exc, "stage", None))
            finally:
                legacy_report["seconds"] = perf_counter() - legacy_started
                for row in self.diagnostics.search[trace_start:]:
                    row.update(search_track="legacy_full_library", publication_size=node["count"])
                legacy_report["evaluations"] = sum(row.get("evaluations_executed", 0)
                    for row in self.diagnostics.search[trace_start:])
                self._release_idle_memory(recent=True)

            def search(track, emit, *, budget=budget, completed=completed, prefixes=prefixes,
                       probes=probes, improvements=improvements, node=node, prefix_options=prefix_options):
                nonlocal reference_winner
                from time import monotonic

                if track == "reference" and reference_winner is not None:
                    emit(*reference_winner)
                    return
                # Each independent track owns its seed container; the ordinary
                # optimizer consumes initial_evaluations during its first beam.
                kwargs = independent_kwargs()
                if track == "improvement":
                    budget.started = monotonic()

                    def bounded_accepts(chosen, *, final):
                        budget.proposal()
                        return accepts(chosen, final=final)

                    def bounded_evaluate(chosen, *, final):
                        budget.evaluation()
                        result = evaluate(chosen, final=final)
                        if final:
                            emit(chosen, result)
                        return result

                    kwargs.update(accepts=bounded_accepts, evaluate=bounded_evaluate)
                attempts = [("per_pack_reference", reference, {})]
                if track == "improvement":
                    small = {"unordered_small_pool_limit": 4096} if not self.items and not self.spec.product_locks else {}
                    attempts = [("full_pool", [(node["generation"], prefix_options)], small),
                        ("geometric", improvements, {"completed_prefix_indexes": completed,
                            "cohort_prefix_sizes": prefixes, "checkpoint_probe_indexes": probes})]
                for phase, cohorts, extra in attempts:
                    phase_kwargs = {**kwargs, **extra,
                        "initial_evaluations": OrderedDict(search_kwargs.get("initial_evaluations") or {})}
                    start = len(self.diagnostics.search)
                    try:
                        chosen, result = self.service.menu_optimizer.optimize_library_slots(cohorts, **phase_kwargs)
                        if track == "reference":
                            reference_winner = chosen, result
                        emit(chosen, result)
                    finally:
                        for row in self.diagnostics.search[start:]:
                            row["search_track"] = track
                            row["improvement_path"] = phase
                            row["publication_size"] = node["count"]
                        self._release_idle_memory(recent=True)

            chosen, result, report = verified_search(search, audit=audit,
                accepts=lambda chosen: accepts(chosen, final=True),
                rank=lambda chosen, result: (self._week_purchase_key(result["basket"]),
                                             search_kwargs["score"](chosen, result)), budget=budget,
                previous=previous)
            incumbent = chosen, result
            reports.append({**report, "publication_size": node["count"],
                            "paid": str(money(result["basket"].total)),
                            "legacy_full_library_preparation": legacy_report})
            chain_complete = chain_complete and report["budget_stop"] != "wall_time_safety_stop"
            replayed += 1
            if chain and reference_winner is not None:
                certificate = save_certificate(self.artifacts, context, node, predecessor,
                    chosen, reference_winner[0], result, replay_complete=chain_complete,
                    qualification=self.diagnostics.pools, candidate_inputs=candidate_inputs,
                    qualification_library=chain[-1]["sha256"],
                    culinary_profiles=self._culinary_snapshot(chosen, reference_winner[0]))
                predecessor = certificate["sha256"]
            self._release_idle_memory()
        chosen, result = incumbent
        if result is None:
            # The durable certificate is result evidence, never current basket
            # approval. Reject an invalid cached winner and fall back to ref.
            def cached_tracks(track, emit):
                if track == "reference":
                    emit(reference_winner[0], evaluate(reference_winner[0], final=False))

            prior, cached_winner_audited = [], False
            cached_winner = tuple(chosen)

            def cached_audit(slots):
                nonlocal cached_winner_audited
                value = audit(slots)
                if tuple(slots) == cached_winner:
                    cached_winner_audited = True
                return value

            try:
                prior.append((chosen, evaluate(chosen, final=False)))
            except (ValueError, IncompleteBasketError):
                pass
            for record in prior_records:
                restored = restore_slots(record, options, slot_index)
                if restored is not None and not any(tuple(restored) == tuple(row[0]) for row in prior):
                    try:
                        prior.append((restored, evaluate(restored, final=False)))
                    except (ValueError, IncompleteBasketError):
                        pass
            try:
                chosen, result, report = verified_search(cached_tracks, audit=cached_audit,
                    accepts=lambda chosen: accepts(chosen, final=True),
                    rank=lambda chosen, result: (self._week_purchase_key(result["basket"]),
                                                 search_kwargs["score"](chosen, result)),
                    budget=SearchBudget(IMPROVEMENT_EVALUATIONS, IMPROVEMENT_PROPOSALS), previous=prior)
            except (ValueError, IncompleteBasketError):
                return self._search_verified_reference(options, search_kwargs, _ignore_cache=True)
            if not cached_winner_audited:
                return self._search_verified_reference(options, search_kwargs, _ignore_cache=True)
            certificate = save_certificate(self.artifacts, context, nodes[-1], cached[2]["predecessor"],
                chosen, reference_winner[0], result, qualification=self.diagnostics.pools,
                candidate_inputs=candidate_inputs,
                qualification_library=chain[-1]["sha256"],
                culinary_profiles=self._culinary_snapshot(chosen, reference_winner[0])) if chain else None
            predecessor = certificate["sha256"] if certificate else None
            reports.append(report)
            self.diagnostics.search.append({"depth": len(chosen), "attempt": 1,
                "library_phase": "certificate_reaudit", "search_track": "reference_and_previous",
                "evaluations_executed": 0, "beam_pruned": 0})
        result["checks"]["verified_reference"] = {
            "policy": "smako-verified-reference-v1", "context": context,
            "global_optimum_proven": False, "publications": reports,
            "verified_candidates": reports[-1]["verified_candidates"],
            "reference_manifest": reference_manifest()["sha256"],
            "publication_chain": ("append_only_replayed_or_verified" if chain and chain_complete
                                  else "incomplete_wall_time" if chain else "experiment_content_changed"),
            "certificate": predecessor, "loaded_publications": loaded, "replayed_publications": replayed,
            "improvement_limits": {"evaluations": IMPROVEMENT_EVALUATIONS, "proposals": IMPROVEMENT_PROPOSALS,
                                   "wall_time_safety_seconds": IMPROVEMENT_SAFETY_SECONDS,
                                   "version": "full-pool-first-4096-v1"},
        }
        return chosen, result

    def _search_with_previous_menus(self, search, search_input, options, search_kwargs):
        """Release comparisons may re-audit an old menu against new facts."""
        from app.services.library_publications import index_slots, restore_slots
        from app.services.verified_menu_search import SearchBudget, verified_search

        evaluate, accepts = search_kwargs["evaluate"], search_kwargs["accepts"]
        lookup, previous, rejections = index_slots(options), [], []
        for record in self.previous_menus:
            slots = restore_slots(record, options, lookup)
            if slots is not None:
                try:
                    previous.append((slots, evaluate(slots, final=False)))
                except (ValueError, IncompleteBasketError) as exc:
                    rejections.append({"code": getattr(exc, "code", None),
                        "stage": getattr(exc, "stage", None), "reason": str(exc)})
            else:
                names = {r.get("recipe_name") for r in record if isinstance(r, dict)}
                details = [row for row in self.diagnostics.details if row["recipe"] in names]
                rejections.append({"reason": "recipe_value_changed_removed_or_not_qualified", "details": details})

        def tracks(track, emit):
            if track == "reference":
                emit(*search(search_input, **search_kwargs))

        def audit(slots):
            self._defer_search_audit = False
            try:
                return evaluate(slots, final=True)
            finally:
                self._defer_search_audit = True

        chosen, result, report = verified_search(tracks, audit=audit,
            accepts=lambda slots: accepts(slots, final=True),
            rank=lambda slots, result: (self._week_purchase_key(result["basket"]),
                                       search_kwargs["score"](slots, result)),
            previous=previous, budget=SearchBudget(1, 1))
        result["checks"]["reaudited_previous_menu"] = {**report, "qualification_rejections": rejections}
        return chosen, result

    def _prepared_menu_options(self, slots):
        """Reuse a complete certificate chain; never shorten a cold search pool."""
        from app.services.library_publications import load_certificate_record, publications
        from app.services.meal_library_content import identity
        from app.services.menu_optimizer import MenuOptimizer
        from app.services.planner_context import content_digest, planner_context
        from app.services.recipe_library import prepared_recipe_lookup

        if (not self.complete or self.artifacts is None or not self.include_content_pack
                or self.library_generation is not None or self.request.diversity_mode == "varied"
                or getattr(self.settings, "library_search_policy", "legacy") != "smako-verified-reference-v1"
                or getattr(self._candidates, "__func__", None) is not PersonalPlanner._candidates
                or type(self.service.menu_optimizer) is not MenuOptimizer
                or getattr(self.service.menu_optimizer.optimize_slots, "__func__", None) is not MenuOptimizer.optimize_slots):
            return None
        chain, context, predecessor = publications(), planner_context(self), None
        if not chain:
            return None
        for node in chain:
            data = load_certificate_record(self.artifacts, context, node, predecessor)
            if data is None:
                return None  # Rebuild EVERY missing published predecessor normally.
            predecessor = data["sha256"]
        view = self.artifacts.load("menu_view", content_digest([context, chain[-1]["sha256"]]))
        _, candidate_inputs = self._menu_candidate_inputs(context)
        if (not isinstance(view, dict) or view.get("certificate") != data["sha256"]
                or view.get("candidate_inputs") != candidate_inputs
                or not isinstance(view.get("qualification"), list)
                or not all(isinstance(p, dict) and type(p.get("qualified")) is int
                           and type(p.get("raw")) is int and isinstance(p.get("meal_type"), str)
                           and 0 <= p["qualified"] <= p["raw"] for p in view["qualification"])
                or {p["meal_type"] for p in view["qualification"]} != {slot.meal_type for slot in slots}):
            return None
        allowed = {row[0] for row in chain[-1]["recipes"]}
        candidates = []
        for kind in ("reference", "winner"):
            records = data.get(kind)
            if not isinstance(records, list) or len(records) != len(slots):
                return None
            selected = []
            for row, slot in zip(records, slots, strict=True):
                if not isinstance(row, dict) or row.get("slot") != slot.id or not isinstance(row.get("recipe"), str):
                    return None
                lookup = prepared_recipe_lookup(self.meals[slot.meal_type].servings)
                recipe = lookup.get(row["recipe"]) if lookup is not None else None
                if (recipe is None or identity(recipe) not in allowed
                        or content_digest(recipe) != row["recipe"]):
                    return None
                # Lists/form maps remain request-owned even on this fast path.
                recipe = recipe.model_copy(update={"ingredients": list(recipe.ingredients),
                    "instructions": list(recipe.instructions), "preparation": recipe.preparation.model_copy(
                        update={"input_forms": dict(recipe.preparation.input_forms)})})
                selected.append(slot.model_copy(update={"recipe": recipe}))
            candidates.append(selected)
        from app.services.recipe_profile import RecipeProfile
        try:
            profiles = {}
            for name, row in view["culinary_profiles"]:
                values = dict(row)
                for field in ("vegetables", "major_ingredients", "flavor_profile"):
                    values[field] = tuple(values[field])
                values["ingredient_weights"] = tuple((k, v) for k, v in values["ingredient_weights"])
                if any(not isinstance(k, str) or not math.isfinite(v) or v < 0
                       for k, v in values["ingredient_weights"]):
                    return None
                profiles[name] = RecipeProfile(**values)
            names = {s.recipe.name.casefold().strip() for menu in candidates for s in menu if s.meal_type == "dinner"}
            if set(profiles) != names:
                return None
        except (KeyError, TypeError, ValueError):
            return None
        for summary in view["qualification"]:
            self.diagnostics.pools.append({**summary, "qualification_cache_hits": summary["qualified"],
                                            "reused_library_certificate": True})
            self.diagnostics.singleton_passed += summary["qualified"]
        options = [[group[index] for group in candidates] for index in range(len(slots))]
        return {"certificate": data, "context": context, "chain_length": len(chain),
                "candidates": candidates, "options": options, "culinary_profiles": profiles}

    def _capacity_artifact_key(self):
        from app.services.library_publications import publications
        from app.services.menu_optimizer import MenuOptimizer
        from app.services.planner_context import content_digest, planner_context

        if (not self.complete or self.artifacts is None or self.library_generation is not None
                or not self.include_content_pack or self.spec.slots is not None
                or getattr(self.settings, "library_search_policy", "legacy") != "smako-verified-reference-v1"
                or getattr(self._candidates, "__func__", None) is not PersonalPlanner._candidates
                or type(self.service.menu_optimizer) is not MenuOptimizer
                or getattr(self.service.menu_optimizer.optimize_slots, "__func__", None) is not MenuOptimizer.optimize_slots):
            return None
        chain = publications()
        return content_digest([planner_context(self), chain[-1]["sha256"]]) if chain else None

    def _reuse_capacity_proof(self):
        from app.services.planner_context import content_digest

        key = self._capacity_artifact_key()
        data = self.artifacts.load("capacity_proof", key) if key else None
        if not isinstance(data, dict) or not isinstance(data.get("views"), dict):
            return False
        if set(data["views"]) != {m.meal_type for m in self.spec.meals if m.count}:
            return False
        try:
            for entry in data["views"].values():
                view = self.artifacts.load("qualification", entry["key"])
                if view is None or content_digest(view) != entry["sha256"]:
                    return False
            proof = data["proof"]
            if (proof["scope"] != "qualified_dinner_pool" or proof["status"] != "PROVEN_INFEASIBLE"
                    or proof["dimension"] != "dish_form" or type(proof["maximum_slots"]) is not int
                    or type(proof["required_slots"]) is not int
                    or proof["required_slots"] != sum(m.count for m in self.spec.meals if m.meal_type == "dinner")
                    or not 0 <= proof["maximum_slots"] < proof["required_slots"]):
                return False
            if (not isinstance(data.get("pools"), list) or not all(
                    isinstance(p, dict) and isinstance(p.get("meal_type"), str)
                    and type(p.get("qualified")) is int and type(p.get("raw")) is int
                    and 0 <= p["qualified"] <= p["raw"] for p in data["pools"])):
                return False
            for pool in data["pools"]:
                self.diagnostics.pools.append({**pool, "qualification_cache_hits": pool["qualified"]})
                self.diagnostics.singleton_passed += pool["qualified"]
            self.diagnostics.search.append({**proof, "cached_capacity_proof": True})
            return True
        except (ValueError, KeyError, TypeError):
            return False

    def _retain_capacity_proof(self, proof):
        from app.services.planner_context import content_digest

        key = self._capacity_artifact_key()
        if key is None or set(self._qualification_views) != {m.meal_type for m in self.spec.meals if m.count}:
            return
        views = {}
        for meal, view_key in self._qualification_views.items():
            view = self.artifacts.load("qualification", view_key)
            if view is None:
                return
            views[meal] = {"key": view_key, "sha256": content_digest(view)}
        self.artifacts.save("capacity_proof", key, {"proof": proof, "views": views,
            "pools": [{k: p[k] for k in ("meal_type", "raw", "qualified")}
                      for p in self.diagnostics.pools]})

    def _search_prepared_menu(self, prepared, evaluate, accepts, score):
        from app.services.verified_menu_search import SearchBudget, verified_search

        reference, winner = prepared["candidates"]

        def tracks(track, emit):
            if track == "reference":
                emit(reference, evaluate(reference, final=False))

        def audit(chosen):
            self._defer_search_audit = False
            try:
                return evaluate(chosen, final=True)
            finally:
                self._defer_search_audit = True

        chosen, result, report = verified_search(tracks, audit=audit,
            accepts=lambda chosen: accepts(chosen, final=True),
            rank=lambda chosen, value: (self._week_purchase_key(value["basket"]), score(chosen, value)),
            previous=((winner, evaluate(winner, final=False)),), budget=SearchBudget(1, 1))
        if (report["audit_rejected"] or report["constraint_rejected"]
                or money(result["basket"].total) != money(prepared["certificate"]["total"])):
            raise IncompleteBasketError("Prepared certificate needs ordinary requalification")
        self._library_search_handled = True
        self.diagnostics.search.append({"depth": len(chosen), "attempt": 1,
            "library_phase": "certificate_reaudit", "search_track": "reference_and_previous",
            "evaluations_executed": 0, "beam_pruned": 0})
        result["checks"]["verified_reference"] = {
            **report, "context": prepared["context"], "prepared_menu_hit": True,
            "publication_chain": "append_only_verified_metadata",
            "certificate": prepared["certificate"]["sha256"],
            "loaded_publications": prepared["chain_length"], "replayed_publications": 0,
            "qualification_scope": "cached_complete_library; selected recipes and joint basket rechecked",
        }
        return chosen, result

    def _retain_scope_incumbent(self, candidate, selected_scope, *, error=None):
        """Requalify the exact earlier checkout under the actual wider request."""
        expanded_diagnostics = self.diagnostics.snapshot()
        validated = self.basket(candidate.personal.slots, final=True, _retained=candidate)
        if validated["allocations"] != candidate.personal.allocations:
            raise PolicyConflict("Tidigare skafferifördelning kunde inte bevaras.")
        result = candidate.model_copy(deep=True, update={"optimized_basket": validated["basket"]})
        result.personal.checks.update(validated["checks"])
        result.personal.checks["checkout_audit"] = validated["audit"].model_dump(mode="json")
        result.personal.checks["allowed_store_ids"] = sorted(self.store_ids)
        result.personal.cache_identity = self._cache_identity(result.recipes)
        result.personal.checks["planning_diagnostics_scope"] = "selected_narrow_search"
        result.personal.checks["scope_comparison"] = {
            "selected_from_narrow_scope": True,
            "selected_scope": selected_scope,
            "target_scope": {"max_stores": self.request.max_stores,
                             "purchase_planning_mode": self.request.purchase_planning_mode},
            "exact_checkout_and_private_allocations_preserved": True,
            "target_audit_passed": validated["audit"].passed,
            "expanded_search_diagnostics": expanded_diagnostics,
            "expanded_search_error": ({"code": getattr(error, "code", "SEARCH_BLOCKED"),
                                       "message": str(error)} if error else None),
        }
        return result

    def _finalize_result(self, result, started):
        self.product_trace.finalize(result.optimized_basket)
        comparison = result.personal.checks.get("scope_comparison", {})
        if not comparison.get("selected_from_narrow_scope"):
            result.personal.checks["planning_diagnostics"] = self.diagnostics.snapshot()
        self.timings["total"] += perf_counter() - started
        if self.complete:
            from app.services.complete_recipes import completed_search_outcome
            result.personal.checks["timings_seconds"] = dict(self.timings)
            result.personal.checks["recipe_preferences"] = self.request.recipe_preferences.model_dump(mode="json")
            outcome = completed_search_outcome(result.personal.checks["planning_diagnostics"])
            if comparison.get("selected_from_narrow_scope"):
                outcome["diagnostics_scope"] = "selected_narrow_search"
                outcome["expanded_search_budget"] = completed_search_outcome(
                    comparison["expanded_search_diagnostics"])["search_budget"]
                if comparison["expanded_search_error"] or outcome["expanded_search_budget"]["nutrition_status"] == "REACHED":
                    outcome["budget_message"] = (outcome.get("budget_message") or "En giltig meny hittades.") + (
                        " Sökningen i det större tillåtna området gav ingen bättre giltig lösning; "
                        "den tidigare lösningen behölls och kontrollerades mot dina val.")
            result.personal.checks["search_outcome"] = outcome
        return result

    def _cache_identity(self, recipes):
        if getattr(self.settings, "library_search_policy", "legacy") == "smako-verified-reference-v1":
            from app.services.planner_context import content_digest, planner_context
            return content_digest([planner_context(self), recipes, self.library_generation])
        from app.services.recipe_week_variation import CLASSIFICATION_VERSION

        payload = {
            "policy": POLICY_VERSION,
            "week_classification": CLASSIFICATION_VERSION,
            "request": self.request.model_dump(mode="json"),
            "pantry_revision": self.state["revision"],
            "facts_policy_version": self.facts_version,
            "nutrition_reference_version": self.reference_version,
            "cooked_weight_evidence": self.cooked_weights,
            "state": self.state,
            "recipes": [r.model_dump() for r in recipes],
            "prices": self.prepared.universe.universe_id,
            "library_generation": self.library_generation,
            "freshness": self.view.cache_identity,
            "pricing_date": self.pricing_date.isoformat(),
            "memberships": self.user.cache_identity,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

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

    def _create(self, *, replace_slot=None, balanced_reference=None, _skip_prepared_menu=False):
        slots = self.spec.slots
        if slots is None:
            slots = [
                MealSlot(id=f"{meal.meal_type}-{day}", day=day, meal_type=meal.meal_type)
                for meal in self.spec.meals
                for day in range(1, meal.count + 1)
            ]
        generating = self.spec.slots is None
        if generating and replace_slot is None and self._reuse_capacity_proof():
            raise IncompleteBasketError("Den kvalificerade receptpoolen räcker inte för variationskravet.")
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
                include_content_pack=self.include_content_pack, library_generation=self.library_generation,
                artifacts=self.artifacts,
                previous_menus=self.previous_menus,
            ).create()
        prepared_menu = (self._prepared_menu_options(slots)
                         if generating and replace_slot is None and not _skip_prepared_menu else None)
        pools, options = {}, prepared_menu["options"] if prepared_menu else []
        # Transfer the exact first-slot qualifications to the existing bounded
        # beam cache. Private inputs and slot order are identical within this
        # invocation. Single-slot final checks and edited schedules are fresh.
        qualified_results = OrderedDict()
        for slot in ([] if prepared_menu else slots):
            if generating or slot.id == replace_slot:
                if slot.meal_type not in pools:
                    if (generating and len(slots) > 1 and slot is slots[0]
                            and hasattr(self._candidates, "__wrapped__")
                            and getattr(self._candidates, "__func__", None) is PersonalPlanner._candidates):
                        pools[slot.meal_type] = self._candidates(
                            self.meals[slot.meal_type], qualified_results=qualified_results)
                    elif (replace_slot and hasattr(self._candidates, "__wrapped__")
                          and getattr(self._candidates, "__func__", None)
                          is PersonalPlanner._candidates):
                        pools[slot.meal_type] = self._candidates(
                            self.meals[slot.meal_type],
                            fixed_slots=[s for s in slots if s.id != replace_slot])
                    else:
                        pools[slot.meal_type] = self._candidates(self.meals[slot.meal_type])
                choices = [
                    r
                    for r in pools[slot.meal_type]
                    if not slot.recipe or self._recipe_id(r) != self._recipe_id(slot.recipe)
                    if not (self.complete and slot.recipe and slot.recipe.design and r.design
                            and slot.recipe.design.base_id == r.design.base_id)
                ]
                if slot.id == replace_slot and not choices:
                    raise PolicyConflict(
                        "Ingen annan grundrätt kvalificerades med dina val. Den tidigare planrevisionen är bevarad. "
                        "Utöka matkök, tid eller ingrediensintervall uttryckligen, eller behåll rätten.",
                        code="RECIPE_ALTERNATIVE_NOT_FOUND", stage="variation")
                options.append([slot.model_copy(update={"recipe": r}) for r in choices])
            else:
                options.append([slot])
        dinner_pool = list(
            {
                self._recipe_id(s.recipe): s.recipe
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
        if self.complete:
            from app.services.complete_recipes import diversity_policy
            policy = diversity_policy(self.request, policy)
        if dinner_count < 2:
            policy = policy.model_copy(update={"min_cooking_methods": 0})
        constraints = (self.service._culinary_constraints(dinner_pool, policy, profiles=prepared_menu["culinary_profiles"])
                       if prepared_menu else self.service._culinary_constraints(dinner_pool, policy))
        self._qualified_culinary_view = constraints.pairwise_recipe_similarities
        if self.complete and prepared_menu is None:
            self._release_idle_memory()
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
            # During a one-slot replacement every remaining slot is fixed.
            # Reject only provably incompatible completions before they occupy
            # the bounded beam. Keep actual pricing/allocation in original order.
            constraint_slots = chosen
            constraint_final = final
            if replace_slot and any(s.id == replace_slot for s in chosen) and not final:
                suffix = options[len(chosen):]
                if all(len(group) == 1 for group in suffix):
                    constraint_slots = [*chosen, *(group[0] for group in suffix)]
                    constraint_final = True
            for meal_type, meal in self.meals.items():
                if meal.max_same_base_meals is None:
                    continue
                counts = Counter((s.recipe.design.base_id if s.recipe.design else self._recipe_id(s.recipe))
                                 for s in constraint_slots if s.meal_type == meal_type and s.recipe)
                if any(count > meal.max_same_base_meals for count in counts.values()):
                    self.diagnostics.branch(len(chosen), "variation")
                    return False
            if not distribution_ok(constraint_slots, self.spec.meals, partial=not constraint_final or draft,
                                   classify=self._protein_category):
                self.diagnostics.branch(len(chosen), "policy_taste")
                return False
            dinners = [s.recipe for s in constraint_slots if s.meal_type == "dinner" and s.recipe]
            if self.complete:
                from app.services.recipe_week_variation import accepts_week
                if not accepts_week(dinners, self.request.recipe_preferences,
                                    dinner_count=dinner_count, final=constraint_final and not draft):
                    self.diagnostics.branch(len(chosen), "variation")
                    return False
            if len({self._recipe_id(r) for r in dinners}) != len(dinners):
                self.diagnostics.branch(len(chosen), "variation")
                return False
            if self.complete and len({r.design.base_id for r in dinners}) != len(dinners):
                self.diagnostics.branch(len(chosen), "variation")
                return False
            # Repeated breakfasts/snacks are permitted. Dinner variation follows
            # the existing actual ingredient/preparation constraints.
            accepted = self.service.menu_optimizer.accepts_recipes(
                dinners, constraints, profile_cache=self.recipe_computations)
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
                    and not self.complete
                    and chosen[0].recipe
                    and not self.meals[chosen[0].meal_type].limits.active
                ):
                    self.diagnostics.reject(stage, chosen[0].recipe, str(exc))
                raise
            if (
                len(chosen) == 1
                and generating
                and not self.complete
                and not self.meals[chosen[0].meal_type].limits.active
            ):
                self.diagnostics.singleton_passed += 1
            if final and ceiling is not None and result["basket"].total > ceiling:
                raise PolicyConflict(
                    f"Varierad överskrider vald kostnadsgräns {ceiling:.2f} kr för hela korgen. Balanserad kostar {balanced_reference.optimized_basket.total:.2f} kr."
                )
            return result

        search_started = perf_counter()
        from app.services.plan_jobs import report_stage
        report_stage("week_search")
        from app.services.menu_optimizer import MenuOptimizer
        incremental_library = (
            prepared_menu is None and self.complete and generating and self.include_content_pack and replace_slot is None
            and getattr(self._candidates, "__func__", None) is PersonalPlanner._candidates
            and type(self.service.menu_optimizer) is MenuOptimizer
            and getattr(self.service.menu_optimizer.optimize_slots, "__func__", None) is MenuOptimizer.optimize_slots
        )
        search = self.service.menu_optimizer.optimize_slots
        search_input, library_kwargs = options, {}
        if incremental_library:
            from app.services.library_search_cohorts import per_package_cohorts
            from app.services.recipe_library import current_recipe_generations
            generations = current_recipe_generations(self.library_generation)
            first = 1 if self.request.diversity_mode == "cheapest" else min(2, self._generation)
            if getattr(self.settings, "library_merge_generations", False):
                from app.services.library_search_cohorts import merged_library_cohorts
                from app.services.recipe_library import current_recipes

                search_input, completed, prefixes, probes = merged_library_cohorts(
                    options, current_recipes(self.library_generation), generations, first_generation=first)
                library_kwargs.update(completed_prefix_indexes=completed, cohort_prefix_sizes=prefixes,
                                      checkpoint_probe_indexes=probes)
            else:
                search_input = per_package_cohorts(options, generations,
                    first_generation=first, last_generation=self._generation)
            search = self.service.menu_optimizer.optimize_library_slots
            library_kwargs["retention_score"] = lambda chosen, result: (result["basket"].total, score(chosen, result))
            from app.services.week_refinement import qualified_joint_proposals
            library_kwargs["refinement_score"] = lambda chosen, result: (
                self._week_purchase_key(result["basket"]), score(chosen, result))
            library_kwargs["joint_proposals"] = lambda groups, anchor: qualified_joint_proposals(
                groups, anchor, self.variant_search_evidence)
            def select_seed_options(groups, *, refinement=False):
                if refinement:
                    return self._select_library_options(
                        groups, limit=getattr(self.settings, "library_refinement_pool_limit", 90),
                        shortlist_variants=False)
                return self._select_library_options(
                    groups, limit=getattr(self.settings, "library_seed_pool_limit", 40),
                    shortlist_variants=getattr(self.settings, "library_seed_variant_shortlist", True))
            library_kwargs["seed_selector"] = select_seed_options
            if getattr(self.settings, "library_refinement_pool_limit", 90):
                library_kwargs["refinement_selector"] = lambda groups: select_seed_options(groups, refinement=True)
            substitution_limit = getattr(self.settings, "library_substitution_pool_limit", 160)
            if substitution_limit:
                # Same ranking as the seed cap (cheapest single-recipe purchase,
                # shared packages, two per cuisine), over one generation's
                # additions. No variant shortlist: a generation within the
                # limit is tried in full, exactly as before.
                library_kwargs["substitution_selector"] = lambda groups: self._select_library_options(
                    groups, limit=substitution_limit, shortlist_variants=False)
            screen_margin = getattr(self.settings, "library_substitution_screen_margin", -1.0)
            if screen_margin >= 0:
                library_kwargs["substitution_screen"] = lambda chosen, incumbent, index: self._screen_substitution(
                    chosen, incumbent, index, screen_margin)
            slot_limit = getattr(self.settings, "library_substitution_slot_limit", 0)
            if slot_limit:
                library_kwargs["substitution_order"] = self._predicted_substitution
                library_kwargs["substitution_slot_limit"] = slot_limit
            if (getattr(self.settings, "library_merge_generations", False)
                    and generating and not self.items and not self.spec.product_locks):
                from app.services.library_search_cohorts import SMALL_POOL_LIMIT

                library_kwargs["unordered_small_pool_limit"] = SMALL_POOL_LIMIT
            self._library_search_handled = True
        search_kwargs = dict(
                **library_kwargs,
                evaluate=evaluate,
                accepts=accepts,
                score=score,
                beam_width=8,
                fallback_beam_width=64,
                search_trace=self.diagnostics.search,
                decision_observer=self.product_trace.search_decision,
                initial_evaluations=qualified_results,
                # Generated meals of one type share requirements. With no pantry
                # allocation or product locks, permuting their day numbers cannot
                # change the whole basket or per-recipe nutrient constraints.
                # Explicit edited schedules and private allocations remain ordered.
                state_identity=(
                    lambda chosen: tuple(sorted(
                        (s.meal_type, self._recipe_id(s.recipe) if s.recipe else "") for s in chosen
                    ))
                ) if generating and not self.items and not self.spec.product_locks else None,
            )
        # Complete menus compared during the search are not audited; only the
        # chosen menu is, below. Should it fail the audit (not observed), the
        # search is repeated with every complete menu audited, which is the
        # previous behaviour, so an unaudited menu can never be returned.
        self._defer_search_audit = True
        try:
            with performance_span("personal_week_search"):
                capacity = (self.service.menu_optimizer.dish_form_capacity_conflict(
                    dinner_pool, constraints, dinner_count)
                    if type(self.service.menu_optimizer) is MenuOptimizer and prepared_menu is None else None)
                if capacity is not None:
                    self.diagnostics.branch(dinner_count, "variation")
                    self.diagnostics.search.append({
                        "depth": dinner_count, "attempt": 1, "beam_width": 0,
                        "library_phase": "capacity_check", "status": "PROVEN_INFEASIBLE",
                        "scope": "qualified_dinner_pool",
                        "proposals": 0, "priced": 0, "retained": 0, "beam_pruned": 0,
                        "evaluations_executed": 0, "evaluation_cache_hits": 0,
                        "constraints_rejected": 1, "evaluation_rejected": 0, **capacity,
                    })
                    if incremental_library:
                        self._retain_capacity_proof(dict(self.diagnostics.search[-1]))
                    raise IncompleteBasketError("Den kvalificerade receptpoolen räcker inte för variationskravet.")
                if prepared_menu is not None:
                    try:
                        chosen, result = self._search_prepared_menu(prepared_menu, evaluate, accepts, score)
                    except (ValueError, IncompleteBasketError):
                        self.diagnostics.singleton_passed -= sum(p["qualified"] for p in
                            self.diagnostics.pools if p.get("reused_library_certificate"))
                        self.diagnostics.pools[:] = [p for p in self.diagnostics.pools
                                                     if not p.get("reused_library_certificate")]
                        return self._create(replace_slot=replace_slot, balanced_reference=balanced_reference,
                                            _skip_prepared_menu=True)
                elif (incremental_library
                        and getattr(self.settings, "library_search_policy", "legacy") == "smako-verified-reference-v1"):
                    chosen, result = self._search_verified_reference(options, search_kwargs)
                elif self.previous_menus:
                    chosen, result = self._search_with_previous_menus(search, search_input, options, search_kwargs)
                else:
                    chosen, result = search(search_input, **search_kwargs)
        finally:
            self._defer_search_audit = False
        self.timings["week_search"] += perf_counter() - search_started
        # Recheck every final constraint even if the cache supplied a beam result.
        report_stage("final_audit")
        try:
            verified_reference = result.get("checks", {}).get("verified_reference")
            previous_menu_audit = result.get("checks", {}).get("reaudited_previous_menu")
            result = self.basket(chosen, final=True)
            if verified_reference is not None:
                result["checks"]["verified_reference"] = verified_reference
            if previous_menu_audit is not None:
                result["checks"]["reaudited_previous_menu"] = previous_menu_audit
        except PolicyConflict as exc:
            if not str(exc).startswith(_AUDIT_FAILURE):
                raise
            with performance_span("personal_week_search"):
                chosen, result = search(search_input, **search_kwargs)
            result = self.basket(chosen, final=True)
            result["checks"]["audited_search_retry"] = True
        if not accepts(chosen, final=True):
            raise PolicyConflict("Slutlig fördelning eller variation kunde inte verifieras.")
        recipes = [s.recipe for s in chosen if s.recipe]
        result["checks"]["checkout_audit"] = result["audit"].model_dump(mode="json")
        result["checks"]["allowed_store_ids"] = sorted(self.store_ids)
        from app.services.week_refinement import surplus_summary
        result["checks"]["purchase_surplus"] = {
            **surplus_summary(result["basket"]),
            "tie_break_enabled": self.spec.surplus_mode == "minimize",
            "description": "Kvarvarande andel av betald varukostnad, utan pant. Jämförs först vid samma inköpssumma; dras aldrig av från köpbeloppet. Mängder i olika enheter redovisas separat.",
        }
        if self.complete:
            from app.services.recipe_week_variation import week_summary
            result["checks"]["week_distribution"] = week_summary(
                [s.recipe for s in chosen if s.meal_type == "dinner" and s.recipe])
            result["checks"]["recipe_variation_policy"] = {
                **policy.model_dump(mode="json"),
                "description": "Rättfamilj, huvudråvara, beredning, sås/smakprofil och tillbehör bedöms tillsammans. Samma ris eller kastrull är inte ensamt en upprepning. Uttryckliga begränsningar gäller fortfarande.",
            }
            purchased_items = [item for store in result["basket"].stores for item in store.items]
            cost_known = all(item.merchandise_total is not None and item.purchased_usable_quantity for item in purchased_items)
            used_cost = (float(money(sum(item.merchandise_total * item.required_quantity / item.purchased_usable_quantity
                                       for item in purchased_items))) if cost_known else None)
            result["checks"]["new_purchase_used_cost"] = used_cost
            result["checks"]["used_ingredient_cost"] = used_cost if not result["allocations"] else None
            result["checks"]["used_cost_basis"] = {
                "method": "proportional_allocation_of_paid_merchandise_cost_to_used_usable_quantity",
                "deposit_included": False,
                "pantry_cost_status": "UNKNOWN" if result["allocations"] else "NOT_USED",
                "quantity_status": "ESTIMATED" if any(i.quantity_confidence == "estimated" for i in purchased_items) else "VERIFIED",
                "description": "Varukostnad utan pant fördelad efter använd andel av inköpt användbar mängd. Skafferiets tidigare inköpspris är okänt. Resternas framtida värde dras inte av från köpbeloppet.",
            }
            result["checks"]["ingredient_product_details"] = []
            for item in purchased_items:
                product = self.prepared.universe.products[self.by_identity[(item.store_id, item.product_id)]]
                fact = self.source_facts(product)
                result["checks"]["ingredient_product_details"].append({
                    "ingredient": item.ingredient, "product_name": item.product_name,
                    "ingredients": list(fact.ingredients) if fact else [],
                    "ingredients_complete": bool(fact and fact.ingredients_complete),
                    "allergens_present": list(fact.allergens_present) if fact else [],
                    "allergens_trace": list(fact.allergens_trace) if fact else [],
                    "source": fact.source if fact else None,
                })
        self._trace_final_alternatives(chosen, result)
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
        digest = self._cache_identity(recipes)
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
            usable_context_ids=self.store_ids,
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
            membership_programs_used=(tuple(sorted({
                program for group in basket.stores for item in group.items
                for program in [item.membership_program, *(a.group.membership_program for a in item.group_applications)]
                if program is not None
            }, key=lambda p: p.value)) if self.request.membership_price_policy == "all_advertised" else self.user.memberships),
            data_source="price-universe-offline",
            data=PlanPriceData(
                **status.model_dump(exclude={"hours_until_oldest_usable_stale"}),
                pricing_timestamp=datetime.now(UTC),
                compared_price_contexts=compared,
                excluded_price_contexts=excluded,
            ),
            recipe_source="versioned-complete-library+personal-planning" if self.complete else "deterministic-candidates+personal-planning",
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
