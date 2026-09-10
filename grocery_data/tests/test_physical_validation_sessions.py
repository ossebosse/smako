from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select

from grocery_data.app.domain.enums import PromotionType, SaleModel
from grocery_data.app.domain.physical_price import DigitalPriceCandidate
from grocery_data.app.storage.models import (
    PhysicalObservationAmendmentModel,
    PhysicalPriceObservationModel,
    PhysicalValidationSessionCandidateModel,
    PhysicalValidationSessionItemModel,
    PhysicalValidationSessionModel,
    PriceObservationModel,
)
from grocery_data.tests.test_physical_check_api import NOW, _client

SEMANTICS = ("regular", "sale", "member", "multibuy", "weight")


def _candidate(index: int, semantics: str) -> DigitalPriceCandidate:
    current_price = Decimal(10 + index)
    promotion_type = {
        "sale": PromotionType.SALE_PRICE,
        "member": PromotionType.MEMBER_PRICE,
        "multibuy": PromotionType.MULTIBUY,
    }.get(semantics)
    return DigitalPriceCandidate(
        physical_store_id="physical-hemkop-karhogstorg",
        grocery_context_id="primat-hemkop-karhogstorg",
        source_provider="primat",
        source_snapshot_id=f"frozen-snapshot-{index}",
        observed_at=NOW - timedelta(minutes=index),
        product_id=f"product-{index}",
        product_name=f"{semantics.title()} product {index}",
        brand=f"Brand {index % 5}",
        category=f"Category {index % 7}",
        package_description=f"{index + 1}00 g",
        gtin=f"730000000{index:04d}",
        current_price=current_price,
        regular_price=(current_price + 5 if promotion_type else current_price),
        member_price=(current_price if semantics == "member" else None),
        comparison_price=(current_price if semantics == "weight" else None),
        comparison_unit=("kg" if semantics == "weight" else None),
        promotion_type=promotion_type,
        member_only=semantics == "member",
        multibuy_quantity=(2 if semantics == "multibuy" else None),
        multibuy_total_price=(Decimal(30) if semantics == "multibuy" else None),
        sale_model=(
            SaleModel.SOLD_BY_WEIGHT
            if semantics == "weight"
            else SaleModel.FIXED_PACKAGE
        ),
        common_product_score=Decimal(max(0, 20 - index)),
    )


class TwentyCandidateReader:
    def __init__(self) -> None:
        self.candidates = tuple(
            _candidate(index, SEMANTICS[index // 4]) for index in range(20)
        )

    def for_store(self, physical_store_id: str, *, limit: int):  # type: ignore[no-untyped-def]
        assert limit >= 20
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.physical_store_id == physical_store_id
        )

    def for_observation(self, observation):  # type: ignore[no-untyped-def]
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.physical_store_id == observation.physical_store_id
            and (
                candidate.gtin == observation.gtin
                if observation.gtin
                else candidate.product_name.casefold()
                == (observation.product_name or "").casefold()
            )
        )

    def current_for_observation(self, observation):  # type: ignore[no-untyped-def]
        return self.for_observation(observation)


