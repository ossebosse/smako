from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.community_evidence import (
    CommunityEvidenceSubmission,
    CommunityEvidenceType,
    ModerationDecision,
)
from grocery_data.app.services.community_receipts import (
    ReceiptIngestionRequest,
    ReceiptIngestionService,
    ReceiptRateLimitError,
)
from grocery_data.app.services.evidence_reconciler import EvidenceReconciler
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.community_evidence import (
    CommunityEvidenceRateLimitError,
    CommunityEvidenceRepository,
)
from grocery_data.app.storage.models import (
    CommunityEvidenceObservationModel,
    PhysicalStoreModel,
)


def get_community_session(request: Request) -> Iterator[Session]:
    factory = getattr(request.app.state, "community_session_factory", None) or getattr(
        request.app.state,
        "session_factory",
        None,
    )
    if factory is None:
        raise RuntimeError("community evidence session factory is not configured")
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


SessionDep = Annotated[Session, Depends(get_community_session)]


class CommunityEvidenceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    evidence_type: str
    evidence_source: str
    verification_status: str
    created_at: datetime
    observed_at: datetime
    chain: str | None
    physical_store_id: str | None
    source_provider_store_id: str | None
    store_identity_verified: bool
    store_display_name: str | None
    grocery_context_id: str | None
    gtin: str | None
    source_product_id: str | None
    product_name: str | None
    brand: str | None
    package_description: str | None
    physical_presence: bool | None
    shelf_price: Decimal | None
    digital_price: Decimal | None
    unit_price: Decimal | None
    price_unit: str | None
    quantity: Decimal | None
    identity_confidence: str
    evidence_confidence: Decimal
    plan_id: str | None
    price_snapshot_id: str | None
    promotion: dict[str, Any] | None
    replayed: bool = False
    duplicate: bool = False


class ReceiptIngestionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: str
    parser: str
    retailer: str | None
    purchase_observed_at: datetime | None
    parsed_lines: list[dict[str, Any]]
    evidence_ids: list[str]
    warnings: list[str]
    raw_retained: bool
    raw_discarded_at: datetime
    retention_expires_at: datetime
    privacy_notice: str


class ReconciliationQuery(BaseModel):
    physical_store_id: str
    gtin: str | None = None
    source_product_id: str | None = None
    source_price: Decimal | None = None
    source_price_unit: str | None = None
    price_unit: str | None = None
    source_supported_available: bool | None = None


