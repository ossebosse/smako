from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import OfferKind, OfferMetadata, Product, Store
from app.providers.base import GroceryPriceProvider

from grocery_data.app.domain.enums import DEFAULT_SOURCE_CHAINS, Chain, CoverageLevel
from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.services.exact_identity_reconciliation import (
    ExactProductIdentity,
    IdentityDecisionStatus,
    IdentityEvidenceType,
    SharedOfferScope,
    classify_shared_offer_scope,
    reconcile_exact_identities,
)

_STOCKHOLM = ZoneInfo("Europe/Stockholm")


@dataclass(frozen=True, slots=True)
class BridgeOffer:
    identity: ExactProductIdentity
    scope: SharedOfferScope
    offer: OfferMetadata | None
    valid_from: date | None
    valid_to: date | None
    is_multibuy: bool


def _json_object(value: object) -> dict[str, object]:
    if isinstance(value, Mapping):
        return {str(key): nested for key, nested in value.items()}
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return (
        {str(key): nested for key, nested in decoded.items()}
        if isinstance(decoded, Mapping)
        else {}
    )


def _chain(value: object) -> Chain | None:
    normalized = str(value or "").strip().casefold().replace("_", "")
    aliases = {"citygross": Chain.CITY_GROSS}
    if normalized in aliases:
        return aliases[normalized]
    try:
        return Chain(normalized)
    except ValueError:
        return None


def _text(value: object) -> str | None:
    normalized = str(value).strip() if value is not None else ""
    return normalized or None


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _period_state(row: BridgeOffer, on_date: date) -> str:
    if row.valid_from is not None and on_date < row.valid_from:
        return "future"
    if row.valid_to is not None and on_date > row.valid_to:
        return "expired"
    return "active"


def _target_record_id(
    *,
    source: str,
    chain: Chain,
    context_id: str,
    product_id: str,
) -> str:
    return f"{source}:{chain.value}:{context_id}:{product_id}"


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _database_targets(connection: sqlite3.Connection) -> list[ExactProductIdentity]:
    rows = connection.execute(
        """
        SELECT
            p.id AS product_id,
            p.chain,
            p.gtin AS product_gtin,
            sp.gtin AS source_gtin,
            sp.external_product_id,
            sp.store_id,
            s.external_id AS context_id,
            cs.id AS snapshot_id,
            cs.promoted_at,
            cs.created_at
        FROM products AS p
        JOIN source_products AS sp ON sp.id = p.source_product_id
        JOIN stores AS s ON s.id = sp.store_id
        JOIN catalog_snapshots AS cs ON cs.id = sp.catalog_snapshot_id
        WHERE cs.is_active = 1
          AND cs.state = 'promoted'
          AND cs.coverage IN (?, ?)
        """,
        (CoverageLevel.FULL_CATALOG.value, CoverageLevel.FULL_ONLINE_CATALOG.value),
    ).fetchall()
    latest_snapshot_by_store: dict[str, tuple[str, str]] = {}
    for row in rows:
        ordering = str(row["promoted_at"] or row["created_at"] or "")
        current = latest_snapshot_by_store.get(str(row["store_id"]))
        if current is None or ordering > current[0]:
            latest_snapshot_by_store[str(row["store_id"])] = (ordering, str(row["snapshot_id"]))

    registry_rows = (
        connection.execute(
            """
            SELECT chain, scope_key, external_product_id, identifier_value
            FROM product_identifier_evidence
            WHERE is_active = 1
              AND identifier_type = 'gtin'
              AND lower(confidence) IN ('exact', 'high', 'verified')
            """
        ).fetchall()
        if _table_exists(connection, "product_identifier_evidence")
        else ()
    )
    registry: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for row in registry_rows:
        registry[
            (
                str(row["chain"]),
                str(row["scope_key"]),
                str(row["external_product_id"]),
            )
        ].add(str(row["identifier_value"]))

    targets: list[ExactProductIdentity] = []
    for row in rows:
        latest = latest_snapshot_by_store.get(str(row["store_id"]))
        if latest is None or latest[1] != str(row["snapshot_id"]):
            continue
        chain = _chain(row["chain"])
        context_id = _text(row["context_id"])
        product_id = _text(row["product_id"])
        if chain is None or context_id is None or product_id is None:
            continue
        retailer_product_id = _text(row["external_product_id"])
        gtin = _text(row["product_gtin"] or row["source_gtin"])
        evidence = IdentityEvidenceType.GTIN
        if gtin is None and retailer_product_id is not None:
            values = registry.get((chain.value, context_id, retailer_product_id), set())
            if len(values) == 1:
                gtin = next(iter(values))
                evidence = IdentityEvidenceType.EXPLICIT_REGISTRY
        targets.append(
            ExactProductIdentity(
                record_id=_target_record_id(
                    source="own",
                    chain=chain,
                    context_id=context_id,
                    product_id=product_id,
                ),
                source_provider="own",
                chain=chain,
                context_id=context_id,
                retailer_product_id=retailer_product_id,
                retailer_id_namespace=f"own:{chain.value}",
                gtin=gtin,
                gtin_evidence=evidence,
            )
        )
    return targets


