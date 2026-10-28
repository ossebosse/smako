"""Semantic checks against issued content, not only the amendment helper."""
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.personal import MealSettings
from app.models.recipe_preferences import RecipePreferences
from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.recipe_library import current_recipes, matches_meal


def recipe(base, variant="simple"):
    return next(r for r in current_recipes() if r.design.base_id == base and r.design.variant_id == variant)


def test_cold_mango_topping_is_not_boiled_with_tapioca_and_has_real_thaw_time():
    r = recipe("smako-thai-snack-tapioca-pearl-pudding")
    assert r.design.version == "1.0.2"
    assert r.design.waiting_minutes >= 120
    assert all("mango|raw_edible" not in s.ingredient_keys for s in r.design.steps if s.text.startswith(("Skölj tapiokapärlorna", "Sjud på låg värme", "Rör ner sockret")))
    assert not any("Skala" in s.text and "mango" in s.text for s in r.design.steps)
    assert any("tinade mangobitarna" in s.text for s in r.design.steps)
    permissive = MealSettings(meal_type="snack", recipe_choices={"min_ingredients": 1, "max_ingredients": 40})
    limited = permissive.model_copy(update={"recipe_choices": permissive.recipe_choices.model_copy(update={"max_total_minutes": 60})})
    assert matches_meal(r, permissive, RecipePreferences(mode="complete"))
    assert not matches_meal(r, limited, RecipePreferences(mode="complete"))


@pytest.mark.parametrize("base", ["smako-mexican-tofu-pinapple-skewers", "smako-thai-chicken-pineapple-skewers"])
def test_frozen_pineapple_is_thawed_before_cutting_and_threading_even_before_oven(base):
    r = recipe(base)
    thaw = next(i for i, s in enumerate(r.design.steps) if "tina helt före skärning och trädning" in s.text)
    threading = next(i for i, s in enumerate(r.design.steps) if s.text.startswith("Trä ") or "momentet: Trä " in s.text)
    assert thaw < threading
    assert r.design.waiting_minutes >= 240
    assert r.design.total_minutes == r.design.active_minutes + r.design.waiting_minutes


def test_guacamole_uses_edible_frozen_cubes_without_whole_fruit_preparation():
    r = recipe("smako-mexican-snack-chunky-guacamole")
    assert any("tinade skalade avokadotärningarna" in s.text for s in r.design.steps)
    assert not any("Dela avokadon" in s.text or "väg det råa" in s.text for s in r.design.steps)


def test_green_mango_and_avocado_wedges_cannot_buy_frozen_ripe_cubes():
    from app.services.intake_product_links import compatible, entries

    for base, name, suffix in [("smako-indian-fish-unripe-mango-puree-batons", "mango", "green_mango"),
                               ("smako-swedish-breakfast-breaded-avocado-egg-cream", "avokado", "firm_avocado")]:
        r = recipe(base)
        i = next(i for i in r.ingredients if i.canonical_name == name)
        assert list(i.product_requirements) == ["pack:intake_all_shape_" + suffix]
        old = next(row for row in entries().values() if row["name"] == name and row["kind"] == "frozen_edible")
        e = old["evidence"][0]
        p = SimpleNamespace(**{k: e.get(k) for k in ("name", "brand", "gtin", "product_id", "store_id", "package_quantity", "package_unit")},
                            usable_quantity=e["package_quantity"], usable_unit="g", quantity_confidence="exact")
        assert not compatible("intake_all_shape_" + suffix, p)


def test_all_amended_versions_keep_history_and_original_library_and_source_bytes():
    report = json.loads((ROOT.parents[3] / "docs/reviews/recipe-quality-and-planning-20261026/recipe-review.json").read_bytes())
    current = {identity(r): r for r in current_recipes()}
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries([*manifest["current"], *manifest["history"]], ROOT)}
    week = json.loads((ROOT.parents[3] / "docs/reviews/week-search-and-cache-20261026/recipe-review.json").read_bytes())
    successors = {r["previous_id"]: r["runtime_id"] for r in week["corrected"]}
    mint = json.loads((ROOT.parents[3] / "docs/reviews/recipe-four-staples-20261027/recipe-review.json").read_bytes())
    latest = {r["previous_id"]: r["runtime_id"] for r in mint["corrected"]}
    successors = {k: latest.get(v, v) for k, v in successors.items()} | latest
    egg = json.loads((ROOT.parents[3] / "docs/reviews/egg-preparation-20261028/recipe-review.json").read_bytes())
    latest = {r["previous_id"]: r["runtime_id"] for r in egg["corrected"]}
    successors = {k: latest.get(v, v) for k, v in successors.items()} | latest
    leaf = json.loads((ROOT.parents[3] / "docs/reviews/mint-leaf-preparation-20261028/recipe-review.json").read_bytes())
    latest = {r["previous_id"]: r["runtime_id"] for r in leaf["corrected"]}
    successors = {k: latest.get(v, v) for k, v in successors.items()} | latest
    corn = json.loads((ROOT.parents[3] / "docs/reviews/whole-corn-20261028/recipe-review.json").read_bytes())
    latest = {r["previous_id"]: r["runtime_id"] for r in corn["corrected"]}
    successors = {k: latest.get(v, v) for k, v in successors.items()} | latest
    top_five = json.loads((ROOT.parents[3] / "docs/reviews/top-five-ingredients-20261028/recipe-review.json").read_bytes())
    latest = {r["previous_id"]: r["runtime_id"] for r in top_five["corrected"]}
    successors = {k: latest.get(v, v) for k, v in successors.items()} | latest
    assert report["affected_variants"] == 337
    assert len(current) == 2462
    for row in report["recipes"]:
        assert row["previous_id"] in issued and row["previous_id"] in manifest["revocations"]
        assert row["previous_id"] not in current and successors.get(row["runtime_id"], row["runtime_id"]) in current
        assert issued[row["runtime_id"]].design.content_sha256 == row["content_sha256"]
    for original in current_recipes(13):
        assert current[identity(original)].model_dump() == original.model_dump()


def test_retired_automatic_adapter_cannot_reintroduce_heat_word_bug(monkeypatch):
    directory = Path(__file__).resolve().parents[2] / "scripts/recipe_layer"
    monkeypatch.syspath_prepend(str(directory))
    module = runpy.run_path(str(directory / "complete_intake_delivery.py"))
    with pytest.raises(RuntimeError, match="retired"):
        module["frozen_preparation"]({"steps": []}, [], [])


def test_cold_raspberries_keep_boil_and_cooling_and_hot_compote_keeps_boiling():
    cold = recipe("smako-swedish-snack-drinkable-fruit-oat-smoothie")
    hot = recipe("smako-swedish-snack-jam-thumbprint-shortbread")
    for r in (cold, hot):
        assert any("hela bärmassan kokande minst en minut" in s.text for s in r.design.steps)
    assert any("helt kalla före kall fyllning" in s.text for s in cold.design.steps)
    assert not any("helt kalla före kall fyllning" in s.text for s in hot.design.steps)
