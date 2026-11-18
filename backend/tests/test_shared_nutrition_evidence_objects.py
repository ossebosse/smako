from types import SimpleNamespace

from app.services import nutrition_reference as nr
from app.services import recipe_preparation as rp


def test_plain_reference_evidence_is_one_shared_object_equal_to_a_fresh_one():
    identity = 845  # pasta, dry
    first = nr.reference_evidence(identity)
    assert first is nr.reference_evidence(identity)
    assert first == nr._reference_evidence(identity)


def test_wrapped_inputs_share_their_provenance_step(monkeypatch):
    monkeypatch.setattr(rp, "has_unmeasured_process", lambda recipe: False)
    recipe = SimpleNamespace(preparation=SimpleNamespace(version="v1", family="f", input_forms={"pasta": "dry"}))
    base = nr.NutritionEvidence(source="s", source_product_id="p1", nutrition={"kcal": 350.0},
                                nutrition_unit="g", nutrition_basis="b",
                                field_sources={"nutrition.kcal": ({"a": 1},)})
    other = nr.NutritionEvidence(source="s", source_product_id="p2", nutrition={"kcal": 360.0},
                                 nutrition_unit="g", nutrition_basis="b",
                                 field_sources={"nutrition.kcal": ({"a": 2},)})
    one, two = rp.wrap_evidence(recipe, "pasta", base), rp.wrap_evidence(recipe, "pasta", other)
    assert one.field_sources["nutrition.kcal"][-1] is two.field_sources["nutrition.kcal"][-1]
    assert one.field_sources["nutrition.kcal"] == ({"a": 1}, {
        "kind": "recipe_design_input_estimate", "version": "v1", "family": "f", "input_form": "dry",
        "input_evidence_kind": "generic_reference", "operation": "source_per_100_g * used_edible_g / 100 / servings",
        "cooked_quantity_g": None, "retention_factor": None})
    assert one.evidence_kind == "recipe_design_input_estimate"
