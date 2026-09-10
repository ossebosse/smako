from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Protocol
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from grocery_data.app.domain.community_evidence import ProductIdentityConfidence
from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.storage.community_evidence import pseudonymous_actor_hash
from grocery_data.app.storage.models import CommunityReceiptIngestionModel, utcnow


class ReceiptLine(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(default=Decimal(1), gt=0, max_digits=18, decimal_places=6)
    paid_price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    gtin: str | None = Field(default=None, max_length=32)
    chain_product_id: str | None = Field(default=None, max_length=255)
    match_confidence: ProductIdentityConfidence = ProductIdentityConfidence.UNMATCHED

    @model_validator(mode="after")
    def validate_identity_confidence(self) -> ReceiptLine:
        if self.gtin:
            self.gtin = normalize_gtin(self.gtin).normalized_gtin
            if self.match_confidence is ProductIdentityConfidence.UNMATCHED:
                self.match_confidence = ProductIdentityConfidence.EXACT_GTIN
        if self.match_confidence is ProductIdentityConfidence.EXACT_GTIN and self.gtin is None:
            raise ValueError("EXACT_GTIN receipt match requires gtin")
        if (
            self.match_confidence is ProductIdentityConfidence.EXACT_CHAIN_PRODUCT_ID
            and self.chain_product_id is None
        ):
            raise ValueError("EXACT_CHAIN_PRODUCT_ID requires chain_product_id")
        return self


class ReceiptIngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anonymous_session_id: str | None = Field(default=None, min_length=8, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    retailer: str | None = Field(default=None, max_length=64)
    physical_store_id: str | None = Field(default=None, max_length=128)
    purchase_observed_at: datetime | None = None
    raw_text: str | None = Field(default=None, min_length=1, max_length=50_000)
    lines: tuple[ReceiptLine, ...] = Field(default=(), max_length=250)

    @model_validator(mode="after")
    def validate_input(self) -> ReceiptIngestionRequest:
        if not self.anonymous_session_id and not self.user_id:
            raise ValueError("anonymous_session_id or user_id is required")
        if not self.raw_text and not self.lines:
            raise ValueError("raw_text or structured receipt lines are required")
        if self.purchase_observed_at and self.purchase_observed_at.tzinfo is None:
            raise ValueError("purchase_observed_at must be timezone-aware")
        return self


class ReceiptRateLimitError(RuntimeError):
    pass


def _receipt_request_fingerprint(request: ReceiptIngestionRequest) -> str:
    """Hash a canonical safe payload without retaining raw receipt content."""

    raw_digest = (
        hashlib.sha256(request.raw_text.encode("utf-8")).hexdigest()
        if request.raw_text
        else None
    )
    safe_payload = {
        "retailer": (request.retailer or "").strip().casefold() or None,
        "physical_store_id": request.physical_store_id,
        "purchase_observed_at": (
            request.purchase_observed_at.astimezone(UTC).isoformat()
            if request.purchase_observed_at is not None
            else None
        ),
        "raw_sha256": raw_digest,
        "lines": [line.model_dump(mode="json") for line in request.lines],
    }
    encoded = json.dumps(
        safe_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ReceiptParseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: str
    parser_name: str
    retailer: str | None = None
    store_label: str | None = None
    purchased_at: datetime | None = None
    lines: tuple[ReceiptLine, ...] = ()
    warnings: tuple[str, ...] = ()


class ReceiptParser(Protocol):
    name: str

    def supports(self, retailer: str | None, raw_text: str) -> bool: ...

    def parse(self, raw_text: str) -> ReceiptParseResult: ...


class HemkopTextReceiptParser:
    """Conservative Hemköp/Axfood beta parser; ambiguous lines stay unmatched."""

    name = "hemkop_text_beta_v1"
    _date_patterns = (
        re.compile(r"\b(20\d{2})[-/.](\d{2})[-/.](\d{2})[ T](\d{2}):(\d{2})\b"),
        re.compile(r"\b(\d{2})[-/.](\d{2})[-/.](20\d{2})\s+(\d{2}):(\d{2})\b"),
    )
    _line_pattern = re.compile(
        r"^(?P<description>[A-ZÅÄÖa-zåäö0-9][^\t]{1,120}?)"
        r"(?:\s{2,}|\t)(?P<price>\d{1,6}[,.]\d{2})(?:\s*(?:KR|SEK))?$",
        re.IGNORECASE,
    )

    def supports(self, retailer: str | None, raw_text: str) -> bool:
        normalized = f"{retailer or ''}\n{raw_text[:500]}".casefold()
        return "hemköp" in normalized or "hemkop" in normalized or "axfood" in normalized

    def parse(self, raw_text: str) -> ReceiptParseResult:
        purchased_at = self._parse_date(raw_text)
        lines: list[ReceiptLine] = []
        for raw_line in raw_text.splitlines():
            line = " ".join(raw_line.strip().split())
            # The source spacing is useful to distinguish descriptions from totals;
            # try the original line first and deliberately ignore discount/total rows.
            if any(word in line.casefold() for word in ("total", "moms", "rabatt", "betalt")):
                continue
            match = self._line_pattern.match(raw_line.strip())
            if not match:
                continue
            try:
                price = Decimal(match.group("price").replace(",", "."))
            except InvalidOperation:
                continue
            if price <= 0:
                continue
            lines.append(
                ReceiptLine(
                    description=" ".join(match.group("description").split()),
                    paid_price=price,
                    match_confidence=ProductIdentityConfidence.UNMATCHED,
                )
            )
        warnings = [
            "Receipt descriptions are not exact product identity; user confirmation is required."
        ]
        if not lines:
            warnings.append("No unambiguous purchase lines were parsed.")
        return ReceiptParseResult(
            status="PARSED" if lines else "UNSUPPORTED_RECEIPT_FORMAT",
            parser_name=self.name,
            retailer="hemkop",
            purchased_at=purchased_at,
            lines=tuple(lines),
            warnings=tuple(warnings),
        )

    def _parse_date(self, raw_text: str) -> datetime | None:
        for index, pattern in enumerate(self._date_patterns):
            match = pattern.search(raw_text)
            if not match:
                continue
            values = tuple(int(value) for value in match.groups())
            if index == 0:
                year, month, day, hour, minute = values
            else:
                day, month, year, hour, minute = values
            try:
                return datetime(
                    year,
                    month,
                    day,
                    hour,
                    minute,
                    tzinfo=ZoneInfo("Europe/Stockholm"),
                ).astimezone(UTC)
            except ValueError:
                return None
        return None


class ReceiptIngestionService:
    def __init__(
        self,
        session: Session,
        *,
        parsers: tuple[ReceiptParser, ...] | None = None,
        raw_retention_hours: float = 0,
    ) -> None:
        self.session = session
        self.parsers = parsers or (HemkopTextReceiptParser(),)
        self.raw_retention_hours = raw_retention_hours

    def ingest(
        self,
        request: ReceiptIngestionRequest,
        *,
        now: datetime | None = None,
        max_receipts_per_hour: int = 60,
    ) -> CommunityReceiptIngestionModel:
        if max_receipts_per_hour <= 0:
            raise ValueError("max_receipts_per_hour must be greater than zero")
        timestamp = (now or utcnow()).astimezone(UTC)
        actor_hash = pseudonymous_actor_hash(request.user_id or request.anonymous_session_id)
        request_fingerprint = _receipt_request_fingerprint(request)
        existing = self.session.scalar(
            select(CommunityReceiptIngestionModel)
            .where(
                CommunityReceiptIngestionModel.actor_hash == actor_hash,
                CommunityReceiptIngestionModel.raw_sha256 == request_fingerprint,
            )
            .order_by(CommunityReceiptIngestionModel.created_at, CommunityReceiptIngestionModel.id)
            .limit(1)
        )
        if existing is not None:
            return existing

        recent_count = self.session.scalar(
            select(func.count(CommunityReceiptIngestionModel.id)).where(
                CommunityReceiptIngestionModel.actor_hash == actor_hash,
                CommunityReceiptIngestionModel.created_at >= timestamp - timedelta(hours=1),
            )
        )
        if int(recent_count or 0) >= max_receipts_per_hour:
            raise ReceiptRateLimitError("receipt ingestion rate limit exceeded")

        if request.lines:
            parsed = ReceiptParseResult(
                status="PARSED_STRUCTURED",
                parser_name="manual_structured_v1",
                retailer=request.retailer,
                purchased_at=request.purchase_observed_at,
                lines=request.lines,
            )
        else:
            assert request.raw_text is not None
            parser = next(
                (
                    candidate
                    for candidate in self.parsers
                    if candidate.supports(request.retailer, request.raw_text or "")
                ),
                None,
            )
            parsed = (
                parser.parse(request.raw_text)
                if parser
                else ReceiptParseResult(
                    status="UNSUPPORTED_RECEIPT_FORMAT",
                    parser_name="unsupported",
                    retailer=request.retailer,
                    warnings=("Receipt format is not supported; no facts were inferred.",),
                )
            )

        row = CommunityReceiptIngestionModel(
            actor_hash=actor_hash,
            retailer=(parsed.retailer or request.retailer),
            physical_store_id=request.physical_store_id,
            status=parsed.status,
            parser_name=parsed.parser_name,
            # This is a one-way canonical request fingerprint. Raw text is
            # hashed in memory and is never assigned to a model field.
            raw_sha256=request_fingerprint,
            raw_retained=False,
            # Raw receipt content is processed in memory and discarded immediately.
            raw_discarded_at=timestamp,
            retention_expires_at=timestamp + timedelta(hours=self.raw_retention_hours),
            purchase_observed_at=parsed.purchased_at or request.purchase_observed_at,
            parsed_lines=[line.model_dump(mode="json") for line in parsed.lines],
            warnings=list(parsed.warnings),
            created_at=timestamp,
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
            return row
        except IntegrityError:
            # A concurrent retry may win the unique actor/fingerprint insert.
            # The savepoint is rolled back without disturbing the outer request.
            existing = self.session.scalar(
                select(CommunityReceiptIngestionModel).where(
                    CommunityReceiptIngestionModel.actor_hash == actor_hash,
                    CommunityReceiptIngestionModel.raw_sha256 == request_fingerprint,
                )
            )
            if existing is None:
                raise
            return existing


__all__ = [
    "HemkopTextReceiptParser",
    "ReceiptIngestionRequest",
    "ReceiptIngestionService",
    "ReceiptLine",
    "ReceiptParseResult",
    "ReceiptParser",
    "ReceiptRateLimitError",
]
