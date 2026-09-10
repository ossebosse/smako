from enum import StrEnum


class Chain(StrEnum):
    ICA = "ica"
    COOP = "coop"
    WILLYS = "willys"
    HEMKOP = "hemkop"
    LIDL = "lidl"
    CITY_GROSS = "citygross"


class CoverageLevel(StrEnum):
    FULL_CATALOG = "full_catalog"
    FULL_ONLINE_CATALOG = "full_online_catalog"
    PARTIAL_CATALOG = "partial_catalog"
    OFFERS_ONLY = "offers_only"
    UNAVAILABLE = "unavailable"


_COMPLETE_CATALOG_COVERAGE = frozenset(
    {
        CoverageLevel.FULL_CATALOG,
        CoverageLevel.FULL_ONLINE_CATALOG,
    }
)


def is_complete_catalog_coverage(value: CoverageLevel | str) -> bool:
    """Return whether coverage proves a complete declared catalog scope.

    ``FULL_ONLINE_CATALOG`` is complete for the chain's explicitly declared
    online assortment context.  It deliberately does not claim every product
    in a physical store.  Unknown persisted or remote values fail closed.
    """

    try:
        coverage = CoverageLevel(value)
    except ValueError:
        return False
    return coverage in _COMPLETE_CATALOG_COVERAGE


class SourcePolicy(StrEnum):
    """Operational permission for collecting from a technically visible source."""

    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


class SourceTechnicalCapability(StrEnum):
    """Observed source potential, kept separate from operational coverage."""

    VERIFIED_FULL_CATALOG = "verified_full_catalog"
    LIKELY_FULL_ONLINE_CATALOG = "likely_full_online_catalog"
    PARTIAL_CATALOG = "partial_catalog"
    OFFERS_ONLY = "offers_only"
    UNAVAILABLE = "unavailable"


class PriceContextType(StrEnum):
    """The commercial context that owns assortment and price observations.

    This is deliberately independent of chain and coverage.  In particular, an
    online store may be linked to a physical site without claiming that its
    online prices are physical shelf prices.
    """

    PHYSICAL_STORE = "physical_store"
    ONLINE_STORE = "online_store"
    ONLINE_FULFILLMENT = "online_fulfillment"
    REGIONAL = "regional"


class StoreContextRelationType(StrEnum):
    """Evidence-backed relationship between a site and a commercial context."""

    EXACT_STORE_ONLINE_CONTEXT = "exact_store_online_context"
    PICKUP_CONTEXT = "pickup_context"
    DELIVERY_CONTEXT = "delivery_context"
    REGIONAL_CONTEXT = "regional_context"
    UNKNOWN = "unknown"


class StoreIdentityMatchConfidence(StrEnum):
    """Evidence strength for mapping a provider context to a physical store.

    Only the first four values are eligible for automatic activation. Name
    similarity on its own is deliberately represented by ``PROBABLE`` and is
    therefore suggestion-only.
    """

    EXACT_ID = "exact_id"
    EXACT_ADDRESS = "exact_address"
    EXACT_NAME_AND_POSTAL = "exact_name_and_postal"
    STRONG_GEO = "strong_geo"
    PROBABLE = "probable"
    AMBIGUOUS = "ambiguous"
    NONE = "none"


class ProviderStoreMappingStatus(StrEnum):
    """Persistent state of one external-provider identity mapping."""

    VERIFIED = "verified"
    MAPPING_DRIFT = "mapping_drift"
    UNRESOLVED = "unresolved"


class PhysicalStoreLifecycleState(StrEnum):
    """Non-destructive lifecycle for official physical-store discovery."""

    ACTIVE = "active"
    NOT_SEEN = "not_seen"


class PhysicalStoreCoverageState(StrEnum):
    """Current reconciliation state for one official physical store."""

    DISCOVERED = "discovered"
    MAPPED = "mapped"
    BASKET_CAPABLE = "basket_capable"
    OFFERS_ONLY = "offers_only"
    NO_PRICE_CONTEXT = "no_price_context"
    STALE = "stale"
    MISSING = "missing"


class PriceContextState(StrEnum):
    """Exactly one explainable price-context state for an active physical store.

    These values describe usable price evidence, not the existence of the
    physical site.  In particular, a regional offer surface never claims a
    store-specific shelf price and an unresolved external identity is never
    silently treated as an eligible basket context.
    """

    OWN_FULL_CONTEXT = "own_full_context"
    EXTERNAL_FULL_CONTEXT = "external_full_context"
    OWN_OFFERS_ONLY = "own_offers_only"
    REGIONAL_OFFERS_ONLY = "regional_offers_only"
    NO_PRICE_CONTEXT = "no_price_context"
    STALE_CONTEXT = "stale_context"
    MAPPING_UNRESOLVED = "mapping_unresolved"


class StoreDiscoveryErrorCode(StrEnum):
    """Closed operational outcomes for bounded official-store discovery."""

    EMPTY_LOCATOR_RESULT = "empty_locator_result"
    STORE_COUNT_COLLAPSE = "store_count_collapse_requires_confirmation"
    BOUNDED_TIMEOUT = "bounded_timeout"
    SCHEMA_OR_IDENTITY_CONTRACT_FAILED = "schema_or_identity_contract_failed"
    DISCOVERY_FAILED = "official_store_discovery_failed"
    MISSING_ADAPTER = "missing_adapter"


class SaleModel(StrEnum):
    FIXED_PACKAGE = "fixed_package"
    SOLD_BY_WEIGHT = "sold_by_weight"
    SOLD_BY_PIECE = "sold_by_piece"
    VARIABLE_WEIGHT_PACKAGE = "variable_weight_package"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    EXACT = "exact"
    HIGH = "high"
    DERIVED = "derived"
    MEDIUM = "medium"
    ESTIMATED = "estimated"
    LOW = "low"
    UNKNOWN = "unknown"
    REJECTED = "rejected"


class PromotionType(StrEnum):
    SALE_PRICE = "sale_price"
    MEMBER_PRICE = "member_price"
    MULTIBUY = "multibuy"
    PERCENT_DISCOUNT = "percent_discount"
    OTHER = "other"


class ParserErrorCode(StrEnum):
    MISSING_PRODUCT_ID = "missing_product_id"
    INVALID_PRICE = "invalid_price"
    UNKNOWN_PRICE_UNIT = "unknown_price_unit"
    UNKNOWN_PACKAGE_FORMAT = "unknown_package_format"
    MISSING_NAME = "missing_name"
    SCHEMA_CHANGED = "schema_changed"
    INVALID_PROMOTION = "invalid_promotion"
    INVALID_JSON = "invalid_json"
    UNKNOWN = "unknown"


class ConnectorStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BROKEN = "broken"
    STALE = "stale"
    UNKNOWN = "unknown"


class SnapshotState(StrEnum):
    FETCHED = "fetched"
    PARSED = "parsed"
    VALIDATED = "validated"
    HEALTH_CHECKED = "health_checked"
    PROMOTED = "promoted"
    REJECTED = "rejected"
