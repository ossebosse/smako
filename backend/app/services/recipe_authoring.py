"""Compact recipe authoring -> standardized ``smako-meal-pack-v1`` content.

Authors write what a cook decides: ingredients per component, steps with the
ingredients they use, minutes and dependencies. Everything Smako derives is
computed here the same way for every recipe, so a new dish is immediately
eligible for planning:

* identity, unit and product requirements come from the existing library's
  vocabulary for each ``canonical|form`` (unknown identities are rejected with
  suggestions; nothing is guessed),
* component amounts, merged purchase lines, quantity bounds and the counted
  ingredient number (``ingredient_count``),
* times: active = all non-passive step minutes (parallel branches included),
  total = the longer of the critical path and the active work, waiting = the
  rest (``estimated_minutes`` = total),
* vegetarian/fish flags from the ingredients,
* process water written as "N ml vatten" scales with portions
  (``scalable_amounts``); water in dl/l is rejected,
* readiness warnings: default selection range (10-15 counted ingredients for
  dinners), food-safety temperatures in the text, unused or unknown ingredients.

The result still passes the ordinary ``validate`` -> ``import`` -> ``qualify``
path; this module never approves content or purchases.
"""
from __future__ import annotations

import difflib
import json
import re
from collections import Counter
from pathlib import Path

SCHEMA = "smako-recipe-authoring-v1"
MEAT = {"kyckling", "nötfärs", "fläskfärs", "blandfärs", "fläskkött", "kalkon"}
FISH = {"fisk", "lax", "torsk", "tonfisk"}
FISH.update({"makrill", "rökt makrill", "sardiner", "matjessill", "stenbitsrom", "rökt lax", "varmrökt lax"})
FISH.update({"sardeller", "fisksås", "ostronsås"})
REVIEWED_VOCABULARY = Path(__file__).parents[1] / "data/ingredients/authoring-20261025.json"
AUTHORING_REQUIREMENTS = {"aggnudlar": ("pack:egg_noodles",)}
SAFETY = {
    "kyckling": ("74 °C",), "kalkon": ("74 °C",),
    "nötfärs": ("72 °C", "genomstekt"), "fläskfärs": ("72 °C", "genomstekt"),
    "blandfärs": ("72 °C", "genomstekt"), "fisk": ("63 °C",), "lax": ("63 °C",),
}


def library_vocabulary(recipes, *, reviewed_path=REVIEWED_VOCABULARY):
    """Most common unit and product requirements per ``canonical|form``."""
    counts = Counter()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            counts[(ingredient.canonical_name, ingredient.form, ingredient.unit,
                    tuple(ingredient.product_requirements or ()))] += 1
    vocabulary = {}
    for (canonical, form, unit, requirements), _ in counts.most_common():
        vocabulary.setdefault(f"{canonical}|{form}", (unit, list(requirements)))
    # Explicit reviewed additions bootstrap authoring without dummy recipes.
    # Existing issued defaults cannot be silently replaced by this overlay.
    from app.services.content_pack_requirements import PACK_KEYS
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    document = json.loads(reviewed_path.read_bytes())
    if reviewed_path == REVIEWED_VOCABULARY:
        for name in ("intake-all-20261026.json", "expansion-20261101.json"):
            document["ingredients"].extend(json.loads(reviewed_path.with_name(name).read_bytes())["ingredients"])
    if document["schema_version"] != "smako-authoring-vocabulary-v1":
        raise ValueError("Okänd schema för granskat ingrediensvokabulär")
    seen = set()
    for row in document["ingredients"]:
        key = f"{row['name']}|{row['form']}"
        requirements = row["requirements"]
        if (key in seen or canonicalize_ingredient_name(row["name"]) != row["name"]
                or row["unit"] not in {"g", "ml", "st"}
                or row["form"] not in {"dry", "raw_edible", "as_sold", "preserved_drained", "cooked_drained"}
                or (row["form"] != "as_sold" and row["unit"] != "g")
                or not requirements or not row["review_basis"] or not row["evidence"]
                or any(not r.startswith("pack:") or r[5:] not in PACK_KEYS for r in requirements)):
            raise ValueError(f"Ogiltig granskad ingrediens: {key}")
        seen.add(key)
        vocabulary.setdefault(key, (row["unit"], list(requirements)))
    return vocabulary


