from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from grocery_data.__main__ import main as cli_main
from grocery_data.app.api.physical_check import _digital_price_presentation, router
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.enums import Chain, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceObservation,
)
from grocery_data.app.services.physical_price_candidates import (
    ExternalPhysicalPriceCandidateReader,
)
from grocery_data.app.storage import (
    PriceObservationModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import (
    PhysicalPriceObservationModel,
    PhysicalStoreModel,
    StoreContextLinkModel,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def test_external_candidate_reader_contract_has_observation_and_store_reads() -> None:
    assert callable(ExternalPhysicalPriceCandidateReader.for_observation)
    assert callable(ExternalPhysicalPriceCandidateReader.for_store)


class PersistedPrimatFixtureReader:
    """Test double for a local licensed snapshot reader; it makes no provider call."""

    candidate = DigitalPriceCandidate(
        physical_store_id="physical-hemkop-karhogstorg",
        grocery_context_id="primat-hemkop-karhogstorg",
        source_provider="primat",
        source_snapshot_id="primat-snapshot-1",
        observed_at=NOW - timedelta(hours=1),
        product_id="primat-product-milk",
        product_name="Mjölk 1 l",
        gtin="7310865004703",
        current_price=Decimal("29.90"),
        regular_price=Decimal("31.90"),
        sale_model=SaleModel.FIXED_PACKAGE,
        common_product_score=Decimal(5),
    )

    def for_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> tuple[DigitalPriceCandidate, ...]:
        if (
            observation.physical_store_id == self.candidate.physical_store_id
            and observation.gtin == self.candidate.gtin
        ):
            return (self.candidate,)
        return ()

    def for_store(
        self,
        physical_store_id: str,
        *,
        limit: int,
    ) -> tuple[DigitalPriceCandidate, ...]:
        del limit
        return (self.candidate,) if physical_store_id == self.candidate.physical_store_id else ()


def _client():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id="physical-hemkop-karhogstorg",
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="223 58",
                city="Lund",
                official_source="https://www.hemkop.se/butik/karhogstorg",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.flush()
        session.add(
            StoreContextLinkModel(
                id="link-primat-karhogstorg",
                physical_store_id="physical-hemkop-karhogstorg",
                grocery_context_id="primat-hemkop-karhogstorg",
                source_provider="primat",
                source_channel="catalog",
                grocery_context_name="Hemköp Lund Karhögstorg",
                price_context_type="online_store",
                coverage="full_online_catalog",
                relation_type="exact_store_online_context",
                confidence="high",
                evidence="exact official identity fixture",
                basket_eligible=True,
                offers_only=False,
                snapshot_id="primat-snapshot-1",
                observed_at=NOW - timedelta(hours=1),
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.commit()

    application = FastAPI()
    application.state.session_factory = factory
    application.state.external_physical_price_candidate_reader = PersistedPrimatFixtureReader()
    application.state.settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("raw_snapshots-test"),
        user_agent="grocery-data-test",
        field_validation_max_price_age_hours=10_000.0,
    )
    application.include_router(router)
    return TestClient(application), factory


def test_manual_api_saves_evidence_but_never_catalog_price() -> None:
    client, factory = _client()

    response = client.post(
        "/physical-check/observations",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "gtin": "7310865004703",
            "product_name": "Mjölk 1 l",
            "shelf_price": "29.90",
            "observed_at": NOW.isoformat(),
            "notes": "Frivilligt stickprov",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["catalog_price_updated"] is False
    assert body["observation"]["source"] == "manual"
    assert body["observation"]["confidence"] == "high"
    assert body["comparisons"][0]["source_provider"] == "primat"
    assert body["comparisons"][0]["status"] == "match"
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalPriceObservationModel)) == 1
        assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 0


def test_physical_check_read_endpoints_label_results_as_samples() -> None:
    client, _factory = _client()
    create = client.post(
        "/physical-check/observations",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "gtin": "7310865004703",
            "shelf_price": "30.40",
            "observed_at": NOW.isoformat(),
        },
    )
    assert create.status_code == 201

    stores = client.get("/physical-check/stores?city=Lund")
    observations = client.get("/physical-check/observations?store_id=physical-hemkop-karhogstorg")
    report = client.get("/physical-check/report?store_id=physical-hemkop-karhogstorg")
    suggestions = client.get(
        "/physical-check/suggestions?store_id=physical-hemkop-karhogstorg&limit=10"
    )

    assert stores.status_code == 200
    assert stores.json()["items"][0]["name"] == "Hemköp Lund Karhögstorg"
    assert observations.json()["sampled_only"] is True
    assert observations.json()["count"] == 1
    assert report.json()["sampled_only"] is True
    assert report.json()["blocks_normal_use"] is False
    assert "sampled observations" in report.json()["report"]["scope_label"]
    assert report.json()["report"]["providers"]["primat"]["within_050"] == 1
    assert suggestions.json()["count"] == 1
    assert suggestions.json()["items"][0]["gtin"] == "7310865004703"


def test_karhogstorg_is_selectable_and_digital_preview_is_read_only() -> None:
    client, factory = _client()

    stores = client.get("/physical-check/stores?city=Lund")
    preview = client.get(
        "/physical-check/digital-price-preview",
        params={
            "store_id": "physical-hemkop-karhogstorg",
            "gtin": "7310865004703",
        },
    )

    assert stores.status_code == 200
    [karhogstorg] = stores.json()["items"]
    assert karhogstorg["id"] == "physical-hemkop-karhogstorg"
    assert karhogstorg["external_store_id"] == "4123"
    assert karhogstorg["name"] == "Hemköp Lund Karhögstorg"
    assert preview.status_code == 200
    body = preview.json()
    assert body["preview_only"] is True
    assert body["shelf_price_prefilled"] is False
    assert body["live_provider_requests"] == 0
    assert body["count"] == 1
    assert body["items"][0]["source_provider"] == "primat"
    assert body["items"][0]["match_path"] == "external_gtin"
    assert body["lookup_order"] == [
        "own_gtin",
        "external_gtin",
        "persisted_detail_identity",
        "manual_exact_name",
    ]
    assert body["items"][0]["current_price"] == "29.90"
    assert body["items"][0]["observed_at"] == (NOW - timedelta(hours=1)).isoformat().replace(
        "+00:00", "Z"
    )
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalPriceObservationModel)) == 0
        assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 0