class TwentyFiveCandidateReader(TwentyCandidateReader):
    def __init__(self) -> None:
        candidates = [
            _candidate(index, SEMANTICS[index // 5]) for index in range(25)
        ]
        candidates[10] = candidates[10].model_copy(
            update={
                "product_name": "Rågbröd Bosses",
                "current_price": Decimal("12.00"),
                "regular_price": Decimal("23.61"),
                "member_price": Decimal("12.00"),
            }
        )
        candidates[11] = candidates[11].model_copy(
            update={
                "product_name": "Smör Extrasaltat 81%",
                "current_price": Decimal("39.95"),
                "regular_price": Decimal("54.95"),
                "member_price": Decimal("39.95"),
            }
        )
        candidates[15] = candidates[15].model_copy(
            update={
                "product_name": "Fetaost Block 23%",
                "current_price": Decimal("22.85"),
                "regular_price": Decimal("22.85"),
                "multibuy_quantity": 2,
                "multibuy_total_price": Decimal("43.50"),
            }
        )
        self.candidates = tuple(candidates)


def _session_client():  # type: ignore[no-untyped-def]
    client, factory = _client()
    reader = TwentyCandidateReader()
    client.app.state.external_physical_price_candidate_reader = reader
    return client, factory, reader


def _start(client, *, blind_capture: bool = True):  # type: ignore[no-untyped-def]
    response = client.post(
        "/physical-check/sessions",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "target_sample_size": 20,
            "sampling_strategy": "stratified",
            "blind_capture": blind_capture,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _capture_payload(item, candidate):  # type: ignore[no-untyped-def]
    semantics = item["stratum"]
    payload: dict[str, object] = {
        "gtin": item["target_gtin"],
        "shelf_price": str(candidate.current_price),
        "price_semantics": semantics,
        "identity_status": "exact",
        "observed_at": NOW.isoformat(),
    }
    if semantics == "multibuy":
        payload.update(
            multibuy_quantity=2,
            multibuy_total_price="30.00",
            promotion_text="2 för 30 kr",
        )
    if semantics == "weight":
        payload.update(
            comparison_price=str(candidate.comparison_price),
            comparison_unit="SEK/kg",
        )
    return payload


def test_session_start_freezes_twenty_stratified_candidates_and_hides_prices() -> None:
    client, factory, _reader = _session_client()

    body = _start(client)

    assert body["session"]["blind_capture"] is True
    assert body["session"]["target_count"] == 20
    assert body["available_suggestions"] == 20
    assert body["sample_composition"] == {name: 4 for name in SEMANTICS}
    assert all(item["digital_price_hidden"] for item in body["items"])
    assert all(item["digital_evidence"] == [] for item in body["items"])
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(PhysicalValidationSessionModel)) == 1
        assert (
            session.scalar(select(func.count()).select_from(PhysicalValidationSessionItemModel))
            == 20
        )
        assert (
            session.scalar(
                select(func.count()).select_from(PhysicalValidationSessionCandidateModel)
            )
            == 20
        )


def test_blind_exact_capture_reveals_only_committed_item_with_snapshot_provenance() -> None:
    client, factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])

    response = client.post(
        f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
        json=_capture_payload(item, candidate),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["blind_price_revealed_after_commit"] is True
    assert body["item"]["digital_price_hidden"] is False
    [evidence] = body["item"]["digital_evidence"]
    assert evidence["source_snapshot_id"] == candidate.source_snapshot_id
    assert Decimal(evidence["digital_price"]) == candidate.current_price
    assert body["comparisons"][0]["source_snapshot_id"] == candidate.source_snapshot_id
    assert body["comparison_output"]["physical"] == {
        "price": str(candidate.current_price),
        "basis": "package",
        "unit": "SEK/package",
        "promotion_mechanism": "none",
        "member_only": False,
        "multibuy_quantity": None,
        "multibuy_total_price": None,
    }
    assert Decimal(body["comparison_output"]["digital"]["price"]) == (
        candidate.current_price
    )
    assert body["comparison_output"]["result"]["status"] == "match"
    assert body["catalog_price_updated"] is False
    session_body = client.get(
        f"/physical-check/sessions/{started['session']['id']}"
    ).json()
    assert sum(not row["digital_price_hidden"] for row in session_body["items"]) == 1
    with factory() as database_session:
        assert (
            database_session.scalar(
                select(func.count()).select_from(PhysicalPriceObservationModel)
            )
            == 1
        )
        assert (
            database_session.scalar(select(func.count()).select_from(PriceObservationModel))
            == 0
        )


def test_blind_identity_lookup_verifies_gtin_without_revealing_price() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
    url = (
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/identity"
    )

    matched = client.get(url, params={"gtin": candidate.gtin})
    missing = client.get(url, params={"gtin": "4000000000999"})

    assert matched.status_code == 200
    assert matched.json() == {
        "status": "match",
        "match_method": "exact_gtin",
        "gtin": candidate.gtin,
        "product_name": item["target_product_name"],
        "brand": item["target_brand"],
        "package": item["target_package"],
        "matching_evidence_rows": 1,
        "digital_price_hidden": True,
    }
    assert not any("price" in key for key in matched.json() if key != "digital_price_hidden")
    assert missing.status_code == 200
    assert missing.json()["status"] == "no_match"
    assert missing.json()["digital_price_hidden"] is True


def test_exact_gtin_identity_collapses_provider_rows_but_reports_distinct_products() -> None:
    client, factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
    url = (
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/identity"
    )

    def add_evidence(*, name: str, package: str | None, suffix: str) -> None:
        with factory() as database_session:
            database_session.add(
                PhysicalValidationSessionCandidateModel(
                    id=f"candidate-{suffix}",
                    session_item_id=item["id"],
                    physical_store_id=candidate.physical_store_id,
                    grocery_context_id=f"context-{suffix}",
                    source_provider=f"provider-{suffix}",
                    source_snapshot_id=f"snapshot-{suffix}",
                    observed_at=candidate.observed_at,
                    product_id=f"product-{suffix}",
                    product_name=name,
                    brand=candidate.brand,
                    category=candidate.category,
                    package_description=package,
                    gtin=candidate.gtin,
                    current_price=candidate.current_price,
                    regular_price=candidate.regular_price,
                    member_price=candidate.member_price,
                    comparison_price=candidate.comparison_price,
                    comparison_unit=candidate.comparison_unit,
                    promotion_type=(
                        candidate.promotion_type.value if candidate.promotion_type else None
                    ),
                    member_only=candidate.member_only,
                    multibuy_quantity=candidate.multibuy_quantity,
                    multibuy_total_price=candidate.multibuy_total_price,
                    sale_model=candidate.sale_model.value,
                    common_product_score=candidate.common_product_score,
                    recent_price_change=candidate.recent_price_change,
                    candidate_sha256=("a" if suffix == "duplicate" else "b") * 64,
                )
            )
            database_session.commit()

    add_evidence(
        name=f"  {candidate.product_name.upper()}  ",
        package=candidate.package_description,
        suffix="duplicate",
    )
    duplicated = client.get(url, params={"gtin": candidate.gtin}).json()
    assert duplicated["status"] == "match"
    assert duplicated["matching_evidence_rows"] == 2
    assert duplicated["digital_price_hidden"] is True

    add_evidence(name="Annan exakt GTIN-produkt", package="500 g", suffix="conflict")
    ambiguous = client.get(url, params={"gtin": candidate.gtin}).json()
    assert ambiguous["status"] == "multiple_matches"
    assert len(ambiguous["products"]) == 2
    assert sum(row["matching_evidence_rows"] for row in ambiguous["products"]) == 3
    assert ambiguous["digital_price_hidden"] is True
    assert not any("price" in key for key in ambiguous if key != "digital_price_hidden")


def test_capture_retries_are_idempotent_for_the_same_client_request_id() -> None:
    client, factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
    payload = _capture_payload(item, candidate)
    payload["client_request_id"] = "field-request-00000001"
    url = (
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation"
    )

    first = client.post(url, json=payload)
    retried = client.post(url, json=payload)

    assert first.status_code == 201, first.text
    assert retried.status_code == 201, retried.text
    assert first.json()["idempotent_replay"] is False
    assert retried.json()["idempotent_replay"] is True
    assert retried.json()["observation"]["id"] == first.json()["observation"]["id"]
    with factory() as database_session:
        assert (
            database_session.scalar(
                select(func.count()).select_from(PhysicalPriceObservationModel)
            )
            == 1
        )


def test_exact_identity_fails_closed_but_explicit_no_match_is_preserved() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
    payload = _capture_payload(item, candidate)
    payload["gtin"] = "4000000000999"

    rejected = client.post(
        f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
        json=payload,
    )
    assert rejected.status_code == 422

    payload["identity_status"] = "no_match"
    accepted = client.post(
        f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
        json=payload,
    )
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["observation"]["identity_status"] == "no_match"
    assert accepted.json()["observation"]["confidence"] == "low"
    assert accepted.json()["comparisons"][0]["status"] == "no_digital_match"


def test_all_price_semantics_compare_without_flattening_conditions() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    by_semantics = {item["stratum"]: item for item in started["items"]}

    for semantics in SEMANTICS:
        item = by_semantics[semantics]
        candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
        response = client.post(
            f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
            json=_capture_payload(item, candidate),
        )
        assert response.status_code == 201, response.text
        comparison = response.json()["comparisons"][0]
        assert comparison["status"] == "match"
        if semantics == "multibuy":
            assert comparison["physical_price"] == "30.00"
            assert comparison["digital_price"] == "30.00"
            assert comparison["multibuy_match"] is True
        if semantics == "weight":
            assert comparison["comparison_price_match"] is True


def test_complete_twenty_sample_exports_v3_official_frozen_evidence() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    for item in started["items"]:
        candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
        response = client.post(
            f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
            json=_capture_payload(item, candidate),
        )
        assert response.status_code == 201, response.text

    completed = client.post(
        f"/physical-check/sessions/{started['session']['id']}/complete",
        json={},
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["captured_observations"] == 20
    assert body["accuracy_display"] == "insufficient_sample"
    assert body["v3_official"]["physical_observation_count"] == 20
    assert body["v3_official"]["comparable_denominator"] == 16
    assert body["v3_official"]["excluded_comparisons"] == 4
    assert body["v3_official"]["minimum_comparable_sample"] == 20
    assert body["v3_official"]["score_eligible"] is False
    assert body["report"]["score_eligible"] is True
    assert body["report"]["sampled_only"] is True
    assert body["report"]["providers"]["primat"]["mean_absolute_error"] == "0.00"
    assert body["report"]["providers"]["primat"]["median_absolute_error"] == "0.00"

    json_export = client.get(
        f"/physical-check/sessions/{started['session']['id']}/export?format=json"
    )
    csv_export = client.get(
        f"/physical-check/sessions/{started['session']['id']}/export?format=csv"
    )
    assert json_export.status_code == 200
    assert json_export.json()["sampled_only"] is True
    assert json_export.json()["accuracy_display"] == "insufficient_sample"
    assert json_export.json()["v3_official"]["comparable_denominator"] == 16
    assert json_export.json()["v3_official"]["score_eligible"] is False
    assert len(json_export.json()["rows"]) == 20
    assert json_export.json()["rows"][0]["snapshot_id"].startswith("frozen-snapshot-")
    assert any(
        row["promotion_text"] == "2 för 30 kr"
        for row in json_export.json()["rows"]
    )
    assert csv_export.status_code == 200
    assert "snapshot_id" in csv_export.text.splitlines()[0]
    assert "frozen-snapshot-" in csv_export.text
    assert "2 för 30 kr" in csv_export.text


def test_completed_twenty_raw_observations_hide_accuracy_below_v3_threshold() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    for index, item in enumerate(started["items"]):
        candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
        payload = _capture_payload(item, candidate)
        if index == 0:
            payload["identity_status"] = "no_match"
        response = client.post(
            f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
            json=payload,
        )
        assert response.status_code == 201, response.text

    completed = client.post(
        f"/physical-check/sessions/{started['session']['id']}/complete",
        json={},
    )
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["captured_observations"] == 20
    assert body["report"]["score_eligible"] is True
    assert body["v3_official"]["physical_observation_count"] == 20
    assert body["v3_official"]["comparable_denominator"] == 15
    assert body["v3_official"]["excluded_comparisons"] == 5
    assert body["v3_official"]["minimum_comparable_sample"] == 20
    assert body["v3_official"]["score_eligible"] is False
    assert body["accuracy_display"] == "insufficient_sample"

    report = client.get(
        f"/physical-check/sessions/{started['session']['id']}/report"
    )
    assert report.status_code == 200, report.text
    assert report.json()["v3_official"]["comparable_denominator"] == 15
    assert report.json()["v3_official"]["score_eligible"] is False
    assert report.json()["accuracy_display"] == "insufficient_sample"

    json_export = client.get(
        f"/physical-check/sessions/{started['session']['id']}/export?format=json"
    )
    assert json_export.status_code == 200, json_export.text
    assert json_export.json()["v3_official"]["comparable_denominator"] == 15
    assert json_export.json()["v3_official"]["score_eligible"] is False
    assert json_export.json()["accuracy_display"] == "insufficient_sample"


def test_accuracy_is_hidden_below_twenty_samples() -> None:
    client, _factory, reader = _session_client()
    started = _start(client)
    item = started["items"][0]
    candidate = next(row for row in reader.candidates if row.gtin == item["target_gtin"])
    client.post(
        f"/physical-check/sessions/{started['session']['id']}/items/{item['id']}/observation",
        json=_capture_payload(item, candidate),
    )

    report = client.get(
        f"/physical-check/sessions/{started['session']['id']}/report"
    ).json()

    assert report["accuracy_display"] == "insufficient_sample"
    assert report["report"]["score_eligible"] is False
    assert report["report"]["providers"]["primat"]["display_exact_percent"] is None
    assert report["sampled_only"] is True


def test_completed_session_amendments_are_append_only_and_score_separately() -> None:
    client, factory = _client()
    reader = TwentyFiveCandidateReader()
    client.app.state.external_physical_price_candidate_reader = reader
    start_response = client.post(
        "/physical-check/sessions",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "target_sample_size": 25,
            "sampling_strategy": "stratified",
            "blind_capture": True,
        },
    )
    assert start_response.status_code == 201, start_response.text
    started = start_response.json()
    session_id = started["session"]["id"]
    items_by_name = {item["target_product_name"]: item for item in started["items"]}
    missing_names = {"Rågbröd Bosses", "Smör Extrasaltat 81%"}
    feta_item = items_by_name["Fetaost Block 23%"]
    raw_feta: dict[str, object] | None = None

    for item in started["items"]:
        if item["target_product_name"] in missing_names:
            continue
        candidate = next(
            row for row in reader.candidates if row.gtin == item["target_gtin"]
        )
        payload = _capture_payload(item, candidate)
        if item["id"] == feta_item["id"]:
            payload["identity_status"] = "no_match"
        response = client.post(
            f"/physical-check/sessions/{session_id}/items/{item['id']}/observation",
            json=payload,
        )
        assert response.status_code == 201, response.text
        if item["id"] == feta_item["id"]:
            raw_feta = response.json()["observation"]

    assert raw_feta is not None
    completed = client.post(
        f"/physical-check/sessions/{session_id}/complete",
        json={},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["captured_observations"] == 23
    assert completed.json()["v3_official"]["comparable_denominator"] == 17
    assert completed.json()["v3_official"]["score_eligible"] is False
    assert "v3_amended" not in completed.json()

    def amendment_payload(
        *,
        kind: str,
        product_name: str,
        shelf_price: str,
        price_semantics: str,
        regular_shelf_price: str,
        client_request_id: str,
        base_observation_id: str | None = None,
    ) -> dict[str, object]:
        observation: dict[str, object] = {
            "product_name": product_name,
            "shelf_price": shelf_price,
            "regular_shelf_price": regular_shelf_price,
            "price_semantics": price_semantics,
            "identity_status": "manual_exact_match",
            "identification_evidence": "source_product_manual",
            "observed_at": NOW.isoformat(),
        }
        if price_semantics == "multibuy":
            observation.update(
                multibuy_quantity=2,
                multibuy_total_price="43.50",
                promotion_text="2 för 43,50 kr",
            )
        return {
            "kind": kind,
            "observation": observation,
            "base_observation_id": base_observation_id,
            "observed_at_precision": "minute",
            "reason": "Recovered from the completed field visit",
            "evidence_source": "field_notes",
            "evidence_reference": f"test-photo:{product_name}",
            "client_request_id": client_request_id,
        }

    for product_name, price, regular_price, request_id in (
        ("Rågbröd Bosses", "12.00", "23.61", "late-ragbrod-00000001"),
        ("Smör Extrasaltat 81%", "39.95", "54.95", "late-smor-000000001"),
    ):
        item = items_by_name[product_name]
        response = client.post(
            f"/physical-check/sessions/{session_id}/items/{item['id']}/amendments",
            json=amendment_payload(
                kind="late_capture",
                product_name=product_name,
                shelf_price=price,
                regular_shelf_price=regular_price,
                price_semantics="member",
                client_request_id=request_id,
            ),
        )
        assert response.status_code == 201, response.text
        assert response.json()["raw_observation"] is None
        assert response.json()["raw_observation_preserved"] is True
        assert response.json()["v3_official"]["comparable_denominator"] == 17

    feta_amendment = amendment_payload(
        kind="correction",
        product_name="Fetaost Block 23%",
        shelf_price="43.50",
        regular_shelf_price="22.85",
        price_semantics="multibuy",
        client_request_id="correct-feta-00000001",
        base_observation_id=str(raw_feta["id"]),
    )
    feta_url = (
        f"/physical-check/sessions/{session_id}/items/{feta_item['id']}/amendments"
    )
    corrected = client.post(feta_url, json=feta_amendment)
    assert corrected.status_code == 201, corrected.text
    corrected_body = corrected.json()
    assert corrected_body["idempotent_replay"] is False
    assert corrected_body["raw_observation"]["identity_status"] == "no_match"
    assert Decimal(corrected_body["raw_observation"]["shelf_price"]) == Decimal(
        str(raw_feta["shelf_price"])
    )
    assert (
        corrected_body["effective_observation"]["identity_status"]
        == "manual_exact_match"
    )
    assert corrected_body["effective_observation"]["shelf_price"] == "43.50"
    assert corrected_body["effective_observation"]["regular_shelf_price"] == "22.85"
    assert corrected_body["v3_official"]["comparable_denominator"] == 17
    assert corrected_body["v3_official"]["score_eligible"] is False
    assert corrected_body["v3_amended"]["comparable_denominator"] == 20
    assert corrected_body["v3_amended"]["score_eligible"] is True
    assert corrected_body["v3_amended"]["official"] is False
    assert corrected_body["v3_amended"]["amended_physical_evidence"] is True
    assert corrected_body["v3_amended"]["version"]["kind"] == (
        "amended_physical_evidence"
    )
    assert corrected_body["official_replaced_by_amendment"] is False

    replay = client.post(feta_url, json=feta_amendment)
    assert replay.status_code == 201, replay.text
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["amendment"]["id"] == corrected_body["amendment"]["id"]

    divergent = {
        **feta_amendment,
        "observation": {
            **feta_amendment["observation"],  # type: ignore[dict-item]
            "shelf_price": "44.00",
            "multibuy_total_price": "44.00",
        },
    }
    conflict = client.post(feta_url, json=divergent)
    assert conflict.status_code == 409, conflict.text

    stale_head = amendment_payload(
        kind="correction",
        product_name="Fetaost Block 23%",
        shelf_price="43.50",
        regular_shelf_price="22.85",
        price_semantics="multibuy",
        client_request_id="correct-feta-stale-0001",
        base_observation_id=str(raw_feta["id"]),
    )
    stale = client.post(feta_url, json=stale_head)
    assert stale.status_code == 409, stale.text

    report = client.get(f"/physical-check/sessions/{session_id}/report")
    assert report.status_code == 200, report.text
    report_body = report.json()
    assert report_body["v3_official"]["comparable_denominator"] == 17
    assert report_body["v3_official"]["score_eligible"] is False
    assert report_body["accuracy_display"] == "insufficient_sample"
    assert report_body["v3_amended"]["comparable_denominator"] == 20
    assert report_body["v3_amended"]["score_eligible"] is True
    assert report_body["amended_accuracy_display"] == "scored"

    exported = client.get(
        f"/physical-check/sessions/{session_id}/export?format=json"
    )
    assert exported.status_code == 200, exported.text
    export_body = exported.json()
    assert len(export_body["rows"]) == 23
    assert export_body["v3_official"]["comparable_denominator"] == 17
    assert export_body["v3_official"]["score_eligible"] is False
    assert export_body["v3_amended"]["comparable_denominator"] == 20
    assert export_body["v3_amended"]["score_eligible"] is True
    assert export_body["amended_accuracy_display"] == "scored"

    with factory() as database_session:
        base_rows = list(
            database_session.scalars(
                select(PhysicalPriceObservationModel).where(
                    PhysicalPriceObservationModel.validation_session_id == session_id
                )
            )
        )
        assert len(base_rows) == 23
        persisted_feta = next(row for row in base_rows if row.id == raw_feta["id"])
        assert persisted_feta.identity_status == "no_match"
        assert persisted_feta.shelf_price == Decimal(str(raw_feta["shelf_price"]))
        assert not any(
            row.validation_session_item_id
            in {
                items_by_name["Rågbröd Bosses"]["id"],
                items_by_name["Smör Extrasaltat 81%"]["id"],
            }
            for row in base_rows
        )
        assert (
            database_session.scalar(
                select(func.count()).select_from(PhysicalObservationAmendmentModel)
            )
            == 3
        )