def _external_targets(products: Iterable[Product]) -> list[ExactProductIdentity]:
    targets: list[ExactProductIdentity] = []
    for product in products:
        chain = _chain(product.chain)
        provenance = product.source_provenance
        context_id = _text(
            provenance.provider_store_id if provenance is not None else None
        )
        if chain is None or context_id is None:
            continue
        targets.append(
            ExactProductIdentity(
                record_id=_target_record_id(
                    source="external",
                    chain=chain,
                    context_id=context_id,
                    product_id=product.product_id,
                ),
                source_provider=(
                    provenance.source_provider
                    if provenance is not None
                    else "external"
                ),
                chain=chain,
                context_id=context_id,
                retailer_product_id=product.product_id,
                retailer_id_namespace=(
                    f"{provenance.source_provider}:{chain.value}"
                    if provenance is not None
                    else None
                ),
                gtin=product.gtin,
            )
        )
    return targets


def _offer_metadata(row: sqlite3.Row, chain: Chain) -> OfferMetadata | None:
    try:
        price = float(row["price"])
    except (TypeError, ValueError, OverflowError):
        return None
    if price <= 0:
        return None
    try:
        quantity = int(row["quantity"] or 1)
    except (TypeError, ValueError, OverflowError):
        return None
    if quantity < 1:
        return None
    try:
        max_quantity = int(row["max_quantity"]) if row["max_quantity"] is not None else None
    except (TypeError, ValueError, OverflowError):
        return None
    if max_quantity is not None and max_quantity < 1:
        return None

    raw_type = str(row["type"] or "").casefold()
    multibuy = raw_type in {"multibuy", "multipack"} and quantity >= 2
    kind = OfferKind.MULTIPACK if multibuy else OfferKind.MEMBER
    mechanism = PromotionMechanism.MULTIBUY if multibuy else PromotionMechanism.SALE_PRICE
    description = _text(row["description"]) or (
        f"{quantity} för {price:g} kr" if multibuy else "Medlemspris"
    )
    return OfferMetadata(
        kind=kind,
        description=description,
        price=price,
        required_packages=quantity if multibuy else 1,
        max_quantity=max_quantity,
        price_contract_id=f"own:{row['snapshot_id']}:{row['promotion_id']}",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=mechanism,
        membership_program=MembershipProgram.from_value(chain.value),
        member_program=MembershipProgram.from_value(chain.value).consumer_label,
        source_confidence="promoted_snapshot",
        semantic_confidence="source_explicit_member",
        quantity_confidence="exact" if multibuy else "not_applicable",
        valid_from=_parse_date(row["valid_from"]),
        valid_to=_parse_date(row["valid_to"]),
    )


