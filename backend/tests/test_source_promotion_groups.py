"""Synthetic source contract across the real collector, OWN, PU and checkout."""

from datetime import date
from decimal import Decimal

import httpx
import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.providers.own import OwnGroceryPriceProvider
from app.services.basket_auditor import BasketAuditor
from app.services.basket_optimizer import BasketOptimizer
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.production_price_universe_build import _read_only_app
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain import CoverageLevel, GeographicArea, SourceOffer, SourceProduct
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.domain.purchase_terms import PurchaseTerms
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.tests.test_collector import FixtureWillysConnector


class MixedSource(FixtureWillysConnector):
    coverage = CoverageLevel.OFFERS_ONLY
    parser_version = "synthetic-explicit-mixed-source-v1"

    def parse_stores(self, raw, references, area):
        result = super().parse_stores(raw, references, area)
        return [s.model_copy(update={"coverage": self.coverage}) for s in result]

    async def fetch_offers(self, store):
        return await self.fetch_catalog(store)

    def parse_offers(self, raw, references, store):
        from grocery_data.app.domain import ProductParseResult

        terms = PurchaseTerms(
            source_reference="synthetic:ad:mix",
            purchase_form="fixed_package",
            complete_group_size=3,
            mixing_allowed=True,
            campaign_group_id="synthetic:mix",
            eligible_variant_ids=("rice", "pasta", "not-present"),
            limit_scope="household_campaign",
        )
        offer = SourceOffer(
            type="multibuy",
            price=Decimal(75),
            quantity=3,
            max_quantity=2,
            valid_from=date(2026, 9, 1),
            valid_to=date(2026, 10, 1),
            description="SYNTHETIC: mix three exact source IDs",
            source_payload={"purchase_terms": terms.model_dump(mode="json")},
        )
        return ProductParseResult(
            products=[
                SourceProduct(
                    chain="willys",
                    store_external_id=store.external_id,
                    external_product_id=i,
                    name=n,
                    sale_price=Decimal(25),
                    package_quantity=Decimal(1000),
                    package_unit="g",
                    package_text="1 kg",
                    sale_unit="st",
                    raw_reference=references[0],
                    offers=(offer,),
                )
                for i, n in [("rice", "Ris"), ("pasta", "Pasta")]
            ]
        )

    parse_catalog = parse_offers


@pytest.mark.asyncio
async def test_collector_own_pu_mixed_subset_checkout_and_roundtrip(tmp_path):
    engine = create_database_engine("sqlite:///" + str(tmp_path / "source.sqlite"))
    create_schema(engine)
    sessions = create_session_factory(engine)
    collector = GroceryCollector(sessions, FilesystemRawSnapshotStore(tmp_path / "raw"))
    result = await collector.collect_area(MixedSource(b"{}"), GeographicArea(city="Lund"))
    assert result.promoted
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_read_only_app(sessions)), base_url="http://test"
    ) as client:
        own = OwnGroceryPriceProvider(
            "http://test",
            client=client,
            include_offers_only=True,
            include_conditional_offer_products=True,
        )
        stores = await own.find_offer_stores("22350")
        products = await own.get_offers(stores[0].store_id)
        assert len(products) == 2 and all(p.price is None for p in products)
        assert all(len(p.promotion_groups) == 1 for p in products)
        group = products[0].promotion_groups[0]
        assert set(group.eligible_product_ids) == {p.product_id for p in products}
        assert group.limit_scope == "household_campaign" and group.max_groups == 2
        assert all(
            p.purchase_terms.eligible_variant_ids == ("rice", "pasta", "not-present")
            for p in products
        )
        key = PriceUniverseKey.create(
            city="Lund",
            postal_codes=("22350",),
            snapshot_ids=(result.snapshot_id,),
            memberships={},
            source_strategy_version="synthetic",
            normalizer_version="synthetic",
            taxonomy_version="synthetic",
        )
        universe = PriceUniverseBuilder().build(key, products)
        needs = [
            NormalizedIngredient(canonical_name=p.name.casefold(), required_quantity=1000, unit="g")
            for p in products
        ]
        candidates = {
            n.canonical_name: [
                price_candidate_for_context(
                    ProductCandidate.from_product(p, 1),
                    UserPricingContext(),
                    on_date=date(2026, 9, 24),
                )
            ]
            for p, n in zip(universe.products, needs, strict=True)
        }
        basket = BasketOptimizer().optimize(needs, candidates, stores, max_stores=1)
        assert (
            basket.total == 75
            and sum(i.packages_needed for s in basket.stores for i in s.items) == 3
        )
        assert BasketAuditor(pantry_items=frozenset()).audit(needs, basket).passed
        restored = type(basket).model_validate_json(basket.model_dump_json())
        assert BasketAuditor(pantry_items=frozenset()).audit(needs, restored).passed
    engine.dispose()


