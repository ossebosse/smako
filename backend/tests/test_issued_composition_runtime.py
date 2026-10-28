"""Issued recipe facts must reach ordinary loading without weakening identity."""
import json
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Product
from app.services.intake_product_links import composition_signature
from app.services.personal_policy import ProductFacts
from app.services.reviewed_ingredients import enrich_issued_compositions

DOCUMENT = json.loads((Path(__file__).parents[1] / "app/data/ingredients/issued-compositions-20261028.json").read_bytes())
ROWS = DOCUMENT["products"]


def fixture(row):
    proof = row["proof"]
    product = Product(product_id=proof["product_id"], store_id=proof["store_id"],
        store_name="Synthetic source store", name=proof["name"], canonical_name=proof["name"],
        brand=proof["brand"], category=proof["category"], gtin=proof["gtin"],
        chain=proof["source_provenance"]["chain"], price=10,
        sale_model=proof["sale_model"], package_quantity=proof["package_quantity"],
        package_unit=proof["package_unit"], usable_quantity=proof["package_quantity"],
        usable_unit=proof["package_unit"], quantity_confidence="exact",
        source_provenance=proof["source_provenance"])
    fact = ProductFacts(source="synthetic current catalog", source_product_id=product.product_id,
        source_snapshot_id=product.source_provenance.source_snapshot_id,
        retailer_product_id=proof.get("retailer_product_id"))
    return product, fact


def project(product, fact=None):
    prepared = SimpleNamespace(universe=SimpleNamespace(products=(product,)))
    return enrich_issued_compositions(prepared,
        {(product.store_id, product.product_id): fact} if fact else {})


@pytest.mark.parametrize("row", ROWS, ids=[r["proof"]["product_id"] for r in ROWS])
def test_every_issued_composition_projects_without_changing_other_facts(row):
    product, fact = fixture(row)
    before_product = product.model_dump(mode="json")
    result = project(product, fact)[(product.store_id, product.product_id)]
    assert composition_signature(result) == row["proof"]["composition_sha256"]
    for name, value in asdict(fact).items():
        if name not in {"ingredients", "ingredients_complete", "ingredient_evidence_kind", "field_sources"}:
            assert getattr(result, name) == value
    assert product.model_dump(mode="json") == before_product
    assert project(product, result)[(product.store_id, product.product_id)] == result


@pytest.mark.parametrize("change", [
    {"store_id": "different-context"}, {"name": "Unreviewed variant"},
    {"brand": "Different brand"}, {"gtin": "7310500019628"},
    {"package_quantity": 123}, {"package_unit": "st"}, {"source_provenance": None},
])
def test_exact_identity_and_context_boundaries_are_mandatory(change):
    product, fact = fixture(ROWS[0])
    changed = product.model_copy(update=change)
    result = project(changed, fact)[(changed.store_id, changed.product_id)]
    assert result == fact


def test_current_declaration_conflicts_and_wrong_fact_binding_are_preserved():
    product, fact = fixture(ROWS[0])
    for conflict in (
        replace(fact, ingredients=("Different current declaration",)),
        replace(fact, conflicts=("ingredients",)),
        replace(fact, source_snapshot_id="wrong-snapshot"),
    ):
        assert project(product, conflict)[(product.store_id, product.product_id)] == conflict


def test_new_price_generation_rechecks_food_identity_without_renewing_evidence():
    product, fact = fixture(ROWS[0])
    changed = product.model_copy(update={"product_id": "new-product-uuid", "price": 12,
        "source_provenance": product.source_provenance.model_copy(update={"source_snapshot_id": "new-price-generation"})})
    current = replace(fact, source_product_id=changed.product_id,
                      source_snapshot_id="new-price-generation")
    result = project(changed, current)[(changed.store_id, changed.product_id)]
    assert result.ingredients == tuple(ROWS[0]["ingredients"])
    assert result.observed_at == fact.observed_at
    assert changed.price == 12
    source = result.field_sources["ingredients"][-1]
    assert source["bound_snapshot_id"] == "new-price-generation"
    assert source["reviewed_original_binding"]["bound_snapshot_id"] == fact.source_snapshot_id


def test_ordinary_fact_loader_includes_issued_composition(monkeypatch):
    from app.services import personal_source_facts

    product, fact = fixture(next(r for r in ROWS if "tamarind" in r["proof"]["name"].casefold()))
    prepared = SimpleNamespace(universe=SimpleNamespace(products=(product,)))
    monkeypatch.setattr(personal_source_facts, "_load_retained_catalog_facts",
        lambda *a, **kw: personal_source_facts.FactsCollection({(product.store_id, product.product_id): fact}))
    result = personal_source_facts.load_retained_facts(prepared)
    assert result[(product.store_id, product.product_id)].ingredients_complete
    assert not result[(product.store_id, product.product_id)].allergens_checked
    assert result[(product.store_id, product.product_id)].nutrition == {}
