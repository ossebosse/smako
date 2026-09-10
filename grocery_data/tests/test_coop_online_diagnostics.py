from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.connector import CoopConnector
from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.connectors.coop.online_diagnostics import (
    CoopOnlineCompletenessError,
    CoopOnlineDiagnosticAccessChallenge,
    CoopOnlineDiagnosticReplayService,
    CoopOnlineDiagnosticService,
)
from grocery_data.app.connectors.coop.online_models import (
    CoopOnlineContextIdVerification,
    CoopOnlineContextKind,
)
from grocery_data.app.connectors.coop.online_parser import (
    COOP_ONLINE_ACCESS_CHALLENGE_KIND,
    COOP_ONLINE_CATEGORY_CAPTURE_KIND,
    COOP_ONLINE_PRODUCT_DETAIL_KIND,
    COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND,
    CoopOnlineDiagnosticParser,
)
from grocery_data.app.domain import Chain, CoverageLevel, RawBatch, RawFetch
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "coop" / "fixtures"
CATEGORY_FIXTURE = FIXTURES / "online_formpasta_stadion_2026_08_22.json"


def _category_raw(
    payload: bytes | None = None,
    *,
    store_external_id: str | None = None,
) -> RawFetch:
    return RawFetch(
        chain=Chain.COOP,
        store_external_id=store_external_id,
        kind=COOP_ONLINE_CATEGORY_CAPTURE_KIND,
        method="GET",
        url=("https://www.coop.se/handla/varor/skafferi/pasta-pastasas/formpasta"),
        http_status=200,
        content_type="application/json; profile=coop-online-rendered-category-v1",
        payload=payload if payload is not None else CATEGORY_FIXTURE.read_bytes(),
        connector_version="coop-online-browser-diagnostic-v1",
    )


def _product_detail_raw(
    *,
    explicit_gtin: bool = True,
    store_external_id: str | None = None,
) -> RawFetch:
    fixture = "product_detail.html" if explicit_gtin else "product_detail_sku_only.html"
    return RawFetch(
        chain=Chain.COOP,
        store_external_id=store_external_id,
        kind=COOP_ONLINE_PRODUCT_DETAIL_KIND,
        method="GET",
        url=(
            "https://www.coop.se/handla/varor/skafferi/pasta-pastasas/"
            "formpasta/pasta-amorosi-7340191165588"
        ),
        http_status=200,
        content_type="text/html; profile=sanitized-jsonld-product",
        payload=(FIXTURES / fixture).read_bytes(),
        connector_version="coop-online-browser-diagnostic-v1",
    )


def _product_detail_sample_raw() -> RawFetch:
    return RawFetch(
        chain=Chain.COOP,
        kind=COOP_ONLINE_PRODUCT_DETAIL_SAMPLE_KIND,
        method="GET",
        url="https://www.coop.se/handla/",
        http_status=200,
        content_type="application/json; profile=coop-online-product-detail-sample-v1",
        payload=(FIXTURES / "online_recipe_product_details_2026_08_22.json").read_bytes(),
        connector_version="coop-online-browser-diagnostic-v1",
    )


def _payload() -> dict[str, object]:
    return json.loads(CATEGORY_FIXTURE.read_bytes())


def _encoded(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()


def test_real_stadion_formpasta_capture_proves_exact_page_union() -> None:
    result = CoopOnlineDiagnosticService().analyze_category(
        RawBatch(chain=Chain.COOP, documents=(_category_raw(),)),
        ["raw:stadion-formpasta"],
    )

    assert result.route.endswith("/pasta-pastasas/formpasta")
    assert result.reported_total == 77
    assert result.page_row_counts == (48, 29)
    assert result.raw_rows == 77
    assert result.unique_products == 77
    assert result.duplicate_products == 0
    assert result.complete_page_union is True
    assert result.context.kind == CoopOnlineContextKind.ONLINE_FULFILLMENT
    assert result.context.selected_label == "Stora Coop Stadion"
    assert result.context.external_online_context_id is None
    assert (
        result.context.external_context_id_verification
        == CoopOnlineContextIdVerification.UNVERIFIED
    )
    assert result.context.physical_store_external_id == "3853"
    assert result.store_price_context_verified is False
    assert result.products[0].external_product_id == "7340191165588"
    assert result.products[0].gtin is None


def test_real_capture_contains_only_allowlisted_browser_evidence() -> None:
    root = _payload()
    assert set(root) == {
        "profile",
        "captured_at",
        "context",
        "route",
        "reported_total",
        "pages",
    }
    assert set(root["context"]) == {
        "kind",
        "fulfillment_mode",
        "label",
        "external_context_id",
        "physical_store_external_id",
        "verification",
    }
    serialized = CATEGORY_FIXTURE.read_text(encoding="utf-8").casefold()
    for forbidden in (
        "authorization",
        "cookie",
        "localstorage",
        "sessionstorage",
        "subscriptionkey",
        "x-api-key",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("count", "captured 77 rows, reported 78"),
        ("page", "not contiguous"),
        ("duplicate", "duplicate products"),
    ],
)
def test_page_union_fails_closed(
    mutation: str,
    message: str,
) -> None:
    payload = _payload()
    if mutation == "count":
        payload["reported_total"] = 78
    elif mutation == "page":
        payload["pages"][1]["page_number"] = 3
    else:
        payload["pages"][1]["cards"][-1] = payload["pages"][0]["cards"][0]

    with pytest.raises(CoopOnlineCompletenessError, match=message):
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(
                chain=Chain.COOP,
                documents=(_category_raw(_encoded(payload)),),
            ),
            ["raw:broken-page-union"],
        )


