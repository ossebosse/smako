from __future__ import annotations

import json

from grocery_data.app.connectors.coop.models import (
    CoopSchemaError,
    source_id_from_product_url,
)
from grocery_data.app.connectors.coop.online_models import (
    CoopOnlineCaptureSurface,
    CoopOnlineContextEvidence,
    CoopOnlineDiagnosticReplayResult,
    CoopOnlineProductIdentity,
    CoopOnlineTraversalDiagnostic,
)
from grocery_data.app.connectors.coop.online_parser import (
    COOP_ONLINE_ACCESS_CHALLENGE_KIND,
    COOP_ONLINE_CATEGORY_CAPTURE_KIND,
    COOP_ONLINE_PRODUCT_DETAIL_KIND,
    COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND,
    CoopOnlineDiagnosticParser,
)
from grocery_data.app.domain import Chain, RawBatch, RawFetch, StoredRawDocument
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore


class CoopOnlineCompletenessError(RuntimeError):
    """The diagnostic page union cannot prove the declared result set."""


class CoopOnlineDiagnosticAccessChallenge(RuntimeError):
    """An ordinary browser encountered a challenge and the run must stop."""


_SAFE_CHALLENGE_REASONS = {
    "access_denied",
    "aws_waf",
    "captcha",
    "human_verification",
}


def _context_key(context: CoopOnlineContextEvidence) -> tuple[str | None, ...]:
    return (
        context.kind.value,
        context.fulfillment_mode,
        context.selected_label,
        context.external_online_context_id,
        context.external_context_id_verification.value,
        context.physical_store_external_id,
    )


