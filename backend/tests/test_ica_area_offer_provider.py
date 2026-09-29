"""Synthetic source boundary tests; prices are not retailer observations."""
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from app.models import Product, SourceProvenance, Store
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.providers.own import OwnGroceryPriceProvider

from backend.tests.test_own_provider import _envelope, _fixed_product


@pytest.mark.parametrize("member", [False, True])
async def test_conditional_contract_projects_without_fabricated_ordinary_price(member):
    row = {"type": "multibuy", "price": 30, "quantity": 2, "member_only": member,
           "max_quantity": 1, "product_id": "fixture", "chain": "ica", "store_id": "own:1",
           "store_coverage": "offers_only", "source_channel": "offers",
           "valid_from": "2026-09-14", "valid_to": "2026-09-20",
           "product": _fixed_product(id="fixture", store_id="own:1", chain="ica",
               sale_price=None, regular_price=None, promotions=[], source_channel="offers")}
    async with httpx.AsyncClient(base_url="http://test/", transport=httpx.MockTransport(
            lambda req: httpx.Response(200, json=_envelope([row])))) as client:
        own = OwnGroceryPriceProvider("http://test", client=client, include_offers_only=True,
                                      include_conditional_offer_products=True)
        products = await own.get_offers("own:1")
    assert len(products) == 1 and products[0].price is None
    contract = products[0].offers[0]
    assert contract.required_packages == 2 and contract.price == 30 and contract.max_quantity == 1
    assert str(contract.eligibility) == ("member" if member else "public")


class Base:
    def __init__(self, stores=()): self.rows = list(stores)
    async def find_stores(self, postal): return self.rows
    async def get_store_products(self, store): return []
    async def search_products(self, query, stores): return []
    def report(self): return {}


class Own:
    def __init__(self, fail=False): self.fail = fail
    async def find_offer_stores(self, postal):
        if self.fail: raise ValueError("synthetic failure")
        return [Store(store_id="own:fixture", source_store_id="1", chain="ica", name="Fixture",
                      city="Lund", address="Fixture 1", postal_code="22476", coverage="offers_only")]
    async def get_offers(self, store):
        now = datetime.now(UTC)
        return [Product(product_id="fixture", name="Tomater", canonical_name="tomater", category="mat",
            store_id=store, store_name="Fixture", chain="ica", price=None, sale_price=20,
            effective_price=20, package_quantity=500, package_unit="g", sale_model="fixed_package",
            usable_quantity=500, usable_unit="g",
            quantity_confidence="exact", gtin="7310000000001",
            source_provenance=SourceProvenance(source_provider="own", source_channel="offers",
                source_snapshot_id="fixture", source_observed_at=now, store_id=store),
            offers=[{"kind": "campaign", "description": "Synthetic", "price": 20,
                     "valid_from": now.date(),
                     "valid_to": (now + timedelta(days=2)).date()}])]


async def test_optional_missing_evidence_or_transport_never_blocks_base(tmp_path):
    base = Base([Store(store_id="base", chain="willys", name="Base", city="Lund")])
    for failure in (False, True):
        provider = IcaAreaOfferProvider(base, Own(failure), database=tmp_path/"absent.sqlite",
                                       city="Lund", account_ids=frozenset({"1"}))
        assert await provider.find_stores("22350") == base.rows
        assert "evidence" in provider.diagnostics


async def test_exact_variants_and_real_store_identity_are_required(tmp_path):
    baseline = Store(store_id="base-ica", chain="ica", name="Fixture base", city="Lund",
                     price_context_type="physical_store", physical_store_external_id="1")
    for variants in (1, 2):
        provider = IcaAreaOfferProvider(Base([baseline]), Own(), database=tmp_path/"absent.sqlite",
                                       city="Lund", account_ids=frozenset({"1"}))
        provider.evidence = {"fixture": {"parser_version": "ica-parser-v6",
            "external_product_id": "fixture", "source_fields": json.dumps({"variant_count": variants})}}
        assert await provider.find_stores("22350") == [baseline]
        products = await provider.get_store_products("base-ica")
        assert len(products) == (1 if variants == 1 else 0)
        if products:
            assert products[0].price is None
            assert products[0].source_provenance.provider_store_id == "1"
            assert products[0].offers[0].price_contract_id == "own:fixture:fixture"


def test_deduplication_retains_different_purchase_caps():
    from app.models import OfferMetadata
    a = OfferMetadata(kind="campaign", description="Synthetic", price=20, max_quantity=1)
    b = a.model_copy(update={"max_quantity": 2})
    assert len(OwnGroceryPriceProvider._deduplicate_offers([a, a, b])) == 2


async def test_member_only_ranking_never_becomes_shared_public_sale(tmp_path):
    from app.services.user_pricing import price_candidate_for_context
    from app.models.product import ProductCandidate
    from grocery_data.app.domain.promotion_pricing import UserPricingContext
    class MemberOwn(Own):
        async def get_offers(self, store):
            product=(await super().get_offers(store))[0]
            from app.models.product import OfferMetadata
            offer=OfferMetadata.model_validate({**product.offers[0].model_dump(),
                'kind':'member','eligibility':'member','membership_program':'ICA_STAMMIS','member_program':'ica medlem'})
            return [product.model_copy(update={'offers':[offer]})]
    provider=IcaAreaOfferProvider(Base(),MemberOwn(),database=tmp_path/'absent.sqlite',city='Lund',account_ids=frozenset({'1'}))
    provider.evidence={'fixture':{'parser_version':'ica-parser-v7','external_product_id':'fixture',
                                  'source_fields':json.dumps({'variant_count':1})}}
    stores=await provider.find_stores('22350')
    product=(await provider.get_store_products(stores[0].store_id))[0]
    assert product.price is None and product.conditional_price_signal and product.effective_price==20
    candidate=ProductCandidate.from_product(product,0)
    with pytest.raises(ValueError):
        price_candidate_for_context(candidate,UserPricingContext(),on_date=product.offers[0].valid_from)
    assert price_candidate_for_context(candidate,UserPricingContext.from_chain_flags({'ica':True}),
        on_date=product.offers[0].valid_from).effective_price==20


@pytest.mark.parametrize("corrupt", [False, True])
async def test_optional_database_failure_keeps_full_original_source_build(tmp_path, corrupt):
    from app.services.production_price_universe_build import build_city_price_universe

    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database
    source, _ = _contract_database()
    try:
        database = tmp_path / "base.sqlite"
        _copy_sqlite_database(source, database)
        optional = tmp_path / "optional.sqlite"
        if corrupt:
            optional.write_text("synthetic broken database", encoding="utf8")
        result = await build_city_price_universe(database, "Lund", "22350", None,
            tmp_path/"candidate.json", 48, ica_offer_store_ids=frozenset({"1"}),
            ica_offer_database=optional)
        assert result["status"] == "PASS" and result["raw_products"] == 1
        assert result["persistent_activation"] is False and result["database_unchanged"]
    finally:
        source.dispose()
