"""Language successors preserve cooking quantities, timing and coverage identity."""
import copy
import json
import runpy
import sys
from pathlib import Path

import pytest
from app.models.recipe import RecipeBatchScaling
from app.services.meal_library_content import identity, load_entries
from app.services.recipe_authoring import language_warnings
from app.services.recipe_library import _scaled, _structural_check, current_recipes

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer"))
import rewrite_recipe_language as language
from coverage_reference import (
    digest,
    imported_recipes,
    reviewed_recipe_transition,
)


@pytest.fixture(scope="module")
def review():
    return json.loads((language.REPORT / "library-transition.json").read_bytes())


def test_full_transition_preserves_issued_history_and_all_current_identities(review):
    language.checked_transition(review)
    active = current_recipes()
    assert len(active) == 2851
    assert len({r.design.base_id for r in active}) == 1083
    for recipe in active:
        assert language.WAIT not in recipe.instructions
        assert not any(language.PREFIX in text or "Finhacka fasta bitar" in text for text in recipe.instructions)


def test_coverage_keeps_every_original_id_and_maps_only_its_reviewed_successors(review):
    original, current = imported_recipes()
    assert len(original) == len(set(original)) == len(current) == 2200
    predecessors = {r["runtime_id"]: r["previous_id"] for r in review["corrected"]}
    ids = [identity(r) for r in current]
    before_ids = [predecessors.get(key, key) for key in ids]
    before = {"manifest_sha256": review["before_manifest_file_sha256"], "recipe_ids_sha256": digest(before_ids)}
    after = {"manifest_sha256": review["after_manifest_file_sha256"], "recipe_ids_sha256": digest(ids)}
    assert reviewed_recipe_transition(before, after, [{"current_id": key} for key in before_ids]) == ids


def test_coverage_rejects_incomplete_or_unbound_language_receipt(review):
    for field in ("corrected", "added_entries"):
        broken = copy.deepcopy(review)
        broken[field].pop()
        with pytest.raises(AssertionError):
            language.checked_transition(broken)
    broken = copy.deepcopy(review)
    broken["corrected"][0]["previous_content_sha256"] = "0" * 64
    with pytest.raises(AssertionError):
        language.checked_transition(broken)


def test_merged_wait_and_explicit_batch_basis_preserve_portion_scaling(review):
    before = review["before_manifest"]
    old = {identity(r): r for r in load_entries(before["current"] + before["history"])}
    added = {identity(r): r for r in load_entries(review["added_entries"])}
    # Exercise serial waiting, unchanged graphs, cold assembly and unknown losses.
    cases = {}
    for row in review["corrected"]:
        new = added[row["runtime_id"]]
        key = (bool(row["merged_wait_steps"]), new.design.method, new.preparation.version)
        cases.setdefault(key, row)
    for row in cases.values():
        language.verify_pair(old[row["previous_id"]], added[row["runtime_id"]])


def test_batch_basis_ignores_new_heat_verbs_but_rejects_unknown_step(review):
    recipe = next(r for r in load_entries(review["added_entries"])
                  if r.design.method not in {"cold_assembly", "refrigerated_assembly"})
    steps = tuple(s.model_copy(update={"text": s.text.replace("stek", "tillaga").replace("sjud", "tillaga")})
                  for s in recipe.design.steps)
    changed = recipe.model_copy(update={"design": recipe.design.model_copy(update={"steps": steps}),
                                       "instructions": [s.text for s in steps]})
    assert _scaled(recipe, 12).design.estimated_minutes == _scaled(changed, 12).design.estimated_minutes
    bad = recipe.model_copy(update={"design": recipe.design.model_copy(update={
        "batch_scaling": RecipeBatchScaling(step_id="missing", duration_minutes=20)})})
    with pytest.raises(ValueError, match="okänt tillagningssteg"):
        _structural_check(bad)


def test_recipe_authoring_warns_without_rewriting_and_retired_adapter_cannot_emit_filler(monkeypatch):
    row = {"name": "Linsgryta – standard", "steps": [{"text": language.WAIT}]}
    before = copy.deepcopy(row)
    assert len(language_warnings(row)) == 2
    assert row == before
    directory = Path(__file__).resolve().parents[2] / "scripts/recipe_layer"
    monkeypatch.syspath_prepend(str(directory))
    module = runpy.run_path(str(directory / "complete_intake_delivery.py"))
    with pytest.raises(RuntimeError, match="retired"):
        module["phases"](row, [])


def test_concrete_preparation_does_not_invent_solids_or_unrelated_root_vegetables():
    recipe = {"ingredients": [{"canonical_name": "yoghurt naturell", "form": "as_sold"}]}
    step = {"ingredient_keys": ["yoghurt naturell|as_sold", "salt|as_sold"]}
    assert language.rewrite_step("Finhacka fasta bitar och färska örter. Rör ihop yoghurt och salt.", recipe, step) == "Rör ihop yoghurt och salt."
    assert language.rewrite_step("Väg gurkan; skala rotfrukter före vägning.", recipe, step) == "Väg gurkan."
