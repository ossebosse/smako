"""Recipes that share a nutrition input key share qualified products exactly.

The planner caches each product's evidence by the recipe's validated input
identity, and qualifies a whole recipe line by the same key. These tests check
that the key captures everything the evidence reads from the recipe, across
the whole authored library, including gross bone/pod/shell packs.
"""
from collections import defaultdict

from app.config import Settings
from app.models.recipe_preferences import RecipePreferences
from app.services import recipe_preparation
from app.services.intake_product_links import gross_purchase_input
from app.services.personal_planner import PersonalPlanner
from app.services.recipe_computation_cache import RecipeComputationCache
from app.services.recipe_library import candidates

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, state
from backend.tests.test_personal_qualified_facts import facts

FIELDS = frozenset({"protein_g", "fat_g", "carbs_g", "kcal"})


def test_gross_pack_line_never_shares_input_identity_with_a_plain_line():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    cache = RecipeComputationCache()
    seen = set()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            name = recipe_preparation.canonical(ingredient.canonical_name)
            identity = recipe_preparation.input_evidence_identity(recipe, name, cache)
            if identity is None:
                continue
            gross = gross_purchase_input(recipe, name)
            # input_evidence refuses a gross pack, so the identity must say so.
            assert identity[3] is gross
            seen.add(gross)
    assert seen == {True, False}


def test_every_library_line_sharing_a_key_has_identical_evidence():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    lines = {(i.canonical_name, i.unit) for r in recipes for i in r.ingredients if i.unit in ("g", "ml")}
    items = {line: product(line[0], 500, line[1], 20, identity=f"{line[0]}|{line[1]}") for line in lines}
    nutrition = {"protein_g": 10, "fat_g": 5, "carbs_g": 20, "kcal": 165}
    evidence = {(p.store_id, p.product_id): facts(p, nutrition=nutrition, nutrition_unit=unit,
                                                  nutrition_basis=f"per 100 {unit}",
                                                  field_sources={f"nutrition.{k}": ({"source": "test declaration"},)
                                                                 for k in nutrition})
                for (_name, unit), p in items.items()}
    planner = PersonalPlanner(request(allow_nutrition_estimates=True), Settings(),
                              prepared(*items.values()), state(), facts=evidence, now=NOW)
    groups = defaultdict(list)
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            line = (ingredient.canonical_name, ingredient.unit)
            if line not in items:
                continue
            key = planner._nutrition_recipe_key(recipe, ingredient.canonical_name, FIELDS)
            value = planner._nutrition_evidence(items[line], ingredient.canonical_name, ingredient.unit,
                                                set(FIELDS), recipe)
            if key is None:
                assert value is None
                continue
            groups[(key, line)].append(value)
    shared = [values for values in groups.values() if len(values) > 1]
    assert len(shared) > 100
    for values in shared:
        assert all(value == values[0] for value in values)