class CommunityPhysicalStoreOption(BaseModel):
    """Consumer-safe exact physical-store identity for report attribution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    chain: str
    external_store_id: str | None
    name: str
    address: str | None
    postal_code: str | None
    city: str | None


def _settings(request: Request) -> GroceryDataSettings:
    configured = getattr(request.app.state, "community_evidence_settings", None)
    if isinstance(configured, GroceryDataSettings):
        return configured
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, GroceryDataSettings):
        return configured
    return GroceryDataSettings.from_env()


def _admin_authorized(
    request: Request,
    x_community_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = _settings(request).community_admin_token
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="community moderation API is disabled; use the local CLI",
        )
    if not x_community_admin_token or not hmac.compare_digest(
        x_community_admin_token,
        expected,
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


def _promotion(row: CommunityEvidenceObservationModel) -> dict[str, Any] | None:
    if row.promotion_mechanism is None:
        return None
    return {
        "eligibility": row.promotion_eligibility,
        "mechanism": row.promotion_mechanism,
        "regular_price": row.promotion_regular_price,
        "active_price": row.promotion_active_price,
        "required_quantity": row.promotion_required_quantity,
        "total_price": row.promotion_total_price,
        "percent_discount": row.promotion_percent_discount,
        "max_quantity": row.promotion_max_quantity,
        "member_program": row.promotion_member_program,
        "valid_from": row.promotion_valid_from,
        "valid_to": row.promotion_valid_to,
        "description": row.promotion_description,
    }


def _response(
    row: CommunityEvidenceObservationModel,
    repository: CommunityEvidenceRepository,
    *,
    replayed: bool = False,
    duplicate: bool = False,
) -> CommunityEvidenceResponse:
    return CommunityEvidenceResponse(
        id=row.id,
        evidence_type=row.evidence_type,
        evidence_source=row.evidence_source,
        verification_status=repository.current_status(row.id).value,
        created_at=row.created_at,
        observed_at=row.observed_at,
        chain=row.chain,
        physical_store_id=row.physical_store_id,
        source_provider_store_id=row.source_provider_store_id,
        store_identity_verified=row.store_identity_verified,
        store_display_name=row.store_display_name,
        grocery_context_id=row.grocery_context_id,
        gtin=row.gtin,
        source_product_id=row.source_product_id,
        product_name=row.product_name,
        brand=row.brand,
        package_description=row.package_description,
        physical_presence=row.physical_presence,
        shelf_price=row.shelf_price,
        digital_price=row.digital_price,
        unit_price=row.unit_price,
        price_unit=row.price_unit,
        quantity=row.quantity,
        identity_confidence=row.identity_confidence,
        evidence_confidence=row.evidence_confidence,
        plan_id=row.plan_id,
        price_snapshot_id=row.price_snapshot_id,
        promotion=_promotion(row),
        replayed=replayed,
        duplicate=duplicate,
    )


def persist_community_evidence(
    payload: CommunityEvidenceSubmission,
    *,
    session: Session,
    settings: GroceryDataSettings,
    idempotency_key: str | None = None,
) -> CommunityEvidenceResponse:
    """Persist one validated report through the shared append-only boundary.

    Consumer surfaces with stronger server-side provenance (for example a
    saved shopping-list row) use this function instead of reimplementing rate
    limits, idempotency or trust calculation.  It deliberately has no access
    to source snapshots or PriceUniverse activation state.
    """

    if idempotency_key and payload.idempotency_key is None:
        try:
            payload = payload.model_copy(update={"idempotency_key": idempotency_key})
            payload = CommunityEvidenceSubmission.model_validate(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    repository = CommunityEvidenceRepository(session)
    try:
        result = repository.create(
            payload,
            max_reports_per_hour=settings.community_evidence_max_reports_per_hour,
            duplicate_window_hours=settings.community_evidence_duplicate_window_hours,
        )
        session.commit()
    except CommunityEvidenceRateLimitError as exc:
        session.rollback()
        raise HTTPException(
            status_code=429, detail="För många rapporter. Försök senare."
        ) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _response(
        result.observation,
        repository,
        replayed=result.replayed,
        duplicate=result.duplicate,
    )


def create_community_evidence_router(
    *,
    prefix: str = "/api/community-evidence",
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=["community-evidence"])

    @router.post("", response_model=CommunityEvidenceResponse, status_code=201)
    def submit_evidence(
        payload: CommunityEvidenceSubmission,
        session: SessionDep,
        request: Request,
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> CommunityEvidenceResponse:
        return persist_community_evidence(
            payload,
            session=session,
            settings=_settings(request),
            idempotency_key=idempotency_key,
        )

    @router.post("/receipt", response_model=ReceiptIngestionResponse, status_code=201)
    def ingest_receipt(
        payload: ReceiptIngestionRequest,
        session: SessionDep,
        request: Request,
    ) -> ReceiptIngestionResponse:
        settings = _settings(request)
        service = ReceiptIngestionService(
            session,
            raw_retention_hours=settings.community_receipt_raw_retention_hours,
        )
        try:
            ingestion = service.ingest(
                payload,
                max_receipts_per_hour=settings.community_evidence_max_reports_per_hour,
            )
        except ReceiptRateLimitError as exc:
            session.rollback()
            raise HTTPException(
                status_code=429,
                detail="För många kvitton. Försök senare.",
            ) from exc
        repository = CommunityEvidenceRepository(session)
        evidence_ids: list[str] = []
        # Only structured lines with exact identifiers become evidence automatically.
        for index, line_json in enumerate(ingestion.parsed_lines):
            gtin = line_json.get("gtin")
            chain_product_id = line_json.get("chain_product_id")
            confidence = line_json.get("match_confidence")
            if confidence not in {"EXACT_GTIN", "EXACT_CHAIN_PRODUCT_ID"}:
                continue
            key = hashlib.sha256(f"{ingestion.id}:{index}".encode()).hexdigest()
            quantity = Decimal(str(line_json.get("quantity") or "1"))
            unit_price = line_json.get("unit_price")
            result = repository.create(
                CommunityEvidenceSubmission(
                    evidence_type=CommunityEvidenceType.RECEIPT_PURCHASE,
                    evidence_source="RECEIPT",
                    anonymous_session_id=payload.anonymous_session_id,
                    user_id=payload.user_id,
                    idempotency_key=key,
                    observed_at=(ingestion.purchase_observed_at or datetime.now(tz=UTC)),
                    physical_store_id=payload.physical_store_id,
                    chain=ingestion.retailer,
                    gtin=gtin,
                    source_product_id=chain_product_id,
                    product_name=line_json["description"],
                    shelf_price=line_json["paid_price"],
                    unit_price=unit_price,
                    # Exact GTIN receipt lines are retail purchase units. A
                    # multi-quantity paid total remains untyped unless the
                    # parser/user supplied an explicit per-unit price.
                    price_unit=(
                        "SEK/item"
                        if unit_price is not None or quantity == Decimal(1)
                        else None
                    ),
                    quantity=quantity,
                    receipt_ingestion_id=ingestion.id,
                ),
                max_reports_per_hour=settings.community_evidence_max_reports_per_hour,
                duplicate_window_hours=settings.community_evidence_duplicate_window_hours,
            )
            evidence_ids.append(result.observation.id)
        session.commit()
        return ReceiptIngestionResponse(
            id=ingestion.id,
            status=ingestion.status,
            parser=ingestion.parser_name,
            retailer=ingestion.retailer,
            purchase_observed_at=ingestion.purchase_observed_at,
            parsed_lines=ingestion.parsed_lines,
            evidence_ids=evidence_ids,
            warnings=ingestion.warnings,
            raw_retained=ingestion.raw_retained,
            raw_discarded_at=ingestion.raw_discarded_at,
            retention_expires_at=ingestion.retention_expires_at,
            privacy_notice=(
                "Raw receipt text/image is not retained. Structured evidence is append-only; "
                "receipt lines may require user confirmation."
            ),
        )

    @router.get("/reconcile")
    def reconcile(
        session: SessionDep,
        request: Request,
        physical_store_id: Annotated[str, Query(min_length=1, max_length=128)],
        gtin: Annotated[str | None, Query(max_length=32)] = None,
        source_product_id: Annotated[str | None, Query(max_length=500)] = None,
        source_price: Annotated[Decimal | None, Query(gt=0)] = None,
        source_price_unit: Annotated[str | None, Query(max_length=32)] = None,
        price_unit: Annotated[str | None, Query(max_length=32)] = None,
        source_supported_available: bool | None = None,
    ) -> dict[str, Any]:
        settings = _settings(request)
        service = EvidenceReconciler(
            session,
            availability_half_life_hours=settings.community_availability_half_life_hours,
            recent_hours=settings.community_evidence_recent_hours,
        )
        try:
            result = service.reconcile(
                physical_store_id=physical_store_id,
                gtin=gtin,
                source_product_id=source_product_id,
                source_price=source_price,
                source_price_unit=source_price_unit,
                price_unit=price_unit,
                source_supported_available=source_supported_available,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result.model_dump(mode="json")

    @router.get("/metrics")
    def metrics(session: SessionDep) -> dict[str, object]:
        return CommunityEvidenceRepository(session).privacy_safe_metrics()

    @router.get("/store-options", response_model=list[CommunityPhysicalStoreOption])
    def physical_store_options(
        session: SessionDep,
        city: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
        query: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
        limit: Annotated[int, Query(ge=1, le=500)] = 250,
    ) -> list[CommunityPhysicalStoreOption]:
        """List exact registry stores without conflating them with price contexts."""

        statement = select(PhysicalStoreModel).where(
            PhysicalStoreModel.is_active.is_(True)
        )
        if city:
            statement = statement.where(
                func.lower(func.trim(PhysicalStoreModel.city))
                == " ".join(city.casefold().split())
            )
        if query:
            needle = f"%{' '.join(query.casefold().split())}%"
            statement = statement.where(
                or_(
                    func.lower(PhysicalStoreModel.name).like(needle),
                    func.lower(func.coalesce(PhysicalStoreModel.address, "")).like(needle),
                )
            )
        rows = session.scalars(
            statement.order_by(
                PhysicalStoreModel.chain,
                PhysicalStoreModel.name,
            ).limit(limit)
        )
        return [
            CommunityPhysicalStoreOption(
                id=row.id,
                chain=row.chain,
                external_store_id=row.external_store_id,
                name=row.name,
                address=row.address,
                postal_code=row.postal_code,
                city=row.city,
            )
            for row in rows
        ]

    @router.get("", dependencies=[Depends(_admin_authorized)])
    def list_evidence(
        session: SessionDep,
        physical_store_id: str | None = None,
        chain: str | None = None,
        evidence_type: CommunityEvidenceType | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    ) -> list[CommunityEvidenceResponse]:
        repository = CommunityEvidenceRepository(session)
        return [
            _response(row, repository)
            for row in repository.list_recent(
                physical_store_id=physical_store_id,
                chain=chain,
                evidence_type=evidence_type,
                limit=limit,
            )
        ]

    @router.post("/{evidence_id}/moderation", dependencies=[Depends(_admin_authorized)])
    def moderate_evidence(
        evidence_id: str,
        decision: ModerationDecision,
        session: SessionDep,
    ) -> dict[str, Any]:
        repository = CommunityEvidenceRepository(session)
        try:
            event = repository.moderate(evidence_id, decision)
            session.commit()
        except KeyError as exc:
            session.rollback()
            raise HTTPException(status_code=404, detail="evidence not found") from exc
        return {
            "evidence_id": evidence_id,
            "status": event.status,
            "reason": event.reason,
            "created_at": event.created_at,
        }

    return router


router = create_community_evidence_router()


def install_community_evidence_api(
    application: Any,
    *,
    settings: GroceryDataSettings,
    create_tables: bool = True,
) -> Any:
    """Mount the shared router into the consumer backend without duplicating logic."""

    engine = create_database_engine(settings.database_url)
    if create_tables:
        create_schema(engine)
    application.state.community_session_factory = create_session_factory(engine)
    application.state.community_evidence_settings = settings
    application.state.community_evidence_engine = engine
    application.include_router(router)
    # The host app owns shutdown composition (the consumer backend disposes
    # this engine in its existing lifespan). FastAPI no longer exposes a
    # portable add_event_handler seam when an explicit lifespan is installed.
    return engine


__all__ = [
    "CommunityEvidenceResponse",
    "CommunityPhysicalStoreOption",
    "create_community_evidence_router",
    "get_community_session",
    "install_community_evidence_api",
    "persist_community_evidence",
    "router",
]