def test_split_page_union_fails_on_context_mismatch() -> None:
    source = _payload()
    first = {**source, "pages": [source["pages"][0]]}
    second = json.loads(json.dumps({**source, "pages": [source["pages"][1]]}))
    second["context"]["label"] = "Another Coop online context"

    with pytest.raises(CoopOnlineCompletenessError, match="context mismatch"):
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(
                chain=Chain.COOP,
                documents=(
                    _category_raw(_encoded(first)),
                    _category_raw(_encoded(second)),
                ),
            ),
            ["raw:page-1", "raw:page-2"],
        )


def test_physical_store_id_cannot_impersonate_online_context_id() -> None:
    with pytest.raises(CoopOnlineCompletenessError, match="physical store ID"):
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(
                chain=Chain.COOP,
                documents=(_category_raw(store_external_id="3853"),),
            ),
            ["raw:wrong-context-identity"],
        )

    payload = _payload()
    payload["context"]["external_context_id"] = "unverified-online-id"
    with pytest.raises(CoopOnlineCompletenessError, match="physical store ID"):
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(
                chain=Chain.COOP,
                documents=(_category_raw(_encoded(payload), store_external_id="3853"),),
            ),
            ["raw:unverified-online-id"],
        )


def test_product_detail_rejects_physical_store_id_for_unverified_online_context() -> None:
    service = CoopOnlineDiagnosticService()
    traversal = service.analyze_category(
        RawBatch(chain=Chain.COOP, documents=(_category_raw(),)),
        ["raw:category"],
    )

    with pytest.raises(CoopSchemaError, match="physical store ID"):
        CoopOnlineDiagnosticParser().parse_product_detail(
            _product_detail_raw(store_external_id="3853"),
            reference="raw:wrong-detail-context",
            context=traversal.context,
        )


def test_verified_online_context_requires_exact_raw_identity() -> None:
    parser = CoopOnlineDiagnosticParser()
    unverified = parser.context_evidence(parser.parse_category_capture(_category_raw()))
    verified_payload = unverified.model_dump()
    verified_payload.update(
        {
            "external_online_context_id": "verified-production-unit",
            "external_context_id_verification": CoopOnlineContextIdVerification.VERIFIED,
        }
    )
    verified = type(unverified).model_validate(verified_payload)

    parser.require_context_identity(
        _product_detail_raw(store_external_id="verified-production-unit"),
        verified,
    )
    with pytest.raises(CoopSchemaError, match="disagrees with verified context"):
        parser.require_context_identity(
            _product_detail_raw(store_external_id="3853"),
            verified,
        )


def test_only_explicit_jsonld_may_create_gtin() -> None:
    service = CoopOnlineDiagnosticService()
    traversal = service.analyze_category(
        RawBatch(chain=Chain.COOP, documents=(_category_raw(),)),
        ["raw:category"],
    )
    parser = CoopOnlineDiagnosticParser()

    explicit = parser.parse_product_detail(
        _product_detail_raw(),
        reference="raw:detail-explicit",
        context=traversal.context,
    )
    assert explicit.external_product_id == "7340191165588"
    assert explicit.url_source_id == "7340191165588"
    assert explicit.gtin == "7340191165588"
    assert explicit.gtin_evidence == "explicit_jsonld"
    assert explicit.name == "Pasta Amorosi"
    assert explicit.brand == "Coop"
    assert explicit.category_path == ("Skafferi",)
    assert explicit.package_quantity == Decimal(500)
    assert explicit.package_unit == "g"
    assert explicit.sale_price == Decimal("11.95")
    assert explicit.price_currency == "SEK"
    assert explicit.availability == "InStock"
    assert explicit.price_context_verified is False

    impossible_price_context = explicit.model_dump()
    impossible_price_context["price_context_verified"] = True
    with pytest.raises(ValueError, match="verified Coop online product price"):
        type(explicit).model_validate(impossible_price_context)

    sku_only = parser.parse_product_detail(
        _product_detail_raw(explicit_gtin=False),
        reference="raw:detail-sku-only",
        context=traversal.context,
    )
    assert sku_only.external_product_id == "7340191165588"
    assert sku_only.url_source_id == "7340191165588"
    assert sku_only.gtin is None
    assert sku_only.gtin_evidence is None


