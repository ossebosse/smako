"""Reviewed links and quantity reviews apply chain-wide via the retailer article
(owner decision 2026-11-07); the exact label, package and source still bind."""
from types import SimpleNamespace

import pytest
from app.models.product import QuantityConfidence
from app.services import intake_product_links as links
from app.services.intake_product_links import (
    _articles,
    _review_identity,
    entries,
    project_reviewed_quantity,
)

# Real reviewed Axfood links; in tests the composition binding (served by
# production facts) is replaced by the whole-produce basis so that only the
# chain-wide identity is exercised. The composition rule is tested separately.
LINKS = [(key, row, {**{k: v for k, v in proof.items() if k != "composition_sha256"},
                     "identity_basis": "whole_fresh_produce"})
         for key, row in entries().items() for proof in row.get("reviewed_links", ())
         if proof.get("retailer_product_id") and proof["store_id"].split(":")[1] in {"hemkop", "willys"}
         and proof["quantity"].get("method") == "usda_sr28_refuse_v1"]
COMPOSED = [proof for row in entries().values() for proof in row.get("reviewed_links", ())
            if proof.get("retailer_product_id") and proof.get("composition_sha256")]


class Item(SimpleNamespace):
    def model_copy(self, update):
        return Item(**{**vars(self), **update})


def in_store(proof, store_id, provider_store_id="9999", article=None):
    original = proof["source_provenance"]
    provenance = SimpleNamespace(**{**{k: original.get(k) for k in (
        "source_provider", "source_channel", "source_role", "chain", "price_context", "retailer_id_namespace")},
        "provider_store_id": provider_store_id, "source_snapshot_id": "new-snapshot", "retailer_product_id": None})
    product = Item(
        name=proof["name"], brand=proof.get("brand"), category=proof.get("category"), gtin=proof.get("gtin"),
        package_quantity=proof["package_quantity"], package_unit=proof["package_unit"],
        usable_quantity=proof["package_quantity"], usable_unit=proof["package_unit"],
        sale_model=proof.get("sale_model"), quantity_confidence=QuantityConfidence.EXACT, purchase_terms=None,
        store_id=store_id, product_id="new-product", source_provenance=provenance)
    fact = SimpleNamespace(source_product_id="new-product", source_snapshot_id="new-snapshot",
                           retailer_product_id=article or proof["retailer_product_id"], ingredients=(),
                           conflicts=(), field_sources={})
    return product, fact


@pytest.fixture(params=LINKS[:6], ids=lambda c: c[1]["name"])
def link(request):
    return request.param


def test_reviewed_link_holds_in_another_store_of_the_chain(link):
    _, _, proof = link
    chain = proof["store_id"].split(":")[1]
    product, fact = in_store(proof, f"context:{chain}:lund-store")
    assert _review_identity(proof, product, fact)


def test_reviewed_link_fails_for_other_chain_article_or_label(link):
    _, _, proof = link
    chain = proof["store_id"].split(":")[1]
    product, fact = in_store(proof, "context:otherchain:store")
    assert not _review_identity(proof, product, fact)
    product, fact = in_store(proof, f"context:{chain}:lund-store", article="other-article")
    assert not _review_identity(proof, product, fact)
    product, fact = in_store(proof, f"context:{chain}:lund-store")
    product.package_quantity += 1
    assert not _review_identity(proof, product, fact)
    product, fact = in_store(proof, f"context:{chain}:lund-store")
    product.source_provenance.source_channel = "other-channel"
    assert not _review_identity(proof, product, fact)


def test_estimated_edible_quantity_review_applies_chain_wide(link, monkeypatch):
    _, _, proof = link
    chain_key = ("article", proof["store_id"].split(":")[1], proof["retailer_product_id"])
    monkeypatch.setattr(links, "_quantity_reviews", lambda: {chain_key: [proof]})
    chain = proof["store_id"].split(":")[1]
    product, fact = in_store(proof, f"context:{chain}:lund-store")
    projected = project_reviewed_quantity(product, fact, allow_estimates=True, required_unit="g")
    assert projected.usable_quantity == proof["quantity"]["usable_quantity"]
    assert projected.quantity_confidence == "estimated"
    assert project_reviewed_quantity(product, fact, allow_estimates=False, required_unit="g") is product


def test_flyer_advertisement_id_is_not_an_article():
    provenance = SimpleNamespace(retailer_product_id="ad-123", retailer_id_namespace="willys:flyer-document-ad",
                                 source_snapshot_id="s")
    product = SimpleNamespace(source_provenance=provenance, product_id="p")
    fact = SimpleNamespace(source_product_id="p", source_snapshot_id="s", retailer_product_id="100943534_KG")
    assert _articles(product, fact) == {"100943534_KG"}
    fact.source_snapshot_id = "other"
    assert _articles(product, fact) == set()


def test_registry_has_reviewed_axfood_links():
    assert len(LINKS) >= 6


def test_reviewed_composition_still_has_to_match_in_the_other_store():
    proof = COMPOSED[0]
    chain = proof["store_id"].split(":")[1]
    product, fact = in_store(proof, f"context:{chain}:lund-store")
    assert not _review_identity(proof, product, fact)  # no matching declaration
