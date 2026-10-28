"""Original, versioned complete dinners. No runtime model call or price engine.

Content is immutable application data; candidates are exact registered portions
and approved variations. Product declarations and the existing planner still
decide nutrition, allergens, purchase feasibility and economic selection.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from app.models.recipe import Recipe, RecipePreparation
from app.models.recipe_preferences import RecipePreferences

LIBRARY_VERSION = "smako-complete-dinners-v1"
LIBRARY_PATH = Path(__file__).parents[1] / "data/recipes/complete-dinners-v1.json"
# Updated only together with reviewed, versioned source content.
CONTENT_SHA256 = "1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c"
SUPPLEMENT_PATH = LIBRARY_PATH.parent / "content-pack-20261004/registered.json"
SUPPLEMENT_SHA256 = "d1c5325453bf1d7583658db4a069623777902846c89d7935a80289abc4c2e20c"
COUNT_EXEMPT = frozenset({"salt", "svartpeppar", "peppar", "vatten"})
ARCHIVED_CONTENT = {
    "complete-dinners-1.3.0.json": "27d53cb050248c826285b445deac0c6e1a87f9a1182fe39b881b189ab3a136b8",
    "complete-dinners-1.2.0.json": "92d7ff63473969e659c61b7ff96b9bd852d8037e7174499a65d60f58297a983e",
    "complete-dinners-1.0.0.json": "4baec1580728294b2805e3716b719d68b2d12ca0f2cbdc469bb074769700de66",
    "complete-dinners-1.1.0.json": "b27912d63f05f993635d4a3516a4e1bba0fa94acd5f682a258eeccdacb4efd07",
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
        if i.unit not in {"g", "ml", "st"} or (i.form != "as_sold" and i.unit != "g"):
            raise ValueError("Mängden kräver kvalificerad massa, volym eller antal som såld.")
        if not (i.quantity_min and i.quantity_max and i.quantity_step):
            raise ValueError("Ingrediensen saknar godkänt mängdintervall.")
        if not i.quantity_min <= i.quantity <= i.quantity_max:
            raise ValueError("Mängden ligger utanför receptets godkända intervall.")
    if d.content_source is not None or any(c.amounts for c in d.components):
        totals: dict[str, float] = {}
        units = {ingredient_key(i): i.unit for i in recipe.ingredients}
        for c in d.components:
            if not c.amounts:
                raise ValueError("Innehållspaketet saknar komponentmängder.")
            for amount in c.amounts:
                if amount.ingredient_key == "vatten|process_water":
                    if amount.unit != "ml":
                        raise ValueError("Processvatten ska anges i ml.")
                    continue
                if units.get(amount.ingredient_key) != amount.unit:
                    raise ValueError("Komponentens ingrediens eller mängdbasis avviker.")
                totals[amount.ingredient_key] = totals.get(amount.ingredient_key, 0) + amount.quantity
        if set(totals) != keys or any(abs(totals[ingredient_key(i)] - i.quantity) > 1e-7 for i in recipe.ingredients):
            raise ValueError("Komponentmängderna stämmer inte med inköpsbehovet.")
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
    if max(ends.values()) > (d.total_minutes or d.estimated_minutes):
        raise ValueError("Beroendena ryms inte inom den uppskattade tillagningstiden.")
    if recipe.instructions != [s.text for s in d.steps]:
        raise ValueError("Visade instruktioner skiljer sig från den granskade tillagningsplanen.")
    if content_hash(recipe) != d.content_sha256:
        raise ValueError("Receptets innehåll har ändrats utan ny granskad version.")
    p = recipe.preparation
    if (p is None or p.parent_sha256 != d.content_sha256 or p.family != d.family
            or p.input_forms != {i.canonical_name: i.form for i in recipe.ingredients}):
        raise ValueError("Beredningsmetoden är inte bunden till receptets exakta innehåll.")


def current_recipes(generation=None):
    from app.services.meal_library_content import load_entries, manifest_entries
    manifest = manifest_entries()
    entries = manifest["current"]
    if generation is not None:
        entries = entries[:generation]
    # Importing a package containing an unchanged older version must not
    # reactivate it over a newer version. All issued versions remain readable.
    current = {}
    for recipe in load_entries(entries):
        if f"{recipe.design.base_id}:{recipe.design.version}:{recipe.design.variant_id}" in manifest.get("revocations", {}):
            continue
        key = (recipe.design.base_id, recipe.design.variant_id)
        previous = current.get(key)
        version = tuple(map(int, recipe.design.version.split(".")))
        if previous is None or version > tuple(map(int, previous.design.version.split("."))):
            current[key] = recipe
    return tuple(current.values())


def reset_library_caches():
    for function in (_registered, _registered_history, _registered_portions,
                     _registered_historical_portions, _issued_index, _current_issued_index):
        function.cache_clear()
    _revocations.cache_clear()
    _prepared_recipe_lookup.cache_clear()


def current_recipe_generations(generation=None):
    """First publication of each still-current exact version, never old versions."""
    from app.services.meal_library_content import identity, load_entries, manifest_entries

    current = {identity(recipe) for recipe in current_recipes(generation)}
    entries = manifest_entries()["current"]
    if generation is not None:
        entries = entries[:generation]
    result = {}
    for number, entry in enumerate(entries, start=1):
        for recipe in load_entries([entry]):
            key = identity(recipe)
            if key in current:
                result.setdefault(key, number)
    return result


@lru_cache(maxsize=1)
def _revocations():
    from app.services.meal_library_content import manifest_entries
    return manifest_entries().get("revocations", {})


@lru_cache(maxsize=1)
def _registered() -> tuple[Recipe, ...]:
    result = current_recipes()
    from app.services.meal_prepared_artifacts import prepare_content
    prepare_content(result)
    identities = set()
    for recipe in result:
        identity = (recipe.design.base_id, recipe.design.version, recipe.design.variant_id)
        if identity in identities:
            raise ValueError("Receptversionen förekommer flera gånger.")
        identities.add(identity)
    return result


@lru_cache(maxsize=1)
def _registered_history() -> tuple[Recipe, ...]:
    """Retain validation of issued plans when current authoring advances."""
    from app.services.meal_library_content import load_entries, manifest_entries
    result = list(load_entries(manifest_entries()["current"]))
    result.extend(load_entries(manifest_entries()["history"]))
    from app.services.meal_prepared_artifacts import prepare_content
    prepare_content(result)
    return tuple(result)


def _format_ml(value):
    text = f"{round(value, 2):g}"
    return text.replace(".", ",") + " ml"


def _scale_amount_tokens(text, amounts, factor):
    """Scale every process amount once, over the original text.

    Tokens are matched as whole numbers (no digit, comma or point directly
    before, no digit after), so "100 ml ... 200 ml" scales both, "125,5 ml" is
    one amount and a token never matches inside another number. Replacements
    are never rescanned.
    """
    if not amounts:
        return text
    scaled = {token: _format_ml(quantity * factor) for token, quantity in amounts}
    pattern = re.compile(r"(?<![\d,.])(?:" + "|".join(re.escape(t) for t in sorted(scaled, key=len, reverse=True))
                         + r")(?!\d)")
    return pattern.sub(lambda m: scaled[m.group(0)], text)


def _scaled(recipe: Recipe, servings: int) -> Recipe:
    if servings == recipe.servings:
        # Native four-/one-portion authoring is already complete. Do not add
        # the old two-portion scaling allowance to an unchanged recipe.
        preparation = recipe.preparation
        return recipe.model_copy(update={"ingredients": list(recipe.ingredients),
            "instructions": list(recipe.instructions), "preparation": preparation.model_copy(
                update={"input_forms": dict(preparation.input_forms)}) if preparation else None})
    factor = servings / recipe.servings
    ingredients = [i.model_copy(update={
        key: round(getattr(i, key) * factor, 8)
        for key in ("quantity", "quantity_min", "quantity_max", "quantity_step")
    }) for i in recipe.ingredients]
    # Authored ingredient/design trees are recursively frozen. Only the recipe
    # lists and preparation form map are mutable; copy lists here and replace
    # preparation below. Updated quantities/steps always use new frozen models.
    result = recipe.model_copy(update={"servings": servings, "ingredients": ingredients,
                                      "instructions": list(recipe.instructions)})
    if result.design.content_source is not None:
        components = tuple(c.model_copy(update={"amounts": tuple(a.model_copy(update={
            "quantity": round(a.quantity * factor, 8)}) for a in c.amounts)}) for c in result.design.components)
        steps = []
        for step in result.design.steps:
            text = _scale_amount_tokens(step.text, step.scalable_amounts, factor)
            if servings != 2:
                for phrase in ("två portioner", "två djupa tallrikar", "två tallrikar"):
                    text = text.replace(phrase, f"{servings} portioner")
            if recipe.servings == 4:
                text = text.replace("fyra portioner", f"{servings} portioner")
            if recipe.servings == 1:
                text = text.replace("en mellanmålsportion", f"{servings} mellanmålsportioner")
                text = text.replace("en portion", f"{servings} portioner")
            steps.append(step.model_copy(update={"text": text}))
        if servings >= 4 and servings > recipe.servings and not (result.design.active_minutes is not None and result.design.method in {"cold_assembly", "refrigerated_assembly"}):
            steps[0] = steps[0].model_copy(update={"text": steps[0].text +
                " Använd tillräckligt stor panna eller fler plåtar så att lagrets djup är detsamma. "
                "Om maten måste lagas i omgångar blir tiden längre än uppskattningen."})
        result = result.model_copy(update={"design": result.design.model_copy(update={
            "components": components, "steps": tuple(steps)}), "instructions": [s.text for s in steps]})
    extra_prep = max(0, (servings - 1) // 2 - (recipe.servings - 1) // 2) * 3
    if extra_prep and (result.design.version != "1.0.0" or result.design.active_minutes is not None):
        # More chopping/weighing for four portions is real work, even when the
        # oven or a large pot can accommodate the full batch without extra heat.
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
    if servings > max(4, recipe.servings) and not (result.design.active_minutes is not None and result.design.method in {"cold_assembly", "refrigerated_assembly"}):
        # A larger pan is not an implicit unlimited cooking resource. Reserve
        # sequential batches and show that allowance instead of silently keeping
        # the two-person time estimate for twelve portions.
        batches = (servings + 3) // 4
        steps = list(result.design.steps)
        heat = next((index for index, step in enumerate(steps)
                     if index > 0 and step.duration_minutes >= 10
                     and (recipe.servings == 2 or re.search(r"grädda|stek|baka|sjud|koka", step.text.casefold()))
                     and not (result.design.version in {"1.3.0", "1.4.0"}
                              and step.id in {"rice", "prebake"})), 0)
        original = steps[heat]
        extra = original.duration_minutes * (batches - (recipe.servings + 3) // 4)
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
    if result.design.total_minutes is not None:
        extra = result.design.estimated_minutes - recipe.design.estimated_minutes
        result = result.model_copy(update={"design": result.design.model_copy(update={
            "total_minutes": recipe.design.total_minutes + extra,
            "active_minutes": recipe.design.active_minutes + extra if recipe.design.active_minutes else None,
        })})
    digest = content_hash(result)
    result = result.model_copy(update={"design": result.design.model_copy(update={"content_sha256": digest})})
    return result.model_copy(update={"preparation": RecipePreparation(
        version=recipe.preparation.version, origin="smako_recipe_design", parent_sha256=digest,
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
    # Current and historical registries share the hash-validated source objects.
    # Reuse only that exact identity, never just a version label or claimed hash.
    # Serializing the entire scaled library into a disk payload retained a second
    # model tree and large temporary dictionaries while building the issued index.
    current = {id(source): (source, scaled) for source, scaled in
               zip(_registered(), _registered_portions(servings), strict=True)}
    result = []
    for source in _registered_history():
        existing = current.get(id(source))
        recipe = existing[1] if existing is not None and existing[0] is source else _scaled(source, servings)
        _structural_check(recipe)
        result.append(recipe)
    return tuple(result)


def validate_recipe_design(recipe: Recipe) -> bool:
    """Only exact issued versions qualify; a self-computed hash cannot approve edits."""
    if recipe.design is None:
        return False
    d = recipe.design
    reason = _revocations().get(f"{d.base_id}:{d.version}:{d.variant_id}")
    if reason:
        raise ValueError("Receptversionens innehållsgodkännande har återkallats: " + reason)
    key = (d.base_id, d.version, d.variant_id)
    registered = _current_issued_index(recipe.servings).get(key)
    if registered is None:
        registered = _issued_index(recipe.servings).get(key)
    if registered is None or _exact_value(recipe) != registered:
        _structural_check(recipe)  # retain precise diagnostics for rejected edits
        raise ValueError("Receptversionen eller mängden saknar godkänd innehållsgranskning.")
    return True


def share_issued_recipe_parts(recipe: Recipe) -> Recipe:
    """Share frozen authority values only after exact issued-content validation.

    Caller parsing/normalization still runs first. Never intern a caller's model
    by a claimed hash or version. Mutable lists and preparation forms stay owned
    by the caller; only registered frozen ingredient/design models are reused.
    """
    if not validate_recipe_design(recipe):
        return recipe
    d = recipe.design
    key = (d.base_id, d.version, d.variant_id)
    registered = _current_issued_index(recipe.servings).get(key)
    if registered is None:
        registered = _issued_index(recipe.servings)[key]
    return recipe.model_copy(update={
        "ingredients": list(registered[2]), "design": registered[5],
        "instructions": list(recipe.instructions),
        "preparation": recipe.preparation.model_copy(update={"input_forms": dict(recipe.preparation.input_forms)}),
    })


def _exact_value(recipe):
    from app.services.recipe_computation_cache import recipe_value
    value = recipe_value(recipe)
    prep = value[4]
    if prep:
        prep = (*prep[:4], tuple(sorted(prep[4])))
    return (*value[:4], prep, value[5])


@lru_cache(maxsize=12)
def _current_issued_index(servings):
    """Public exact current values; historical plans keep their fallback index."""
    from app.services.plan_jobs import check_cancelled
    rows = {}
    for r in _registered_portions(servings):
        check_cancelled()
        rows[(r.design.base_id, r.design.version, r.design.variant_id)] = _exact_value(r)
    return rows


@lru_cache(maxsize=12)
def _issued_index(servings):
    result = {}
    for recipe in _registered_historical_portions(servings):
        d = recipe.design
        key = (d.base_id, d.version, d.variant_id)
        value = _exact_value(recipe)
        if key in result and result[key] != value:
            raise ValueError("Motstridigt innehåll för en utfärdad receptversion")
        result[key] = value
    return result


@lru_cache(maxsize=4)
def _prepared_recipe_lookup(signature, servings):
    """Pure issued-recipe references, at most 2 MiB per view / 8 MiB total.

    Build during cold qualification, never duplicate product or recipe graphs.
    Oversized/ambiguous registries simply use ordinary planning. Selected values
    are freshly hashed and checked against the issued registry before checkout.
    """
    import sys

    from app.services.planner_context import content_digest

    if signature != library_version():
        return None
    recipes = _registered_portions(servings)
    if len(recipes) > 16384:
        return None
    result = {content_digest(recipe): recipe for recipe in recipes}
    if sys.getsizeof(result) + sum(sys.getsizeof(k) + 8 for k in result) > 2 * 1024 * 1024:
        return None
    return MappingProxyType(result)


def prepared_recipe_lookup(servings):
    return _prepared_recipe_lookup(library_version(), servings)


def candidates(preferences: RecipePreferences, servings: int = 2, *, include_supplement: bool = True) -> list[Recipe]:
    """Return complete allowed candidates; nutrition targets are qualified downstream."""
    if preferences.mode != "complete":
        return []
    return [r.model_copy(update={
                "ingredients": list(r.ingredients), "instructions": list(r.instructions),
                "preparation": r.preparation.model_copy(update={"input_forms": dict(r.preparation.input_forms)}),
            }) for r in _registered_portions(servings)
            if "dinner" in r.design.meal_types
            if (include_supplement or r.design.content_source is None)
            and (not preferences.cuisines or set(r.design.cuisines) & set(preferences.cuisines))
            and preferences.min_ingredients <= r.design.ingredient_count <= preferences.max_ingredients
            and (preferences.max_minutes is None or r.design.estimated_minutes <= preferences.max_minutes)
            and (preferences.allow_fish or not r.design.fish)
            and (preferences.adaptation == "approved" or r.design.variant_id == "base")]


def matches_meal(recipe, meal, preferences):
    """A cheap content filter applied before product and basket qualification."""
    validate_recipe_design(recipe)
    d, choices = recipe.design, meal.recipe_choices
    if not d or meal.meal_type not in d.meal_types:
        return False
    if preferences.adaptation == "products" and d.variant_id != "base":
        return False
    if choices is None:
        if meal.meal_type == "dinner":
            from app.services.complete_recipes import matches_preferences
            return matches_preferences(recipe,preferences)
        return True
    if meal.meal_type == "dinner":
        if choices.dinner_level not in {None,"mixed",d.dinner_level}:
            return False
        if preferences.cuisines and not set(preferences.cuisines).intersection(d.cuisines):
            return False
        if not preferences.allow_fish and d.fish:
            return False
    count = ingredient_count(recipe)
    active = d.active_minutes or (d.content_source.active_minutes if d.content_source else None)
    return ((choices.min_ingredients is None or count >= choices.min_ingredients)
            and (choices.max_ingredients is None or count <= choices.max_ingredients)
            and (choices.max_active_minutes is None or active is not None and active <= choices.max_active_minutes)
            and (choices.max_total_minutes is None or (d.total_minutes or d.estimated_minutes) <= choices.max_total_minutes)
            and (choices.max_waiting_minutes is None or d.waiting_minutes <= choices.max_waiting_minutes))


def meal_candidates(meal, preferences, *, include_supplement=True, generation=None):
    if meal.meal_type == "dinner" and meal.recipe_choices is None and generation is None:
        return candidates(preferences, meal.servings, include_supplement=include_supplement)
    result = []
    # Filter unscaled metadata by meal type first. Irrelevant categories never
    # trigger quantity scaling, product matching or basket construction.
    for recipe in (_registered() if generation is None else current_recipes(generation)):
        if meal.meal_type not in recipe.design.meal_types:
            continue
        if not include_supplement and recipe.design.content_source is not None:
            continue
        scaled = _scaled(recipe,meal.servings)
        if matches_meal(scaled,meal,preferences):
            result.append(scaled)
    return result


def validate_library() -> dict:
    recipes = _registered()
    base = [r for r in recipes if r.design.variant_id == "base"]
    return {
        "library_version": LIBRARY_VERSION,
        "content_sha256": CONTENT_SHA256,
        "base_recipes": len(base), "approved_variants": len(recipes) - len(base),
        "by_cuisine": dict(Counter(r.design.cuisines[0] for r in base if r.design.cuisines)),
        "vegetarian_by_cuisine": dict(Counter(r.design.cuisines[0] for r in base if r.design.vegetarian and r.design.cuisines)),
        "structural_validation": "passed", "content_review": "model_assisted_review",
        "cooking_test": "not_cooked", "purchase_qualification": "performed_by_planner_per_snapshot",
        "nutrition_qualification": "performed_by_planner_per_product_and_user_consent",
    }


def library_version() -> str:
    from app.services.meal_library_content import library_signature
    return f"{LIBRARY_VERSION}:{library_signature()}"


def library_summary() -> dict:
    return {**validate_library(), "ingredient_bounds": {"min": 3, "max": 20},
            "ingredient_presets": [[5, 9], [10, 15], [16, 20]],
            "cuisines": ["greek", "italian", "mexican", "indian", "thai", "swedish"]}
