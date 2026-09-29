"""Actual PDF, separate manually read samples and explicit adversarial mutations."""

import copy
import importlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop import xtra_pdf
from grocery_data.app.domain import ProductParseResult, RawFetch, SourceStore
from grocery_data.app.services.offer_rows import qualify_rows

FIX = Path(__file__).parent / "fixtures/xtra-text-20260921"


def source():
    store = SourceStore.model_validate_json((FIX / "store.json").read_bytes())
    doc = RawFetch(
        **json.loads((FIX / "source.json").read_bytes()), payload=(FIX / "source.pdf").read_bytes()
    )
    return store, doc


def parsed():
    store, doc = source()
    rows, report = xtra_pdf.parse_pdf(doc, store, "retained-pdf")
    return rows, report, store, doc


def test_real_pdf_against_separate_text_layout_reference():
    rows, report, store, doc = parsed()
    ref = json.loads((FIX / "manual-reference.json").read_bytes())
    assert doc.payload_hash == ref["document_sha256"]
    assert len(report["pages"]) == 8 and len(rows.products) == 57
    assert not report["complete"]
    for expected in ref["ads"]:
        ad = next(
            a
            for p in report["pages"]
            for a in p["ads"]
            if a["page"] == expected["page"] and a["title"] == expected["title"]
        )
        for key in [
            "package_quantity",
            "package_unit",
            "purchase_price",
            "required_packages",
            "member_only",
        ]:
            assert ad[key] == expected[key]
        assert ad["text_spans"][0]["id"] == expected["title_span"]
        assert [s["id"] for s in ad["price_spans"]] == expected["price_spans"]
        assert expected["comparison"] in ad["body"]
        if expected["reference_amount"]:
            assert expected["reference_amount"] in ad["body"]
        p = next(p for p in rows.products if p.external_product_id == ad["source_product_id"])
        assert p.regular_price is None and p.sale_price is None and p.gtin is None
        assert p.fetched_at == doc.fetched_at
        assert xtra_pdf.row_evidence_matches(p, store)
    accepted, evidence = qualify_rows(rows, store=store, observed_at=doc.fetched_at)
    assert len(accepted.products) == 18
    assert sum(p.source_fields['purchase_terms']['variant_selection']=='resolved' for p in accepted.products)==10
    assert (
        evidence["full_parse"]["denominator"] == 57 and evidence["full_parse"]["threshold"] == 0.95
    )


def test_real_member_deposit_reference_and_shorter_period_are_not_flattened():
    _, report, _, _ = parsed()
    ads = {a["title"]: a for p in report["pages"] for a in p["ads"]}
    assert ads["Bröd"]["member_only"] and ads["Bröd"]["required_packages"] == 2
    water = ads["Kolsyrat vatten 6-pack"]
    assert water["member_only"] and water["purchase_price"] == "34"
    assert water["package_quantity"] is None and "deposit_amount_unverified" in water["blockers"]
    assert ads["Snacktomater"]["valid_from"] == "2026-09-24"
    assert ads["Snacktomater"]["valid_to"] == "2026-09-27"
    assert ads["Couscous"]["purchase_price"] == "15"  # not 4.78 saving or 19.78 reference
    bregott = ads["Bregott"]
    assert bregott["purchase_price"] == "49.90" and bregott["purchase_limit"] == 2
    assert "printed_comparison_conflicts_with_purchase" in bregott["blockers"]
    assert all(p["unclassified_price_spans"] == [] for p in report["pages"])
    assert all(p["advertisement_completeness"].startswith("unknown") for p in report["pages"])


@pytest.mark.parametrize(
    "change",
    [
        {"external_id": "other-store"},
        {"source_fields": {"offers_url": "https://dr.coop.se/Butik/?store=WRONG"}},
        {"source_fields": {"pdf_sha256": "0" * 64}},
        {"source_fields": {"pdf_observed_at": "2026-09-22T00:00:00+00:00"}},
        {"source_fields": {"pdf_pages": 7}},
    ],
)
def test_shared_binding_failures_block_entire_source(change):
    store, doc = source()
    if "source_fields" in change:
        change = {"source_fields": {**store.source_fields, **change["source_fields"]}}
    store = store.model_copy(update=change)
    rows, report = xtra_pdf.parse_pdf(doc, store, "retained")
    accepted, evidence = qualify_rows(rows, store=store, observed_at=doc.fetched_at)
    assert not accepted.products and evidence["shared_blockers"] and report["shared_blocker"]


