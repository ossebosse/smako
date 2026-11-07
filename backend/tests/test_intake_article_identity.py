"""Reviewed links survive a new collection only through the retailer article id.

Product ids change with every snapshot. An article id from the product's own
provenance, or from facts bound to that exact product and snapshot, is the
global identity; name, brand and package must still match the reviewed row.
"""
from types import SimpleNamespace

import pytest
from app.services.intake_product_links import compatible, entries, search_positions

CASES = [(key, row, evidence) for key, row in entries().items() if row["kind"] != "definition_only"
         for evidence in row["evidence"] if evidence.get("retailer_product_id")]


def test_registry_carries_article_ids_for_snapshot_bound_evidence():
    assert len(CASES) >= 200
    assert all(e["retailer_product_id_evidence"]["basis"] == "reviewed_product_facts_same_product_and_snapshot"
               for _, _, e in CASES)


def new_collection(evidence, *, article_in_provenance=None):
    provenance = SimpleNamespace(source_snapshot_id="new-snapshot", retailer_product_id=article_in_provenance)
    return SimpleNamespace(gtin=None, name=evidence["name"], brand=evidence.get("brand"), product_id="new-product-id",
                           store_id=evidence["store_id"], source_provenance=provenance,
                           package_quantity=evidence["package_quantity"], package_unit=evidence["package_unit"],
                           usable_quantity=evidence["package_quantity"], usable_unit=evidence["package_unit"],
                           quantity_confidence=evidence.get("quantity_confidence", "exact"),
                           category=evidence["category"], purchase_terms=None, sale_model="fixed_package")


def bound_fact(product, article):
    return SimpleNamespace(source_product_id=product.product_id, source_snapshot_id="new-snapshot",
                           retailer_product_id=article, ingredients=(), field_sources={}, conflicts=())


@pytest.fixture(params=CASES[:12], ids=lambda c: c[1]["name"])
def case(request):
    return request.param


def test_same_article_in_a_new_collection_is_the_reviewed_product(case):
    key, _, evidence = case
    product = new_collection(evidence)
    assert compatible(key, product, bound_fact(product, evidence["retailer_product_id"]))
    assert compatible(key, new_collection(evidence, article_in_provenance=evidence["retailer_product_id"]))


def test_no_article_unbound_fact_or_other_article_cannot_cross_a_snapshot(case):
    key, _, evidence = case
    product = new_collection(evidence)
    assert not compatible(key, product)
    unbound = bound_fact(product, evidence["retailer_product_id"])
    unbound.source_snapshot_id = "older-snapshot"
    assert not compatible(key, product, unbound)
    assert not compatible(key, product, bound_fact(product, "other-article"))


def test_same_article_with_changed_label_or_package_is_rejected(case):
    key, _, evidence = case
    product = new_collection(evidence)
    fact = bound_fact(product, evidence["retailer_product_id"])
    product.name += " färdigrätt"
    assert not compatible(key, product, fact)
    product.name = evidence["name"]
    product.package_quantity += 1
    product.usable_quantity += 1
    assert not compatible(key, product, fact)


def test_article_applies_in_every_store_of_the_same_chain_only(case):
    key, _, evidence = case
    product = new_collection(evidence)
    chain = evidence["store_id"].split(":")[1]
    product.store_id = f"context:{chain}:another-store"
    assert compatible(key, product, bound_fact(product, evidence["retailer_product_id"]))
    product.store_id = "context:other-chain:store"
    assert not compatible(key, product, bound_fact(product, evidence["retailer_product_id"]))


def test_retrieval_finds_the_article_through_bound_facts():
    _, row, evidence = CASES[0]
    product = new_collection(evidence)
    facts = {(product.store_id, product.product_id): bound_fact(product, evidence["retailer_product_id"])}
    prepared = SimpleNamespace(universe=SimpleNamespace(products=[product]),
                               product_search_cache=SimpleNamespace(get_or_compute=lambda _key, compute: compute()))
    assert search_positions(prepared, facts).get(row["name"]) == frozenset({0})
    assert search_positions(prepared).get(row["name"]) is None