def _times(steps):
    """(active, waiting, total) minutes for one cook.

    active  = every non-passive step's minutes, including parallel branches
              (a cook does them one after another),
    total   = the longer of the step graph's critical path and the active work,
    waiting = the rest of the total, i.e. passive time not covered by work.
    """
    ends = {}
    for step in steps:
        start = max((ends[d] for d in step["depends_on"]), default=0)
        ends[step["id"]] = start + step["duration_minutes"]
    active = sum(s["duration_minutes"] for s in steps if not s.get("_passive"))
    total = max(max(ends.values()), active)
    return max(1, active), total - max(1, active), total


def standardize(source, vocabulary, *, reviewed_at):
    """Return ``(pack, report)``; raise ValueError on content Smako cannot use."""
    from app.models import Recipe
    from app.services.ingredient_normalizer import _search_text, canonicalize_ingredient_name
    from app.services.recipe_library import ingredient_count

    if source.get("schema_version") != SCHEMA:
        raise ValueError(f"schema_version måste vara {SCHEMA}")
    out, report = [], []
    for index, row in enumerate(source["recipes"]):
        where = f"recipes[{index}] {row.get('name', '?')}"
        warnings = []
        lines, components = {}, []
        for component in row["components"]:
            amounts = []
            for item in component["ingredients"]:
                canonical = canonicalize_ingredient_name(item["name"])
                key = f"{canonical}|{item['form']}"
                if key not in vocabulary:
                    near = difflib.get_close_matches(key, vocabulary, n=3)
                    raise ValueError(f"{where}: okänd identitet {key}; närmaste kända: {near}")
                unit, requirements = vocabulary[key]
                reviewed_requirements = {r for r in requirements if r.startswith("pack:intake_")}
                unit = item.get("unit", unit)
                requirements = list(dict.fromkeys([*item.get("requirements", requirements),
                    *AUTHORING_REQUIREMENTS.get(_search_text(item["name"]), ())]))
                if not reviewed_requirements <= set(requirements):
                    raise ValueError(f"{where}: {key} får inte tappa granskade produktkrav")
                quantity = float(item["quantity"])
                amounts.append({"ingredient_key": key, "name": item.get("label", canonical),
                                "note": item.get("note", ""), "quantity": quantity, "unit": unit})
                line = lines.setdefault(key, {"name": canonical, "canonical_name": canonical,
                    "quantity": 0.0, "unit": unit, "form": item["form"], "component": component["id"],
                    "required": True, "role": item["role"], "product_requirements": requirements})
                if line["unit"] != unit:
                    raise ValueError(f"{where}: {key} anges i både {line['unit']} och {unit}")
                if sorted(line["product_requirements"]) != sorted(requirements):
                    # One purchase line has one set of product requirements; a
                    # merge would silently drop a stricter component's demand.
                    raise ValueError(f"{where}: {key} har olika produktkrav i olika komponenter "
                                     f"({sorted(line['product_requirements'])} och {sorted(requirements)}); "
                                     "ange samma krav eller dela upp till olika former")
                line["quantity"] += quantity
            components.append({"id": component["id"], "name": component["name"], "amounts": amounts})
        ingredients = []
        for line in lines.values():
            q = round(line["quantity"], 4)
            line.update(quantity=q, quantity_min=q, quantity_max=q, quantity_step=q)
            if not line["product_requirements"]:
                line.pop("product_requirements")
            ingredients.append(line)
        names = {line["canonical_name"]: key for key, line in lines.items()}
        steps = []
        for n, step in enumerate(row["steps"], 1):
            keys = []
            for used in step["uses"]:
                key = used if "|" in used else names.get(canonicalize_ingredient_name(used))
                if key not in lines:
                    raise ValueError(f"{where}: steg {n} använder {used!r} som inte finns i receptet")
                keys.append(key)
            if re.search(r"\d+(?:[,.]\d+)?\s*(?:dl|l|liter)\s+(?:dricks)?vatten", step["text"]):
                raise ValueError(f"{where}: steg {n} anger vatten i dl/l; skriv ml så att mängden skalas med portionerna")
            water = list(dict.fromkeys(
                (f"{m.group(1)} ml", float(m.group(1).replace(",", ".")))
                for m in re.finditer(r"(?<![\d,.])(\d+(?:[,.]\d+)?) ml (?:dricksvatten|vatten)", step["text"])))
            row_step = {"id": f"s{n}", "text": step["text"], "ingredient_keys": sorted(set(keys)),
                        "depends_on": [f"s{d}" for d in step.get("after", [])],
                        "duration_minutes": int(step["minutes"]), "parallel_group": None,
                        "_passive": bool(step.get("passive"))}
            if water:
                # Process water is not a purchase line, so the step text itself
                # carries the amount and scales with the portion count.
                row_step["scalable_amounts"] = water
            steps.append(row_step)
        unused = set(lines) - {k for s in steps for k in s["ingredient_keys"]}
        if unused:
            raise ValueError(f"{where}: ingredienser används inte i något steg: {sorted(unused)}")
        active, waiting, total = _times(steps)
        for step in steps:
            step.pop("_passive")
        canon = {line["canonical_name"] for line in ingredients}
        fish = bool(canon & FISH)
        from app.models.plan import DietPreference
        from app.services.diet_policy import _excluded_by_diet

        vegetarian = not any(_excluded_by_diet(name, DietPreference.VEGETARIAN) for name in canon)
        for food, markers in SAFETY.items():
            text = " ".join(s["text"] for s in steps)
            if food in canon and not any(m in text for m in markers):
                warnings.append(f"{food}: ange säkerhetskontroll ({' eller '.join(markers)}) i texten")
        meal_type = row.get("meal_type", "dinner")
        design = {"base_id": row["base_id"], "version": row.get("version", "1.0.0"),
                  "variant_id": row.get("variant_id", "base"), "cuisines": [row["cuisine"]],
                  "family": row["family"], "primary_ingredient": row["primary"], "method": row["method"],
                  "side": row["side"], "flavor_profile": row["flavor"], "components": components,
                  "steps": steps, "estimated_minutes": total, "equipment": row["equipment"],
                  "vegetarian": vegetarian, "fish": fish, "ingredient_count": 1,
                  "provenance": {"reviewed_at": reviewed_at, "notes": row.get("notes",
                      "Författat och standardiserat med recept-författarverktyget. Inte provlagat. "
                      "Köp, allergener och näring kvalificeras separat.")},
                  "content_sha256": "0" * 64, "meal_types": [meal_type], "active_minutes": active,
                  "waiting_minutes": waiting, "total_minutes": total}
        if row.get("level", "crafted") != "crafted":
            design["dinner_level"] = row["level"]
        recipe = {"name": row["name"], "servings": row["servings"], "ingredients": ingredients,
                  "instructions": [s["text"] for s in steps], "design": design}
        recipe["design"]["ingredient_count"] = ingredient_count(Recipe.model_validate(recipe))
        counted = recipe["design"]["ingredient_count"]
        if meal_type == "dinner" and not 10 <= counted <= 15:
            warnings.append(f"{counted} räknade ingredienser; standardvalet för middag är 10–15, "
                            "så rätten väljs bara med ändrade receptval")
        for flag in ("vegetarian", "fish"):
            if flag in row and row[flag] != design[flag]:
                warnings.append(f"{flag}={row[flag]} i källan ändrades till {design[flag]} enligt ingredienserna")
        out.append(recipe)
        report.append({"id": f"{design['base_id']}:{design['version']}:{design['variant_id']}",
                       "name": row["name"], "meal_type": meal_type, "counted_ingredients": counted,
                       "active_minutes": active, "waiting_minutes": waiting, "total_minutes": total,
                       "vegetarian": vegetarian, "fish": fish, "warnings": warnings})
    pack = {"schema_version": "smako-meal-pack-v1", "pack_id": source["pack_id"], "recipes": out}
    return pack, report


def readiness(recipes):
    """Whether each issued recipe passes the default library filter."""
    from app.models.recipe_preferences import RecipePreferences
    from app.services.complete_recipes import matches_preferences

    defaults = RecipePreferences(mode="complete")
    return {f"{r.design.base_id}:{r.design.version}:{r.design.variant_id}":
            bool(r.design.meal_types[0] != "dinner" or matches_preferences(r, defaults)) for r in recipes}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
