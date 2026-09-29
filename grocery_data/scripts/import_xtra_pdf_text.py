"""Isolated import of an already observed, hash-bound official X:-tra PDF.

Never renews source observation, fetches images, calls models or activates beta.
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI

from grocery_data.app.api import catalog_router
from grocery_data.app.connectors.coop.xtra_pdf import POLICY, XtraTextOfferConnector
from grocery_data.app.domain import GeographicArea, RawBatch, RawFetch, SourceStore
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory


async def run(inventory_path, metadata_path, pdf_path, output):
    # Backend path is configured by the usual PYTHONPATH=backend;. caller.
    from app.models.ingredient import NormalizedIngredient
    from app.providers.own import OwnGroceryPriceProvider
    from app.services.basket_auditor import BasketAuditor
    from app.services.basket_calculator import BasketCalculator
    from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
    from app.services.product_matcher import ProductMatcher
    from app.services.user_pricing import price_candidate_for_context

    from grocery_data.app.domain.promotion_pricing import UserPricingContext

    if output.exists():
        raise ValueError("refusing to overwrite existing work")
    started = perf_counter()
    inventory = json.loads(inventory_path.read_bytes())
    meta = json.loads(metadata_path.read_bytes())
    from grocery_data.app.services.area_membership import approved_municipal_stores

    if meta["store_id"] not in approved_municipal_stores(inventory, concepts=("X:-tra",)):
        raise ValueError("PDF store is not bound to requested municipality")
    row = next(r for r in inventory["stores"] if r["store"]["external_id"] == meta["store_id"])
    if row["geographic_evidence"]["status"] != "inside" or row["store"]["source_fields"].get(
        "identity_conflict"
    ):
        raise ValueError("store not approved by supplied municipality inventory")
    store = SourceStore.model_validate(row["store"])
    store = store.model_copy(
        update={
            "source_fields": {
                **store.source_fields,
                "offer_policy": POLICY,
                "pdf_sha256": meta["sha256"],
                "pdf_observed_at": meta["observed_at"],
                "pdf_pages": meta["document_pages"],
            }
        }
    )
    doc = RawFetch(
        chain="coop",
        store_external_id=store.external_id,
        kind="xtra_pdf",
        method="GET",
        url=meta["source_url"],
        fetched_at=datetime.fromisoformat(meta["observed_at"]),
        http_status=200,
        content_type="application/pdf",
        payload=pdf_path.read_bytes(),
        connector_version="retained-official-xtra-pdf-v1",
    )
    if doc.payload_hash != meta["sha256"]:
        raise ValueError("retained PDF bytes do not match observed source")
    # Stale stored observations are regression evidence, not current acceptance.
    now = datetime.now(ZoneInfo("Europe/Stockholm"))
    age = (now - doc.fetched_at).total_seconds() / 3600
    if age < 0 or age >= 48:
        raise ValueError("source outside unchanged 48h current acceptance window")
    source = store.source_fields["coordinate_source"]
    locator = RawBatch(
        chain="coop",
        documents=(
            RawFetch(
                chain="coop",
                kind="xtra_registry",
                method="GET",
                url=source["url"],
                fetched_at=datetime.fromisoformat(source["observed_at"]),
                http_status=200,
                content_type="application/json",
                payload=store.model_dump_json().encode(),
                connector_version="retained-registry-v1",
            ),
        ),
    )
    offers = RawBatch(chain="coop", documents=(doc,))
    connector = XtraTextOfferConnector(store=store, locator=locator, offers=offers)
    output.mkdir(parents=True)
    db = output / "own.sqlite"
    engine = create_database_engine("sqlite:///" + db.resolve().as_posix())
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        with RefreshRunLock(production_refresh_lock_path(db, output / "price-universes")):
            collector = GroceryCollector(factory, FilesystemRawSnapshotStore(output / "raw"))
            result = await collector.collect_area(
                connector,
                GeographicArea(city=store.city),
                scope_key=f"{store.city.casefold()}:coop:{store.external_id}:xtra-text:offer-rows",
            )
            report = connector.layout_report
            report.update(
                production_activation=False,
                external_network_calls=0,
                source_mode="retained_official_observation_not_new_collection",
                verification_at=now.isoformat(),
                source_age_hours=round(age, 3),
                full_snapshot_status=result.status.value,
                partial_promoted=result.promoted,
                metrics=result.metrics.model_dump(mode="json"),
                qualification=connector.row_acceptance,
            )
            (output / "source-products.json").write_text(
                connector.extracted.model_dump_json(indent=2), encoding="utf-8"
            )
            app = FastAPI()
            app.state.session_factory = factory
            app.include_router(catalog_router)
            async with httpx.AsyncClient(
                base_url="http://isolated-own.test", transport=httpx.ASGITransport(app=app)
            ) as client:
                own = OwnGroceryPriceProvider(
                    "http://isolated-own.test",
                    client=client,
                    include_offers_only=True,
                    include_conditional_offer_products=True,
                )
                response = await client.get("/stores", params={"chain": "coop", "city": store.city})
                response.raise_for_status()
                target = next(
                    (s for s in response.json()["stores"] if s["external_id"] == store.external_id),
                    None,
                )
                products = await own.get_offers(target["id"]) if target else []
                key = PriceUniverseKey.create(
                    city=inventory["area"]["city"],
                    snapshot_ids=[result.snapshot_id],
                    source_strategy_version=POLICY+":municipality:"+inventory["area"]["municipality_code"],
                    normalizer_version="product-normalizer-v3-recipe-taxonomy",
                    taxonomy_version="existing-taxonomy-v1",
                )
                universe = PriceUniverseBuilder().build(key, products)
                (output / "price-universe.json").write_text(
                    universe.model_dump_json(indent=2), encoding="utf-8"
                )
                report["price_universe_id"] = universe.universe_id
                report["price_universe_count"] = len(universe.products)
                report["own_projected"] = len(products)
                report["proofs"] = []
                # Verification sample only. Parser/import have no product list.
                for title, target_food in [
                    ("Couscous", "couscous"),
                    ("Ekologisk tomatpuré", "tomatpuré"),
                    ("Gul lök i nät", "gul lök"),
                    ("Flytande honung", "honung"),
                ]:
                    p = next((p for p in universe.products if p.name == title), None)
                    if p is None:
                        report["proofs"].append(
                            {"name": title, "blocker": "not_projected_to_price_universe"}
                        )
                        continue
                    offer = p.offers[0]
                    need = NormalizedIngredient(
                        canonical_name=target_food,
                        required_quantity=p.package_quantity * offer.required_packages,
                        unit=p.package_unit,
                    )
                    matches = ProductMatcher().match(need, [p])
                    if len(matches) != 1:
                        report["proofs"].append(
                            {
                                "name": title,
                                "blocker": "ingredient_match_rejected",
                                "canonical_name": p.canonical_name,
                            }
                        )
                        continue
                    candidate = price_candidate_for_context(
                        matches[0], UserPricingContext(), on_date=now.date()
                    )
                    item = BasketCalculator().calculate_item(need, candidate)
                    audit = BasketAuditor(pantry_items=frozenset()).audit(
                        [need], [item], user_pricing_context=UserPricingContext()
                    )
                    assert p.price is None and item.regular_total_price is None
                    report["proofs"].append(
                        {
                            "name": title,
                            "ingredient": need.model_dump(mode="json"),
                            "item": item.model_dump(mode="json"),
                            "audit": audit.model_dump(mode="json"),
                        }
                    )
                accepted = set(connector.row_acceptance["accepted_ids"])
                for page in report["pages"]:
                    for ad in page["ads"]:
                        ad["own"] = ad["source_product_id"] in accepted and result.promoted
                        # Offer IDs are preserved in campaign evidence through the provider.
                        matching = [
                            p
                            for p in universe.products
                            if any(
                                o.campaign_evidence
                                and o.campaign_evidence.offer_id == ad["source_product_id"]
                                for o in p.offers
                            )
                        ]
                        ad["price_universe_product_ids"] = [p.product_id for p in matching]
                        ad["status"] = "imported" if ad["own"] else "blocked"
                        ad["period_status"] = (
                            "future"
                            if date_from(ad["valid_from"]) > now.date()
                            else "expired"
                            if date_from(ad["valid_to"]) < now.date()
                            else "current"
                        )
                        ad["planning"] = "not_nutrition_qualified"
            report["runtime_seconds"] = round(perf_counter() - started, 3)
            (output / "result.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(
                json.dumps(
                    {
                        "own": result.metrics.products_parsed,
                        "pu": len(products),
                        "quarantined": result.metrics.products_quarantined,
                        "proofs": [
                            {k: v for k, v in p.items() if k not in ["item", "ingredient", "audit"]}
                            | {"audit_pass": p.get("audit", {}).get("passed")}
                            for p in report["proofs"]
                        ],
                        "seconds": report["runtime_seconds"],
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        engine.dispose()
    return report


def date_from(value):
    return datetime.fromisoformat(value).date()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for name in ["inventory", "source-metadata", "pdf", "output"]:
        p.add_argument("--" + name, required=True, type=Path)
    a = p.parse_args()
    asyncio.run(run(a.inventory, a.source_metadata, a.pdf, a.output))