def test_source_group_needs_explicit_ids_same_scope_and_consistent_contracts():
    from app.models.product import OfferMetadata
    from app.services.source_promotion_groups import attach_source_groups, groups_in_context

    from backend.tests.test_personal_planning_v2 import product

    terms = PurchaseTerms(
        source_reference="synthetic:ad",
        purchase_form="fixed_package",
        complete_group_size=3,
        mixing_allowed=True,
        campaign_group_id="synthetic:mix",
        eligible_variant_ids=("A", "B"),
    )
    offer = OfferMetadata(
        kind="multipack",
        price=75,
        required_packages=3,
        description="synthetic",
        purchase_terms=terms,
        valid_from=date(2026, 9, 1),
        valid_to=date(2026, 10, 1),
    )
    rows = [
        product(n, 1000, "g", None, effective_price=25, sale_price=None, offers=[offer])
        for n in ["ris", "pasta"]
    ]
    identities = [
        {
            "product_id": p.product_id,
            "external_product_id": external,
            "store_id": p.store_id,
            "source_snapshot_id": p.source_provenance.source_snapshot_id,
        }
        for p, external in zip(rows, ["A", "B"], strict=True)
    ]
    result = attach_source_groups(rows, identities)
    assert all(p.promotion_groups for p in result)
    assert groups_in_context(result[0], "new-context")[0].store_id == "new-context"
    assert not any(
        p.promotion_groups
        for p in attach_source_groups(rows, [{**r, "store_id": "other"} for r in identities])
    )
    assert not any(
        p.promotion_groups
        for p in attach_source_groups(
            rows, [{**r, "external_product_id": "similar name"} for r in identities]
        )
    )
    # A safe subset works; unknown variants are neither invented nor necessary.
    subset = attach_source_groups(rows[:1], identities[:1])
    assert subset[0].promotion_groups[0].eligible_product_ids == (rows[0].product_id,)
    conflicting = [
        rows[0],
        rows[1].model_copy(update={"offers": [offer.model_copy(update={"price": 60})]}),
    ]
    assert not any(p.promotion_groups for p in attach_source_groups(conflicting, identities))
    with pytest.raises(ValueError, match="explicit eligible"):
        PurchaseTerms(source_reference="x", purchase_form="fixed_package", mixing_allowed=True)


def test_new_group_defaults_preserve_existing_artifact_serialization():
    """A rebuild/restart must not invalidate old PU hashes by adding defaults."""
    from app.models.product import PromotionGroup

    legacy_group = {
        "group_id": "saved-group", "chain": "coop", "store_id": "saved-store",
        "eligible_product_ids": ["saved-product"], "required_packages": 2,
        "pricing_rule": "fixed_total", "amount": 30.0,
        "valid_from": "2026-09-21", "valid_to": "2026-09-27",
        "membership_program": None, "max_groups": None,
        "source": "synthetic:saved-source", "source_snapshot_id": "saved-snapshot",
    }
    assert PromotionGroup.model_validate(legacy_group).model_dump(mode="json") == legacy_group
    legacy_terms = PurchaseTerms(
        source_reference="synthetic:saved-ad", purchase_form="piece",
    ).model_dump(mode="json")
    assert "mixing_allowed" not in legacy_terms
    assert "campaign_group_id" not in legacy_terms
    assert PurchaseTerms.model_validate(legacy_terms).model_dump(mode="json") == legacy_terms