def _database_member_offers(connection: sqlite3.Connection) -> list[BridgeOffer]:
    rows = connection.execute(
        """
        SELECT
            pr.id AS promotion_id,
            pr.catalog_snapshot_id AS snapshot_id,
            pr.type,
            pr.valid_from,
            pr.valid_to,
            pr.price,
            pr.quantity,
            pr.max_quantity,
            pr.member_only,
            pr.description,
            pr.source_payload,
            sp.external_product_id,
            sp.gtin,
            sp.source_fields,
            sp.chain,
            s.external_id AS context_id
        FROM promotions AS pr
        JOIN source_products AS sp ON sp.id = pr.source_product_id
        JOIN stores AS s ON s.id = sp.store_id
        JOIN catalog_snapshots AS cs ON cs.id = pr.catalog_snapshot_id
        WHERE cs.is_active = 1
          AND cs.state = 'promoted'
          AND cs.coverage = ?
          AND pr.member_only = 1
          AND pr.price IS NOT NULL
        ORDER BY sp.chain, s.external_id, pr.id
        """,
        (CoverageLevel.OFFERS_ONLY.value,),
    ).fetchall()
    offers: list[BridgeOffer] = []
    for row in rows:
        chain = _chain(row["chain"])
        context_id = _text(row["context_id"])
        if chain is None or context_id is None:
            continue
        payload = _json_object(row["source_payload"])
        source_fields = _json_object(row["source_fields"])
        scope = classify_shared_offer_scope(
            chain=chain,
            member_only=True,
            description=_text(row["description"]),
            source_payload=payload,
            source_fields=source_fields,
        )
        metadata = (
            _offer_metadata(row, chain)
            if scope is SharedOfferScope.GENERIC_MEMBER
            else None
        )
        offers.append(
            BridgeOffer(
                identity=ExactProductIdentity(
                    record_id=str(row["promotion_id"]),
                    source_provider="own",
                    chain=chain,
                    context_id=context_id,
                    retailer_product_id=_text(row["external_product_id"]),
                    retailer_id_namespace=f"own:{chain.value}",
                    gtin=_text(row["gtin"]),
                ),
                scope=scope,
                offer=metadata,
                valid_from=_parse_date(row["valid_from"]),
                valid_to=_parse_date(row["valid_to"]),
                is_multibuy=(
                    str(row["type"] or "").casefold() in {"multibuy", "multipack"}
                    and int(row["quantity"] or 1) >= 2
                ),
            )
        )
    return offers


def load_exact_identity_bridge(
    database: Path,
    *,
    external_products: Sequence[Product] = (),
    on_date: date | None = None,
    exclude_offer_chains: frozenset[Chain] = frozenset(),
) -> ExactIdentityBridgeProvider:
    """Load only promoted local evidence through immutable SQLite access."""

    resolved = database.resolve(strict=True)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        targets = [*_database_targets(connection), *_external_targets(external_products)]
        offers = [row for row in _database_member_offers(connection)
                  if row.identity.chain not in exclude_offer_chains]
    finally:
        connection.close()
    return ExactIdentityBridgeProvider.from_evidence(
        targets=targets,
        offers=offers,
        on_date=on_date,
    )


