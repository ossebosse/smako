from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain.enums import Chain
from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin


class IdentityEvidenceType(StrEnum):
    """Strong identity evidence accepted by the source bridge."""

    GTIN = "gtin"
    RETAILER_PRODUCT_ID = "retailer_product_id"
    EXPLICIT_REGISTRY = "explicit_registry"


class IdentityDecisionStatus(StrEnum):
    MATCHED = "matched"
    UNMAPPED = "unmapped"
    AMBIGUOUS = "ambiguous"
    SCOPE_MISMATCH = "scope_mismatch"


class IdentityDecisionReason(StrEnum):
    """Stable, reportable reason for every exact-reconciliation decision."""

    EXACT_GTIN = "exact_gtin"
    EXACT_RETAILER_PRODUCT_ID = "exact_retailer_product_id"
    EXPLICIT_REGISTRY_GTIN = "explicit_registry_gtin"
    MULTIPLE_EXACT_EVIDENCE = "multiple_exact_evidence"
    NO_EXACT_IDENTIFIER = "no_exact_identifier"
    EXACT_IDENTIFIER_NOT_FOUND = "exact_identifier_not_found"
    EXACT_IDENTITY_SCOPE_INCOMPATIBLE = "exact_identity_scope_incompatible"
    DUPLICATE_EXACT_IDENTITY = "duplicate_exact_identity"
    CONFLICTING_EXACT_IDENTIFIERS = "conflicting_exact_identifiers"


class IdentityLinkConfidence(StrEnum):
    EXACT = "exact"


class SharedOfferScope(StrEnum):
    """Whether an offer may be stored in the shared PriceUniverse."""

    PUBLIC = "public"
    GENERIC_MEMBER = "generic_member"
    USER_SPECIFIC = "user_specific"
    UNKNOWN = "unknown"


class ExactProductIdentity(BaseModel):
    """A product identity in one exact price/store context.

    Context is part of the key on purpose. Equal GTINs never move an offer
    between stores, an online fulfilment context and a physical-store context,
    or a national/regional offer scope without an explicit upstream mapping.
    Names, brands and package descriptions are deliberately absent: this
    service never performs fuzzy reconciliation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1, max_length=512)
    source_provider: str = Field(default="unknown", min_length=1, max_length=64)
    chain: Chain
    context_id: str = Field(min_length=1, max_length=255)
    retailer_product_id: str | None = Field(default=None, min_length=1, max_length=255)
    retailer_id_namespace: str | None = Field(default=None, min_length=1, max_length=128)
    gtin: str | None = None
    gtin_evidence: IdentityEvidenceType = IdentityEvidenceType.GTIN

    @field_validator(
        "record_id",
        "source_provider",
        "context_id",
        "retailer_product_id",
        "retailer_id_namespace",
        mode="before",
    )
    @classmethod
    def strip_identifiers(cls, value: object) -> object:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @field_validator("gtin", mode="before")
    @classmethod
    def validate_gtin(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        try:
            return normalize_gtin(value).normalized_gtin
        except InvalidGtinError:
            # Invalid source identifiers are not evidence. Keeping the row
            # allows a second exact identifier to match while GTIN fails closed.
            return None


class SourceProductIdentityLink(BaseModel):
    """Auditable exact cross-source identity with an explicit scope verdict.

    The link is deliberately not a fuzzy product mapping.  A persisted link is
    safe for authoritative price attachment only when ``scope_compatible`` is
    true.  ``verified_at`` belongs to the reconciliation/audit run rather than
    to either mutable product row.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_provider: str = Field(min_length=1, max_length=64)
    source_record_id: str = Field(min_length=1, max_length=512)
    source_context_id: str = Field(min_length=1, max_length=255)
    target_provider: str = Field(min_length=1, max_length=64)
    target_record_id: str = Field(min_length=1, max_length=512)
    target_context_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    gtin: str | None = None
    retailer_product_id: str | None = None
    retailer_id_namespace: str | None = None
    evidence: tuple[IdentityEvidenceType, ...]
    scope_compatible: Literal[True] = True
    scope_evidence: str = Field(min_length=1, max_length=255)
    confidence: IdentityLinkConfidence = IdentityLinkConfidence.EXACT
    verified_at: datetime | None = None

    @model_validator(mode="after")
    def validate_exact_link(self) -> SourceProductIdentityLink:
        if not self.evidence:
            raise ValueError("identity link requires exact evidence")
        if (
            self.scope_evidence == "exact_context_id"
            and self.source_context_id != self.target_context_id
        ):
            raise ValueError("exact-context scope evidence requires equal context IDs")
        if IdentityEvidenceType.RETAILER_PRODUCT_ID in self.evidence and (
            self.retailer_product_id is None or self.retailer_id_namespace is None
        ):
            raise ValueError("retailer product evidence requires an explicit namespace")
        if any(
            evidence in {IdentityEvidenceType.GTIN, IdentityEvidenceType.EXPLICIT_REGISTRY}
            for evidence in self.evidence
        ) and self.gtin is None:
            raise ValueError("GTIN evidence requires a checksum-valid GTIN")
        return self


class ExactIdentityDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_record_id: str
    status: IdentityDecisionStatus
    reason: IdentityDecisionReason
    target_record_id: str | None = None
    evidence: tuple[IdentityEvidenceType, ...] = ()
    conflicting_target_ids: tuple[str, ...] = ()
    identity_link: SourceProductIdentityLink | None = None


def _matched_reason(
    evidence: tuple[IdentityEvidenceType, ...],
) -> IdentityDecisionReason:
    if len(evidence) > 1:
        return IdentityDecisionReason.MULTIPLE_EXACT_EVIDENCE
    if evidence == (IdentityEvidenceType.EXPLICIT_REGISTRY,):
        return IdentityDecisionReason.EXPLICIT_REGISTRY_GTIN
    if evidence == (IdentityEvidenceType.RETAILER_PRODUCT_ID,):
        return IdentityDecisionReason.EXACT_RETAILER_PRODUCT_ID
    return IdentityDecisionReason.EXACT_GTIN


def reconcile_exact_identities(
    sources: list[ExactProductIdentity] | tuple[ExactProductIdentity, ...],
    targets: list[ExactProductIdentity] | tuple[ExactProductIdentity, ...],
    *,
    verified_at: datetime | None = None,
) -> tuple[ExactIdentityDecision, ...]:
    """Match source rows to targets using only exact, scope-preserving facts.

    A duplicated GTIN/retailer ID is ambiguous even if another field happens
    to point at one of the duplicates. Two independent identifiers pointing at
    different products are also ambiguous. No arbitrary first-match is ever
    returned.
    """

    gtin_index: dict[tuple[Chain, str, str], set[str]] = defaultdict(set)
    retailer_index: dict[tuple[Chain, str, str, str], set[str]] = defaultdict(set)
    global_gtin_index: dict[tuple[Chain, str], set[str]] = defaultdict(set)
    global_retailer_index: dict[tuple[Chain, str, str], set[str]] = defaultdict(set)
    targets_by_id = {target.record_id: target for target in targets}
    for target in targets:
        if target.gtin is not None:
            gtin_index[(target.chain, target.context_id, target.gtin)].add(target.record_id)
            global_gtin_index[(target.chain, target.gtin)].add(target.record_id)
        if (
            target.retailer_product_id is not None
            and target.retailer_id_namespace is not None
        ):
            retailer_index[
                (
                    target.chain,
                    target.context_id,
                    target.retailer_id_namespace,
                    target.retailer_product_id,
                )
            ].add(target.record_id)
            global_retailer_index[
                (
                    target.chain,
                    target.retailer_id_namespace,
                    target.retailer_product_id,
                )
            ].add(target.record_id)

    decisions: list[ExactIdentityDecision] = []
    for source in sources:
        evidence_targets: list[tuple[IdentityEvidenceType, set[str]]] = []
        if source.gtin is not None:
            evidence_targets.append(
                (
                    source.gtin_evidence,
                    set(gtin_index.get((source.chain, source.context_id, source.gtin), ())),
                )
            )
        if (
            source.retailer_product_id is not None
            and source.retailer_id_namespace is not None
        ):
            evidence_targets.append(
                (
                    IdentityEvidenceType.RETAILER_PRODUCT_ID,
                    set(
                        retailer_index.get(
                            (
                                source.chain,
                                source.context_id,
                                source.retailer_id_namespace,
                                source.retailer_product_id,
                            ),
                            (),
                        )
                    ),
                )
            )

        nonempty = [(kind, rows) for kind, rows in evidence_targets if rows]
        conflicting = sorted({record_id for _kind, rows in nonempty for record_id in rows})
        duplicated_identity = any(len(rows) > 1 for _kind, rows in nonempty)
        if duplicated_identity or len(conflicting) > 1:
            reason = (
                IdentityDecisionReason.DUPLICATE_EXACT_IDENTITY
                if duplicated_identity
                else IdentityDecisionReason.CONFLICTING_EXACT_IDENTIFIERS
            )
            decisions.append(
                ExactIdentityDecision(
                    source_record_id=source.record_id,
                    status=IdentityDecisionStatus.AMBIGUOUS,
                    reason=reason,
                    evidence=tuple(dict.fromkeys(kind for kind, _rows in nonempty)),
                    conflicting_target_ids=tuple(conflicting),
                )
            )
        elif len(conflicting) == 1:
            target_id = conflicting[0]
            target = targets_by_id[target_id]
            evidence = tuple(
                dict.fromkeys(kind for kind, rows in nonempty if target_id in rows)
            )
            decisions.append(
                ExactIdentityDecision(
                    source_record_id=source.record_id,
                    status=IdentityDecisionStatus.MATCHED,
                    reason=_matched_reason(evidence),
                    target_record_id=target_id,
                    evidence=evidence,
                    identity_link=SourceProductIdentityLink(
                        source_provider=source.source_provider,
                        source_record_id=source.record_id,
                        source_context_id=source.context_id,
                        target_provider=target.source_provider,
                        target_record_id=target.record_id,
                        target_context_id=target.context_id,
                        chain=source.chain,
                        gtin=source.gtin or target.gtin,
                        retailer_product_id=(
                            source.retailer_product_id or target.retailer_product_id
                        ),
                        retailer_id_namespace=(
                            source.retailer_id_namespace
                            or target.retailer_id_namespace
                        ),
                        evidence=evidence,
                        scope_compatible=True,
                        scope_evidence="exact_context_id",
                        verified_at=verified_at,
                    ),
                )
            )
        else:
            global_candidates: set[str] = set()
            global_evidence: list[IdentityEvidenceType] = []
            if source.gtin is not None:
                matched_gtin = set(
                    global_gtin_index.get((source.chain, source.gtin), ())
                )
                global_candidates.update(matched_gtin)
                if matched_gtin:
                    global_evidence.append(source.gtin_evidence)
            if (
                source.retailer_product_id is not None
                and source.retailer_id_namespace is not None
            ):
                matched_retailer = set(
                    global_retailer_index.get(
                        (
                            source.chain,
                            source.retailer_id_namespace,
                            source.retailer_product_id,
                        ),
                        (),
                    )
                )
                global_candidates.update(matched_retailer)
                if matched_retailer:
                    global_evidence.append(IdentityEvidenceType.RETAILER_PRODUCT_ID)
            if global_candidates:
                decisions.append(
                    ExactIdentityDecision(
                        source_record_id=source.record_id,
                        status=IdentityDecisionStatus.SCOPE_MISMATCH,
                        reason=(
                            IdentityDecisionReason.EXACT_IDENTITY_SCOPE_INCOMPATIBLE
                        ),
                        evidence=tuple(dict.fromkeys(global_evidence)),
                        conflicting_target_ids=tuple(sorted(global_candidates)),
                    )
                )
                continue
            has_identifier = (
                source.gtin is not None
                or (
                    source.retailer_product_id is not None
                    and source.retailer_id_namespace is not None
                )
            )
            decisions.append(
                ExactIdentityDecision(
                    source_record_id=source.record_id,
                    status=IdentityDecisionStatus.UNMAPPED,
                    reason=(
                        IdentityDecisionReason.EXACT_IDENTIFIER_NOT_FOUND
                        if has_identifier
                        else IdentityDecisionReason.NO_EXACT_IDENTIFIER
                    ),
                )
            )
    return tuple(decisions)


