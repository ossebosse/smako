import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from app.services.axfood_product_details import merge_axfood_details

from backend.tests.test_axfood_product_details import _Product, catalogue_fact, detail, store
from grocery_data.app.domain.enums import Chain
from grocery_data.app.services.axfood_detail_archive import (
    publish_release,
    read_document,
    recheck_state,
    retain_response,
    selection_state,
    verify_release,
)

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)
CODE = "101548687_ST"


@pytest.mark.parametrize("mutation", [
    {"code": "other"}, {"chain": "hemkop"}, {"url": "https://example.org/axfood/rest/p/101548687_ST"},
    {"fetched_at": "2026-10-22"}, {"fetched_at": "2999-01-01T00:00:00Z"},
    {"http_status": 404}, {"payload_sha256": "0" * 64},
])
def test_invalid_evidence_is_counted_and_never_enriches(tmp_path, mutation):
    store(tmp_path, "willys", detail())
    path = tmp_path / "willys" / f"{CODE}.meta.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), **mutation}))
    facts = {("s1", "p1"): catalogue_fact()}
    before = asdict(facts[("s1", "p1")])
    stats = merge_axfood_details([_Product("willys")], facts, tmp_path)
    assert stats["rejected_own_document"] == 1
    assert asdict(facts[("s1", "p1")]) == before


def test_broken_own_document_is_visible_even_when_shared_fallback_succeeds(tmp_path):
    store(tmp_path, "willys", detail())
    store(tmp_path, "hemkop", detail())
    (tmp_path / "hemkop" / f"{CODE}.meta.json").write_text("{")
    facts = {("s1", "p1"): catalogue_fact()}
    stats = merge_axfood_details([_Product("hemkop")], facts, tmp_path)
    assert stats["shared_document"] == 1 and stats["rejected_own_document"] == 1
    assert stats["rejections"]["corrupt"] == 1


def test_missing_gtin_cannot_fill_a_catalogue_gtin_and_zero_padding_is_exact(tmp_path):
    facts = {("s1", "p1"): catalogue_fact()}
    store(tmp_path, "willys", detail(ean=None))
    assert merge_axfood_details([_Product("willys", "7311043008346")], facts, tmp_path)["gtin_mismatch"] == 1
    store(tmp_path, "willys", detail(ean="07311043008346"))
    assert merge_axfood_details([_Product("willys", "7311043008346")], facts, tmp_path)["own_document"] == 1


def test_conflicting_detail_cannot_overwrite_or_approve_existing_declaration(tmp_path):
    store(tmp_path, "willys", detail())
    prior = replace(catalogue_fact(), nutrition={"protein_g": 999}, nutrition_unit="g",
                    nutrition_basis="per 100 g", ingredients=("annan deklaration",))
    facts = {("s1", "p1"): prior}
    merge_axfood_details([_Product("willys")], facts, tmp_path)
    result = facts[("s1", "p1")]
    assert result.nutrition["protein_g"] == 999 and result.ingredients == prior.ingredients
    assert {"ingredients", "nutrition_basis"} <= set(result.conflicts)


def test_revocation_does_not_disappear_behind_shared_document(tmp_path):
    store(tmp_path, "willys", detail())
    store(tmp_path, "hemkop", detail())
    path = tmp_path / "hemkop" / f"{CODE}.meta.json"
    path.write_text(json.dumps({**json.loads(path.read_text()), "revoked": True}))
    facts = {("s1", "p1"): catalogue_fact()}
    stats = merge_axfood_details([_Product("hemkop")], facts, tmp_path)
    assert stats["shared_document"] == 0 and "axfood_identity_revoked" in facts[("s1", "p1")].conflicts


def test_revocation_only_release_blocks_shared_article_and_survives_publication(tmp_path):
    staging = tmp_path / "staging/run"
    store(staging, "willys", detail())
    meta = staging / "willys" / f"{CODE}.meta.json"
    meta.write_text(json.dumps({**json.loads(meta.read_bytes()), "revoked": True}))
    release = publish_release(tmp_path, "run")
    facts = {("s1", "p1"): catalogue_fact()}
    merge_axfood_details([_Product("hemkop")], facts, release)
    assert "axfood_identity_revoked" in facts[("s1", "p1")].conflicts
    assert not facts[("s1", "p1")].nutrition


