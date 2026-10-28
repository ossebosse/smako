"""Exact public links do not bypass form, package, source or facts boundaries."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.services.intake_product_links import (
    compatible,
    entries,
    ingredient_product,
    recipe_product,
)


def product(evidence):
    return SimpleNamespace(gtin=evidence.get("gtin"), name=evidence["name"], brand=evidence.get("brand"),
        product_id=evidence["product_id"], store_id=evidence["store_id"],
        source_provenance=SimpleNamespace(source_snapshot_id=evidence["source_provenance"]["source_snapshot_id"]),
        package_quantity=evidence["package_quantity"], package_unit=evidence["package_unit"],
        usable_quantity=evidence["package_quantity"], usable_unit=evidence["package_unit"],
        quantity_confidence=evidence.get("quantity_confidence", "exact"), category=evidence["category"], purchase_terms=None)


CASES = [(key, evidence) for key, row in entries().items() if row["kind"] != "definition_only"
         for evidence in row["evidence"]]


@pytest.mark.parametrize("key,evidence", CASES)
def test_each_reviewed_reference_requires_its_exact_package_and_whole_label(key, evidence):
    p = product(evidence)
    assert compatible(key, p)
    p.name += " färdigrätt"
    assert not compatible(key, p)
    p.name = evidence["name"]
    p.brand = "other unreviewed brand"
    assert not compatible(key, p)
    p.brand = evidence.get("brand")
    p.usable_quantity -= 1
    assert not compatible(key, p)
    p.usable_quantity += 1
    p.package_unit = "st"
    assert not compatible(key, p)


def test_source_scoped_link_cannot_cross_a_snapshot_without_a_global_identity():
    key, evidence = next((k, e) for k, e in CASES if not e.get("gtin"))
    p = product(evidence)
    assert compatible(key, p)
    p.source_provenance.source_snapshot_id = "replacement-not-reviewed"
    assert not compatible(key, p)


def test_same_gtin_does_not_approve_a_different_package_size():
    key, evidence = next((k, e) for k, e in CASES if e.get("gtin"))
    p = product(evidence)
    p.package_quantity += 100
    p.usable_quantity += 100
    assert not compatible(key, p)


def test_exact_product_link_is_bound_to_authored_canonical_and_input_form():
    key, row = next((k, r) for k, r in entries().items() if r["name"] == "gröna linser" and r["form"] == "dry")
    p = product(row["evidence"][0])
    assert ingredient_product("gröna linser", "dry", ["pack:" + key], p)
    assert not ingredient_product("gröna linser", "cooked_drained", ["pack:" + key], p)
    assert not ingredient_product("linser", "dry", ["pack:" + key], p)
    fact = SimpleNamespace(ingredients=("Gröna linser, vatten",))
    assert not ingredient_product("gröna linser", "dry", ["pack:" + key], p, fact)
    recipe = SimpleNamespace(ingredients=[SimpleNamespace(canonical_name="gröna linser", form="dry",
                                                           product_requirements=["pack:" + key])])
    assert recipe_product(recipe, "gröna linser", p)
    assert not recipe_product(recipe, "gröna linser", p, fact)


def test_registry_data_change_invalidates_method_after_restart(tmp_path, monkeypatch):
    from app.services import meal_prepared_artifacts as prepared

    path = tmp_path / "backend/app/services/runtime.py"
    path.parent.mkdir(parents=True)
    path.write_text("# synthetic runtime\n")
    ingredients = tmp_path / "backend/app/data/ingredients/reviewed.json"
    ingredients.parent.mkdir(parents=True)
    ingredients.write_text('{"approved": "first"}')
    declarations = tmp_path / "grocery_data/app/data/product_declarations.json"
    declarations.parent.mkdir(parents=True)
    declarations.write_text('{}')
    service = tmp_path / "grocery_data/app/services/product_declarations.py"
    service.parent.mkdir(parents=True)
    service.write_text('# synthetic declarations')
    original = prepared.__file__
    try:
        monkeypatch.setattr(prepared, "__file__", str(path))
        prepared.method_signature.cache_clear()
        first = prepared.method_signature()
        ingredients.write_text('{"approved": "replacement"}')
        prepared.method_signature.cache_clear()
        assert prepared.method_signature() != first
    finally:
        monkeypatch.setattr(prepared, "__file__", original)
        prepared.method_signature.cache_clear()


def test_passive_hours_and_original_dependencies_are_preserved(monkeypatch):
    import runpy

    directory = Path(__file__).resolve().parents[2] / "scripts/recipe_layer"
    monkeypatch.syspath_prepend(str(directory))
    module = runpy.run_path(str(directory / "complete_intake_delivery.py"))
    row = {"steps": [
        {"text": "Fördela lagen. Låt ånga av högst 20 minuter och ställ i kylskåp minst fyra timmar.",
         "minutes": 260, "passive": True, "uses": ["lax"]},
        {"text": "Servera kall.", "minutes": 2, "uses": ["lax"], "after": [1]},
    ]}
    module["phases"](row, [])
    assert row["steps"][0]["minutes"] == 1
    assert row["steps"][1]["minutes"] == 260
    assert row["steps"][1]["passive"] is True
    assert row["steps"][2]["after"] == [2]


def declaration_case():
    key, row = next((k, r) for k, r in entries().items() if r["name"] == "salladslök")
    p = SimpleNamespace(product_id="synthetic-scallion", store_id="synthetic-store", name="Ansad salladslök",
        brand="Synthetic test", source_provenance=SimpleNamespace(source_snapshot_id="synthetic-snapshot"),
        package_quantity=100, package_unit="g", usable_quantity=100, usable_unit="g", quantity_confidence="exact")
    proof = {"kind": "manufacturer_culinary_declaration", "declared_forms": [row["required_classification"]],
        "declared_name": p.name, "declared_brand": p.brand,
        "identity_method": "unique_exact_complete_brand_variant_fixed_pack",
        "bound_product_id": p.product_id, "bound_store_id": p.store_id,
        "bound_snapshot_id": p.source_provenance.source_snapshot_id,
        "source_package_quantity": 100, "source_package_unit": "g",
        "source": "https://example.invalid/synthetic-test-only", "document_sha256": "f" * 64,
        "declared_usable_quantity": 100, "declared_usable_unit": "g", "declared_quantity_basis": "edible_as_sold"}
    f = SimpleNamespace(conflicts=(), product_classification=(row["required_classification"],),
        field_sources={"product_classification": [proof]})
    return key, p, f, proof


def test_definition_requires_actual_bound_edible_mass_declaration():
    key, p, f, proof = declaration_case()
    assert not compatible(key, p)
    assert compatible(key, p, f)
    # A net package amount is not a source statement of prepared edible mass.
    proof["declared_quantity_basis"] = "as_sold"
    assert not compatible(key, p, f)


@pytest.mark.parametrize("field,value", [("bound_snapshot_id", "other"), ("bound_store_id", "other"),
    ("bound_product_id", "other"), ("declared_name", "Salladslök färdig sås"),
    ("declared_brand", "Other"), ("source_package_quantity", 200), ("declared_usable_quantity", 75),
    ("declared_usable_unit", "ml"), ("declared_forms", ["culinary_input:mynta:dry:g"]),
    ("kind", "unreviewed_label_guess")])
def test_definition_declaration_cannot_cross_identity_quantity_or_form(field, value):
    key, p, f, proof = declaration_case()
    proof[field] = value
    assert not compatible(key, p, f)


def test_gross_bone_shell_pod_and_cob_mass_cannot_supply_edible_nutrients():
    from app.services.recipe_preparation import input_evidence

    for key, row in entries().items():
        if not row.get("gross_inedible_mass"):
            continue
        recipe = SimpleNamespace(ingredients=[SimpleNamespace(canonical_name=row["name"],
            product_requirements=["pack:" + key])])
        # Even qualified numbers must not certify 100 g edible food per 100 g
        # shell/bone/pod/cob purchase mass. No test or runtime yield is invented.
        assert input_evidence(recipe, None, row["name"], "g", True, None) is None


def test_entire_intake_is_imported_and_scales_without_changing_original_library():
    import hashlib
    import json

    from app.models.recipe import Recipe
    from app.services.meal_library_content import ROOT, identity
    from app.services.recipe_library import _scaled, current_recipes, validate_recipe_design

    report = json.loads((ROOT.parents[3] / "docs/reviews/recipe-integration-all-20261026/all-recipes.json").read_bytes())
    amendments = json.loads((ROOT.parents[3] / "docs/reviews/recipe-quality-and-planning-20261026/recipe-review.json").read_bytes())
    replacements = {r["previous_id"]: r["runtime_id"] for r in amendments["recipes"]}
    week = json.loads((ROOT.parents[3] / "docs/reviews/week-search-and-cache-20261026/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in week["corrected"]}
    replacements = {k: successors.get(v, v) for k, v in replacements.items()}
    replacements.update(successors)
    mint = json.loads((ROOT.parents[3] / "docs/reviews/recipe-four-staples-20261027/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in mint["corrected"]}
    replacements = {k: successors.get(v, v) for k, v in replacements.items()}
    replacements.update(successors)
    egg = json.loads((ROOT.parents[3] / "docs/reviews/egg-preparation-20261028/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in egg["corrected"]}
    replacements = {k: successors.get(v, v) for k, v in replacements.items()}
    replacements.update(successors)
    leaf = json.loads((ROOT.parents[3] / "docs/reviews/mint-leaf-preparation-20261028/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in leaf["corrected"]}
    replacements = {k: successors.get(v, v) for k, v in replacements.items()}
    replacements.update(successors)
    current = {identity(r): r for r in current_recipes()}
    corn = json.loads((ROOT.parents[3] / "docs/reviews/whole-corn-20261028/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in corn["corrected"]}
    replacements = {k: successors.get(v, v) for k, v in replacements.items()}
    replacements.update(successors)
    assert len(report["recipes"]) == 2200
    assert len({r["source_id"] for r in report["recipes"]}) == 2200
    assert report["status"] == {"accepted": 2155, "already_imported": 45}
    assert len(current) == 2462
    assert len({r.design.base_id for r in current.values()}) == 934
    for original in current_recipes(13):
        assert current[identity(original)].model_dump() == original.model_dump()
    for record in report["recipes"]:
        assert not record["blockers"]
        recipe = current[replacements.get(record["runtime_id"], record["runtime_id"])]
        for servings in (1, 2, 4, 12):
            scaled = Recipe.model_validate_json(_scaled(recipe, servings).model_dump_json())
            assert validate_recipe_design(scaled)
            assert scaled.design.base_id == recipe.design.base_id
            assert scaled.design.family == recipe.design.family
            assert scaled.design.waiting_minutes == recipe.design.waiting_minutes
            assert scaled.design.total_minutes == scaled.design.active_minutes + scaled.design.waiting_minutes
            if servings == recipe.servings:
                assert scaled.design.total_minutes == recipe.design.total_minutes
            for before, after in zip(recipe.ingredients, scaled.ingredients, strict=True):
                assert after.quantity == pytest.approx(before.quantity * servings / recipe.servings)
                assert after.form == before.form
                assert after.product_requirements == before.product_requirements
    source = ROOT / "incoming/authoring-800-20261025"
    manifest = json.loads((source / "SOURCE-MANIFEST.json").read_bytes())
    assert len(manifest["preserved_files"]) == 166
    for entry in manifest["preserved_files"]:
        assert hashlib.sha256((source / entry["path"]).read_bytes()).hexdigest() == entry["sha256"]


def test_large_batch_retains_real_active_time_and_obeys_user_limit():
    from app.models.personal import MealSettings
    from app.models.recipe_preferences import RecipePreferences
    from app.services.recipe_library import _scaled, current_recipes, matches_meal

    preferences = RecipePreferences(mode="complete")
    unlimited = MealSettings(recipe_choices={"min_ingredients": 1, "max_ingredients": 40})
    limited = MealSettings(recipe_choices={"min_ingredients": 1, "max_ingredients": 40, "max_active_minutes": 180})
    batch = next(scaled for recipe in current_recipes() if recipe.design.meal_types[0] == "dinner"
                 and (scaled := _scaled(recipe, 12)).design.active_minutes is not None
                 and scaled.design.active_minutes > 180 and matches_meal(scaled, unlimited, preferences))
    assert not matches_meal(batch, limited, preferences)


@pytest.mark.parametrize("key,accepted,rejected", [
    ("beef_inner_round_cut", "Innanlår Nötkött Sverige", "Högrev Benfri"),
    ("beef_whole_tenderloin_cut", "Oxfilé Mittbit", "Flankstek"),
    ("beef_roasting_cut", "Fransyska Nötkött", "Högrev Benfri"),
    ("beef_lean_strips_cut", "Flankstek", "Entrecôte Nötkött"),
])
def test_source_named_cut_is_not_replaced_by_a_generic_cooking_time_rule(key, accepted, rejected):
    from app.services.content_pack_requirements import compatible as culinary_requirement

    assert culinary_requirement([key], SimpleNamespace(name=accepted), None)
    assert not culinary_requirement([key], SimpleNamespace(name=rejected), None)