_PERSONAL_MARKERS = (
    "personlig",
    "personal offer",
    "personalized",
    "just for you",
    "din kupong",
    "your coupon",
    "aktiverad kupong",
    "activated coupon",
)
_COUPON_MARKERS = ("kupong", "coupon", "voucher", "bonuscheck")


def classify_shared_offer_scope(
    *,
    chain: Chain,
    member_only: bool,
    description: str | None,
    source_payload: dict[str, object] | None = None,
    source_fields: dict[str, object] | None = None,
) -> SharedOfferScope:
    """Classify shared eligibility without upgrading unclear coupons.

    Existing approved parsers are the authority for non-Lidl generic member
    flags. Lidl has a distinct public Lidl Plus surface *and* coupon wording;
    coupon/personal semantics are therefore rejected from the shared artifact
    unless a future source field explicitly proves generic availability.
    """

    if not member_only:
        return SharedOfferScope.PUBLIC

    payload = source_payload or {}
    fields = source_fields or {}
    explicit_scope = str(
        payload.get("member_offer_scope")
        or fields.get("member_offer_scope")
        or ""
    ).strip().casefold()
    if explicit_scope in {"user_specific", "personal", "personalized"}:
        return SharedOfferScope.USER_SPECIFIC
    if payload.get("personalized_coupon") is True or fields.get("personalized_coupon") is True:
        return SharedOfferScope.USER_SPECIFIC
    text = " ".join(
        str(value or "")
        for value in (
            description,
            payload.get("discount_text"),
            payload.get("lidl_plus_text"),
        )
    ).casefold()
    if any(marker in text for marker in _PERSONAL_MARKERS):
        return SharedOfferScope.USER_SPECIFIC
    if explicit_scope in {"unknown", "coupon_unknown"}:
        return SharedOfferScope.UNKNOWN
    if explicit_scope in {"generic", "generic_member", "public_member"}:
        # A Lidl coupon is not a shared Lidl Plus price merely because a
        # generic flag and coupon-shaped data coexist.  Require the approved
        # public Lidl Plus surface to classify it before it reaches here.
        if chain is Chain.LIDL and any(marker in text for marker in _COUPON_MARKERS):
            return SharedOfferScope.UNKNOWN
        return SharedOfferScope.GENERIC_MEMBER
    if any(marker in text for marker in _COUPON_MARKERS):
        return SharedOfferScope.UNKNOWN
    if chain is not Chain.LIDL:
        return SharedOfferScope.GENERIC_MEMBER
    if fields.get("public_lidl_plus") is True or "lidl plus" in text:
        return SharedOfferScope.GENERIC_MEMBER
    return SharedOfferScope.UNKNOWN


__all__ = [
    "ExactIdentityDecision",
    "ExactProductIdentity",
    "IdentityDecisionReason",
    "IdentityDecisionStatus",
    "IdentityEvidenceType",
    "IdentityLinkConfidence",
    "SharedOfferScope",
    "SourceProductIdentityLink",
    "classify_shared_offer_scope",
    "reconcile_exact_identities",
]