def test_adjacent_product_price_swap_fails_independent_package_check(monkeypatch):
    store, doc = source()
    meta, pages = xtra_pdf.read_layout(doc.payload)
    # Swap honey30 and granola37; nearest-price selection alone would accept it.
    pages[1]["spans"][81]["text"] = "37"
    pages[1]["spans"][84]["text"] = "30"
    monkeypatch.setattr(xtra_pdf, "read_layout", lambda _: (meta, pages))
    _, report = xtra_pdf.parse_pdf(doc, store, "mutated-layout-test")
    honey = next(a for a in report["pages"][1]["ads"] if a["title"] == "Flytande honung")
    assert "printed_comparison_conflicts_with_purchase" in honey["blockers"]


@pytest.mark.parametrize("condition_y", [100, 700])
def test_unassigned_small_condition_blocks_page_not_other_pages(monkeypatch, condition_y):
    store, doc = source()
    meta, pages = xtra_pdf.read_layout(doc.payload)
    span = copy.deepcopy(pages[2]["spans"][3])
    span.update(
        id=999,
        text="Pant tillkommer",
        bbox=[100, condition_y, 200, condition_y + 10],
        origin=[100, condition_y + 9],
    )
    pages[2]["spans"].append(span)
    monkeypatch.setattr(xtra_pdf, "read_layout", lambda _: (meta, pages))
    rows, report = xtra_pdf.parse_pdf(doc, store, "mutated-layout-test")
    assert all(
        "unassigned_page_critical_condition" in a["blockers"] for a in report["pages"][2]["ads"]
    )
    accepted, _ = qualify_rows(rows, store=store, observed_at=doc.fetched_at)
    assert any(p.name == "Leverpastej" for p in accepted.products)
    assert not any(p.name == "Couscous" for p in accepted.products)


def test_changed_price_package_or_membership_cannot_reuse_ad_binding():
    rows, _, store, doc = parsed()
    p = next(p for p in rows.products if p.name == "Couscous")
    for patch in [
        {"package_quantity": Decimal(1000)},
        {"offers": (p.offers[0].model_copy(update={"price": Decimal(1)}),)},
        {"offers": (p.offers[0].model_copy(update={"member_only": True}),)},
    ]:
        changed = p.model_copy(update=patch)
        result, evidence = qualify_rows(
            ProductParseResult(products=[changed]), store=store, observed_at=doc.fetched_at
        )
        assert not result.products
        assert "pdf_advertisement_binding_mismatch" in evidence["decisions"][0]["blockers"]


class ReplayClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 9, 22, 6, tzinfo=UTC)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def test_member_household_cap_requires_cross_store_campaign_identity(monkeypatch):
    original = xtra_pdf.page_ads

    def changed(page, start, end):
        ads, status = original(page, start, end)
        for ad in ads:
            if ad["title"] == "Couscous":
                ad["body"] += " Max 2 st/hushåll."
                ad["member_only"] = True
        return ads, status

    monkeypatch.setattr(xtra_pdf, "page_ads", changed)
    rows, _, store, doc = parsed()
    accepted, evidence = qualify_rows(rows, store=store, observed_at=doc.fetched_at)
    assert not any(p.name == "Couscous" for p in accepted.products)
    assert any(
        "shared_household_campaign_identity_unverified" in r["blockers"]
        for r in evidence["decisions"]
    )