def test_coop_pickup_preview_is_explicitly_an_online_price_not_a_shelf_price() -> None:
    client, factory = _client()
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id="physical:coop:2696",
                chain="coop",
                external_store_id="2696",
                name="Stora Coop Lund",
                address="Traktorvagen 2",
                postal_code="22660",
                city="Lund",
                official_source=(
                    "https://www.coop.se/butiker-erbjudanden/stora-coop/"
                    "stora-coop-lund/"
                ),
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.flush()
        session.add(
            StoreContextLinkModel(
                id="link-coop-lund-pickup",
                physical_store_id="physical:coop:2696",
                grocery_context_id="own:coop:730400",
                source_provider="own",
                source_channel="catalog",
                pickup_point_external_id="257611",
                grocery_context_name="Coop Online Syd",
                price_context_type="online_fulfillment",
                coverage="full_online_catalog",
                relation_type="pickup_context",
                confidence="exact",
                evidence="public fulfillment fixture",
                basket_eligible=True,
                offers_only=False,
                snapshot_id="coop-full-snapshot",
                observed_at=NOW,
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.commit()

    candidate = DigitalPriceCandidate(
        physical_store_id="physical:coop:2696",
        grocery_context_id="own:coop:730400",
        source_provider="own",
        source_snapshot_id="coop-full-snapshot",
        observed_at=NOW,
        product_id="7300156573186",
        product_name="Standardmjolk 1,5 l",
        gtin="7300156573186",
        current_price=Decimal("16.27"),
        regular_price=Decimal("16.27"),
        sale_model=SaleModel.FIXED_PACKAGE,
    )

    class CoopPreviewReader:
        def for_observation(self, observation):  # type: ignore[no-untyped-def]
            return (
                (candidate,)
                if observation.physical_store_id == candidate.physical_store_id
                else ()
            )

        def current_for_observation(self, observation):  # type: ignore[no-untyped-def]
            return self.for_observation(observation)

        def for_store(self, physical_store_id, *, limit):  # type: ignore[no-untyped-def]
            del limit
            return (candidate,) if physical_store_id == candidate.physical_store_id else ()

    client.app.state.external_physical_price_candidate_reader = CoopPreviewReader()
    response = client.get(
        "/physical-check/digital-price-preview",
        params={"store_id": "physical:coop:2696", "gtin": "7300156573186"},
    )

    assert response.status_code == 200
    [item] = response.json()["items"]
    assert item["grocery_context_id"] == "own:coop:730400"
    assert item["price_context_type"] == "online_fulfillment"
    assert item["price_semantics"] == "online_price"
    assert item["price_label"] == "Coop onlinepris"
    assert "hyll" not in item["price_label"].casefold()
    assert response.json()["shelf_price_prefilled"] is False
    assert response.json()["live_provider_requests"] == 0


def test_ica_online_context_preview_is_not_labelled_as_shelf_price() -> None:
    _client_instance, factory = _client()
    physical_store_id = "physical:ica:17883"
    context_id = "own:ica:92198f17-b02f-4fae-ad41-228bcc725420"
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id=physical_store_id,
                chain="ica",
                external_store_id="1088004",
                name="Maxi ICA Stormarknad Gunnesbo Lund",
                address="Traktorvägen 1-3",
                postal_code="226 60",
                city="Lund",
                official_source="https://www.ica.se/butiker/maxi/lund/",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.flush()
        session.add(
            StoreContextLinkModel(
                id="link-ica-gunnesbo-online-fixture",
                physical_store_id=physical_store_id,
                grocery_context_id=context_id,
                source_provider="own",
                source_channel="catalog",
                grocery_context_name="ICA Online Gunnesbo",
                price_context_type="online_store",
                coverage="full_online_catalog",
                relation_type="exact_store_online_context",
                confidence="exact",
                evidence="sanitized context-readback fixture",
                basket_eligible=True,
                offers_only=False,
                snapshot_id="ica-online-fixture",
                observed_at=NOW,
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.flush()
        candidate = DigitalPriceCandidate(
            physical_store_id=physical_store_id,
            grocery_context_id=context_id,
            source_provider="own",
            source_snapshot_id="ica-online-fixture",
            observed_at=NOW,
            product_id="f4ec81a4-4fff-4696-92dc-4a3e7bf06c31",
            product_name="Ekologisk mjölk 1,5 l",
            current_price=Decimal("20.55"),
            sale_model=SaleModel.FIXED_PACKAGE,
        )
        presentation = _digital_price_presentation(
            session,
            physical_store_id=physical_store_id,
            chain=Chain.ICA,
            candidates=[("own_gtin", candidate)],
        )

    context_type, semantics, label = presentation[("own", context_id)]
    assert context_type == "online_store"
    assert semantics == "online_price"
    assert label == "ICA onlinepris"
    assert "hyll" not in label.casefold()


def test_preview_fallback_order_uses_external_then_persisted_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from grocery_data.app.api import physical_check as physical_check_api

    class LocalReader:
        detail = PersistedPrimatFixtureReader.candidate.model_copy(
            update={
                "source_provider": "own",
                "grocery_context_id": "own:hemkop:4123",
                "source_snapshot_id": "own-snapshot",
                "product_id": "own-product",
                "gtin": None,
            }
        )

        def __init__(self, session) -> None:  # type: ignore[no-untyped-def]
            del session

        def current_for_observation(self, observation):  # type: ignore[no-untyped-def]
            del observation
            return ()

        def current_for_known_detail_identity(self, observation):  # type: ignore[no-untyped-def]
            assert observation.gtin == "7310865004703"
            return (self.detail,)

    monkeypatch.setattr(
        physical_check_api,
        "PersistedPhysicalPriceCandidateReader",
        LocalReader,
    )
    client, _factory = _client()

    payload = client.get(
        "/physical-check/digital-price-preview",
        params={
            "store_id": "physical-hemkop-karhogstorg",
            "gtin": "7310865004703",
            "product_name": "Mjölk 1 l",
        },
    ).json()

    assert [item["match_path"] for item in payload["items"]] == [
        "external_gtin",
        "persisted_detail_identity",
    ]
    assert [item["source_provider"] for item in payload["items"]] == ["primat", "own"]
    assert payload["live_provider_requests"] == 0


def test_invalid_preview_gtin_returns_422_without_observation() -> None:
    client, factory = _client()

    response = client.get(
        "/physical-check/digital-price-preview",
        params={"store_id": "physical-hemkop-karhogstorg", "gtin": "12345678x"},
    )

    assert response.status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalPriceObservationModel)) == 0


def test_physical_check_page_is_mobile_and_camera_optional_without_image_upload() -> None:
    client, _factory = _client()

    response = client.get("/physical-check")
    javascript = Path("grocery_data/app/static/physical-check.js").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert 'name="viewport"' in response.text
    assert 'inputmode="numeric"' in response.text
    assert "Manuell GTIN-inmatning fungerar alltid" in response.text
    assert "/static/physical-check-api-errors.js" in response.text
    assert "/static/physical-barcode-scanner.js" in response.text
    assert "PhysicalCheckApiErrors?.formatApiErrorResponse" in javascript
    assert "product-identification-v2" in javascript
    assert "Stoppa och starta om scripts/start_field_server.ps1" in javascript
    assert "GroceryBarcodeScanner.createBarcodeScanner" in javascript
    assert "BarcodeDetector" not in javascript
    assert "getUserMedia" in javascript
    assert "if (scannerStarting || activeBarcodeScanner) return;" in javascript
    assert 'window.addEventListener("pagehide", stopScanner)' in javascript
    assert 'window.addEventListener("beforeunload", stopScanner)' in javascript
    assert "scanner_provider" in javascript
    assert 'saveButton.textContent = body.idempotent_replay ? "Redan sparat" : "Sparat"' in javascript
    assert "nextProductButton.hidden = false" in javascript
    assert "Fysiskt: ${physicalText}" in javascript
    assert 'name="price_basis"' in response.text
    assert 'id="promotion-member"' in response.text
    assert 'id="promotion-multibuy"' in response.text
    assert "comparison_output" in javascript
    assert "target_sample_size: 25" in javascript
    assert 'replace(",", ".")' in javascript
    assert "client_request_id: requestId" in javascript
    assert "if (savePending) return" in javascript
    assert "Din inmatning finns kvar; försök igen" in javascript
    assert "Du behöver inte räkna ut styckpris" in javascript
    assert "stopScanner();\n  const selectedStore" in javascript
    assert "geolocation" not in javascript
    assert "canvas" not in javascript
    assert "photo" not in javascript
    assert "/physical-check/digital-price-preview" in javascript
    assert "/identity?${query}" in javascript
    assert "Sökresultat accepteras aldrig automatiskt" in response.text
    assert "Okänd GTIN är inte i sig NO_MATCH" in response.text
    assert "WEIGHT_ITEM_NO_GTIN_REQUIRED" in javascript
    assert "GTIN_NOT_KNOWN_BY_SOURCE" in javascript
    assert "item.barcode_required === false" not in javascript
    assert 'mode: activeScannerMode' in javascript
    assert "/physical-check/shelf-identifiers" in javascript
    assert "weight_price_type" in javascript
    assert "regular_shelf_price" in javascript
    assert "manualProductResults" in javascript
    assert "shelfPriceInput.value" not in javascript
    assert "Hyllprisfältet fylls aldrig automatiskt" in response.text


def test_unknown_or_inactive_physical_store_fails_closed() -> None:
    client, factory = _client()
    payload = {
        "physical_store_id": "missing",
        "gtin": "7310865004703",
        "shelf_price": "29.90",
    }
    assert client.post("/physical-check/observations", json=payload).status_code == 404

    with factory() as session:
        row = session.get(PhysicalStoreModel, "physical-hemkop-karhogstorg")
        assert row is not None
        row.is_active = False
        row.lifecycle_state = "not_seen"
        row.not_seen_at = NOW
        session.commit()
    payload["physical_store_id"] = "physical-hemkop-karhogstorg"
    assert client.post("/physical-check/observations", json=payload).status_code == 409


@pytest.mark.parametrize(
    "invalid_fields",
    [
        {"gtin": "123"},
        {"observed_at": "2026-08-23T12:00:00"},
        {"comparison_price": "31.90"},
        {
            "promotion_type": "sale_price",
            "multibuy_quantity": 2,
            "multibuy_total_price": "40.00",
        },
    ],
)
def test_invalid_physical_observation_domain_input_returns_422_without_write(
    invalid_fields: dict[str, object],
) -> None:
    client, factory = _client()
    payload: dict[str, object] = {
        "physical_store_id": "physical-hemkop-karhogstorg",
        "gtin": "7310865004703",
        "shelf_price": "29.90",
        "observed_at": NOW.isoformat(),
    }
    payload.update(invalid_fields)

    response = client.post("/physical-check/observations", json=payload)

    assert response.status_code == 422
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalPriceObservationModel)) == 0
        assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 0


def test_fast_cli_records_sample_and_reports_without_catalog_write(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "physical-cli.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id="physical-hemkop-karhogstorg",
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="22358",
                city="Lund",
                official_source="https://www.hemkop.se/",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.commit()
    engine.dispose()
    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")

    assert (
        cli_main(
            [
                "record-physical-price",
                "--store",
                "physical-hemkop-karhogstorg",
                "--gtin",
                "7310865004703",
                "--price",
                "29,90",
                "--observed-at",
                NOW.isoformat(),
            ]
        )
        == 0
    )
    recorded = json.loads(capsys.readouterr().out)
    assert recorded["catalog_price_updated"] is False
    assert recorded["sampled_only"] is True
    assert recorded["observation"]["source"] == "manual"

    assert (
        cli_main(
            [
                "physical-price-report",
                "--store",
                "physical-hemkop-karhogstorg",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["sampled_only"] is True
    assert report["blocks_normal_use"] is False
    assert report["report"]["observation_count"] == 1

    verification_engine = create_database_engine(database_url)
    with create_session_factory(verification_engine)() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalPriceObservationModel)) == 1
        assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 0
    verification_engine.dispose()
