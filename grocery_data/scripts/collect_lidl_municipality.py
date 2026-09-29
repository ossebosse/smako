"""Optional municipality Lidl offers, existing collector/OWN and operation lock."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from grocery_data.app.connectors.lidl.client import LidlClient
from grocery_data.app.connectors.lidl.document_qualification import national_metadata
from grocery_data.app.connectors.lidl.municipal_offers import (
    MunicipalLidlOfferConnector,
)
from grocery_data.app.connectors.lidl.municipality_inventory import approved_lidl_stores, discover
from grocery_data.app.connectors.lidl.parser import LidlParser
from grocery_data.app.domain import GeographicArea, RawBatch, RawFetch
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.scripts.collect_citygross_municipality import _accepted_details


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


async def fetch_bundle(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    client = LidlClient(page_size=108, max_pages=8)
    try:
        listing = await client._request("https://www.lidl.se/c/reklamblad/s10018018", kind="publication_listing")
        soup = BeautifulSoup(listing.payload, "html.parser", from_encoding="utf-8")
        ids = [n.get("data-track-id") for n in soup.select("a[data-track-flyer]")]
        write(output / "listing.json", {"url": listing.url, "observed_at": listing.fetched_at.isoformat(),
                                       "sha256": listing.payload_hash, "publication_ids": ids})
        current = []
        today = datetime.now(UTC).date().isoformat()
        for identity in dict.fromkeys(ids):
            if not identity:
                continue
            candidate = await client._request("https://endpoints.leaflets.schwarz/v4/flyer",
                kind="national_publication", params={"flyer_identifier": identity, "region_id": 0, "store_id": 0})
            try:
                metadata = national_metadata(candidate)
            except (ValueError, KeyError):
                continue
            if metadata['offer_start'] <= today <= metadata['offer_end']:
                current.append(candidate)
        if len(current) != 1:
            raise ValueError("current_national_publication_missing_or_ambiguous")
        publication = current[0]
        write(output / "publication.json", publication.model_dump(mode="json"))
        flyer = publication.json_payload()["flyer"]
        # Single public document request. Never retry an access challenge.
        async with httpx.AsyncClient(timeout=90, follow_redirects=False) as http:
            response = await http.get(flyer["pdfUrl"])
            response.raise_for_status()
            pdf = response.content
        (output / "publication.pdf").write_bytes(pdf)
        write(output / "pdf-source.json", {"url": flyer["pdfUrl"], "observed_at": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(pdf).hexdigest(), "network_requests": 1})
        national_metadata(publication, pdf)
        regional = LidlParser._regional_offer_context(reference=listing.url, requested_city="Sverige")
        catalog = await client.fetch_catalog(regional)
        write(output / "catalog.json", catalog.model_dump(mode="json"))
        return {"catalog": catalog, "publication": publication, "pdf": pdf,
                "mode": "fresh_network", "network_requests": client._request_count + 1}
    finally:
        await client.aclose()


def retained_bundle(path):
    path = Path(path)
    publication = RawFetch.model_validate_json((path / "publication.json").read_bytes())
    pdf = (path / "publication.pdf").read_bytes()
    evidence = json.loads((path / "pdf-source.json").read_bytes())
    if (evidence['url'] != publication.json_payload()['flyer']['pdfUrl']
            or evidence['sha256'] != hashlib.sha256(pdf).hexdigest()):
        raise ValueError('retained_document_acquisition_binding_changed')
    return {"catalog": RawBatch.model_validate_json((path / "catalog.json").read_bytes()),
            "publication": publication, "pdf": pdf, "mode": "replay", "network_requests": 0}


async def collect(inventory, store_ids, output, *, bundle=None):
    approved = approved_lidl_stores(inventory)
    if not set(store_ids).issubset(approved):
        raise ValueError("collection escaped verified municipality")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write(output / "inventory.json", inventory)
    area = GeographicArea.model_validate(inventory["area"])
    report = {"municipality_code": area.municipality_code, "stores": [], "production_activation": False,
              "source_fetch_mode": "no_price_calls", "external_price_requests": 0}
    if store_ids:
        bundle = bundle or await fetch_bundle(output / "source")
        report.update(source_fetch_mode=bundle["mode"], external_price_requests=bundle["network_requests"])
    for identity in sorted(store_ids):
        store = approved[identity]
        directory = output / identity
        directory.mkdir()
        database = directory / "offers.sqlite"
        engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
        create_schema(engine)
        row = {"store_id": identity, "name": store.name, "municipality_status": "inside",
            "source_url": store.source_fields["official_store_url"], "coverage": "offers_only",
            "price_channel": "physical_store_national_campaign", "status": "failed", "own": 0,
            "database": database.relative_to(output).as_posix(), "resolved_database": str(database.resolve())}
        try:
            connector = MunicipalLidlOfferConnector(store=store, registry=inventory["registry"],
                catalog=bundle["catalog"], publication=bundle["publication"], pdf=bundle["pdf"])
            collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(directory / "raw"))
            with RefreshRunLock(production_refresh_lock_path(database, directory / "price-universes")):
                result = await collector.collect_area(connector, area,
                    scope_key=f"municipality:{area.municipality_code}:lidl:{identity}:offer-rows")
            row.update(_accepted_details(database, result))
            row.update(status="success" if result.promoted else "failed", qualification=connector.row_acceptance)
        except Exception as exc:  # noqa: BLE001 - optional per-store failure
            row.update(reason=str(exc), error_type=type(exc).__name__)
        finally:
            engine.dispose()
        report["stores"].append(row)
        write(directory / "result.json", row)
        write(output / "coverage.json", report)
    write(output / "coverage.json", report)
    return report


async def run(args):
    area = GeographicArea(city=municipality_name(args.municipality_code), mode="municipality",
                          municipality_code=args.municipality_code)
    inventory = json.loads(args.inventory.read_bytes()) if args.inventory else await discover(area, args.output / "inventory")
    if inventory["area"] != area.model_dump(mode="json"):
        raise ValueError("inventory municipality mismatch")
    return await collect(inventory, approved_lidl_stores(inventory), args.output / "collection",
                         bundle=retained_bundle(args.replay) if args.replay else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipality-code", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--replay", type=Path)
    result = asyncio.run(run(parser.parse_args()))
    print(json.dumps({"municipality": result["municipality_code"], "stores": [
        {k: r.get(k) for k in ("store_id", "status", "own", "reason")} for r in result["stores"]]}))


if __name__ == "__main__":
    main()
