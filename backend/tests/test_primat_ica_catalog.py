from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.services.primat_ica_catalog import (
    CatalogStore,
    QuotaExhausted,
    catalog_products,
    is_food_category,
    merge_row,
    run_catalog_step,
)

STORES = [
    {"chain": "ica", "store_id": "1088004", "name": "Maxi Gunnesbo", "city": "Lund", "tier": "full"},
    {"chain": "ica", "store_id": "1003569", "name": "Maxi Västra Hamnen", "city": "Malmö", "tier": "full"},
    {"chain": "ica", "store_id": "1000001", "name": "ICA Nära", "city": "Lund", "tier": "offers_only"},
    {"chain": "willys", "store_id": "2103", "name": "Willys", "city": "Lund", "tier": "full"},
    {"chain": "ica", "store_id": "1009999", "name": "Maxi Elsewhere", "city": "Ystad", "tier": "full"},
]


def _row(store: str, product: int, *, category: str = "Skafferi > Mjöl", price: float = 10.0,
         offer: float | None = None) -> dict:
    return {
        "chain": "ica", "store_id": store, "product_id": f"p{product}", "name": f"Vara {product}",
        "category": category, "price": price, "offer_price": offer,
        "changed_at": "2026-11-20T00:00:00+00:00",
    }


class FakePrimat:
    def __init__(self, catalog: list[dict], *, used: int = 0, per_day: int = 20000,
                 stores: list[dict] | None = None, fail_after: int | None = None) -> None:
        self.catalog = catalog
        self.used = used
        self.per_day = per_day
        self.stores = STORES if stores is None else stores
        self.calls: list[tuple[str, str, dict | None]] = []
        self.batch_ids: list[str] = []
        self.fail_after = fail_after

    async def __call__(self, method, path, *, params=None, json=None):
        self.calls.append((method, path, params))
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise QuotaExhausted("429")
        if path == "/me":
            return {"plan": {"rows_per_day": self.per_day, "rows_returned_today": self.used,
                             "max_rows_per_call": 200}}
        if path == "/stores":
            return {"stores": self.stores}
        if path == "/prices":
            wanted = set(params["stores"].split(","))
            rows = [r for r in self.catalog if f"ica:{r['store_id']}" in wanted]
            if params.get("offers"):
                rows = [r for r in rows if r.get("offer_price")]
            start = int(params.get("cursor") or 0)
            page = rows[start:start + params["limit"]]
            self.used += len(page)
            nxt = start + params["limit"]
            return {"data": page, "next_cursor": str(nxt) if nxt < len(rows) else None}
        if path == "/batch":
            data = []
            for lookup in json["lookups"]:
                self.batch_ids.append(lookup["product_id"])
                data.append({"lookup": lookup, "count": 1, "results": [{
                    "chain": "ica", "store_id": lookup["store_id"], "product_id": lookup["product_id"],
                    "amount": 500, "unit": "g", "package": "500 g", "sold_by_weight": False,
                    "prices": {"regular": 20.0, "comparison": {"price": 40.0, "unit": "kg"}},
                }]})
            self.used += len(data)
            return {"data": data, "count": len(data)}
        raise AssertionError(path)


async def _no_sleep(_seconds: float) -> None:
    return None


def _step(store, fake, **kwargs):
    return asyncio.run(run_catalog_step(store, fake, cities=["Lund", "Malmö"],
                                        sleep=_no_sleep, **kwargs))