class CoopOnlineDiagnosticService:
    """Validate sanitized browser evidence without activating it as catalog data."""

    def __init__(self, parser: CoopOnlineDiagnosticParser | None = None) -> None:
        self.parser = parser or CoopOnlineDiagnosticParser()

    @staticmethod
    def _challenge_reason(document: RawFetch) -> str:
        try:
            payload = json.loads(document.payload)
        except (TypeError, ValueError):
            return "ACCESS_CHALLENGE"
        if not isinstance(payload, dict):
            return "ACCESS_CHALLENGE"
        reason = str(payload.get("reason") or "").strip().casefold()
        # Challenge diagnostics are persisted separately, but even malformed
        # evidence must not turn arbitrary source text into a log/error value.
        return reason if reason in _SAFE_CHALLENGE_REASONS else "ACCESS_CHALLENGE"

    def analyze_category(
        self,
        batch: RawBatch,
        references: list[str],
    ) -> CoopOnlineTraversalDiagnostic:
        if batch.chain != Chain.COOP:
            raise CoopSchemaError("Coop online diagnostics received another chain")
        if len(references) != len(batch.documents):
            raise ValueError("one raw reference is required per diagnostic document")
        for document in batch.documents:
            if document.kind == COOP_ONLINE_ACCESS_CHALLENGE_KIND:
                raise CoopOnlineDiagnosticAccessChallenge(self._challenge_reason(document))
            if document.kind not in {
                COOP_ONLINE_CATEGORY_CAPTURE_KIND,
                COOP_ONLINE_PRODUCT_DETAIL_KIND,
                COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND,
            }:
                raise CoopSchemaError(f"unsupported Coop online diagnostic kind {document.kind!r}")

        capture_pairs = [
            (document, reference)
            for document, reference in zip(batch.documents, references, strict=True)
            if document.kind == COOP_ONLINE_CATEGORY_CAPTURE_KIND
        ]
        if not capture_pairs:
            raise CoopSchemaError("Coop online diagnostic has no category capture")

        captures = [self.parser.parse_category_capture(document) for document, _ in capture_pairs]
        contexts = [self.parser.context_evidence(capture) for capture in captures]
        if len({_context_key(context) for context in contexts}) != 1:
            raise CoopOnlineCompletenessError("Coop online page union context mismatch")
        context = contexts[0]
        for document, _ in capture_pairs:
            try:
                self.parser.require_context_identity(document, context)
            except CoopSchemaError as exc:
                raise CoopOnlineCompletenessError(str(exc)) from exc

        routes = {capture.route for capture in captures}
        if len(routes) != 1:
            raise CoopOnlineCompletenessError("Coop online page union route mismatch")
        route = next(iter(routes))
        totals = {capture.reported_total for capture in captures}
        if len(totals) != 1:
            raise CoopOnlineCompletenessError("Coop online page union total mismatch")
        reported_total = next(iter(totals))

        pages = [page for capture in captures for page in capture.pages]
        page_numbers = [page.page_number for page in pages]
        if len(set(page_numbers)) != len(page_numbers):
            raise CoopOnlineCompletenessError("Coop online page union contains duplicate pages")
        sorted_pages = sorted(pages, key=lambda page: page.page_number)
        expected_page_numbers = list(range(1, len(sorted_pages) + 1))
        if [page.page_number for page in sorted_pages] != expected_page_numbers:
            raise CoopOnlineCompletenessError(
                "Coop online page union is not contiguous from page 1"
            )

        identities: list[CoopOnlineProductIdentity] = []
        hrefs: set[str] = set()
        source_ids: set[str] = set()
        duplicate_products = 0
        category_prefix = f"{route}/"
        for page in sorted_pages:
            for card in page.cards:
                if not card.href.startswith(category_prefix):
                    raise CoopOnlineCompletenessError(
                        "Coop online card does not belong to the captured category route"
                    )
                source_id = source_id_from_product_url(card.href)
                if source_id is None:
                    raise CoopOnlineCompletenessError(
                        "Coop online card URL has no verified external source ID suffix"
                    )
                if card.href in hrefs or source_id in source_ids:
                    duplicate_products += 1
                    continue
                hrefs.add(card.href)
                source_ids.add(source_id)
                identities.append(
                    CoopOnlineProductIdentity(
                        external_product_id=source_id,
                        href=card.href,
                        aria_label=card.aria_label,
                        # A numeric URL suffix remains only a source identity.
                        gtin=None,
                    )
                )

        raw_rows = sum(len(page.cards) for page in sorted_pages)
        if duplicate_products:
            raise CoopOnlineCompletenessError(
                f"Coop online page union contains {duplicate_products} duplicate products"
            )
        if raw_rows != reported_total:
            raise CoopOnlineCompletenessError(
                f"Coop online page union captured {raw_rows} rows, reported {reported_total}"
            )
        if len(identities) != reported_total:
            raise CoopOnlineCompletenessError(
                "Coop online unique product count does not match the reported total"
            )

        return CoopOnlineTraversalDiagnostic(
            context=context,
            surface=CoopOnlineCaptureSurface.RENDERED_CATEGORY,
            route=route,
            reported_total=reported_total,
            pages_fetched=len(sorted_pages),
            page_row_counts=tuple(len(page.cards) for page in sorted_pages),
            raw_rows=raw_rows,
            unique_products=len(identities),
            duplicate_products=0,
            complete_page_union=True,
            # The selected label is visible, but no online productionUnitId
            # was observed. These prices remain diagnostics only.
            store_price_context_verified=False,
            products=tuple(identities),
            raw_references=tuple(reference for _, reference in capture_pairs),
        )

    def analyze(
        self,
        batch: RawBatch,
        references: list[str],
    ) -> CoopOnlineDiagnosticReplayResult:
        traversal = self.analyze_category(batch, references)
        details = []
        for document, reference in zip(batch.documents, references, strict=True):
            if document.kind == COOP_ONLINE_PRODUCT_DETAIL_KIND:
                details.append(
                    self.parser.parse_product_detail(
                        document,
                        reference=reference,
                        context=traversal.context,
                    )
                )
            elif document.kind == COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND:
                sample_context, sample_details = self.parser.parse_product_detail_sample(
                    document,
                    reference=reference,
                )
                if _context_key(sample_context) != _context_key(traversal.context):
                    raise CoopOnlineCompletenessError(
                        "Coop online product details context mismatch"
                    )
                details.extend(sample_details)
        return CoopOnlineDiagnosticReplayResult(
            traversal=traversal,
            product_details=tuple(details),
            network_requests=0,
            browser_launches=0,
        )


class CoopOnlineDiagnosticReplayService:
    """Replay browser diagnostics from immutable local payloads only."""

    def __init__(
        self,
        raw_store: FilesystemRawSnapshotStore,
        service: CoopOnlineDiagnosticService | None = None,
    ) -> None:
        self.raw_store = raw_store
        self.service = service or CoopOnlineDiagnosticService()

    def replay(self, records: list[StoredRawDocument]) -> CoopOnlineDiagnosticReplayResult:
        if not records:
            raise ValueError("Coop online diagnostic replay requires raw records")
        documents = tuple(
            RawFetch(
                chain=record.chain,
                store_external_id=record.store_external_id,
                kind=record.kind,
                method=record.method,
                url=record.url,
                query=record.query,
                fetched_at=record.fetched_at,
                http_status=record.http_status,
                content_type=record.content_type,
                payload=self.raw_store.load(record),
                connector_version=record.connector_version,
                page_number=record.page_number,
            )
            for record in records
        )
        return self.service.analyze(
            RawBatch(chain=Chain.COOP, documents=documents),
            [f"raw:{record.document_id}" for record in records],
        )
