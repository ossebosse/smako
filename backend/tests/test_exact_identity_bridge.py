from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from app.models import (
    OfferKind,
    OfferMetadata,
    Product,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
    SourceProvenance,
    Store,
)
from app.providers.base import GroceryPriceProvider
from app.providers.exact_identity_bridge import (
    BridgeOffer,
    ExactIdentityBridgeProvider,
)

from grocery_data.app.domain.enums import Chain
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.services.exact_identity_reconciliation import (
    ExactProductIdentity,
    IdentityDecisionReason,
    IdentityDecisionStatus,
    IdentityEvidenceType,
    SharedOfferScope,
    classify_shared_offer_scope,
    reconcile_exact_identities,
)

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


def _identity(
    record_id: str,
    *,
    chain: Chain = Chain.ICA,
    context: str = "1088004",
    gtin: str | None = "7318690492313",
    retailer_id: str | None = None,
    retailer_namespace: str | None = "retailer:ica",
    evidence: IdentityEvidenceType = IdentityEvidenceType.GTIN,
) -> ExactProductIdentity:
    return ExactProductIdentity(
        record_id=record_id,
        chain=chain,
        context_id=context,
        gtin=gtin,
        retailer_product_id=retailer_id,
        retailer_id_namespace=retailer_namespace,
        gtin_evidence=evidence,
    )


def _offer() -> OfferMetadata:
    return OfferMetadata(
        kind=OfferKind.MEMBER,
        description="ICA Stammis",
        price=19.95,
        price_contract_id="own:snapshot:offer-1",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        membership_program=MembershipProgram.ICA_STAMMIS,
        member_program="ICA Stammis",
        valid_from=date(2026, 8, 25),
        valid_to=date(2026, 9, 1),
    )


def _product(
    *,
    gtin: str | None = None,
    context: str = "1088004",
    product_id: str = "product-1",
) -> Product:
    return Product(
        product_id=product_id,
        name="Produkt",
        canonical_name="produkt",
        category="Mat",
        store_id=f"context:ica:{context}",
        store_name="ICA",
        price=29.95,
        sale_price=29.95,
        sale_model=SaleModel.FIXED_PACKAGE,
        package_quantity=500,
        package_unit="g",
        usable_quantity=500,
        usable_unit="g",
        semantic_confidence=SemanticConfidence.HIGH,
        quantity_confidence=QuantityConfidence.EXACT,
        chain="ica",
        gtin=gtin,
        source_provenance=SourceProvenance(
            source_provider="primat",
            source_channel="catalog",
            source_snapshot_id="primat-snapshot",
            source_observed_at=NOW,
            provider_store_id=context,
            price_context="physical_store",
        ),
    )


class _Provider(GroceryPriceProvider):
    def __init__(self, product: Product) -> None:
        super().__init__(use_member_prices=False)
        self.product = product

    async def find_stores(self, postal_code: str) -> list[Store]:
        del postal_code
        return []

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        del query, store_ids
        return [self.product]

    async def get_store_products(self, store_id: str) -> list[Product]:
        del store_id
        return [self.product]

    async def get_offers(self, store_id: str) -> list[Product]:
        del store_id
        return [self.product]


def test_exact_reconciliation_is_context_bound_and_never_fuzzy() -> None:
    source = _identity("offer")
    same = _identity("same")
    other_store = _identity("other", context="1004409")

    [matched] = reconcile_exact_identities([source], [same, other_store])
    assert matched.status is IdentityDecisionStatus.MATCHED
    assert matched.target_record_id == "same"
    assert matched.evidence == (IdentityEvidenceType.GTIN,)
    assert matched.reason is IdentityDecisionReason.EXACT_GTIN
    assert matched.identity_link is not None
    assert matched.identity_link.scope_compatible is True
    assert matched.identity_link.scope_evidence == "exact_context_id"

    [scope_mismatch] = reconcile_exact_identities(
        [_identity("scoped", context="730400")],
        [_identity("physical", context="2696")],
    )
    assert scope_mismatch.status is IdentityDecisionStatus.SCOPE_MISMATCH
    assert (
        scope_mismatch.reason
        is IdentityDecisionReason.EXACT_IDENTITY_SCOPE_INCOMPATIBLE
    )
    assert scope_mismatch.target_record_id is None
    assert scope_mismatch.evidence == (IdentityEvidenceType.GTIN,)


def test_exact_identity_without_target_and_missing_identity_have_distinct_reasons() -> None:
    [not_found] = reconcile_exact_identities(
        [_identity("not-found", gtin="7350027799153")],
        [_identity("target")],
    )
    assert not_found.status is IdentityDecisionStatus.UNMAPPED
    assert not_found.reason is IdentityDecisionReason.EXACT_IDENTIFIER_NOT_FOUND

    [no_identifier] = reconcile_exact_identities(
        [_identity("missing", gtin=None, retailer_id=None)],
        [_identity("target")],
    )
    assert no_identifier.status is IdentityDecisionStatus.UNMAPPED
    assert no_identifier.reason is IdentityDecisionReason.NO_EXACT_IDENTIFIER


