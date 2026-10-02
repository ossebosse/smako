"""Original, versioned complete dinners. No runtime model call or price engine.

Content is immutable application data; candidates are exact registered portions
and approved variations. Product declarations and the existing planner still
decide nutrition, allergens, purchase feasibility and economic selection.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.models.recipe import Recipe, RecipePreparation
from app.models.recipe_preferences import RecipePreferences

LIBRARY_VERSION = "smako-complete-dinners-v1"
LIBRARY_PATH = Path(__file__).parents[1] / "data/recipes/complete-dinners-v1.json"
# Updated only together with reviewed, versioned source content.
CONTENT_SHA256 = "b27912d63f05f993635d4a3516a4e1bba0fa94acd5f682a258eeccdacb4efd07"
COUNT_EXEMPT = frozenset({"salt", "svartpeppar", "peppar", "vatten"})
ARCHIVED_CONTENT = {
    "complete-dinners-1.0.0.json": "4baec1580728294b2805e3716b719d68b2d12ca0f2cbdc469bb074769700de66",
}


def ingredient_key(ingredient) -> str:
    return f"{ingredient.canonical_name or ingredient.name}|{ingredient.form or 'unspecified'}"


def ingredient_count(recipe: Recipe) -> int:
    return len({ingredient_key(i) for i in recipe.ingredients
                if (i.canonical_name or i.name) not in COUNT_EXEMPT})


def content_hash(recipe: Recipe) -> str:
    value = recipe.model_dump(mode="json", exclude={"preparation"})
    if value.get("design"):
        value["design"].pop("content_sha256", None)
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def _structural_check(recipe: Recipe) -> None:
    d = recipe.design
    if d is None:
        raise ValueError("Receptet saknar versionsbundet innehåll.")
    keys = {ingredient_key(i) for i in recipe.ingredients}
    if len(keys) != len(recipe.ingredients):
        raise ValueError("Samla samma ingrediens och form innan antal och köp beräknas.")
    if len({i.canonical_name for i in recipe.ingredients}) != len(keys):
        raise ValueError("Olika former av samma råvara kräver separata kvalificerade identiteter.")
    components = {c.id for c in d.components}
    if len(components) != len(d.components):
        raise ValueError("Komponent-ID:n måste vara unika.")
    for i in recipe.ingredients:
        if not i.canonical_name or not i.form or i.component not in components:
            raise ValueError("Ingrediensen saknar identitet, form eller komponent.")
        if i.unit not in {"g", "ml"} or (i.form != "as_sold" and i.unit != "g"):
            raise ValueError("Mängden kräver en uttryckligt kvalificerad gram-/volymgrund.")
        if not (i.quantity_min and i.quantity_max and i.quantity_step):
            raise ValueError("Ingrediensen saknar godkänt mängdintervall.")
        if not i.quantity_min <= i.quantity <= i.quantity_max:
            raise ValueError("Mängden ligger utanför receptets godkända intervall.")
    if d.ingredient_count != ingredient_count(recipe):
        raise ValueError("Ingrediensantalet stämmer inte med hela rätten.")
    ends: dict[str, int] = {}
    used: set[str] = set()
    for step in d.steps:
        if step.id in ends or not set(step.depends_on) <= ends.keys():
            raise ValueError("Tillagningsplanen har en cykel eller okänt beroende.")
        if not set(step.ingredient_keys) <= keys:
            raise ValueError("Instruktionerna använder en ingrediens som inte finns i receptet.")
        used.update(step.ingredient_keys)
        ends[step.id] = max((ends[k] for k in step.depends_on), default=0) + step.duration_minutes
    if used != keys or not ends:
        raise ValueError("Varje ingrediens måste användas i den dokumenterade tillagningen.")
    if max(ends.values()) > d.estimated_minutes:
        raise ValueError("Beroendena ryms inte inom den uppskattade tillagningstiden.")
    if recipe.instructions != [s.text for s in d.steps]:
        raise ValueError("Visade instruktioner skiljer sig från den granskade tillagningsplanen.")
    if content_hash(recipe) != d.content_sha256:
        raise ValueError("Receptets innehåll har ändrats utan ny granskad version.")
    p = recipe.preparation
    if (p is None or p.parent_sha256 != d.content_sha256 or p.family != d.family
            or p.input_forms != {i.canonical_name: i.form for i in recipe.ingredients}):
        raise ValueError("Beredningsmetoden är inte bunden till receptets exakta innehåll.")


@lru_cache(maxsize=1)
def _registered() -> tuple[Recipe, ...]:
    raw = LIBRARY_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CONTENT_SHA256:
        raise ValueError("Receptbibliotekets kontrollsumma avviker från granskad utgåva.")
    payload = json.loads(raw)
    if payload["library_version"] != LIBRARY_VERSION:
        raise ValueError("Okänd receptutgåva.")
    result = tuple(Recipe.model_validate(r) for r in payload["recipes"])
    identities = set()
    for recipe in result:
        _structural_check(recipe)
        identity = (recipe.design.base_id, recipe.design.version, recipe.design.variant_id)
        if identity in identities:
            raise ValueError("Receptversionen förekommer flera gånger.")
        identities.add(identity)
    return result


@lru_cache(maxsize=1)
def _registered_history() -> tuple[Recipe, ...]:
    """Retain validation of issued plans when current authoring advances."""
    result = list(_registered())
    for filename, digest in ARCHIVED_CONTENT.items():
        raw = LIBRARY_PATH.with_name(filename).read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("En arkiverad receptutgåva har ändrats.")
        for value in json.loads(raw)["recipes"]:
            recipe = Recipe.model_validate(value)
            _structural_check(recipe)
            result.append(recipe)
    return tuple(result)


def _scaled(recipe: Recipe, servings: int) -> Recipe:
    factor = servings / recipe.servings
    ingredients = [i.model_copy(update={
        key: round(getattr(i, key) * factor, 8)
        for key in ("quantity", "quantity_min", "quantity_max", "quantity_step")
    }) for i in recipe.ingredients]
    result = recipe.model_copy(deep=True, update={"servings": servings, "ingredients": ingredients})
    if servings > 2 and result.design.version != "1.0.0":
        # More chopping/weighing for four portions is real work, even when the
        # oven or a large pot can accommodate the full batch without extra heat.
        extra_prep = ((servings - 1) // 2) * 3
        steps = list(result.design.steps)
        steps[0] = steps[0].model_copy(update={
            "duration_minutes": steps[0].duration_minutes + extra_prep,
            "text": steps[0].text + f" För {servings} portioner är {extra_prep} extra minuter "
            "för vägning och beredning inräknade i tidsuppskattningen.",
        })
        result = result.model_copy(update={
            "design": result.design.model_copy(update={
                "steps": tuple(steps), "estimated_minutes": result.design.estimated_minutes + extra_prep,
            }),
            "instructions": [s.text for s in steps],
        })
    if servings > 4:
        # A larger pan is not an implicit unlimited cooking resource. Reserve
        # sequential batches and show that allowance instead of silently keeping
        # the two-person time estimate for twelve portions.
        batches = (servings + 3) // 4
        steps = list(result.design.steps)
        heat = next((index for index, step in enumerate(steps)
                     if index > 0 and step.duration_minutes >= 10), 0)
        original = steps[heat]
        extra = original.duration_minutes * (batches - 1)
        steps[heat] = original.model_copy(update={
            "duration_minutes": original.duration_minutes + extra,
            "text": original.text + f" För {servings} portioner: tillaga i {batches} omgångar "
            "om allt inte ryms med samma djup i panna eller form. Håll färdig mat varm. "
            f"Tidsuppskattningen inkluderar {extra} minuter för omgångarna.",
        })
        result = result.model_copy(update={
            "design": result.design.model_copy(update={
                "steps": tuple(steps), "estimated_minutes": result.design.estimated_minutes + extra,
            }),
            "instructions": [s.text for s in steps],
        })
    digest = content_hash(result)
    result = result.model_copy(update={"design": result.design.model_copy(update={"content_sha256": digest})})
    return result.model_copy(update={"preparation": RecipePreparation(
        version="smako-edible-input-v1", origin="smako_recipe_design", parent_sha256=digest,
        family=result.design.family,
        input_forms={i.canonical_name: i.form for i in ingredients},
    )})


@lru_cache(maxsize=12)
def _registered_portions(servings: int) -> tuple[Recipe, ...]:
    if not 1 <= servings <= 12:
        raise ValueError("Antal portioner måste vara mellan 1 och 12.")
    return tuple(_scaled(r, servings) for r in _registered())


@lru_cache(maxsize=12)
def _registered_historical_portions(servings: int) -> tuple[Recipe, ...]:
    if not 1 <= servings <= 12:
        raise ValueError("Antal portioner måste vara mellan 1 och 12.")
    return tuple(_scaled(r, servings) for r in _registered_history())


def validate_recipe_design(recipe: Recipe) -> bool:
    """Only exact issued versions qualify; a self-computed hash cannot approve edits."""
    if recipe.design is None:
        return False
    _structural_check(recipe)
    d = recipe.design
    registered = next((r for r in _registered_historical_portions(recipe.servings)
                       if (r.design.base_id, r.design.version, r.design.variant_id)
                       == (d.base_id, d.version, d.variant_id)), None)
    if registered is None or registered.model_dump() != recipe.model_dump():
        raise ValueError("Receptversionen eller mängden saknar godkänd innehållsgranskning.")
    return True


def candidates(preferences: RecipePreferences, servings: int = 2) -> list[Recipe]:
    """Return complete allowed candidates; nutrition targets are qualified downstream."""
    if preferences.mode != "complete":
        return []
    return [r.model_copy(deep=True) for r in _registered_portions(servings)
            if (not preferences.cuisines or set(r.design.cuisines) & set(preferences.cuisines))
            and preferences.min_ingredients <= r.design.ingredient_count <= preferences.max_ingredients
            and (preferences.max_minutes is None or r.design.estimated_minutes <= preferences.max_minutes)
            and (preferences.allow_fish or not r.design.fish)
            and (preferences.adaptation == "approved" or r.design.variant_id == "base")]


def validate_library() -> dict:
    recipes = _registered()
    base = [r for r in recipes if r.design.variant_id == "base"]
    return {
        "library_version": LIBRARY_VERSION,
        "content_sha256": CONTENT_SHA256,
        "base_recipes": len(base), "approved_variants": len(recipes) - len(base),
        "by_cuisine": dict(Counter(r.design.cuisines[0] for r in base)),
        "vegetarian_by_cuisine": dict(Counter(r.design.cuisines[0] for r in base if r.design.vegetarian)),
        "structural_validation": "passed", "content_review": "model_assisted_review",
        "cooking_test": "not_cooked", "purchase_qualification": "performed_by_planner_per_snapshot",
        "nutrition_qualification": "performed_by_planner_per_product_and_user_consent",
    }


def library_version() -> str:
    return f"{LIBRARY_VERSION}:{CONTENT_SHA256}"


def library_summary() -> dict:
    return {**validate_library(), "ingredient_bounds": {"min": 3, "max": 20},
            "ingredient_presets": [[5, 9], [10, 15], [16, 20]],
            "cuisines": ["greek", "italian", "mexican", "indian", "thai", "swedish"]}