class ExactIdentityBridgeProvider(GroceryPriceProvider):
    """Decorate a provider with pre-reconciled, immutable member contracts."""

    source_name = "exact-identity-bridge"
    attribution_text = "Exakt identifieringsbrygga över godkända snapshots"

    def __init__(
        self,
        inner: GroceryPriceProvider | None,
        *,
        targets: Sequence[ExactProductIdentity],
        offers: Sequence[BridgeOffer],
        on_date: date | None = None,
        verified_at: datetime | None = None,
    ) -> None:
        super().__init__(use_member_prices=False)
        self._inner = inner
        if inner is not None:
            self.source_name = getattr(
                inner,
                "source_name",
                ExactIdentityBridgeProvider.source_name,
            )
            self.attribution_text = getattr(
                inner,
                "attribution_text",
                ExactIdentityBridgeProvider.attribution_text,
            )
        self._targets = {target.record_id: target for target in targets}
        self._offers = tuple(offers)
        self._verified_at = verified_at or datetime.now(tz=_STOCKHOLM)
        safe = [
            row.identity
            for row in self._offers
            if row.scope is SharedOfferScope.GENERIC_MEMBER and row.offer is not None
        ]
        self._decisions = {
            decision.source_record_id: decision
            for decision in reconcile_exact_identities(
                safe,
                list(targets),
                verified_at=self._verified_at,
            )
        }
        self._offers_by_target: dict[str, list[OfferMetadata]] = defaultdict(list)
        by_id = {row.identity.record_id: row for row in self._offers}
        for decision in self._decisions.values():
            if (
                decision.status is IdentityDecisionStatus.MATCHED
                and decision.target_record_id is not None
            ):
                row = by_id[decision.source_record_id]
                assert row.offer is not None
                self._offers_by_target[decision.target_record_id].append(row.offer)
        self._on_date = on_date or datetime.now(tz=_STOCKHOLM).date()
        target_candidates: dict[
            tuple[str, str, str],
            list[ExactProductIdentity],
        ] = defaultdict(list)
        for target in targets:
            # External provider product IDs are already the exact retailer ID
            # and may themselves contain a colon.  OWN provider rows use the
            # internal product UUID encoded as the record-id suffix.
            product_id = (
                target.retailer_product_id
                if target.record_id.startswith("external:")
                and target.retailer_product_id is not None
                else target.record_id.rsplit(":", 1)[-1]
            )
            target_candidates[(target.chain.value, target.context_id, product_id)].append(
                target
            )
        self._target_lookup = {
            key: rows[0]
            for key, rows in target_candidates.items()
            if len(rows) == 1
        }
        self._attached_contract_ids: set[str] = set()
        self._registry_gtin_targets_applied: set[str] = set()

    @classmethod
    def from_evidence(
        cls,
        *,
        targets: Sequence[ExactProductIdentity],
        offers: Sequence[BridgeOffer],
        on_date: date | None = None,
        verified_at: datetime | None = None,
    ) -> ExactIdentityBridgeProvider:
        return cls(
            None,
            targets=targets,
            offers=offers,
            on_date=on_date,
            verified_at=verified_at,
        )

    def bind(self, inner: GroceryPriceProvider) -> ExactIdentityBridgeProvider:
        return type(self)(
            inner,
            targets=tuple(self._targets.values()),
            offers=self._offers,
            on_date=self._on_date,
            verified_at=self._verified_at,
        )

    @staticmethod
    def _deduplicate_offers(offers: Sequence[OfferMetadata]) -> list[OfferMetadata]:
        selected: dict[tuple[object, ...], OfferMetadata] = {}
        for offer in offers:
            key = (
                offer.price_contract_id,
                offer.eligibility,
                offer.mechanism,
                offer.membership_program,
                round(offer.price, 4),
                offer.required_packages,
                offer.max_quantity,
                offer.valid_from,
                offer.valid_to,
            )
            selected.setdefault(key, offer)
        return list(selected.values())

    def _bridge(self, products: Sequence[Product]) -> list[Product]:
        result: list[Product] = []
        for product in products:
            chain = _chain(product.chain)
            provenance = product.source_provenance
            context_id = _text(
                provenance.provider_store_id if provenance is not None else None
            )
            if chain is None or context_id is None:
                result.append(product)
                continue
            target = self._target_lookup.get((chain.value, context_id, product.product_id))
            if target is None:
                result.append(product)
                continue
            updates: dict[str, object] = {}
            if product.gtin is None and target.gtin is not None:
                updates["gtin"] = target.gtin
                if target.gtin_evidence is IdentityEvidenceType.EXPLICIT_REGISTRY:
                    self._registry_gtin_targets_applied.add(target.record_id)
            extra = self._offers_by_target.get(target.record_id, ())
            if extra:
                offers = self._deduplicate_offers([*product.offers, *extra])
                updates["offers"] = offers
                self._attached_contract_ids.update(
                    offer.price_contract_id
                    for offer in extra
                    if offer.price_contract_id is not None
                )
            result.append(product.model_copy(update=updates, deep=True) if updates else product)
        return result

    def report(self) -> dict[str, object]:
        report: dict[str, dict[str, object]] = {}
        for chain in DEFAULT_SOURCE_CHAINS:
            rows = [row for row in self._offers if row.identity.chain is chain]
            if not rows:
                continue
            decisions = {
                row.identity.record_id: self._decisions.get(row.identity.record_id)
                for row in rows
            }
            states = [_period_state(row, self._on_date) for row in rows]
            accepted_rows = [
                row
                for row in rows
                if (
                    (decision := decisions[row.identity.record_id]) is not None
                    and decision.status is IdentityDecisionStatus.MATCHED
                )
            ]
            semantic_rows = [
                row
                for row in rows
                if row.scope is SharedOfferScope.GENERIC_MEMBER
                and row.offer is not None
            ]
            accepted_ids = {
                row.identity.record_id for row in accepted_rows
            }
            reason_counts: dict[str, int] = defaultdict(int)
            for decision in decisions.values():
                if decision is not None:
                    reason_counts[decision.reason.value] += 1
            unknown_scope = sum(
                row.scope is SharedOfferScope.UNKNOWN for row in rows
            )
            user_specific = sum(
                row.scope is SharedOfferScope.USER_SPECIFIC for row in rows
            )
            if unknown_scope:
                reason_counts["unknown_eligibility"] += unknown_scope
            if user_specific:
                reason_counts["user_specific_excluded"] += user_specific
            semantic_states = [
                _period_state(row, self._on_date) for row in semantic_rows
            ]
            target_contexts = sorted(
                {
                    target.context_id
                    for target in self._targets.values()
                    if target.chain is chain
                }
            )
            report[chain.value] = {
                "discovered": len(rows),
                "semantically_accepted": len(semantic_rows),
                "semantically_accepted_active": semantic_states.count("active"),
                "semantically_accepted_expired": semantic_states.count("expired"),
                "semantically_accepted_future": semantic_states.count("future"),
                "accepted": len(accepted_rows),
                "exact_product_mapped": len(accepted_rows),
                "scope_compatible": len(accepted_rows),
                "accepted_active": sum(
                    _period_state(row, self._on_date) == "active"
                    for row in accepted_rows
                ),
                "retained_active": sum(
                    _period_state(row, self._on_date) == "active"
                    for row in accepted_rows
                ),
                "active": states.count("active"),
                "expired": states.count("expired"),
                "future": states.count("future"),
                "source_contexts": sorted(
                    {row.identity.context_id for row in rows}
                ),
                "target_contexts": target_contexts,
                "with_gtin": sum(row.identity.gtin is not None for row in rows),
                "with_retailer_product_id": sum(
                    row.identity.retailer_product_id is not None for row in rows
                ),
                "unmapped": sum(
                    decision is not None
                    and decision.status is IdentityDecisionStatus.UNMAPPED
                    for decision in decisions.values()
                ),
                "unmapped_identity": sum(
                    decision is not None
                    and decision.status is IdentityDecisionStatus.UNMAPPED
                    for decision in decisions.values()
                ),
                "scope_mismatch": sum(
                    decision is not None
                    and decision.status is IdentityDecisionStatus.SCOPE_MISMATCH
                    for decision in decisions.values()
                ),
                "ambiguous": sum(
                    decision is not None
                    and decision.status is IdentityDecisionStatus.AMBIGUOUS
                    for decision in decisions.values()
                ),
                "user_specific_excluded": user_specific,
                "unknown_scope_excluded": unknown_scope,
                "user_specific_or_unknown_excluded": (
                    user_specific + unknown_scope
                ),
                "member_multibuy": sum(row.is_multibuy for row in rows),
                "active_member_multibuy": sum(
                    row.is_multibuy and _period_state(row, self._on_date) == "active"
                    for row in rows
                ),
                "retained_active_member_multibuy": sum(
                    row.is_multibuy
                    and _period_state(row, self._on_date) == "active"
                    and row.identity.record_id in accepted_ids
                    for row in rows
                ),
                "rejection_reasons": dict(sorted(reason_counts.items())),
            }
        enriched = sum(
            target.gtin is not None
            and target.gtin_evidence is IdentityEvidenceType.EXPLICIT_REGISTRY
            for target in self._targets.values()
        )
        return {
            "member_offer_reconciliation": report,
            "targets": len(self._targets),
            "registry_gtins_available": enriched,
            "registry_gtins_applied": len(self._registry_gtin_targets_applied),
            "attached_contracts": len(self._attached_contract_ids),
            "fuzzy_matches": 0,
            "identity_links": [
                decision.identity_link.model_dump(mode="json")
                for decision in sorted(
                    self._decisions.values(),
                    key=lambda row: row.source_record_id,
                )
                if decision.identity_link is not None
            ],
            "identity_link_policy": {
                "identity": "exact_gtin_retailer_id_or_verified_registry_only",
                "scope": "exact_context_id",
                "confidence": "exact",
                "fuzzy_authoritative_join": False,
            },
        }

    def _required_inner(self) -> GroceryPriceProvider:
        if self._inner is None:
            raise RuntimeError("exact identity bridge must be bound before provider use")
        return self._inner

    async def find_stores(self, postal_code: str) -> list[Store]:
        return await self._required_inner().find_stores(postal_code)

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        return self._bridge(await self._required_inner().search_products(query, store_ids))

    async def get_store_products(self, store_id: str) -> list[Product]:
        return self._bridge(await self._required_inner().get_store_products(store_id))

    async def get_offers(self, store_id: str) -> list[Product]:
        return self._bridge(await self._required_inner().get_offers(store_id))

    async def aclose(self) -> None:
        inner = self._inner
        close = getattr(inner, "aclose", None) if inner is not None else None
        if close is not None:
            await close()


__all__ = [
    "BridgeOffer",
    "ExactIdentityBridgeProvider",
    "load_exact_identity_bridge",
]