def test_only_full_ica_stores_in_the_cities_are_fetched(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    fake = FakePrimat([_row("1088004", 1)])
    report = _step(store, fake, max_rows=19000)
    assert report.stores == ["ica:1003569", "ica:1088004"]
    prices = [params for _m, path, params in fake.calls if path == "/prices"]
    assert all(p["stores"] == "ica:1003569,ica:1088004" for p in prices)


def test_a_round_continues_across_days_within_the_budget(tmp_path):
    catalog = [_row(s, i) for i in range(500) for s in ("1088004", "1003569")]  # 1000 rows
    store = CatalogStore(tmp_path / "c.sqlite")
    day1 = _step(store, FakePrimat(catalog), max_rows=500, reserve_rows=0, offers=False)
    assert day1.budget_rows == 500
    assert day1.rows_used <= 500 and not day1.round_completed
    assert store.get("catalog_cursor") is not None
    reports = [day1]
    for _ in range(10):
        reports.append(_step(store, FakePrimat(catalog), max_rows=500, reserve_rows=0, offers=False))
        if reports[-1].round_completed:
            break
    assert reports[-1].round_completed
    assert store.counts()["rows_per_store"] == {"ica:1003569": 500, "ica:1088004": 500}
    assert store.get("catalog_cursor") is None
    # Package details trail the round and are asked once per product,
    # shared by both stores.
    fake = FakePrimat(catalog)
    for _ in range(5):
        _step(store, fake, max_rows=500, reserve_rows=0, offers=False)
    assert store.counts()["meta_products"] == 500
    assert len(fake.batch_ids) == 100


def test_budget_respects_rows_already_used_today_and_the_reserve(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    report = _step(store, FakePrimat([_row("1088004", 1)], used=19000), max_rows=19000,
                   reserve_rows=500)
    assert report.budget_rows == 500
    report = _step(store, FakePrimat([_row("1088004", 1)], used=19800), max_rows=19000,
                   reserve_rows=500)
    assert report.budget_rows == 0 and report.rows_used == 0


def test_package_details_are_looked_up_only_for_food(tmp_path):
    catalog = [_row("1088004", 1), _row("1088004", 2, category="Skönhet > Hår"),
               _row("1088004", 3, category="Barn > Barnmat"), _row("1088004", 4, category="Barn > Blöjor")]
    store = CatalogStore(tmp_path / "c.sqlite")
    fake = FakePrimat(catalog)
    _step(store, fake, max_rows=19000)
    _step(store, fake, max_rows=19000)
    assert sorted(fake.batch_ids) == ["p1", "p3"]


def test_finished_round_removes_products_the_store_no_longer_sells(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    _step(store, FakePrimat([_row("1088004", 1), _row("1088004", 2)]), max_rows=19000)
    report = _step(store, FakePrimat([_row("1088004", 1)]), max_rows=19000)
    assert report.round_completed and report.rows_removed == 1
    assert store.counts()["rows_per_store"] == {"ica:1088004": 1}


def test_offers_are_read_once_a_day(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    catalog = [_row("1088004", 1, offer=8.0), _row("1088004", 2)]
    fake = FakePrimat(catalog)
    first = _step(store, fake, max_rows=19000)
    second = _step(store, fake, max_rows=19000)
    assert first.offer_rows == 1 and second.offer_rows == 0


def test_a_new_store_starts_a_new_round(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    catalog = [_row(s, i) for i in range(400) for s in ("1088004", "1003569")]
    only_lund = [STORES[0]]
    _step(store, FakePrimat(catalog, stores=only_lund), max_rows=300, reserve_rows=0, offers=False)
    assert store.get("catalog_scope") == "ica:1088004"
    _step(store, FakePrimat(catalog), max_rows=300, reserve_rows=0, offers=False)
    assert store.get("catalog_scope") == "ica:1003569,ica:1088004"


def test_rate_limit_stops_the_day_and_keeps_progress(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    catalog = [_row("1088004", i) for i in range(1000)]
    report = _step(store, FakePrimat(catalog, fail_after=5), max_rows=19000, offers=False)
    assert report.stopped == "quota_exhausted"
    assert store.get("catalog_cursor") is not None
    assert sum(store.counts()["rows_per_store"].values()) > 0


def test_merged_rows_carry_package_and_own_comparison_price(tmp_path):
    store = CatalogStore(tmp_path / "c.sqlite")
    _step(store, FakePrimat([_row("1088004", 1, price=25.0), _row("1088004", 2, category="Kök")]),
          max_rows=19000)
    merged = catalog_products(store, store_ids=["ica:1088004"],
                              not_before=datetime.now(UTC) - timedelta(days=14))
    assert len(merged) == 1
    row, fetched_at = merged[0]
    assert row["amount"] == 500 and row["unit"] == "g"
    assert row["comparison"] == {"price": 50.0, "unit": "kg"}  # 25 kr for 500 g
    assert fetched_at.tzinfo is not None
    assert catalog_products(store, store_ids=["ica:1088004"],
                            not_before=datetime.now(UTC) + timedelta(minutes=1)) == []


def test_food_categories():
    assert is_food_category("Mejeri & Ost > Yoghurt")
    assert not is_food_category("Skönhet > Hår")
    assert not is_food_category(None)
    assert merge_row({"price": 10}, {"amount": 1, "unit": "kg"})["amount"] == 1


def test_scheduler_adds_the_catalog_job_only_when_enabled(monkeypatch):
    from deploy.scripts.start_cron import scheduled_jobs

    monkeypatch.setenv("DEMAND_REFRESH_ENABLED", "true")
    monkeypatch.delenv("PRIMAT_ICA_CATALOG_ENABLED", raising=False)
    assert ("PRIMAT_ICA_CATALOG_CRON", "run_primat_ica_catalog.py") not in scheduled_jobs()
    monkeypatch.setenv("PRIMAT_ICA_CATALOG_ENABLED", "true")
    assert ("PRIMAT_ICA_CATALOG_CRON", "run_primat_ica_catalog.py") in scheduled_jobs()


@pytest.mark.parametrize("value", ["false", ""])
def test_job_does_nothing_when_disabled(monkeypatch, value, capsys):
    import deploy.scripts.run_primat_ica_catalog as job

    monkeypatch.setenv("PRIMAT_ICA_CATALOG_ENABLED", value)
    assert job.main() == 0
    assert "disabled" in capsys.readouterr().out


def test_an_offer_missing_from_the_latest_offer_pass_is_dropped(tmp_path, monkeypatch):
    import app.services.primat_ica_catalog as module

    store = CatalogStore(tmp_path / "c.sqlite")
    day = [datetime(2026, 11, 24, 6, tzinfo=UTC)]
    clock = lambda: day[0]  # noqa: E731
    on_offer = [_row("1088004", 1, offer=8.0), _row("1088004", 2, offer=5.0)]
    asyncio.run(run_catalog_step(store, FakePrimat(on_offer), cities=["Lund"], max_rows=19000,
                                 sleep=_no_sleep, now=clock))
    asyncio.run(run_catalog_step(store, FakePrimat(on_offer), cities=["Lund"], max_rows=19000,
                                 sleep=_no_sleep, now=clock))  # package details
    day[0] = datetime(2026, 11, 25, 6, tzinfo=UTC)
    still = [_row("1088004", 1, offer=8.0), _row("1088004", 2)]
    fake = FakePrimat(still)
    fake.catalog = still
    # Next day: only the offers pass runs (no budget left for the catalog).
    asyncio.run(run_catalog_step(store, fake, cities=["Lund"], max_rows=200, reserve_rows=0,
                                 sleep=_no_sleep, now=clock))
    merged = {row["product_id"]: row for row, _at in catalog_products(
        store, store_ids=["ica:1088004"], not_before=datetime(2026, 11, 1, tzinfo=UTC))}
    assert merged["p1"]["offer_price"] == 8.0
    assert merged["p2"]["offer_price"] is None


def test_catalog_is_ready_only_after_a_full_round_with_package_details(tmp_path):
    from app.services.primat_ica_catalog import catalog_ready

    store = CatalogStore(tmp_path / "c.sqlite")
    assert not catalog_ready(store, store_ids=["ica:1088004"], min_products=1)
    catalog = [_row("1088004", i) for i in range(3)]
    _step(store, FakePrimat(catalog), max_rows=19000)
    _step(store, FakePrimat(catalog), max_rows=19000)
    assert catalog_ready(store, store_ids=["ica:1088004"], min_products=3)
    assert not catalog_ready(store, store_ids=["ica:1088004"], min_products=4)
