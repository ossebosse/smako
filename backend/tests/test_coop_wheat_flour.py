"""Real wheat-flour identity; no relaxation for other flours or mixtures."""
import pytest
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.product_semantics import evaluate_product_semantics

from grocery_data.tests.test_coop_physical_structured import parse


@pytest.mark.parametrize("account", ["3839", "3815"])
def test_real_parent_child_name_proves_plain_wheat_flour_alias(account):
    _, approved, _ = parse(account)
    flour = next(p for p in approved.products if p.name == "Kärnvetemjöl")
    source = flour.offers[0].source_payload["source_record"]
    assert source["content"]["parentTitle"] == "Vetemjöl"
    assert source["content"]["onlineProductName"] == "Kärnvetemjöl"
    assert flour.package_quantity == 2000
    assert flour.offers[0].quantity == 2 and flour.offers[0].price == 26
    assert canonicalize_ingredient_name(flour.name) == "vetemjöl"
    for target in ["vetemjöl", "kärnvetemjöl"]:
        result = evaluate_product_semantics(target, {"name": flour.name, "canonical_food": flour.name})
        assert result.compatible and result.confidence.value == "high"


@pytest.mark.parametrize("name", [
    "Rågmjöl", "Rismjöl", "Majsmjöl", "Mjöl", "Glutenfritt mjöl",
    "Självjäsande vetemjöl", "Vetemjöl special", "Fullkornsvetemjöl",
    "Brödmix med vetemjöl", "Pannkaksmix vetemjöl", "Pizza med kärnvetemjöl",
    "Kärnvetemjöl fullkorn", "Kärnvetemjöl till hund",
])
def test_other_or_prepared_flours_do_not_inherit_plain_identity(name):
    # Even incorrect upstream canonical metadata cannot override visible text.
    decision = evaluate_product_semantics("vetemjöl", {
        "name": name, "canonical_name": "vetemjöl", "canonical_food": "vetemjöl",
        "semantic_confidence": "exact",
    })
    assert not decision.compatible
    assert "plain_wheat_flour_identity_unverified" in decision.evidence


def test_generic_flour_is_not_an_alias_for_wheat():
    assert canonicalize_ingredient_name("mjöl") == "mjöl"
    assert canonicalize_ingredient_name("rågmjöl") == "rågmjöl"
