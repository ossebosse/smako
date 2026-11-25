"""Scaled siblings of recipes with reviewed ranges (owner decision 2026-11-24).

A recipe whose main ingredient or side has a reviewed range
(``quantity_min < quantity_max``, see docs/recipes/AUTHORING.md) gets a few
scaled versions when the library is loaded: more of the main ingredient and/or
less of the side, on the reviewed grid. They are ordinary recipes with their
own identity (``<variant>-m125s100``), so preparation, indexes, product,
nutrition and price checks treat them like any other recipe. Planning offers
them only to a meal with nutrition limits (``recipe_library.meal_candidates``)
and prefers the closest one (``PlanningRules.scaled_step_kr`` per grid step).
Step texts are reviewed for the whole range and are not changed.

Owner decision 2026-11-25: an ingredient with ``scales_with`` (seasoning,
marinade, cooking fat used with the main ingredient) follows it. Only its
amount in the components that hold the main ingredient scales, by the same
factor, so salt shared with a side stays right for the side.
"""

from __future__ import annotations

import math

SCALED_ROLES = {"primary": "main", "side": "side"}
# (main factor, side factor); "min" is the side's reviewed minimum.
SHAPES = ((1.25, 1.0), (1.5, 1.0), (1.25, "min"), (1.0, "min"))


def is_scalable(recipe) -> bool:
    """Ranges reviewed for scaling (``design.scaling``); older flexible families are not."""
    return bool(recipe.design) and recipe.design.scaling == "reviewed_ranges" and any(
        i.role in SCALED_ROLES and i.quantity_min is not None and i.quantity_max is not None
        and i.quantity_min < i.quantity_max for i in recipe.ingredients)


def is_scaled(recipe) -> bool:
    return bool(recipe.design and recipe.design.scaled_from)


def _snap(ingredient, target):
    step = ingredient.quantity_step or 1.0
    steps = math.floor(round((target - ingredient.quantity) / step, 6)) if target >= ingredient.quantity \
        else -math.floor(round((ingredient.quantity - target) / step, 6))
    value = ingredient.quantity + steps * step
    return round(min(ingredient.quantity_max, max(ingredient.quantity_min, value)), 4)


def _ranged(ingredient):
    return (ingredient.role in SCALED_ROLES and ingredient.quantity_min is not None
            and ingredient.quantity_max is not None and ingredient.quantity_min < ingredient.quantity_max)


def scaled_versions(recipe):
    """Scaled siblings of one recipe, closest first; none for a recipe without ranges."""
    from app.services.recipe_library import content_hash

    if not is_scalable(recipe) or is_scaled(recipe):
        return []
    seen, result = set(), []
    for main, side in SHAPES:
        quantities = {}
        for i in recipe.ingredients:
            if not _ranged(i):
                continue
            factor = main if SCALED_ROLES[i.role] == "main" else side
            quantities[i.name] = i.quantity_min if factor == "min" else _snap(i, i.quantity * factor)
        changed = {n: q for n, q in quantities.items()
                   if abs(q - next(i.quantity for i in recipe.ingredients if i.name == n)) > 1e-9}
        signature = tuple(sorted(changed.items()))
        if not changed or signature in seen:
            continue
        seen.add(signature)
        result.append(_scaled_copy(recipe, changed, content_hash))
    result.sort(key=lambda r: (r.design.scale_steps, r.design.variant_id))
    # Two shapes can differ only in a second main ingredient and get the same name;
    # keep the closest one so every identity is unique.
    unique = {}
    for r in result:
        unique.setdefault(r.design.variant_id, r)
    return list(unique.values())


def follower_amount(value):
    """Round a scaled seasoning to what a cook measures."""
    precision = 0.5 if value < 10 else 1.0 if value < 100 else 5.0
    return max(precision, round(round(value / precision) * precision, 4))


def _scaled_copy(recipe, changed, content_hash):
    d = recipe.design
    ratio, steps = {}, 0
    for i in recipe.ingredients:
        if i.name in changed:
            ratio[f"{i.canonical_name}|{i.form}"] = changed[i.name] / i.quantity
            steps += round(abs(changed[i.name] - i.quantity) / (i.quantity_step or 1.0))
    # Followers scale only in the components that hold the main ingredient they follow.
    holders = {key: {c.id for c in d.components if any(a.ingredient_key == key for a in c.amounts)} for key in ratio}
    new_amounts = {}
    for c in d.components:
        for n, a in enumerate(c.amounts):
            if a.ingredient_key in ratio:
                new_amounts[(c.id, n)] = round(a.quantity * ratio[a.ingredient_key], 6)
    for i in recipe.ingredients:
        key = f"{i.canonical_name}|{i.form}"
        if i.scales_with in ratio and key not in ratio:
            for c in d.components:
                if c.id not in holders[i.scales_with]:
                    continue
                for n, a in enumerate(c.amounts):
                    if a.ingredient_key == key:
                        new_amounts[(c.id, n)] = follower_amount(a.quantity * ratio[i.scales_with])
    components = tuple(c.model_copy(update={"amounts": tuple(
        a.model_copy(update={"quantity": new_amounts[(c.id, n)]}) if (c.id, n) in new_amounts else a
        for n, a in enumerate(c.amounts))}) for c in d.components)
    totals = {}
    for c in components:
        for a in c.amounts:
            totals[a.ingredient_key] = totals.get(a.ingredient_key, 0.0) + a.quantity
    ingredients = []
    for i in recipe.ingredients:
        key = f"{i.canonical_name}|{i.form}"
        if i.name in changed:
            ingredients.append(i.model_copy(update={"quantity": changed[i.name]}))
        elif i.scales_with in ratio and key in totals and abs(totals[key] - i.quantity) > 1e-9:
            q = round(totals[key], 6)
            ingredients.append(i.model_copy(update={"quantity": q, "quantity_min": min(i.quantity_min or q, q),
                                                    "quantity_max": max(i.quantity_max or q, q)}))
        else:
            ingredients.append(i)
    main = next((i for i in recipe.ingredients if i.role == "primary" and i.name in changed), None)
    side = next((i for i in recipe.ingredients if i.role == "side" and i.name in changed), None)
    tag = f"m{round(100 * changed[main.name] / main.quantity) if main else 100}s{round(100 * changed[side.name] / side.quantity) if side else 100}"
    design = d.model_copy(update={"variant_id": f"{d.variant_id}-{tag}", "components": components,
                                  "scaled_from": d.variant_id, "scale_steps": steps,
                                  "content_sha256": "0" * 64})
    copy = recipe.model_copy(update={"ingredients": ingredients, "instructions": list(recipe.instructions),
                                     "design": design})
    sha = content_hash(copy)
    copy = copy.model_copy(update={"design": design.model_copy(update={"content_sha256": sha})})
    if recipe.preparation is not None:
        copy = copy.model_copy(update={"preparation": recipe.preparation.model_copy(update={
            "parent_sha256": sha, "input_forms": dict(recipe.preparation.input_forms)})})
    return copy


def with_scaled_versions(recipes):
    """The recipes followed by the scaled siblings of those with reviewed ranges."""
    recipes = list(recipes)
    extra = [s for r in recipes for s in scaled_versions(r)]
    return recipes + extra


def nutrition_limited(meal) -> bool:
    limits = getattr(meal, "limits", None)
    return bool(limits) and any(getattr(limits, f) is not None for f in (
        "min_protein_g", "max_protein_g", "min_carbs_g", "max_carbs_g", "min_fat_g", "max_fat_g", "max_kcal"))