def test_duplicate_gtin_or_conflicting_exact_ids_is_ambiguous() -> None:
    duplicate_targets = [
        _identity("first", retailer_id="retailer-a"),
        _identity("second", retailer_id="retailer-b"),
    ]
    [duplicate] = reconcile_exact_identities([_identity("offer")], duplicate_targets)
    assert duplicate.status is IdentityDecisionStatus.AMBIGUOUS
    assert duplicate.reason is IdentityDecisionReason.DUPLICATE_EXACT_IDENTITY
    assert duplicate.conflicting_target_ids == ("first", "second")

    conflicting_source = _identity("conflict", retailer_id="retailer-b")
    targets = [
        _identity("by-gtin", retailer_id="retailer-a"),
        _identity("by-retailer", gtin="7350027799153", retailer_id="retailer-b"),
    ]
    [conflict] = reconcile_exact_identities([conflicting_source], targets)
    assert conflict.status is IdentityDecisionStatus.AMBIGUOUS
    assert conflict.reason is IdentityDecisionReason.CONFLICTING_EXACT_IDENTIFIERS


def test_retailer_id_and_explicit_registry_are_strong_evidence() -> None:
    [retailer] = reconcile_exact_identities(
        [_identity("offer", gtin=None, retailer_id="5004057853")],
        [_identity("product", gtin=None, retailer_id="5004057853")],
    )
    assert retailer.status is IdentityDecisionStatus.MATCHED
    assert retailer.evidence == (IdentityEvidenceType.RETAILER_PRODUCT_ID,)

    [wrong_namespace] = reconcile_exact_identities(
        [
            _identity(
                "offer-wrong-namespace",
                gtin=None,
                retailer_id="5004057853",
                retailer_namespace="own:ica",
            )
        ],
        [
            _identity(
                "product-wrong-namespace",
                gtin=None,
                retailer_id="5004057853",
                retailer_namespace="primat:ica",
            )
        ],
    )
    assert wrong_namespace.status is IdentityDecisionStatus.UNMAPPED
    assert wrong_namespace.reason is IdentityDecisionReason.EXACT_IDENTIFIER_NOT_FOUND

    [registry] = reconcile_exact_identities(
        [
            _identity(
                "offer",
                evidence=IdentityEvidenceType.EXPLICIT_REGISTRY,
            )
        ],
        [_identity("product")],
    )
    assert registry.status is IdentityDecisionStatus.MATCHED
    assert registry.evidence == (IdentityEvidenceType.EXPLICIT_REGISTRY,)


@pytest.mark.parametrize(
    ("description", "discount", "expected"),
    [
        ("Med Lidl Plus", "-20%", SharedOfferScope.GENERIC_MEMBER),
        ("Med Lidl Plus", "Kupong -20%", SharedOfferScope.UNKNOWN),
        ("Din kupong", "-20%", SharedOfferScope.USER_SPECIFIC),
    ],
)
def test_lidl_generic_member_scope_is_strict(
    description: str,
    discount: str,
    expected: SharedOfferScope,
) -> None:
    assert (
        classify_shared_offer_scope(
            chain=Chain.LIDL,
            member_only=True,
            description=description,
            source_payload={"discount_text": discount},
            source_fields={"public_lidl_plus": True},
        )
        is expected
    )


def test_lidl_personal_marker_overrides_inconsistent_generic_flag() -> None:
    assert (
        classify_shared_offer_scope(
            chain=Chain.LIDL,
            member_only=True,
            description="Din kupong",
            source_payload={"member_offer_scope": "generic_member"},
            source_fields={"public_lidl_plus": True},
        )
        is SharedOfferScope.USER_SPECIFIC
    )


def test_lidl_exact_identity_requires_generic_semantics_and_compatible_scope() -> None:
    source = _identity(
        "lidl-plus-offer",
        chain=Chain.LIDL,
        context="public-default-region",
        retailer_id="article-42",
    )
    target = _identity(
        "lidl-catalog-product",
        chain=Chain.LIDL,
        context="public-default-region",
        retailer_id="article-42",
    )
    [matched] = reconcile_exact_identities([source], [target])
    assert matched.status is IdentityDecisionStatus.MATCHED
    assert matched.identity_link is not None
    assert matched.identity_link.scope_compatible is True
    assert (
        classify_shared_offer_scope(
            chain=Chain.LIDL,
            member_only=True,
            description="Med Lidl Plus",
            source_fields={"public_lidl_plus": True},
        )
        is SharedOfferScope.GENERIC_MEMBER
    )

    [wrong_region] = reconcile_exact_identities(
        [source],
        [target.model_copy(update={"context_id": "another-region"})],
    )
    assert wrong_region.status is IdentityDecisionStatus.SCOPE_MISMATCH