@pytest.mark.asyncio
async def test_real_pdf_collector_own_pu_checkout_audit_and_future_gate(tmp_path, monkeypatch):
    from app.models import Product
    from app.models.ingredient import NormalizedIngredient
    from app.models.product import ProductCandidate
    from app.services.basket_calculator import BasketCalculator
    from app.services.user_pricing import price_candidate_for_context

    from grocery_data.app.domain.promotion_pricing import UserPricingContext
    from grocery_data.scripts import import_xtra_pdf_text as runner

    for module in [
        "grocery_data.app.api.common",
        "grocery_data.app.api.catalog",
        "grocery_data.app.services.freshness",
        "app.providers.own",
        "app.models.product",
        "grocery_data.app.domain.promotion_pricing",
        "grocery_data.app.services.fixed_checkout_price",
        "grocery_data.scripts.import_xtra_pdf_text",
    ]:
        monkeypatch.setattr(importlib.import_module(module), "datetime", ReplayClock)
    store, doc = source()
    inv = tmp_path / "inventory.json"
    meta = tmp_path / "meta.json"
    inv.write_text(
        json.dumps(
            {
                "area": {"city": "Lund", "mode":"municipality", "municipality_code":"1281"},
                "stores": [
                    {
                        "store": store.model_dump(mode="json"),
                        "geographic_evidence": {"status": "inside"},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    meta.write_text(
        json.dumps(
            {
                "store_id": store.external_id,
                "sha256": doc.payload_hash,
                "observed_at": doc.fetched_at.isoformat(),
                "source_url": doc.url,
                "document_pages": 8,
            }
        ),
        encoding="utf-8",
    )
    await runner.run(inv, meta, FIX / "source.pdf", tmp_path / "run")
    report = json.loads((tmp_path / "run/result.json").read_bytes())
    assert report["partial_promoted"] and report["full_snapshot_status"] == "broken"
    assert report["metrics"]["products_parsed"] == 18 and report["price_universe_count"] == 17
    assert sum(p.get("audit", {}).get("passed", False) for p in report["proofs"]) == 3
    assert report["observed_at"] == doc.fetched_at.isoformat()
    products = [
        Product.model_validate(p)
        for p in json.loads((tmp_path / "run/price-universe.json").read_bytes())["products"]
    ]
    assert not any(p.name == "Snacktomater" for p in products)
    tomato = next(p for p in products if p.name == "Ekologisk tomatpuré")
    candidate = price_candidate_for_context(
        ProductCandidate.from_product(tomato, 1), UserPricingContext(), on_date=date(2026, 9, 22)
    )
    completed = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name="tomatpuré", required_quantity=200, unit="g"), candidate)
    assert completed.packages_needed == tomato.offers[0].required_packages
    assert completed.total_price == tomato.offers[0].price and not completed.ordinary_price_known
    with pytest.raises(ValueError):
        price_candidate_for_context(
            ProductCandidate.from_product(tomato, 1),
            UserPricingContext(),
            on_date=date(2026, 9, 28),
        )
    assert all(p.price is None and p.gtin is None for p in products)


@pytest.mark.asyncio
@pytest.mark.parametrize("age_hours", [-1, 48])
async def test_retained_source_cannot_be_renewed_by_import(tmp_path, monkeypatch, age_hours):
    from grocery_data.scripts import import_xtra_pdf_text as runner

    store, doc = source()

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (doc.fetched_at + timedelta(hours=age_hours)).astimezone(tz)

    monkeypatch.setattr(runner, "datetime", Clock)
    inventory = tmp_path / "inventory.json"
    metadata = tmp_path / "metadata.json"
    inventory.write_text(
        json.dumps(
            {
                "area": {"city": "Lund", "mode":"municipality", "municipality_code":"1281"},
                "stores": [
                    {
                        "store": store.model_dump(mode="json"),
                        "geographic_evidence": {"status": "inside"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    metadata.write_text(
        json.dumps(
            {
                "store_id": store.external_id,
                "sha256": doc.payload_hash,
                "observed_at": doc.fetched_at.isoformat(),
                "source_url": doc.url,
                "document_pages": 8,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="48h current acceptance"):
        await runner.run(inventory, metadata, FIX / "source.pdf", tmp_path / "output")
    assert not (tmp_path / "output").exists()
