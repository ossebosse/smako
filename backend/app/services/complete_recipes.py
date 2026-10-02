"""Request translation and hard authored-recipe boundaries, using PersonalPlanner.

There is no second price engine. Public dinners become private meal slots before
admission and persistence so the exact same policies survive later revisions.
"""
from __future__ import annotations

import re

from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.services.personal_policy import PolicyConflict


def enabled(request):
    return bool(request.recipe_preferences and request.recipe_preferences.mode == "complete")


def prepare_request(request, settings, *, pantry_revision=0):
    if not enabled(request):
        return request
    if not settings.complete_recipes_enabled:
        raise PolicyConflict("Genomarbetade middagar är inte aktiverade i denna miljö. Välj befintligt receptläge.", code="FEATURE_DISABLED")
    prefs = request.recipe_preferences
    if request.personal is None:
        spec = PersonalPlanning(
            meals=[MealSettings(count=request.recipes, servings=request.servings,
                                diet=request.diet_preference.value if request.diet_preference.value in {"vegetarian", "vegan"} else "mixed")],
            pantry_revision=pantry_revision,
            allow_nutrition_estimates=request.allow_nutrition_estimates,
            use_pantry=request.use_pantry,
        )
    else:
        spec = request.personal.model_copy(deep=True)
    for meal in spec.meals:
        if meal.meal_type != "dinner" or not meal.count:
            continue
        if request.diet_preference.value in {"vegetarian", "vegan"} and meal.diet != request.diet_preference.value:
            raise PolicyConflict("Måltidens kostval strider mot planens kostval. Använd samma kostinriktning i båda valen.", code="RECIPE_CHOICES_CONFLICT")
        if not prefs.allow_fish and meal.distribution.get("fish", 0):
            raise PolicyConflict("Fisk är avstängd men ingår i vald fördelning. Ta bort fiskmåltiderna eller tillåt fisk.", code="RECIPE_CHOICES_CONFLICT")
        if prefs.min_protein_g is not None:
            limits = meal.limits.model_dump()
            limits["min_protein_g"] = max(prefs.min_protein_g, meal.limits.min_protein_g or 0)
            if limits["max_protein_g"] is not None and limits["max_protein_g"] < limits["min_protein_g"]:
                raise PolicyConflict("Proteinmålet överstiger måltidens maxgräns. Ändra en av proteingränserna.", code="RECIPE_CHOICES_CONFLICT")
            meal.limits = PortionLimits.model_validate(limits)
    return request.model_copy(update={"personal": spec, "strategy": "optimized"})


def identity(recipe):
    d = recipe.design
    return f"{d.base_id}:{d.version}:{d.variant_id}" if d else None


def matches_preferences(recipe, preferences):
    from app.services.recipe_library import ingredient_count, validate_recipe_design

    validate_recipe_design(recipe)
    d = recipe.design
    if not d or preferences.cuisines and not set(preferences.cuisines) & set(d.cuisines):
        return False
    if not preferences.min_ingredients <= ingredient_count(recipe) <= preferences.max_ingredients:
        return False
    if preferences.max_minutes is not None and d.estimated_minutes > preferences.max_minutes:
        return False
    from app.services.personal_policy import protein_category
    if not preferences.allow_fish and protein_category(recipe) == "fish":
        return False
    return not (preferences.adaptation == "products" and d.variant_id != "base")


def product_form_compatible(recipe, name, product, fact):
    """Apply raw/dry/drained boundaries even without a nutrition target.

    Existing semantic matching remains authoritative; this only tightens it for
    the explicit input form in an immutable authored recipe.
    """
    if not getattr(recipe, "design", None):
        return True
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    canonical = canonicalize_ingredient_name(name)
    form = recipe.preparation.input_forms.get(canonical)
    if not form or (product.purchase_terms and product.purchase_terms.identity_scope == "campaign_group"):
        return False
    text = product.name.casefold()
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    if form == "raw_edible" and re.search(r"torkad|pulver|granulat|kokt|grillad|stekt|panerad|nugget|rökt|gravad|rimmad|marinerad", text):
        return False
    if form == "dry" and (re.search(r"kokt|färdig|konserv|avrun", text) or "vatten" in composition):
        return False
    if form == "cooked_drained":
        return bool(fact and any(e.get("basis") == "drained" and e.get("unit") == "g"
                                and e.get("quantity") == product.usable_quantity and e.get("source")
                                for e in fact.field_sources.get("usable_quantity", ())))
    return True