def raw(status=200, *, chain="willys", document=None):
    body = json.dumps(detail() if document is None else document).encode()
    return SimpleNamespace(chain=Chain(chain), payload=body, payload_hash=hashlib.sha256(body).hexdigest(),
        http_status=status, url=f"https://www.{chain}.se/axfood/rest/p/{CODE}",
        query={}, fetched_at=NOW, content_type="application/json", connector_version="fixture", store_external_id="1",
        kind="product_detail")


def test_failures_retain_lkg_and_observation_time_but_have_separate_retry_state(tmp_path):
    staging = tmp_path / "staging" / "run"
    retain_response(staging, "willys", CODE, raw(), now=NOW)
    old = (staging / "willys" / f"{CODE}.meta.json").read_bytes()
    assert recheck_state(staging, "willys", CODE, now=NOW + timedelta(days=29)) == "verified"
    assert recheck_state(staging, "willys", CODE, now=NOW + timedelta(days=30)) == "due"
    retain_response(staging, "willys", CODE, raw(404), now=NOW + timedelta(days=30))
    assert (staging / "willys" / f"{CODE}.meta.json").read_bytes() == old
    assert selection_state(staging, "willys", CODE, now=NOW + timedelta(days=36)) == "waiting_after_error"
    assert selection_state(staging, "willys", CODE, now=NOW + timedelta(days=37)) == "due"


def test_missing_and_access_stops_do_not_get_skipped_as_success(tmp_path):
    staging = tmp_path / "staging" / "run"
    retain_response(staging, "willys", CODE, raw(404), now=NOW)
    assert recheck_state(staging, "willys", CODE, now=NOW) == "permanent_missing"
    assert recheck_state(staging, "willys", CODE, now=NOW + timedelta(days=7)) == "due_missing"
    retain_response(staging, "willys", CODE, raw(429), now=NOW, retry_after=7200)
    assert selection_state(staging, "willys", CODE, now=NOW + timedelta(days=8)) == "access_stopped"


def test_negative_evidence_survives_release_and_next_staging_copy(tmp_path):
    import shutil

    staging = tmp_path / "staging/run"
    retain_response(staging, "willys", CODE, raw(404), now=NOW)
    store(staging, "hemkop", detail())
    release = publish_release(tmp_path, "run")
    assert read_document(release, "willys", CODE, now=NOW, manifest=verify_release(release)).status == "http_error"
    newer = tmp_path / "staging/new"
    shutil.copytree(release, newer)
    assert selection_state(newer, "willys", CODE, now=NOW + timedelta(days=6)) == "waiting_after_error"
    assert selection_state(newer, "willys", CODE, now=NOW + timedelta(days=7)) == "due_missing"


def test_release_is_atomic_and_staging_failure_cannot_mutate_it(tmp_path, monkeypatch):
    staging = tmp_path / "staging" / "run"
    retain_response(staging, "willys", CODE, raw(), now=NOW)
    release = publish_release(tmp_path, "run")
    before = verify_release(release)
    payload = staging / "willys" / f"{CODE}.json"
    payload.write_text("half-written")
    with pytest.raises(ValueError, match="Rejected staging pair"):
        publish_release(tmp_path, "run")
    assert verify_release(release) == before
    # Even a warm manifest cache never approves a changed consumed pair.
    merge_axfood_details([_Product("willys")], {("s1", "p1"): catalogue_fact()}, release)
    (release / "willys" / f"{CODE}.json").write_text("tampered")
    stats = merge_axfood_details([_Product("willys")], {("s1", "p1"): catalogue_fact()}, release)
    assert stats["rejections"]["release_file_mismatch"] == 1