def test_coop_physical_offer_scope_never_becomes_online_scope() -> None:
    physical = _identity(
        "coop-physical-offer",
        chain=Chain.COOP,
        context="2696",
        retailer_id="coop-product-1",
    )
    online = _identity(
        "coop-online-product",
        chain=Chain.COOP,
        context="730400",
        retailer_id="coop-product-1",
    )

    [decision] = reconcile_exact_identities([physical], [online])

    assert decision.status is IdentityDecisionStatus.SCOPE_MISMATCH
    assert decision.target_record_id is None


@pytest.mark.asyncio
async def test_bridge_enriches_registry_gtin_and_attaches_only_exact_context_offer() -> None:
    target = _identity(
        "external:ica:1088004:product-1",
        retailer_id="product-1",
        evidence=IdentityEvidenceType.EXPLICIT_REGISTRY,
    )
    bridge_row = BridgeOffer(
        identity=_identity("offer-1", retailer_id=None),
        scope=SharedOfferScope.GENERIC_MEMBER,
        offer=_offer(),
        valid_from=date(2026, 8, 25),
        valid_to=date(2026, 9, 1),
        is_multibuy=False,
    )
    bridge = ExactIdentityBridgeProvider(
        _Provider(_product()),
        targets=[target],
        offers=[bridge_row],
        on_date=date(2026, 8, 31),
    )

    [result] = await bridge.get_store_products("unused")
    assert result.gtin == "7318690492313"
    assert [offer.price_contract_id for offer in result.offers] == [
        "own:snapshot:offer-1"
    ]
    assert result.effective_price == result.price == 29.95
    report = bridge.report()
    assert report["attached_contracts"] == 1
    metrics = report["member_offer_reconciliation"]["ica"]
    assert metrics["semantically_accepted"] == 1
    assert metrics["exact_product_mapped"] == 1
    assert metrics["scope_compatible"] == 1
    assert metrics["retained_active"] == 1
    assert metrics["rejection_reasons"] == {"exact_gtin": 1}
    assert len(report["identity_links"]) == 1
    assert report["identity_links"][0]["scope_compatible"] is True

    wrong_scope = ExactIdentityBridgeProvider(
        _Provider(_product(context="730400")),
        targets=[target],
        offers=[bridge_row],
        on_date=date(2026, 8, 31),
    )
    [not_bridged] = await wrong_scope.get_store_products("unused")
    assert not_bridged.gtin is None
    assert not_bridged.offers == []


@pytest.mark.asyncio
async def test_bridge_preserves_external_product_id_containing_colon() -> None:
    product_id = "retailer:product:1"
    target = _identity(
        f"external:ica:1088004:{product_id}",
        retailer_id=product_id,
    )
    bridge = ExactIdentityBridgeProvider(
        _Provider(_product(product_id=product_id)),
        targets=[target],
        offers=[
            BridgeOffer(
                identity=_identity("offer-colon", retailer_id=None),
                scope=SharedOfferScope.GENERIC_MEMBER,
                offer=_offer(),
                valid_from=date(2026, 8, 25),
                valid_to=date(2026, 9, 1),
                is_multibuy=False,
            )
        ],
        on_date=date(2026, 8, 31),
    )

    [result] = await bridge.get_store_products("unused")
    assert [offer.price_contract_id for offer in result.offers] == [
        "own:snapshot:offer-1"
    ]


def test_unknown_or_user_specific_offer_never_enters_shared_bridge() -> None:
    target = _identity("external:ica:1088004:product-1", retailer_id="product-1")
    rows = [
        BridgeOffer(
            identity=_identity("unknown"),
            scope=SharedOfferScope.UNKNOWN,
            offer=None,
            valid_from=None,
            valid_to=None,
            is_multibuy=False,
        ),
        BridgeOffer(
            identity=_identity("personal"),
            scope=SharedOfferScope.USER_SPECIFIC,
            offer=None,
            valid_from=None,
            valid_to=None,
            is_multibuy=False,
        ),
    ]
    bridge = ExactIdentityBridgeProvider.from_evidence(
        targets=[target],
        offers=rows,
        on_date=date(2026, 8, 31),
    )
    metrics = bridge.report()["member_offer_reconciliation"]["ica"]
    assert metrics["accepted"] == 0
    assert metrics["unknown_scope_excluded"] == 1
    assert metrics["user_specific_excluded"] == 1
