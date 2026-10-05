import json
import runpy
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.recipe import Recipe
from app.models.recipe_preferences import RecipePreferences
from app.services.content_pack_requirements import compatible
from app.services.recipe_library import (
    LIBRARY_PATH,
    _registered,
    _structural_check,
    candidates,
    ingredient_key,
    validate_recipe_design,
)

ROOT = Path(__file__).parents[2]


def test_deterministic_import_preserves_every_amount_and_own_instruction():
    importer = runpy.run_path(str(ROOT / "scripts/recipe_layer/import_content_pack.py"))
    issued = [r for r in _registered() if r.design.content_source]
    priority = max(r.design.content_source.priority for r in issued)
    assert importer["build"](priority)["recipes"] == [r.model_dump(mode="json") for r in issued]
    source = json.loads(importer["SOURCE"].read_text(encoding="utf8"))
    originals = {r["proposal_id"]: r for r in source["recipe_versions"]}
    for recipe in issued:
        original = originals[recipe.design.content_source.proposal_id]
        for actual, expected in zip(recipe.design.components, original["components"], strict=True):
            assert actual.name == expected["name_sv"]
            assert [(a.quantity, a.unit, a.note) for a in actual.amounts] == [
                (a["quantity"], a["unit"], a["prep_note_sv"]) for a in expected["ingredients"]]
        for actual, expected in zip(recipe.design.steps, original["steps"], strict=True):
            assert actual.text.startswith(expected["instruction_sv"])
            assert actual.duration_minutes == expected["duration_minutes_estimate"]
            assert actual.depends_on == tuple(expected["depends_on"])
        assert recipe.design.ingredient_count == original["ingredient_count_excluding_salt_pepper_water"]
        assert recipe.design.provenance.cooking_test == "not_cooked"
        assert isinstance(hash(recipe.design), int)  # bounded calculation caches


def test_old_104_recipes_unchanged_and_registered():
    old = json.loads(LIBRARY_PATH.read_text(encoding="utf8"))["recipes"]
    assert [r.model_dump(mode="json") for r in _registered() if r.design.content_source is None] == [Recipe.model_validate(r).model_dump(mode="json") for r in old]
    assert len(old) == 104


def test_overlap_variants_keep_the_existing_diversity_family():
    original = {r.design.base_id: r.design.family for r in _registered() if not r.design.content_source}
    for r in _registered():
        if r.design.content_source and r.design.base_id in original:
            assert r.design.variant_id != "base"
            assert r.design.family == original[r.design.base_id]


@pytest.mark.parametrize("servings", [1, 2, 4, 6, 12])
def test_portions_preserve_component_purchase_sum_and_registered_identity(servings):
    for r in candidates(RecipePreferences(mode="complete", max_ingredients=20), servings):
        assert validate_recipe_design(r)
        if not r.design.content_source:
            continue
        totals = defaultdict(float)
        for c in r.design.components:
            for a in c.amounts:
                if a.ingredient_key != "vatten|process_water":
                    totals[a.ingredient_key] += a.quantity
        assert dict(totals) == pytest.approx({ingredient_key(i): i.quantity for i in r.ingredients})
        assert "vatten" not in {i.canonical_name for i in r.ingredients}


def test_component_mutation_cannot_authorize_different_amount():
    r = next(r for r in _registered() if r.design.content_source)
    c = r.design.components[0]
    changed = c.model_copy(update={"amounts": (c.amounts[0].model_copy(update={"quantity": 999}), *c.amounts[1:])})
    with pytest.raises(ValueError, match="Komponentmängderna"):
        _structural_check(r.model_copy(update={"design": r.design.model_copy(update={"components": (changed, *r.design.components[1:])})}))


@pytest.mark.parametrize(("requirement", "name", "expected"), [
    ("chicken_thigh", "Kycklingfilé", False), ("chicken_thigh", "Kycklinglårfilé", True),
    ("chicken_breast", "Kycklinglårfilé", False), ("cod", "Sejfilé", False),
    ("rice_noodles", "Äggnudlar", False), ("egg_noodles", "Risnudlar", False),
    ("pita", "Formbröd", False), ("unknown", "Unknown", False),
    ("small_pasta", "Ris", False), ("small_pasta", "Risoni", True),
    ("yogurt", "Grekisk yoghurt", True),
    ("paprika_powder", "Paprikapulver", False),
    ("paprika_powder", "Paprikapulver Milt", True),
    ("paprika_powder", "Paprikapulver Stark", False),
    ("black_pepper", "Svartpeppar Hel", False),
    ("black_pepper", "Svartpeppar Malen", True),
    ("spinach", "Spenat Blad Fryst", False),
    ("spinach", "Spenat Hackad Fryst", True),
    ("chili", "Chili Flakes Red Hot", False),
    ("chili", "Chili Flakes Mild", True),
])
def test_pack_culinary_restrictions(requirement, name, expected):
    # This only asserts the additional restriction; other existing checks still
    # establish whole identity, usable mass, nutrition, source and allergens.
    assert compatible([requirement], SimpleNamespace(name=name, category=""), None) is expected