def test_unsafe_identity_is_rejected_before_reading(tmp_path):
    assert read_document(tmp_path, "willys", "../secret").status == "invalid_identity"


def test_retention_protects_active_rollback_and_evidence(tmp_path, monkeypatch):
    import os

    from deploy.scripts.storage_maintenance import maintain_axfood_archives

    releases = []
    for index in range(4):
        staging = tmp_path / "staging" / f"run{index}"
        retain_response(staging, "willys", CODE, raw(document=detail(ingredients=f"declared ingredient {index}")), now=NOW)
        releases.append(publish_release(tmp_path, f"run{index}"))
    (tmp_path / "retention.json").write_text(json.dumps({
        "active": releases[0].name, "rollback": releases[1].name,
        "evidence": [releases[2].name]}))
    old = (datetime.now(UTC) - timedelta(days=10)).timestamp()
    for item in releases:
        for path in [item, *item.rglob("*")]:
            os.utime(path, (old, old))
    monkeypatch.setenv("AXFOOD_ARCHIVE_MAX_RELEASES", "2")
    report = maintain_axfood_archives(tmp_path, now=datetime.now(UTC), apply=True)
    assert all(path.exists() for path in releases[:3])
    assert report["status"] == "blocked"  # Protected evidence wins over cap.


@pytest.mark.asyncio
async def test_collector_stops_on_429_and_never_visits_the_next_code(tmp_path, monkeypatch):
    import argparse
    import importlib
    from pathlib import Path

    from grocery_data.app.connectors.willys.client import WillysHttpError

    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "scripts"))
    collector = importlib.import_module("fetch_axfood_product_details")
    codes = [CODE, "next_ST"]
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"schema": "smako-axfood-code-list-v1", "chain": "willys",
        "codes_sha256": hashlib.sha256(("\n".join(codes) + "\n").encode()).hexdigest(),
        "store_external_ids": ["1"], "catalogs": [{"sha256": "a" * 64}]}))
    calls = []

    class Client:
        requests_per_second = 1

        def __init__(self, **kwargs):
            pass

        async def fetch_product_detail(self, store, code):
            calls.append(code)
            raise WillysHttpError("synthetic rate limit", raw(429))

        async def aclose(self):
            pass

    monkeypatch.setattr(collector, "WillysClient", Client)
    args = argparse.Namespace(chain="willys", catalog_proof=proof, publish_only=False,
                              limit=0, store_id="1", archive_root=tmp_path)
    assert await collector.collect(args, codes, tmp_path / "staging/run", 1) == 2
    assert calls == [CODE]
    assert await collector.collect(args, codes, tmp_path / "staging/run", 1) == 2
    assert calls == [CODE]


def test_augment_checks_all_input_hashes_and_updates_both_changed_outputs(tmp_path):
    from backend.scripts.augment_review_facts import augment
    from backend.tests.test_personal_planning_v2 import prepared, product

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    values = {"combined-prices.json": prepared(product("ris", 1000, "g", 10)).to_json().encode(),
              "combined-request.json": b'{"synthetic":true}',
              "combined-facts.json": b'{"facts":[]}', "product-facts.json": b'{"rows":[]}'}
    for name, body in values.items():
        (inputs / name).write_bytes(body)
    manifest = {"now": NOW.isoformat(), "sha256": {
        name: hashlib.sha256(body).hexdigest() for name, body in values.items()}}
    (inputs / "matrix-inputs.json").write_text(json.dumps(manifest))
    (inputs / "combined-request.json").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="combined-request.json"):
        augment(inputs, tmp_path / "bad")
    assert not (tmp_path / "bad").exists()
    (inputs / "combined-request.json").write_bytes(values["combined-request.json"])
    augment(inputs, tmp_path / "output")
    result = json.loads((tmp_path / "output/matrix-inputs.json").read_bytes())
    assert result["now"] == manifest["now"]
    for name, digest in result["sha256"].items():
        data = (tmp_path / "output" / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest
        if name in {"combined-prices.json", "combined-request.json"}:
            assert data == values[name]
