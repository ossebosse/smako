"""Follow-up recipe text has an explicit history edge and unchanged food facts."""
import copy
import json
import re
import sys
from pathlib import Path

import pytest
from app.services.meal_library_content import identity, load_entries
from app.services.recipe_library import current_recipes

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer"))
import rewrite_recipe_language_followup as language
from coverage_reference import digest, imported_recipes, reviewed_recipe_transition


@pytest.fixture(scope="module")
def review():
    return json.loads((language.REPORT / "library-transition.json").read_bytes())


def test_followup_has_complete_bound_transition_and_no_remaining_target_phrases(review):
    language.checked_transition(review)
    for recipe in current_recipes():
        assert not re.search(r"huvudråvar|huvudkomponent|nästa aktiva steg|förlusten är okänd", " ".join(recipe.instructions))
        assert all("ny receptdos" not in a.name for c in recipe.design.components for a in c.amounts or ())
    for field in ("corrected", "added_entries"):
        broken = copy.deepcopy(review)
        broken[field].pop()
        with pytest.raises(AssertionError):
            language.checked_transition(broken)


def test_both_language_edges_preserve_all_original_coverage_ids(review):
    first = json.loads((language.first.REPORT / "library-transition.json").read_bytes())
    original, current = imported_recipes()
    assert len(original) == len(set(original)) == len(current) == 2200
    predecessors = {r["runtime_id"]: r["previous_id"] for edge in (first, review) for r in edge["corrected"]}
    ids = [identity(r) for r in current]
    before_ids = []
    for recipe_id in ids:
        while recipe_id in predecessors:
            recipe_id = predecessors[recipe_id]
        before_ids.append(recipe_id)
    before = {"manifest_sha256": first["before_manifest_file_sha256"], "recipe_ids_sha256": digest(before_ids)}
    after = {"manifest_sha256": review["after_manifest_file_sha256"], "recipe_ids_sha256": digest(ids)}
    assert reviewed_recipe_transition(before, after, [{"current_id": key} for key in before_ids]) == ids


def test_label_rewrite_preserves_product_and_amount_and_rejects_quantity_drift(review):
    old = {identity(r): r for r in load_entries(review["before_manifest"]["current"])}
    added = {identity(r): r for r in load_entries(review["added_entries"])}
    row = next(row for row in review["corrected"] if any(
        a.name == language.TAMARIND_LABEL for c in old[row["previous_id"]].design.components for a in c.amounts or ()))
    previous, successor = old[row["previous_id"]], added[row["runtime_id"]]
    # The preparation envelope is rebound to the new content hash, but all
    # preparation facts (including forms, losses and method) must stay exact.
    assert successor.preparation.model_dump(exclude={"parent_sha256"}) == previous.preparation.model_dump(exclude={"parent_sha256"})
    assert successor.preparation.parent_sha256 == successor.design.content_sha256
    language.verify_pair(previous, successor)
    altered = copy.deepcopy(successor)
    component = next(c for c in altered.design.components if any(a.name == "Tamarindkoncentrat CHS" for a in c.amounts or ()))
    amount = next(a for a in component.amounts if a.name == "Tamarindkoncentrat CHS")
    changed = amount.model_copy(update={"quantity": amount.quantity + 1})
    altered_component = component.model_copy(update={"amounts": tuple(changed if a == amount else a for a in component.amounts)})
    altered = altered.model_copy(update={"design": altered.design.model_copy(update={
        "components": tuple(altered_component if c == component else c for c in altered.design.components)})})
    with pytest.raises(AssertionError):
        language.verify_pair(previous, altered)