def test_traversal_model_rejects_impossible_verified_price_context() -> None:
    traversal = CoopOnlineDiagnosticService().analyze_category(
        RawBatch(chain=Chain.COOP, documents=(_category_raw(),)),
        ["raw:category"],
    )
    impossible_price_context = traversal.model_dump()
    impossible_price_context["store_price_context_verified"] = True

    with pytest.raises(ValueError, match="verified Coop online traversal price"):
        type(traversal).model_validate(impossible_price_context)


def test_real_recipe_product_sample_stays_unverified_but_preserves_source_facts() -> None:
    context, observations = CoopOnlineDiagnosticParser().parse_product_detail_sample(
        _product_detail_sample_raw(),
        reference="raw:recipe-sample",
    )

    assert context.external_online_context_id is None
    assert context.physical_store_external_id == "3853"
    assert context.external_context_id_verification == CoopOnlineContextIdVerification.UNVERIFIED
    assert len(observations) == 10
    assert sum(observation.gtin is not None for observation in observations) == 8
    assert all(observation.sale_price is not None for observation in observations)
    assert all(observation.package_quantity is not None for observation in observations)
    assert all(observation.availability == "InStock" for observation in observations)
    assert all(observation.price_context_verified is False for observation in observations)

    by_name = {observation.name: observation for observation in observations}
    assert by_name["Ägg 10-pack M/L Frigående utomhus"].package_quantity == 10
    assert by_name["Ägg 10-pack M/L Frigående utomhus"].package_unit == "st"
    assert by_name["Kycklingbröstfilé"].gtin is None
    assert by_name["Kycklingbröstfilé"].package_quantity == 900
    assert by_name["Hushållsost"].gtin is None
    assert by_name["Hushållsost"].package_quantity == 1100
    assert by_name["Hushållsost"].package_unit == "g"


def test_schema_break_is_rejected_before_page_union() -> None:
    payload = _payload()
    payload["items"] = payload.pop("pages")

    with pytest.raises(CoopSchemaError, match="schema changed"):
        CoopOnlineDiagnosticParser().parse_category_capture(_category_raw(_encoded(payload)))


def test_access_challenge_stops_diagnostic_before_products() -> None:
    challenge = RawFetch(
        chain=Chain.COOP,
        kind=COOP_ONLINE_ACCESS_CHALLENGE_KIND,
        method="GET",
        url="https://www.coop.se/handla/",
        http_status=403,
        content_type="application/json; profile=sanitized-diagnostic",
        payload=(FIXTURES / "online_access_challenge.json").read_bytes(),
        connector_version="coop-online-browser-diagnostic-v1",
    )
    with pytest.raises(CoopOnlineDiagnosticAccessChallenge, match="human_verification"):
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(
                chain=Chain.COOP,
                documents=(challenge, _category_raw()),
            ),
            ["raw:challenge", "raw:must-not-parse"],
        )


def test_access_challenge_reason_is_allowlisted_before_error_output() -> None:
    challenge = RawFetch(
        chain=Chain.COOP,
        kind=COOP_ONLINE_ACCESS_CHALLENGE_KIND,
        method="GET",
        url="https://www.coop.se/handla/",
        http_status=403,
        content_type="application/json; profile=sanitized-diagnostic",
        payload=b'{"reason":"sessionId=must-not-leak"}',
        connector_version="coop-online-browser-diagnostic-v1",
    )
    with pytest.raises(CoopOnlineDiagnosticAccessChallenge) as raised:
        CoopOnlineDiagnosticService().analyze_category(
            RawBatch(chain=Chain.COOP, documents=(challenge,)),
            ["raw:challenge"],
        )

    assert str(raised.value) == "ACCESS_CHALLENGE"
    assert "session" not in str(raised.value).casefold()


def test_saved_browser_evidence_replays_with_zero_network_and_browser(
    tmp_path: Path,
) -> None:
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    batch = RawBatch(
        chain=Chain.COOP,
        documents=(_category_raw(), _product_detail_raw()),
    )
    records = raw_store.save_batch(batch, snapshot_id="coop-online-diagnostic")

    replay = CoopOnlineDiagnosticReplayService(raw_store).replay(records)

    assert replay.network_requests == 0
    assert replay.browser_launches == 0
    assert replay.traversal.unique_products == 77
    assert len(replay.product_details) == 1
    assert replay.product_details[0].gtin == "7340191165588"
    assert replay.product_details[0].price_context_verified is False


def test_online_diagnostics_are_not_wired_into_active_coop_connector() -> None:
    connector = CoopConnector()
    assert connector.coverage == CoverageLevel.OFFERS_ONLY
    assert connector.connector_version == "coop-v1"
    assert not hasattr(connector, "fetch_online_catalog")
